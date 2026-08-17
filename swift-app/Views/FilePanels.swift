import AppKit
import UniformTypeIdentifiers

/// 三个文件面板的唯一定义处，避免同一个对话框在多个视图里各写一份标题。
enum FilePanels {
    static func chooseSource() -> URL? {
        let panel = NSOpenPanel()
        panel.title = UIStrings.FilePicker.sourceTitle
        panel.prompt = UIStrings.FilePicker.sourcePrompt
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = contentTypes(["docx", "docm", "dotx", "dotm"])
        return panel.runModal() == .OK ? panel.url : nil
    }

    static func chooseTarget() -> URL? {
        let panel = NSOpenPanel()
        panel.title = UIStrings.FilePicker.targetTitle
        panel.prompt = UIStrings.FilePicker.targetPrompt
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = contentTypes(["docx", "docm"])
        return panel.runModal() == .OK ? panel.url : nil
    }

    static func chooseDestination(basedOn targetURL: URL) -> URL? {
        let panel = NSSavePanel()
        panel.title = UIStrings.FilePicker.saveTitle
        panel.prompt = UIStrings.FilePicker.savePrompt
        panel.canCreateDirectories = true
        panel.allowedContentTypes = contentTypes([targetURL.pathExtension])
        panel.nameFieldStringValue = targetURL.deletingPathExtension().lastPathComponent
            + UIStrings.FilePicker.outputSuffix
            + "." + targetURL.pathExtension
        panel.directoryURL = targetURL.deletingLastPathComponent()
        return panel.runModal() == .OK ? panel.url : nil
    }

    /// 从拖放数据里取出第一个文件 URL。
    static func firstFileURL(from providers: [NSItemProvider], handler: @escaping (URL) -> Void) -> Bool {
        guard let provider = providers.first else { return false }
        provider.loadDataRepresentation(forTypeIdentifier: UTType.fileURL.identifier) { data, _ in
            guard let data,
                  let url = URL(dataRepresentation: data, relativeTo: nil) else { return }
            Task { @MainActor in handler(url) }
        }
        return true
    }

    private static func contentTypes(_ extensions: [String]) -> [UTType] {
        extensions.compactMap { UTType(filenameExtension: $0) }
    }
}
