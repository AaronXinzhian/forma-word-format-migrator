// 本文件由 scripts/gen_ui_strings.py 从 shared/ui-strings.json 生成，请勿手工编辑。
// 改文案请改 shared/ui-strings.json，然后重新运行生成器。

import Foundation

enum UIStrings {
    enum App {
        static let windowTitle = "Forma 赋式｜Word 文档格式引擎"
        static let brand = "Forma 赋式"
        static let slogan = "一份范本，万卷同式。"
        static func libraryCount(count: String) -> String {
            "本机已保存 " + count + " 套"
        }
        static let errorTitle = "操作没有完成"
        static let errorConfirm = "好"
        static let exitBusyTitle = "退出 Forma 赋式"
        static let exitBusyMessage = "文档仍在处理中。确定要退出吗？"
        static let exitBusyConfirm = "仍要退出"
        static let exitBusyCancel = "继续等待"
    }

    enum Steps {
        static let importTitle = "导入格式源"
        static let importSubtitle = "保存到本机"
        static let previewTitle = "查看已用格式"
        static let previewSubtitle = "确认样式与页面"
        static let applyTitle = "应用到文档"
        static let applySubtitle = "另存为新文件"
    }

    enum Sidebar {
        static let title = "我的格式库"
        static let hint = "保存后无需重复上传样板"
        static let importButton = "导入新的格式源"
        static let refreshButton = "刷新格式库"
        static let empty = "还没有保存格式。\n\n导入一份 Word 样板后，它会出现在这里。"
        static func readErrorNotice(count: String) -> String {
            "有 " + count + " 个格式库文件无法读取，已自动跳过。"
        }
        static func packSummaryWithInferred(used: String, inferred: String) -> String {
            "实际 " + used + " 种 · 智能补全 " + inferred + " 种"
        }
        static func packSummary(used: String) -> String {
            "实际使用 " + used + " 种格式"
        }
        static let packDateUnknown = "已保存"
        static let deleteButton = "删除"
    }

    enum Deletion {
        static func confirmTitle(name: String) -> String {
            "移除“" + name + "”？"
        }
        static let confirmMessage = "只会把本机保存的这套格式方案移到废纸篓，不会删除原来的样板 Word 文件，也不会影响已经生成的文档。"
        static let confirmPrimary = "移到废纸篓"
        static let confirmCancel = "取消"
        static func busy(name: String) -> String {
            "正在将“" + name + "”移到废纸篓…"
        }
        static func done(name: String) -> String {
            "已将“" + name + "”移到废纸篓，需要时可以恢复。"
        }
    }

    enum ImportStep {
        static let eyebrow = "第一步 · 格式样板"
        static let title = "先选择一份“格式样板”"
        static let subtitle = "程序只提取格式系统，不保存文档正文、页眉页脚文字或批注内容。"
        static let chooseButton = "选择 Word 格式源"
        static let dropHint = "也可以把文件拖到这里"
        static let supportedFormats = "支持 DOCX、DOCM、DOTX、DOTM"
        static let infoTitle = "一次导入，反复使用"
        static let info1 = "只展示文档里真正用过的格式"
        static let info2 = "保存标题编号、字体、段落与页面设置"
        static let info3 = "模板不含表格样式时，保留目标表格并清掉两字符首行缩进"
        static func savedToast(name: String) -> String {
            "“" + name + "”已保存到本机格式库。"
        }
    }

    enum FilePicker {
        static let sourceTitle = "选择 Word 格式源"
        static let sourcePrompt = "导入格式"
        static let targetTitle = "选择要修改格式的 Word 文件"
        static let targetPrompt = "选择目标文件"
        static let saveTitle = "保存应用格式后的 Word 文件"
        static let savePrompt = "应用并保存"
        static let outputSuffix = "-已套用格式"
        static let sourceFilter = "Word 格式源 (*.docx;*.docm;*.dotx;*.dotm)|*.docx;*.docm;*.dotx;*.dotm"
        static let targetFilter = "Word 文档 (*.docx;*.docm)|*.docx;*.docm"
        static let outputFilterDocx = "Word 文档 (*.docx)|*.docx"
        static let outputFilterDocm = "启用宏的 Word 文档 (*.docm)|*.docm"
    }

    enum PreviewStep {
        static func summaryWithInferred(inferred: String, hidden: String) -> String {
            "展示实际使用格式，以及按标题层级逻辑智能补全的 " + inferred + " 种格式；另有 " + hidden + " 个未使用样式已隐藏。"
        }
        static func summary(hidden: String) -> String {
            "只展示文档中实际使用的格式；另有 " + hidden + " 个未使用样式已隐藏。"
        }
        static let nextButton = "下一步：选择目标文档"
        static let switchPackButton = "换一套格式"
        static let listTitle = "文档中使用的格式"
        static let emptyList = "这一类没有被使用的格式。"
        static let privacy = "格式方案仅保存在这台电脑上，可从格式库随时删除。"
        static let statFormatsUsed = "实际使用"
        static let statFormatsBoth = "实际 + 补全"
        static let statParagraphs = "段落"
        static let statTables = "表格"
        static let statSections = "节"
        static func manualNotice(paragraphs: String, runs: String) -> String {
            "发现 " + paragraphs + " 个手工设置段落、" + runs + " 处手工字符格式。它们不是可复用样式，因此不会出现在下方列表中；应用时会清理目标文档的手工视觉格式。"
        }
        static func numberingConflict(count: String) -> String {
            "检测到 " + count + " 个标题样式使用多套编号；将采用最常用规则，请在生成后检查章节重启。"
        }
        static let structureOk = "格式结构完整，可以继续应用到目标文档。"
    }

    enum Filters {
        static let all = "全部"
        static let headings = "标题"
        static let paragraphs = "正文与段落"
        static let characters = "字符"
        static let tables = "表格"
        static func withCount(name: String, count: String) -> String {
            name + " " + count
        }
    }

    enum FormatList {
        static let columnName = "格式"
        static let columnUsage = "来源"
        static let columnFont = "字体 / 字号"
        static let columnNumbering = "编号示意"
        static let usageInferred = "智能补全"
        static func usageCount(count: String) -> String {
            "用过 " + count + " 次"
        }
        static let inheritFont = "继承字体"
        static let inheritSize = "继承字号"
        static let badgeHeading = "标题"
        static let badgeParagraph = "段落"
        static let badgeCharacter = "字符"
        static let badgeTable = "表格"
    }

    enum Inspector {
        static let title = "格式属性"
        static let empty = "选择一张格式卡片查看详细属性。"
        static let inherit = "继承 / 未指定"
        static let labelType = "类型"
        static let labelSource = "来源"
        static let labelFontEastAsia = "中文字体"
        static let labelFontLatin = "西文字体"
        static let labelSize = "字号"
        static let labelTraits = "字形"
        static let labelColor = "颜色"
        static let labelAlignment = "对齐"
        static let labelSpacing = "段前 / 段后"
        static let labelLineSpacing = "行距"
        static let labelOutline = "大纲级别"
        static let labelNumbering = "编号"
        static let labelTableFill = "表格底色"
        static let labelTableAccent = "强调色"
        static func sourceUsedCount(count: String) -> String {
            "实际使用 " + count + " 次"
        }
        static func typeHeading(level: String) -> String {
            level + " 级标题"
        }
        static let typeParagraph = "段落样式"
        static let typeCharacter = "字符样式"
        static let typeTable = "表格样式"
        static let traitBold = "粗体"
        static let traitItalic = "斜体"
        static let traitRegular = "常规"
        static let traitSeparator = "、"
        static let alignLeft = "左对齐"
        static let alignCenter = "居中"
        static let alignRight = "右对齐"
        static let alignJustify = "两端对齐"
        static let alignDistribute = "分散对齐"
        static func spacingValue(before: String, after: String) -> String {
            before + " / " + after + " pt"
        }
        static func sizeValue(size: String) -> String {
            size + " pt"
        }
        static func lineSpacingMultiple(value: String) -> String {
            value + " 倍"
        }
        static func lineSpacingExact(value: String) -> String {
            value + " pt"
        }
        static func outlineValue(level: String) -> String {
            level + " 级"
        }
        static func numberingWithExample(example: String) -> String {
            "自动编号（示意：" + example + "）"
        }
        static let numberingPlain = "自动编号"
        static let numberingNone = "无"
        static let pageTitle = "页面设置"
        static let pageOrientationLandscape = "横向"
        static let pageOrientationPortrait = "纵向"
        static let pageLabelSize = "纸张"
        static let pageLabelMargins = "页边距"
        static func pageSizeValue(width: String, height: String) -> String {
            width + " × " + height + " cm"
        }
        static let pageSizeDefault = "使用文档默认页面"
        static func pageMarginVertical(top: String, bottom: String) -> String {
            "上 / 下：" + top + " / " + bottom
        }
        static func pageMarginHorizontal(left: String, right: String) -> String {
            "左 / 右：" + left + " / " + right
        }
        static func centimeterValue(value: String) -> String {
            value + " cm"
        }
    }

    enum ApplyStep {
        static let title = "最后，选择要修改的 Word 文件"
        static let subtitle = "原文件不会被覆盖；处理结果会另存为一个新文件。"
        static let backButton = "返回检查格式"
        static func packTitle(name: String) -> String {
            "将应用：" + name
        }
        static func packSummaryWithInferred(used: String, inferred: String) -> String {
            "包含 " + used + " 种实际格式 + " + inferred + " 种智能补全标题"
        }
        static func packSummary(used: String) -> String {
            "包含 " + used + " 种实际使用格式"
        }
        static let changePackButton = "更换"
        static let targetTitle = "目标 Word 文件"
        static let targetEmptyTitle = "上传要修改格式的 Word 文件"
        static let targetEmptyHint = "支持 DOCX 与保留宏的 DOCM"
        static let targetDropHint = "也可以把文件拖到这里"
        static let chooseTargetButton = "选择目标文件"
        static let changeTargetButton = "更换目标文件"
        static let optionsTitle = "应用选项"
        static let optionPageLayout = "同步格式源的页面设置"
        static let optionPageLayoutHint = "包含纸张、方向与页边距"
        static let optionDemote = "所有标题向下调整一级"
        static let optionDemoteHint = "标题一→标题二，标题八→标题九"
        static let optionDemoteNote = "标题九受 Word 上限保持不变；若再次对已处理文件勾选，会再向下一级。"
        static let noteKeepContent = "保留正文、图片、表格结构与页眉页脚内容"
        static let noteCleanup = "清理旧样式与手工视觉格式"
        static let noteInferredHeadings = "用标题一至标题三的设计逻辑补全标题四、标题五"
        static let noteSaveAsNew = "始终另存为新文件"
        static let noteNumbering = "同步标题多级编号，例如 1、1.1、1.1.1"
        static let noteManualPrefix = "自动清理与层级计数一致的手工序号，例如“第三章”“3.1”"
        static let noteTableFallback = "格式库没有表格样式：保留表格外观，并用稳定样式取消单元格的两字符首行缩进"
        static let applyButton = "选择保存位置并应用"
        static let applyAgainButton = "重新生成"
    }

    enum Success {
        static let title = "格式已经应用完成"
        static func warnings(details: String) -> String {
            "请留意：" + details
        }
        static let warningSeparator = "；"
        static let openButton = "打开结果"
        static let revealButton = "在 Finder 中显示"
        static let nextButton = "处理下一份"
    }

    enum EmptySelection {
        static let title = "还没有选择格式库"
        static let action = "返回导入"
    }

    enum Busy {
        static let loadingLibrary = "正在读取本机格式库…"
        static let importing = "正在识别文档中实际使用的格式…"
        static func applying(name: String) -> String {
            "正在清理旧格式并应用“" + name + "”…"
        }
    }

    enum Errors {
        static let unsupportedSource = "请选择 .docx、.docm、.dotx 或 .dotm 格式的 Word 文件。"
        static let unsupportedTarget = "目标文件只支持 .docx 或 .docm。"
        static let missingSelection = "请先选择格式库和要修改的 Word 文件。"
        static let extensionMismatch = "输出文件必须与目标文件保持相同扩展名。"
        static let sameAsTarget = "为保护原文件，请另存为一个新文件。"
        static let packMissingInfo = "格式已读取，但没有返回可展示的信息。"
        static let outputMissing = "生成的文件已经移动或删除。"
        static func openFailed(detail: String) -> String {
            "无法打开生成的文件：" + detail
        }
        static func revealFailed(detail: String) -> String {
            "无法在文件夹中显示结果：" + detail
        }
        static let packNotInLibrary = "这套格式已不在当前格式库中，请刷新后重试。"
        static let packWithoutPath = "这套格式缺少本机存储位置，无法删除。"
        static let packOutsideLibrary = "为保护其他文件，只能删除格式库目录中的 .wfstyle 格式方案。"
        static let packEscapesLibrary = "检测到格式方案指向格式库以外的位置，已停止删除。"
        static let packNotRegularFile = "为保护其他内容，只能删除普通的 .wfstyle 格式库文件。"
        static let packMissingFile = "这套格式文件已经不存在，请刷新格式库。"
        static let emptyResult = "文档处理组件没有返回结果。"
        static let unreadableResult = "无法读取文档处理结果。"
        static func unreadableResultDetail(detail: String) -> String {
            "无法读取文档处理结果：" + detail
        }
        static func transferFailedDetail(detail: String) -> String {
            "文档处理失败：" + detail
        }
        static let transferFailed = "文档处理失败。"
        static let managerExit = "文档处理组件异常退出。"
        static let managerMissing = "应用资源不完整：找不到 style_pack_manager.py。请重新安装应用。"
        static let runtimeMissing = "应用资源不完整：找不到 Python 运行环境。请重新安装应用。"
        static func managerLaunchFailed(detail: String) -> String {
            "无法启动文档处理组件：" + detail
        }
        static let managerLaunchFailedPlain = "无法启动文档处理组件。"
        static let unauthorized = "无法读取或写入所选位置，请选择“文档”或桌面等可写位置。"
        static let fileNotFound = "所选文件已被移动或删除，请重新选择。"
        static let fileLocked = "文件正在被 Word 或其他程序占用，请关闭文件后重试。"
    }
}
