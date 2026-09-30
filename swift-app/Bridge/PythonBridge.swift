// [INPUT]: 依赖 AppKit, Darwin, SwiftUI, UniformTypeIdentifiers
// [OUTPUT]: 提供PythonBridge 中的类型与接口
// [POS]: Mac 原生终端 - 可取消本地 Python 进程与嵌入运行时发现
// [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
import AppKit
import Darwin
import SwiftUI
import UniformTypeIdentifiers

// MARK: - Python bridge

final class PythonOperation: @unchecked Sendable {
    private let lock = NSLock()
    private var process: Process?
    private var cancelled = false

    var isCancelled: Bool {
        lock.lock()
        defer { lock.unlock() }
        return cancelled
    }

    func attach(_ process: Process) {
        lock.lock()
        self.process = process
        let shouldStop = cancelled
        lock.unlock()
        if shouldStop {
            Self.stop(process)
        }
    }

    func detach(_ process: Process) {
        lock.lock()
        if self.process === process {
            self.process = nil
        }
        lock.unlock()
    }

    func cancel() {
        lock.lock()
        cancelled = true
        let processToStop = process
        lock.unlock()
        if let processToStop {
            Self.stop(processToStop)
        }
    }

    private static func stop(_ process: Process) {
        guard process.isRunning else { return }
        process.terminate()
        let processIdentifier = process.processIdentifier
        DispatchQueue.global(qos: .userInitiated).asyncAfter(deadline: .now() + 1) {
            guard process.isRunning else { return }
            Darwin.kill(processIdentifier, SIGKILL)
        }
    }
}

enum PythonBridge {
    static let bundledRuntimeRelativePath = "runtime/bin/python3"

    static func run(
        arguments: [String],
        operation: PythonOperation
    ) async throws -> ManagerOutput {
        guard let scriptURL = managerScriptURL() else {
            throw AppFailure.message("应用资源不完整：找不到 style_pack_manager.py。请重新安装应用。")
        }

        let process = Process()
        if let bundledPython = bundledPythonURL() {
            process.executableURL = bundledPython
            process.arguments = ["-B", "-E", "-s", "-X", "utf8", scriptURL.path] + arguments
            process.environment = isolatedEnvironment(for: bundledPython)
        } else if isRunningFromApplicationBundle {
            throw AppFailure.message(
                "应用资源不完整：找不到内置文档处理环境。请重新安装 Forma 赋式。"
            )
        } else if FileManager.default.isExecutableFile(atPath: "/usr/bin/python3") {
            // Development-only fallback. A distributed .app must always use
            // Contents/Resources/runtime/bin/python3.
            process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            process.arguments = ["-B", "-E", "-X", "utf8", scriptURL.path] + arguments
            process.environment = developmentEnvironment()
        } else {
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = ["python3", "-B", "-E", "-X", "utf8", scriptURL.path] + arguments
            process.environment = developmentEnvironment()
        }
        process.currentDirectoryURL = scriptURL.deletingLastPathComponent()

        let standardOutput = Pipe()
        let standardError = Pipe()
        process.standardOutput = standardOutput
        process.standardError = standardError

        do {
            try process.run()
        } catch {
            throw AppFailure.message("无法启动文档处理组件：\(error.localizedDescription)")
        }
        operation.attach(process)
        defer { operation.detach(process) }

        return try await withTaskCancellationHandler {
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
            // A cancel request can arrive after the helper has already
            // committed its atomic output and exited successfully.  In that
            // narrow window the successful protocol result is authoritative;
            // reporting a cancellation would leave a valid but hidden pack
            // or document behind.  Non-zero exits still resolve as cancelled.
            if (operation.isCancelled || Task.isCancelled) && status != 0 {
                throw CancellationError()
            }
            let errorText = String(data: errorData, encoding: .utf8) ?? ""
            return ManagerOutput(data: data, standardError: errorText, status: status)
        } onCancel: {
            operation.cancel()
        }
    }

    private static var isRunningFromApplicationBundle: Bool {
        Bundle.main.bundleURL.pathExtension.lowercased() == "app"
    }

    private static func bundledPythonURL() -> URL? {
        guard let resources = Bundle.main.resourceURL else { return nil }
        let url = resources.appendingPathComponent(bundledRuntimeRelativePath)
        return FileManager.default.isExecutableFile(atPath: url.path) ? url : nil
    }

    private static func isolatedEnvironment(for pythonURL: URL) -> [String: String] {
        var environment = [
            "PATH": pythonURL.deletingLastPathComponent().path + ":/usr/bin:/bin",
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1"
        ]
        if let temporaryDirectory = ProcessInfo.processInfo.environment["TMPDIR"] {
            environment["TMPDIR"] = temporaryDirectory
        }
        return environment
    }

    private static func developmentEnvironment() -> [String: String] {
        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUTF8"] = "1"
        environment["PYTHONUNBUFFERED"] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return environment
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

        // Test/debug builds may locate the adjacent helper from the source
        // tree. Release binaries deliberately omit #filePath so a developer's
        // local workspace path is never embedded in a distributed executable.
#if DEBUG || WORD_FORMAT_LIBRARY_TESTING
        let sourceFile = URL(fileURLWithPath: #filePath)
        candidates.append(
            sourceFile.deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .appendingPathComponent("style_pack_manager.py")
        )
#endif
        candidates.append(
            URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
                .appendingPathComponent("style_pack_manager.py")
        )

        return candidates.first { fileManager.fileExists(atPath: $0.path) }
    }
}
