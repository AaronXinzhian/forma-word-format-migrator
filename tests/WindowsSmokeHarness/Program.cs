using System.Diagnostics;
using System.IO.Compression;
using System.Text;
using System.Text.Json;

var baseDirectory = AppContext.BaseDirectory;
var reportPath = Path.Combine(baseDirectory, "windows-smoke-report.json");
var fixtureDirectory = Path.Combine(baseDirectory, "smoke-fixtures");
var pythonPath = Path.Combine(baseDirectory, "runtime", "python.exe");
var managerPath = Path.Combine(baseDirectory, "resources", "style_pack_manager.py");
var sourcePath = Path.Combine(fixtureDirectory, "source-no-table.docx");
var targetPath = Path.Combine(fixtureDirectory, "target.docx");
var packPath = Path.Combine(fixtureDirectory, "windows-smoke.wfstyle");
var outputPath = Path.Combine(fixtureDirectory, "windows-smoke-output.docx");

try
{
    RequireFile(pythonPath);
    RequireFile(managerPath);
    RequireFile(sourcePath);
    RequireFile(targetPath);
    DeleteIfPresent(packPath);
    DeleteIfPresent(outputPath);

    var version = await RunPythonAsync(pythonPath, baseDirectory, [
        "-B", "-X", "utf8", "-c", "import sys, lxml; print(sys.version.split()[0] + ' / lxml ' + lxml.__version__)"
    ]);
    var created = await RunPythonAsync(pythonPath, Path.GetDirectoryName(managerPath)!, [
        "-B", "-X", "utf8", managerPath,
        "create-pack", "--source", sourcePath, "--out", packPath,
        "--name", "Windows smoke", "--force"
    ]);
    RequireOkJson(created.StandardOutput, "create-pack");

    var applied = await RunPythonAsync(pythonPath, Path.GetDirectoryName(managerPath)!, [
        "-B", "-X", "utf8", managerPath,
        "apply-pack", "--pack", packPath, "--target", targetPath,
        "--out", outputPath, "--force"
    ]);
    RequireOkJson(applied.StandardOutput, "apply-pack");

    using (var package = ZipFile.OpenRead(outputPath))
    {
        var names = package.Entries.Select(entry => entry.FullName).ToHashSet(StringComparer.Ordinal);
        if (!names.Contains("word/document.xml") || !names.Contains("word/styles.xml"))
        {
            throw new InvalidDataException("生成文档缺少 document.xml 或 styles.xml。");
        }
    }

    WriteReport(reportPath, new
    {
        ok = true,
        runtime = version.StandardOutput.Trim(),
        architecture = System.Runtime.InteropServices.RuntimeInformation.ProcessArchitecture.ToString(),
        operating_system = System.Runtime.InteropServices.RuntimeInformation.OSDescription,
        pack_created = File.Exists(packPath),
        output_created = File.Exists(outputPath),
        output_bytes = new FileInfo(outputPath).Length,
        create_json_utf8 = created.StandardOutput.Contains("Windows smoke", StringComparison.Ordinal),
        completed_at = DateTimeOffset.Now
    });
}
catch (Exception exception)
{
    WriteReport(reportPath, new
    {
        ok = false,
        error = exception.ToString(),
        completed_at = DateTimeOffset.Now
    });
    Environment.ExitCode = 1;
}

static async Task<ProcessResult> RunPythonAsync(string pythonPath, string workingDirectory, IEnumerable<string> arguments)
{
    var startInfo = new ProcessStartInfo
    {
        FileName = pythonPath,
        WorkingDirectory = workingDirectory,
        UseShellExecute = false,
        CreateNoWindow = true,
        RedirectStandardOutput = true,
        RedirectStandardError = true,
        StandardOutputEncoding = new UTF8Encoding(false),
        StandardErrorEncoding = new UTF8Encoding(false)
    };
    foreach (var argument in arguments)
    {
        startInfo.ArgumentList.Add(argument);
    }

    using var process = Process.Start(startInfo) ?? throw new InvalidOperationException("无法启动 Windows Python。");
    var outputTask = process.StandardOutput.ReadToEndAsync();
    var errorTask = process.StandardError.ReadToEndAsync();
    await process.WaitForExitAsync();
    var result = new ProcessResult(process.ExitCode, await outputTask, await errorTask);
    if (result.ExitCode != 0)
    {
        throw new InvalidOperationException($"Python 退出码 {result.ExitCode}：{result.StandardError}\n{result.StandardOutput}");
    }

    return result;
}

static void RequireOkJson(string value, string operation)
{
    using var document = JsonDocument.Parse(value);
    if (!document.RootElement.TryGetProperty("ok", out var ok) || !ok.GetBoolean())
    {
        throw new InvalidDataException($"{operation} 没有返回 ok=true：{value}");
    }
}

static void RequireFile(string path)
{
    if (!File.Exists(path))
    {
        throw new FileNotFoundException("缺少冒烟测试文件。", path);
    }
}

static void DeleteIfPresent(string path)
{
    if (File.Exists(path))
    {
        File.Delete(path);
    }
}

static void WriteReport(string path, object report)
{
    File.WriteAllText(
        path,
        JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }),
        new UTF8Encoding(false));
}

internal sealed record ProcessResult(int ExitCode, string StandardOutput, string StandardError);
