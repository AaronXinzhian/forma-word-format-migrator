import Foundation

private enum DeletionTestFailure: LocalizedError {
    case failed(String)

    var errorDescription: String? {
        switch self {
        case .failed(let message): return message
        }
    }
}

@main
struct PackDeletionPolicyTests {
    static func main() throws {
        let fileManager = FileManager.default
        let testRoot = fileManager.temporaryDirectory.appendingPathComponent(
            "word-format-library-delete-tests-\(UUID().uuidString)",
            isDirectory: true
        )
        let library = testRoot.appendingPathComponent("style-packs", isDirectory: true)
        try fileManager.createDirectory(at: library, withIntermediateDirectories: true)
        defer { try? fileManager.removeItem(at: testRoot) }

        let validURL = library.appendingPathComponent("valid.wfstyle")
        try Data("test-format-pack".utf8).write(to: validURL)
        let validPack = try makePack(id: "shared-id", path: validURL.path)
        let validResult = try PackDeletionPolicy.validatedURL(
            for: validPack,
            currentPacks: [validPack],
            libraryDirectory: library
        )
        try require(
            validResult.path == validURL.path,
            "格式库根目录中的普通 .wfstyle 文件应通过校验"
        )

        let duplicateURL = library.appendingPathComponent("duplicate-id.wfstyle")
        try Data("another-format-pack".utf8).write(to: duplicateURL)
        let duplicatePack = try makePack(id: "shared-id", path: duplicateURL.path)
        let duplicateResult = try PackDeletionPolicy.validatedURL(
            for: duplicatePack,
            currentPacks: [validPack, duplicatePack],
            libraryDirectory: library
        )
        try require(
            duplicateResult.path == duplicateURL.path,
            "重复 manifest id 时必须按精确 packPath 识别"
        )
        try expectRejection("同 id 但不在当前列表中的路径必须拒绝") {
            let unknownURL = library.appendingPathComponent("unknown.wfstyle")
            try Data("unknown".utf8).write(to: unknownURL)
            let unknownPack = try makePack(id: "shared-id", path: unknownURL.path)
            _ = try PackDeletionPolicy.validatedURL(
                for: unknownPack,
                currentPacks: [validPack, duplicatePack],
                libraryDirectory: library
            )
        }

        let outsideURL = testRoot.appendingPathComponent("outside.wfstyle")
        try Data("outside".utf8).write(to: outsideURL)
        let outsidePack = try makePack(id: "outside", path: outsideURL.path)
        try expectRejection("格式库外部文件必须拒绝") {
            _ = try PackDeletionPolicy.validatedURL(
                for: outsidePack,
                currentPacks: [outsidePack],
                libraryDirectory: library
            )
        }

        let nestedDirectory = library.appendingPathComponent("nested", isDirectory: true)
        try fileManager.createDirectory(at: nestedDirectory, withIntermediateDirectories: true)
        let nestedURL = nestedDirectory.appendingPathComponent("nested.wfstyle")
        try Data("nested".utf8).write(to: nestedURL)
        let nestedPack = try makePack(id: "nested", path: nestedURL.path)
        try expectRejection("格式库子目录中的文件必须拒绝") {
            _ = try PackDeletionPolicy.validatedURL(
                for: nestedPack,
                currentPacks: [nestedPack],
                libraryDirectory: library
            )
        }

        let disguisedDirectory = library.appendingPathComponent("folder.wfstyle", isDirectory: true)
        try fileManager.createDirectory(at: disguisedDirectory, withIntermediateDirectories: true)
        let disguisedPack = try makePack(id: "folder", path: disguisedDirectory.path)
        try expectRejection("伪装成 .wfstyle 的目录必须拒绝") {
            _ = try PackDeletionPolicy.validatedURL(
                for: disguisedPack,
                currentPacks: [disguisedPack],
                libraryDirectory: library
            )
        }

        let symlinkURL = library.appendingPathComponent("outside-link.wfstyle")
        try fileManager.createSymbolicLink(
            atPath: symlinkURL.path,
            withDestinationPath: outsideURL.path
        )
        let symlinkPack = try makePack(id: "symlink", path: symlinkURL.path)
        try expectRejection("指向格式库外部的符号链接必须拒绝") {
            _ = try PackDeletionPolicy.validatedURL(
                for: symlinkPack,
                currentPacks: [symlinkPack],
                libraryDirectory: library
            )
        }

        try require(
            PackDeletionPolicy.fallbackIndex(afterDeleting: 0, remainingCount: 2) == 0,
            "删除中间项后应优先选择原位置的下一项"
        )
        try require(
            PackDeletionPolicy.fallbackIndex(afterDeleting: 2, remainingCount: 2) == 1,
            "删除末项后应选择上一项"
        )
        try require(
            PackDeletionPolicy.fallbackIndex(afterDeleting: 0, remainingCount: 0) == nil,
            "删除唯一项后不应保留选择"
        )

        let trashableURL = library.appendingPathComponent("trash-roundtrip.wfstyle")
        try Data("trash-roundtrip".utf8).write(to: trashableURL)
        let trashablePack = try makePack(id: "trash-roundtrip", path: trashableURL.path)
        let validatedTrashableURL = try PackDeletionPolicy.validatedURL(
            for: trashablePack,
            currentPacks: [trashablePack],
            libraryDirectory: library
        )
        var trashedURL: NSURL?
        try fileManager.trashItem(at: validatedTrashableURL, resultingItemURL: &trashedURL)
        try require(!fileManager.fileExists(atPath: trashableURL.path), "文件应从格式库中消失")
        guard let trashedURL = trashedURL as URL? else {
            throw DeletionTestFailure.failed("系统没有返回废纸篓位置")
        }
        try require(fileManager.fileExists(atPath: trashedURL.path), "文件应存在于废纸篓")
        try fileManager.moveItem(at: trashedURL, to: trashableURL)
        try require(fileManager.fileExists(atPath: trashableURL.path), "废纸篓文件应可恢复")

        print("PackDeletionPolicyTests: 12 checks passed")
    }

    private static func makePack(id: String, path: String) throws -> PackManifest {
        let object: [String: Any] = [
            "id": id,
            "name": "临时格式",
            "used_formats": [],
            "used_style_count": 0,
            "manual_formatting": ["paragraph_count": 0, "run_count": 0],
            "document_summary": [
                "paragraph_count": 0,
                "run_count": 0,
                "table_count": 0,
                "section_count": 0
            ],
            "page_layout": [:],
            "pack_path": path
        ]
        let data = try JSONSerialization.data(withJSONObject: object)
        return try JSONDecoder().decode(PackManifest.self, from: data)
    }

    private static func require(_ condition: @autoclosure () -> Bool, _ message: String) throws {
        guard condition() else { throw DeletionTestFailure.failed(message) }
    }

    private static func expectRejection(_ message: String, operation: () throws -> Void) throws {
        do {
            try operation()
            throw DeletionTestFailure.failed(message)
        } catch is DeletionTestFailure {
            throw DeletionTestFailure.failed(message)
        } catch {
            return
        }
    }
}
