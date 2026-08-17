// 本文件由 scripts/gen_ui_strings.py 从 shared/ui-strings.json 生成，请勿手工编辑。
// 改文案请改 shared/ui-strings.json，然后重新运行生成器。

namespace FormaFushi.Windows.Generated;

internal static class UIStrings
{
    internal static class App
    {
        public const string WindowTitle = "Forma 赋式｜Word 文档格式引擎";
        public const string Brand = "Forma 赋式";
        public const string Slogan = "一份范本，万卷同式。";
        public static string LibraryCount(string count) => "本机已保存 " + count + " 套";
        public const string ErrorTitle = "操作没有完成";
        public const string ErrorConfirm = "好";
        public const string ExitBusyTitle = "退出 Forma 赋式";
        public const string ExitBusyMessage = "文档仍在处理中。确定要退出吗？";
        public const string ExitBusyConfirm = "仍要退出";
        public const string ExitBusyCancel = "继续等待";
    }

    internal static class Steps
    {
        public const string ImportTitle = "导入格式源";
        public const string ImportSubtitle = "保存到本机";
        public const string PreviewTitle = "查看已用格式";
        public const string PreviewSubtitle = "确认样式与页面";
        public const string ApplyTitle = "应用到文档";
        public const string ApplySubtitle = "另存为新文件";
    }

    internal static class Sidebar
    {
        public const string Title = "我的格式库";
        public const string Hint = "保存后无需重复上传样板";
        public const string ImportButton = "导入新的格式源";
        public const string RefreshButton = "刷新格式库";
        public const string Empty = "还没有保存格式。\n\n导入一份 Word 样板后，它会出现在这里。";
        public static string ReadErrorNotice(string count) => "有 " + count + " 个格式库文件无法读取，已自动跳过。";
        public static string PackSummaryWithInferred(string used, string inferred) => "实际 " + used + " 种 · 智能补全 " + inferred + " 种";
        public static string PackSummary(string used) => "实际使用 " + used + " 种格式";
        public const string PackDateUnknown = "已保存";
        public const string DeleteButton = "删除";
    }

    internal static class Deletion
    {
        public static string ConfirmTitle(string name) => "移除“" + name + "”？";
        public const string ConfirmMessage = "只会把本机保存的这套格式方案移到回收站，不会删除原来的样板 Word 文件，也不会影响已经生成的文档。";
        public const string ConfirmPrimary = "移到回收站";
        public const string ConfirmCancel = "取消";
        public static string Busy(string name) => "正在将“" + name + "”移到回收站…";
        public static string Done(string name) => "已将“" + name + "”移到回收站，需要时可以恢复。";
    }

    internal static class ImportStep
    {
        public const string Eyebrow = "第一步 · 格式样板";
        public const string Title = "先选择一份“格式样板”";
        public const string Subtitle = "程序只提取格式系统，不保存文档正文、页眉页脚文字或批注内容。";
        public const string ChooseButton = "选择 Word 格式源";
        public const string DropHint = "也可以把文件拖到这里";
        public const string SupportedFormats = "支持 DOCX、DOCM、DOTX、DOTM";
        public const string InfoTitle = "一次导入，反复使用";
        public const string Info1 = "只展示文档里真正用过的格式";
        public const string Info2 = "保存标题编号、字体、段落与页面设置";
        public const string Info3 = "模板不含表格样式时，保留目标表格并清掉两字符首行缩进";
        public static string SavedToast(string name) => "“" + name + "”已保存到本机格式库。";
    }

    internal static class FilePicker
    {
        public const string SourceTitle = "选择 Word 格式源";
        public const string SourcePrompt = "导入格式";
        public const string TargetTitle = "选择要修改格式的 Word 文件";
        public const string TargetPrompt = "选择目标文件";
        public const string SaveTitle = "保存应用格式后的 Word 文件";
        public const string SavePrompt = "应用并保存";
        public const string OutputSuffix = "-已套用格式";
        public const string SourceFilter = "Word 格式源 (*.docx;*.docm;*.dotx;*.dotm)|*.docx;*.docm;*.dotx;*.dotm";
        public const string TargetFilter = "Word 文档 (*.docx;*.docm)|*.docx;*.docm";
        public const string OutputFilterDocx = "Word 文档 (*.docx)|*.docx";
        public const string OutputFilterDocm = "启用宏的 Word 文档 (*.docm)|*.docm";
    }

    internal static class PreviewStep
    {
        public static string SummaryWithInferred(string inferred, string hidden) => "展示实际使用格式，以及按标题层级逻辑智能补全的 " + inferred + " 种格式；另有 " + hidden + " 个未使用样式已隐藏。";
        public static string Summary(string hidden) => "只展示文档中实际使用的格式；另有 " + hidden + " 个未使用样式已隐藏。";
        public const string NextButton = "下一步：选择目标文档";
        public const string SwitchPackButton = "换一套格式";
        public const string ListTitle = "文档中使用的格式";
        public const string EmptyList = "这一类没有被使用的格式。";
        public const string Privacy = "格式方案仅保存在这台电脑上，可从格式库随时删除。";
        public const string StatFormatsUsed = "实际使用";
        public const string StatFormatsBoth = "实际 + 补全";
        public const string StatParagraphs = "段落";
        public const string StatTables = "表格";
        public const string StatSections = "节";
        public static string ManualNotice(string paragraphs, string runs) => "发现 " + paragraphs + " 个手工设置段落、" + runs + " 处手工字符格式。它们不是可复用样式，因此不会出现在下方列表中；应用时会清理目标文档的手工视觉格式。";
        public static string NumberingConflict(string count) => "检测到 " + count + " 个标题样式使用多套编号；将采用最常用规则，请在生成后检查章节重启。";
        public const string StructureOk = "格式结构完整，可以继续应用到目标文档。";
    }

    internal static class Filters
    {
        public const string All = "全部";
        public const string Headings = "标题";
        public const string Paragraphs = "正文与段落";
        public const string Characters = "字符";
        public const string Tables = "表格";
        public static string WithCount(string name, string count) => name + " " + count;
    }

    internal static class FormatList
    {
        public const string ColumnName = "格式";
        public const string ColumnUsage = "来源";
        public const string ColumnFont = "字体 / 字号";
        public const string ColumnNumbering = "编号示意";
        public const string UsageInferred = "智能补全";
        public static string UsageCount(string count) => "用过 " + count + " 次";
        public const string InheritFont = "继承字体";
        public const string InheritSize = "继承字号";
        public const string BadgeHeading = "标题";
        public const string BadgeParagraph = "段落";
        public const string BadgeCharacter = "字符";
        public const string BadgeTable = "表格";
    }

    internal static class Inspector
    {
        public const string Title = "格式属性";
        public const string Empty = "选择一张格式卡片查看详细属性。";
        public const string Inherit = "继承 / 未指定";
        public const string LabelType = "类型";
        public const string LabelSource = "来源";
        public const string LabelFontEastAsia = "中文字体";
        public const string LabelFontLatin = "西文字体";
        public const string LabelSize = "字号";
        public const string LabelTraits = "字形";
        public const string LabelColor = "颜色";
        public const string LabelAlignment = "对齐";
        public const string LabelSpacing = "段前 / 段后";
        public const string LabelLineSpacing = "行距";
        public const string LabelOutline = "大纲级别";
        public const string LabelNumbering = "编号";
        public const string LabelTableFill = "表格底色";
        public const string LabelTableAccent = "强调色";
        public static string SourceUsedCount(string count) => "实际使用 " + count + " 次";
        public static string TypeHeading(string level) => level + " 级标题";
        public const string TypeParagraph = "段落样式";
        public const string TypeCharacter = "字符样式";
        public const string TypeTable = "表格样式";
        public const string TraitBold = "粗体";
        public const string TraitItalic = "斜体";
        public const string TraitRegular = "常规";
        public const string TraitSeparator = "、";
        public const string AlignLeft = "左对齐";
        public const string AlignCenter = "居中";
        public const string AlignRight = "右对齐";
        public const string AlignJustify = "两端对齐";
        public const string AlignDistribute = "分散对齐";
        public static string SpacingValue(string before, string after) => before + " / " + after + " pt";
        public static string SizeValue(string size) => size + " pt";
        public static string LineSpacingMultiple(string value) => value + " 倍";
        public static string LineSpacingExact(string value) => value + " pt";
        public static string OutlineValue(string level) => level + " 级";
        public static string NumberingWithExample(string example) => "自动编号（示意：" + example + "）";
        public const string NumberingPlain = "自动编号";
        public const string NumberingNone = "无";
        public const string PageTitle = "页面设置";
        public const string PageOrientationLandscape = "横向";
        public const string PageOrientationPortrait = "纵向";
        public const string PageLabelSize = "纸张";
        public const string PageLabelMargins = "页边距";
        public static string PageSizeValue(string width, string height) => width + " × " + height + " cm";
        public const string PageSizeDefault = "使用文档默认页面";
        public static string PageMarginVertical(string top, string bottom) => "上 / 下：" + top + " / " + bottom;
        public static string PageMarginHorizontal(string left, string right) => "左 / 右：" + left + " / " + right;
        public static string CentimeterValue(string value) => value + " cm";
    }

    internal static class ApplyStep
    {
        public const string Title = "最后，选择要修改的 Word 文件";
        public const string Subtitle = "原文件不会被覆盖；处理结果会另存为一个新文件。";
        public const string BackButton = "返回检查格式";
        public static string PackTitle(string name) => "将应用：" + name;
        public static string PackSummaryWithInferred(string used, string inferred) => "包含 " + used + " 种实际格式 + " + inferred + " 种智能补全标题";
        public static string PackSummary(string used) => "包含 " + used + " 种实际使用格式";
        public const string ChangePackButton = "更换";
        public const string TargetTitle = "目标 Word 文件";
        public const string TargetEmptyTitle = "上传要修改格式的 Word 文件";
        public const string TargetEmptyHint = "支持 DOCX 与保留宏的 DOCM";
        public const string TargetDropHint = "也可以把文件拖到这里";
        public const string ChooseTargetButton = "选择目标文件";
        public const string ChangeTargetButton = "更换目标文件";
        public const string OptionsTitle = "应用选项";
        public const string OptionPageLayout = "同步格式源的页面设置";
        public const string OptionPageLayoutHint = "包含纸张、方向与页边距";
        public const string OptionDemote = "所有标题向下调整一级";
        public const string OptionDemoteHint = "标题一→标题二，标题八→标题九";
        public const string OptionDemoteNote = "标题九受 Word 上限保持不变；若再次对已处理文件勾选，会再向下一级。";
        public const string NoteKeepContent = "保留正文、图片、表格结构与页眉页脚内容";
        public const string NoteCleanup = "清理旧样式与手工视觉格式";
        public const string NoteInferredHeadings = "用标题一至标题三的设计逻辑补全标题四、标题五";
        public const string NoteSaveAsNew = "始终另存为新文件";
        public const string NoteNumbering = "同步标题多级编号，例如 1、1.1、1.1.1";
        public const string NoteManualPrefix = "自动清理与层级计数一致的手工序号，例如“第三章”“3.1”";
        public const string NoteTableFallback = "格式库没有表格样式：保留表格外观，并用稳定样式取消单元格的两字符首行缩进";
        public const string ApplyButton = "选择保存位置并应用";
        public const string ApplyAgainButton = "重新生成";
    }

    internal static class Success
    {
        public const string Title = "格式已经应用完成";
        public static string Warnings(string details) => "请留意：" + details;
        public const string WarningSeparator = "；";
        public const string OpenButton = "打开结果";
        public const string RevealButton = "在文件夹中显示";
        public const string NextButton = "处理下一份";
    }

    internal static class EmptySelection
    {
        public const string Title = "还没有选择格式库";
        public const string Action = "返回导入";
    }

    internal static class Busy
    {
        public const string LoadingLibrary = "正在读取本机格式库…";
        public const string Importing = "正在识别文档中实际使用的格式…";
        public static string Applying(string name) => "正在清理旧格式并应用“" + name + "”…";
    }

    internal static class Errors
    {
        public const string UnsupportedSource = "请选择 .docx、.docm、.dotx 或 .dotm 格式的 Word 文件。";
        public const string UnsupportedTarget = "目标文件只支持 .docx 或 .docm。";
        public const string MissingSelection = "请先选择格式库和要修改的 Word 文件。";
        public const string ExtensionMismatch = "输出文件必须与目标文件保持相同扩展名。";
        public const string SameAsTarget = "为保护原文件，请另存为一个新文件。";
        public const string PackMissingInfo = "格式已读取，但没有返回可展示的信息。";
        public const string OutputMissing = "生成的文件已经移动或删除。";
        public static string OpenFailed(string detail) => "无法打开生成的文件：" + detail;
        public static string RevealFailed(string detail) => "无法在文件夹中显示结果：" + detail;
        public const string PackNotInLibrary = "这套格式已不在当前格式库中，请刷新后重试。";
        public const string PackWithoutPath = "这套格式缺少本机存储位置，无法删除。";
        public const string PackOutsideLibrary = "为保护其他文件，只能删除格式库目录中的 .wfstyle 格式方案。";
        public const string PackEscapesLibrary = "检测到格式方案指向格式库以外的位置，已停止删除。";
        public const string PackNotRegularFile = "为保护其他内容，只能删除普通的 .wfstyle 格式库文件。";
        public const string PackMissingFile = "这套格式文件已经不存在，请刷新格式库。";
        public const string EmptyResult = "文档处理组件没有返回结果。";
        public const string UnreadableResult = "无法读取文档处理结果。";
        public static string UnreadableResultDetail(string detail) => "无法读取文档处理结果：" + detail;
        public static string TransferFailedDetail(string detail) => "文档处理失败：" + detail;
        public const string TransferFailed = "文档处理失败。";
        public const string ManagerExit = "文档处理组件异常退出。";
        public const string ManagerMissing = "应用资源不完整：找不到 style_pack_manager.py。请重新安装应用。";
        public const string RuntimeMissing = "应用资源不完整：找不到 Python 运行环境。请重新安装应用。";
        public static string ManagerLaunchFailed(string detail) => "无法启动文档处理组件：" + detail;
        public const string ManagerLaunchFailedPlain = "无法启动文档处理组件。";
        public const string Unauthorized = "无法读取或写入所选位置，请选择“文档”或桌面等可写位置。";
        public const string FileNotFound = "所选文件已被移动或删除，请重新选择。";
        public const string FileLocked = "文件正在被 Word 或其他程序占用，请关闭文件后重试。";
    }
}
