/**
 * [INPUT]: 依赖 AppKit, UniformTypeIdentifiers
 * [OUTPUT]: 提供 FilePanels
 * [POS]: Word 与格式方案导入导出文件面板、另存输出及拖放路径解析
 * [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
 */
import AppKit
import UniformTypeIdentifiers

/// 三个文件面板的唯一定义处，避免同一个对话框在多个视图里各写一份标题。
enum FilePanels {
    static func choosePack() -> URL? {
        let panel = NSOpenPanel()
        panel.title = "导入格式方案"
        panel.prompt = "导入"
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = contentTypes(["wfstyle"])
        return panel.runModal() == .OK ? panel.url : nil
    }

    static func exportDestination(for pack: PackManifest) -> URL? {
        let panel = NSSavePanel()
        panel.title = "导出格式方案用于备份或分享"
        panel.prompt = "导出"
        panel.allowedContentTypes = contentTypes(["wfstyle"])
        panel.canCreateDirectories = true
        let safeName = pack.name.replacingOccurrences(of: "/", with: "-").replacingOccurrences(of: ":", with: "-")
        panel.nameFieldStringValue = safeName + ".wfstyle"
        return panel.runModal() == .OK ? panel.url : nil
    }
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
