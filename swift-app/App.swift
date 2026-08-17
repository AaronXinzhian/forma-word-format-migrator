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
            CommandGroup(replacing: .newItem) { }
        }
    }
}
#endif
