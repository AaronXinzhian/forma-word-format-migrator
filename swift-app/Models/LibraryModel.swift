// [INPUT]: 依赖 AppKit, Darwin, SwiftUI, UniformTypeIdentifiers
// [OUTPUT]: 提供LibraryModel 中的类型与接口
// [POS]: Mac 原生终端 - 格式库、编辑派生、目标处理与取消状态协调
// [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
import AppKit
import Darwin
import SwiftUI
import UniformTypeIdentifiers

// MARK: - Application state

@MainActor
enum AppActivity {
    static var isBusy = false
}

@MainActor
final class WordFormatLibraryModel: ObservableObject {
    @Published var packs: [PackManifest] = []
    @Published var selectedPack: PackManifest?
    @Published var selectedFormatID: String?
    @Published var currentStep = 1
    @Published var targetURL: URL?
    @Published var outputURL: URL?
    @Published var applyReport: ApplyReport?
    @Published var preflight: DocumentPreflight?
    @Published var libraryReadErrors: [LibraryReadError] = []
    @Published var applySourcePageLayout = true {
        didSet { if oldValue != applySourcePageLayout { preflight = nil } }
    }
    @Published var demoteHeadings = false {
        didSet { if oldValue != demoteHeadings { preflight = nil } }
    }
    @Published var isBusy = false {
        didSet { AppActivity.isBusy = isBusy }
    }
    @Published var busyMessage = ""
    @Published private(set) var canCancelBusyOperation = false
    @Published private(set) var isCancelling = false
    @Published var errorMessage = ""
    @Published var isShowingError = false
    @Published var libraryNotice: String?
    @Published var libraryConfirmation: String?
    @Published var operationNotice: String?
    @Published var isLibraryHighlighted = false
    @Published var isEditingFormat = false
    var toastMessage: String? {
        get { operationNotice ?? libraryConfirmation }
        set { operationNotice = newValue; libraryConfirmation = nil }
    }

    let libraryDirectory: URL
    private var activePythonOperation: PythonOperation?
    private var phaseMessageTask: Task<Void, Never>?
    private var highlightTask: Task<Void, Never>?

    init(libraryDirectory: URL = LibraryLocation.resolve(), automaticallyReload: Bool = true) {
        self.libraryDirectory = libraryDirectory
        if automaticallyReload {
            Task { [weak self] in await self?.reloadLibrary() }
        }
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
            libraryReadErrors = envelope.errors ?? []
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

    func importPack(_ url: URL) async {
        guard !isBusy else { return }
        guard url.pathExtension.lowercased() == "wfstyle" else {
            show(AppFailure.message("请选择 .wfstyle 格式方案。")); return
        }
        beginBusy("正在校验并导入格式方案…")
        defer { finishBusy() }
        do {
            try ensureLibraryDirectory()
            let envelope = try await execute(["import-pack", "--pack", url.path, "--dir", libraryDirectory.path])
            guard let pack = envelope.pack else { throw AppFailure.message("没有收到导入方案的信息。") }
            await reloadLibrary(selecting: pack.id, showProgress: false)
            operationNotice = envelope.imported == false ? "相同格式方案已在格式库中，已选中现有方案。" : "已导入「\(pack.name)」。"
        } catch { show(error) }
    }

    func exportPack(_ pack: PackManifest, to destination: URL) async {
        guard !isBusy, let packURL = pack.packURL else { return }
        guard destination.pathExtension.lowercased() == "wfstyle" else {
            show(AppFailure.message("导出文件请使用 .wfstyle 扩展名。")); return
        }
        beginBusy("正在校验并导出格式方案…")
        defer { finishBusy() }
        do {
            _ = try await execute(["export-pack", "--pack", packURL.path, "--out", destination.path, "--force"])
            operationNotice = "已导出「\(pack.name)」。可用于备份或在另一台电脑导入。"
        } catch { show(error) }
    }

    func derivePack(
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

    func selectPack(_ pack: PackManifest, advance: Bool = true, resetTarget: Bool = true) {
        let changed = selectedPack?.libraryIdentity != pack.libraryIdentity
        selectedPack = pack
        selectedFormatID = pack.usedFormats.first?.id
        if changed && resetTarget { clearTarget() }
        if advance { currentStep = 2 }
    }

    func clearTarget() {
        targetURL = nil
        outputURL = nil
        applyReport = nil
        preflight = nil
        demoteHeadings = false
    }

    func highlightLibrary() {
        highlightTask?.cancel()
        isLibraryHighlighted = true
        highlightTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 1_600_000_000)
            guard !Task.isCancelled else { return }
            self?.isLibraryHighlighted = false
        }
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
        preflight = nil
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
        preflight = nil
        Task { await refreshPreflight() }
    }

    var canApplyPreflight: Bool {
        targetURL != nil && selectedPack != nil &&
            preflight?.matches(demoteHeadings: demoteHeadings, applyPageLayout: applySourcePageLayout) == true
    }

    func refreshPreflight() async {
        guard !isBusy, let packURL = selectedPack?.packURL, let targetURL else { return }
        preflight = nil
        let demote = demoteHeadings
        let pageLayout = applySourcePageLayout
        beginBusy("正在预检目标文档与格式方案…")
        defer { finishBusy() }
        do {
            var arguments = ["preflight-pack", "--pack", packURL.path, "--target", targetURL.path]
            if demote { arguments.append("--demote-headings") }
            if !pageLayout { arguments.append("--preserve-page-layout") }
            let envelope = try await execute(arguments)
            guard let report = envelope.preflight,
                  report.matches(demoteHeadings: demote, applyPageLayout: pageLayout),
                  self.targetURL == targetURL, self.selectedPack?.packURL == packURL,
                  self.demoteHeadings == demote, self.applySourcePageLayout == pageLayout else {
                throw AppFailure.message("预检期间输入或选项发生变化，请重新预检。")
            }
            preflight = report
        } catch { show(error) }
    }

    func applyPack(savingTo destination: URL) async {
        guard !isBusy else { return }
        guard let selectedPack,
              let packURL = selectedPack.packURL,
              let targetURL else {
            show(AppFailure.message("请先选择格式库和要修改的 Word 文件。"))
            return
        }
        guard let preflight, canApplyPreflight else {
            show(AppFailure.message("请先完成当前文档和应用选项的预检。")); return
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
                "--expected-pack-sha256", preflight.inputBinding.packSHA256,
                "--expected-target-sha256", preflight.inputBinding.targetSHA256,
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
            self.preflight = nil
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
        highlightTask?.cancel()
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
