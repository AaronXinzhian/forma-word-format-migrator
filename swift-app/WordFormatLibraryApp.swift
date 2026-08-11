import AppKit
import Darwin
import SwiftUI
import UniformTypeIdentifiers

// MARK: - Data returned by style_pack_manager.py

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

    var libraryIdentity: String {
        packPath ?? id
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

private struct ManagerEnvelope: Decodable {
    let ok: Bool
    let error: String?
    let pack: PackManifest?
    let packs: [PackManifest]?
    let output: String?
    let errors: [LibraryReadError]?
    let stats: TransferStats?
}

private struct StyleEditRequest: Encodable {
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
            tableAccentHex != nil
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

private struct LibraryReadError: Decodable {
    let path: String
    let error: String
}

private struct ManagerOutput {
    let data: Data
    let standardError: String
    let status: Int32
}

private enum AppFailure: LocalizedError {
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

// MARK: - Python bridge

private final class PythonOperation: @unchecked Sendable {
    private let lock = NSLock()
    private var process: Process?
    private var cancelled = false

    var isCancelled: Bool {
        lock.lock()
        defer { lock.unlock() }
        return cancelled
    }

    func attach(_ process: Process) {
        lock.lock()
        self.process = process
        let shouldStop = cancelled
        lock.unlock()
        if shouldStop {
            Self.stop(process)
        }
    }

    func detach(_ process: Process) {
        lock.lock()
        if self.process === process {
            self.process = nil
        }
        lock.unlock()
    }

    func cancel() {
        lock.lock()
        cancelled = true
        let processToStop = process
        lock.unlock()
        if let processToStop {
            Self.stop(processToStop)
        }
    }

    private static func stop(_ process: Process) {
        guard process.isRunning else { return }
        process.terminate()
        let processIdentifier = process.processIdentifier
        DispatchQueue.global(qos: .userInitiated).asyncAfter(deadline: .now() + 1) {
            guard process.isRunning else { return }
            Darwin.kill(processIdentifier, SIGKILL)
        }
    }
}

private enum PythonBridge {
    static let bundledRuntimeRelativePath = "runtime/bin/python3"

    static func run(
        arguments: [String],
        operation: PythonOperation
    ) async throws -> ManagerOutput {
        guard let scriptURL = managerScriptURL() else {
            throw AppFailure.message("应用资源不完整：找不到 style_pack_manager.py。请重新安装应用。")
        }

        let process = Process()
        if let bundledPython = bundledPythonURL() {
            process.executableURL = bundledPython
            process.arguments = ["-B", "-E", "-s", "-X", "utf8", scriptURL.path] + arguments
            process.environment = isolatedEnvironment(for: bundledPython)
        } else if isRunningFromApplicationBundle {
            throw AppFailure.message(
                "应用资源不完整：找不到内置文档处理环境。请重新安装 Forma 赋式。"
            )
        } else if FileManager.default.isExecutableFile(atPath: "/usr/bin/python3") {
            // Development-only fallback. A distributed .app must always use
            // Contents/Resources/runtime/bin/python3.
            process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            process.arguments = ["-B", "-E", "-X", "utf8", scriptURL.path] + arguments
            process.environment = developmentEnvironment()
        } else {
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = ["python3", "-B", "-E", "-X", "utf8", scriptURL.path] + arguments
            process.environment = developmentEnvironment()
        }
        process.currentDirectoryURL = scriptURL.deletingLastPathComponent()

        let standardOutput = Pipe()
        let standardError = Pipe()
        process.standardOutput = standardOutput
        process.standardError = standardError

        do {
            try process.run()
        } catch {
            throw AppFailure.message("无法启动文档处理组件：\(error.localizedDescription)")
        }
        operation.attach(process)
        defer { operation.detach(process) }

        return try await withTaskCancellationHandler {
            let outputTask = Task.detached {
                standardOutput.fileHandleForReading.readDataToEndOfFile()
            }
            let errorTask = Task.detached {
                standardError.fileHandleForReading.readDataToEndOfFile()
            }
            let statusTask = Task.detached { () -> Int32 in
                process.waitUntilExit()
                return process.terminationStatus
            }

            let data = await outputTask.value
            let errorData = await errorTask.value
            let status = await statusTask.value
            // A cancel request can arrive after the helper has already
            // committed its atomic output and exited successfully.  In that
            // narrow window the successful protocol result is authoritative;
            // reporting a cancellation would leave a valid but hidden pack
            // or document behind.  Non-zero exits still resolve as cancelled.
            if (operation.isCancelled || Task.isCancelled) && status != 0 {
                throw CancellationError()
            }
            let errorText = String(data: errorData, encoding: .utf8) ?? ""
            return ManagerOutput(data: data, standardError: errorText, status: status)
        } onCancel: {
            operation.cancel()
        }
    }

    private static var isRunningFromApplicationBundle: Bool {
        Bundle.main.bundleURL.pathExtension.lowercased() == "app"
    }

    private static func bundledPythonURL() -> URL? {
        guard let resources = Bundle.main.resourceURL else { return nil }
        let url = resources.appendingPathComponent(bundledRuntimeRelativePath)
        return FileManager.default.isExecutableFile(atPath: url.path) ? url : nil
    }

    private static func isolatedEnvironment(for pythonURL: URL) -> [String: String] {
        var environment = [
            "PATH": pythonURL.deletingLastPathComponent().path + ":/usr/bin:/bin",
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1"
        ]
        if let temporaryDirectory = ProcessInfo.processInfo.environment["TMPDIR"] {
            environment["TMPDIR"] = temporaryDirectory
        }
        return environment
    }

    private static func developmentEnvironment() -> [String: String] {
        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUTF8"] = "1"
        environment["PYTHONUNBUFFERED"] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return environment
    }

    private static func managerScriptURL() -> URL? {
        let fileManager = FileManager.default
        var candidates: [URL] = []

        if let bundled = Bundle.main.url(forResource: "style_pack_manager", withExtension: "py") {
            candidates.append(bundled)
        }
        if let resources = Bundle.main.resourceURL {
            candidates.append(resources.appendingPathComponent("style_pack_manager.py"))
        }

        // Test/debug builds may locate the adjacent helper from the source
        // tree. Release binaries deliberately omit #filePath so a developer's
        // local workspace path is never embedded in a distributed executable.
#if DEBUG || WORD_FORMAT_LIBRARY_TESTING
        let sourceFile = URL(fileURLWithPath: #filePath)
        candidates.append(
            sourceFile.deletingLastPathComponent()
                .deletingLastPathComponent()
                .appendingPathComponent("style_pack_manager.py")
        )
#endif
        candidates.append(
            URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
                .appendingPathComponent("style_pack_manager.py")
        )

        return candidates.first { fileManager.fileExists(atPath: $0.path) }
    }
}

// MARK: - Application state

@MainActor
final class WordFormatLibraryModel: ObservableObject {
    @Published var packs: [PackManifest] = []
    @Published var selectedPack: PackManifest?
    @Published var selectedFormatID: String?
    @Published var currentStep = 1
    @Published var targetURL: URL?
    @Published var outputURL: URL?
    @Published var applyReport: ApplyReport?
    @Published var applySourcePageLayout = true
    @Published var demoteHeadings = false
    @Published var isBusy = false
    @Published var busyMessage = ""
    @Published private(set) var canCancelBusyOperation = false
    @Published private(set) var isCancelling = false
    @Published var errorMessage = ""
    @Published var isShowingError = false
    @Published var libraryNotice: String?
    @Published var libraryConfirmation: String?
    @Published var operationNotice: String?

    let libraryDirectory: URL
    private var activePythonOperation: PythonOperation?
    private var phaseMessageTask: Task<Void, Never>?

    init() {
        let environmentPath = ProcessInfo.processInfo.environment["WORD_FORMAT_LIBRARY_DIR"]?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if let environmentPath, !environmentPath.isEmpty {
            libraryDirectory = URL(fileURLWithPath: environmentPath, isDirectory: true)
        } else {
            let applicationSupport = FileManager.default.urls(
                for: .applicationSupportDirectory,
                in: .userDomainMask
            ).first!
            libraryDirectory = applicationSupport
                .appendingPathComponent("WordFormatMigrator", isDirectory: true)
                .appendingPathComponent("style-packs", isDirectory: true)
        }

        Task { [weak self] in await self?.reloadLibrary() }
    }

    var selectedFormat: UsedFormat? {
        guard let selectedFormatID else { return selectedPack?.usedFormats.first }
        return selectedPack?.usedFormats.first { $0.id == selectedFormatID }
    }

    func reloadLibrary(selecting preferredID: String? = nil, showProgress: Bool = true) async {
        // Internal refreshes run with showProgress=false while their owning
        // operation keeps the busy overlay.  User-triggered refreshes must not
        // start a second process or clear another operation's UI state.
        guard !showProgress || !isBusy else { return }
        let hadSelection = selectedPack != nil || preferredID != nil
        if showProgress {
            beginBusy("正在读取本机格式库…")
            libraryConfirmation = nil
        }
        defer {
            if showProgress {
                finishBusy()
            }
        }

        do {
            try ensureLibraryDirectory()
            let envelope = try await execute([
                "list-library", "--dir", libraryDirectory.path
            ])
            packs = envelope.packs ?? []
            if let errors = envelope.errors, !errors.isEmpty {
                libraryNotice = "有 \(errors.count) 个格式库文件无法读取，已自动跳过。"
            } else {
                libraryNotice = nil
            }

            if let preferredID,
               let match = packs.first(where: { $0.id == preferredID }) {
                refreshSelection(with: match)
            } else if let selectedPath = selectedPack?.packPath,
                      let match = packs.first(where: { $0.packPath == selectedPath }) {
                refreshSelection(with: match)
            } else if selectedPack?.packPath == nil,
                      let selectedID = selectedPack?.id,
                      let match = packs.first(where: { $0.id == selectedID }) {
                refreshSelection(with: match)
            } else if packs.isEmpty || hadSelection {
                clearSelection()
            }
        } catch {
            show(error)
        }
    }

    func importSource(_ sourceURL: URL) async {
        guard !isBusy else { return }
        guard Self.isSupportedSource(sourceURL) else {
            show(AppFailure.message("请选择 .docx、.docm、.dotx 或 .dotm 格式的 Word 文件。"))
            return
        }

        beginBusy(
            "正在读取 Word 文档的格式结构…",
            followUps: [
                (900_000_000, "正在识别文档中实际使用的格式…"),
                (2_000_000_000, "正在整理标题、编号、表格与页面设置…"),
                (3_000_000_000, "文档较大，正在完成格式方案校验…")
            ]
        )
        defer { finishBusy() }

        do {
            try ensureLibraryDirectory()
            let packURL = libraryDirectory.appendingPathComponent(
                "\(UUID().uuidString.lowercased()).wfstyle"
            )
            let envelope = try await execute([
                "create-pack",
                "--source", sourceURL.path,
                "--out", packURL.path
            ])
            guard let pack = envelope.pack else {
                throw AppFailure.message("格式已读取，但没有返回可展示的信息。")
            }
            await reloadLibrary(selecting: pack.id, showProgress: false)
            if let reloaded = packs.first(where: { $0.id == pack.id }) {
                selectPack(reloaded)
            } else {
                packs.insert(pack, at: 0)
                selectPack(pack)
            }
        } catch {
            show(error)
        }
    }

    fileprivate func derivePack(
        from sourcePack: PackManifest,
        named requestedName: String,
        request: StyleEditRequest
    ) async throws -> PackManifest {
        guard !isBusy else {
            throw AppFailure.message("另一项文档处理仍在进行，请稍候。")
        }
        guard !request.styles.isEmpty else {
            throw AppFailure.message("请至少修改一个格式属性后再保存。")
        }
        guard request.styles.allSatisfy({ $0.changedFieldCount > 0 }) else {
            throw AppFailure.message("格式编辑请求中包含没有实际变化的项目，请重置后重试。")
        }
        guard packs.contains(where: {
            $0.id == sourcePack.id && $0.packPath == sourcePack.packPath
        }) else {
            throw AppFailure.message("原格式方案已不在当前格式库中，请返回刷新后重试。")
        }
        guard let sourceURL = sourcePack.packURL else {
            throw AppFailure.message("原格式方案缺少本机存储位置，无法创建调整版。")
        }

        let name = requestedName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty else {
            throw AppFailure.message("请为调整后的格式方案填写名称。")
        }
        guard name.count <= 120 else {
            throw AppFailure.message("格式方案名称最多允许 120 个字符。")
        }

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        let encodedRequest: Data
        do {
            encodedRequest = try encoder.encode(request)
        } catch {
            throw AppFailure.message("无法整理格式修改内容：\(error.localizedDescription)")
        }
        guard let editsJSON = String(data: encodedRequest, encoding: .utf8) else {
            throw AppFailure.message("无法生成格式修改请求，请重试。")
        }

        try ensureLibraryDirectory()
        // Derived packs always use an opaque filename and never reuse the
        // source path. The Python layer independently enforces the same rule.
        let destination = libraryDirectory.appendingPathComponent(
            "\(UUID().uuidString.lowercased()).wfstyle"
        )

        beginBusy(
            "正在创建调整后的格式方案…",
            followUps: [
                (900_000_000, "正在更新字体、颜色与样式预览…"),
                (2_000_000_000, "正在校验新格式方案的完整性…")
            ]
        )
        defer { finishBusy() }

        var arguments = [
            "derive-pack",
            "--pack", sourceURL.path,
            "--out", destination.path,
            "--edits-json", editsJSON
        ]
        // The untouched default name remains explicitly source-derived.  Only
        // a name the user actually changes is declared independent from the
        // original document name in the pack's privacy metadata.
        if name != "\(sourcePack.name) · 自定义" {
            arguments += ["--name", name]
        }
        let envelope = try await execute(arguments)
        guard let derived = envelope.pack else {
            throw AppFailure.message("调整已完成，但没有收到新格式方案的信息。")
        }

        await reloadLibrary(selecting: derived.id, showProgress: false)
        if let reloaded = packs.first(where: { $0.id == derived.id }) {
            selectPack(reloaded, advance: false)
        } else {
            packs.insert(derived, at: 0)
            selectPack(derived, advance: false)
        }
        currentStep = 2
        operationNotice = "已创建「\(name)」并自动选中；原格式方案保持不变。"
        return selectedPack ?? derived
    }

    func deletePack(_ pack: PackManifest) async {
        guard !isBusy else { return }

        let deletedIndex = packs.firstIndex(where: {
            $0.id == pack.id && $0.packPath == pack.packPath
        }) ?? 0
        let wasSelected = selectedPack.map {
            $0.id == pack.id && $0.packPath == pack.packPath
        } ?? false

        beginBusy("正在将「\(pack.name)」移到废纸篓…")
        libraryConfirmation = nil
        defer { finishBusy() }

        do {
            let packURL = try PackDeletionPolicy.validatedURL(
                for: pack,
                currentPacks: packs,
                libraryDirectory: libraryDirectory
            )
            var trashedURL: NSURL?
            try FileManager.default.trashItem(at: packURL, resultingItemURL: &trashedURL)

            packs.removeAll(where: {
                $0.id == pack.id && $0.packPath == pack.packPath
            })
            if wasSelected {
                clearSelection()
                if let nextIndex = PackDeletionPolicy.fallbackIndex(
                    afterDeleting: deletedIndex,
                    remainingCount: packs.count
                ) {
                    selectPack(packs[nextIndex], advance: false)
                    currentStep = 1
                }
            }
            await reloadLibrary(showProgress: false)
            libraryConfirmation = "已将「\(pack.name)」移到废纸篓，需要时可以恢复。"
        } catch {
            show(error)
        }
    }

    func selectPack(_ pack: PackManifest, advance: Bool = true) {
        selectedPack = pack
        selectedFormatID = pack.usedFormats.first?.id
        targetURL = nil
        outputURL = nil
        applyReport = nil
        demoteHeadings = false
        if advance { currentStep = 2 }
    }

    private func refreshSelection(with pack: PackManifest) {
        let previousFormatID = selectedFormatID
        selectedPack = pack
        if let previousFormatID,
           pack.usedFormats.contains(where: { $0.id == previousFormatID }) {
            selectedFormatID = previousFormatID
        } else {
            selectedFormatID = pack.usedFormats.first?.id
        }
    }

    private func clearSelection() {
        selectedPack = nil
        selectedFormatID = nil
        targetURL = nil
        outputURL = nil
        applyReport = nil
        demoteHeadings = false
        currentStep = 1
    }

    func beginTargetStep() {
        guard selectedPack != nil else { return }
        currentStep = 3
    }

    func chooseTarget(_ url: URL) {
        guard !isBusy else { return }
        guard Self.isSupportedTarget(url) else {
            show(AppFailure.message("目标文件只支持 .docx 或 .docm。"))
            return
        }
        targetURL = url
        outputURL = nil
        applyReport = nil
        demoteHeadings = false
    }

    func applyPack(savingTo destination: URL) async {
        guard !isBusy else { return }
        guard let selectedPack,
              let packURL = selectedPack.packURL,
              let targetURL else {
            show(AppFailure.message("请先选择格式库和要修改的 Word 文件。"))
            return
        }
        guard destination.pathExtension.lowercased() == targetURL.pathExtension.lowercased() else {
            show(AppFailure.message("输出文件必须与目标文件保持相同扩展名。"))
            return
        }
        guard destination.standardizedFileURL != targetURL.standardizedFileURL else {
            show(AppFailure.message("为保护原文件，请另存为一个新文件。"))
            return
        }

        let shouldApplyPageLayout = applySourcePageLayout
        let shouldDemoteHeadings = demoteHeadings
        beginBusy(
            "正在验证格式方案与目标文档…",
            followUps: [
                (800_000_000, "正在清理旧格式并匹配段落样式…"),
                (2_200_000_000, "正在处理标题、编号与表格格式…"),
                (3_500_000_000, "正在写入并校验新文档，请稍候…")
            ]
        )
        defer { finishBusy() }

        do {
            var arguments = [
                "apply-pack",
                "--pack", packURL.path,
                "--target", targetURL.path,
                "--out", destination.path,
                "--force"
            ]
            if !shouldApplyPageLayout {
                arguments.append("--preserve-page-layout")
            }
            if shouldDemoteHeadings {
                arguments.append("--demote-headings")
            }
            let envelope = try await execute(arguments)
            busyMessage = "正在确认输出文件并整理处理报告…"
            guard let stats = envelope.stats else {
                throw AppFailure.message("文档已处理，但没有收到可验证的处理统计。请重新生成。")
            }
            let resolvedOutput = envelope.output.map { URL(fileURLWithPath: $0) } ?? destination
            var isDirectory: ObjCBool = false
            guard FileManager.default.fileExists(
                atPath: resolvedOutput.path,
                isDirectory: &isDirectory
            ), !isDirectory.boolValue else {
                throw AppFailure.message("文档处理组件未生成预期的输出文件。")
            }
            let report = ApplyReport(
                outputURL: resolvedOutput,
                targetFileName: targetURL.lastPathComponent,
                formatName: selectedPack.name,
                appliedPageLayout: shouldApplyPageLayout,
                demotedHeadings: shouldDemoteHeadings,
                completedAt: Date(),
                stats: stats
            )
            outputURL = resolvedOutput
            applyReport = report
            operationNotice = nil
        } catch {
            show(error)
        }
    }

    func show(_ error: Error) {
        if error is CancellationError {
            operationNotice = "处理已取消；Forma 赋式不会覆盖原文件。"
            return
        }
        errorMessage = error.localizedDescription
        isShowingError = true
    }

    func cancelCurrentOperation() {
        guard let activePythonOperation, !isCancelling else { return }
        isCancelling = true
        canCancelBusyOperation = false
        phaseMessageTask?.cancel()
        busyMessage = "正在安全停止处理…"
        activePythonOperation.cancel()
    }

    func stopBackgroundWork() {
        phaseMessageTask?.cancel()
        activePythonOperation?.cancel()
    }

    private func execute(_ arguments: [String]) async throws -> ManagerEnvelope {
        guard activePythonOperation == nil else {
            throw AppFailure.message("另一项文档处理仍在进行，请稍候。")
        }
        let operation = PythonOperation()
        activePythonOperation = operation
        canCancelBusyOperation = true
        isCancelling = false
        defer {
            if activePythonOperation === operation {
                activePythonOperation = nil
                canCancelBusyOperation = false
                isCancelling = false
            }
        }

        let result = try await PythonBridge.run(arguments: arguments, operation: operation)
        guard !result.data.isEmpty else {
            let detail = result.standardError.trimmingCharacters(in: .whitespacesAndNewlines)
            throw AppFailure.message(
                detail.isEmpty ? "文档处理组件没有返回结果。" : "文档处理失败：\(detail)"
            )
        }

        let envelope: ManagerEnvelope
        do {
            envelope = try JSONDecoder().decode(ManagerEnvelope.self, from: result.data)
        } catch {
            let detail = result.standardError.trimmingCharacters(in: .whitespacesAndNewlines)
            throw AppFailure.message(
                detail.isEmpty
                    ? "无法读取文档处理结果。"
                    : "无法读取文档处理结果：\(detail)"
            )
        }
        guard envelope.ok else {
            throw AppFailure.message(envelope.error ?? "文档处理失败。")
        }
        if result.status != 0 {
            throw AppFailure.message(envelope.error ?? "文档处理组件异常退出。")
        }
        return envelope
    }

    private func beginBusy(
        _ message: String,
        followUps: [(UInt64, String)] = []
    ) {
        phaseMessageTask?.cancel()
        operationNotice = nil
        isBusy = true
        busyMessage = message
        canCancelBusyOperation = false
        isCancelling = false
        guard !followUps.isEmpty else { return }
        phaseMessageTask = Task { [weak self] in
            for (delay, nextMessage) in followUps {
                do {
                    try await Task.sleep(nanoseconds: delay)
                } catch {
                    return
                }
                guard let self, self.isBusy, !self.isCancelling else { return }
                self.busyMessage = nextMessage
            }
        }
    }

    private func finishBusy() {
        phaseMessageTask?.cancel()
        phaseMessageTask = nil
        isBusy = false
        busyMessage = ""
        canCancelBusyOperation = false
        isCancelling = false
    }

    private func ensureLibraryDirectory() throws {
        try FileManager.default.createDirectory(
            at: libraryDirectory,
            withIntermediateDirectories: true
        )
        try FileManager.default.setAttributes(
            [.posixPermissions: NSNumber(value: Int16(0o700))],
            ofItemAtPath: libraryDirectory.path
        )
    }

    private static func isSupportedSource(_ url: URL) -> Bool {
        ["docx", "docm", "dotx", "dotm"].contains(url.pathExtension.lowercased())
    }

    private static func isSupportedTarget(_ url: URL) -> Bool {
        ["docx", "docm"].contains(url.pathExtension.lowercased())
    }

}

// MARK: - Visual language

private enum Palette {
    static let ink = Color(hex: "19332F")
    static let mutedInk = Color(hex: "687873")
    static let green = Color(hex: "27685D")
    static let greenDeep = Color(hex: "184D45")
    static let mint = Color(hex: "DDEBE5")
    static let paper = Color(hex: "F5F2EA")
    static let card = Color.white.opacity(0.94)
    static let line = Color(hex: "D8DED9")
    static let amber = Color(hex: "B96B2C")
    static let amberWash = Color(hex: "FFF0DB")
    static let success = Color(hex: "2B735C")
}

private extension Color {
    init(hex: String) {
        let cleaned = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var value: UInt64 = 0
        Scanner(string: cleaned).scanHexInt64(&value)
        let red, green, blue, alpha: UInt64
        switch cleaned.count {
        case 8:
            red = (value >> 24) & 0xFF
            green = (value >> 16) & 0xFF
            blue = (value >> 8) & 0xFF
            alpha = value & 0xFF
        default:
            red = (value >> 16) & 0xFF
            green = (value >> 8) & 0xFF
            blue = value & 0xFF
            alpha = 255
        }
        self.init(
            .sRGB,
            red: Double(red) / 255,
            green: Double(green) / 255,
            blue: Double(blue) / 255,
            opacity: Double(alpha) / 255
        )
    }
}

private struct AppCard<Content: View>: View {
    var padding: CGFloat = 20
    @ViewBuilder let content: Content

    var body: some View {
        content
            .padding(padding)
            .background(Palette.card)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(Palette.line.opacity(0.8), lineWidth: 1)
            }
            .shadow(color: Palette.ink.opacity(0.045), radius: 14, y: 6)
    }
}

private struct PrimaryButtonStyle: ButtonStyle {
    var compact = false

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: compact ? 13 : 14, weight: .semibold))
            .foregroundStyle(.white)
            .padding(.horizontal, compact ? 14 : 19)
            .frame(height: compact ? 34 : 42)
            .background(configuration.isPressed ? Palette.greenDeep : Palette.green)
            .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
            .opacity(configuration.isPressed ? 0.88 : 1)
    }
}

private struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(Palette.ink)
            .padding(.horizontal, 14)
            .frame(height: 36)
            .background(configuration.isPressed ? Palette.mint : Color.white.opacity(0.72))
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .stroke(Palette.line, lineWidth: 1)
            }
    }
}

// MARK: - Main window

struct WordFormatLibraryView: View {
    @StateObject private var model = WordFormatLibraryModel()

    var body: some View {
        ZStack {
            Palette.paper.ignoresSafeArea()
            VStack(spacing: 0) {
                AppHeader(model: model)
                StepStrip(model: model)
                Divider().overlay(Palette.line)
                Group {
                    switch model.currentStep {
                    case 1: ImportStepView(model: model)
                    case 2: FormatPreviewStepView(model: model)
                    default: ApplyStepView(model: model)
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }

            if let notice = model.operationNotice, !model.isBusy {
                VStack {
                    Spacer()
                    OperationNoticeBanner(message: notice) {
                        model.operationNotice = nil
                    }
                    .padding(.horizontal, 28)
                    .padding(.bottom, 22)
                }
                .transition(.move(edge: .bottom).combined(with: .opacity))
            }

            if model.isBusy {
                BusyOverlay(
                    message: model.busyMessage,
                    canCancel: model.canCancelBusyOperation,
                    isCancelling: model.isCancelling,
                    cancel: model.cancelCurrentOperation
                )
            }
        }
        .animation(.easeInOut(duration: 0.2), value: model.operationNotice)
        .frame(minWidth: 1080, minHeight: 720)
        .foregroundStyle(Palette.ink)
        .alert("操作没有完成", isPresented: $model.isShowingError) {
            Button("好") { model.isShowingError = false }
        } message: {
            Text(model.errorMessage)
        }
        .onDisappear {
            model.stopBackgroundWork()
        }
    }
}

private struct AppHeader: View {
    @ObservedObject var model: WordFormatLibraryModel

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(Palette.green)
                Image(systemName: "textformat.alt")
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundStyle(.white)
            }
            .frame(width: 42, height: 42)

            VStack(alignment: .leading, spacing: 2) {
                Text("Forma 赋式")
                    .font(.system(size: 19, weight: .bold, design: .rounded))
                Text("一份范本，万卷同式")
                    .font(.system(size: 12))
                    .foregroundStyle(Palette.mutedInk)
            }
            Spacer()
            HStack(spacing: 7) {
                Image(systemName: "archivebox")
                Text("本机已保存 \(model.packs.count) 套")
            }
            .font(.system(size: 12, weight: .medium))
            .foregroundStyle(Palette.mutedInk)
            .padding(.horizontal, 12)
            .padding(.vertical, 7)
            .background(Color.white.opacity(0.62))
            .clipShape(Capsule())
        }
        .padding(.horizontal, 28)
        .frame(height: 72)
    }
}

private struct StepStrip: View {
    @ObservedObject var model: WordFormatLibraryModel

    private let steps = [
        (1, "导入格式源", "保存到本机"),
        (2, "查看已用格式", "确认样式与页面"),
        (3, "应用到文档", "另存为新文件")
    ]

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(steps.enumerated()), id: \.element.0) { index, item in
                Button {
                    if item.0 == 1 || (item.0 == 2 && model.selectedPack != nil) ||
                        (item.0 == 3 && model.selectedPack != nil) {
                        model.currentStep = item.0
                    }
                } label: {
                    HStack(spacing: 11) {
                        ZStack {
                            Circle()
                                .fill(model.currentStep == item.0 ? Palette.green : Palette.mint)
                            Text("\(item.0)")
                                .font(.system(size: 12, weight: .bold))
                                .foregroundStyle(model.currentStep == item.0 ? .white : Palette.green)
                        }
                        .frame(width: 27, height: 27)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(item.1)
                                .font(.system(size: 13, weight: .semibold))
                            Text(item.2)
                                .font(.system(size: 10.5))
                                .foregroundStyle(Palette.mutedInk)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .disabled(model.isBusy || (item.0 > 1 && model.selectedPack == nil))

                if index < steps.count - 1 {
                    Rectangle()
                        .fill(Palette.line)
                        .frame(width: 46, height: 1)
                }
            }
        }
        .padding(.horizontal, 72)
        .frame(height: 67)
        .background(Color.white.opacity(0.28))
    }
}

// MARK: - Step 1

private struct ImportStepView: View {
    @ObservedObject var model: WordFormatLibraryModel
    @State private var isDropTarget = false
    @State private var packPendingDeletion: PackManifest?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                HStack(alignment: .firstTextBaseline) {
                    VStack(alignment: .leading, spacing: 5) {
                        Text("先选择一份“格式样板”")
                            .font(.system(size: 28, weight: .bold, design: .rounded))
                        Text("程序只提取格式系统，不保存文档正文、页眉页脚文字或批注内容。")
                            .font(.system(size: 13))
                            .foregroundStyle(Palette.mutedInk)
                    }
                    Spacer()
                    if !model.packs.isEmpty {
                        Button {
                            Task { await model.reloadLibrary() }
                        } label: {
                            Label("刷新", systemImage: "arrow.clockwise")
                        }
                        .buttonStyle(SecondaryButtonStyle())
                    }
                }

                HStack(alignment: .top, spacing: 22) {
                    ImportDropCard(model: model, isTargeted: $isDropTarget)
                        .frame(maxWidth: .infinity, minHeight: 252)
                    VStack(alignment: .leading, spacing: 14) {
                        Label("导入后会发生什么", systemImage: "checklist")
                            .font(.system(size: 15, weight: .bold))
                        ExplanationRow(number: "01", text: "识别文档里真正使用过的标题、正文、字符与表格样式")
                        ExplanationRow(number: "02", text: "保存字体、段落、标题多级编号与页面设置")
                        ExplanationRow(number: "03", text: "以后直接选择格式库，无需再次选择样板文档")
                    }
                    .frame(width: 330, alignment: .leading)
                    .padding(24)
                    .background(Palette.mint.opacity(0.66))
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                }

                if let notice = model.libraryNotice {
                    Label(notice, systemImage: "exclamationmark.triangle")
                        .font(.system(size: 12))
                        .foregroundStyle(Palette.amber)
                }

                if let confirmation = model.libraryConfirmation {
                    Label(confirmation, systemImage: "checkmark.circle.fill")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(Palette.green)
                }

                if !model.packs.isEmpty {
                    VStack(alignment: .leading, spacing: 13) {
                        HStack {
                            Text("我的格式库")
                                .font(.system(size: 18, weight: .bold))
                            Text("无需重新导入")
                                .font(.system(size: 11, weight: .medium))
                                .foregroundStyle(Palette.green)
                                .padding(.horizontal, 9)
                                .padding(.vertical, 4)
                                .background(Palette.mint)
                                .clipShape(Capsule())
                        }
                        LazyVGrid(
                            columns: [GridItem(.adaptive(minimum: 280), spacing: 14)],
                            spacing: 14
                        ) {
                            ForEach(model.packs, id: \.libraryIdentity) { pack in
                                SavedPackCard(
                                    pack: pack,
                                    selectAction: { model.selectPack(pack) },
                                    deleteAction: { packPendingDeletion = pack }
                                )
                                .disabled(model.isBusy)
                            }
                        }
                    }
                }
            }
            .padding(28)
        }
        .alert(item: $packPendingDeletion) { pack in
            Alert(
                title: Text("移除「\(pack.name)」？"),
                message: Text(
                    "只会把本机保存的这套格式方案移到废纸篓，不会删除原来的样板 Word 文件，也不会影响已经生成的文档。"
                ),
                primaryButton: .destructive(Text("移到废纸篓")) {
                    Task { await model.deletePack(pack) }
                },
                secondaryButton: .cancel(Text("取消"))
            )
        }
    }
}

private struct ImportDropCard: View {
    @ObservedObject var model: WordFormatLibraryModel
    @Binding var isTargeted: Bool

    var body: some View {
        VStack(spacing: 14) {
            ZStack {
                Circle().fill(Palette.mint)
                Image(systemName: "doc.badge.plus")
                    .font(.system(size: 31, weight: .medium))
                    .foregroundStyle(Palette.green)
            }
            .frame(width: 68, height: 68)
            Text("选择 Word 格式源")
                .font(.system(size: 19, weight: .bold))
            Text("拖放到这里，或从 Mac 中选择文件")
                .font(.system(size: 13))
                .foregroundStyle(Palette.mutedInk)
            Button {
                chooseSourceFile()
            } label: {
                Label("选择 Word 文件", systemImage: "folder")
            }
            .buttonStyle(PrimaryButtonStyle())
            Text("支持 DOCX、DOCM、DOTX、DOTM")
                .font(.system(size: 10.5, weight: .medium))
                .foregroundStyle(Palette.mutedInk)
        }
        .frame(maxWidth: .infinity, minHeight: 252)
        .background(isTargeted ? Palette.mint : Palette.card)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(
                    isTargeted ? Palette.green : Palette.line,
                    style: StrokeStyle(lineWidth: isTargeted ? 2 : 1, dash: [7, 5])
                )
        }
        .onDrop(of: [UTType.fileURL], isTargeted: $isTargeted) { providers in
            guard let provider = providers.first else { return false }
            provider.loadDataRepresentation(forTypeIdentifier: UTType.fileURL.identifier) { data, _ in
                guard let data,
                      let url = URL(dataRepresentation: data, relativeTo: nil) else { return }
                Task { @MainActor in
                    await model.importSource(url)
                }
            }
            return true
        }
    }

    private func chooseSourceFile() {
        let panel = NSOpenPanel()
        panel.title = "选择包含所需格式的 Word 文档"
        panel.prompt = "导入格式"
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = ["docx", "docm", "dotx", "dotm"].compactMap {
            UTType(filenameExtension: $0)
        }
        guard panel.runModal() == .OK, let url = panel.url else { return }
        Task { await model.importSource(url) }
    }
}

private struct ExplanationRow: View {
    let number: String
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 11) {
            Text(number)
                .font(.system(size: 10, weight: .bold, design: .monospaced))
                .foregroundStyle(Palette.green)
                .frame(width: 26, height: 26)
                .background(Color.white.opacity(0.78))
                .clipShape(Circle())
            Text(text)
                .font(.system(size: 12.5))
                .foregroundStyle(Palette.ink.opacity(0.88))
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

private struct SavedPackCard: View {
    let pack: PackManifest
    let selectAction: () -> Void
    let deleteAction: () -> Void

    var body: some View {
        HStack(spacing: 0) {
            Button(action: selectAction) {
                HStack(spacing: 14) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(Palette.mint)
                        Image(systemName: "text.book.closed")
                            .font(.system(size: 21, weight: .medium))
                            .foregroundStyle(Palette.green)
                    }
                    .frame(width: 48, height: 48)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(pack.name)
                            .font(.system(size: 14, weight: .bold))
                            .lineLimit(1)
                        Text("\(pack.formatCountSummary) · \(dateText(pack.createdAt))")
                            .font(.system(size: 11))
                            .foregroundStyle(Palette.mutedInk)
                            .lineLimit(1)
                        Text(pack.sourceFileName ?? "来源文件名未保存")
                            .font(.system(size: 10.5))
                            .foregroundStyle(Palette.mutedInk.opacity(0.85))
                            .lineLimit(1)
                    }
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(Palette.green)
                }
                .padding(15)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            Rectangle()
                .fill(Palette.line)
                .frame(width: 1, height: 48)

            Button(role: .destructive, action: deleteAction) {
                Image(systemName: "trash")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(Color.red.opacity(0.82))
                    .frame(width: 48, height: 78)
            }
            .buttonStyle(.plain)
            .help("移除「\(pack.name)」")
            .accessibilityLabel("移除格式方案 \(pack.name)")
        }
        .background(Palette.card)
        .clipShape(RoundedRectangle(cornerRadius: 15, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 15, style: .continuous)
                .stroke(Palette.line, lineWidth: 1)
        }
    }

    private func dateText(_ raw: String?) -> String {
        guard let raw else { return "已保存" }
        let parser = ISO8601DateFormatter()
        guard let date = parser.date(from: raw) else { return "已保存" }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_CN")
        formatter.dateFormat = "yyyy/MM/dd"
        return formatter.string(from: date)
    }
}

// MARK: - Step 2

private enum FormatFilter: String, CaseIterable, Identifiable {
    case all = "全部"
    case headings = "标题"
    case paragraphs = "正文与段落"
    case characters = "字符"
    case tables = "表格"

    var id: String { rawValue }

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

enum ParagraphAlignmentEditChoice: String, CaseIterable, Identifiable {
    case unchanged
    case left
    case center
    case right
    case justified
    case distributed

    var id: String { rawValue }

    var label: String {
        switch self {
        case .unchanged: return "不修改"
        case .left: return "左对齐"
        case .center: return "居中"
        case .right: return "右对齐"
        case .justified: return "两端对齐"
        case .distributed: return "分散对齐"
        }
    }

    var encodedValue: String? {
        switch self {
        case .unchanged: return nil
        case .left: return "left"
        case .center: return "center"
        case .right: return "right"
        case .justified: return "both"
        case .distributed: return "distribute"
        }
    }

    func effectiveValue(original: String?) -> String? {
        encodedValue ?? Self.canonical(original)
    }

    func changedValue(original: String?) -> String? {
        guard let encodedValue else { return nil }
        return Self.canonical(original) == encodedValue ? nil : encodedValue
    }

    static func canonical(_ value: String?) -> String? {
        guard let value else { return nil }
        switch value {
        case "start": return "left"
        case "end": return "right"
        default: return value
        }
    }
}

enum LineSpacingEditChoice: String, CaseIterable, Identifiable {
    case unchanged
    case auto
    case exact
    case atLeast

    var id: String { rawValue }

    var label: String {
        switch self {
        case .unchanged: return "不修改"
        case .auto: return "倍数"
        case .exact: return "固定值"
        case .atLeast: return "最小值"
        }
    }

    var encodedValue: String? {
        self == .unchanged ? nil : rawValue
    }

    static func canonical(_ rule: String?, spacing: Double?) -> String? {
        if rule == nil, spacing != nil { return "auto" }
        return rule
    }
}

enum ParagraphIndentUnit: String, CaseIterable, Identifiable {
    case characters
    case points

    var id: String { rawValue }
    var label: String { self == .characters ? "字符" : "pt" }
    var fullLabel: String { self == .characters ? "字符" : "磅" }
}

enum SpecialIndentEditChoice: String, CaseIterable, Identifiable {
    case unchanged
    case none
    case firstLine
    case hanging

    var id: String { rawValue }

    var label: String {
        switch self {
        case .unchanged: return "不修改"
        case .none: return "无"
        case .firstLine: return "首行缩进"
        case .hanging: return "悬挂缩进"
        }
    }

    var requiresValue: Bool {
        self == .firstLine || self == .hanging
    }
}

struct ParagraphIndentMeasurement: Equatable {
    let value: Double
    let unit: ParagraphIndentUnit

    var displayText: String {
        "\(paragraphNumber(value)) \(unit.label)"
    }

    func previewPoints(fontSize: Double) -> Double {
        unit == .characters ? value * fontSize : value
    }
}

private struct ParagraphLineEdit {
    let spacing: Double
    let rule: String
}

private struct ParagraphSpecialIndentEdit {
    let firstLine: Double
    let hanging: Double
}

enum BoldEditChoice: String, CaseIterable, Identifiable {
    case inherit
    case bold
    case regular

    var id: String { rawValue }

    var label: String {
        switch self {
        case .inherit: return "继承"
        case .bold: return "粗体"
        case .regular: return "常规"
        }
    }

    func effectiveValue(original: Bool?) -> Bool? {
        switch self {
        case .inherit: return original
        case .bold: return true
        case .regular: return false
        }
    }

    func changedValue(original: Bool?) -> Bool? {
        switch self {
        case .inherit: return nil
        case .bold: return original == true ? nil : true
        case .regular: return original == false ? nil : false
        }
    }
}

struct StyleEditDraft: Identifiable {
    let format: UsedFormat
    var fontEastAsiaOverride = ""
    var fontLatinOverride = ""
    var sizeOverride = ""
    var boldChoice: BoldEditChoice = .inherit
    var colorOverride = ""
    var alignmentChoice: ParagraphAlignmentEditChoice = .unchanged
    var spaceBeforeOverride = ""
    var spaceAfterOverride = ""
    var lineSpacingChoice: LineSpacingEditChoice = .unchanged
    var lineSpacingOverride = ""
    var indentUnit: ParagraphIndentUnit
    var leftIndentOverride = ""
    var rightIndentOverride = ""
    var specialIndentChoice: SpecialIndentEditChoice = .unchanged
    var specialIndentOverride = ""
    var tableFillOverride = ""
    var tableAccentOverride = ""

    init(format: UsedFormat) {
        self.format = format
        indentUnit = Self.preferredIndentUnit(for: format)
    }

    var id: String { format.id }
    var isTable: Bool { format.type == "table" }
    var isOptionalTableCandidate: Bool {
        isTable && format.inferenceLabel == "可选表格方案"
    }
    var supportsTextFormatting: Bool {
        format.type == "paragraph" || format.type == "character"
    }
    var supportsParagraphFormatting: Bool { format.type == "paragraph" }

    var effectiveFontEastAsia: String? {
        normalizedText(fontEastAsiaOverride) ?? format.fontEastAsia
    }

    var effectiveFontLatin: String? {
        normalizedText(fontLatinOverride) ?? format.fontLatin
    }

    var effectiveSize: Double? {
        parsedSize(sizeOverride) ?? format.sizePt
    }

    var effectiveBold: Bool? {
        boldChoice.effectiveValue(original: format.bold)
    }

    var effectiveColorHex: String? {
        normalizedColor(colorOverride) ?? normalizedColor(format.colorHex ?? "")
    }

    var effectiveAlignment: String? {
        alignmentChoice.effectiveValue(original: format.alignment)
    }

    var effectiveSpaceBeforePt: Double? {
        parsedNumber(spaceBeforeOverride) ?? format.spaceBeforePt
    }

    var effectiveSpaceAfterPt: Double? {
        parsedNumber(spaceAfterOverride) ?? format.spaceAfterPt
    }

    var effectiveLineRule: String? {
        lineSpacingChoice.encodedValue ?? LineSpacingEditChoice.canonical(
            format.lineRule,
            spacing: format.lineSpacing
        )
    }

    var effectiveLineSpacing: Double? {
        parsedNumber(lineSpacingOverride) ?? format.lineSpacing
    }

    var effectiveLeftIndent: ParagraphIndentMeasurement? {
        if let value = parsedNumber(leftIndentOverride) {
            return ParagraphIndentMeasurement(value: value, unit: indentUnit)
        }
        return Self.preferredMeasurement(
            chars: format.leftIndentChars,
            points: format.leftIndentPt
        )
    }

    var effectiveRightIndent: ParagraphIndentMeasurement? {
        if let value = parsedNumber(rightIndentOverride) {
            return ParagraphIndentMeasurement(value: value, unit: indentUnit)
        }
        return Self.preferredMeasurement(
            chars: format.rightIndentChars,
            points: format.rightIndentPt
        )
    }

    var originalSpecialIndentChoice: SpecialIndentEditChoice {
        if Self.hasNonzero(format.firstLineIndentChars) ||
            Self.hasNonzero(format.firstLineIndentPt) {
            return .firstLine
        }
        if Self.hasNonzero(format.hangingIndentChars) ||
            Self.hasNonzero(format.hangingIndentPt) {
            return .hanging
        }
        return .none
    }

    var effectiveSpecialIndentChoice: SpecialIndentEditChoice {
        specialIndentChoice == .unchanged
            ? originalSpecialIndentChoice
            : specialIndentChoice
    }

    var effectiveSpecialIndent: ParagraphIndentMeasurement? {
        switch specialIndentChoice {
        case .firstLine, .hanging:
            guard let value = parsedNumber(specialIndentOverride) else { return nil }
            return ParagraphIndentMeasurement(value: value, unit: indentUnit)
        case .none:
            return nil
        case .unchanged:
            switch originalSpecialIndentChoice {
            case .firstLine:
                return Self.preferredMeasurement(
                    chars: format.firstLineIndentChars,
                    points: format.firstLineIndentPt
                )
            case .hanging:
                return Self.preferredMeasurement(
                    chars: format.hangingIndentChars,
                    points: format.hangingIndentPt
                )
            case .none, .unchanged:
                return nil
            }
        }
    }

    var effectiveTableFillHex: String? {
        normalizedColor(tableFillOverride) ?? normalizedColor(format.tableFillHex ?? "")
    }

    var effectiveTableAccentHex: String? {
        normalizedColor(tableAccentOverride) ?? normalizedColor(format.tableAccentHex ?? "")
    }

    var validationError: String? {
        guard isTable || supportsTextFormatting else { return nil }
        if supportsTextFormatting {
            for (label, value) in [
                ("中文字体", fontEastAsiaOverride),
                ("西文字体", fontLatinOverride)
            ] {
                let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
                if trimmed.count > 127 {
                    return "\(label)名称最多允许 127 个字符。"
                }
                if trimmed.unicodeScalars.contains(where: {
                    CharacterSet.controlCharacters.contains($0)
                }) {
                    return "\(label)名称不能包含控制字符。"
                }
            }
            if !sizeOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                guard let size = parsedSize(sizeOverride),
                      size >= 5,
                      size <= 200,
                      (size * 2).rounded() == size * 2 else {
                    return "字号需要在 5–200 pt 之间，并以 0.5 pt 递增。"
                }
            }
            if !colorOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
               normalizedColor(colorOverride) == nil {
                return "文字颜色请输入 6 位十六进制色值，例如 165D52。"
            }
        }
        if supportsParagraphFormatting {
            if let error = validateNumber(
                spaceBeforeOverride,
                label: "段前间距",
                range: 0...1584,
                scale: 20,
                unit: "pt"
            ) { return error }
            if let error = validateNumber(
                spaceAfterOverride,
                label: "段后间距",
                range: 0...1584,
                scale: 20,
                unit: "pt"
            ) { return error }

            if lineSpacingChoice != .unchanged,
               lineSpacingOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                return "选择新的行距类型后，请填写行距值。"
            }
            if !lineSpacingOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                let rule = lineSpacingChoice.encodedValue ??
                    LineSpacingEditChoice.canonical(
                        format.lineRule,
                        spacing: format.lineSpacing
                    ) ?? "auto"
                if rule == "auto" {
                    if let error = validateNumber(
                        lineSpacingOverride,
                        label: "倍数行距",
                        range: 0.5...10,
                        scale: 100,
                        unit: "倍"
                    ) { return error }
                } else if let error = validateNumber(
                    lineSpacingOverride,
                    label: rule == "exact" ? "固定行距" : "最小行距",
                    range: 1...1584,
                    scale: 20,
                    unit: "pt"
                ) { return error }
            }

            let sideRange: ClosedRange<Double> = indentUnit == .characters
                ? -100...100
                : -1584...1584
            let positiveRange: ClosedRange<Double> = indentUnit == .characters
                ? 0...100
                : 0...1584
            let scale = indentUnit == .characters ? 100.0 : 20.0
            if let error = validateNumber(
                leftIndentOverride,
                label: "左缩进",
                range: sideRange,
                scale: scale,
                unit: indentUnit.label
            ) { return error }
            if let error = validateNumber(
                rightIndentOverride,
                label: "右缩进",
                range: sideRange,
                scale: scale,
                unit: indentUnit.label
            ) { return error }
            if specialIndentChoice.requiresValue {
                if specialIndentOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    return "请选择首行或悬挂缩进后填写缩进值。"
                }
                if let error = validateNumber(
                    specialIndentOverride,
                    label: specialIndentChoice == .firstLine ? "首行缩进" : "悬挂缩进",
                    range: positiveRange,
                    scale: scale,
                    unit: indentUnit.label
                ) { return error }
            }
        }
        if isTable {
            if !tableFillOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
               normalizedColor(tableFillOverride) == nil {
                return "表格底色请输入 6 位十六进制色值，例如 F7F7F7。"
            }
            if !tableAccentOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
               normalizedColor(tableAccentOverride) == nil {
                return "首行强调色请输入 6 位十六进制色值，例如 165D52。"
            }
        }
        return nil
    }

    var payload: StyleEditPayload? {
        guard validationError == nil else { return nil }

        let eastAsia = changedText(
            override: fontEastAsiaOverride,
            original: format.fontEastAsia
        )
        let latin = changedText(
            override: fontLatinOverride,
            original: format.fontLatin
        )
        let size = changedSize(override: sizeOverride, original: format.sizePt)
        let textColor = changedColor(
            override: colorOverride,
            original: format.colorHex
        )
        let tableFill = changedColor(
            override: tableFillOverride,
            original: format.tableFillHex
        )
        let tableAccent = changedColor(
            override: tableAccentOverride,
            original: format.tableAccentHex
        )
        let lineEdit = changedLineEdit
        let leftIndent = changedNumber(
            override: leftIndentOverride,
            original: indentUnit == .characters
                ? format.leftIndentChars
                : format.leftIndentPt
        )
        let rightIndent = changedNumber(
            override: rightIndentOverride,
            original: indentUnit == .characters
                ? format.rightIndentChars
                : format.rightIndentPt
        )
        let specialIndent = changedSpecialIndent
        let payload = StyleEditPayload(
            styleID: format.styleID,
            fontEastAsia: supportsTextFormatting ? eastAsia : nil,
            fontLatin: supportsTextFormatting ? latin : nil,
            sizePt: supportsTextFormatting ? size : nil,
            bold: supportsTextFormatting
                ? boldChoice.changedValue(original: format.bold)
                : nil,
            colorHex: supportsTextFormatting ? textColor : nil,
            alignment: supportsParagraphFormatting
                ? alignmentChoice.changedValue(original: format.alignment)
                : nil,
            spaceBeforePt: supportsParagraphFormatting
                ? changedNumber(
                    override: spaceBeforeOverride,
                    original: format.spaceBeforePt
                )
                : nil,
            spaceAfterPt: supportsParagraphFormatting
                ? changedNumber(
                    override: spaceAfterOverride,
                    original: format.spaceAfterPt
                )
                : nil,
            lineSpacing: supportsParagraphFormatting ? lineEdit?.spacing : nil,
            lineRule: supportsParagraphFormatting ? lineEdit?.rule : nil,
            leftIndentPt: supportsParagraphFormatting && indentUnit == .points
                ? leftIndent
                : nil,
            rightIndentPt: supportsParagraphFormatting && indentUnit == .points
                ? rightIndent
                : nil,
            firstLineIndentPt: supportsParagraphFormatting && indentUnit == .points
                ? specialIndent?.firstLine
                : nil,
            hangingIndentPt: supportsParagraphFormatting && indentUnit == .points
                ? specialIndent?.hanging
                : nil,
            leftIndentChars: supportsParagraphFormatting && indentUnit == .characters
                ? leftIndent
                : nil,
            rightIndentChars: supportsParagraphFormatting && indentUnit == .characters
                ? rightIndent
                : nil,
            firstLineIndentChars: supportsParagraphFormatting && indentUnit == .characters
                ? specialIndent?.firstLine
                : nil,
            hangingIndentChars: supportsParagraphFormatting && indentUnit == .characters
                ? specialIndent?.hanging
                : nil,
            tableFillHex: isTable ? tableFill : nil,
            tableAccentHex: isTable ? tableAccent : nil
        )
        return payload.changedFieldCount > 0 ? payload : nil
    }

    var changedFieldCount: Int { payload?.changedFieldCount ?? 0 }
    var isEdited: Bool { changedFieldCount > 0 }
    var hasUserInput: Bool {
        [
            fontEastAsiaOverride,
            fontLatinOverride,
            sizeOverride,
            colorOverride,
            spaceBeforeOverride,
            spaceAfterOverride,
            lineSpacingOverride,
            leftIndentOverride,
            rightIndentOverride,
            tableFillOverride,
            tableAccentOverride
        ].contains(where: {
            !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }) || boldChoice != .inherit ||
            alignmentChoice != .unchanged ||
            lineSpacingChoice != .unchanged ||
            specialIndentChoice != .unchanged ||
            (specialIndentChoice.requiresValue &&
                !specialIndentOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
    }

    mutating func reset() {
        fontEastAsiaOverride = ""
        fontLatinOverride = ""
        sizeOverride = ""
        boldChoice = .inherit
        colorOverride = ""
        alignmentChoice = .unchanged
        spaceBeforeOverride = ""
        spaceAfterOverride = ""
        lineSpacingChoice = .unchanged
        lineSpacingOverride = ""
        indentUnit = Self.preferredIndentUnit(for: format)
        leftIndentOverride = ""
        rightIndentOverride = ""
        specialIndentChoice = .unchanged
        specialIndentOverride = ""
        tableFillOverride = ""
        tableAccentOverride = ""
    }

    private func changedText(override: String, original: String?) -> String? {
        guard let value = normalizedText(override) else { return nil }
        return value == original?.trimmingCharacters(in: .whitespacesAndNewlines)
            ? nil
            : value
    }

    private func changedSize(override: String, original: Double?) -> Double? {
        guard let value = parsedSize(override) else { return nil }
        if let original, abs(original - value) < 0.0001 { return nil }
        return value
    }

    private func changedNumber(override: String, original: Double?) -> Double? {
        guard let value = parsedNumber(override) else { return nil }
        if let original, abs(original - value) < 0.0001 { return nil }
        return value
    }

    private var changedLineEdit: ParagraphLineEdit? {
        let hasValue = !lineSpacingOverride
            .trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        guard hasValue || lineSpacingChoice != .unchanged,
              let value = parsedNumber(lineSpacingOverride) else {
            return nil
        }
        let rule = lineSpacingChoice.encodedValue ??
            LineSpacingEditChoice.canonical(
                format.lineRule,
                spacing: format.lineSpacing
            ) ?? "auto"
        let originalRule = LineSpacingEditChoice.canonical(
            format.lineRule,
            spacing: format.lineSpacing
        )
        if rule == originalRule,
           let originalSpacing = format.lineSpacing,
           abs(originalSpacing - value) < 0.0001 {
            return nil
        }
        return ParagraphLineEdit(spacing: value, rule: rule)
    }

    private var changedSpecialIndent: ParagraphSpecialIndentEdit? {
        switch specialIndentChoice {
        case .unchanged:
            return nil
        case .none:
            guard originalSpecialIndentChoice != .none else { return nil }
            return ParagraphSpecialIndentEdit(firstLine: 0, hanging: 0)
        case .firstLine, .hanging:
            guard let value = parsedNumber(specialIndentOverride) else { return nil }
            let originalValue: Double?
            if indentUnit == .characters {
                originalValue = specialIndentChoice == .firstLine
                    ? format.firstLineIndentChars
                    : format.hangingIndentChars
            } else {
                originalValue = specialIndentChoice == .firstLine
                    ? format.firstLineIndentPt
                    : format.hangingIndentPt
            }
            if originalSpecialIndentChoice == specialIndentChoice,
               let originalValue,
               abs(originalValue - value) < 0.0001 {
                return nil
            }
            return ParagraphSpecialIndentEdit(
                firstLine: specialIndentChoice == .firstLine ? value : 0,
                hanging: specialIndentChoice == .hanging ? value : 0
            )
        }
    }

    private func changedColor(override: String, original: String?) -> String? {
        guard let value = normalizedColor(override) else { return nil }
        return value == normalizedColor(original ?? "") ? nil : value
    }

    private func normalizedText(_ value: String) -> String? {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    private func parsedSize(_ value: String) -> Double? {
        parsedNumber(value)
    }

    private func parsedNumber(_ value: String) -> Double? {
        let normalized = value
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: ",", with: ".")
        guard !normalized.isEmpty,
              let parsed = Double(normalized),
              parsed.isFinite else { return nil }
        return parsed
    }

    private func normalizedColor(_ value: String) -> String? {
        normalizedHexColor(value)
    }

    private func validateNumber(
        _ raw: String,
        label: String,
        range: ClosedRange<Double>,
        scale: Double,
        unit: String
    ) -> String? {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        guard let value = parsedNumber(raw), range.contains(value) else {
            return "\(label)需要在 \(paragraphNumber(range.lowerBound))–\(paragraphNumber(range.upperBound)) \(unit) 之间。"
        }
        guard abs(value * scale - (value * scale).rounded()) < 0.0001 else {
            let increment = 1 / scale
            return "\(label)请以 \(paragraphNumber(increment)) \(unit) 递增。"
        }
        return nil
    }

    private static func preferredIndentUnit(for format: UsedFormat) -> ParagraphIndentUnit {
        if [
            format.leftIndentChars,
            format.rightIndentChars,
            format.firstLineIndentChars,
            format.hangingIndentChars
        ].contains(where: { $0 != nil }) {
            return .characters
        }
        if [
            format.leftIndentPt,
            format.rightIndentPt,
            format.firstLineIndentPt,
            format.hangingIndentPt
        ].contains(where: { $0 != nil }) {
            return .points
        }
        return .characters
    }

    private static func preferredMeasurement(
        chars: Double?,
        points: Double?
    ) -> ParagraphIndentMeasurement? {
        if let chars {
            return ParagraphIndentMeasurement(value: chars, unit: .characters)
        }
        if let points {
            return ParagraphIndentMeasurement(value: points, unit: .points)
        }
        return nil
    }

    private static func hasNonzero(_ value: Double?) -> Bool {
        guard let value else { return false }
        return abs(value) >= 0.0001
    }
}

private struct StyleEditorSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var model: WordFormatLibraryModel
    let pack: PackManifest

    @State private var drafts: [StyleEditDraft]
    @State private var selectedDraftID: String?
    @State private var schemeName: String
    @State private var searchText = ""
    @State private var isSubmitting = false
    @State private var errorMessage = ""
    @State private var isShowingError = false
    @State private var isConfirmingDiscard = false
    @State private var editorNotice: String?

    init(model: WordFormatLibraryModel, pack: PackManifest) {
        self.model = model
        self.pack = pack
        var editableFormats = pack.usedFormats
        if !editableFormats.contains(where: { $0.type == "table" }),
           let candidate = pack.tableStyleEditCandidate,
           candidate.type == "table",
           !editableFormats.contains(where: { $0.id == candidate.id }) {
            editableFormats.append(candidate)
        }
        let initialDrafts = editableFormats.map { StyleEditDraft(format: $0) }
        _drafts = State(initialValue: initialDrafts)
        _selectedDraftID = State(initialValue: initialDrafts.first?.id)
        _schemeName = State(initialValue: "\(pack.name) · 自定义")
    }

    private var filteredDrafts: [StyleEditDraft] {
        let query = searchText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return drafts }
        return drafts.filter {
            $0.format.name.localizedCaseInsensitiveContains(query) ||
                $0.format.styleID.localizedCaseInsensitiveContains(query) ||
                styleTypeText($0.format).localizedCaseInsensitiveContains(query) ||
                ($0.format.inferenceLabel?.localizedCaseInsensitiveContains(query) ?? false)
        }
    }

    private var selectedIndex: Int? {
        guard let selectedDraftID else { return nil }
        return drafts.firstIndex(where: { $0.id == selectedDraftID })
    }

    private var editedStyleCount: Int {
        drafts.filter(\.isEdited).count
    }

    private var dirtyStyleCount: Int {
        drafts.filter(\.hasUserInput).count
    }

    private var editedFieldCount: Int {
        drafts.reduce(0) { $0 + $1.changedFieldCount }
    }

    private var firstValidationError: String? {
        drafts.compactMap(\.validationError).first
    }

    private var normalizedSchemeName: String {
        schemeName.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var nameValidationError: String? {
        if normalizedSchemeName.isEmpty { return "请填写新格式方案的名称。" }
        if normalizedSchemeName.count > 120 { return "格式方案名称最多允许 120 个字符。" }
        return nil
    }

    private var request: StyleEditRequest? {
        guard nameValidationError == nil, firstValidationError == nil else { return nil }
        let payloads = drafts.compactMap(\.payload)
        return payloads.isEmpty ? nil : StyleEditRequest(styles: payloads)
    }

    private var canSave: Bool {
        request != nil && !isSubmitting && !model.isBusy
    }

    var body: some View {
        VStack(spacing: 0) {
            editorHeader
            Divider().overlay(Palette.line)
            HStack(spacing: 0) {
                editorSidebar
                    .frame(width: 265)
                Divider().overlay(Palette.line)
                if let selectedIndex {
                    StyleEditControls(draft: $drafts[selectedIndex])
                        .frame(minWidth: 330, maxWidth: .infinity, maxHeight: .infinity)
                    Divider().overlay(Palette.line)
                    StyleEditLivePreview(draft: drafts[selectedIndex])
                        .frame(width: 330)
                        .frame(maxHeight: .infinity)
                } else {
                    VStack(spacing: 10) {
                        Image(systemName: "textformat")
                            .font(.system(size: 28))
                        Text("选择一种格式开始调整")
                    }
                    .foregroundStyle(Palette.mutedInk)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            Divider().overlay(Palette.line)
            editorFooter
        }
        .frame(minWidth: 930, idealWidth: 1080, minHeight: 650, idealHeight: 740)
        .background(Palette.paper)
        .foregroundStyle(Palette.ink)
        .overlay {
            if model.isBusy {
                BusyOverlay(
                    message: model.busyMessage,
                    canCancel: model.canCancelBusyOperation,
                    isCancelling: model.isCancelling,
                    cancel: model.cancelCurrentOperation
                )
            }
        }
        .alert("无法保存格式方案", isPresented: $isShowingError) {
            Button("好") { isShowingError = false }
        } message: {
            Text(errorMessage)
        }
        .alert("放弃这些调整？", isPresented: $isConfirmingDiscard) {
            Button("继续编辑", role: .cancel) { }
            Button("放弃调整", role: .destructive) { dismiss() }
        } message: {
            Text("已经修改的格式还没有保存。关闭后，本次调整会丢失，原格式方案不会受到影响。")
        }
        .interactiveDismissDisabled(dirtyStyleCount > 0 || model.isBusy)
    }

    private var editorHeader: some View {
        HStack(spacing: 16) {
            ZStack {
                RoundedRectangle(cornerRadius: 11, style: .continuous)
                    .fill(Palette.mint)
                Image(systemName: "paintbrush.pointed.fill")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(Palette.green)
            }
            .frame(width: 42, height: 42)

            VStack(alignment: .leading, spacing: 3) {
                Text("编辑格式方案")
                    .font(.system(size: 19, weight: .bold, design: .rounded))
                Text("从「\(pack.name)」派生新方案，原方案始终保持不变")
                    .font(.system(size: 11.5))
                    .foregroundStyle(Palette.mutedInk)
                    .lineLimit(1)
            }
            Spacer(minLength: 18)
            VStack(alignment: .leading, spacing: 4) {
                Text("新方案名称")
                    .font(.system(size: 10.5, weight: .semibold))
                    .foregroundStyle(Palette.mutedInk)
                TextField("填写方案名称", text: $schemeName)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 280)
                    .accessibilityLabel("新格式方案名称")
            }
        }
        .padding(.horizontal, 22)
        .frame(height: 78)
        .background(Color.white.opacity(0.38))
    }

    private var editorSidebar: some View {
        VStack(spacing: 0) {
            TextField("搜索格式", text: $searchText)
                .textFieldStyle(.roundedBorder)
                .padding(14)
                .accessibilityLabel("搜索可编辑格式")
            Divider().overlay(Palette.line)
            ScrollView {
                LazyVStack(spacing: 7) {
                    ForEach(filteredDrafts) { draft in
                        Button {
                            selectedDraftID = draft.id
                        } label: {
                            HStack(spacing: 10) {
                                Image(systemName: draft.isTable ? "tablecells" : "textformat")
                                    .font(.system(size: 12, weight: .semibold))
                                    .foregroundStyle(Palette.green)
                                    .frame(width: 28, height: 28)
                                    .background(Palette.mint)
                                    .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(draft.format.name)
                                        .font(.system(size: 12.5, weight: .semibold))
                                        .lineLimit(1)
                                    Text(
                                        draft.isOptionalTableCandidate
                                            ? "可选表格方案 · 修改后启用"
                                            : styleTypeText(draft.format)
                                    )
                                        .font(.system(size: 10))
                                        .foregroundStyle(Palette.mutedInk)
                                }
                                Spacer(minLength: 4)
                                if draft.validationError != nil && draft.hasUserInput {
                                    Image(systemName: "exclamationmark.triangle.fill")
                                        .font(.system(size: 10))
                                        .foregroundStyle(Palette.amber)
                                } else if draft.isEdited {
                                    Text("已改 \(draft.changedFieldCount)")
                                        .font(.system(size: 9.5, weight: .bold))
                                        .foregroundStyle(Palette.green)
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 3)
                                        .background(Palette.mint)
                                        .clipShape(Capsule())
                                }
                            }
                            .padding(.horizontal, 9)
                            .frame(maxWidth: .infinity, minHeight: 48, alignment: .leading)
                            .background(
                                selectedDraftID == draft.id
                                    ? Palette.mint.opacity(0.82)
                                    : Color.white.opacity(0.54)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                            .overlay {
                                RoundedRectangle(cornerRadius: 10, style: .continuous)
                                    .stroke(
                                        selectedDraftID == draft.id
                                            ? Palette.green.opacity(0.48)
                                            : Palette.line.opacity(0.75),
                                        lineWidth: 1
                                    )
                            }
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("编辑 \(draft.format.name)")
                        .accessibilityValue(
                            draft.validationError != nil && draft.hasUserInput
                                ? "修改内容需要修正"
                                : (draft.isEdited ? "已修改 \(draft.changedFieldCount) 项" : "未修改")
                        )
                    }
                }
                .padding(10)
            }
            if filteredDrafts.isEmpty {
                Text("没有匹配的格式")
                    .font(.system(size: 11.5))
                    .foregroundStyle(Palette.mutedInk)
                    .padding(.bottom, 14)
            }
        }
        .background(Color.white.opacity(0.28))
    }

    private var editorFooter: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                if let error = nameValidationError ?? firstValidationError {
                    Label(error, systemImage: "exclamationmark.triangle")
                        .foregroundStyle(Palette.amber)
                } else if let editorNotice {
                    Label(editorNotice, systemImage: "info.circle")
                        .foregroundStyle(Palette.mutedInk)
                } else if editedStyleCount > 0 {
                    Text("已修改 \(editedStyleCount) 种格式、\(editedFieldCount) 个属性")
                        .foregroundStyle(Palette.green)
                } else if dirtyStyleCount > 0 {
                    Text("当前填写内容与原方案相同，尚无需要保存的变化。")
                        .foregroundStyle(Palette.mutedInk)
                } else {
                    Text("选择格式并修改属性；空白字段会继承原方案。")
                        .foregroundStyle(Palette.mutedInk)
                }
            }
            .font(.system(size: 11.5, weight: .medium))
            .lineLimit(2)

            Spacer()
            Button("重置全部") {
                for index in drafts.indices { drafts[index].reset() }
                editorNotice = "全部属性已恢复为原方案。"
            }
            .buttonStyle(SecondaryButtonStyle())
            .disabled(dirtyStyleCount == 0 || model.isBusy)

            Button("取消") {
                if dirtyStyleCount > 0 {
                    isConfirmingDiscard = true
                } else {
                    dismiss()
                }
            }
            .buttonStyle(SecondaryButtonStyle())
            .keyboardShortcut(.cancelAction)
            .disabled(model.isBusy)

            Button {
                saveDerivedPack()
            } label: {
                Label("保存为新方案", systemImage: "square.and.arrow.down")
            }
            .buttonStyle(PrimaryButtonStyle())
            .keyboardShortcut(.defaultAction)
            .disabled(!canSave)
            .opacity(canSave ? 1 : 0.48)
            .accessibilityHint("保存为一套新的格式方案，不会覆盖原方案")
        }
        .padding(.horizontal, 18)
        .frame(minHeight: 66)
        .background(Color.white.opacity(0.44))
    }

    private func saveDerivedPack() {
        guard !isSubmitting, !model.isBusy, let request else { return }
        isSubmitting = true
        editorNotice = nil
        Task {
            defer { isSubmitting = false }
            do {
                _ = try await model.derivePack(
                    from: pack,
                    named: normalizedSchemeName,
                    request: request
                )
                dismiss()
            } catch is CancellationError {
                editorNotice = "保存已取消；原格式方案和格式库均未被覆盖。"
            } catch {
                errorMessage = error.localizedDescription
                isShowingError = true
            }
        }
    }
}

private struct StyleEditControls: View {
    @Binding var draft: StyleEditDraft

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(draft.format.name)
                            .font(.system(size: 18, weight: .bold, design: .rounded))
                        Text("\(styleTypeText(draft.format)) · ID：\(draft.format.styleID)")
                            .font(.system(size: 10.5))
                            .foregroundStyle(Palette.mutedInk)
                            .lineLimit(1)
                    }
                    Spacer()
                    Button("重置此格式") { draft.reset() }
                        .buttonStyle(.plain)
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(Palette.green)
                        .disabled(!draft.hasUserInput)
                        .accessibilityHint("恢复这一个格式的全部属性")
                }

                Text("仅填写需要调整的属性；留空或选择“继承”会使用原方案。")
                    .font(.system(size: 11.5))
                    .foregroundStyle(Palette.mutedInk)
                    .padding(11)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Palette.mint.opacity(0.56))
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))

                if draft.isOptionalTableCandidate {
                    Label(
                        "模板没有实际使用表格。只有修改并保存此方案后，它才会用于目标文档；不修改时仍保留目标表格外观。",
                        systemImage: "tablecells"
                    )
                    .font(.system(size: 11.5, weight: .medium))
                    .foregroundStyle(Palette.green)
                    .padding(11)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Palette.mint.opacity(0.68))
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                }

                if draft.supportsTextFormatting {
                    StyleEditorSection(title: "字体", icon: "textformat") {
                        FontOverrideField(
                            label: "中文字体",
                            original: draft.format.fontEastAsia,
                            value: $draft.fontEastAsiaOverride
                        )
                        FontOverrideField(
                            label: "西文字体",
                            original: draft.format.fontLatin,
                            value: $draft.fontLatinOverride
                        )
                        HStack {
                            StyleEditorControlLabel("字号")
                            TextField(
                                draft.format.sizePt.map { "原方案 \(number($0)) pt" } ?? "继承原方案",
                                text: $draft.sizeOverride
                            )
                            .textFieldStyle(.roundedBorder)
                            .frame(maxWidth: 170)
                            .accessibilityLabel("字号")
                            Text("pt")
                                .font(.system(size: 11))
                                .foregroundStyle(Palette.mutedInk)
                        }
                        Text("支持 5–200 pt，并以 0.5 pt 递增。")
                            .font(.system(size: 10))
                            .foregroundStyle(Palette.mutedInk)
                            .padding(.leading, 98)
                    }

                    StyleEditorSection(title: "字形与颜色", icon: "bold") {
                        HStack {
                            StyleEditorControlLabel("粗细")
                            Picker("粗细", selection: $draft.boldChoice) {
                                ForEach(BoldEditChoice.allCases) { choice in
                                    Text(choice.label).tag(choice)
                                }
                            }
                            .labelsHidden()
                            .pickerStyle(.segmented)
                            .accessibilityLabel("字形粗细")
                        }
                        EditorColorField(
                            label: "文字颜色",
                            originalHex: draft.format.colorHex,
                            value: $draft.colorOverride,
                            fallbackHex: "19332F"
                        )
                    }

                    if draft.supportsParagraphFormatting {
                        StyleEditorSection(title: "段落排列", icon: "text.alignleft") {
                            HStack(spacing: 8) {
                                StyleEditorControlLabel("对齐方式")
                                Picker("对齐方式", selection: $draft.alignmentChoice) {
                                    ForEach(ParagraphAlignmentEditChoice.allCases) { choice in
                                        Text(choice.label).tag(choice)
                                    }
                                }
                                .labelsHidden()
                                .pickerStyle(.menu)
                                .frame(maxWidth: 190)
                                .accessibilityLabel("段落对齐方式")
                                .accessibilityValue(
                                    draft.alignmentChoice == .unchanged
                                        ? "不修改，原方案\(paragraphAlignmentText(draft.format.alignment))"
                                        : draft.alignmentChoice.label
                                )
                                Spacer(minLength: 0)
                            }
                            EditorOriginalValue(
                                "原方案：\(paragraphAlignmentText(draft.format.alignment))"
                            )
                        }

                        StyleEditorSection(title: "间距与行距", icon: "line.3.horizontal") {
                            ParagraphNumberField(
                                label: "段前",
                                originalText: originalPointText(draft.format.spaceBeforePt),
                                value: $draft.spaceBeforeOverride,
                                unit: "pt",
                                accessibilityHint: "允许 0 到 1584 磅，留空保留原方案"
                            )
                            ParagraphNumberField(
                                label: "段后",
                                originalText: originalPointText(draft.format.spaceAfterPt),
                                value: $draft.spaceAfterOverride,
                                unit: "pt",
                                accessibilityHint: "允许 0 到 1584 磅，留空保留原方案"
                            )
                            HStack(spacing: 8) {
                                StyleEditorControlLabel("行距类型")
                                Picker("行距类型", selection: $draft.lineSpacingChoice) {
                                    ForEach(LineSpacingEditChoice.allCases) { choice in
                                        Text(choice.label).tag(choice)
                                    }
                                }
                                .labelsHidden()
                                .pickerStyle(.menu)
                                .frame(maxWidth: 190)
                                .accessibilityLabel("行距类型")
                                .accessibilityValue(
                                    draft.lineSpacingChoice == .unchanged
                                        ? "不修改，原方案\(paragraphLineSpacingText(value: draft.format.lineSpacing, rule: draft.format.lineRule))"
                                        : draft.lineSpacingChoice.label
                                )
                                Spacer(minLength: 0)
                            }
                            ParagraphNumberField(
                                label: "行距数值",
                                originalText: originalLineSpacingValue,
                                value: $draft.lineSpacingOverride,
                                unit: lineSpacingUnit,
                                accessibilityHint: lineSpacingHint
                            )
                            EditorOriginalValue(
                                "原方案：\(paragraphLineSpacingText(value: draft.format.lineSpacing, rule: draft.format.lineRule))"
                            )
                        }

                        StyleEditorSection(title: "缩进", icon: "arrow.left.and.right") {
                            HStack(spacing: 8) {
                                StyleEditorControlLabel("输入单位")
                                Picker("缩进输入单位", selection: $draft.indentUnit) {
                                    ForEach(ParagraphIndentUnit.allCases) { unit in
                                        Text(unit.fullLabel).tag(unit)
                                    }
                                }
                                .labelsHidden()
                                .pickerStyle(.segmented)
                                .frame(maxWidth: 190)
                                .accessibilityLabel("缩进输入单位")
                                .accessibilityValue(draft.indentUnit.fullLabel)
                                Spacer(minLength: 0)
                            }
                            ParagraphNumberField(
                                label: "左缩进",
                                originalText: originalIndentText(
                                    chars: draft.format.leftIndentChars,
                                    points: draft.format.leftIndentPt
                                ),
                                value: $draft.leftIndentOverride,
                                unit: draft.indentUnit.label,
                                accessibilityHint: indentSideHint
                            )
                            ParagraphNumberField(
                                label: "右缩进",
                                originalText: originalIndentText(
                                    chars: draft.format.rightIndentChars,
                                    points: draft.format.rightIndentPt
                                ),
                                value: $draft.rightIndentOverride,
                                unit: draft.indentUnit.label,
                                accessibilityHint: indentSideHint
                            )
                            HStack(spacing: 8) {
                                StyleEditorControlLabel("特殊格式")
                                Picker("特殊缩进格式", selection: $draft.specialIndentChoice) {
                                    ForEach(SpecialIndentEditChoice.allCases) { choice in
                                        Text(choice.label).tag(choice)
                                    }
                                }
                                .labelsHidden()
                                .pickerStyle(.menu)
                                .frame(maxWidth: 190)
                                .accessibilityLabel("特殊缩进格式")
                                .accessibilityValue(
                                    draft.specialIndentChoice == .unchanged
                                        ? "不修改，原方案\(paragraphSpecialIndentText(draft.format))"
                                        : draft.specialIndentChoice.label
                                )
                                Spacer(minLength: 0)
                            }
                            ParagraphNumberField(
                                label: "缩进值",
                                originalText: originalSpecialIndentValue,
                                value: $draft.specialIndentOverride,
                                unit: draft.indentUnit.label,
                                accessibilityHint: specialIndentHint,
                                isEnabled: draft.specialIndentChoice.requiresValue
                            )
                            EditorOriginalValue(
                                "原方案：\(paragraphIndentSidesText(draft.format))；\(paragraphSpecialIndentText(draft.format))"
                            )
                            Text("字符单位可精确设置“首行缩进 2 字符”；切换单位不会换算已经输入的数值。")
                                .font(.system(size: 10))
                                .foregroundStyle(Palette.mutedInk)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                } else if draft.isTable {
                    StyleEditorSection(title: "表格颜色", icon: "tablecells") {
                        EditorColorField(
                            label: "表格底色",
                            originalHex: draft.format.tableFillHex,
                            value: $draft.tableFillOverride,
                            fallbackHex: "FFFFFF"
                        )
                        EditorColorField(
                            label: "首行强调色",
                            originalHex: draft.format.tableAccentHex,
                            value: $draft.tableAccentOverride,
                            fallbackHex: "27685D"
                        )
                    }
                    Text("首版只调整表格底色和首行强调色；边框、行高与单元格边距继续继承原方案。")
                        .font(.system(size: 10.5))
                        .foregroundStyle(Palette.mutedInk)
                        .fixedSize(horizontal: false, vertical: true)
                } else {
                    Label("此类格式暂不支持直接编辑。", systemImage: "lock")
                        .font(.system(size: 12))
                        .foregroundStyle(Palette.mutedInk)
                }

                if let error = draft.validationError {
                    Label(error, systemImage: "exclamationmark.triangle.fill")
                        .font(.system(size: 11.5, weight: .medium))
                        .foregroundStyle(Palette.amber)
                        .padding(11)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Palette.amberWash)
                        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                }
            }
            .padding(20)
        }
        .background(Palette.paper.opacity(0.72))
    }

    private var originalLineSpacingValue: String {
        draft.format.lineSpacing.map(paragraphNumber) ?? "继承"
    }

    private var lineSpacingUnit: String {
        let rule = draft.lineSpacingChoice.encodedValue ??
            LineSpacingEditChoice.canonical(
                draft.format.lineRule,
                spacing: draft.format.lineSpacing
            ) ?? "auto"
        return rule == "auto" ? "倍" : "pt"
    }

    private var lineSpacingHint: String {
        lineSpacingUnit == "倍"
            ? "允许 0.5 到 10 倍，并以 0.01 递增；留空保留原方案"
            : "允许 1 到 1584 磅，并以 0.05 磅递增；留空保留原方案"
    }

    private var indentSideHint: String {
        draft.indentUnit == .characters
            ? "允许负 100 到 100 字符，并以 0.01 字符递增；留空保留原方案"
            : "允许负 1584 到 1584 磅，并以 0.05 磅递增；留空保留原方案"
    }

    private var specialIndentHint: String {
        draft.indentUnit == .characters
            ? "允许 0 到 100 字符，并以 0.01 字符递增"
            : "允许 0 到 1584 磅，并以 0.05 磅递增"
    }

    private var originalSpecialIndentValue: String {
        switch draft.originalSpecialIndentChoice {
        case .firstLine:
            return originalIndentText(
                chars: draft.format.firstLineIndentChars,
                points: draft.format.firstLineIndentPt
            )
        case .hanging:
            return originalIndentText(
                chars: draft.format.hangingIndentChars,
                points: draft.format.hangingIndentPt
            )
        case .none, .unchanged:
            return "无"
        }
    }

    private func originalPointText(_ value: Double?) -> String {
        value.map { "\(paragraphNumber($0)) pt" } ?? "继承"
    }

    private func originalIndentText(chars: Double?, points: Double?) -> String {
        if let chars { return "\(paragraphNumber(chars)) 字符" }
        if let points { return "\(paragraphNumber(points)) pt" }
        return "继承"
    }
}

private struct StyleEditorSection<Content: View>: View {
    let title: String
    let icon: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            Label(title, systemImage: icon)
                .font(.system(size: 13.5, weight: .bold))
                .foregroundStyle(Palette.ink)
            content
        }
        .padding(15)
        .background(Color.white.opacity(0.76))
        .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 13, style: .continuous)
                .stroke(Palette.line, lineWidth: 1)
        }
    }
}

private struct StyleEditorControlLabel: View {
    let text: String

    init(_ text: String) {
        self.text = text
    }

    var body: some View {
        Text(text)
            .font(.system(size: 11.5, weight: .semibold))
            .foregroundStyle(Palette.mutedInk)
            .frame(width: 86, alignment: .leading)
    }
}

private struct ParagraphNumberField: View {
    let label: String
    let originalText: String
    @Binding var value: String
    let unit: String
    let accessibilityHint: String
    var isEnabled = true

    var body: some View {
        HStack(spacing: 8) {
            StyleEditorControlLabel(label)
            TextField(
                isEnabled ? "原方案 \(originalText)" : "无需填写",
                text: $value
            )
            .textFieldStyle(.roundedBorder)
            .frame(maxWidth: 170)
            .disabled(!isEnabled)
            .accessibilityLabel("\(label)，单位\(unit)")
            .accessibilityValue(
                value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    ? (isEnabled ? "不修改，原方案 \(originalText)" : "无需填写")
                    : "\(value) \(unit)"
            )
            .accessibilityHint(accessibilityHint)
            Text(unit)
                .font(.system(size: 11))
                .foregroundStyle(Palette.mutedInk)
                .frame(minWidth: 24, alignment: .leading)
                .accessibilityHidden(true)
            if isEnabled && !value.isEmpty {
                Button {
                    value = ""
                } label: {
                    Image(systemName: "arrow.uturn.backward.circle")
                }
                .buttonStyle(.plain)
                .foregroundStyle(Palette.mutedInk)
                .help("恢复原方案")
                .accessibilityLabel("恢复\(label)原值")
            }
        }
    }
}

private struct EditorOriginalValue: View {
    let text: String

    init(_ text: String) {
        self.text = text
    }

    var body: some View {
        Text(text)
            .font(.system(size: 10))
            .foregroundStyle(Palette.mutedInk)
            .padding(.leading, 98)
            .fixedSize(horizontal: false, vertical: true)
    }
}

private struct FontOverrideField: View {
    let label: String
    let original: String?
    @Binding var value: String

    private static let installedFamilies = NSFontManager.shared.availableFontFamilies
        .sorted { $0.localizedCaseInsensitiveCompare($1) == .orderedAscending }

    var body: some View {
        HStack(spacing: 8) {
            StyleEditorControlLabel(label)
            TextField(
                original.map { "原方案 \($0)" } ?? "继承主题字体",
                text: $value
            )
            .textFieldStyle(.roundedBorder)
            .accessibilityLabel(label)
            Menu {
                ForEach(Self.installedFamilies, id: \.self) { family in
                    Button(family) { value = family }
                }
            } label: {
                Image(systemName: "chevron.down")
                    .frame(width: 22, height: 22)
            }
            .menuStyle(.borderlessButton)
            .frame(width: 28)
            .help("从本机已安装字体中选择")
            .accessibilityLabel("选择\(label)")
            if !value.isEmpty {
                Button {
                    value = ""
                } label: {
                    Image(systemName: "arrow.uturn.backward.circle")
                }
                .buttonStyle(.plain)
                .foregroundStyle(Palette.mutedInk)
                .help("恢复原方案")
                .accessibilityLabel("恢复\(label)原值")
            }
        }
    }
}

private struct EditorColorField: View {
    let label: String
    let originalHex: String?
    @Binding var value: String
    let fallbackHex: String

    private var effectiveHex: String {
        normalizedHexColor(value) ?? normalizedHexColor(originalHex ?? "") ?? fallbackHex
    }

    private var colorBinding: Binding<Color> {
        Binding(
            get: { Color(hex: effectiveHex) },
            set: { value = hexString(from: $0) ?? effectiveHex }
        )
    }

    var body: some View {
        HStack(spacing: 8) {
            StyleEditorControlLabel(label)
            ColorPicker("选择\(label)", selection: colorBinding, supportsOpacity: false)
                .labelsHidden()
                .frame(width: 28)
            TextField(
                originalHex.map { "原方案 #\($0)" } ?? "继承原方案",
                text: $value
            )
            .textFieldStyle(.roundedBorder)
            .frame(maxWidth: 150)
            .accessibilityLabel("\(label)十六进制值")
            Text("#RRGGBB")
                .font(.system(size: 9.5, design: .monospaced))
                .foregroundStyle(Palette.mutedInk)
            if !value.isEmpty {
                Button {
                    value = ""
                } label: {
                    Image(systemName: "arrow.uturn.backward.circle")
                }
                .buttonStyle(.plain)
                .foregroundStyle(Palette.mutedInk)
                .help("恢复原方案")
                .accessibilityLabel("恢复\(label)原值")
            }
        }
    }
}

private struct StyleEditLivePreview: View {
    let draft: StyleEditDraft

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("实时示意")
                        .font(.system(size: 16, weight: .bold, design: .rounded))
                    Text("用于比较视觉方向；最终效果以 Word 生成结果为准。")
                        .font(.system(size: 10.5))
                        .foregroundStyle(Palette.mutedInk)
                        .fixedSize(horizontal: false, vertical: true)
                }

                if draft.isTable {
                    tablePreview
                } else {
                    textPreview
                }

                VStack(spacing: 0) {
                    PreviewPropertyRow(label: "格式", value: draft.format.name)
                    if draft.supportsTextFormatting {
                        PreviewPropertyRow(
                            label: "中文字体",
                            value: draft.effectiveFontEastAsia ?? "继承主题"
                        )
                        PreviewPropertyRow(
                            label: "西文字体",
                            value: draft.effectiveFontLatin ?? "继承主题"
                        )
                        PreviewPropertyRow(
                            label: "字号",
                            value: draft.effectiveSize.map { "\(number($0)) pt" } ?? "继承"
                        )
                        PreviewPropertyRow(
                            label: "字形",
                            value: draft.effectiveBold == true ? "粗体" : "常规"
                        )
                        PreviewPropertyRow(
                            label: "文字颜色",
                            value: draft.effectiveColorHex.map { "#\($0)" } ?? "自动"
                        )
                        if draft.supportsParagraphFormatting {
                            PreviewPropertyRow(
                                label: "对齐",
                                value: paragraphAlignmentText(draft.effectiveAlignment)
                            )
                            PreviewPropertyRow(
                                label: "段前 / 段后",
                                value: paragraphSpacingText(
                                    before: draft.effectiveSpaceBeforePt,
                                    after: draft.effectiveSpaceAfterPt
                                )
                            )
                            PreviewPropertyRow(
                                label: "行距",
                                value: paragraphLineSpacingText(
                                    value: draft.effectiveLineSpacing,
                                    rule: draft.effectiveLineRule
                                )
                            )
                            PreviewPropertyRow(
                                label: "左 / 右缩进",
                                value: paragraphIndentSidesText(
                                    left: draft.effectiveLeftIndent,
                                    right: draft.effectiveRightIndent
                                )
                            )
                            PreviewPropertyRow(
                                label: "特殊缩进",
                                value: paragraphSpecialIndentText(
                                    choice: draft.effectiveSpecialIndentChoice,
                                    measurement: draft.effectiveSpecialIndent
                                )
                            )
                        }
                    } else if draft.isTable {
                        PreviewPropertyRow(
                            label: "表格底色",
                            value: draft.effectiveTableFillHex.map { "#\($0)" } ?? "继承"
                        )
                        PreviewPropertyRow(
                            label: "首行强调",
                            value: draft.effectiveTableAccentHex.map { "#\($0)" } ?? "继承"
                        )
                    }
                }
                .background(Color.white.opacity(0.64))
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

                if draft.isEdited {
                    Label(
                        "此格式已修改 \(draft.changedFieldCount) 个属性",
                        systemImage: "checkmark.circle.fill"
                    )
                    .font(.system(size: 11.5, weight: .semibold))
                    .foregroundStyle(Palette.green)
                }
            }
            .padding(20)
        }
        .background(Color.white.opacity(0.32))
    }

    private var textPreview: some View {
        let size = min(max(draft.effectiveSize ?? 16, 11), 34)
        let fontName = draft.effectiveFontEastAsia ?? draft.effectiveFontLatin
        return VStack(alignment: .leading, spacing: 11) {
            if draft.supportsParagraphFormatting {
                ParagraphStyleTextPreview(draft: draft)
                    .frame(maxWidth: .infinity, minHeight: 138, maxHeight: 168)
                    .accessibilityHidden(true)
            } else {
                Text(draft.format.sample.isEmpty ? "标题与正文格式示意 Aa 123" : draft.format.sample)
                    .font(fontName.map { .custom($0, size: size) } ?? .system(size: size))
                    .fontWeight(draft.effectiveBold == true ? .bold : .regular)
                    .italic(draft.format.italic == true)
                    .foregroundStyle(draft.effectiveColorHex.map(Color.init(hex:)) ?? Palette.ink)
                    .lineLimit(3)
                    .frame(maxWidth: .infinity, minHeight: 94, alignment: .leading)
            }
            Rectangle()
                .fill(Palette.line)
                .frame(height: 1)
            Text("Forma 赋式 · Typography Preview")
                .font(.system(size: 10.5))
                .foregroundStyle(Palette.mutedInk)
        }
        .padding(17)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(Palette.line, lineWidth: 1)
        }
        .shadow(color: Palette.ink.opacity(0.06), radius: 10, y: 4)
    }

    private var tablePreview: some View {
        let fill = Color(hex: draft.effectiveTableFillHex ?? "FFFFFF")
        let accent = Color(hex: draft.effectiveTableAccentHex ?? "27685D")
        return VStack(spacing: 1) {
            previewTableRow(values: ["项目", "说明", "状态"], fill: accent, isHeader: true)
            previewTableRow(values: ["标题", "格式规范", "完成"], fill: fill, isHeader: false)
            previewTableRow(values: ["正文", "字体与颜色", "检查"], fill: fill, isHeader: false)
        }
        .padding(1)
        .background(Palette.line)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(Palette.line, lineWidth: 1)
        }
    }

    private func previewTableRow(values: [String], fill: Color, isHeader: Bool) -> some View {
        HStack(spacing: 1) {
            ForEach(values, id: \.self) { value in
                Text(value)
                    .font(.system(size: 10.5, weight: isHeader ? .bold : .regular))
                    .foregroundStyle(isHeader ? Color.white : Palette.ink)
                    .frame(maxWidth: .infinity, minHeight: 38)
                    .background(fill)
            }
        }
    }
}

private struct ParagraphStyleTextPreview: NSViewRepresentable {
    let draft: StyleEditDraft

    func makeNSView(context: Context) -> NSTextView {
        let textView = NSTextView(frame: .zero)
        textView.isEditable = false
        textView.isSelectable = false
        textView.drawsBackground = false
        textView.textContainerInset = .zero
        textView.textContainer?.lineFragmentPadding = 0
        textView.textContainer?.widthTracksTextView = true
        textView.isHorizontallyResizable = false
        textView.isVerticallyResizable = true
        textView.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        return textView
    }

    func updateNSView(_ textView: NSTextView, context: Context) {
        let size = min(max(draft.effectiveSize ?? 16, 11), 34)
        let fontName = draft.effectiveFontEastAsia ?? draft.effectiveFontLatin
        var font = fontName.flatMap { NSFont(name: $0, size: CGFloat(size)) }
            ?? NSFont.systemFont(ofSize: CGFloat(size))
        if draft.effectiveBold == true {
            font = NSFontManager.shared.convert(font, toHaveTrait: .boldFontMask)
        }
        if draft.format.italic == true {
            font = NSFontManager.shared.convert(font, toHaveTrait: .italicFontMask)
        }

        let paragraphStyle = NSMutableParagraphStyle()
        paragraphStyle.alignment = nsTextAlignment(draft.effectiveAlignment)
        paragraphStyle.paragraphSpacingBefore = CGFloat(
            min(max(draft.effectiveSpaceBeforePt ?? 0, 0), 42)
        )
        paragraphStyle.paragraphSpacing = CGFloat(
            min(max(draft.effectiveSpaceAfterPt ?? 0, 0), 42)
        )

        if let lineSpacing = draft.effectiveLineSpacing {
            switch draft.effectiveLineRule ?? "auto" {
            case "exact":
                let height = CGFloat(min(max(lineSpacing, 1), 80))
                paragraphStyle.minimumLineHeight = height
                paragraphStyle.maximumLineHeight = height
            case "atLeast":
                paragraphStyle.minimumLineHeight = CGFloat(min(max(lineSpacing, 1), 80))
            default:
                paragraphStyle.lineHeightMultiple = CGFloat(min(max(lineSpacing, 0.5), 3))
            }
        }

        let left = previewIndentPoints(draft.effectiveLeftIndent, fontSize: size)
        let right = max(0, previewIndentPoints(draft.effectiveRightIndent, fontSize: size))
        let special = max(0, previewIndentPoints(draft.effectiveSpecialIndent, fontSize: size))
        paragraphStyle.headIndent = CGFloat(left)
        paragraphStyle.firstLineHeadIndent = CGFloat(left)
        paragraphStyle.tailIndent = CGFloat(-right)
        switch draft.effectiveSpecialIndentChoice {
        case .firstLine:
            paragraphStyle.firstLineHeadIndent = CGFloat(left + special)
        case .hanging:
            paragraphStyle.headIndent = CGFloat(left + special)
        case .none, .unchanged:
            break
        }

        let primary = draft.format.sample.isEmpty
            ? "标题与正文格式示意 Aa 123"
            : draft.format.sample
        let previewText = primary +
            "　这是一段用于观察自动换行、首行或悬挂缩进的示意文字。\n" +
            "下一段用于比较段前、段后与行距设置。"
        let color = draft.effectiveColorHex.flatMap(nsColorFromHex) ?? NSColor.labelColor
        textView.textStorage?.setAttributedString(
            NSAttributedString(
                string: previewText,
                attributes: [
                    .font: font,
                    .foregroundColor: color,
                    .paragraphStyle: paragraphStyle
                ]
            )
        )
    }

    private func previewIndentPoints(
        _ measurement: ParagraphIndentMeasurement?,
        fontSize: Double
    ) -> Double {
        guard let measurement else { return 0 }
        return min(max(measurement.previewPoints(fontSize: fontSize), -24), 120)
    }

    private func nsTextAlignment(_ value: String?) -> NSTextAlignment {
        switch ParagraphAlignmentEditChoice.canonical(value) {
        case "center": return .center
        case "right": return .right
        case "both", "distribute": return .justified
        default: return .left
        }
    }

    private func nsColorFromHex(_ value: String) -> NSColor? {
        guard let normalized = normalizedHexColor(value),
              let rgb = UInt64(normalized, radix: 16) else { return nil }
        return NSColor(
            red: CGFloat((rgb >> 16) & 0xFF) / 255,
            green: CGFloat((rgb >> 8) & 0xFF) / 255,
            blue: CGFloat(rgb & 0xFF) / 255,
            alpha: 1
        )
    }
}

private struct PreviewPropertyRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Text(label).foregroundStyle(Palette.mutedInk)
            Spacer(minLength: 8)
            Text(value)
                .foregroundStyle(Palette.ink)
                .lineLimit(2)
                .multilineTextAlignment(.trailing)
        }
        .font(.system(size: 10.5))
        .padding(.horizontal, 11)
        .padding(.vertical, 8)
        .overlay(alignment: .bottom) {
            Rectangle().fill(Palette.line.opacity(0.65)).frame(height: 1)
        }
    }
}

private func paragraphAlignmentText(_ alignment: String?) -> String {
    switch ParagraphAlignmentEditChoice.canonical(alignment) {
    case "center": return "居中"
    case "right": return "右对齐"
    case "both": return "两端对齐"
    case "distribute": return "分散对齐"
    case "left": return "左对齐"
    case .some(let value): return "其他（\(value)）"
    case nil: return "继承"
    }
}

private func paragraphSpacingText(before: Double?, after: Double?) -> String {
    let beforeText = before.map { "\(paragraphNumber($0)) pt" } ?? "继承"
    let afterText = after.map { "\(paragraphNumber($0)) pt" } ?? "继承"
    return "\(beforeText) / \(afterText)"
}

private func paragraphLineSpacingText(value: Double?, rule: String?) -> String {
    guard let value else { return "继承" }
    switch LineSpacingEditChoice.canonical(rule, spacing: value) {
    case "exact": return "固定值 \(paragraphNumber(value)) pt"
    case "atLeast": return "最小值 \(paragraphNumber(value)) pt"
    case "auto", nil: return "\(paragraphNumber(value)) 倍"
    case .some(let raw): return "\(paragraphNumber(value)) pt（\(raw)）"
    }
}

private func paragraphIndentSidesText(_ format: UsedFormat) -> String {
    paragraphIndentSidesText(
        left: preferredParagraphIndentMeasurement(
            chars: format.leftIndentChars,
            points: format.leftIndentPt
        ),
        right: preferredParagraphIndentMeasurement(
            chars: format.rightIndentChars,
            points: format.rightIndentPt
        )
    )
}

private func paragraphIndentSidesText(
    left: ParagraphIndentMeasurement?,
    right: ParagraphIndentMeasurement?
) -> String {
    "左 \(left?.displayText ?? "继承")，右 \(right?.displayText ?? "继承")"
}

private func paragraphSpecialIndentText(_ format: UsedFormat) -> String {
    if let measurement = preferredNonzeroParagraphIndentMeasurement(
        chars: format.firstLineIndentChars,
        points: format.firstLineIndentPt
    ) {
        return paragraphSpecialIndentText(choice: .firstLine, measurement: measurement)
    }
    if let measurement = preferredNonzeroParagraphIndentMeasurement(
        chars: format.hangingIndentChars,
        points: format.hangingIndentPt
    ) {
        return paragraphSpecialIndentText(choice: .hanging, measurement: measurement)
    }
    return "无"
}

private func paragraphSpecialIndentText(
    choice: SpecialIndentEditChoice,
    measurement: ParagraphIndentMeasurement?
) -> String {
    switch choice {
    case .firstLine:
        return "首行 \(measurement?.displayText ?? "待填写")"
    case .hanging:
        return "悬挂 \(measurement?.displayText ?? "待填写")"
    case .none, .unchanged:
        return "无"
    }
}

private func preferredParagraphIndentMeasurement(
    chars: Double?,
    points: Double?
) -> ParagraphIndentMeasurement? {
    if let chars {
        return ParagraphIndentMeasurement(value: chars, unit: .characters)
    }
    if let points {
        return ParagraphIndentMeasurement(value: points, unit: .points)
    }
    return nil
}

private func preferredNonzeroParagraphIndentMeasurement(
    chars: Double?,
    points: Double?
) -> ParagraphIndentMeasurement? {
    if let chars, abs(chars) >= 0.0001 {
        return ParagraphIndentMeasurement(value: chars, unit: .characters)
    }
    if let points, abs(points) >= 0.0001 {
        return ParagraphIndentMeasurement(value: points, unit: .points)
    }
    return nil
}

private func styleTypeText(_ format: UsedFormat) -> String {
    if let level = format.outlineLevel { return "标题 \(level + 1)" }
    switch format.type {
    case "paragraph": return "段落样式"
    case "character": return "字符样式"
    case "table": return "表格样式"
    default: return "\(format.type) 样式"
    }
}

private func normalizedHexColor(_ raw: String) -> String? {
    let value = raw
        .trimmingCharacters(in: .whitespacesAndNewlines)
        .trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        .uppercased()
    guard value.count == 6,
          value.unicodeScalars.allSatisfy({
              CharacterSet(charactersIn: "0123456789ABCDEF").contains($0)
          }) else { return nil }
    return value
}

private func hexString(from color: Color) -> String? {
    let native = NSColor(color)
    guard let rgb = native.usingColorSpace(.sRGB) else { return nil }
    return String(
        format: "%02X%02X%02X",
        Int((rgb.redComponent * 255).rounded()),
        Int((rgb.greenComponent * 255).rounded()),
        Int((rgb.blueComponent * 255).rounded())
    )
}

private struct FormatPreviewStepView: View {
    @ObservedObject var model: WordFormatLibraryModel
    @State private var filter: FormatFilter = .all
    @State private var isShowingStyleEditor = false

    private var formats: [UsedFormat] {
        model.selectedPack?.usedFormats.filter(filter.includes) ?? []
    }

    var body: some View {
        if let pack = model.selectedPack {
            VStack(spacing: 0) {
                HStack(spacing: 14) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(pack.name)
                            .font(.system(size: 23, weight: .bold, design: .rounded))
                        Text(pack.formatOverviewDescription)
                            .font(.system(size: 12.5))
                            .foregroundStyle(Palette.mutedInk)
                    }
                    Spacer()
                    Button {
                        isShowingStyleEditor = true
                    } label: {
                        Label("编辑格式方案", systemImage: "slider.horizontal.3")
                    }
                    .buttonStyle(SecondaryButtonStyle())
                    .help("调整标题、段落、字符或表格样式，并另存为新方案")
                    Button {
                        model.currentStep = 1
                    } label: {
                        Label("换一套格式", systemImage: "arrow.left.arrow.right")
                    }
                    .buttonStyle(SecondaryButtonStyle())
                    Button {
                        model.beginTargetStep()
                    } label: {
                        Label("下一步", systemImage: "arrow.right")
                    }
                    .buttonStyle(PrimaryButtonStyle())
                }
                .padding(.horizontal, 28)
                .padding(.vertical, 18)

                Divider().overlay(Palette.line)

                HStack(spacing: 0) {
                    VStack(spacing: 0) {
                        SummaryBar(pack: pack)
                        if pack.manualFormatting.paragraphCount > 0 || pack.manualFormatting.runCount > 0 {
                            ManualFormattingNotice(manual: pack.manualFormatting)
                                .padding(.horizontal, 24)
                                .padding(.top, 12)
                        }
                        if let conflicts = pack.headingNumberingConflicts, !conflicts.isEmpty {
                            Label(
                                "检测到 \(conflicts.count) 个标题样式使用多套编号；将采用最常用规则，请在生成后检查章节重启。",
                                systemImage: "exclamationmark.triangle"
                            )
                            .font(.system(size: 11.5, weight: .medium))
                            .foregroundStyle(Color.orange)
                            .padding(.horizontal, 24)
                            .padding(.top, 12)
                        }
                        if let warnings = pack.headingCompletionWarnings, !warnings.isEmpty {
                            ForEach(warnings, id: \.self) { warning in
                                Label(warning, systemImage: "exclamationmark.triangle")
                                    .font(.system(size: 11.5, weight: .medium))
                                    .foregroundStyle(Color.orange)
                                    .padding(.horizontal, 24)
                                    .padding(.top, 12)
                            }
                        }
                        FormatFilterBar(
                            filter: $filter,
                            formats: pack.usedFormats
                        )
                        ScrollView {
                            if formats.isEmpty {
                                VStack(spacing: 10) {
                                    Image(systemName: "line.3.horizontal.decrease.circle")
                                        .font(.system(size: 26))
                                    Text("这一类没有被使用的格式")
                                        .font(.system(size: 13, weight: .medium))
                                }
                                .foregroundStyle(Palette.mutedInk)
                                .frame(maxWidth: .infinity)
                                .padding(.top, 74)
                            } else {
                                LazyVGrid(
                                    columns: [GridItem(.adaptive(minimum: 270), spacing: 13)],
                                    spacing: 13
                                ) {
                                    ForEach(formats) { format in
                                        FormatCard(
                                            format: format,
                                            isSelected: model.selectedFormatID == format.id
                                        ) {
                                            model.selectedFormatID = format.id
                                        }
                                    }
                                }
                                .padding(.horizontal, 24)
                                .padding(.bottom, 28)
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)

                    Divider().overlay(Palette.line)

                    StyleInspector(
                        format: model.selectedFormat,
                        pageLayout: pack.pageLayout
                    )
                    .frame(width: 310)
                    .background(Color.white.opacity(0.34))
                }
            }
            .sheet(isPresented: $isShowingStyleEditor) {
                StyleEditorSheet(model: model, pack: pack)
            }
        } else {
            EmptySelectionView { model.currentStep = 1 }
        }
    }
}

private struct SummaryBar: View {
    let pack: PackManifest

    var body: some View {
        HStack(spacing: 10) {
            MiniStat(
                value: "\(pack.usedStyleCount + (pack.inferredStyleCount ?? 0) + pack.resolvedCustomStyleCount)",
                label: pack.resolvedCustomStyleCount > 0
                    ? "格式总数（含自定义）"
                    : ((pack.inferredStyleCount ?? 0) > 0 ? "实际 + 补全" : "实际使用"),
                icon: "textformat"
            )
            MiniStat(value: "\(pack.documentSummary.paragraphCount)", label: "段落", icon: "paragraphsign")
            MiniStat(value: "\(pack.documentSummary.tableCount)", label: "表格", icon: "tablecells")
            MiniStat(value: "\(pack.documentSummary.sectionCount)", label: "节", icon: "doc.text")
        }
        .padding(.horizontal, 24)
        .padding(.top, 16)
    }
}

private struct MiniStat: View {
    let value: String
    let label: String
    let icon: String

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(Palette.green)
                .frame(width: 29, height: 29)
                .background(Palette.mint)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            VStack(alignment: .leading, spacing: 0) {
                Text(value).font(.system(size: 16, weight: .bold, design: .rounded))
                Text(label).font(.system(size: 10.5)).foregroundStyle(Palette.mutedInk)
            }
        }
        .padding(.horizontal, 13)
        .frame(maxWidth: .infinity, minHeight: 54, alignment: .leading)
        .background(Color.white.opacity(0.72))
        .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 13, style: .continuous)
                .stroke(Palette.line.opacity(0.8), lineWidth: 1)
        }
    }
}

private struct ManualFormattingNotice: View {
    let manual: ManualFormatting

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "paintbrush.pointed")
                .foregroundStyle(Palette.amber)
            Text("发现 \(manual.paragraphCount) 个手工设置段落、\(manual.runCount) 处手工字符格式。它们不是可复用样式，因此不会出现在下方列表中；应用时会清理目标文档的手工视觉格式。")
                .font(.system(size: 11.5))
                .foregroundStyle(Palette.ink.opacity(0.84))
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(12)
        .background(Palette.amberWash)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

private struct FormatFilterBar: View {
    @Binding var filter: FormatFilter
    let formats: [UsedFormat]

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(FormatFilter.allCases) { item in
                    Button {
                        filter = item
                    } label: {
                        Text("\(item.rawValue)  \(formats.filter(item.includes).count)")
                            .font(.system(size: 11.5, weight: .semibold))
                            .foregroundStyle(filter == item ? .white : Palette.mutedInk)
                            .padding(.horizontal, 12)
                            .frame(height: 31)
                            .background(filter == item ? Palette.green : Color.white.opacity(0.66))
                            .clipShape(Capsule())
                            .overlay {
                                if filter != item {
                                    Capsule().stroke(Palette.line, lineWidth: 1)
                                }
                            }
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 14)
        }
    }
}

private struct FormatCard: View {
    let format: UsedFormat
    let isSelected: Bool
    let action: () -> Void

    private var previewFont: Font {
        let size = min(max(format.sizePt ?? 14, 11), 25)
        let name = format.fontEastAsia ?? format.fontLatin
        return name.map { .custom($0, size: size) } ?? .system(size: size)
    }

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 11) {
                HStack {
                    Text(format.name)
                        .font(.system(size: 13, weight: .bold))
                        .lineLimit(1)
                    Spacer()
                    Text(format.inferred == true
                         ? (format.inferenceLabel ?? "智能补全")
                         : "用过 \(format.usageCount) 次")
                        .font(.system(size: 9.5, weight: .semibold))
                        .foregroundStyle(Palette.green)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 4)
                        .background(Palette.mint)
                        .clipShape(Capsule())
                }
                Text(format.sample)
                    .font(previewFont)
                    .fontWeight(format.bold == true ? .bold : .regular)
                    .italic(format.italic == true)
                    .foregroundStyle(format.colorHex.map(Color.init(hex:)) ?? Palette.ink)
                    .lineLimit(2)
                    .frame(maxWidth: .infinity, minHeight: 45, alignment: alignment(format.alignment))
                    .padding(.horizontal, 10)
                    .background((format.tableFillHex.map(Color.init(hex:)) ?? Palette.paper).opacity(0.7))
                    .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
                HStack(spacing: 6) {
                    TypeBadge(format: format)
                    if let font = format.fontEastAsia ?? format.fontLatin {
                        Text(font).lineLimit(1)
                    }
                    if let size = format.sizePt {
                        Text("\(number(size)) pt")
                    }
                }
                .font(.system(size: 10.5))
                .foregroundStyle(Palette.mutedInk)
            }
            .padding(14)
            .background(isSelected ? Palette.mint.opacity(0.55) : Palette.card)
            .clipShape(RoundedRectangle(cornerRadius: 15, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 15, style: .continuous)
                    .stroke(isSelected ? Palette.green : Palette.line, lineWidth: isSelected ? 1.7 : 1)
            }
        }
        .buttonStyle(.plain)
    }

    private func alignment(_ value: String?) -> Alignment {
        switch value {
        case "center": return .center
        case "right", "end": return .trailing
        default: return .leading
        }
    }
}

private struct TypeBadge: View {
    let format: UsedFormat

    var body: some View {
        Text(label)
            .font(.system(size: 9.5, weight: .bold))
            .foregroundStyle(Palette.green)
    }

    private var label: String {
        if format.outlineLevel != nil { return "标题" }
        switch format.type {
        case "character": return "字符"
        case "table": return "表格"
        default: return "段落"
        }
    }
}

private struct StyleInspector: View {
    let format: UsedFormat?
    let pageLayout: PageLayout

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("格式属性")
                    .font(.system(size: 16, weight: .bold))
                if let format {
                    VStack(alignment: .leading, spacing: 7) {
                        Text(format.sample)
                            .font(inspectorFont(format))
                            .fontWeight(format.bold == true ? .bold : .regular)
                            .italic(format.italic == true)
                            .foregroundStyle(format.colorHex.map(Color.init(hex:)) ?? Palette.ink)
                            .fixedSize(horizontal: false, vertical: true)
                        Text(format.name)
                            .font(.system(size: 11))
                            .foregroundStyle(Palette.mutedInk)
                    }
                    .frame(maxWidth: .infinity, minHeight: 84, alignment: .leading)
                    .padding(14)
                    .background(Color.white.opacity(0.78))
                    .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))

                    VStack(spacing: 0) {
                        PropertyRow(label: "类型", value: typeText(format))
                        PropertyRow(
                            label: "来源",
                            value: format.inferred == true
                                ? (format.inferenceLabel ?? "智能补全")
                                : "源文档实际使用 \(format.usageCount) 次"
                        )
                        PropertyRow(label: "中文字体", value: format.fontEastAsia ?? "继承主题")
                        PropertyRow(label: "西文字体", value: format.fontLatin ?? "继承主题")
                        PropertyRow(label: "字号", value: format.sizePt.map { "\(number($0)) pt" } ?? "继承")
                        PropertyRow(label: "字形", value: fontTraits(format))
                        PropertyRow(label: "颜色", value: format.colorHex.map { "#\($0)" } ?? "自动")
                        if format.type == "paragraph" {
                            PropertyRow(
                                label: "对齐",
                                value: paragraphAlignmentText(format.alignment)
                            )
                            PropertyRow(
                                label: "段前 / 段后",
                                value: paragraphSpacingText(
                                    before: format.spaceBeforePt,
                                    after: format.spaceAfterPt
                                )
                            )
                            PropertyRow(
                                label: "行距",
                                value: paragraphLineSpacingText(
                                    value: format.lineSpacing,
                                    rule: format.lineRule
                                )
                            )
                            PropertyRow(
                                label: "左 / 右缩进",
                                value: paragraphIndentSidesText(format)
                            )
                            PropertyRow(
                                label: "特殊缩进",
                                value: paragraphSpecialIndentText(format)
                            )
                            if let level = format.outlineLevel {
                                PropertyRow(label: "大纲级别", value: "\(level + 1) 级")
                            }
                            PropertyRow(
                                label: "编号",
                                value: format.numbered
                                    ? format.numberingExample.map { "是（示意：\($0)）" } ?? "是"
                                    : "否"
                            )
                        }
                        if format.type == "table" {
                            PropertyRow(label: "表格底色", value: hexText(format.tableFillHex))
                            PropertyRow(label: "强调色", value: hexText(format.tableAccentHex))
                        }
                    }
                    .background(Color.white.opacity(0.55))
                    .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
                } else {
                    Text("选择一张格式卡片查看详细属性。")
                        .font(.system(size: 12))
                        .foregroundStyle(Palette.mutedInk)
                }

                Divider().overlay(Palette.line)
                PageLayoutCard(layout: pageLayout)
            }
            .padding(20)
        }
    }

    private func inspectorFont(_ format: UsedFormat) -> Font {
        let size = min(max(format.sizePt ?? 14, 11), 24)
        if let name = format.fontEastAsia ?? format.fontLatin {
            return .custom(name, size: size)
        }
        return .system(size: size)
    }

    private func typeText(_ format: UsedFormat) -> String {
        if let level = format.outlineLevel { return "\(level + 1) 级标题" }
        switch format.type {
        case "character": return "字符样式"
        case "table": return "表格样式"
        default: return "段落样式"
        }
    }

    private func fontTraits(_ format: UsedFormat) -> String {
        var traits: [String] = []
        if format.bold == true { traits.append("粗体") }
        if format.italic == true { traits.append("斜体") }
        return traits.isEmpty ? "常规" : traits.joined(separator: "、")
    }

    private func hexText(_ value: String?) -> String {
        value.map { "#\($0)" } ?? "—"
    }
}

private struct PropertyRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 9) {
            Text(label)
                .foregroundStyle(Palette.mutedInk)
            Spacer(minLength: 6)
            Text(value)
                .foregroundStyle(Palette.ink)
                .multilineTextAlignment(.trailing)
                .lineLimit(2)
        }
        .font(.system(size: 11))
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .overlay(alignment: .bottom) {
            Rectangle().fill(Palette.line.opacity(0.65)).frame(height: 1)
        }
    }
}

private struct PageLayoutCard: View {
    let layout: PageLayout

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("页面设置")
                    .font(.system(size: 14, weight: .bold))
                Spacer()
                Text(layout.orientation == "landscape" ? "横向" : "纵向")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(Palette.green)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Palette.mint)
                    .clipShape(Capsule())
            }
            HStack(spacing: 14) {
                ZStack {
                    Rectangle()
                        .fill(Color.white)
                        .shadow(color: Palette.ink.opacity(0.12), radius: 4, y: 2)
                    RoundedRectangle(cornerRadius: 1)
                        .stroke(Palette.line, lineWidth: 1)
                        .padding(7)
                }
                .aspectRatio(pageAspect, contentMode: .fit)
                .frame(width: layout.orientation == "landscape" ? 74 : 52)
                VStack(alignment: .leading, spacing: 5) {
                    Text(pageSize)
                    Text("上 / 下：\(cm(layout.marginTopCM)) / \(cm(layout.marginBottomCM))")
                    Text("左 / 右：\(cm(layout.marginLeftCM)) / \(cm(layout.marginRightCM))")
                }
                .font(.system(size: 10.5))
                .foregroundStyle(Palette.mutedInk)
            }
        }
    }

    private var pageAspect: CGFloat {
        guard let width = layout.widthCM, let height = layout.heightCM, height > 0 else {
            return 0.707
        }
        return CGFloat(width / height)
    }

    private var pageSize: String {
        guard let width = layout.widthCM, let height = layout.heightCM else { return "使用文档默认页面" }
        return "\(number(width)) × \(number(height)) cm"
    }

    private func cm(_ value: Double?) -> String {
        value.map { "\(number($0)) cm" } ?? "—"
    }
}

// MARK: - Step 3

private struct ApplyStepView: View {
    @ObservedObject var model: WordFormatLibraryModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                HStack {
                    VStack(alignment: .leading, spacing: 5) {
                        Text("最后，选择要修改的 Word 文件")
                            .font(.system(size: 27, weight: .bold, design: .rounded))
                        Text("原文件不会被覆盖；处理结果会另存为一个新文件。")
                            .font(.system(size: 13))
                            .foregroundStyle(Palette.mutedInk)
                    }
                    Spacer()
                    Button {
                        model.currentStep = 2
                    } label: {
                        Label("返回检查格式", systemImage: "arrow.left")
                    }
                    .buttonStyle(SecondaryButtonStyle())
                }

                if let pack = model.selectedPack {
                    HStack(spacing: 14) {
                        Image(systemName: "text.book.closed.fill")
                            .font(.system(size: 22))
                            .foregroundStyle(Palette.green)
                            .frame(width: 48, height: 48)
                            .background(Palette.mint)
                            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                        VStack(alignment: .leading, spacing: 3) {
                            Text("将应用：\(pack.name)")
                                .font(.system(size: 15, weight: .bold))
                            Text("包含 \(pack.formatCountSummary) · \(pack.sourceFileName ?? "来源内容已脱敏")")
                                .font(.system(size: 11.5))
                                .foregroundStyle(Palette.mutedInk)
                        }
                        Spacer()
                        Button("更换") { model.currentStep = 1 }
                            .buttonStyle(SecondaryButtonStyle())
                    }
                    .padding(16)
                    .background(Color.white.opacity(0.62))
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .overlay {
                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .stroke(Palette.line, lineWidth: 1)
                    }
                }

                HStack(alignment: .top, spacing: 20) {
                    TargetDocumentCard(model: model)
                        .frame(maxWidth: .infinity, minHeight: 255)
                    ApplyOptionsCard(model: model)
                        .frame(width: 355)
                }

                if let report = model.applyReport {
                    SuccessCard(report: report, restart: {
                        model.targetURL = nil
                        model.outputURL = nil
                        model.applyReport = nil
                        model.demoteHeadings = false
                    })
                }
            }
            .padding(28)
        }
    }
}

private struct TargetDocumentCard: View {
    @ObservedObject var model: WordFormatLibraryModel

    var body: some View {
        AppCard {
            VStack(spacing: 15) {
                ZStack {
                    Circle().fill(Palette.mint)
                    Image(systemName: model.targetURL == nil ? "doc.badge.arrow.up" : "doc.fill")
                        .font(.system(size: 31, weight: .medium))
                        .foregroundStyle(Palette.green)
                }
                .frame(width: 66, height: 66)

                if let targetURL = model.targetURL {
                    Text(targetURL.lastPathComponent)
                        .font(.system(size: 16, weight: .bold))
                        .lineLimit(2)
                        .multilineTextAlignment(.center)
                    Text(targetURL.deletingLastPathComponent().path)
                        .font(.system(size: 10.5))
                        .foregroundStyle(Palette.mutedInk)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    Button("更换目标文件") { chooseTargetFile() }
                        .buttonStyle(SecondaryButtonStyle())
                } else {
                    Text("选择要修改格式的 Word 文件")
                        .font(.system(size: 17, weight: .bold))
                    Text("支持 DOCX 与保留宏的 DOCM")
                        .font(.system(size: 12))
                        .foregroundStyle(Palette.mutedInk)
                    Button {
                        chooseTargetFile()
                    } label: {
                        Label("选择目标文件", systemImage: "folder")
                    }
                    .buttonStyle(PrimaryButtonStyle())
                }
            }
            .frame(maxWidth: .infinity, minHeight: 215)
        }
    }

    private func chooseTargetFile() {
        let panel = NSOpenPanel()
        panel.title = "选择要修改格式的 Word 文档"
        panel.prompt = "选择目标文件"
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = ["docx", "docm"].compactMap {
            UTType(filenameExtension: $0)
        }
        guard panel.runModal() == .OK, let url = panel.url else { return }
        model.chooseTarget(url)
    }
}

private struct ApplyOptionsCard: View {
    @ObservedObject var model: WordFormatLibraryModel

    var body: some View {
        AppCard {
            VStack(alignment: .leading, spacing: 17) {
                Text("应用选项")
                    .font(.system(size: 16, weight: .bold))
                Toggle(isOn: $model.applySourcePageLayout) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("同步格式源的页面设置")
                            .font(.system(size: 13, weight: .semibold))
                        Text("包含纸张、方向与页边距")
                            .font(.system(size: 10.5))
                            .foregroundStyle(Palette.mutedInk)
                    }
                }
                .toggleStyle(.switch)
                .tint(Palette.green)

                Divider().overlay(Palette.line)
                Toggle(isOn: $model.demoteHeadings) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("所有标题向下调整一级")
                            .font(.system(size: 13, weight: .semibold))
                        Text("标题一→标题二，标题八→标题九")
                            .font(.system(size: 10.5))
                            .foregroundStyle(Palette.mutedInk)
                    }
                }
                .toggleStyle(.switch)
                .tint(Palette.green)
                Text("标题九受 Word 上限保持不变；若再次对已处理文件勾选，会再向下一级。")
                    .font(.system(size: 10.5))
                    .foregroundStyle(Palette.mutedInk)
                    .fixedSize(horizontal: false, vertical: true)

                Divider().overlay(Palette.line)
                VStack(alignment: .leading, spacing: 8) {
                    OptionLine(icon: "checkmark.circle", text: "保留正文、图片、表格与页眉页脚内容")
                    OptionLine(icon: "eraser", text: "清理旧样式与手工视觉格式")
                    if (model.selectedPack?.inferredStyleCount ?? 0) > 0 {
                        OptionLine(
                            icon: "wand.and.stars",
                            text: "用标题一至标题三的设计逻辑补全标题四、标题五"
                        )
                    }
                    OptionLine(icon: "doc.on.doc", text: "始终另存为新文件")
                    if model.selectedPack?.usedFormats.contains(where: {
                        $0.type == "paragraph" && $0.outlineLevel != nil && $0.numbered
                    }) == true {
                        OptionLine(
                            icon: "list.number",
                            text: "同步标题多级编号，例如 1、1.1、1.1.1"
                        )
                        OptionLine(
                            icon: "checkmark.circle",
                            text: "自动清理与层级计数一致的手工序号，例如“第三章”“3.1”"
                        )
                    }
                    if model.selectedPack?.usedFormats.contains(where: { $0.type == "table" }) == false {
                        OptionLine(
                            icon: "tablecells",
                            text: "格式库没有表格样式：保留表格外观，并用稳定样式取消单元格的两字符首行缩进"
                        )
                    }
                }
                Spacer(minLength: 2)
                Button {
                    chooseDestinationAndApply()
                } label: {
                    Label(model.outputURL == nil ? "选择保存位置并应用" : "重新生成", systemImage: "wand.and.stars")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(model.targetURL == nil)
                .opacity(model.targetURL == nil ? 0.48 : 1)
            }
            .frame(minHeight: 215)
        }
    }

    private func chooseDestinationAndApply() {
        guard let targetURL = model.targetURL else { return }
        let panel = NSSavePanel()
        panel.title = "另存处理后的 Word 文档"
        panel.prompt = "应用并保存"
        panel.canCreateDirectories = true
        panel.allowedContentTypes = [UTType(filenameExtension: targetURL.pathExtension)].compactMap { $0 }
        panel.nameFieldStringValue = "\(targetURL.deletingPathExtension().lastPathComponent)-已套用格式.\(targetURL.pathExtension)"
        panel.directoryURL = targetURL.deletingLastPathComponent()
        guard panel.runModal() == .OK, let destination = panel.url else { return }
        Task { await model.applyPack(savingTo: destination) }
    }
}

private struct OptionLine: View {
    let icon: String
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(Palette.green)
                .frame(width: 16)
            Text(text)
                .font(.system(size: 11.5))
                .foregroundStyle(Palette.mutedInk)
        }
    }
}

private struct SuccessCard: View {
    let report: ApplyReport
    let restart: () -> Void
    @State private var didCopyReport = false

    private let metricColumns = Array(
        repeating: GridItem(.flexible(), spacing: 10),
        count: 4
    )

    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            HStack(spacing: 15) {
                ZStack {
                    Circle().fill(Palette.success)
                    Image(systemName: "checkmark")
                        .font(.system(size: 19, weight: .bold))
                        .foregroundStyle(.white)
                }
                .frame(width: 44, height: 44)
                VStack(alignment: .leading, spacing: 3) {
                    Text("格式已经应用完成")
                        .font(.system(size: 15, weight: .bold))
                    Text(report.outputURL.path)
                        .font(.system(size: 10.5))
                        .foregroundStyle(Palette.mutedInk)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
                Spacer()
                Button {
                    copyReport()
                } label: {
                    Label(
                        didCopyReport ? "已复制报告" : "复制处理报告",
                        systemImage: didCopyReport ? "checkmark" : "doc.on.doc"
                    )
                }
                .buttonStyle(SecondaryButtonStyle())
                Button("在 Finder 中显示") {
                    NSWorkspace.shared.activateFileViewerSelecting([report.outputURL])
                }
                .buttonStyle(SecondaryButtonStyle())
                Button("打开结果") {
                    NSWorkspace.shared.open(report.outputURL)
                }
                .buttonStyle(PrimaryButtonStyle(compact: true))
            }

            LazyVGrid(columns: metricColumns, spacing: 10) {
                SuccessMetric(
                    label: "已处理段落",
                    value: report.stats.paragraphsSeen,
                    icon: "text.alignleft"
                )
                SuccessMetric(
                    label: "样式重映射",
                    value: report.stats.stylesRemapped,
                    icon: "arrow.triangle.2.circlepath"
                )
                SuccessMetric(
                    label: "清理旧格式属性",
                    value: report.stats.directPropertiesRemoved,
                    icon: "eraser"
                )
                SuccessMetric(
                    label: "应用标题编号",
                    value: report.stats.headingNumbersApplied,
                    icon: "list.number"
                )
                SuccessMetric(
                    label: "保留正文列表",
                    value: report.stats.bodyListParagraphsPreserved,
                    icon: "list.bullet"
                )
                SuccessMetric(
                    label: "清理表格缩进",
                    value: report.stats.tableParagraphIndentsCleared,
                    icon: "tablecells"
                )
                SuccessMetric(
                    label: report.stats.tableFormatsPreserved > 0
                        ? "保留表格外观"
                        : "已处理表格",
                    value: report.stats.tableFormatsPreserved > 0
                        ? report.stats.tableFormatsPreserved
                        : report.stats.tablesSeen,
                    icon: "rectangle.grid.2x2"
                )
            }

            if !report.stats.uniqueWarnings.isEmpty {
                VStack(alignment: .leading, spacing: 7) {
                    Label("需要留意", systemImage: "exclamationmark.triangle.fill")
                        .font(.system(size: 12.5, weight: .bold))
                        .foregroundStyle(Palette.amber)
                    ForEach(report.stats.uniqueWarnings, id: \.self) { warning in
                        HStack(alignment: .top, spacing: 7) {
                            Circle()
                                .fill(Palette.amber)
                                .frame(width: 4, height: 4)
                                .padding(.top, 6)
                            Text(warning)
                                .font(.system(size: 11.5))
                                .foregroundStyle(Palette.ink)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Palette.amberWash.opacity(0.8))
                .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
            }

            HStack {
                Label(
                    report.stats.uniqueWarnings.isEmpty
                        ? "处理统计已验证，建议打开结果做最终审阅。"
                        : "文档已生成，请结合上述提示完成最终审阅。",
                    systemImage: report.stats.uniqueWarnings.isEmpty
                        ? "checkmark.shield"
                        : "doc.text.magnifyingglass"
                )
                .font(.system(size: 11.5, weight: .medium))
                .foregroundStyle(Palette.mutedInk)
                Spacer()
                Button("处理下一份") { restart() }
                    .buttonStyle(.plain)
                    .font(.system(size: 11.5, weight: .semibold))
                    .foregroundStyle(Palette.green)
            }
        }
        .padding(17)
        .background(Palette.mint.opacity(0.74))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(Palette.success.opacity(0.4), lineWidth: 1)
        }
    }

    private func copyReport() {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(report.plainText, forType: .string)
        didCopyReport = true
        Task {
            try? await Task.sleep(nanoseconds: 1_800_000_000)
            didCopyReport = false
        }
    }
}

private struct SuccessMetric: View {
    let label: String
    let value: Int
    let icon: String

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(Palette.green)
                .frame(width: 25, height: 25)
                .background(Color.white.opacity(0.75))
                .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
            VStack(alignment: .leading, spacing: 1) {
                Text("\(value)")
                    .font(.system(size: 17, weight: .bold, design: .rounded))
                Text(label)
                    .font(.system(size: 10.5))
                    .foregroundStyle(Palette.mutedInk)
                    .lineLimit(1)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 11)
        .frame(height: 49)
        .background(Color.white.opacity(0.55))
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }
}

private struct EmptySelectionView: View {
    let action: () -> Void

    var body: some View {
        VStack(spacing: 13) {
            Image(systemName: "archivebox")
                .font(.system(size: 34))
                .foregroundStyle(Palette.mutedInk)
            Text("还没有选择格式库")
                .font(.system(size: 18, weight: .bold))
            Button("返回导入") { action() }
                .buttonStyle(PrimaryButtonStyle())
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

private struct OperationNoticeBanner: View {
    let message: String
    let dismiss: () -> Void

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "info.circle.fill")
                .foregroundStyle(Palette.green)
            Text(message)
                .font(.system(size: 12.5, weight: .semibold))
            Spacer(minLength: 18)
            Button(action: dismiss) {
                Image(systemName: "xmark")
                    .font(.system(size: 10, weight: .bold))
                    .frame(width: 24, height: 24)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("关闭提示")
        }
        .padding(.horizontal, 14)
        .frame(maxWidth: 620, minHeight: 44)
        .background(.ultraThickMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(Palette.green.opacity(0.28), lineWidth: 1)
        }
        .shadow(color: .black.opacity(0.12), radius: 15, y: 6)
    }
}

private struct BusyOverlay: View {
    let message: String
    let canCancel: Bool
    let isCancelling: Bool
    let cancel: () -> Void

    var body: some View {
        ZStack {
            Color.black.opacity(0.16).ignoresSafeArea()
            VStack(spacing: 12) {
                ProgressView()
                    .controlSize(.large)
                    .tint(Palette.green)
                Text(message)
                    .font(.system(size: 13, weight: .semibold))
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 330)
                Text(isCancelling ? "正在等待当前写入安全结束。" : "全程在本机处理，原文件不会被覆盖。")
                    .font(.system(size: 10.5))
                    .foregroundStyle(Palette.mutedInk)
                    .multilineTextAlignment(.center)
                if canCancel || isCancelling {
                    Button(isCancelling ? "正在停止…" : "取消处理") {
                        cancel()
                    }
                    .buttonStyle(SecondaryButtonStyle())
                    .disabled(isCancelling)
                    .keyboardShortcut(.cancelAction)
                }
            }
            .padding(.horizontal, 30)
            .padding(.vertical, 22)
            .frame(minWidth: 360, minHeight: 150)
            .background(.ultraThickMaterial)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .shadow(color: .black.opacity(0.16), radius: 24, y: 10)
        }
    }
}

private func number(_ value: Double) -> String {
    if value.rounded() == value { return String(Int(value)) }
    return String(format: "%.1f", value)
}

private func paragraphNumber(_ value: Double) -> String {
    if abs(value.rounded() - value) < 0.000_001 {
        return String(Int(value.rounded()))
    }
    var rendered = String(
        format: "%.2f",
        locale: Locale(identifier: "en_US_POSIX"),
        value
    )
    while rendered.last == "0" { rendered.removeLast() }
    if rendered.last == "." { rendered.removeLast() }
    return rendered
}

#if !WORD_FORMAT_LIBRARY_TESTING
@main
struct WordFormatLibraryApp: App {
    var body: some Scene {
        WindowGroup {
            WordFormatLibraryView()
        }
        .defaultSize(width: 1180, height: 790)
        .windowStyle(.hiddenTitleBar)
        .windowToolbarStyle(.unifiedCompact)
        .commands {
            CommandGroup(replacing: .newItem) { }
        }
    }
}
#endif
