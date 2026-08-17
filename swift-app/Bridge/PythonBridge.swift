import Foundation

struct ManagerOutput {
    let data: Data
    let standardError: String
    let status: Int32
}

/// 与 style_pack_manager.py 之间唯一的进程边界。
///
/// 阶段二把引擎换成 Rust 静态库时，只需要替换这个类型的实现，
/// 上层视图与模型不受影响。
enum PythonBridge {
    static func run(arguments: [String]) async throws -> ManagerOutput {
        guard let scriptURL = managerScriptURL() else {
            throw AppFailure.message(UIStrings.Errors.managerMissing)
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
            throw AppFailure.message(
                UIStrings.Errors.managerLaunchFailed(detail: error.localizedDescription)
            )
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

        // 开发期回退：让 `swiftc … && ./app` 依然可用；分发的 .app 永远解析到
        // Contents/Resources 里的副本。本文件位于 swift-app/Bridge/，向上三层是仓库根目录。
        let sourceFile = URL(fileURLWithPath: #filePath)
        candidates.append(
            sourceFile.deletingLastPathComponent()
                .deletingLastPathComponent()
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
