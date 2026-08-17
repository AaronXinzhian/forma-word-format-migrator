using System.Diagnostics;
using System.Text;
using System.Text.Json;
using FormaFushi.Windows.Generated;

namespace FormaFushi.Windows;

internal static class PythonBridge
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static async Task<ManagerEnvelope> RunAsync(IEnumerable<string> arguments, CancellationToken cancellationToken = default)
    {
        var baseDirectory = AppContext.BaseDirectory;
        var pythonPath = Path.Combine(baseDirectory, "runtime", "python.exe");
        var resourcesDirectory = Path.Combine(baseDirectory, "resources");
        var managerPath = Path.Combine(resourcesDirectory, "style_pack_manager.py");

        if (!File.Exists(pythonPath))
        {
            throw new AppFailure(UIStrings.Errors.RuntimeMissing);
        }

        if (!File.Exists(managerPath))
        {
            throw new AppFailure(UIStrings.Errors.ManagerMissing);
        }

        var startInfo = new ProcessStartInfo
        {
            FileName = pythonPath,
            WorkingDirectory = resourcesDirectory,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = new UTF8Encoding(false),
            StandardErrorEncoding = new UTF8Encoding(false)
        };
        startInfo.ArgumentList.Add("-B");
        startInfo.ArgumentList.Add("-X");
        startInfo.ArgumentList.Add("utf8");
        startInfo.ArgumentList.Add(managerPath);
        foreach (var argument in arguments)
        {
            startInfo.ArgumentList.Add(argument);
        }

        startInfo.Environment["PYTHONIOENCODING"] = "utf-8";
        startInfo.Environment["PYTHONUTF8"] = "1";
        startInfo.Environment["PYTHONDONTWRITEBYTECODE"] = "1";

        using var process = new Process { StartInfo = startInfo };
        try
        {
            if (!process.Start())
            {
                throw new AppFailure(UIStrings.Errors.ManagerLaunchFailedPlain);
            }
        }
        catch (AppFailure)
        {
            throw;
        }
        catch (Exception exception)
        {
            throw new AppFailure(UIStrings.Errors.ManagerLaunchFailed(exception.Message));
        }

        using var cancellationRegistration = cancellationToken.Register(
            static state => TryKill((Process)state!),
            process);
        var outputTask = process.StandardOutput.ReadToEndAsync(cancellationToken);
        var errorTask = process.StandardError.ReadToEndAsync(cancellationToken);
        try
        {
            await process.WaitForExitAsync(cancellationToken);
        }
        catch (OperationCanceledException)
        {
            TryKill(process);
            throw;
        }

        var output = (await outputTask).Trim();
        var error = (await errorTask).Trim();
        if (string.IsNullOrWhiteSpace(output))
        {
            throw new AppFailure(string.IsNullOrWhiteSpace(error)
                ? UIStrings.Errors.EmptyResult
                : UIStrings.Errors.TransferFailedDetail(error));
        }

        ManagerEnvelope? envelope;
        try
        {
            envelope = JsonSerializer.Deserialize<ManagerEnvelope>(output, JsonOptions);
        }
        catch (JsonException)
        {
            throw new AppFailure(string.IsNullOrWhiteSpace(error)
                ? UIStrings.Errors.UnreadableResult
                : UIStrings.Errors.UnreadableResultDetail(error));
        }

        if (envelope is null)
        {
            throw new AppFailure(UIStrings.Errors.UnreadableResult);
        }

        envelope.Pack?.Normalize();
        if (envelope.Packs is not null)
        {
            foreach (var pack in envelope.Packs)
            {
                pack.Normalize();
            }
        }

        if (!envelope.Ok)
        {
            throw new AppFailure(envelope.Error ?? UIStrings.Errors.TransferFailed);
        }

        if (process.ExitCode != 0)
        {
            throw new AppFailure(envelope.Error ?? UIStrings.Errors.ManagerExit);
        }

        return envelope;
    }

    private static void TryKill(Process process)
    {
        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }
        }
        catch
        {
            // The process may already have ended or be unavailable during shutdown.
        }
    }
}
