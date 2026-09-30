// [INPUT]: 依赖 AppKit, Darwin, SwiftUI, UniformTypeIdentifiers
// [OUTPUT]: 提供PackModels 中的类型与接口
// [POS]: Mac 原生终端 - 样式与格式库、编辑请求、处理结果及删除策略模型
// [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
import AppKit
import Darwin
import SwiftUI
import UniformTypeIdentifiers

struct UsedFormat: Codable, Hashable, Identifiable {
    let styleID: String
    let name: String
    let type: String
    let usageCount: Int
    let inferred: Bool?
    let configured: Bool?
    let inferenceLabel: String?
    let sample: String
    let fontLatin: String?
    let fontEastAsia: String?
    let fontLatinAliases: [String]?
    let fontEastAsiaAliases: [String]?
    let sizePt: Double?
    let bold: Bool?
    let italic: Bool?
    let colorHex: String?
    let alignment: String?
    let spaceBeforePt: Double?
    let spaceAfterPt: Double?
    let lineSpacing: Double?
    let lineRule: String?
    let leftIndentPt: Double?
    let rightIndentPt: Double?
    let firstLineIndentPt: Double?
    let hangingIndentPt: Double?
    let leftIndentChars: Double?
    let rightIndentChars: Double?
    let firstLineIndentChars: Double?
    let hangingIndentChars: Double?
    let outlineLevel: Int?
    let numbered: Bool
    let numberingLevel: Int?
    let numberingFormat: String?
    let numberingPattern: String?
    let numberingExample: String?
    let tableFillHex: String?
    let tableAccentHex: String?
    var numberingStart: Int? = nil
    var numberingRestart: Bool? = nil
    var tableBorderStyle: String? = nil
    var tableBorderColorHex: String? = nil
    var tableBorderWidthPt: Double? = nil
    var tableCellMarginTopPt: Double? = nil
    var tableCellMarginBottomPt: Double? = nil
    var tableCellMarginLeftPt: Double? = nil
    var tableCellMarginRightPt: Double? = nil

    var id: String { "\(type):\(styleID)" }

    enum CodingKeys: String, CodingKey {
        case styleID = "style_id"
        case name, type
        case usageCount = "usage_count"
        case inferred
        case configured
        case inferenceLabel = "inference_label"
        case sample
        case fontLatin = "font_latin"
        case fontEastAsia = "font_east_asia"
        case fontLatinAliases = "font_latin_aliases"
        case fontEastAsiaAliases = "font_east_asia_aliases"
        case sizePt = "size_pt"
        case bold, italic
        case colorHex = "color_hex"
        case alignment
        case spaceBeforePt = "space_before_pt"
        case spaceAfterPt = "space_after_pt"
        case lineSpacing = "line_spacing"
        case lineRule = "line_rule"
        case leftIndentPt = "left_indent_pt"
        case rightIndentPt = "right_indent_pt"
        case firstLineIndentPt = "first_line_indent_pt"
        case hangingIndentPt = "hanging_indent_pt"
        case leftIndentChars = "left_indent_chars"
        case rightIndentChars = "right_indent_chars"
        case firstLineIndentChars = "first_line_indent_chars"
        case hangingIndentChars = "hanging_indent_chars"
        case outlineLevel = "outline_level"
        case numbered
        case numberingLevel = "numbering_level"
        case numberingFormat = "numbering_format"
        case numberingPattern = "numbering_pattern"
        case numberingExample = "numbering_example"
        case tableFillHex = "table_fill_hex"
        case tableAccentHex = "table_accent_hex"
        case numberingStart = "numbering_start"
        case numberingRestart = "numbering_restart"
        case tableBorderStyle = "table_border_style"
        case tableBorderColorHex = "table_border_color_hex"
        case tableBorderWidthPt = "table_border_width_pt"
        case tableCellMarginTopPt = "table_cell_margin_top_pt"
        case tableCellMarginBottomPt = "table_cell_margin_bottom_pt"
        case tableCellMarginLeftPt = "table_cell_margin_left_pt"
        case tableCellMarginRightPt = "table_cell_margin_right_pt"
    }
}

struct ManualFormatting: Codable, Hashable {
    let paragraphCount: Int
    let runCount: Int

    enum CodingKeys: String, CodingKey {
        case paragraphCount = "paragraph_count"
        case runCount = "run_count"
    }
}

struct DocumentSummary: Codable, Hashable {
    let paragraphCount: Int
    let runCount: Int
    let tableCount: Int
    let sectionCount: Int

    enum CodingKeys: String, CodingKey {
        case paragraphCount = "paragraph_count"
        case runCount = "run_count"
        case tableCount = "table_count"
        case sectionCount = "section_count"
    }
}

struct PageLayout: Codable, Hashable {
    let widthCM: Double?
    let heightCM: Double?
    let orientation: String?
    let marginTopCM: Double?
    let marginBottomCM: Double?
    let marginLeftCM: Double?
    let marginRightCM: Double?

    enum CodingKeys: String, CodingKey {
        case widthCM = "width_cm"
        case heightCM = "height_cm"
        case orientation
        case marginTopCM = "margin_top_cm"
        case marginBottomCM = "margin_bottom_cm"
        case marginLeftCM = "margin_left_cm"
        case marginRightCM = "margin_right_cm"
    }
}

struct PackManifest: Codable, Hashable, Identifiable {
    let id: String
    let name: String
    let sourceFileName: String?
    let sourceSHA256: String?
    let createdAt: String?
    let usedFormats: [UsedFormat]
    let tableStyleEditCandidate: UsedFormat?
    let usedStyleCount: Int
    let inferredStyleCount: Int?
    let customStyleCount: Int?
    let inferredHeadingStyles: [String]?
    let definedStyleCount: Int?
    let hiddenStyleCount: Int?
    let headingNumberingConflicts: [String]?
    let headingCompletionWarnings: [String]?
    let manualFormatting: ManualFormatting
    let documentSummary: DocumentSummary
    let pageLayout: PageLayout
    let packPath: String?

    enum CodingKeys: String, CodingKey {
        case id, name
        case sourceFileName = "source_file_name"
        case sourceSHA256 = "source_sha256"
        case createdAt = "created_at"
        case usedFormats = "used_formats"
        case tableStyleEditCandidate = "table_style_edit_candidate"
        case usedStyleCount = "used_style_count"
        case inferredStyleCount = "inferred_style_count"
        case customStyleCount = "custom_style_count"
        case inferredHeadingStyles = "inferred_heading_styles"
        case definedStyleCount = "defined_style_count"
        case hiddenStyleCount = "hidden_style_count"
        case headingNumberingConflicts = "heading_numbering_conflicts"
        case headingCompletionWarnings = "heading_completion_warnings"
        case manualFormatting = "manual_formatting"
        case documentSummary = "document_summary"
        case pageLayout = "page_layout"
        case packPath = "pack_path"
    }

    var packURL: URL? {
        guard let packPath else { return nil }
        return URL(fileURLWithPath: packPath)
    }

    var libraryIdentity: String { packPath ?? id }
    var inferredCount: Int { inferredStyleCount ?? 0 }
    var hiddenCount: Int {
        hiddenStyleCount ?? max(0, (definedStyleCount ?? usedStyleCount) - usedStyleCount)
    }
    var createdDisplay: String {
        guard let createdAt, let date = ISO8601DateFormatter().date(from: createdAt) else {
            return UIStrings.Sidebar.packDateUnknown
        }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_CN")
        formatter.dateFormat = "yyyy/MM/dd"
        return formatter.string(from: date)
    }

    var resolvedCustomStyleCount: Int {
        customStyleCount ?? usedFormats.filter { $0.configured == true }.count
    }

    var formatCountSummary: String {
        var parts = ["实际 \(usedStyleCount) 种"]
        if (inferredStyleCount ?? 0) > 0 {
            parts.append("智能补全 \(inferredStyleCount ?? 0) 种")
        }
        if resolvedCustomStyleCount > 0 {
            parts.append("自定义 \(resolvedCustomStyleCount) 种")
        }
        return parts.joined(separator: " · ")
    }

    var formatOverviewDescription: String {
        var scopes = ["实际使用格式"]
        if (inferredStyleCount ?? 0) > 0 {
            scopes.append("按标题层级逻辑智能补全的 \(inferredStyleCount ?? 0) 种标题格式")
        }
        if resolvedCustomStyleCount > 0 {
            scopes.append("\(resolvedCustomStyleCount) 种主动配置的表格方案")
        }
        return "展示" + scopes.joined(separator: "，以及") +
            "；另有 \(hiddenStyleCount ?? 0) 个未使用样式已隐藏"
    }
}

struct ManagerEnvelope: Decodable {
    let ok: Bool
    let error: String?
    let pack: PackManifest?
    let packs: [PackManifest]?
    let output: String?
    let errors: [LibraryReadError]?
    let stats: TransferStats?
    let preflight: DocumentPreflight?
    let imported: Bool?
}

struct DocumentPreflight: Decodable, Hashable {
    struct Summary: Decodable, Hashable {
        let paragraphCount: Int
        let tableCount: Int
        let characterCount: Int
        enum CodingKeys: String, CodingKey {
            case paragraphCount = "paragraph_count", tableCount = "table_count"
            case characterCount = "character_count"
        }
    }
    struct InputBinding: Decodable, Hashable {
        let packSHA256: String
        let targetSHA256: String
        let demoteHeadings: Bool
        let preservePageLayout: Bool
        enum CodingKeys: String, CodingKey {
            case packSHA256 = "pack_sha256", targetSHA256 = "target_sha256"
            case demoteHeadings = "demote_headings", preservePageLayout = "preserve_page_layout"
        }
    }
    let summary: Summary
    let headingLevelCounts: [String: Int]
    let headingDemotionCount: Int
    let tableAction: String
    let pageLayoutAction: String
    let fontNames: [String]
    let warnings: [String]
    let inputBinding: InputBinding
    var runtimeInferredHeadingLevels: [Int]? = nil
    var manualFormatting: ManualFormatting? = nil
    var packSHA256: String { inputBinding.packSHA256 }
    var targetSHA256: String { inputBinding.targetSHA256 }
    enum CodingKeys: String, CodingKey {
        case summary, warnings
        case headingLevelCounts = "heading_level_counts"
        case headingDemotionCount = "heading_demotion_count"
        case tableAction = "table_action", pageLayoutAction = "page_layout_action"
        case fontNames = "font_names"
        case inputBinding = "input_binding"
        case runtimeInferredHeadingLevels = "runtime_inferred_heading_levels"
        case manualFormatting = "manual_formatting"
    }
    func matches(demoteHeadings: Bool, applyPageLayout: Bool) -> Bool {
        inputBinding.demoteHeadings == demoteHeadings &&
            inputBinding.preservePageLayout == !applyPageLayout &&
            Self.isSHA256(packSHA256) && Self.isSHA256(targetSHA256)
    }
    private static func isSHA256(_ value: String) -> Bool {
        value.count == 64 && value.utf8.allSatisfy { (48...57).contains($0) || (97...102).contains($0) }
    }
}

struct StyleEditRequest: Encodable {
    let styles: [StyleEditPayload]
}

struct StyleEditPayload: Encodable {
    let styleID: String
    let fontEastAsia: String?
    let fontLatin: String?
    let sizePt: Double?
    let bold: Bool?
    let colorHex: String?
    let alignment: String?
    let spaceBeforePt: Double?
    let spaceAfterPt: Double?
    let lineSpacing: Double?
    let lineRule: String?
    let leftIndentPt: Double?
    let rightIndentPt: Double?
    let firstLineIndentPt: Double?
    let hangingIndentPt: Double?
    let leftIndentChars: Double?
    let rightIndentChars: Double?
    let firstLineIndentChars: Double?
    let hangingIndentChars: Double?
    let tableFillHex: String?
    let tableAccentHex: String?
    var numberingFormat: String? = nil
    var numberingPattern: String? = nil
    var numberingStart: Int? = nil
    var numberingRestart: Bool? = nil
    var tableBorderStyle: String? = nil
    var tableBorderColorHex: String? = nil
    var tableBorderWidthPt: Double? = nil
    var tableCellMarginTopPt: Double? = nil
    var tableCellMarginBottomPt: Double? = nil
    var tableCellMarginLeftPt: Double? = nil
    var tableCellMarginRightPt: Double? = nil

    enum CodingKeys: String, CodingKey {
        case styleID = "style_id"
        case fontEastAsia = "font_east_asia"
        case fontLatin = "font_latin"
        case sizePt = "size_pt"
        case bold
        case colorHex = "color_hex"
        case alignment
        case spaceBeforePt = "space_before_pt"
        case spaceAfterPt = "space_after_pt"
        case lineSpacing = "line_spacing"
        case lineRule = "line_rule"
        case leftIndentPt = "left_indent_pt"
        case rightIndentPt = "right_indent_pt"
        case firstLineIndentPt = "first_line_indent_pt"
        case hangingIndentPt = "hanging_indent_pt"
        case leftIndentChars = "left_indent_chars"
        case rightIndentChars = "right_indent_chars"
        case firstLineIndentChars = "first_line_indent_chars"
        case hangingIndentChars = "hanging_indent_chars"
        case tableFillHex = "table_fill_hex"
        case tableAccentHex = "table_accent_hex"
        case numberingFormat = "numbering_format", numberingPattern = "numbering_pattern"
        case numberingStart = "numbering_start", numberingRestart = "numbering_restart"
        case tableBorderStyle = "table_border_style", tableBorderColorHex = "table_border_color_hex"
        case tableBorderWidthPt = "table_border_width_pt"
        case tableCellMarginTopPt = "table_cell_margin_top_pt"
        case tableCellMarginBottomPt = "table_cell_margin_bottom_pt"
        case tableCellMarginLeftPt = "table_cell_margin_left_pt"
        case tableCellMarginRightPt = "table_cell_margin_right_pt"
    }

    var changedFieldCount: Int {
        [
            fontEastAsia != nil,
            fontLatin != nil,
            sizePt != nil,
            bold != nil,
            colorHex != nil,
            alignment != nil,
            spaceBeforePt != nil,
            spaceAfterPt != nil,
            lineSpacing != nil,
            lineRule != nil,
            leftIndentPt != nil,
            rightIndentPt != nil,
            firstLineIndentPt != nil,
            hangingIndentPt != nil,
            leftIndentChars != nil,
            rightIndentChars != nil,
            firstLineIndentChars != nil,
            hangingIndentChars != nil,
            tableFillHex != nil,
            tableAccentHex != nil,
            numberingFormat != nil, numberingPattern != nil, numberingStart != nil,
            numberingRestart != nil, tableBorderStyle != nil, tableBorderColorHex != nil,
            tableBorderWidthPt != nil, tableCellMarginTopPt != nil, tableCellMarginBottomPt != nil,
            tableCellMarginLeftPt != nil, tableCellMarginRightPt != nil
        ].filter { $0 }.count
    }
}

struct TransferStats: Decodable, Hashable {
    let contentPartsCleaned: Int
    let paragraphsSeen: Int
    let runsSeen: Int
    let tablesSeen: Int
    let tableFormatsPreserved: Int
    let tableParagraphIndentsCleared: Int
    let tableParagraphStylesHardened: Int
    let bodyListParagraphsPreserved: Int
    let targetNumberingDefinitionsImported: Int
    let targetNumberingAbstractsImported: Int
    let targetPictureBulletsImported: Int
    let headingNumbersApplied: Int
    let headingIndentsApplied: Int
    let headingPrefixesRemoved: Int
    let headingLevelsDemoted: Int
    let headingLevel9Unchanged: Int
    let headingNumberingStart: Int?
    let sectionsUpdated: Int
    let paragraphPropertiesRemoved: Int
    let runPropertiesRemoved: Int
    let tablePropertiesRemoved: Int
    let stylesRemapped: Int
    let sourceFormatPartsCopied: Int
    let dependentPartsCopied: Int
    let settingsItemsImported: Int
    let warnings: [String]

    enum CodingKeys: String, CodingKey {
        case contentPartsCleaned = "content_parts_cleaned"
        case paragraphsSeen = "paragraphs_seen"
        case runsSeen = "runs_seen"
        case tablesSeen = "tables_seen"
        case tableFormatsPreserved = "table_formats_preserved"
        case tableParagraphIndentsCleared = "table_paragraph_indents_cleared"
        case tableParagraphStylesHardened = "table_paragraph_styles_hardened"
        case bodyListParagraphsPreserved = "body_list_paragraphs_preserved"
        case targetNumberingDefinitionsImported = "target_numbering_definitions_imported"
        case targetNumberingAbstractsImported = "target_numbering_abstracts_imported"
        case targetPictureBulletsImported = "target_picture_bullets_imported"
        case headingNumbersApplied = "heading_numbers_applied"
        case headingIndentsApplied = "heading_indents_applied"
        case headingPrefixesRemoved = "heading_prefixes_removed"
        case headingLevelsDemoted = "heading_levels_demoted"
        case headingLevel9Unchanged = "heading_level9_unchanged"
        case headingNumberingStart = "heading_numbering_start"
        case sectionsUpdated = "sections_updated"
        case paragraphPropertiesRemoved = "paragraph_properties_removed"
        case runPropertiesRemoved = "run_properties_removed"
        case tablePropertiesRemoved = "table_properties_removed"
        case stylesRemapped = "styles_remapped"
        case sourceFormatPartsCopied = "source_format_parts_copied"
        case dependentPartsCopied = "dependent_parts_copied"
        case settingsItemsImported = "settings_items_imported"
        case warnings
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        contentPartsCleaned = try values.decodeIfPresent(Int.self, forKey: .contentPartsCleaned) ?? 0
        paragraphsSeen = try values.decodeIfPresent(Int.self, forKey: .paragraphsSeen) ?? 0
        runsSeen = try values.decodeIfPresent(Int.self, forKey: .runsSeen) ?? 0
        tablesSeen = try values.decodeIfPresent(Int.self, forKey: .tablesSeen) ?? 0
        tableFormatsPreserved = try values.decodeIfPresent(Int.self, forKey: .tableFormatsPreserved) ?? 0
        tableParagraphIndentsCleared = try values.decodeIfPresent(Int.self, forKey: .tableParagraphIndentsCleared) ?? 0
        tableParagraphStylesHardened = try values.decodeIfPresent(Int.self, forKey: .tableParagraphStylesHardened) ?? 0
        bodyListParagraphsPreserved = try values.decodeIfPresent(Int.self, forKey: .bodyListParagraphsPreserved) ?? 0
        targetNumberingDefinitionsImported = try values.decodeIfPresent(Int.self, forKey: .targetNumberingDefinitionsImported) ?? 0
        targetNumberingAbstractsImported = try values.decodeIfPresent(Int.self, forKey: .targetNumberingAbstractsImported) ?? 0
        targetPictureBulletsImported = try values.decodeIfPresent(Int.self, forKey: .targetPictureBulletsImported) ?? 0
        headingNumbersApplied = try values.decodeIfPresent(Int.self, forKey: .headingNumbersApplied) ?? 0
        headingIndentsApplied = try values.decodeIfPresent(Int.self, forKey: .headingIndentsApplied) ?? 0
        headingPrefixesRemoved = try values.decodeIfPresent(Int.self, forKey: .headingPrefixesRemoved) ?? 0
        headingLevelsDemoted = try values.decodeIfPresent(Int.self, forKey: .headingLevelsDemoted) ?? 0
        headingLevel9Unchanged = try values.decodeIfPresent(Int.self, forKey: .headingLevel9Unchanged) ?? 0
        headingNumberingStart = try values.decodeIfPresent(Int.self, forKey: .headingNumberingStart)
        sectionsUpdated = try values.decodeIfPresent(Int.self, forKey: .sectionsUpdated) ?? 0
        paragraphPropertiesRemoved = try values.decodeIfPresent(Int.self, forKey: .paragraphPropertiesRemoved) ?? 0
        runPropertiesRemoved = try values.decodeIfPresent(Int.self, forKey: .runPropertiesRemoved) ?? 0
        tablePropertiesRemoved = try values.decodeIfPresent(Int.self, forKey: .tablePropertiesRemoved) ?? 0
        stylesRemapped = try values.decodeIfPresent(Int.self, forKey: .stylesRemapped) ?? 0
        sourceFormatPartsCopied = try values.decodeIfPresent(Int.self, forKey: .sourceFormatPartsCopied) ?? 0
        dependentPartsCopied = try values.decodeIfPresent(Int.self, forKey: .dependentPartsCopied) ?? 0
        settingsItemsImported = try values.decodeIfPresent(Int.self, forKey: .settingsItemsImported) ?? 0
        warnings = try values.decodeIfPresent([String].self, forKey: .warnings) ?? []
    }

    var directPropertiesRemoved: Int {
        paragraphPropertiesRemoved + runPropertiesRemoved + tablePropertiesRemoved
    }

    var uniqueWarnings: [String] {
        var seen = Set<String>()
        return warnings.compactMap { value in
            let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty, seen.insert(trimmed).inserted else { return nil }
            return trimmed
        }
    }
}

struct ApplyReport: Hashable {
    let outputURL: URL
    let targetFileName: String
    let formatName: String
    let appliedPageLayout: Bool
    let demotedHeadings: Bool
    let completedAt: Date
    let stats: TransferStats

    var plainText: String {
        let dateFormatter = DateFormatter()
        dateFormatter.locale = Locale(identifier: "zh_CN")
        dateFormatter.dateFormat = "yyyy-MM-dd HH:mm:ss"

        var lines = [
            "Forma 赋式处理报告",
            "处理时间：\(dateFormatter.string(from: completedAt))",
            "格式方案：\(formatName)",
            "目标文档：\(targetFileName)",
            "输出文档：\(outputURL.path)",
            "页面设置：\(appliedPageLayout ? "已同步格式源" : "保留目标文档")",
            "标题层级：\(demotedHeadings ? "所有标题下调一级" : "保持原层级")",
            "",
            "处理统计",
            "- 段落：\(stats.paragraphsSeen)",
            "- 文字片段：\(stats.runsSeen)",
            "- 表格：\(stats.tablesSeen)",
            "- 样式重映射：\(stats.stylesRemapped)",
            "- 清除旧的直接格式属性：\(stats.directPropertiesRemoved)",
            "- 应用标题编号：\(stats.headingNumbersApplied)",
            "- 保留正文编号与项目列表：\(stats.bodyListParagraphsPreserved) 段",
            "- 清理重复手工标题序号：\(stats.headingPrefixesRemoved)",
            "- 清理表格单元格两字符缩进：\(stats.tableParagraphIndentsCleared)",
            "- 保留目标表格外观：\(stats.tableFormatsPreserved)",
            "- 更新页面节：\(stats.sectionsUpdated)"
        ]
        let warnings = stats.uniqueWarnings
        if !warnings.isEmpty {
            lines.append("")
            lines.append("需要留意")
            lines.append(contentsOf: warnings.map { "- \($0)" })
        }
        return lines.joined(separator: "\n")
    }
}

struct LibraryReadError: Decodable, Identifiable {
    let path: String
    let error: String
    var id: String { path }
}

struct ManagerOutput {
    let data: Data
    let standardError: String
    let status: Int32
}

enum AppFailure: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let message): return message
        }
    }
}

enum PackDeletionPolicy {
    static func validatedURL(
        for pack: PackManifest,
        currentPacks: [PackManifest],
        libraryDirectory: URL
    ) throws -> URL {
        guard currentPacks.contains(where: {
            $0.id == pack.id && $0.packPath == pack.packPath
        }) else {
            throw AppFailure.message("这套格式已不在当前格式库中，请刷新后重试。")
        }
        guard let rawPackURL = pack.packURL, rawPackURL.isFileURL else {
            throw AppFailure.message("这套格式缺少本机存储位置，无法删除。")
        }

        let directLibraryURL = libraryDirectory.standardizedFileURL
        let directPackURL = rawPackURL.standardizedFileURL
        guard directPackURL.pathExtension.lowercased() == "wfstyle",
              directPackURL.deletingLastPathComponent().path == directLibraryURL.path else {
            throw AppFailure.message("为保护其他文件，只能删除格式库目录中的 .wfstyle 格式方案。")
        }

        let resolvedLibraryURL = directLibraryURL.resolvingSymlinksInPath()
        let resolvedPackURL = directPackURL.resolvingSymlinksInPath()
        guard resolvedPackURL.deletingLastPathComponent().path == resolvedLibraryURL.path else {
            throw AppFailure.message("检测到格式方案指向格式库以外的位置，已停止删除。")
        }

        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(
            atPath: directPackURL.path,
            isDirectory: &isDirectory
        ), !isDirectory.boolValue else {
            throw AppFailure.message("这套格式文件已经不存在，请刷新格式库。")
        }
        let values = try directPackURL.resourceValues(forKeys: [
            .isRegularFileKey,
            .isSymbolicLinkKey
        ])
        guard values.isRegularFile == true, values.isSymbolicLink != true else {
            throw AppFailure.message("为保护其他内容，只能删除普通的 .wfstyle 格式库文件。")
        }
        return directPackURL
    }

    static func fallbackIndex(afterDeleting deletedIndex: Int, remainingCount: Int) -> Int? {
        guard remainingCount > 0 else { return nil }
        return min(max(deletedIndex, 0), remainingCount - 1)
    }
}
