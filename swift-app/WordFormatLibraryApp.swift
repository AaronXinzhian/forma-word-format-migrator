import AppKit
import SwiftUI
import UniformTypeIdentifiers

// MARK: - Data returned by style_pack_manager.py

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
    let sourceFileName: String?
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
        case sourceFileName = "source_file_name"
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
}

private struct ManagerEnvelope: Decodable {
    let ok: Bool
    let error: String?
    let pack: PackManifest?
    let packs: [PackManifest]?
    let output: String?
    let errors: [LibraryReadError]?
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

private enum PythonBridge {
    static func run(arguments: [String]) async throws -> ManagerOutput {
        guard let scriptURL = managerScriptURL() else {
            throw AppFailure.message("应用资源不完整：找不到 style_pack_manager.py。请重新安装应用。")
        }

        let process = Process()
        if FileManager.default.isExecutableFile(atPath: "/usr/bin/python3") {
            process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            process.arguments = [scriptURL.path] + arguments
        } else {
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = ["python3", scriptURL.path] + arguments
        }
        process.currentDirectoryURL = scriptURL.deletingLastPathComponent()

        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUNBUFFERED"] = "1"
        process.environment = environment

        let standardOutput = Pipe()
        let standardError = Pipe()
        process.standardOutput = standardOutput
        process.standardError = standardError

        do {
            try process.run()
        } catch {
            throw AppFailure.message("无法启动文档处理组件：\(error.localizedDescription)")
        }

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
        let errorText = String(data: errorData, encoding: .utf8) ?? ""
        return ManagerOutput(data: data, standardError: errorText, status: status)
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

        // Development fallback: this keeps `swiftc … && ./app` useful while the
        // distributed .app always resolves the copy in Contents/Resources.
        let sourceFile = URL(fileURLWithPath: #filePath)
        candidates.append(
            sourceFile.deletingLastPathComponent()
                .deletingLastPathComponent()
                .appendingPathComponent("style_pack_manager.py")
        )
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
    @Published var applySourcePageLayout = true
    @Published var demoteHeadings = false
    @Published var isBusy = false
    @Published var busyMessage = ""
    @Published var errorMessage = ""
    @Published var isShowingError = false
    @Published var libraryNotice: String?
    @Published var libraryConfirmation: String?

    let libraryDirectory: URL

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

        Task { await reloadLibrary() }
    }

    var selectedFormat: UsedFormat? {
        guard let selectedFormatID else { return selectedPack?.usedFormats.first }
        return selectedPack?.usedFormats.first { $0.id == selectedFormatID }
    }

    func reloadLibrary(selecting preferredID: String? = nil, showProgress: Bool = true) async {
        let hadSelection = selectedPack != nil || preferredID != nil
        if showProgress {
            isBusy = true
            busyMessage = "正在读取本机格式库…"
            libraryConfirmation = nil
        }
        defer {
            if showProgress {
                isBusy = false
                busyMessage = ""
            }
        }

        do {
            try FileManager.default.createDirectory(
                at: libraryDirectory,
                withIntermediateDirectories: true
            )
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
        guard Self.isSupportedSource(sourceURL) else {
            show(AppFailure.message("请选择 .docx、.docm、.dotx 或 .dotm 格式的 Word 文件。"))
            return
        }

        isBusy = true
        busyMessage = "正在识别文档中实际使用的格式…"
        defer {
            isBusy = false
            busyMessage = ""
        }

        do {
            try FileManager.default.createDirectory(
                at: libraryDirectory,
                withIntermediateDirectories: true
            )
            let stem = Self.safeFileStem(sourceURL.deletingPathExtension().lastPathComponent)
            let packURL = libraryDirectory.appendingPathComponent(
                "\(stem)-\(UUID().uuidString.lowercased()).wfstyle"
            )
            let envelope = try await execute([
                "create-pack",
                "--source", sourceURL.path,
                "--out", packURL.path,
                "--name", sourceURL.deletingPathExtension().lastPathComponent
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

    func deletePack(_ pack: PackManifest) async {
        guard !isBusy else { return }

        let deletedIndex = packs.firstIndex(where: {
            $0.id == pack.id && $0.packPath == pack.packPath
        }) ?? 0
        let wasSelected = selectedPack.map {
            $0.id == pack.id && $0.packPath == pack.packPath
        } ?? false

        isBusy = true
        busyMessage = "正在将「\(pack.name)」移到废纸篓…"
        libraryConfirmation = nil
        defer {
            isBusy = false
            busyMessage = ""
        }

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
        demoteHeadings = false
        currentStep = 1
    }

    func beginTargetStep() {
        guard selectedPack != nil else { return }
        currentStep = 3
    }

    func chooseTarget(_ url: URL) {
        guard Self.isSupportedTarget(url) else {
            show(AppFailure.message("目标文件只支持 .docx 或 .docm。"))
            return
        }
        targetURL = url
        outputURL = nil
        demoteHeadings = false
    }

    func applyPack(savingTo destination: URL) async {
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

        isBusy = true
        busyMessage = "正在清理旧格式并应用「\(selectedPack.name)」…"
        defer {
            isBusy = false
            busyMessage = ""
        }

        do {
            var arguments = [
                "apply-pack",
                "--pack", packURL.path,
                "--target", targetURL.path,
                "--out", destination.path,
                "--force"
            ]
            if !applySourcePageLayout {
                arguments.append("--preserve-page-layout")
            }
            if demoteHeadings {
                arguments.append("--demote-headings")
            }
            let envelope = try await execute(arguments)
            outputURL = envelope.output.map { URL(fileURLWithPath: $0) } ?? destination
        } catch {
            show(error)
        }
    }

    func show(_ error: Error) {
        errorMessage = error.localizedDescription
        isShowingError = true
    }

    private func execute(_ arguments: [String]) async throws -> ManagerEnvelope {
        let result = try await PythonBridge.run(arguments: arguments)
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

    private static func isSupportedSource(_ url: URL) -> Bool {
        ["docx", "docm", "dotx", "dotm"].contains(url.pathExtension.lowercased())
    }

    private static func isSupportedTarget(_ url: URL) -> Bool {
        ["docx", "docm"].contains(url.pathExtension.lowercased())
    }

    private static func safeFileStem(_ value: String) -> String {
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_"))
        let mapped = value.unicodeScalars.map { allowed.contains($0) ? Character(String($0)) : "-" }
        let result = String(mapped).trimmingCharacters(in: CharacterSet(charactersIn: "-"))
        return result.isEmpty ? "word-format" : String(result.prefix(48))
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

            if model.isBusy {
                BusyOverlay(message: model.busyMessage)
            }
        }
        .frame(minWidth: 1080, minHeight: 720)
        .foregroundStyle(Palette.ink)
        .alert("操作没有完成", isPresented: $model.isShowingError) {
            Button("好") { model.isShowingError = false }
        } message: {
            Text(model.errorMessage)
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
                .disabled(item.0 > 1 && model.selectedPack == nil)

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
                        ExplanationRow(number: "03", text: "以后直接选择格式库，无需再次上传样板文档")
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
                        Text((pack.inferredStyleCount ?? 0) > 0
                             ? "实际 \(pack.usedStyleCount) 种 · 智能补全 \(pack.inferredStyleCount ?? 0) 种 · \(dateText(pack.createdAt))"
                             : "实际使用 \(pack.usedStyleCount) 种格式 · \(dateText(pack.createdAt))")
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

private struct FormatPreviewStepView: View {
    @ObservedObject var model: WordFormatLibraryModel
    @State private var filter: FormatFilter = .all

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
                        Text((pack.inferredStyleCount ?? 0) > 0
                             ? "展示实际使用格式，以及按标题层级逻辑智能补全的 \(pack.inferredStyleCount ?? 0) 种格式；另有 \(pack.hiddenStyleCount ?? 0) 个未使用样式已隐藏"
                             : "只展示实际使用格式；另有 \(pack.hiddenStyleCount ?? 0) 个未使用样式已隐藏")
                            .font(.system(size: 12.5))
                            .foregroundStyle(Palette.mutedInk)
                    }
                    Spacer()
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
                value: (pack.inferredStyleCount ?? 0) > 0
                    ? "\(pack.usedStyleCount) + \(pack.inferredStyleCount ?? 0)"
                    : "\(pack.usedStyleCount)",
                label: (pack.inferredStyleCount ?? 0) > 0 ? "实际 + 补全" : "实际使用",
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
                            PropertyRow(label: "对齐", value: alignmentText(format.alignment))
                            PropertyRow(label: "段前 / 段后", value: spacingText(format))
                            PropertyRow(label: "行距", value: lineSpacingText(format))
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

    private func alignmentText(_ alignment: String?) -> String {
        switch alignment {
        case "center": return "居中"
        case "right", "end": return "右对齐"
        case "both", "distribute": return "两端对齐"
        case "left", "start": return "左对齐"
        default: return "继承"
        }
    }

    private func spacingText(_ format: UsedFormat) -> String {
        let before = format.spaceBeforePt.map(number) ?? "—"
        let after = format.spaceAfterPt.map(number) ?? "—"
        return "\(before) / \(after) pt"
    }

    private func lineSpacingText(_ format: UsedFormat) -> String {
        guard let value = format.lineSpacing else { return "继承" }
        if format.lineRule == nil || format.lineRule == "auto" {
            return "\(number(value)) 倍"
        }
        return "\(number(value)) pt"
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
                            Text((pack.inferredStyleCount ?? 0) > 0
                                 ? "包含 \(pack.usedStyleCount) 种实际格式 + \(pack.inferredStyleCount ?? 0) 种智能补全标题 · \(pack.sourceFileName ?? "来源内容已脱敏")"
                                 : "包含 \(pack.usedStyleCount) 种实际使用格式 · \(pack.sourceFileName ?? "来源内容已脱敏")")
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

                if let outputURL = model.outputURL {
                    SuccessCard(url: outputURL, restart: {
                        model.targetURL = nil
                        model.outputURL = nil
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
                    Text("上传要修改格式的 Word 文件")
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
    let url: URL
    let restart: () -> Void

    var body: some View {
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
                Text(url.path)
                    .font(.system(size: 10.5))
                    .foregroundStyle(Palette.mutedInk)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
            Spacer()
            Button("在 Finder 中显示") {
                NSWorkspace.shared.activateFileViewerSelecting([url])
            }
            .buttonStyle(SecondaryButtonStyle())
            Button("打开结果") {
                NSWorkspace.shared.open(url)
            }
            .buttonStyle(PrimaryButtonStyle(compact: true))
            Button("处理下一份") { restart() }
                .buttonStyle(.plain)
                .font(.system(size: 11.5, weight: .semibold))
                .foregroundStyle(Palette.green)
        }
        .padding(17)
        .background(Palette.mint.opacity(0.74))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(Palette.success.opacity(0.4), lineWidth: 1)
        }
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

private struct BusyOverlay: View {
    let message: String

    var body: some View {
        ZStack {
            Color.black.opacity(0.16).ignoresSafeArea()
            VStack(spacing: 13) {
                ProgressView()
                    .controlSize(.large)
                    .tint(Palette.green)
                Text(message)
                    .font(.system(size: 13, weight: .semibold))
                    .multilineTextAlignment(.center)
            }
            .padding(.horizontal, 30)
            .frame(minWidth: 260, minHeight: 116)
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
