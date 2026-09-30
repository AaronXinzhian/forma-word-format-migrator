# scripts/ — 模块索引(L2)

> 本文件夹内文件增删、重命名、接口变更时,必须更新本文件。上级索引:[../PROJECT_INDEX.md](../PROJECT_INDEX.md)

## 模块定位
开发与 CI 构建入口；调用共享引擎、平台工具链和测试，记录源码身份与包验证证据。

## 文件清单
| 文件 | 职责 | 关键导出 |
|------|------|----------|
| build_macos_app.sh | 构建双架构 Mac 包并执行运行时、签名与归档验证 | cleanup_build_root, download_verified, remove_build_tree, is_signable_macho, sign_item, verify_universal_binary, source_fingerprint |
| build_windows_app.ps1 | 在 Windows 本机构建并执行打包、签名及解压后验证 | — |
| build_windows_app.sh | 在 Mac 交叉构建 Windows 包，不冒充 Windows 执行验收 | — |
| check_project_docs.py | 用受版本控制的源码快照执行 GEB 文档闭环 | source_paths(), main() |
| gen_ui_strings.py | 从共享文案源生成两平台类型安全常量 | REPO_ROOT, SOURCE, SWIFT_OUTPUT, CSHARP_OUTPUT, PLACEHOLDER, PLATFORM_KEYS, BANNER, GeneratorError, load_catalog(), is_platform_variant(), resolve(), placeholders(), validate(), split_template(), literal(), expression(), pascal(), camel(), render_swift(), render_csharp(), main() |
| source_manifest.py | 记录源码版本、逐文件哈希与实际构建环境 | git(), source_manifest(), main() |
