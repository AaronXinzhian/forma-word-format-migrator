# swift-app/Models/ — 模块索引(L2)

> 本文件夹内文件增删、重命名、接口变更时,必须更新本文件。上级索引:[../../PROJECT_INDEX.md](../../PROJECT_INDEX.md)

## 模块定位
界面状态和格式资产投影；以 Python 输出为依据，管理输入绑定、编辑草稿和字体解析。

## 文件清单
| 文件 | 职责 | 关键导出 |
|------|------|----------|
| EditorStatePolicy.swift | 管理样式选中状态及重置撤销历史 | FormatSelectionPolicy, StyleResetHistory |
| FontCatalog.swift | 解析模板字体与系统本地化字体别名 | InstalledFontFaceRecord, InstalledFontFamily, InstalledFontMatchKind, InstalledFontMatch, InstalledFontCatalog, TemplateFontRole, TemplateFontOption, templateFontOptions, templateAliases, localPreviewDescription, normalizedFontName, fontStrictLookupKey, fontCompactLookupKey, uniqueFontNames, preferredFontRecordOrder |
| LibraryModel.swift | 协调格式库、编辑、预检、应用和任务状态 | AppActivity, WordFormatLibraryModel |
| PackModels.swift | 定义格式包、预检、编辑请求和结果投影 | UsedFormat, ManualFormatting, DocumentSummary, PageLayout, PackManifest, ManagerEnvelope, DocumentPreflight, StyleEditRequest, StyleEditPayload, TransferStats, ApplyReport, LibraryReadError, ManagerOutput, AppFailure, PackDeletionPolicy |
| StyleEditDraft.swift | 构造受约束的格式编辑草稿与单位状态 | ParagraphAlignmentEditChoice, LineSpacingEditChoice, ParagraphIndentUnit, SpecialIndentEditChoice, ParagraphIndentMeasurement, ParagraphLineEdit, ParagraphSpecialIndentEdit, NumberingFormatEditChoice, NumberingRestartEditChoice, TableBorderEditChoice, BoldEditChoice, StyleEditDraft |
