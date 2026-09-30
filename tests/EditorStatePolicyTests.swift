// [INPUT]: 依赖 Foundation
// [OUTPUT]: 验证选择归一、重置撤销、单位清空、编号表格请求与预检绑定
// [POS]: Mac 原生编辑与应用前预检的行为回归入口
// [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
import Foundation

private enum EditorTestFailure: Error { case failed(String) }

@main
struct EditorStatePolicyTests {
    @MainActor static func main() async throws {
        if CommandLine.arguments.count > 1 {
            let envelope = try JSONDecoder().decode(ManagerEnvelope.self, from: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1])))
            guard let actual = envelope.preflight else { throw EditorTestFailure.failed("真实 CLI 未返回预检") }
            try require(envelope.ok && actual.matches(demoteHeadings: actual.inputBinding.demoteHeadings, applyPageLayout: !actual.inputBinding.preservePageLayout) && actual.summary.paragraphCount > 0, "真实 CLI 预检协议必须完整解码并通过绑定校验")
        }
        try require(FormatSelectionPolicy.selectedID(current: "hidden", visibleIDs: ["visible"]) == "visible", "筛选后必须切换到可见格式")
        try require(FormatSelectionPolicy.selectedID(current: "visible", visibleIDs: []) == nil, "无结果必须清空选择")

        let heading = try format(["type": "paragraph", "outline_level": 1, "numbered": true, "numbering_level": 1, "numbering_format": "decimal", "numbering_pattern": "%1.%2", "numbering_start": 1, "numbering_restart": true, "first_line_indent_chars": 2])
        var draft = StyleEditDraft(format: heading)
        draft.leftIndentOverride = "2"
        draft.rightIndentOverride = "1"
        draft.specialIndentChoice = .firstLine
        draft.specialIndentOverride = "2"
        draft.indentUnit = .points
        try require(draft.leftIndentOverride.isEmpty && draft.rightIndentOverride.isEmpty && draft.specialIndentOverride.isEmpty && draft.specialIndentChoice == .unchanged, "切换单位必须清空本次缩进输入")
        try require(draft.format.firstLineIndentChars == 2 && draft.payload == nil, "切换单位不能改变原方案")
        draft.fontLatinOverride = "Times New Roman"
        var drafts = [draft]
        var history = StyleResetHistory()
        history.reset(&drafts)
        try require(!drafts[0].hasUserInput && history.canUndo, "重置后支持撤销")
        history.undo(&drafts)
        try require(drafts[0].fontLatinOverride == "Times New Roman" && !history.canUndo, "撤销恢复原输入")
        history.reset(&drafts)
        history.discardUndoAfterNewInput()
        history.undo(&drafts)
        try require(!drafts[0].hasUserInput, "新输入后不允许恢复旧重置快照")

        var numbered = StyleEditDraft(format: heading)
        numbered.numberingFormatChoice = .upperRoman
        numbered.numberingPatternOverride = "（%1-%2）"
        numbered.numberingStartOverride = "4"
        numbered.numberingRestartChoice = .continueCount
        let numbering = try encodedPayload(numbered)
        try require(numbering["numbering_format"] as? String == "upperRoman" && numbering["numbering_pattern"] as? String == "（%1-%2）", "数字形式与标点必须编码到后端字段")
        try require(numbering["numbering_start"] as? Int == 4 && numbering["numbering_restart"] as? Bool == false, "起始值和连续编号不能丢失")
        try require(numbering["table_border_style"] == nil && numbering["font_latin"] == nil, "只编码实际变更")
        numbered.numberingPatternOverride = "%1-%3"
        try require(numbered.validationError != nil && numbered.payload == nil, "不能引用不存在的下级编号")
        numbered.numberingPatternOverride = "%1.%2"
        numbered.numberingStartOverride = "1.5"
        try require(numbered.validationError != nil, "起始值不能为小数")
        var top = StyleEditDraft(format: try format(["outline_level": 0, "numbered": true, "numbering_level": 0]))
        top.numberingRestartChoice = .restart
        try require(top.validationError != nil, "最高层级无上级，不能随上级重启")

        var table = StyleEditDraft(format: try format(["type": "table", "style_id": "TableStyle", "table_cell_margin_top_pt": 2]))
        table.tableBorderChoice = .double
        table.tableBorderColorOverride = "#123abc"
        table.tableBorderWidthOverride = "1.25"
        table.tableMarginTopOverride = "5.5"
        table.tableMarginLeftOverride = "0"
        let borders = try encodedPayload(table)
        try require(borders["table_border_style"] as? String == "double" && borders["table_border_color_hex"] as? String == "123ABC", "表格边框字段与颜色归一")
        try require(borders["table_border_width_pt"] as? Double == 1.25 && borders["table_cell_margin_top_pt"] as? Double == 5.5 && borders["table_cell_margin_left_pt"] as? Double == 0, "精确边框宽度和零边距应保留")
        table.tableBorderWidthOverride = "1.3"
        try require(table.validationError != nil, "边框宽度必须符合八分之一磅精度")
        table.reset()
        try require(!table.hasUserInput && table.payload == nil, "表格重置清空全部新增控件")

        let report = try preflight()
        try require(report.matches(demoteHeadings: true, applyPageLayout: false), "匹配同一套预检选项")
        try require(!report.matches(demoteHeadings: false, applyPageLayout: false) && !report.matches(demoteHeadings: true, applyPageLayout: true), "任何选项变化均使预检失效")
        let malformed = try preflight(hash: String(repeating: "z", count: 64))
        try require(!malformed.matches(demoteHeadings: true, applyPageLayout: false), "不能接受非十六进制摘要")
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("forma-editor-policy-\(UUID().uuidString)")
        let model = WordFormatLibraryModel(libraryDirectory: root, automaticallyReload: false)
        model.selectedPack = try pack(path: root.appendingPathComponent("test.wfstyle").path)
        model.targetURL = root.appendingPathComponent("target.docx")
        model.demoteHeadings = true
        model.applySourcePageLayout = false
        model.preflight = report
        try require(model.canApplyPreflight, "模型允许当前有效预检")
        model.applySourcePageLayout = true
        try require(model.preflight == nil && !model.canApplyPreflight, "切换页面选项立即失效")
        model.preflight = report
        model.demoteHeadings = false
        try require(model.preflight == nil, "切换标题选项立即失效")
        model.preflight = report
        model.clearTarget()
        try require(model.preflight == nil && model.targetURL == nil, "更换文档不得复用旧预检")
        let scanning = InstalledFontCatalog(records: [], isLoaded: false)
        try require(scanning.match(name: "SimSun").kind == .loading, "扫描过程中不能把字体判断为缺失")
        let loaded = await InstalledFontCatalog.refreshSystem()
        try require(loaded.isLoaded && !loaded.families.isEmpty, "后台字体扫描完成并返回系统目录")
        print("EditorStatePolicyTests: selection, reset undo, units, numbering, tables, bindings and fonts passed")
    }

    private static func format(_ overrides: [String: Any]) throws -> UsedFormat {
        var object: [String: Any] = ["style_id": "Heading2", "name": "标题 2", "type": "paragraph", "usage_count": 1, "sample": "示例", "numbered": false]
        object.merge(overrides) { _, new in new }
        return try JSONDecoder().decode(UsedFormat.self, from: JSONSerialization.data(withJSONObject: object))
    }

    private static func encodedPayload(_ draft: StyleEditDraft) throws -> [String: Any] {
        guard let payload = draft.payload else { throw EditorTestFailure.failed(draft.validationError ?? "未生成请求") }
        return try JSONSerialization.jsonObject(with: JSONEncoder().encode(payload)) as! [String: Any]
    }

    private static func preflight(hash: String = String(repeating: "a", count: 64)) throws -> DocumentPreflight {
        let data: [String: Any] = ["summary": ["paragraph_count": 7, "table_count": 1, "character_count": 42], "heading_level_counts": ["2": 3], "heading_demotion_count": 3, "table_action": "apply_pack_table_style", "page_layout_action": "preserve_target", "font_names": ["SimSun"], "warnings": [], "input_binding": ["pack_sha256": hash, "target_sha256": hash, "demote_headings": true, "preserve_page_layout": true]]
        return try JSONDecoder().decode(DocumentPreflight.self, from: JSONSerialization.data(withJSONObject: data))
    }

    private static func pack(path: String) throws -> PackManifest {
        let data: [String: Any] = ["id": "test", "name": "测试", "pack_path": path, "used_formats": [], "used_style_count": 0, "manual_formatting": ["paragraph_count": 0, "run_count": 0], "document_summary": ["paragraph_count": 0, "run_count": 0, "table_count": 0, "section_count": 0], "page_layout": [:]]
        return try JSONDecoder().decode(PackManifest.self, from: JSONSerialization.data(withJSONObject: data))
    }

    private static func require(_ condition: @autoclosure () -> Bool, _ message: String) throws {
        guard condition() else { throw EditorTestFailure.failed(message) }
    }
}
