/**
 * [INPUT]: 依赖 System.Text, FormaFushi.Windows.Generated
 * [OUTPUT]: 提供 MainForm
 * [POS]: 创建 Windows 三步流程控件和布局
 * [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
 */
using System.Text;
using FormaFushi.Windows.Generated;

namespace FormaFushi.Windows;

internal sealed partial class MainForm
{
    private sealed record FilterOption(string Title, Func<UsedFormat, bool> Includes);

    private static readonly FilterOption[] FilterOptions =
    [
        new(UIStrings.Filters.All, _ => true),
        new(UIStrings.Filters.Headings, format => format.Type == "paragraph" && format.OutlineLevel.HasValue),
        new(UIStrings.Filters.Paragraphs, format => format.Type == "paragraph" && !format.OutlineLevel.HasValue),
        new(UIStrings.Filters.Characters, format => format.Type == "character"),
        new(UIStrings.Filters.Tables, format => format.Type == "table")
    ];

    private readonly Label _libraryCount = Theme.Label(UIStrings.App.LibraryCount("0"), 9, color: Theme.MutedInk);
    private readonly FlowLayoutPanel _libraryList = new();
    private readonly Label _libraryNotice = Theme.Label("", 8.5f, color: Theme.Amber);
    private readonly Panel _libraryHighlight = new();
    private readonly System.Windows.Forms.Timer _highlightTimer = new();
    private readonly Panel _contentHost = new();
    private readonly Panel _emptyPage = new();
    private readonly Panel _previewPage = new();
    private readonly Panel _applyPage = new();
    private readonly Panel[] _stepPanels = new Panel[3];
    private readonly Label[] _stepNumbers = new Label[3];
    private readonly Label[] _stepTitles = new Label[3];
    private readonly Label[] _stepSubtitles = new Label[3];
    private readonly Label _previewTitle = Theme.Label("", 21, FontStyle.Bold);
    private readonly Label _previewSummary = Theme.Label("", 9.5f, color: Theme.MutedInk);
    private readonly Label _statsLabel = Theme.Label("", 10, FontStyle.Bold);
    private readonly Label _warningLabel = Theme.Label("", 9, color: Theme.Amber);
    private readonly ComboBox _formatFilter = new();
    private readonly DataGridView _formatsGrid = new();
    private readonly Label _formatProperties = Theme.Label("", 9.25f);
    private readonly Label _pageOrientation = Theme.Label("", 8.5f, FontStyle.Bold, Theme.Green);
    private readonly Label _pageSize = Theme.Label("", 8.5f, color: Theme.MutedInk);
    private readonly Label _pageMarginVertical = Theme.Label("", 8.5f, color: Theme.MutedInk);
    private readonly Label _pageMarginHorizontal = Theme.Label("", 8.5f, color: Theme.MutedInk);
    private readonly Label _applyPackTitle = Theme.Label("", 14, FontStyle.Bold);
    private readonly Label _applyPackSummary = Theme.Label("", 9, color: Theme.MutedInk);
    private readonly Panel _targetEmptyPanel = new();
    private readonly Panel _targetChosenPanel = new();
    private readonly Label _targetName = Theme.Label("", 11, FontStyle.Bold);
    private readonly Label _targetPathLabel = Theme.Label("", 8.5f, color: Theme.MutedInk);
    private readonly CheckBox _applyPageLayout = new();
    private readonly CheckBox _demoteHeadings = new();
    private readonly Label _applyNotes = Theme.Label("", 9, color: Theme.MutedInk);
    private readonly Button _applyButton = Theme.PrimaryButton(UIStrings.ApplyStep.ApplyButton);
    private readonly Panel _successPanel = new();
    private readonly Label _successPath = Theme.Label("", 8.5f, color: Theme.MutedInk);
    private readonly Label _successWarnings = Theme.Label("", 8.5f, color: Theme.Amber);
    private readonly Panel _busyOverlay = new();
    private readonly Label _busyMessage = Theme.Label("", 12, FontStyle.Bold);
    private readonly Panel _toastPanel = new();
    private readonly Label _toastLabel = Theme.Label("", 9, FontStyle.Bold, Theme.Success);
    private bool _isBusy;

    private void InitializeLayout()
    {
        Text = UIStrings.App.WindowTitle;
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(1180, 680);
        MinimumSize = new Size(1080, 680);
        BackColor = Theme.Paper;
        ForeColor = Theme.Ink;
        Font = Theme.UiFont;
        AutoScaleMode = AutoScaleMode.None;
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);

        var header = BuildHeader();
        var body = new Panel { Dock = DockStyle.Fill, BackColor = Theme.Paper };
        var sidebar = BuildSidebar();
        var main = BuildMainArea();
        body.Controls.Add(main);
        body.Controls.Add(sidebar);

        Controls.Add(body);
        Controls.Add(header);
        BuildBusyOverlay();
        Controls.Add(_busyOverlay);
        _busyOverlay.BringToFront();

        _highlightTimer.Interval = 1600;
        _highlightTimer.Tick += (_, _) =>
        {
            _highlightTimer.Stop();
            _libraryHighlight.Visible = false;
        };

        FormClosing += (_, args) =>
        {
            if (_isBusy)
            {
                var shouldExit = ConfirmDialog.Show(
                    this,
                    UIStrings.App.ExitBusyTitle,
                    UIStrings.App.ExitBusyMessage,
                    UIStrings.App.ExitBusyConfirm,
                    UIStrings.App.ExitBusyCancel);
                args.Cancel = !shouldExit;
                if (shouldExit)
                {
                    _activeOperation?.Cancel();
                }
            }
        };
        FormClosed += (_, _) => _activeOperation?.Cancel();
    }

    private Panel BuildHeader()
    {
        var header = new Panel
        {
            Dock = DockStyle.Top,
            Height = 92,
            BackColor = Theme.GreenDeep,
            Padding = new Padding(30, 18, 30, 14)
        };

        // 这个字是图标而不是文案：macOS 用 SF Symbol 表达同一位置，
        // 图标风格属于计划里明确不统一的平台惯例，因此不进 ui-strings.json。
        var brandMark = new Label
        {
            Text = "赋",
            TextAlign = ContentAlignment.MiddleCenter,
            Font = Theme.CreateFont(18, FontStyle.Bold),
            ForeColor = Theme.GreenDeep,
            BackColor = Theme.Mint,
            Size = new Size(50, 50),
            Location = new Point(30, 20)
        };
        var title = Theme.Label(UIStrings.App.Brand, 18, FontStyle.Bold, Color.White);
        title.Location = new Point(96, 19);
        var slogan = Theme.Label(UIStrings.App.Slogan, 9.5f, color: Color.FromArgb(205, 226, 218));
        slogan.Location = new Point(98, 53);
        _libraryCount.ForeColor = Color.FromArgb(205, 226, 218);
        _libraryCount.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        _libraryCount.Location = new Point(ClientSize.Width - 160, 38);
        header.Resize += (_, _) => _libraryCount.Location = new Point(header.ClientSize.Width - _libraryCount.Width - 30, 38);
        header.Controls.Add(brandMark);
        header.Controls.Add(title);
        header.Controls.Add(slogan);
        header.Controls.Add(_libraryCount);
        return header;
    }

    private Panel BuildSidebar()
    {
        var sidebar = new Panel
        {
            Dock = DockStyle.Left,
            Width = 310,
            BackColor = Theme.Sidebar,
            Padding = new Padding(22, 24, 18, 18)
        };
        var heading = Theme.Label(UIStrings.Sidebar.Title, 15, FontStyle.Bold);
        heading.Location = new Point(22, 22);
        var hint = Theme.Label(UIStrings.Sidebar.Hint, 8.5f, color: Theme.MutedInk);
        hint.Location = new Point(23, 52);

        var importButton = Theme.PrimaryButton("＋  " + UIStrings.Sidebar.ImportButton);
        importButton.AutoSize = false;
        importButton.SetBounds(22, 82, 270, 42);
        importButton.Click += (_, _) => BrowseSource();

        var refreshButton = Theme.TextButton(UIStrings.Sidebar.RefreshButton);
        refreshButton.AutoSize = false;
        refreshButton.SetBounds(180, 128, 112, 30);
        refreshButton.Click += async (_, _) => await ReloadLibraryAsync();

        _libraryNotice.AutoSize = false;
        _libraryNotice.SetBounds(22, 158, 270, 42);
        _libraryNotice.Visible = false;

        _libraryList.FlowDirection = FlowDirection.TopDown;
        _libraryList.WrapContents = false;
        _libraryList.AutoScroll = true;
        _libraryList.BackColor = Color.Transparent;
        _libraryList.SetBounds(13, 202, 288, 560);
        _libraryList.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;

        _libraryHighlight.Dock = DockStyle.Right;
        _libraryHighlight.Width = 3;
        _libraryHighlight.BackColor = Theme.Green;
        _libraryHighlight.Visible = false;

        sidebar.Controls.Add(heading);
        sidebar.Controls.Add(hint);
        sidebar.Controls.Add(importButton);
        sidebar.Controls.Add(refreshButton);
        sidebar.Controls.Add(_libraryNotice);
        sidebar.Controls.Add(_libraryList);
        sidebar.Controls.Add(_libraryHighlight);
        return sidebar;
    }

    private Panel BuildMainArea()
    {
        var main = new Panel { Dock = DockStyle.Fill, BackColor = Theme.Paper };
        var stepBar = BuildStepBar();
        _contentHost.Dock = DockStyle.Fill;
        _contentHost.Padding = new Padding(26, 18, 26, 22);
        _contentHost.BackColor = Theme.Paper;

        BuildEmptyPage();
        BuildPreviewPage();
        BuildApplyPage();
        _contentHost.Controls.Add(_emptyPage);
        _contentHost.Controls.Add(_previewPage);
        _contentHost.Controls.Add(_applyPage);

        _toastPanel.Height = 38;
        _toastPanel.Dock = DockStyle.Bottom;
        _toastPanel.BackColor = Theme.Mint;
        _toastPanel.Padding = new Padding(22, 9, 22, 7);
        _toastPanel.Visible = false;
        _toastPanel.Controls.Add(_toastLabel);
        _toastPanel.Click += (_, _) => _toastPanel.Visible = false;
        _toastLabel.Click += (_, _) => _toastPanel.Visible = false;

        main.Controls.Add(_contentHost);
        main.Controls.Add(_toastPanel);
        main.Controls.Add(stepBar);
        ShowStep(1);
        return main;
    }

    private Panel BuildStepBar()
    {
        var bar = new Panel
        {
            Dock = DockStyle.Top,
            Height = 72,
            BackColor = Color.White,
            Padding = new Padding(28, 10, 28, 8)
        };
        var table = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 3,
            RowCount = 1,
            BackColor = Color.White
        };
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 33.333f));
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 33.333f));
        table.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 33.334f));
        var titles = new[]
        {
            UIStrings.Steps.ImportTitle,
            UIStrings.Steps.PreviewTitle,
            UIStrings.Steps.ApplyTitle
        };
        var subtitles = new[]
        {
            UIStrings.Steps.ImportSubtitle,
            UIStrings.Steps.PreviewSubtitle,
            UIStrings.Steps.ApplySubtitle
        };
        for (var index = 0; index < 3; index++)
        {
            var step = new Panel { Dock = DockStyle.Fill, Padding = new Padding(8, 8, 8, 5), Cursor = Cursors.Hand };
            var number = new Label
            {
                Text = (index + 1).ToString(),
                Font = Theme.CreateFont(9, FontStyle.Bold),
                TextAlign = ContentAlignment.MiddleCenter,
                Size = new Size(28, 28),
                Location = new Point(8, 11)
            };
            var label = Theme.Label(titles[index], 9.5f, FontStyle.Bold);
            label.Location = new Point(45, 6);
            var subtitle = Theme.Label(subtitles[index], 8, color: Theme.MutedInk);
            subtitle.Location = new Point(46, 28);
            var capturedIndex = index + 1;
            step.Click += (_, _) => NavigateToStep(capturedIndex);
            number.Click += (_, _) => NavigateToStep(capturedIndex);
            label.Click += (_, _) => NavigateToStep(capturedIndex);
            subtitle.Click += (_, _) => NavigateToStep(capturedIndex);
            step.Controls.Add(number);
            step.Controls.Add(label);
            step.Controls.Add(subtitle);
            table.Controls.Add(step, index, 0);
            _stepPanels[index] = step;
            _stepNumbers[index] = number;
            _stepTitles[index] = label;
            _stepSubtitles[index] = subtitle;
        }

        bar.Controls.Add(table);
        return bar;
    }

    private void BuildEmptyPage()
    {
        _emptyPage.Dock = DockStyle.Fill;
        _emptyPage.BackColor = Theme.Paper;
        var layout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 2,
            RowCount = 1,
            BackColor = Theme.Paper,
            Padding = new Padding(0, 8, 0, 0)
        };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 64));
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 36));

        var dropCard = new CardPanel { Dock = DockStyle.Fill, Margin = new Padding(0, 0, 12, 0), AllowDrop = true };
        var dropContents = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 7,
            ColumnCount = 1,
            BackColor = Color.Transparent,
            Padding = new Padding(34, 52, 34, 35)
        };
        for (var row = 0; row < 6; row++)
        {
            dropContents.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        }

        dropContents.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        var eyebrow = Theme.Label(UIStrings.ImportStep.Eyebrow, 9, FontStyle.Bold, Theme.Green);
        var title = Theme.Label(UIStrings.ImportStep.Title, 19, FontStyle.Bold);
        title.Margin = new Padding(0, 12, 0, 8);
        var subtitle = Theme.Label(UIStrings.ImportStep.Subtitle, 10, color: Theme.MutedInk);
        subtitle.MaximumSize = new Size(430, 0);
        subtitle.Margin = new Padding(0, 0, 0, 28);
        var chooseButton = Theme.PrimaryButton(UIStrings.ImportStep.ChooseButton);
        chooseButton.AutoSize = false;
        chooseButton.Width = 210;
        chooseButton.Height = 46;
        chooseButton.Margin = new Padding(0, 0, 0, 12);
        chooseButton.Click += (_, _) => BrowseSource();
        var dropHint = Theme.Label(UIStrings.ImportStep.DropHint, 9, color: Theme.MutedInk);
        var formatHint = Theme.Label(UIStrings.ImportStep.SupportedFormats, 8.5f, color: Theme.MutedInk);
        dropContents.Controls.Add(eyebrow);
        dropContents.Controls.Add(title);
        dropContents.Controls.Add(subtitle);
        dropContents.Controls.Add(chooseButton);
        dropContents.Controls.Add(dropHint);
        dropContents.Controls.Add(formatHint);
        dropCard.Controls.Add(dropContents);
        dropCard.Resize += (_, _) =>
        {
            var availableWidth = Math.Max(200, dropCard.ClientSize.Width - 104);
            title.MaximumSize = new Size(availableWidth, 0);
            subtitle.MaximumSize = new Size(availableWidth, 0);
            dropHint.MaximumSize = new Size(availableWidth, 0);
            formatHint.MaximumSize = new Size(availableWidth, 0);
        };
        dropCard.DragEnter += (_, args) =>
        {
            args.Effect = args.Data?.GetDataPresent(DataFormats.FileDrop) == true ? DragDropEffects.Copy : DragDropEffects.None;
        };
        dropCard.DragDrop += (_, args) => HandleSourceDrop(args);
        dropContents.AllowDrop = true;
        dropContents.DragEnter += (_, args) => args.Effect = args.Data?.GetDataPresent(DataFormats.FileDrop) == true ? DragDropEffects.Copy : DragDropEffects.None;
        dropContents.DragDrop += (_, args) => HandleSourceDrop(args);

        var infoCard = new CardPanel { Dock = DockStyle.Fill, Margin = new Padding(12, 0, 0, 0) };
        var info = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 5,
            ColumnCount = 1,
            BackColor = Color.Transparent,
            Padding = new Padding(10, 18, 10, 10)
        };
        info.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        info.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        info.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        info.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        info.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        var infoTitle = Theme.Label(UIStrings.ImportStep.InfoTitle, 13, FontStyle.Bold);
        infoTitle.Margin = new Padding(0, 0, 0, 20);
        info.Controls.Add(infoTitle);
        info.Controls.Add(FeatureRow("01", UIStrings.ImportStep.Info1));
        info.Controls.Add(FeatureRow("02", UIStrings.ImportStep.Info2));
        info.Controls.Add(FeatureRow("03", UIStrings.ImportStep.Info3));
        infoCard.Controls.Add(info);

        layout.Controls.Add(dropCard, 0, 0);
        layout.Controls.Add(infoCard, 1, 0);
        _emptyPage.Controls.Add(layout);
    }

    private static Panel FeatureRow(string number, string text)
    {
        var row = new Panel { Height = 82, Dock = DockStyle.Top, BackColor = Color.Transparent };
        var badge = new Label
        {
            Text = number,
            Font = Theme.CreateFont(9, FontStyle.Bold),
            ForeColor = Theme.Green,
            BackColor = Theme.Mint,
            TextAlign = ContentAlignment.MiddleCenter,
            Size = new Size(38, 28),
            Location = new Point(0, 8)
        };
        var label = Theme.Label(text, 9.5f, color: Theme.Ink);
        label.AutoSize = false;
        label.SetBounds(52, 5, 138, 68);
        label.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
        row.Resize += (_, _) => label.Width = Math.Max(90, row.ClientSize.Width - 56);
        row.Controls.Add(badge);
        row.Controls.Add(label);
        return row;
    }

    private void BuildPreviewPage()
    {
        _previewPage.Dock = DockStyle.Fill;
        _previewPage.BackColor = Theme.Paper;
        var root = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 4,
            ColumnCount = 1,
            BackColor = Theme.Paper
        };
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 82));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 62));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));

        var header = new Panel { Dock = DockStyle.Fill, BackColor = Color.Transparent };
        _previewTitle.Location = new Point(0, 0);
        _previewSummary.AutoSize = false;
        _previewSummary.SetBounds(1, 39, 560, 38);
        var nextButton = Theme.PrimaryButton(UIStrings.PreviewStep.NextButton);
        nextButton.AutoSize = false;
        nextButton.Size = new Size(210, 42);
        nextButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        nextButton.Click += (_, _) => ShowStep(3);
        // 「换一套格式」在两端的统一行为：把注意力引到常驻格式库，而不是弹文件对话框。
        var switchButton = Theme.SecondaryButton(UIStrings.PreviewStep.SwitchPackButton);
        switchButton.AutoSize = false;
        switchButton.Size = new Size(132, 42);
        switchButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        switchButton.Click += (_, _) => HighlightLibrary();
        header.Resize += (_, _) =>
        {
            nextButton.Location = new Point(header.ClientSize.Width - nextButton.Width, 8);
            switchButton.Location = new Point(nextButton.Left - switchButton.Width - 10, 8);
            _previewSummary.Width = Math.Max(200, switchButton.Left - 20);
        };
        header.Controls.Add(_previewTitle);
        header.Controls.Add(_previewSummary);
        header.Controls.Add(nextButton);
        header.Controls.Add(switchButton);

        var summaryCard = new CardPanel { Dock = DockStyle.Fill, Margin = new Padding(0, 0, 0, 10), Padding = new Padding(16, 10, 16, 8) };
        _statsLabel.Location = new Point(16, 11);
        _warningLabel.AutoSize = false;
        _warningLabel.SetBounds(16, 33, 830, 24);
        summaryCard.Resize += (_, _) => _warningLabel.Width = summaryCard.ClientSize.Width - 32;
        summaryCard.Controls.Add(_statsLabel);
        summaryCard.Controls.Add(_warningLabel);

        var split = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 2,
            RowCount = 1,
            BackColor = Theme.Paper
        };
        split.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 68));
        split.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 32));
        split.Controls.Add(BuildFormatsListCard(), 0, 0);
        split.Controls.Add(BuildInspectorCard(), 1, 0);

        var footer = new Panel { Dock = DockStyle.Fill, BackColor = Color.Transparent };
        var privacy = Theme.Label(UIStrings.PreviewStep.Privacy, 8.5f, color: Theme.MutedInk);
        privacy.Location = new Point(0, 12);
        footer.Controls.Add(privacy);

        root.Controls.Add(header, 0, 0);
        root.Controls.Add(summaryCard, 0, 1);
        root.Controls.Add(split, 0, 2);
        root.Controls.Add(footer, 0, 3);
        _previewPage.Controls.Add(root);
    }

    private CardPanel BuildFormatsListCard()
    {
        var card = new CardPanel { Dock = DockStyle.Fill, Margin = new Padding(0, 0, 10, 0), Padding = new Padding(14) };
        var header = new Panel { Dock = DockStyle.Top, Height = 48, BackColor = Color.Transparent };
        var title = Theme.Label(UIStrings.PreviewStep.ListTitle, 12, FontStyle.Bold);
        title.Location = new Point(0, 7);
        _formatFilter.DropDownStyle = ComboBoxStyle.DropDownList;
        _formatFilter.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        _formatFilter.SetBounds(415, 4, 146, 32);
        header.Resize += (_, _) => _formatFilter.Left = header.ClientSize.Width - _formatFilter.Width;
        _formatFilter.SelectedIndexChanged += (_, _) => PopulateFormatsGrid();
        header.Controls.Add(title);
        header.Controls.Add(_formatFilter);

        ConfigureFormatsGrid();
        card.Controls.Add(_formatsGrid);
        card.Controls.Add(header);
        return card;
    }

    private void ConfigureFormatsGrid()
    {
        _formatsGrid.Dock = DockStyle.Fill;
        _formatsGrid.BackgroundColor = Color.White;
        _formatsGrid.BorderStyle = BorderStyle.None;
        _formatsGrid.RowHeadersVisible = false;
        _formatsGrid.AllowUserToAddRows = false;
        _formatsGrid.AllowUserToDeleteRows = false;
        _formatsGrid.AllowUserToResizeRows = false;
        _formatsGrid.ReadOnly = true;
        _formatsGrid.MultiSelect = false;
        _formatsGrid.SelectionMode = DataGridViewSelectionMode.FullRowSelect;
        _formatsGrid.AutoGenerateColumns = false;
        _formatsGrid.ColumnHeadersHeight = 38;
        _formatsGrid.RowTemplate.Height = 48;
        _formatsGrid.EnableHeadersVisualStyles = false;
        _formatsGrid.ColumnHeadersDefaultCellStyle.BackColor = Color.FromArgb(242, 246, 243);
        _formatsGrid.ColumnHeadersDefaultCellStyle.ForeColor = Theme.Ink;
        _formatsGrid.ColumnHeadersDefaultCellStyle.Font = Theme.CreateFont(9, FontStyle.Bold);
        _formatsGrid.DefaultCellStyle.Font = Theme.UiFont;
        _formatsGrid.DefaultCellStyle.ForeColor = Theme.Ink;
        _formatsGrid.DefaultCellStyle.SelectionBackColor = Theme.Mint;
        _formatsGrid.DefaultCellStyle.SelectionForeColor = Theme.GreenDeep;
        _formatsGrid.GridColor = Theme.Line;
        _formatsGrid.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = UIStrings.FormatList.ColumnName, Name = "Name", Width = 138 });
        _formatsGrid.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = UIStrings.FormatList.ColumnUsage, Name = "Usage", Width = 78 });
        _formatsGrid.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = UIStrings.FormatList.ColumnFont, Name = "Font", Width = 138 });
        _formatsGrid.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = UIStrings.FormatList.ColumnNumbering, Name = "Numbering", AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill, MinimumWidth = 92 });
        _formatsGrid.SelectionChanged += (_, _) => UpdateFormatInspector();
    }

    private CardPanel BuildInspectorCard()
    {
        var card = new CardPanel { Dock = DockStyle.Fill, Margin = new Padding(10, 0, 0, 0), Padding = new Padding(18) };
        var title = Theme.Label(UIStrings.Inspector.Title, 12, FontStyle.Bold);
        title.Dock = DockStyle.Top;
        title.Height = 32;

        _formatProperties.AutoSize = false;
        _formatProperties.Dock = DockStyle.Fill;
        _formatProperties.Padding = new Padding(0, 14, 0, 0);
        _formatProperties.ForeColor = Theme.Ink;

        card.Controls.Add(_formatProperties);
        card.Controls.Add(BuildPageLayoutPanel());
        card.Controls.Add(title);
        return card;
    }

    /// <summary>
    /// 页面设置改为结构化展示，字段与 Mac 端 PageLayoutCard 一致。
    /// </summary>
    private Panel BuildPageLayoutPanel()
    {
        var panel = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 128,
            BackColor = Color.FromArgb(246, 249, 247),
            Padding = new Padding(12, 10, 12, 10)
        };
        var title = Theme.Label(UIStrings.Inspector.PageTitle, 10, FontStyle.Bold);
        title.Location = new Point(12, 10);
        _pageOrientation.BackColor = Theme.Mint;
        _pageOrientation.AutoSize = false;
        _pageOrientation.TextAlign = ContentAlignment.MiddleCenter;
        _pageOrientation.SetBounds(12, 36, 56, 24);
        _pageOrientation.Anchor = AnchorStyles.Top | AnchorStyles.Left;

        _pageSize.Location = new Point(78, 40);
        _pageMarginVertical.Location = new Point(13, 70);
        _pageMarginHorizontal.Location = new Point(13, 94);

        panel.Controls.Add(title);
        panel.Controls.Add(_pageOrientation);
        panel.Controls.Add(_pageSize);
        panel.Controls.Add(_pageMarginVertical);
        panel.Controls.Add(_pageMarginHorizontal);
        return panel;
    }

    private void BuildApplyPage()
    {
        _applyPage.Dock = DockStyle.Fill;
        _applyPage.BackColor = Theme.Paper;
        var root = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 4,
            ColumnCount = 1,
            BackColor = Theme.Paper
        };
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 78));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 76));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 62));

        var header = new Panel { Dock = DockStyle.Fill, BackColor = Color.Transparent };
        var title = Theme.Label(UIStrings.ApplyStep.Title, 21, FontStyle.Bold);
        title.Location = new Point(0, 0);
        var subtitle = Theme.Label(UIStrings.ApplyStep.Subtitle, 9.5f, color: Theme.MutedInk);
        subtitle.Location = new Point(1, 39);
        var back = Theme.SecondaryButton(UIStrings.ApplyStep.BackButton);
        back.AutoSize = false;
        back.Size = new Size(142, 38);
        back.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        header.Resize += (_, _) => back.Location = new Point(header.ClientSize.Width - back.Width, 4);
        back.Click += (_, _) => ShowStep(2);
        header.Controls.Add(title);
        header.Controls.Add(subtitle);
        header.Controls.Add(back);

        var selectedCard = new CardPanel { Dock = DockStyle.Fill, Margin = new Padding(0, 0, 0, 12), Padding = new Padding(17, 10, 17, 8) };
        _applyPackTitle.Location = new Point(17, 11);
        _applyPackSummary.Location = new Point(18, 39);
        var change = Theme.TextButton(UIStrings.ApplyStep.ChangePackButton);
        change.AutoSize = false;
        change.Size = new Size(74, 32);
        change.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        change.Click += (_, _) => HighlightLibrary();
        selectedCard.Resize += (_, _) => change.Location = new Point(selectedCard.ClientSize.Width - change.Width - 13, 15);
        selectedCard.Controls.Add(_applyPackTitle);
        selectedCard.Controls.Add(_applyPackSummary);
        selectedCard.Controls.Add(change);

        var body = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 2,
            RowCount = 1,
            BackColor = Theme.Paper
        };
        body.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 54));
        body.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 46));
        body.Controls.Add(BuildTargetCard(), 0, 0);
        body.Controls.Add(BuildOptionsCard(), 1, 0);

        var footer = new Panel { Dock = DockStyle.Fill, BackColor = Color.Transparent };
        _applyButton.AutoSize = false;
        _applyButton.Size = new Size(225, 44);
        _applyButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        _applyButton.Enabled = false;
        footer.Resize += (_, _) => _applyButton.Location = new Point(footer.ClientSize.Width - _applyButton.Width, 10);
        _applyButton.Click += async (_, _) => await ApplyPackAsync();
        var footerHint = Theme.Label(UIStrings.ApplyStep.NoteKeepContent, 8.5f, color: Theme.MutedInk);
        footerHint.Location = new Point(0, 24);
        footer.Controls.Add(footerHint);
        footer.Controls.Add(_applyButton);

        root.Controls.Add(header, 0, 0);
        root.Controls.Add(selectedCard, 0, 1);
        root.Controls.Add(body, 0, 2);
        root.Controls.Add(footer, 0, 3);
        _applyPage.Controls.Add(root);
    }

    private CardPanel BuildTargetCard()
    {
        var card = new CardPanel { Dock = DockStyle.Fill, Margin = new Padding(0, 0, 10, 0), Padding = new Padding(20) };
        var title = Theme.Label(UIStrings.ApplyStep.TargetTitle, 13, FontStyle.Bold);
        title.Dock = DockStyle.Top;
        title.Height = 38;

        _targetEmptyPanel.Dock = DockStyle.Top;
        _targetEmptyPanel.Height = 160;
        _targetEmptyPanel.BackColor = Color.FromArgb(246, 249, 247);
        _targetEmptyPanel.AllowDrop = true;
        var emptyTitle = Theme.Label(UIStrings.ApplyStep.TargetEmptyTitle, 11, FontStyle.Bold);
        emptyTitle.Location = new Point(18, 17);
        var emptyHint = Theme.Label(UIStrings.ApplyStep.TargetEmptyHint, 8.5f, color: Theme.MutedInk);
        emptyHint.Location = new Point(19, 48);
        var choose = Theme.PrimaryButton(UIStrings.ApplyStep.ChooseTargetButton);
        choose.AutoSize = false;
        choose.Size = new Size(146, 38);
        choose.Location = new Point(18, 82);
        choose.Click += (_, _) => BrowseTarget();
        var dropHint = Theme.Label(UIStrings.ApplyStep.TargetDropHint, 8.5f, color: Theme.MutedInk);
        dropHint.Location = new Point(19, 128);
        _targetEmptyPanel.Controls.Add(emptyTitle);
        _targetEmptyPanel.Controls.Add(emptyHint);
        _targetEmptyPanel.Controls.Add(choose);
        _targetEmptyPanel.Controls.Add(dropHint);
        _targetEmptyPanel.DragEnter += (_, args) => args.Effect = args.Data?.GetDataPresent(DataFormats.FileDrop) == true ? DragDropEffects.Copy : DragDropEffects.None;
        _targetEmptyPanel.DragDrop += (_, args) => HandleTargetDrop(args);

        _targetChosenPanel.Dock = DockStyle.Top;
        _targetChosenPanel.Height = 160;
        _targetChosenPanel.BackColor = Color.FromArgb(235, 244, 239);
        _targetChosenPanel.AllowDrop = true;
        _targetChosenPanel.Visible = false;
        _targetName.Location = new Point(18, 18);
        _targetPathLabel.AutoSize = false;
        _targetPathLabel.SetBounds(19, 50, 120, 27);
        _targetPathLabel.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
        var change = Theme.SecondaryButton(UIStrings.ApplyStep.ChangeTargetButton);
        change.AutoSize = false;
        change.Size = new Size(138, 36);
        change.Location = new Point(18, 85);
        change.Click += (_, _) => BrowseTarget();
        _targetChosenPanel.Controls.Add(_targetName);
        _targetChosenPanel.Controls.Add(_targetPathLabel);
        _targetChosenPanel.Controls.Add(change);
        _targetChosenPanel.DragEnter += (_, args) => args.Effect = args.Data?.GetDataPresent(DataFormats.FileDrop) == true ? DragDropEffects.Copy : DragDropEffects.None;
        _targetChosenPanel.DragDrop += (_, args) => HandleTargetDrop(args);
        _targetChosenPanel.Resize += (_, _) =>
            _targetPathLabel.Width = Math.Max(100, _targetChosenPanel.ClientSize.Width - 38);

        _successPanel.Dock = DockStyle.Fill;
        _successPanel.BackColor = Theme.Mint;
        _successPanel.Visible = false;
        var successContents = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 1,
            RowCount = 4,
            BackColor = Color.Transparent,
            Padding = new Padding(18, 12, 18, 12)
        };
        successContents.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));
        successContents.RowStyles.Add(new RowStyle(SizeType.Absolute, 46));
        successContents.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        successContents.RowStyles.Add(new RowStyle(SizeType.Absolute, 52));
        var successTitle = Theme.Label(UIStrings.Success.Title, 12, FontStyle.Bold, Theme.Success);
        successTitle.Dock = DockStyle.Fill;
        _successPath.AutoSize = false;
        _successPath.Dock = DockStyle.Fill;
        _successWarnings.AutoSize = false;
        _successWarnings.Dock = DockStyle.Fill;
        _successWarnings.Visible = false;
        var actions = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 3,
            RowCount = 1,
            BackColor = Color.Transparent,
            Padding = new Padding(0, 5, 0, 3)
        };
        actions.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 28));
        actions.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 42));
        actions.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 30));
        var open = Theme.PrimaryButton(UIStrings.Success.OpenButton);
        open.AutoSize = false;
        open.Dock = DockStyle.Fill;
        open.Margin = new Padding(0, 0, 4, 0);
        open.Click += (_, _) => OpenOutput();
        var reveal = Theme.SecondaryButton(UIStrings.Success.RevealButton);
        reveal.AutoSize = false;
        reveal.Dock = DockStyle.Fill;
        reveal.Margin = new Padding(4, 0, 4, 0);
        reveal.Click += (_, _) => RevealOutput();
        var next = Theme.TextButton(UIStrings.Success.NextButton);
        next.AutoSize = false;
        next.Dock = DockStyle.Fill;
        next.Margin = new Padding(4, 0, 0, 0);
        next.Click += (_, _) => ProcessNextDocument();
        actions.Controls.Add(open, 0, 0);
        actions.Controls.Add(reveal, 1, 0);
        actions.Controls.Add(next, 2, 0);
        successContents.Controls.Add(successTitle, 0, 0);
        successContents.Controls.Add(_successPath, 0, 1);
        successContents.Controls.Add(_successWarnings, 0, 2);
        successContents.Controls.Add(actions, 0, 3);
        _successPanel.Controls.Add(successContents);

        card.Controls.Add(_successPanel);
        card.Controls.Add(_targetChosenPanel);
        card.Controls.Add(_targetEmptyPanel);
        card.Controls.Add(title);
        return card;
    }

    private CardPanel BuildOptionsCard()
    {
        var card = new CardPanel { Dock = DockStyle.Fill, Margin = new Padding(10, 0, 0, 0), Padding = new Padding(21) };
        var title = Theme.Label(UIStrings.ApplyStep.OptionsTitle, 13, FontStyle.Bold);
        title.Dock = DockStyle.Top;
        title.Height = 42;

        _applyPageLayout.Text = UIStrings.ApplyStep.OptionPageLayout;
        _applyPageLayout.Checked = true;
        _applyPageLayout.AutoSize = true;
        _applyPageLayout.Font = Theme.CreateFont(10, FontStyle.Bold);
        _applyPageLayout.ForeColor = Theme.Ink;
        _applyPageLayout.Location = new Point(22, 60);
        var layoutHint = Theme.Label(UIStrings.ApplyStep.OptionPageLayoutHint, 8.5f, color: Theme.MutedInk);
        layoutHint.Location = new Point(45, 88);

        _demoteHeadings.Text = UIStrings.ApplyStep.OptionDemote;
        _demoteHeadings.AutoSize = true;
        _demoteHeadings.Font = Theme.CreateFont(10, FontStyle.Bold);
        _demoteHeadings.ForeColor = Theme.Ink;
        _demoteHeadings.Location = new Point(22, 124);
        var demoteHint = Theme.Label(UIStrings.ApplyStep.OptionDemoteHint, 8.5f, color: Theme.MutedInk);
        demoteHint.Location = new Point(45, 152);
        var demoteNote = Theme.Label(UIStrings.ApplyStep.OptionDemoteNote, 8.5f, color: Theme.MutedInk);
        demoteNote.AutoSize = false;
        demoteNote.SetBounds(45, 174, 360, 34);
        demoteNote.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;

        var divider = new Panel { BackColor = Theme.Line, Height = 1, Left = 22, Top = 214, Width = 380, Anchor = AnchorStyles.Left | AnchorStyles.Top | AnchorStyles.Right };

        // 处理说明由 ApplyNotes 根据格式包内容生成，不再是四行静态文本。
        _applyNotes.AutoSize = false;
        _applyNotes.SetBounds(22, 230, 405, 180);
        _applyNotes.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom;

        card.Controls.Add(title);
        card.Controls.Add(_applyPageLayout);
        card.Controls.Add(layoutHint);
        card.Controls.Add(_demoteHeadings);
        card.Controls.Add(demoteHint);
        card.Controls.Add(demoteNote);
        card.Controls.Add(divider);
        card.Controls.Add(_applyNotes);
        return card;
    }

    private void BuildBusyOverlay()
    {
        _busyOverlay.Dock = DockStyle.Fill;
        _busyOverlay.BackColor = Color.FromArgb(246, 246, 242);
        _busyOverlay.Visible = false;
        var center = new CardPanel
        {
            Size = new Size(430, 154),
            BackColor = Color.White,
            BorderColor = Theme.Line
        };
        var indicator = new Label
        {
            Text = "•••",
            Font = Theme.CreateFont(22, FontStyle.Bold, "Segoe UI"),
            ForeColor = Theme.Green,
            AutoSize = true,
            Location = new Point(181, 26)
        };
        _busyMessage.AutoSize = false;
        _busyMessage.TextAlign = ContentAlignment.MiddleCenter;
        _busyMessage.SetBounds(28, 78, 374, 38);
        center.Controls.Add(indicator);
        center.Controls.Add(_busyMessage);
        _busyOverlay.Controls.Add(center);
        _busyOverlay.Resize += (_, _) => center.Location = new Point(
            Math.Max(0, (_busyOverlay.ClientSize.Width - center.Width) / 2),
            Math.Max(0, (_busyOverlay.ClientSize.Height - center.Height) / 2));
    }

    private void RenderLibrary()
    {
        _libraryList.SuspendLayout();
        _libraryList.Controls.Clear();
        if (_packs.Count == 0)
        {
            var empty = Theme.Label(UIStrings.Sidebar.Empty, 9, color: Theme.MutedInk);
            empty.AutoSize = false;
            empty.Size = new Size(250, 100);
            empty.Margin = new Padding(10, 18, 8, 0);
            _libraryList.Controls.Add(empty);
        }
        else
        {
            foreach (var pack in _packs)
            {
                _libraryList.Controls.Add(CreatePackCard(pack));
            }
        }

        _libraryList.ResumeLayout();
    }

    private Control CreatePackCard(PackManifest pack)
    {
        var selected = _selectedPack?.LibraryIdentity == pack.LibraryIdentity;
        var panel = new CardPanel
        {
            Width = 260,
            Height = 102,
            Margin = new Padding(6, 5, 6, 7),
            Padding = new Padding(14, 11, 12, 8),
            BackColor = selected ? Theme.Mint : Color.White,
            BorderColor = selected ? Theme.Green : Theme.Line,
            Cursor = Cursors.Hand
        };
        var name = Theme.Label(pack.Name, 10.5f, FontStyle.Bold, selected ? Theme.GreenDeep : Theme.Ink);
        name.AutoSize = false;
        name.SetBounds(14, 11, 195, 25);
        var detailText = pack.InferredCount > 0
            ? UIStrings.Sidebar.PackSummaryWithInferred(pack.UsedStyleCount.ToString(), pack.InferredCount.ToString())
            : UIStrings.Sidebar.PackSummary(pack.UsedStyleCount.ToString());
        var detail = Theme.Label(detailText, 8.25f, color: Theme.MutedInk);
        detail.Location = new Point(15, 43);
        var date = Theme.Label(pack.CreatedDisplay, 8, color: Theme.MutedInk);
        date.Location = new Point(15, 69);
        var delete = Theme.TextButton(UIStrings.Sidebar.DeleteButton);
        delete.AutoSize = false;
        delete.Size = new Size(50, 30);
        delete.Location = new Point(202, 60);
        delete.ForeColor = Theme.Amber;
        delete.Click += async (_, _) => await DeletePackAsync(pack);
        void SelectHandler(object? _, EventArgs __) => SelectPack(pack);
        panel.Click += SelectHandler;
        name.Click += SelectHandler;
        detail.Click += SelectHandler;
        date.Click += SelectHandler;
        panel.Controls.Add(name);
        panel.Controls.Add(detail);
        panel.Controls.Add(date);
        panel.Controls.Add(delete);
        return panel;
    }

    private void PopulatePreview(PackManifest pack)
    {
        _previewTitle.Text = pack.Name;
        _previewSummary.Text = pack.InferredCount > 0
            ? UIStrings.PreviewStep.SummaryWithInferred(pack.InferredCount.ToString(), pack.HiddenCount.ToString())
            : UIStrings.PreviewStep.Summary(pack.HiddenCount.ToString());
        _statsLabel.Text = string.Join("  ·  ", new[]
        {
            $"{UIStrings.PreviewStep.StatFormatsUsed} {pack.UsedStyleCount}",
            $"{UIStrings.PreviewStep.StatParagraphs} {pack.DocumentSummary.ParagraphCount}",
            $"{UIStrings.PreviewStep.StatTables} {pack.DocumentSummary.TableCount}",
            $"{UIStrings.PreviewStep.StatSections} {pack.DocumentSummary.SectionCount}"
        });

        var warnings = new List<string>();
        if (pack.ManualFormatting.ParagraphCount > 0 || pack.ManualFormatting.RunCount > 0)
        {
            warnings.Add(UIStrings.PreviewStep.ManualNotice(
                pack.ManualFormatting.ParagraphCount.ToString(),
                pack.ManualFormatting.RunCount.ToString()));
        }

        if (pack.HeadingNumberingConflicts is { Count: > 0 })
        {
            warnings.Add(UIStrings.PreviewStep.NumberingConflict(pack.HeadingNumberingConflicts.Count.ToString()));
        }

        if (pack.HeadingCompletionWarnings is { Count: > 0 })
        {
            warnings.AddRange(pack.HeadingCompletionWarnings.Take(1));
        }

        _warningLabel.Text = warnings.Count > 0
            ? string.Join(UIStrings.Success.WarningSeparator, warnings)
            : UIStrings.PreviewStep.StructureOk;
        _warningLabel.ForeColor = warnings.Count > 0 ? Theme.Amber : Theme.Success;

        _applyPackTitle.Text = UIStrings.ApplyStep.PackTitle(pack.Name);
        _applyPackSummary.Text = pack.InferredCount > 0
            ? UIStrings.ApplyStep.PackSummaryWithInferred(pack.UsedStyleCount.ToString(), pack.InferredCount.ToString())
            : UIStrings.ApplyStep.PackSummary(pack.UsedStyleCount.ToString());
        _applyNotes.Text = string.Join("\n\n", ApplyNotes.For(pack).Select(note => "✓ " + note));

        UpdatePageLayoutPanel(pack.PageLayout);
        RefreshFilterOptions(pack);
        PopulateFormatsGrid();
    }

    /// <summary>
    /// 筛选器带上每类的数量，与 Mac 端的 Pill 一致。
    /// </summary>
    private void RefreshFilterOptions(PackManifest pack)
    {
        var previousIndex = _formatFilter.SelectedIndex;
        _formatFilter.BeginUpdate();
        _formatFilter.Items.Clear();
        foreach (var option in FilterOptions)
        {
            var count = pack.UsedFormats.Count(option.Includes);
            _formatFilter.Items.Add(UIStrings.Filters.WithCount(option.Title, count.ToString()));
        }

        _formatFilter.EndUpdate();
        _formatFilter.SelectedIndex = previousIndex >= 0 && previousIndex < FilterOptions.Length
            ? previousIndex
            : 0;
    }

    private void UpdatePageLayoutPanel(PageLayout layout)
    {
        _pageOrientation.Text = FormatDisplay.Orientation(layout.Orientation);
        _pageSize.Text = FormatDisplay.PageSize(layout);
        _pageMarginVertical.Text = UIStrings.Inspector.PageMarginVertical(
            FormatDisplay.Centimeters(layout.MarginTopCm),
            FormatDisplay.Centimeters(layout.MarginBottomCm));
        _pageMarginHorizontal.Text = UIStrings.Inspector.PageMarginHorizontal(
            FormatDisplay.Centimeters(layout.MarginLeftCm),
            FormatDisplay.Centimeters(layout.MarginRightCm));
    }

    private void PopulateFormatsGrid()
    {
        if (_selectedPack is null)
        {
            return;
        }

        var selectedIdentity = _formatsGrid.SelectedRows.Count > 0
            ? (_formatsGrid.SelectedRows[0].Tag as UsedFormat)?.Identity
            : null;
        var formats = _selectedPack.UsedFormats.Where(FormatMatchesFilter).ToList();
        _formatsGrid.Rows.Clear();
        foreach (var format in formats)
        {
            var index = _formatsGrid.Rows.Add(
                format.Name,
                FormatDisplay.Usage(format),
                FormatDisplay.FontSummary(format),
                FormatDisplay.NumberingCell(format));
            _formatsGrid.Rows[index].Tag = format;
            if (format.Inferred == true)
            {
                _formatsGrid.Rows[index].DefaultCellStyle.ForeColor = Theme.Green;
            }
        }

        if (_formatsGrid.Rows.Count > 0)
        {
            var matching = _formatsGrid.Rows.Cast<DataGridViewRow>()
                .FirstOrDefault(row => (row.Tag as UsedFormat)?.Identity == selectedIdentity);
            (matching ?? _formatsGrid.Rows[0]).Selected = true;
        }
        else
        {
            _formatProperties.Text = UIStrings.PreviewStep.EmptyList;
        }
    }

    private bool FormatMatchesFilter(UsedFormat format)
    {
        var index = _formatFilter.SelectedIndex;
        if (index < 0 || index >= FilterOptions.Length)
        {
            return true;
        }

        return FilterOptions[index].Includes(format);
    }

    private void UpdateFormatInspector()
    {
        if (_formatsGrid.SelectedRows.Count == 0 || _formatsGrid.SelectedRows[0].Tag is not UsedFormat format)
        {
            return;
        }

        var builder = new StringBuilder();
        builder.AppendLine(format.Name);
        builder.AppendLine(new string('─', 22));
        AddProperty(builder, UIStrings.Inspector.LabelType, FormatDisplay.Type(format));
        AddProperty(builder, UIStrings.Inspector.LabelSource, FormatDisplay.Source(format));
        AddProperty(builder, UIStrings.Inspector.LabelFontEastAsia, FormatDisplay.Optional(format.FontEastAsia));
        AddProperty(builder, UIStrings.Inspector.LabelFontLatin, FormatDisplay.Optional(format.FontLatin));
        AddProperty(builder, UIStrings.Inspector.LabelSize, FormatDisplay.Size(format.SizePt));
        AddProperty(builder, UIStrings.Inspector.LabelTraits, FormatDisplay.Traits(format));
        AddProperty(builder, UIStrings.Inspector.LabelColor, FormatDisplay.Hex(format.ColorHex));
        if (format.Type == "paragraph")
        {
            AddProperty(builder, UIStrings.Inspector.LabelAlignment, FormatDisplay.Alignment(format.Alignment));
            AddProperty(builder, UIStrings.Inspector.LabelSpacing, FormatDisplay.Spacing(format));
            AddProperty(builder, UIStrings.Inspector.LabelLineSpacing, FormatDisplay.LineSpacing(format));
            if (format.OutlineLevel.HasValue)
            {
                AddProperty(
                    builder,
                    UIStrings.Inspector.LabelOutline,
                    UIStrings.Inspector.OutlineValue((format.OutlineLevel.Value + 1).ToString()));
            }

            AddProperty(builder, UIStrings.Inspector.LabelNumbering, FormatDisplay.Numbering(format));
        }
        else if (format.Type == "table")
        {
            AddProperty(builder, UIStrings.Inspector.LabelTableFill, FormatDisplay.Hex(format.TableFillHex));
            AddProperty(builder, UIStrings.Inspector.LabelTableAccent, FormatDisplay.Hex(format.TableAccentHex));
        }

        _formatProperties.Text = builder.ToString().TrimEnd();
    }

    private static void AddProperty(StringBuilder builder, string name, string value)
    {
        builder.Append(name).Append('：').AppendLine(value);
        builder.AppendLine();
    }

    private void NavigateToStep(int step)
    {
        if (step == 1 || _selectedPack is null)
        {
            ShowStep(1);
            return;
        }

        ShowStep(step);
    }

    private void ShowStep(int step)
    {
        _currentStep = Math.Clamp(step, 1, 3);
        _emptyPage.Visible = _currentStep == 1;
        _previewPage.Visible = _currentStep == 2;
        _applyPage.Visible = _currentStep == 3;
        if (_currentStep == 1) _emptyPage.BringToFront();
        if (_currentStep == 2) _previewPage.BringToFront();
        if (_currentStep == 3) _applyPage.BringToFront();
        for (var index = 0; index < 3; index++)
        {
            var active = index == _currentStep - 1;
            var available = index == 0 || _selectedPack is not null;
            _stepPanels[index].BackColor = active ? Theme.Mint : Color.White;
            _stepNumbers[index].BackColor = active ? Theme.Green : Color.FromArgb(231, 235, 232);
            _stepNumbers[index].ForeColor = active ? Color.White : available ? Theme.MutedInk : Color.LightGray;
            _stepTitles[index].ForeColor = active ? Theme.GreenDeep : available ? Theme.MutedInk : Color.LightGray;
            _stepSubtitles[index].ForeColor = available ? Theme.MutedInk : Color.LightGray;
        }
    }

    private void ShowToast(string message)
    {
        _toastLabel.Text = message;
        _toastPanel.Visible = true;
    }

    /// <summary>「换一套格式」的落点：闪一下常驻格式库，而不是弹文件对话框。</summary>
    private void HighlightLibrary()
    {
        _libraryList.Focus();
        _libraryHighlight.Visible = true;
        _libraryHighlight.BringToFront();
        _highlightTimer.Stop();
        _highlightTimer.Start();
    }

    private void SetBusy(bool busy, string message = "")
    {
        _isBusy = busy;
        if (busy)
        {
            _activeOperation ??= new CancellationTokenSource();
        }
        else
        {
            _activeOperation?.Dispose();
            _activeOperation = null;
        }

        if (IsDisposed || Disposing)
        {
            return;
        }

        _busyMessage.Text = message;
        _busyOverlay.Visible = busy;
        if (busy)
        {
            _busyOverlay.BringToFront();
            UseWaitCursor = true;
        }
        else
        {
            UseWaitCursor = false;
        }
    }

    private void HandleSourceDrop(DragEventArgs args)
    {
        if (args.Data?.GetData(DataFormats.FileDrop) is string[] { Length: > 0 } paths)
        {
            _ = ImportSourceAsync(paths[0]);
        }
    }

    private void HandleTargetDrop(DragEventArgs args)
    {
        if (args.Data?.GetData(DataFormats.FileDrop) is string[] { Length: > 0 } paths)
        {
            ChooseTarget(paths[0]);
        }
    }
}
