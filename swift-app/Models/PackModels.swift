import Foundation

// MARK: - style_pack_manager.py 返回的数据

struct UsedFormat: Codable, Hashable, Identifiable {
    let styleID: String
    let name: String
    let type: String
    let usageCount: Int
    let inferred: Bool?
    let inferenceLabel: String?
    let sample: String
    let fontLatin: String?
    let fontEastAsia: String?
    let sizePt: Double?
    let bold: Bool?
    let italic: Bool?
    let colorHex: String?
    let alignment: String?
    let spaceBeforePt: Double?
    let spaceAfterPt: Double?
    let lineSpacing: Double?
    let lineRule: String?
    let outlineLevel: Int?
    let numbered: Bool
    let numberingLevel: Int?
    let numberingFormat: String?
    let numberingPattern: String?
    let numberingExample: String?
    let tableFillHex: String?
    let tableAccentHex: String?

    var id: String { "\(type):\(styleID)" }

    enum CodingKeys: String, CodingKey {
        case styleID = "style_id"
        case name, type
        case usageCount = "usage_count"
        case inferred
        case inferenceLabel = "inference_label"
        case sample
        case fontLatin = "font_latin"
        case fontEastAsia = "font_east_asia"
        case sizePt = "size_pt"
        case bold, italic
        case colorHex = "color_hex"
        case alignment
        case spaceBeforePt = "space_before_pt"
        case spaceAfterPt = "space_after_pt"
        case lineSpacing = "line_spacing"
        case lineRule = "line_rule"
        case outlineLevel = "outline_level"
        case numbered
        case numberingLevel = "numbering_level"
        case numberingFormat = "numbering_format"
        case numberingPattern = "numbering_pattern"
        case numberingExample = "numbering_example"
        case tableFillHex = "table_fill_hex"
        case tableAccentHex = "table_accent_hex"
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
    let sourceSHA256: String?
    let createdAt: String?
    let usedFormats: [UsedFormat]
    let usedStyleCount: Int
    let inferredStyleCount: Int?
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
        case sourceSHA256 = "source_sha256"
        case createdAt = "created_at"
        case usedFormats = "used_formats"
        case usedStyleCount = "used_style_count"
        case inferredStyleCount = "inferred_style_count"
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

    var libraryIdentity: String {
        packPath ?? id
    }

    var inferredCount: Int { inferredStyleCount ?? 0 }

    var hiddenCount: Int {
        hiddenStyleCount ?? max(0, (definedStyleCount ?? usedStyleCount) - usedStyleCount)
    }

    var createdDisplay: String {
        guard let createdAt,
              let date = ISO8601DateFormatter().date(from: createdAt) else {
            return UIStrings.Sidebar.packDateUnknown
        }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_CN")
        formatter.dateFormat = "yyyy/MM/dd"
        return formatter.string(from: date)
    }

    var hasNumberedHeadings: Bool {
        usedFormats.contains { $0.type == "paragraph" && $0.outlineLevel != nil && $0.numbered }
    }

    var hasTableStyles: Bool {
        usedFormats.contains { $0.type == "table" }
    }
}

// MARK: - 进程间信封

struct TransferStats: Decodable {
    let warnings: [String]?
}

struct ManagerEnvelope: Decodable {
    let ok: Bool
    let error: String?
    let pack: PackManifest?
    let packs: [PackManifest]?
    let output: String?
    let errors: [LibraryReadError]?
    let stats: TransferStats?
}

struct LibraryReadError: Decodable {
    let path: String
    let error: String
}

enum AppFailure: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let message): return message
        }
    }
}

// MARK: - 删除策略

enum PackDeletionPolicy {
    static func validatedURL(
        for pack: PackManifest,
        currentPacks: [PackManifest],
        libraryDirectory: URL
    ) throws -> URL {
        guard currentPacks.contains(where: {
            $0.id == pack.id && $0.packPath == pack.packPath
        }) else {
            throw AppFailure.message(UIStrings.Errors.packNotInLibrary)
        }
        guard let rawPackURL = pack.packURL, rawPackURL.isFileURL else {
            throw AppFailure.message(UIStrings.Errors.packWithoutPath)
        }

        let directLibraryURL = libraryDirectory.standardizedFileURL
        let directPackURL = rawPackURL.standardizedFileURL
        guard directPackURL.pathExtension.lowercased() == "wfstyle",
              directPackURL.deletingLastPathComponent().path == directLibraryURL.path else {
            throw AppFailure.message(UIStrings.Errors.packOutsideLibrary)
        }

        let resolvedLibraryURL = directLibraryURL.resolvingSymlinksInPath()
        let resolvedPackURL = directPackURL.resolvingSymlinksInPath()
        guard resolvedPackURL.deletingLastPathComponent().path == resolvedLibraryURL.path else {
            throw AppFailure.message(UIStrings.Errors.packEscapesLibrary)
        }

        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(
            atPath: directPackURL.path,
            isDirectory: &isDirectory
        ), !isDirectory.boolValue else {
            throw AppFailure.message(UIStrings.Errors.packMissingFile)
        }
        let values = try directPackURL.resourceValues(forKeys: [
            .isRegularFileKey,
            .isSymbolicLinkKey
        ])
        guard values.isRegularFile == true, values.isSymbolicLink != true else {
            throw AppFailure.message(UIStrings.Errors.packNotRegularFile)
        }
        return directPackURL
    }

    static func fallbackIndex(afterDeleting deletedIndex: Int, remainingCount: Int) -> Int? {
        guard remainingCount > 0 else { return nil }
        return min(max(deletedIndex, 0), remainingCount - 1)
    }
}

// MARK: - 筛选器

enum FormatFilter: CaseIterable, Identifiable {
    case all
    case headings
    case paragraphs
    case characters
    case tables

    var id: String { title }

    var title: String {
        switch self {
        case .all: return UIStrings.Filters.all
        case .headings: return UIStrings.Filters.headings
        case .paragraphs: return UIStrings.Filters.paragraphs
        case .characters: return UIStrings.Filters.characters
        case .tables: return UIStrings.Filters.tables
        }
    }

    func includes(_ format: UsedFormat) -> Bool {
        switch self {
        case .all: return true
        case .headings: return format.type == "paragraph" && format.outlineLevel != nil
        case .paragraphs: return format.type == "paragraph" && format.outlineLevel == nil
        case .characters: return format.type == "character"
        case .tables: return format.type == "table"
        }
    }
}
