using System.Diagnostics;
using FormaFushi.Windows.Generated;

namespace FormaFushi.Windows;

internal sealed partial class MainForm : Form
{
    private readonly string _libraryDirectory;
    private readonly List<PackManifest> _packs = [];
    private PackManifest? _selectedPack;
    private string? _targetPath;
    private string? _outputPath;
    private int _currentStep = 1;
    private CancellationTokenSource? _activeOperation;

    public MainForm()
    {
        var environmentPath = Environment.GetEnvironmentVariable("WORD_FORMAT_LIBRARY_DIR")?.Trim();
        _libraryDirectory = !string.IsNullOrWhiteSpace(environmentPath)
            ? Path.GetFullPath(environmentPath)
            : Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "FormaFushi",
                "style-packs");

        InitializeLayout();
        Shown += async (_, _) => await ReloadLibraryAsync();
    }

    private async Task ReloadLibraryAsync(string? preferredIdentity = null, bool showProgress = true)
    {
        if (showProgress)
        {
            SetBusy(true, UIStrings.Busy.LoadingLibrary);
        }

        try
        {
            Directory.CreateDirectory(_libraryDirectory);
            preferredIdentity ??= _selectedPack?.LibraryIdentity;
            var envelope = await RunManagerAsync(["list-library", "--dir", _libraryDirectory]);
            _packs.Clear();
            _packs.AddRange(envelope.Packs ?? []);
            RenderLibrary();

            _libraryNotice.Text = envelope.Errors is { Count: > 0 }
                ? UIStrings.Sidebar.ReadErrorNotice(envelope.Errors.Count.ToString())
                : "";
            _libraryNotice.Visible = !string.IsNullOrWhiteSpace(_libraryNotice.Text);

            var preferred = !string.IsNullOrWhiteSpace(preferredIdentity)
                ? _packs.FirstOrDefault(pack => pack.LibraryIdentity == preferredIdentity)
                : null;
            if (preferred is not null)
            {
                SelectPack(preferred, advance: false, resetTarget: false);
            }
            else if (_selectedPack is not null)
            {
                ClearSelection();
            }
            else if (_packs.Count == 0)
            {
                ShowStep(1);
            }

            _libraryCount.Text = UIStrings.App.LibraryCount(_packs.Count.ToString());
        }
        catch (Exception exception)
        {
            ShowError(exception);
        }
        finally
        {
            if (showProgress)
            {
                SetBusy(false);
            }
        }
    }

    private async Task ImportSourceAsync(string sourcePath)
    {
        if (!IsSupportedSource(sourcePath))
        {
            ShowError(new AppFailure(UIStrings.Errors.UnsupportedSource));
            return;
        }

        SetBusy(true, UIStrings.Busy.Importing);
        try
        {
            Directory.CreateDirectory(_libraryDirectory);
            // 输出文件名由引擎决定，两端不再各自拼接命名规则。
            var displayName = Path.GetFileNameWithoutExtension(sourcePath);
            var envelope = await RunManagerAsync([
                "create-pack",
                "--source", sourcePath,
                "--dir", _libraryDirectory,
                "--name", displayName
            ]);
            var created = envelope.Pack ?? throw new AppFailure(UIStrings.Errors.PackMissingInfo);
            await ReloadLibraryAsync(created.LibraryIdentity, showProgress: false);

            var selected = _packs.FirstOrDefault(pack => pack.Id == created.Id && pack.PackPath == created.PackPath)
                ?? _packs.FirstOrDefault(pack => pack.Id == created.Id);
            if (selected is not null)
            {
                SelectPack(selected, advance: true, resetTarget: true);
            }
            else
            {
                _packs.Insert(0, created);
                RenderLibrary();
                SelectPack(created, advance: true, resetTarget: true);
            }

            ShowToast(UIStrings.ImportStep.SavedToast(created.Name));
        }
        catch (Exception exception)
        {
            ShowError(exception);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void BrowseSource()
    {
        using var dialog = new OpenFileDialog
        {
            Title = UIStrings.FilePicker.SourceTitle,
            Filter = UIStrings.FilePicker.SourceFilter,
            CheckFileExists = true,
            Multiselect = false
        };
        if (dialog.ShowDialog(this) == DialogResult.OK)
        {
            _ = ImportSourceAsync(dialog.FileName);
        }
    }

    private void SelectPack(PackManifest pack, bool advance = true, bool resetTarget = true)
    {
        var changed = _selectedPack?.LibraryIdentity != pack.LibraryIdentity;
        _selectedPack = pack;
        if (changed && resetTarget)
        {
            ClearTarget();
        }

        RenderLibrary();
        PopulatePreview(pack);
        if (advance)
        {
            ShowStep(2);
        }
    }

    private async Task DeletePackAsync(PackManifest pack)
    {
        if (_isBusy)
        {
            return;
        }

        var confirmed = ConfirmDialog.Show(
            this,
            UIStrings.Deletion.ConfirmTitle(pack.Name),
            UIStrings.Deletion.ConfirmMessage,
            UIStrings.Deletion.ConfirmPrimary,
            UIStrings.Deletion.ConfirmCancel,
            destructive: true);
        if (!confirmed)
        {
            return;
        }

        var deletedIndex = Math.Max(0, _packs.FindIndex(item => item.Id == pack.Id && item.PackPath == pack.PackPath));
        var wasSelected = _selectedPack?.Id == pack.Id && _selectedPack?.PackPath == pack.PackPath;
        SetBusy(true, UIStrings.Deletion.Busy(pack.Name));
        try
        {
            PackDeletionPolicy.MoveToRecycleBin(pack, _packs, _libraryDirectory);
            _packs.RemoveAll(item => item.Id == pack.Id && item.PackPath == pack.PackPath);
            if (wasSelected)
            {
                _selectedPack = null;
                ClearTarget();
                var nextIndex = PackDeletionPolicy.FallbackIndex(deletedIndex, _packs.Count);
                if (nextIndex is int index)
                {
                    SelectPack(_packs[index], advance: false, resetTarget: false);
                    ShowStep(2);
                }
                else
                {
                    ShowStep(1);
                }
            }

            await ReloadLibraryAsync(_selectedPack?.LibraryIdentity, showProgress: false);
            ShowToast(UIStrings.Deletion.Done(pack.Name));
        }
        catch (Exception exception)
        {
            ShowError(exception);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void BrowseTarget()
    {
        using var dialog = new OpenFileDialog
        {
            Title = UIStrings.FilePicker.TargetTitle,
            Filter = UIStrings.FilePicker.TargetFilter,
            CheckFileExists = true,
            Multiselect = false
        };
        if (dialog.ShowDialog(this) == DialogResult.OK)
        {
            ChooseTarget(dialog.FileName);
        }
    }

    private void ChooseTarget(string path)
    {
        if (!IsSupportedTarget(path))
        {
            ShowError(new AppFailure(UIStrings.Errors.UnsupportedTarget));
            return;
        }

        _targetPath = Path.GetFullPath(path);
        _outputPath = null;
        _demoteHeadings.Checked = false;
        _targetName.Text = Path.GetFileName(_targetPath);
        _targetPathLabel.Text = Path.GetDirectoryName(_targetPath) ?? _targetPath;
        _targetChosenPanel.Visible = true;
        _targetEmptyPanel.Visible = false;
        _applyButton.Enabled = _selectedPack is not null;
        _successPanel.Visible = false;
    }

    private async Task ApplyPackAsync()
    {
        if (_selectedPack is null || string.IsNullOrWhiteSpace(_selectedPack.PackPath) || string.IsNullOrWhiteSpace(_targetPath))
        {
            ShowError(new AppFailure(UIStrings.Errors.MissingSelection));
            return;
        }

        var extension = Path.GetExtension(_targetPath).ToLowerInvariant();
        using var dialog = new SaveFileDialog
        {
            Title = UIStrings.FilePicker.SaveTitle,
            Filter = extension == ".docm"
                ? UIStrings.FilePicker.OutputFilterDocm
                : UIStrings.FilePicker.OutputFilterDocx,
            DefaultExt = extension.TrimStart('.'),
            AddExtension = true,
            OverwritePrompt = true,
            FileName = Path.GetFileNameWithoutExtension(_targetPath) + UIStrings.FilePicker.OutputSuffix + extension,
            InitialDirectory = Path.GetDirectoryName(_targetPath)
        };
        if (dialog.ShowDialog(this) != DialogResult.OK)
        {
            return;
        }

        var destination = Path.GetFullPath(dialog.FileName);
        if (!string.Equals(Path.GetExtension(destination), extension, StringComparison.OrdinalIgnoreCase))
        {
            ShowError(new AppFailure(UIStrings.Errors.ExtensionMismatch));
            return;
        }

        if (string.Equals(destination, Path.GetFullPath(_targetPath), StringComparison.OrdinalIgnoreCase))
        {
            ShowError(new AppFailure(UIStrings.Errors.SameAsTarget));
            return;
        }

        SetBusy(true, UIStrings.Busy.Applying(_selectedPack.Name));
        try
        {
            var arguments = new List<string>
            {
                "apply-pack",
                "--pack", _selectedPack.PackPath,
                "--target", _targetPath,
                "--out", destination,
                "--force"
            };
            if (!_applyPageLayout.Checked)
            {
                arguments.Add("--preserve-page-layout");
            }

            if (_demoteHeadings.Checked)
            {
                arguments.Add("--demote-headings");
            }

            var envelope = await RunManagerAsync(arguments);
            _outputPath = string.IsNullOrWhiteSpace(envelope.Output) ? destination : envelope.Output;
            _successPath.Text = _outputPath;
            var warnings = envelope.Stats?.Warnings?
                .Where(value => !string.IsNullOrWhiteSpace(value))
                .Select(value => value.Trim())
                .Distinct()
                .ToList() ?? [];
            _successWarnings.Text = warnings.Count > 0
                ? UIStrings.Success.Warnings(string.Join(UIStrings.Success.WarningSeparator, warnings.Take(3)))
                : "";
            _successWarnings.Visible = warnings.Count > 0;
            _targetEmptyPanel.Visible = false;
            _targetChosenPanel.Visible = false;
            _successPanel.Visible = true;
            _applyButton.Text = UIStrings.ApplyStep.ApplyAgainButton;
        }
        catch (Exception exception)
        {
            ShowError(exception);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void OpenOutput()
    {
        if (string.IsNullOrWhiteSpace(_outputPath) || !File.Exists(_outputPath))
        {
            ShowError(new AppFailure(UIStrings.Errors.OutputMissing));
            return;
        }

        try
        {
            Process.Start(new ProcessStartInfo(_outputPath) { UseShellExecute = true });
        }
        catch (Exception exception)
        {
            ShowError(new AppFailure(UIStrings.Errors.OpenFailed(exception.Message)));
        }
    }

    private void RevealOutput()
    {
        if (string.IsNullOrWhiteSpace(_outputPath) || !File.Exists(_outputPath))
        {
            ShowError(new AppFailure(UIStrings.Errors.OutputMissing));
            return;
        }

        try
        {
            var startInfo = new ProcessStartInfo("explorer.exe") { UseShellExecute = false };
            startInfo.ArgumentList.Add($"/select,{_outputPath}");
            Process.Start(startInfo);
        }
        catch (Exception exception)
        {
            ShowError(new AppFailure(UIStrings.Errors.RevealFailed(exception.Message)));
        }
    }

    private void ClearTarget()
    {
        _targetPath = null;
        _outputPath = null;
        if (_demoteHeadings is not null)
        {
            _demoteHeadings.Checked = false;
            _targetChosenPanel.Visible = false;
            _targetEmptyPanel.Visible = true;
            _applyButton.Enabled = false;
            _applyButton.Text = UIStrings.ApplyStep.ApplyButton;
            _successPanel.Visible = false;
        }
    }

    private void ClearSelection()
    {
        _selectedPack = null;
        ClearTarget();
        RenderLibrary();
        ShowStep(1);
    }

    private void ProcessNextDocument()
    {
        ClearTarget();
        ShowStep(3);
    }

    private static bool IsSupportedSource(string path)
    {
        return new[] { ".docx", ".docm", ".dotx", ".dotm" }
            .Contains(Path.GetExtension(path), StringComparer.OrdinalIgnoreCase);
    }

    private static bool IsSupportedTarget(string path)
    {
        return new[] { ".docx", ".docm" }
            .Contains(Path.GetExtension(path), StringComparer.OrdinalIgnoreCase);
    }

    private void ShowError(Exception exception)
    {
        if (exception is OperationCanceledException || IsDisposed || Disposing)
        {
            return;
        }

        var message = exception switch
        {
            UnauthorizedAccessException => UIStrings.Errors.Unauthorized,
            FileNotFoundException => UIStrings.Errors.FileNotFound,
            IOException when exception.Message.Contains("used by another process", StringComparison.OrdinalIgnoreCase) =>
                UIStrings.Errors.FileLocked,
            _ => exception.Message
        };
        MessageBox.Show(this, message, UIStrings.App.ErrorTitle, MessageBoxButtons.OK, MessageBoxIcon.Error);
    }

    private Task<ManagerEnvelope> RunManagerAsync(IEnumerable<string> arguments)
    {
        return PythonBridge.RunAsync(
            arguments,
            _activeOperation?.Token ?? CancellationToken.None);
    }
}
