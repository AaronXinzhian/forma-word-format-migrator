using System.Diagnostics;
using System.Text;

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
            SetBusy(true, "正在读取本机格式库…");
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
                ? $"有 {envelope.Errors.Count} 个格式库文件无法读取，已自动跳过。"
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

            _libraryCount.Text = $"本机已保存 {_packs.Count} 套";
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
            ShowError(new AppFailure("请选择 .docx、.docm、.dotx 或 .dotm 格式的 Word 文件。"));
            return;
        }

        SetBusy(true, "正在识别文档中实际使用的格式…");
        try
        {
            Directory.CreateDirectory(_libraryDirectory);
            var packPath = Path.Combine(_libraryDirectory, $"pack-{Guid.NewGuid():N}.wfstyle");
            var displayName = Path.GetFileNameWithoutExtension(sourcePath);
            var envelope = await RunManagerAsync([
                "create-pack",
                "--source", sourcePath,
                "--out", packPath,
                "--name", displayName
            ]);
            var created = envelope.Pack ?? throw new AppFailure("格式已读取，但没有返回可展示的信息。");
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

            _toastLabel.Text = $"“{created.Name}”已保存到本机格式库。";
            _toastPanel.Visible = true;
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
            Title = "选择 Word 格式源",
            Filter = "Word 格式源 (*.docx;*.docm;*.dotx;*.dotm)|*.docx;*.docm;*.dotx;*.dotm",
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

        var confirmation = MessageBox.Show(
            this,
            "只会把本机保存的这套格式方案移到回收站，不会删除原来的样板 Word 文件，也不会影响已经生成的文档。",
            $"移除“{pack.Name}”？",
            MessageBoxButtons.OKCancel,
            MessageBoxIcon.Warning,
            MessageBoxDefaultButton.Button2);
        if (confirmation != DialogResult.OK)
        {
            return;
        }

        var deletedIndex = Math.Max(0, _packs.FindIndex(item => item.Id == pack.Id && item.PackPath == pack.PackPath));
        var wasSelected = _selectedPack?.Id == pack.Id && _selectedPack?.PackPath == pack.PackPath;
        SetBusy(true, $"正在将“{pack.Name}”移到回收站…");
        try
        {
            PackDeletionPolicy.MoveToRecycleBin(pack, _packs, _libraryDirectory);
            _packs.RemoveAll(item => item.Id == pack.Id && item.PackPath == pack.PackPath);
            if (wasSelected)
            {
                _selectedPack = null;
                ClearTarget();
                if (_packs.Count > 0)
                {
                    var next = _packs[Math.Min(deletedIndex, _packs.Count - 1)];
                    SelectPack(next, advance: false, resetTarget: false);
                    ShowStep(2);
                }
                else
                {
                    ShowStep(1);
                }
            }

            await ReloadLibraryAsync(_selectedPack?.LibraryIdentity, showProgress: false);
            _toastLabel.Text = $"已将“{pack.Name}”移到回收站，需要时可以恢复。";
            _toastPanel.Visible = true;
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
            Title = "选择要修改格式的 Word 文件",
            Filter = "Word 文档 (*.docx;*.docm)|*.docx;*.docm",
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
            ShowError(new AppFailure("目标文件只支持 .docx 或 .docm。"));
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
            ShowError(new AppFailure("请先选择格式库和要修改的 Word 文件。"));
            return;
        }

        var extension = Path.GetExtension(_targetPath).ToLowerInvariant();
        using var dialog = new SaveFileDialog
        {
            Title = "保存应用格式后的 Word 文件",
            Filter = extension == ".docm" ? "启用宏的 Word 文档 (*.docm)|*.docm" : "Word 文档 (*.docx)|*.docx",
            DefaultExt = extension.TrimStart('.'),
            AddExtension = true,
            OverwritePrompt = true,
            FileName = $"{Path.GetFileNameWithoutExtension(_targetPath)}-已套用格式{extension}",
            InitialDirectory = Path.GetDirectoryName(_targetPath)
        };
        if (dialog.ShowDialog(this) != DialogResult.OK)
        {
            return;
        }

        var destination = Path.GetFullPath(dialog.FileName);
        if (!string.Equals(Path.GetExtension(destination), extension, StringComparison.OrdinalIgnoreCase))
        {
            ShowError(new AppFailure("输出文件必须与目标文件保持相同扩展名。"));
            return;
        }

        if (string.Equals(destination, Path.GetFullPath(_targetPath), StringComparison.OrdinalIgnoreCase))
        {
            ShowError(new AppFailure("为保护原文件，请另存为一个新文件。"));
            return;
        }

        SetBusy(true, $"正在清理旧格式并应用“{_selectedPack.Name}”…");
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
                .Distinct()
                .ToList() ?? [];
            _successWarnings.Text = warnings.Count > 0
                ? "请留意：" + string.Join("；", warnings.Take(3))
                : "";
            _successWarnings.Visible = warnings.Count > 0;
            _targetEmptyPanel.Visible = false;
            _targetChosenPanel.Visible = false;
            _successPanel.Visible = true;
            _applyButton.Text = "重新生成";
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
            ShowError(new AppFailure("生成的文件已经移动或删除。"));
            return;
        }

        try
        {
            Process.Start(new ProcessStartInfo(_outputPath) { UseShellExecute = true });
        }
        catch (Exception exception)
        {
            ShowError(new AppFailure($"无法打开生成的文件：{exception.Message}"));
        }
    }

    private void RevealOutput()
    {
        if (string.IsNullOrWhiteSpace(_outputPath) || !File.Exists(_outputPath))
        {
            ShowError(new AppFailure("生成的文件已经移动或删除。"));
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
            ShowError(new AppFailure($"无法在文件夹中显示结果：{exception.Message}"));
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
            _applyButton.Text = "选择保存位置并应用";
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
            UnauthorizedAccessException => "无法读取或写入所选位置，请选择“文档”或桌面等可写位置。",
            FileNotFoundException => "所选文件已被移动或删除，请重新选择。",
            IOException when exception.Message.Contains("used by another process", StringComparison.OrdinalIgnoreCase) =>
                "文件正在被 Word 或其他程序占用，请关闭文件后重试。",
            _ => exception.Message
        };
        MessageBox.Show(this, message, "操作没有完成", MessageBoxButtons.OK, MessageBoxIcon.Error);
    }

    private Task<ManagerEnvelope> RunManagerAsync(IEnumerable<string> arguments)
    {
        return PythonBridge.RunAsync(
            arguments,
            _activeOperation?.Token ?? CancellationToken.None);
    }
}
