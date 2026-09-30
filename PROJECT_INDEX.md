# Forma 赋式 — 项目索引(L1)

> 架构、模块和接口变化后同步 L1/L2/L3。使用 scripts/check_project_docs.py --sync 更新机器字段，再检查语义职责。

## 定位

本地 Word 格式资产工具。将模板中实际使用的样式、标题编号和页面布局保存为可复用格式方案，保留目标内容及表格结构并生成独立文档。Mac 是 Swift/SwiftUI 原生界面，Windows 是 WinForms 界面；共享 Python OOXML 内核与 .wfstyle schema 1。

## 技术栈

Python/lxml 负责受限 ZIP/XML 解析与迁移；Mac 使用 SwiftUI、AppKit、CoreText 和打包内 Universal Python；Windows 使用 .NET WinForms 与打包内 x64 Python。共享中文文案由 JSON 生成两端代码。Mac 当前构建固定 SDK 26.5，Windows SDK 固定于 global.json；实际环境记录在 source-manifest.json。

## 目录结构

```text
word-format-migrator/
├── style_pack_manager.py   # 格式资产、预检、导入导出、编辑派生和 CLI
├── word_style_transfer.py  # OOXML 迁移、标题语义、编号身份隔离和表格保护
├── scripts/               # 构建、生成与文档检查 → scripts/FOLDER_INDEX.md
├── shared/                # 两平台共享文案源
├── swift-app/             # Mac 入口 → swift-app/FOLDER_INDEX.md
│   ├── Bridge/            # 库位置与引擎进程 → swift-app/Bridge/FOLDER_INDEX.md
│   ├── Models/            # 状态与数据投影 → swift-app/Models/FOLDER_INDEX.md
│   ├── Views/             # 三步流程与编辑 → swift-app/Views/FOLDER_INDEX.md
│   ├── Theme/             # 统一组件 → swift-app/Theme/FOLDER_INDEX.md
│   └── Generated/         # 自动生成文案（手工协议豁免）
├── windows-app/
│   └── FormaFushi.Windows/ # WinForms 外壳 → windows-app/FormaFushi.Windows/FOLDER_INDEX.md
│       └── Generated/     # 自动生成文案（手工协议豁免）
├── tests/                 # 隔离回归 → tests/FOLDER_INDEX.md
│   ├── WindowsPackDeletionPolicyTests/ # 删除安全 → tests/WindowsPackDeletionPolicyTests/FOLDER_INDEX.md
│   └── WindowsSmokeHarness/ # Windows 原生包验收 → tests/WindowsSmokeHarness/FOLDER_INDEX.md
└── tools/                 # 图标生成 → tools/FOLDER_INDEX.md
```

## 模块依赖关系

Mac Views → LibraryModel → PythonBridge → style_pack_manager → word_style_transfer。
Windows MainForm → PythonBridge → 同一共享引擎。
shared/ui-strings.json → gen_ui_strings.py → 两端 Generated 文案。
tests 验证引擎、库位置和删除边界；scripts 构建并验证实际包及源码哈希。

## 根目录文件

| 文件 | 职责 | 关键导出 |
|------|------|----------|
| style_pack_manager.py | 格式包白名单、实际使用预览、编辑派生、预检绑定与导入导出 | PACK_SCHEMA_VERSION, PACK_SUFFIX, PART_PREFIX, MAX_PACK_MEMBERS, MAX_PACK_MEMBER_BYTES, MAX_PACK_TOTAL_BYTES, MAX_EDITS_JSON_BYTES, MAX_FONT_ALIASES_PER_FORMAT, A_NS, A, FORMAT_ROOT_TAGS, FORMAT_CONTENT_TYPES, FORBIDDEN_FORMAT_TAGS, inspect_source(), pack_file_stem(), allocate_pack_path(), create_style_pack(), load_style_pack(), _RUN_STYLE_EDIT_FIELDS, _PARAGRAPH_STYLE_EDIT_FIELDS, _NUMBERING_STYLE_EDIT_FIELDS, NUMBERING_FORMATS, TABLE_BORDER_STYLES, _TABLE_STYLE_EDIT_FIELDS, _STYLE_EDIT_FIELDS, _DERIVED_MANIFEST_COPY_FIELDS, _TABLE_PROPERTY_ORDER, _TABLE_STYLE_PROPERTY_ORDER, _TABLE_CELL_PROPERTY_ORDER, derive_style_pack(), import_style_pack(), export_style_pack(), preflight_style_pack(), apply_style_pack(), list_library(), build_parser(), main() |
| word_style_transfer.py | Word 安全解析、标题语义映射与编号、表格保护和新文件输出 | W_NS, R_NS, PKG_REL_NS, CT_NS, XML_NS, NS, SOURCE_SUFFIXES, TARGET_SUFFIXES, ROLE_NAMES, ROLE_FALLBACK_PARTS, RUN_SEMANTIC_KEEP, TABLE_PROPERTY_KEEP, ROW_PROPERTY_KEEP, CELL_PROPERTY_KEEP, SECTION_LAYOUT_TAGS, SETTINGS_FORMAT_TAGS, CONTENT_PART_PATTERNS, MAX_PACKAGE_MEMBERS, MAX_PACKAGE_UNCOMPRESSED_BYTES, MAX_PACKAGE_MEMBER_BYTES, MAX_PACKAGE_XML_BYTES, MAX_PACKAGE_COMPRESSION_RATIO, COMPRESSION_RATIO_MIN_BYTES, MAX_PACKAGE_MEMBER_NAME_BYTES, ALLOWED_PACKAGE_COMPRESSIONS, TransferError, qn(), local_name(), parse_xml(), serialize_xml(), normalize_style_name(), relationship_part_path(), resolve_relationship_target(), relative_relationship_target(), relationship_role(), is_content_part(), Package, validate_package_members(), read_package_snapshot(), load_package(), StyleInfo, StyleCatalog, HeadingNumberingRule, HeadingCompletionResult, build_style_catalog(), collect_used_table_styles(), PPR_CHILD_ORDER, HEADING_INDENT_ATTRIBUTES, HEADING_SPACING_INTEGER_ATTRIBUTES, HEADING_SPACING_BOOLEAN_ATTRIBUTES, HEADING_SPACING_ATTRIBUTES, LINE_SPACING_RULES, PARAGRAPH_ALIGNMENT_VALUES, RPR_CHILD_ORDER, STYLE_CHILD_ORDER, collect_used_heading_styles(), paragraph_outline_level(), collect_used_heading_levels(), _INDENT_HIERARCHY_GROUPS, _INDENT_CHARACTER_GROUPS, merge_style_hierarchy_indentation(), collect_heading_paragraph_properties(), collect_heading_paragraph_indents(), heading_paragraph_indents_from_manifest(), heading_paragraph_properties_from_manifest(), TABLE_NO_FIRST_LINE_STYLE_PREFIX, TABLE_NO_FIRST_LINE_STYLE_NAME, ensure_table_no_first_line_indent_styles(), complete_heading_hierarchy(), infer_heading_numbering_rules(), extract_heading_numbering_rules(), heading_numbering_manifest(), heading_numbering_from_manifest(), align_heading_style_numbering(), map_style_id(), TransferStats, BodyNumberingMergeResult, ManualHeadingPrefix, _ARABIC_HEADING_PREFIX, _PAREN_HEADING_PREFIX, _CHINESE_HEADING_PREFIX, set_heading_numbering_start_override(), extract_source_section_layout(), apply_section_layout(), clean_content_xml(), merge_settings(), parse_content_types(), content_type_for(), ensure_content_type_override(), remove_content_type_override(), parse_relationship_root(), unique_relationship_id(), unique_part_name(), copy_part_graph(), collect_format_relationships(), merge_target_table_style_system(), transfer_format_parts(), NUMBERING_CONTENT_TYPE, NUMPR_CHILD_ORDER, materialize_target_body_numbering(), merge_target_body_numbering(), write_package(), transfer(), human_summary(), build_parser(), main() |

## 全局规则

输入 Word 和原格式包不覆盖；输出经过独立验证与原子保存。外来格式包只允许格式 XML，不携带正文、二进制内容或外部关系。标题按有效大纲语义识别，不凭字号猜测；表格结构和正文列表属于内容语义，不能因模板缺失而删除。

目标预检绑定模板与目标 SHA-256 及应用选项；输入或选项变化使预检失效。结构验证不等于 Word 排版验收，生成后需检查实际分页和字体。Mac ad-hoc 包仅为本机验证，正式发布需独立签名、公证；Mac 交叉构建 Windows 不等于 Windows 执行验收。

文档检查只覆盖 Git 源文件快照；忽略的历史构建归档、二进制和自动生成代码不纳入手工协议。归档不能作为当前源码的测试证据。
