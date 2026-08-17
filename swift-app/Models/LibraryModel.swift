import Foundation

/// 供 AppDelegate 在退出前查询的处理状态。
///
/// SwiftUI 的 `App` 场景拿不到 `NSApplicationDelegate` 的上下文，
/// 用一个主线程隔离的静态标志把两者接起来，比在场景里到处传模型更简单。
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
    @Published var outputWarnings: [String] = []
    @Published var applySourcePageLayout = true
    @Published var demoteHeadings = false
    @Published var busyMessage = ""
    @Published var errorMessage = ""
    @Published var isShowingError = false
    @Published var libraryNotice: String?
    @Published var toastMessage: String?
    @Published var isLibraryHighlighted = false

    @Published var isBusy = false {
        didSet { AppActivity.isBusy = isBusy }
    }

    let libraryDirectory: URL
    private var highlightTask: Task<Void, Never>?

    init(libraryDirectory: URL = LibraryLocation.resolve()) {
        self.libraryDirectory = libraryDirectory
        Task { await reloadLibrary() }
    }

    var selectedFormat: UsedFormat? {
        guard let selectedFormatID else { return selectedPack?.usedFormats.first }
        return selectedPack?.usedFormats.first { $0.id == selectedFormatID }
    }

    // MARK: - 格式库

    func reloadLibrary(selecting preferredID: String? = nil, showProgress: Bool = true) async {
        let hadSelection = selectedPack != nil || preferredID != nil
        if showProgress {
            isBusy = true
            busyMessage = UIStrings.Busy.loadingLibrary
            toastMessage = nil
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
                libraryNotice = UIStrings.Sidebar.readErrorNotice(count: "\(errors.count)")
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
            show(AppFailure.message(UIStrings.Errors.unsupportedSource))
            return
        }

        isBusy = true
        busyMessage = UIStrings.Busy.importing
        toastMessage = nil
        defer {
            isBusy = false
            busyMessage = ""
        }

        do {
            try FileManager.default.createDirectory(
                at: libraryDirectory,
                withIntermediateDirectories: true
            )
            // 输出文件名由引擎决定，两端不再各自拼接命名规则。
            let envelope = try await execute([
                "create-pack",
                "--source", sourceURL.path,
                "--dir", libraryDirectory.path,
                "--name", sourceURL.deletingPathExtension().lastPathComponent
            ])
            guard let pack = envelope.pack else {
                throw AppFailure.message(UIStrings.Errors.packMissingInfo)
            }
            await reloadLibrary(selecting: pack.id, showProgress: false)
            selectPack(packs.first { $0.id == pack.id } ?? pack)
            toastMessage = UIStrings.ImportStep.savedToast(name: pack.name)
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
        busyMessage = UIStrings.Deletion.busy(name: pack.name)
        toastMessage = nil
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
                // 落点与 Windows 一致：还有其他格式包就顶上并停在预览页，
                // 全删光了才退回导入引导。删掉的是格式包不是目标文档，
                // 所以已选的目标文件保留，不让用户重挑一遍。
                selectedPack = nil
                selectedFormatID = nil
                if let nextIndex = PackDeletionPolicy.fallbackIndex(
                    afterDeleting: deletedIndex,
                    remainingCount: packs.count
                ) {
                    selectPack(packs[nextIndex], resetTarget: false)
                } else {
                    clearSelection()
                }
            }
            await reloadLibrary(showProgress: false)
            toastMessage = UIStrings.Deletion.done(name: pack.name)
        } catch {
            show(error)
        }
    }

    // MARK: - 选择与导航

    /// 与 Windows 的 SelectPack 参数一一对应：只有真的换了格式包才清空目标文件，
    /// 重复点击侧边栏里已选中的那一项不应该让用户重新挑一遍文档。
    func selectPack(_ pack: PackManifest, advance: Bool = true, resetTarget: Bool = true) {
        let changed = selectedPack?.libraryIdentity != pack.libraryIdentity
        selectedPack = pack
        selectedFormatID = pack.usedFormats.first?.id
        if changed && resetTarget { clearTarget() }
        if advance { currentStep = 2 }
    }

    func beginTargetStep() {
        guard selectedPack != nil else { return }
        currentStep = 3
    }

    /// 「换一套格式」在两端的统一行为：把注意力引到常驻格式库，而不是弹文件对话框。
    func highlightLibrary() {
        highlightTask?.cancel()
        isLibraryHighlighted = true
        highlightTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 1_600_000_000)
            guard !Task.isCancelled else { return }
            self?.isLibraryHighlighted = false
        }
    }

    func chooseTarget(_ url: URL) {
        guard Self.isSupportedTarget(url) else {
            show(AppFailure.message(UIStrings.Errors.unsupportedTarget))
            return
        }
        targetURL = url
        outputURL = nil
        outputWarnings = []
        demoteHeadings = false
    }

    func clearTarget() {
        targetURL = nil
        outputURL = nil
        outputWarnings = []
        demoteHeadings = false
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
        clearTarget()
        currentStep = 1
    }

    // MARK: - 应用

    func applyPack(savingTo destination: URL) async {
        guard let selectedPack,
              let packURL = selectedPack.packURL,
              let targetURL else {
            show(AppFailure.message(UIStrings.Errors.missingSelection))
            return
        }
        guard destination.pathExtension.lowercased() == targetURL.pathExtension.lowercased() else {
            show(AppFailure.message(UIStrings.Errors.extensionMismatch))
            return
        }
        guard destination.standardizedFileURL != targetURL.standardizedFileURL else {
            show(AppFailure.message(UIStrings.Errors.sameAsTarget))
            return
        }

        isBusy = true
        busyMessage = UIStrings.Busy.applying(name: selectedPack.name)
        toastMessage = nil
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
            outputWarnings = Self.dedupedWarnings(envelope.stats?.warnings)
        } catch {
            show(error)
        }
    }

    func show(_ error: Error) {
        errorMessage = error.localizedDescription
        isShowingError = true
    }

    // MARK: - 进程调用

    private func execute(_ arguments: [String]) async throws -> ManagerEnvelope {
        let result = try await PythonBridge.run(arguments: arguments)
        guard !result.data.isEmpty else {
            let detail = result.standardError.trimmingCharacters(in: .whitespacesAndNewlines)
            throw AppFailure.message(
                detail.isEmpty
                    ? UIStrings.Errors.emptyResult
                    : UIStrings.Errors.transferFailedDetail(detail: detail)
            )
        }

        let envelope: ManagerEnvelope
        do {
            envelope = try JSONDecoder().decode(ManagerEnvelope.self, from: result.data)
        } catch {
            let detail = result.standardError.trimmingCharacters(in: .whitespacesAndNewlines)
            throw AppFailure.message(
                detail.isEmpty
                    ? UIStrings.Errors.unreadableResult
                    : UIStrings.Errors.unreadableResultDetail(detail: detail)
            )
        }
        guard envelope.ok else {
            throw AppFailure.message(envelope.error ?? UIStrings.Errors.transferFailed)
        }
        if result.status != 0 {
            throw AppFailure.message(envelope.error ?? UIStrings.Errors.managerExit)
        }
        return envelope
    }

    static func dedupedWarnings(_ warnings: [String]?) -> [String] {
        var seen: Set<String> = []
        return (warnings ?? []).compactMap { warning in
            let trimmed = warning.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty, seen.insert(trimmed).inserted else { return nil }
            return trimmed
        }
    }

    private static func isSupportedSource(_ url: URL) -> Bool {
        ["docx", "docm", "dotx", "dotm"].contains(url.pathExtension.lowercased())
    }

    private static func isSupportedTarget(_ url: URL) -> Bool {
        ["docx", "docm"].contains(url.pathExtension.lowercased())
    }
}
