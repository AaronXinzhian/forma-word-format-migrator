/**
 * [INPUT]: 依赖 AppKit, SwiftUI
 * [OUTPUT]: 提供 AppDelegate, WordFormatLibraryApp
 * [POS]: Mac 应用入口、处理中退出确认与原生文件和格式库命令菜单
 * [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
 */
import AppKit
import SwiftUI

/// 处理中关闭窗口时的二次确认。
///
/// `applicationShouldTerminateAfterLastWindowClosed` 为 true，所以关窗会走到
/// `applicationShouldTerminate`，正在处理文档时先问一句再退出。
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    func applicationShouldTerminate(
        _ sender: NSApplication
    ) -> NSApplication.TerminateReply {
        guard MainActor.assumeIsolated({ AppActivity.isBusy }) else { return .terminateNow }

        let alert = NSAlert()
        alert.alertStyle = .warning
        alert.messageText = UIStrings.App.exitBusyTitle
        alert.informativeText = UIStrings.App.exitBusyMessage
        alert.addButton(withTitle: UIStrings.App.exitBusyCancel)
        alert.addButton(withTitle: UIStrings.App.exitBusyConfirm)
        return alert.runModal() == .alertSecondButtonReturn ? .terminateNow : .terminateCancel
    }
}

#if !WORD_FORMAT_LIBRARY_TESTING
@main
struct WordFormatLibraryApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    var body: some Scene {
        WindowGroup {
            WordFormatLibraryView()
        }
        .defaultSize(width: 1180, height: 790)
        .windowStyle(.hiddenTitleBar)
        .windowToolbarStyle(.unifiedCompact)
        .commands {
            FormaCommands()
        }
    }
}
#endif

struct FormaCommands: Commands {
    @FocusedObject private var model: WordFormatLibraryModel?
    private var canChoose: Bool { model != nil && model?.isBusy != true && model?.isEditingFormat != true }

    var body: some Commands {
        CommandGroup(replacing: .newItem) {
            Button("从 Word 导入格式…") {
                if let model, let url = FilePanels.chooseSource() { Task { await model.importSource(url) } }
            }.keyboardShortcut("o").disabled(!canChoose)
            Button("导入格式方案…") {
                if let model, let url = FilePanels.choosePack() { Task { await model.importPack(url) } }
            }.keyboardShortcut("o", modifiers: [.command, .shift]).disabled(!canChoose)
        }
        CommandGroup(replacing: .saveItem) {
            Button("导出选中格式方案…") {
                if let model, let pack = model.selectedPack, let url = FilePanels.exportDestination(for: pack) {
                    Task { await model.exportPack(pack, to: url) }
                }
            }.disabled(model?.selectedPack == nil || !canChoose)
            Button("另存并应用格式…") {
                if let model, let target = model.targetURL, let destination = FilePanels.chooseDestination(basedOn: target) {
                    Task { await model.applyPack(savingTo: destination) }
                }
            }.keyboardShortcut("s", modifiers: [.command, .shift]).disabled(model?.canApplyPreflight != true || !canChoose)
        }
        CommandMenu("格式库") {
            Button("选择目标 Word 文件…") {
                if let model, let url = FilePanels.chooseTarget() { model.currentStep = 3; model.chooseTarget(url) }
            }.keyboardShortcut("t").disabled(model?.selectedPack == nil || !canChoose)
            Button("刷新格式库") {
                if let model { Task { await model.reloadLibrary() } }
            }.keyboardShortcut("r").disabled(!canChoose)
            Button("重新预检") {
                if let model { Task { await model.refreshPreflight() } }
            }.disabled(model?.targetURL == nil || !canChoose)
            Button("取消当前处理") { model?.cancelCurrentOperation() }
                .disabled(model?.canCancelBusyOperation != true)
        }
    }
}
