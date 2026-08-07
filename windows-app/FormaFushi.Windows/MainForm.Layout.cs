using System.Text;

namespace FormaFushi.Windows;

internal sealed partial class MainForm
{
    private readonly Label _libraryCount = Theme.Label("本机已保存 0 套", 9, color: Theme.MutedInk);
    private readonly FlowLayoutPanel _libraryList = new();
    private readonly Label _libraryNotice = Theme.Label("", 8.5f, color: Theme.Amber);
    private readonly Panel _contentHost = new();
    private readonly Panel _emptyPage = new();
    private readonly Panel _previewPage = new();
    private readonly Panel _applyPage = new();
    private readonly Panel[] _stepPanels = new Panel[3];
    private readonly Label[] _stepNumbers = new Label[3];
    private readonly Label[] _stepTitles = new Label[3];
    private readonly Label _previewTitle = Theme.Label("", 21, FontStyle.Bold);
    private readonly Label _previewSummary = Theme.Label("", 9.5f, color: Theme.MutedInk);
    private readonly Label _statsLabel = Theme.Label("", 10, FontStyle.Bold);
    private readonly Label _warningLabel = Theme.Label("", 9, color: Theme.Amber);
    private readonly ComboBox _formatFilter = new();
    private readonly DataGridView _formatsGrid = new();
    private readonly Label _formatProperties = Theme.Label("", 9.25f);
    private readonly Label _applyPackTitle = Theme.Label("", 14, FontStyle.Bold);
    private readonly Label _applyPackSummary = Theme.Label("", 9, color: Theme.MutedInk);
    private readonly Panel _targetEmptyPanel = new();
    private readonly Panel _targetChosenPanel = new();
    private readonly Label _targetName = Theme.Label("", 11, FontStyle.Bold);
    private readonly Label _targetPathLabel = Theme.Label("", 8.5f, color: Theme.MutedInk);
    private readonly CheckBox _applyPageLayout = new();
    private readonly CheckBox _demoteHeadings = new();
    private readonly Button _applyButton = Theme.PrimaryButton("选择保存位置并应用");
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
        Text = "Forma 赋式｜Word 文档格式引擎";
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

        FormClosing += (_, args) =>
        {
            if (_isBusy)
            {
                var shouldExit = MessageBox.Show(
                    this,
                    "文档仍在处理中。确定要退出吗？",
                    "退出 Forma 赋式",
                    MessageBoxButtons.YesNo,
                    MessageBoxIcon.Question,
                    MessageBoxDefaultButton.Button2) == DialogResult.Yes;
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
        var title = Theme.Label("Forma 赋式", 18, FontStyle.Bold, Color.White);
        title.Location = new Point(96, 19);
        var slogan = Theme.Label("一份范本，万卷同式。", 9.5f, color: Color.FromArgb(205, 226, 218));
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
            BackColor = Color.FromArgb(238, 239, 233),
            Padding = new Padding(22, 24, 18, 18)
        };
        var heading = Theme.Label("我的格式库", 15, FontStyle.Bold);
        heading.Location = new Point(22, 22);
        var hint = Theme.Label("保存后无需重复上传样板", 8.5f, color: Theme.MutedInk);
        hint.Location = new Point(23, 52);

        var importButton = Theme.PrimaryButton("＋  导入新的格式源");
        importButton.AutoSize = false;
        importButton.SetBounds(22, 82, 270, 42);
        importButton.Click += (_, _) => BrowseSource();

        var refreshButton = Theme.TextButton("刷新格式库");
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

        sidebar.Controls.Add(heading);
        sidebar.Controls.Add(hint);
        sidebar.Controls.Add(importButton);
        sidebar.Controls.Add(refreshButton);
        sidebar.Controls.Add(_libraryNotice);
        sidebar.Controls.Add(_libraryList);
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
        var titles = new[] { "导入格式源", "查看已用格式", "应用到文档" };
        for (var index = 0; index < 3; index++)
        {
            var step = new Panel { Dock = DockStyle.Fill, Padding = new Padding(8, 8, 8, 5), Cursor = Cursors.Hand };
            var number = new Label
            {
                Text = (index + 1).ToString(),
                Font = Theme.CreateFont(9, FontStyle.Bold),
                TextAlign = ContentAlignment.MiddleCenter,
                Size = new Size(28, 28),
                Location = new Point(8, 8)
            };
            var label = Theme.Label(titles[index], 9.5f, FontStyle.Bold);
            label.Location = new Point(45, 11);
            var capturedIndex = index + 1;
            step.Click += (_, _) => NavigateToStep(capturedIndex);
            number.Click += (_, _) => NavigateToStep(capturedIndex);
            label.Click += (_, _) => NavigateToStep(capturedIndex);
            step.Controls.Add(number);
            step.Controls.Add(label);
            table.Controls.Add(step, index, 0);
            _stepPanels[index] = step;
            _stepNumbers[index] = number;
            _stepTitles[index] = label;
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
            RowCount = 6,
            ColumnCount = 1,
            BackColor = Color.Transparent,
            Padding = new Padding(34, 52, 34, 35)
        };
        dropContents.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        dropContents.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        dropContents.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        dropContents.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        dropContents.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        dropContents.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        var eyebrow = Theme.Label("第一步 · 格式样板", 9, FontStyle.Bold, Theme.Green);
        var title = Theme.Label("先选择一份“格式样板”", 19, FontStyle.Bold);
        title.Margin = new Padding(0, 12, 0, 8);
        var subtitle = Theme.Label("程序只提取格式系统，不保存文档正文、页眉页脚文字或批注内容。", 10, color: Theme.MutedInk);
        subtitle.MaximumSize = new Size(430, 0);
        subtitle.Margin = new Padding(0, 0, 0, 28);
        var chooseButton = Theme.PrimaryButton("选择 Word 格式源");
        chooseButton.AutoSize = false;
        chooseButton.Width = 210;
        chooseButton.Height = 46;
        chooseButton.Margin = new Padding(0, 0, 0, 12);
        chooseButton.Click += (_, _) => BrowseSource();
        var fileHint = Theme.Label("也可以把文件拖到这里 · 支持 DOCX、DOCM、DOTX、DOTM", 8.5f, color: Theme.MutedInk);
        dropContents.Controls.Add(eyebrow);
        dropContents.Controls.Add(title);
        dropContents.Controls.Add(subtitle);
        dropContents.Controls.Add(chooseButton);
        dropContents.Controls.Add(fileHint);
        dropCard.Controls.Add(dropContents);
        dropCard.Resize += (_, _) =>
        {
            var availableWidth = Math.Max(200, dropCard.ClientSize.Width - 104);
            title.MaximumSize = new Size(availableWidth, 0);
            subtitle.MaximumSize = new Size(availableWidth, 0);
            fileHint.MaximumSize = new Size(availableWidth, 0);
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
        var infoTitle = Theme.Label("一次导入，反复使用", 13, FontStyle.Bold);
        infoTitle.Margin = new Padding(0, 0, 0, 20);
        info.Controls.Add(infoTitle);
        info.Controls.Add(FeatureRow("01", "只展示文档里真正用过的格式"));
        info.Controls.Add(FeatureRow("02", "保存标题编号、字体、段落与页面设置"));
        info.Controls.Add(FeatureRow("03", "模板不含表格样式时，保留目标表格并清掉两字符首行缩进"));
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
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 56));

        var header = new Panel { Dock = DockStyle.Fill, BackColor = Color.Transparent };
        _previewTitle.Location = new Point(0, 0);
        _previewSummary.AutoSize = false;
        _previewSummary.SetBounds(1, 39, 670, 38);
        var nextButton = Theme.PrimaryButton("下一步：选择目标文档");
        nextButton.AutoSize = false;
        nextButton.Size = new Size(210, 42);
        nextButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        nextButton.Location = new Point(680, 8);
        header.Resize += (_, _) => nextButton.Location = new Point(header.ClientSize.Width - nextButton.Width, 8);
        nextButton.Click += (_, _) => ShowStep(3);
        header.Controls.Add(_previewTitle);
        header.Controls.Add(_previewSummary);
        header.Controls.Add(nextButton);

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
        var listCard = BuildFormatsListCard();
        var inspectorCard = BuildInspectorCard();
        split.Controls.Add(listCard, 0, 0);
        split.Controls.Add(inspectorCard, 1, 0);

        var footer = new Panel { Dock = DockStyle.Fill, BackColor = Color.Transparent };
        var backButton = Theme.SecondaryButton("导入另一份模板");
        backButton.AutoSize = false;
        backButton.Size = new Size(150, 38);
        backButton.Location = new Point(0, 10);
        backButton.Click += (_, _) => BrowseSource();
        var privacy = Theme.Label("格式方案仅保存在这台电脑上，可从左侧格式库随时删除。", 8.5f, color: Theme.MutedInk);
        privacy.Location = new Point(170, 20);
        footer.Controls.Add(backButton);
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
        var title = Theme.Label("文档中使用的格式", 12, FontStyle.Bold);
        title.Location = new Point(0, 7);
        _formatFilter.DropDownStyle = ComboBoxStyle.DropDownList;
        _formatFilter.Items.AddRange(["全部", "标题", "正文与段落", "字符", "表格"]);
        _formatFilter.SelectedIndex = 0;
        _formatFilter.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        _formatFilter.SetBounds(435, 4, 126, 32);
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
        _formatsGrid.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = "格式", Name = "Name", Width = 138 });
        _formatsGrid.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = "来源", Name = "Usage", Width = 78 });
        _formatsGrid.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = "字体 / 字号", Name = "Font", Width = 138 });
        _formatsGrid.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = "编号示意", Name = "Numbering", AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill, MinimumWidth = 92 });
        _formatsGrid.SelectionChanged += (_, _) => UpdateFormatInspector();
    }

    private CardPanel BuildInspectorCard()
    {
        var card = new CardPanel { Dock = DockStyle.Fill, Margin = new Padding(10, 0, 0, 0), Padding = new Padding(18) };
        var title = Theme.Label("格式属性", 12, FontStyle.Bold);
        title.Dock = DockStyle.Top;
        title.Height = 32;
        _formatProperties.AutoSize = false;
        _formatProperties.Dock = DockStyle.Fill;
        _formatProperties.Padding = new Padding(0, 14, 0, 0);
        _formatProperties.ForeColor = Theme.Ink;
        card.Controls.Add(_formatProperties);
        card.Controls.Add(title);
        return card;
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
        var title = Theme.Label("最后，选择要修改的 Word 文件", 21, FontStyle.Bold);
        title.Location = new Point(0, 0);
        var subtitle = Theme.Label("原文件不会被覆盖；处理结果会另存为一个新文件。", 9.5f, color: Theme.MutedInk);
        subtitle.Location = new Point(1, 39);
        var back = Theme.SecondaryButton("返回检查格式");
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
        var change = Theme.TextButton("更换");
        change.AutoSize = false;
        change.Size = new Size(74, 32);
        change.Anchor = AnchorStyles.Top | AnchorStyles.Right;
        change.Click += (_, _) => ShowStep(1);
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
        var footerHint = Theme.Label("正文、图片、表格结构与页眉页脚内容会被保留", 8.5f, color: Theme.MutedInk);
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
        var title = Theme.Label("目标 Word 文件", 13, FontStyle.Bold);
        title.Dock = DockStyle.Top;
        title.Height = 38;

        _targetEmptyPanel.Dock = DockStyle.Top;
        _targetEmptyPanel.Height = 138;
        _targetEmptyPanel.BackColor = Color.FromArgb(246, 249, 247);
        _targetEmptyPanel.AllowDrop = true;
        var emptyTitle = Theme.Label("上传要修改格式的 Word 文件", 11, FontStyle.Bold);
        emptyTitle.Location = new Point(18, 17);
        var emptyHint = Theme.Label("支持 DOCX 与保留宏的 DOCM", 8.5f, color: Theme.MutedInk);
        emptyHint.Location = new Point(19, 48);
        var choose = Theme.PrimaryButton("选择目标文件");
        choose.AutoSize = false;
        choose.Size = new Size(146, 38);
        choose.Location = new Point(18, 82);
        choose.Click += (_, _) => BrowseTarget();
        _targetEmptyPanel.Controls.Add(emptyTitle);
        _targetEmptyPanel.Controls.Add(emptyHint);
        _targetEmptyPanel.Controls.Add(choose);
        _targetEmptyPanel.DragEnter += (_, args) => args.Effect = args.Data?.GetDataPresent(DataFormats.FileDrop) == true ? DragDropEffects.Copy : DragDropEffects.None;
        _targetEmptyPanel.DragDrop += (_, args) => HandleTargetDrop(args);

        _targetChosenPanel.Dock = DockStyle.Top;
        _targetChosenPanel.Height = 138;
        _targetChosenPanel.BackColor = Color.FromArgb(235, 244, 239);
        _targetChosenPanel.Visible = false;
        _targetName.Location = new Point(18, 18);
        _targetPathLabel.AutoSize = false;
        _targetPathLabel.SetBounds(19, 50, 120, 27);
        _targetPathLabel.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
        var change = Theme.SecondaryButton("更换目标文件");
        change.AutoSize = false;
        change.Size = new Size(138, 36);
        change.Location = new Point(18, 85);
        change.Click += (_, _) => BrowseTarget();
        _targetChosenPanel.Controls.Add(_targetName);
        _targetChosenPanel.Controls.Add(_targetPathLabel);
        _targetChosenPanel.Controls.Add(change);
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
        var successTitle = Theme.Label("格式已经应用完成", 12, FontStyle.Bold, Theme.Success);
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
        var open = Theme.PrimaryButton("打开结果");
        open.AutoSize = false;
        open.Dock = DockStyle.Fill;
        open.Margin = new Padding(0, 0, 4, 0);
        open.Click += (_, _) => OpenOutput();
        var reveal = Theme.SecondaryButton("在文件夹中显示");
        reveal.AutoSize = false;
        reveal.Dock = DockStyle.Fill;
        reveal.Margin = new Padding(4, 0, 4, 0);
        reveal.Click += (_, _) => RevealOutput();
        var next = Theme.TextButton("处理下一份");
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
        var title = Theme.Label("应用选项", 13, FontStyle.Bold);
        title.Dock = DockStyle.Top;
        title.Height = 42;

        _applyPageLayout.Text = "同步格式源的页面设置";
        _applyPageLayout.Checked = true;
        _applyPageLayout.AutoSize = true;
        _applyPageLayout.Font = Theme.CreateFont(10, FontStyle.Bold);
        _applyPageLayout.ForeColor = Theme.Ink;
        _applyPageLayout.Location = new Point(22, 66);
        var layoutHint = Theme.Label("包含纸张、方向与页边距", 8.5f, color: Theme.MutedInk);
        layoutHint.Location = new Point(45, 95);

        _demoteHeadings.Text = "所有标题向下调整一级";
        _demoteHeadings.AutoSize = true;
        _demoteHeadings.Font = Theme.CreateFont(10, FontStyle.Bold);
        _demoteHeadings.ForeColor = Theme.Ink;
        _demoteHeadings.Location = new Point(22, 138);
        var demoteHint = Theme.Label("标题一→标题二，标题八→标题九；标题九保持不变", 8.5f, color: Theme.MutedInk);
        demoteHint.Location = new Point(45, 167);

        var divider = new Panel { BackColor = Theme.Line, Height = 1, Left = 22, Top = 210, Width = 380, Anchor = AnchorStyles.Left | AnchorStyles.Top | AnchorStyles.Right };
        var preserved = Theme.Label("✓ 保留正文、图片、表格结构与页眉页脚内容\n\n✓ 清理旧样式和手工视觉格式\n\n✓ 表格无模板样式时保留外观，仅清掉两字符首行缩进\n\n✓ 始终另存为新文件", 9, color: Theme.MutedInk);
        preserved.AutoSize = false;
        preserved.SetBounds(22, 232, 405, 170);
        preserved.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;

        card.Controls.Add(title);
        card.Controls.Add(_applyPageLayout);
        card.Controls.Add(layoutHint);
        card.Controls.Add(_demoteHeadings);
        card.Controls.Add(demoteHint);
        card.Controls.Add(divider);
        card.Controls.Add(preserved);
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
            var empty = Theme.Label("还没有保存格式。\n\n导入一份 Word 样板后，它会出现在这里。", 9, color: Theme.MutedInk);
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
        var inferred = pack.InferredStyleCount ?? 0;
        var detailText = inferred > 0
            ? $"实际 {pack.UsedStyleCount} 种 · 补全 {inferred} 种"
            : $"实际使用 {pack.UsedStyleCount} 种格式";
        var detail = Theme.Label(detailText, 8.25f, color: Theme.MutedInk);
        detail.Location = new Point(15, 43);
        var date = Theme.Label(pack.CreatedDisplay, 8, color: Theme.MutedInk);
        date.Location = new Point(15, 69);
        var delete = Theme.TextButton("删除");
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
        var inferred = pack.InferredStyleCount ?? 0;
        var hidden = pack.HiddenStyleCount ?? Math.Max(0, (pack.DefinedStyleCount ?? pack.UsedStyleCount) - pack.UsedStyleCount);
        _previewSummary.Text = inferred > 0
            ? $"展示实际使用格式，以及按标题层级逻辑智能补全的 {inferred} 种格式；另有 {hidden} 个未使用样式已隐藏。"
            : $"只展示文档中实际使用的格式；另有 {hidden} 个未使用样式已隐藏。";
        _statsLabel.Text = $"实际使用 {pack.UsedStyleCount} 种  ·  段落 {pack.DocumentSummary.ParagraphCount}  ·  表格 {pack.DocumentSummary.TableCount}  ·  节 {pack.DocumentSummary.SectionCount}";

        var warnings = new List<string>();
        if (pack.ManualFormatting.ParagraphCount > 0 || pack.ManualFormatting.RunCount > 0)
        {
            warnings.Add($"发现 {pack.ManualFormatting.ParagraphCount} 个手工设置段落、{pack.ManualFormatting.RunCount} 处手工字符格式");
        }
        if (pack.HeadingNumberingConflicts is { Count: > 0 })
        {
            warnings.Add($"{pack.HeadingNumberingConflicts.Count} 个标题样式存在多套编号");
        }
        if (pack.HeadingCompletionWarnings is { Count: > 0 })
        {
            warnings.AddRange(pack.HeadingCompletionWarnings.Take(1));
        }
        _warningLabel.Text = warnings.Count > 0 ? "提示：" + string.Join("；", warnings) : "格式结构完整，可以继续应用到目标文档。";
        _warningLabel.ForeColor = warnings.Count > 0 ? Theme.Amber : Theme.Success;

        _applyPackTitle.Text = $"将应用：{pack.Name}";
        _applyPackSummary.Text = inferred > 0
            ? $"包含 {pack.UsedStyleCount} 种实际格式 + {inferred} 种智能补全标题"
            : $"包含 {pack.UsedStyleCount} 种实际使用格式";
        _formatFilter.SelectedIndex = 0;
        PopulateFormatsGrid();
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
            var usage = format.Inferred == true ? "智能补全" : $"用过 {format.UsageCount} 次";
            var font = string.Join(" / ", new[]
            {
                format.FontEastAsia ?? format.FontLatin ?? "继承字体",
                format.SizePt.HasValue ? $"{format.SizePt:0.##} pt" : "继承字号"
            });
            var numbering = format.Numbered
                ? format.NumberingExample ?? format.NumberingPattern ?? "自动编号"
                : "—";
            var index = _formatsGrid.Rows.Add(format.Name, usage, font, numbering);
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
            _formatProperties.Text = "这一类没有被使用的格式。";
        }
    }

    private bool FormatMatchesFilter(UsedFormat format)
    {
        return (_formatFilter.SelectedItem as string) switch
        {
            "标题" => format.Type == "paragraph" && format.OutlineLevel.HasValue,
            "正文与段落" => format.Type == "paragraph" && !format.OutlineLevel.HasValue,
            "字符" => format.Type == "character",
            "表格" => format.Type == "table",
            _ => true
        };
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
        AddProperty(builder, "类型", TypeDisplay(format.Type));
        AddProperty(builder, "来源", format.Inferred == true ? format.InferenceLabel ?? "智能补全" : $"实际使用 {format.UsageCount} 次");
        AddProperty(builder, "中文字体", format.FontEastAsia);
        AddProperty(builder, "西文字体", format.FontLatin);
        AddProperty(builder, "字号", format.SizePt.HasValue ? $"{format.SizePt:0.##} pt" : null);
        var shape = string.Join("、", new[]
        {
            format.Bold == true ? "粗体" : null,
            format.Italic == true ? "斜体" : null
        }.Where(value => value is not null));
        AddProperty(builder, "字形", string.IsNullOrWhiteSpace(shape) ? null : shape);
        AddProperty(builder, "颜色", string.IsNullOrWhiteSpace(format.ColorHex) ? null : $"#{format.ColorHex}");
        if (format.Type == "paragraph")
        {
            AddProperty(builder, "对齐", AlignmentDisplay(format.Alignment));
            AddProperty(builder, "段前 / 段后", format.SpaceBeforePt.HasValue || format.SpaceAfterPt.HasValue
                ? $"{format.SpaceBeforePt ?? 0:0.##} / {format.SpaceAfterPt ?? 0:0.##} pt"
                : null);
            AddProperty(builder, "行距", format.LineSpacing.HasValue ? $"{format.LineSpacing:0.##} ({format.LineRule ?? "自动"})" : format.LineRule);
            AddProperty(builder, "大纲级别", format.OutlineLevel.HasValue ? $"标题 {format.OutlineLevel + 1}" : null);
            AddProperty(builder, "编号", format.Numbered ? format.NumberingExample ?? format.NumberingPattern ?? "自动编号" : "无");
        }
        else if (format.Type == "table")
        {
            AddProperty(builder, "表格底色", string.IsNullOrWhiteSpace(format.TableFillHex) ? null : $"#{format.TableFillHex}");
            AddProperty(builder, "强调色", string.IsNullOrWhiteSpace(format.TableAccentHex) ? null : $"#{format.TableAccentHex}");
        }

        if (_selectedPack is not null)
        {
            var page = _selectedPack.PageLayout;
            builder.AppendLine();
            builder.AppendLine("页面设置");
            builder.AppendLine(new string('─', 22));
            AddProperty(builder, "方向", page.Orientation == "landscape" ? "横向" : page.Orientation == "portrait" ? "纵向" : page.Orientation);
            AddProperty(builder, "纸张", page.WidthCm.HasValue && page.HeightCm.HasValue ? $"{page.WidthCm:0.##} × {page.HeightCm:0.##} cm" : null);
            AddProperty(builder, "页边距", page.MarginTopCm.HasValue
                ? $"上 {page.MarginTopCm:0.##}  下 {page.MarginBottomCm:0.##}\n左 {page.MarginLeftCm:0.##}  右 {page.MarginRightCm:0.##} cm"
                : null);
        }

        _formatProperties.Text = builder.ToString().TrimEnd();
    }

    private static void AddProperty(StringBuilder builder, string name, string? value)
    {
        builder.Append(name).Append("：").AppendLine(string.IsNullOrWhiteSpace(value) ? "继承 / 未指定" : value);
        builder.AppendLine();
    }

    private static string TypeDisplay(string type) => type switch
    {
        "paragraph" => "段落样式",
        "character" => "字符样式",
        "table" => "表格样式",
        _ => type
    };

    private static string? AlignmentDisplay(string? value) => value switch
    {
        "left" => "左对齐",
        "center" => "居中",
        "right" => "右对齐",
        "both" => "两端对齐",
        "distribute" => "分散对齐",
        _ => value
    };

    private void NavigateToStep(int step)
    {
        if (step == 1)
        {
            ShowStep(1);
            return;
        }

        if (_selectedPack is null)
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
        }
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
