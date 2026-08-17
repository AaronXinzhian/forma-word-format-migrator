import Foundation

// 2.6 把 macOS 的格式库目录从 WordFormatMigrator 改名成 FormaFushi。
// 改名一旦出错就是老用户的格式库整个消失，所以这里逐条钉住迁移行为。

private enum LocationTestFailure: LocalizedError {
    case failed(String)

    var errorDescription: String? {
        switch self {
        case .failed(let message): return message
        }
    }
}

@main
struct LibraryLocationTests {
    static func main() throws {
        let fileManager = FileManager.default
        let testRoot = fileManager.temporaryDirectory.appendingPathComponent(
            "library-location-tests-\(UUID().uuidString)",
            isDirectory: true
        )
        try fileManager.createDirectory(at: testRoot, withIntermediateDirectories: true)
        defer { try? fileManager.removeItem(at: testRoot) }

        try checkEnvironmentOverrideWins(fileManager: fileManager)
        try checkLegacyLibraryIsMoved(under: testRoot, fileManager: fileManager)
        try checkNewContainerIsLeftAlone(under: testRoot, fileManager: fileManager)
        try checkFreshInstallNeedsNoMigration(under: testRoot, fileManager: fileManager)

        print("LibraryLocationTests: 8 checks passed")
    }

    /// 打包脚本与冒烟工具都靠这个变量指向临时格式库。
    private static func checkEnvironmentOverrideWins(fileManager: FileManager) throws {
        let resolved = LibraryLocation.resolve(
            environment: ["WORD_FORMAT_LIBRARY_DIR": "/tmp/custom-library"],
            fileManager: fileManager
        )
        try require(resolved.path == "/tmp/custom-library", "环境变量指定的目录应原样返回")

        let blank = LibraryLocation.resolve(
            environment: ["WORD_FORMAT_LIBRARY_DIR": "   "],
            fileManager: fileManager
        )
        try require(
            blank.lastPathComponent == "style-packs",
            "空白的环境变量应被忽略，回到默认目录"
        )
    }

    private static func checkLegacyLibraryIsMoved(
        under testRoot: URL,
        fileManager: FileManager
    ) throws {
        let support = testRoot.appendingPathComponent("legacy-move", isDirectory: true)
        let legacy = support.appendingPathComponent(
            LibraryLocation.legacyContainerName,
            isDirectory: true
        )
        let container = support.appendingPathComponent(
            LibraryLocation.containerName,
            isDirectory: true
        )
        let packs = legacy.appendingPathComponent("style-packs", isDirectory: true)
        try fileManager.createDirectory(at: packs, withIntermediateDirectories: true)
        try Data("pack".utf8).write(to: packs.appendingPathComponent("kept.wfstyle"))

        let resolved = LibraryLocation.migrateIfNeeded(
            from: legacy,
            to: container,
            fileManager: fileManager
        )
        try require(resolved.path == container.path, "迁移后应改用新目录名")
        try require(
            fileManager.fileExists(
                atPath: container.appendingPathComponent("style-packs/kept.wfstyle").path
            ),
            "旧目录里的格式包应原样出现在新目录"
        )
        try require(
            !fileManager.fileExists(atPath: legacy.path),
            "迁移完成后旧目录不应残留"
        )
        try require(
            fileManager.fileExists(
                atPath: container.appendingPathComponent(
                    ".migrated-from-WordFormatMigrator"
                ).path
            ),
            "迁移应留下可追溯的标记文件"
        )
    }

    /// 新目录已经存在时不能覆盖它——那会用旧数据盖掉用户的现有格式库。
    private static func checkNewContainerIsLeftAlone(
        under testRoot: URL,
        fileManager: FileManager
    ) throws {
        let support = testRoot.appendingPathComponent("both-exist", isDirectory: true)
        let legacy = support.appendingPathComponent(
            LibraryLocation.legacyContainerName,
            isDirectory: true
        )
        let container = support.appendingPathComponent(
            LibraryLocation.containerName,
            isDirectory: true
        )
        try fileManager.createDirectory(at: legacy, withIntermediateDirectories: true)
        try fileManager.createDirectory(at: container, withIntermediateDirectories: true)
        try Data("new".utf8).write(to: container.appendingPathComponent("marker"))

        let resolved = LibraryLocation.migrateIfNeeded(
            from: legacy,
            to: container,
            fileManager: fileManager
        )
        try require(resolved.path == container.path, "两个目录都存在时应使用新目录")
        try require(
            fileManager.fileExists(atPath: container.appendingPathComponent("marker").path),
            "新目录已有的内容不应被旧目录覆盖"
        )
    }

    private static func checkFreshInstallNeedsNoMigration(
        under testRoot: URL,
        fileManager: FileManager
    ) throws {
        let support = testRoot.appendingPathComponent("fresh", isDirectory: true)
        try fileManager.createDirectory(at: support, withIntermediateDirectories: true)
        let container = support.appendingPathComponent(
            LibraryLocation.containerName,
            isDirectory: true
        )

        let resolved = LibraryLocation.migrateIfNeeded(
            from: support.appendingPathComponent(
                LibraryLocation.legacyContainerName,
                isDirectory: true
            ),
            to: container,
            fileManager: fileManager
        )
        try require(resolved.path == container.path, "全新安装应直接使用新目录")
    }

    private static func require(
        _ condition: @autoclosure () -> Bool,
        _ message: String
    ) throws {
        guard condition() else { throw LocationTestFailure.failed(message) }
    }
}
