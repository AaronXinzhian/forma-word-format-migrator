# swift-app/Views/ — 模块索引(L2)

> 本文件夹内文件增删、重命名、接口变更时,必须更新本文件。上级索引:[../../PROJECT_INDEX.md](../../PROJECT_INDEX.md)

## 模块定位
Mac 三步工作流、格式编辑器和状态展示，只通过模型发送操作。

## 文件清单
| 文件 | 职责 | 关键导出 |
|------|------|----------|
| ApplyStepView.swift | 展示目标选择、绑定预检、应用选项和生成结果 | ApplyStepView, TargetDocumentCard, ApplyOptionsCard, PreflightCard, OptionLine, SuccessCard, SuccessMetric |
| DisplayHelpers.swift | 转换 Word 段落和格式属性为界面文案 | paragraphAlignmentText, paragraphSpacingText, paragraphLineSpacingText, paragraphIndentSidesText, paragraphSpecialIndentText, preferredParagraphIndentMeasurement, preferredNonzeroParagraphIndentMeasurement, styleTypeText, normalizedHexColor, hexString, number, paragraphNumber |
| FilePanels.swift | 提供 Word 和格式包选择及保存面板 | FilePanels |
| FormatPreviewStepView.swift | 按实际使用样式过滤展示格式与摘要 | FormatFilter, FormatPreviewStepView, SummaryBar, MiniStat, ManualFormattingNotice, FormatFilterBar, FormatCard, TypeBadge |
| ImportStepView.swift | 引导选取 Word 模板和保存格式方案 | ImportStepView |
| LibrarySidebar.swift | 展示格式库与导入、导出、删除入口 | LibrarySidebar |
| OperationViews.swift | 展示任务状态、通知与阻塞操作层 | OperationNoticeBanner, BusyOverlay |
| RootView.swift | 组织 Mac 三步流程与格式选择 | WordFormatLibraryView, AppHeader, StepStrip, ToastBar, EmptySelectionView |
| StyleEditorSheet.swift | 编辑字体、段落、编号及表格并派生新方案 | StyleEditorSheet, StyleEditControls, StyleEditorSection, StyleEditorControlLabel, ParagraphNumberField, EditorOriginalValue, FontOverrideField, FontPickerPopover, FontPickerSectionLabel, FontChoiceButton, FontRegistrationBadge, fontRegistrationText, fontRegistrationIcon, fontRegistrationColor, EditorColorField, StyleEditLivePreview, ParagraphStyleTextPreview, PreviewPropertyRow |
| StyleInspector.swift | 展示选中样式与页面布局的详细属性 | StyleInspector, PropertyRow, PageLayoutCard |
