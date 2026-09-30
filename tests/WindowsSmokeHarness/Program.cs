/*
 * [INPUT]: 依赖 System.Diagnostics, System.IO.Compression, System.Security.Cryptography, System.Text, System.Text.Json, System.Xml, System.Xml.Linq
 * [OUTPUT]: 提供隔离的 UTF-8、完整 ZIP CRC、标题/内容/表格/缩进语义及包未改写的冒烟报告
 * [POS]: 验证层-Windows 发行包语义门禁；编译通过不能替代 Windows 原生实际运行
 * [PROTOCOL]: 修改时更新此头部,然后检查上级 FOLDER_INDEX.md
 */
using System.Diagnostics;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Xml;
using System.Xml.Linq;

const string packName = "Windows 冒烟格式 Ω";
XNamespace word = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
string? reportPath = null;

try
{
    var options = ParseOptions(args);
    var packageDirectory = FullPath(options, "--package-root", AppContext.BaseDirectory);
    var fixtureDirectory = FullPath(options, "--fixture-root", Path.Combine(AppContext.BaseDirectory, "smoke-fixtures"));
    var workDirectory = FullPath(options, "--work-root", Path.Combine(Path.GetTempPath(), "forma-windows-smoke-" + Guid.NewGuid().ToString("N")));
    var requestedReportPath = FullPath(options, "--report-path", Path.Combine(workDirectory, "windows-smoke-report.json"));
    RequireOutsidePackage(workDirectory, packageDirectory);
    RequireOutsidePackage(requestedReportPath, packageDirectory);
    if (File.Exists(requestedReportPath))
    {
        throw new IOException("冒烟报告已存在，拒绝覆盖。");
    }
    reportPath = requestedReportPath;
    if (Directory.Exists(workDirectory) && Directory.EnumerateFileSystemEntries(workDirectory).Any())
    {
        throw new IOException("冒烟工作目录必须为空，拒绝改写现有文件。");
    }
    Directory.CreateDirectory(workDirectory);

    var pythonPath = Path.Combine(packageDirectory, "runtime", "python.exe");
    var managerPath = Path.Combine(packageDirectory, "resources", "style_pack_manager.py");
    var sourcePath = Path.Combine(fixtureDirectory, "source-no-table.docx");
    var originalTargetPath = Path.Combine(fixtureDirectory, "target.docx");
    var targetPath = Path.Combine(workDirectory, "目标文档-中文Ω.docx");
    var packPath = Path.Combine(workDirectory, "Windows-冒烟格式.wfstyle");
    var outputPath = Path.Combine(workDirectory, "输出文档-中文Ω.docx");
    foreach (var path in new[] { pythonPath, managerPath, sourcePath, originalTargetPath })
    {
        RequireFile(path);
    }
    var packageHashesBefore = HashDirectory(packageDirectory);
    var sourceHashBefore = HashFile(sourcePath);
    var targetHashBefore = HashFile(originalTargetPath);
    var runtime = await RunPythonAsync(pythonPath, workDirectory, [
        "-B", "-X", "utf8", "-c",
        "import json, sys, lxml; print(json.dumps({'python':sys.version.split()[0], 'lxml':lxml.__version__, 'platform':sys.platform}))"
    ]);
    using var runtimeJson = JsonDocument.Parse(runtime.StandardOutput);
    if (runtimeJson.RootElement.GetProperty("python").GetString() != "3.14.6" || runtimeJson.RootElement.GetProperty("lxml").GetString() != "6.1.1")
    {
        throw new InvalidDataException("包内 Python/lxml 版本与构建锁定版本不一致。");
    }

    var crcInputEntries = await ValidateZipCrcAsync(pythonPath, workDirectory, [sourcePath, originalTargetPath]);
    var originalTarget = ReadXmlPackage(originalTargetPath);
    var outlinedHeadingText = PrepareTarget(originalTargetPath, targetPath, originalTarget["word/document.xml"], word);
    var target = ReadXmlPackage(targetPath);
    var created = await RunPythonAsync(pythonPath, workDirectory, [
        "-B", "-X", "utf8", managerPath,
        "create-pack", "--source", sourcePath, "--out", packPath,
        "--name", packName, "--force"
    ]);
    using var createdJson = RequireOkJson(created.StandardOutput, "create-pack");
    var pack = createdJson.RootElement.GetProperty("pack");
    if (pack.GetProperty("name").GetString() != packName)
    {
        throw new InvalidDataException("中文/Unicode 格式库名称没有完整通过 UTF-8 JSON 往返。");
    }
    var expectedHeading2Style = pack.GetProperty("heading_authorities").GetProperty("1").GetString();
    var applied = await RunPythonAsync(pythonPath, workDirectory, [
        "-B", "-X", "utf8", managerPath,
        "apply-pack", "--pack", packPath, "--target", targetPath,
        "--out", outputPath, "--force"
    ]);
    using var appliedJson = RequireOkJson(applied.StandardOutput, "apply-pack");
    if (!Path.GetFullPath(appliedJson.RootElement.GetProperty("output").GetString()!).Equals(outputPath, PathComparison()))
    {
        throw new InvalidDataException("生成文档的中文/Unicode 路径没有完整通过 UTF-8 JSON 往返。");
    }
    var crcOutputEntries = await ValidateZipCrcAsync(pythonPath, workDirectory, [targetPath, packPath, outputPath]);
    var output = ReadXmlPackage(outputPath);
    foreach (var required in new[] { "[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml" })
    {
        if (!output.ContainsKey(required))
        {
            throw new InvalidDataException($"生成文档缺少 {required}。");
        }
    }
    var storyParts = target.Keys.Where(IsStoryPart).ToArray();
    foreach (var name in storyParts)
    {
        if (!output.TryGetValue(name, out var document) || !Text(target[name], word).SequenceEqual(Text(document, word), StringComparer.Ordinal))
        {
            throw new InvalidDataException($"目标内容发生变化：{name}。");
        }
    }
    var targetDocument = target["word/document.xml"];
    var outputDocument = output["word/document.xml"];
    var targetTables = targetDocument.Descendants(word + "tbl").ToArray();
    var outputTables = outputDocument.Descendants(word + "tbl").ToArray();
    if (targetTables.Length == 0 || outputTables.Length != targetTables.Length)
    {
        throw new InvalidDataException("目标表格丢失或数量发生变化。");
    }
    for (var index = 0; index < targetTables.Length; index++)
    {
        var before = targetTables[index];
        var after = outputTables[index];
        foreach (var tag in new[] { "tr", "tc", "p" })
        {
            if (before.Descendants(word + tag).Count() != after.Descendants(word + tag).Count())
            {
                throw new InvalidDataException($"表格 {index + 1} 的 {tag} 数量发生变化。");
            }
        }
        foreach (var tag in new[] { "tblGrid", "trPr", "tcPr" })
        {
            var beforeProperties = before.Descendants(word + tag).Select(NormalizedXml).ToArray();
            var afterProperties = after.Descendants(word + tag).Select(NormalizedXml).ToArray();
            if (!beforeProperties.SequenceEqual(afterProperties, StringComparer.Ordinal))
            {
                throw new InvalidDataException($"无表格模板改变了表格 {index + 1} 的 {tag}。");
            }
        }
    }
    var cleanedIndent = outputTables[0].Descendants(word + "p").First().Element(word + "pPr")?.Element(word + "ind");
    if ((string?)cleanedIndent?.Attribute(word + "firstLineChars") != "0" || (string?)cleanedIndent?.Attribute(word + "firstLine") != "0")
    {
        throw new InvalidDataException("表格中的两字符首行缩进没有被清零。");
    }
    if ((string?)cleanedIndent.Attribute(word + "left") != "240" || (string?)cleanedIndent.Attribute(word + "right") != "120")
    {
        throw new InvalidDataException("清除两字符首行缩进时改变了表格段落的左右缩进。");
    }
    var mappedHeading = outputDocument.Descendants(word + "p").Single(paragraph => string.Concat(Text(paragraph, word)) == outlinedHeadingText);
    if ((string?)mappedHeading.Element(word + "pPr")?.Element(word + "pStyle")?.Attribute(word + "val") != expectedHeading2Style)
    {
        throw new InvalidDataException("仅设置大纲级别的标题没有应用模板标题二样式。");
    }
    var mediaCount = VerifyMediaPreserved(targetPath, outputPath);
    if (!packageHashesBefore.SequenceEqual(HashDirectory(packageDirectory)) || sourceHashBefore != HashFile(sourcePath) || targetHashBefore != HashFile(originalTargetPath))
    {
        throw new InvalidDataException("冒烟测试改写了发行包或原始测试材料。");
    }
    WriteReport(reportPath, new
    {
        smoke_schema = "forma.windows-smoke.v2",
        ok = true,
        runtime = runtimeJson.RootElement.Clone(),
        architecture = System.Runtime.InteropServices.RuntimeInformation.ProcessArchitecture.ToString(),
        operating_system = System.Runtime.InteropServices.RuntimeInformation.OSDescription,
        operating_system_family = OperatingSystem.IsWindows() ? "Windows" : "Other",
        full_zip_crc_entries = crcInputEntries + crcOutputEntries,
        all_xml_parts_parsed = output.Count,
        content_story_parts_preserved = storyParts.Length,
        table_count_preserved = outputTables.Length,
        media_parts_preserved = mediaCount,
        table_two_character_indent_cleared = true,
        outline_only_heading_mapped = true,
        unicode_json_roundtrip = true,
        package_files_unchanged = true,
        output_bytes = new FileInfo(outputPath).Length,
        completed_at_utc = DateTimeOffset.UtcNow
    });
}
catch (Exception exception)
{
    if (reportPath is not null)
    {
        WriteReport(reportPath, new { smoke_schema = "forma.windows-smoke.v2", ok = false, error = exception.ToString(), completed_at_utc = DateTimeOffset.UtcNow });
    }
    Environment.ExitCode = 1;
}

static Dictionary<string, string> ParseOptions(string[] values)
{
    var allowed = new HashSet<string>(["--package-root", "--fixture-root", "--work-root", "--report-path"], StringComparer.Ordinal);
    var result = new Dictionary<string, string>(StringComparer.Ordinal);
    for (var index = 0; index < values.Length; index += 2)
    {
        if (index + 1 >= values.Length || !allowed.Contains(values[index]) || !result.TryAdd(values[index], values[index + 1]))
        {
            throw new ArgumentException("冒烟工具参数无效或重复。");
        }
    }
    return result;
}

static string FullPath(Dictionary<string, string> options, string name, string fallback) => Path.GetFullPath(options.GetValueOrDefault(name, fallback));
static StringComparison PathComparison() => OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;

static void RequireOutsidePackage(string path, string packageDirectory)
{
    var prefix = Path.TrimEndingDirectorySeparator(packageDirectory) + Path.DirectorySeparatorChar;
    if (path.Equals(Path.TrimEndingDirectorySeparator(packageDirectory), PathComparison()) || path.StartsWith(prefix, PathComparison()))
    {
        throw new ArgumentException("冒烟工作目录和报告不能放入发行包。");
    }
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
        StandardOutputEncoding = new UTF8Encoding(false, true),
        StandardErrorEncoding = new UTF8Encoding(false, true)
    };
    startInfo.Environment["PYTHONUTF8"] = "1";
    startInfo.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
    startInfo.Environment["PYTHONNOUSERSITE"] = "1";
    foreach (var argument in arguments)
    {
        startInfo.ArgumentList.Add(argument);
    }
    using var process = Process.Start(startInfo) ?? throw new InvalidOperationException("无法启动包内 Python。");
    var outputTask = process.StandardOutput.ReadToEndAsync();
    var errorTask = process.StandardError.ReadToEndAsync();
    using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(120));
    try
    {
        await process.WaitForExitAsync(deadline.Token);
    }
    catch (OperationCanceledException)
    {
        process.Kill(entireProcessTree: true);
        throw new TimeoutException("包内 Python 冒烟操作超过 120 秒。");
    }
    var result = new ProcessResult(process.ExitCode, await outputTask, await errorTask);
    if (result.ExitCode != 0)
    {
        throw new InvalidOperationException($"Python 退出码 {result.ExitCode}：{result.StandardError}\n{result.StandardOutput}");
    }
    return result;
}

static async Task<int> ValidateZipCrcAsync(string pythonPath, string workingDirectory, IEnumerable<string> paths)
{
    const string check = "import json, sys, zipfile\ncount=0\nfor path in sys.argv[1:]:\n with zipfile.ZipFile(path) as package:\n  bad=package.testzip()\n  if bad is not None: raise RuntimeError('ZIP CRC failed: '+bad)\n  count += len(package.infolist())\nprint(json.dumps({'entries':count}))";
    var result = await RunPythonAsync(pythonPath, workingDirectory, new[] { "-B", "-X", "utf8", "-c", check }.Concat(paths));
    using var document = JsonDocument.Parse(result.StandardOutput);
    return document.RootElement.GetProperty("entries").GetInt32();
}

static Dictionary<string, XDocument> ReadXmlPackage(string path)
{
    using var package = ZipFile.OpenRead(path);
    var result = new Dictionary<string, XDocument>(StringComparer.Ordinal);
    var names = new HashSet<string>(StringComparer.Ordinal);
    foreach (var entry in package.Entries)
    {
        if (!names.Add(entry.FullName))
        {
            throw new InvalidDataException("文档包含重复 ZIP 部件。");
        }
        if (!entry.FullName.EndsWith(".xml", StringComparison.OrdinalIgnoreCase) && !entry.FullName.EndsWith(".rels", StringComparison.OrdinalIgnoreCase))
        {
            continue;
        }
        using var stream = entry.Open();
        using var reader = XmlReader.Create(stream, new XmlReaderSettings { DtdProcessing = DtdProcessing.Prohibit, XmlResolver = null });
        result.Add(entry.FullName, XDocument.Load(reader, LoadOptions.PreserveWhitespace));
    }
    return result;
}

static string PrepareTarget(string originalPath, string destination, XDocument document, XNamespace word)
{
    var tableParagraph = document.Descendants(word + "tbl").First().Descendants(word + "p").First();
    var tableProperties = EnsureParagraphProperties(tableParagraph, word);
    var indent = tableProperties.Element(word + "ind");
    if (indent is null)
    {
        indent = new XElement(word + "ind");
        tableProperties.Add(indent);
    }
    indent.SetAttributeValue(word + "firstLineChars", "200");
    indent.SetAttributeValue(word + "firstLine", "420");
    indent.SetAttributeValue(word + "left", "240");
    indent.SetAttributeValue(word + "right", "120");
    var heading = document.Descendants(word + "p").First(paragraph => !paragraph.Ancestors(word + "tbl").Any() && (string?)paragraph.Element(word + "pPr")?.Element(word + "pStyle")?.Attribute(word + "val") == "Heading2");
    var headingProperties = EnsureParagraphProperties(heading, word);
    headingProperties.Element(word + "pStyle")!.Remove();
    headingProperties.Elements(word + "outlineLvl").Remove();
    headingProperties.Add(new XElement(word + "outlineLvl", new XAttribute(word + "val", "1")));
    using var input = ZipFile.OpenRead(originalPath);
    using var file = new FileStream(destination, FileMode.CreateNew);
    using var output = new ZipArchive(file, ZipArchiveMode.Create);
    foreach (var entry in input.Entries)
    {
        var replacement = output.CreateEntry(entry.FullName, CompressionLevel.Optimal);
        replacement.LastWriteTime = entry.LastWriteTime;
        using var outputStream = replacement.Open();
        if (entry.FullName == "word/document.xml")
        {
            using var writer = XmlWriter.Create(outputStream, new XmlWriterSettings { Encoding = new UTF8Encoding(false), Indent = false });
            document.Save(writer);
        }
        else
        {
            using var inputStream = entry.Open();
            inputStream.CopyTo(outputStream);
        }
    }
    return string.Concat(Text(heading, word));
}

static XElement EnsureParagraphProperties(XElement paragraph, XNamespace word)
{
    var properties = paragraph.Element(word + "pPr");
    if (properties is not null)
    {
        return properties;
    }
    properties = new XElement(word + "pPr");
    paragraph.AddFirst(properties);
    return properties;
}

static IEnumerable<string> Text(XContainer node, XNamespace word) => node.Descendants(word + "t").Select(text => text.Value);
static bool IsStoryPart(string name) => name == "word/document.xml" || name == "word/footnotes.xml" || name == "word/endnotes.xml" || name == "word/comments.xml" || (name.StartsWith("word/header", StringComparison.Ordinal) || name.StartsWith("word/footer", StringComparison.Ordinal)) && name.EndsWith(".xml", StringComparison.Ordinal);

static string NormalizedXml(XElement element)
{
    var copy = new XElement(element);
    foreach (var attribute in copy.DescendantsAndSelf().Attributes().Where(attribute => attribute.IsNamespaceDeclaration).ToArray())
    {
        attribute.Remove();
    }
    return copy.ToString(SaveOptions.DisableFormatting);
}

static int VerifyMediaPreserved(string targetPath, string outputPath)
{
    using var target = ZipFile.OpenRead(targetPath);
    using var output = ZipFile.OpenRead(outputPath);
    var count = 0;
    foreach (var media in target.Entries.Where(entry => entry.FullName.StartsWith("word/media/", StringComparison.Ordinal) && !entry.FullName.EndsWith('/')))
    {
        var destination = output.GetEntry(media.FullName) ?? throw new InvalidDataException("目标图片丢失。");
        using var sourceStream = media.Open();
        using var destinationStream = destination.Open();
        if (!SHA256.HashData(sourceStream).SequenceEqual(SHA256.HashData(destinationStream)))
        {
            throw new InvalidDataException("目标图片内容发生变化。");
        }
        count++;
    }
    return count;
}

static JsonDocument RequireOkJson(string value, string operation)
{
    var document = JsonDocument.Parse(value);
    if (!document.RootElement.TryGetProperty("ok", out var ok) || !ok.GetBoolean())
    {
        document.Dispose();
        throw new InvalidDataException($"{operation} 没有返回 ok=true：{value}");
    }
    return document;
}

static string HashFile(string path)
{
    using var stream = File.OpenRead(path);
    return Convert.ToHexString(SHA256.HashData(stream));
}

static KeyValuePair<string, string>[] HashDirectory(string directory) => Directory.EnumerateFiles(directory, "*", SearchOption.AllDirectories)
    .Select(path => new KeyValuePair<string, string>(Path.GetRelativePath(directory, path), HashFile(path)))
    .OrderBy(pair => pair.Key, StringComparer.Ordinal).ToArray();

static void RequireFile(string path)
{
    if (!File.Exists(path))
    {
        throw new FileNotFoundException("缺少冒烟测试文件。", path);
    }
}

static void WriteReport(string path, object report)
{
    Directory.CreateDirectory(Path.GetDirectoryName(path)!);
    File.WriteAllText(path, JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }), new UTF8Encoding(false));
}

internal sealed record ProcessResult(int ExitCode, string StandardOutput, string StandardError);
