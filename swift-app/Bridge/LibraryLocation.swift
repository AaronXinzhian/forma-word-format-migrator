/**
 * [INPUT]: 依赖 Foundation
 * [OUTPUT]: 提供 LibraryLocation
 * [POS]: Mac 格式库路径解析与旧目录到 FormaFushi 的兼容迁移
 * [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
 */
import Foundation

/// 解析格式库目录，并把 2.6 之前留在旧目录名下的格式库迁移过来。
///
/// 产品早已更名 Forma 赋式，Windows 端一直使用 `FormaFushi`，Mac 端却停在
/// 开发期的 `WordFormatMigrator`。统一到 `FormaFushi` 时必须带迁移，
/// 否则老用户升级后会看到一个空的格式库。
enum LibraryLocation {
    static let containerName = "FormaFushi"
    static let legacyContainerName = "WordFormatMigrator"
    private static let packsFolderName = "style-packs"
    private static let migrationMarkerName = ".migrated-from-WordFormatMigrator"

    static func resolve(
        environment: [String: String] = ProcessInfo.processInfo.environment,
        fileManager: FileManager = .default
    ) -> URL {
        if let override = environment["WORD_FORMAT_LIBRARY_DIR"]?
            .trimmingCharacters(in: .whitespacesAndNewlines),
           !override.isEmpty {
            return URL(fileURLWithPath: override, isDirectory: true)
        }

        guard let applicationSupport = fileManager.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first else {
            return URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
                .appendingPathComponent(containerName, isDirectory: true)
                .appendingPathComponent(packsFolderName, isDirectory: true)
        }

        let container = applicationSupport
            .appendingPathComponent(containerName, isDirectory: true)
        let legacyContainer = applicationSupport
            .appendingPathComponent(legacyContainerName, isDirectory: true)

        return migrateIfNeeded(
            from: legacyContainer,
            to: container,
            fileManager: fileManager
        ).appendingPathComponent(packsFolderName, isDirectory: true)
    }

    /// 迁移成功或无需迁移时返回新容器；迁移失败时返回旧容器，
    /// 宁可保留旧目录名，也不能让用户的格式库凭空消失。
    static func migrateIfNeeded(
        from legacyContainer: URL,
        to container: URL,
        fileManager: FileManager
    ) -> URL {
        guard !directoryExists(container, fileManager: fileManager),
              directoryExists(legacyContainer, fileManager: fileManager) else {
            return container
        }

        do {
            try fileManager.createDirectory(
                at: container.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            try fileManager.moveItem(at: legacyContainer, to: container)
        } catch {
            return legacyContainer
        }

        let marker = container.appendingPathComponent(migrationMarkerName)
        let note = """
        本目录由 \(legacyContainer.path) 迁移而来。
        迁移时间：\(ISO8601DateFormatter().string(from: Date()))
        """
        try? note.write(to: marker, atomically: true, encoding: .utf8)
        return container
    }

    private static func directoryExists(_ url: URL, fileManager: FileManager) -> Bool {
        var isDirectory: ObjCBool = false
        let exists = fileManager.fileExists(atPath: url.path, isDirectory: &isDirectory)
        return exists && isDirectory.boolValue
    }
}
