# windows-app/FormaFushi.Windows/ — 模块索引(L2)

> 本文件夹内文件增删、重命名、接口变更时,必须更新本文件。上级索引:[../../PROJECT_INDEX.md](../../PROJECT_INDEX.md)

## 模块定位
Windows WinForms 外壳；通过 PythonBridge 调用同一格式资产引擎。

## 文件清单
| 文件 | 职责 | 关键导出 |
|------|------|----------|
| ConfirmDialog.cs | 提供中文确认弹窗与安全默认取消 | ConfirmDialog |
| FormatDisplay.cs | 生成格式属性及应用说明的 Windows 展示文案 | FormatDisplay, ApplyNotes |
| MainForm.Layout.cs | 创建 Windows 三步流程控件和布局 | MainForm |
| MainForm.cs | 协调 Windows 格式库读取、保存、删除和应用 | MainForm |
| Models.cs | 解码共享迁移引擎输出为 Windows 模型 | AppFailure, ManagerEnvelope, LibraryReadError, PackManifest, UsedFormat, ManualFormatting, DocumentSummary, PageLayout, TransferStats |
| PackDeletionPolicy.cs | 验证格式库文件身份并限制回收站删除范围 | PackDeletionPolicy |
| Program.cs | 初始化 Windows 单线程桌面应用 | Program |
| PythonBridge.cs | 维护本目录应用接口 | PythonBridge |
| Theme.cs | 提供 Windows 统一视觉样式与卡片 | Theme, CardPanel |
