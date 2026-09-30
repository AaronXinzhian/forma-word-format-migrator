# tests/ — 模块索引(L2)

> 本文件夹内文件增删、重命名、接口变更时,必须更新本文件。上级索引:[../PROJECT_INDEX.md](../PROJECT_INDEX.md)

## 模块定位
共享引擎和平台安全策略的隔离回归集。样本位于 fixtures，测试输出仅进入临时目录。

## 文件清单
| 文件 | 职责 | 关键导出 |
|------|------|----------|
| EditorStatePolicyTests.swift | 验证编辑重置撤销、选择一致性、单位切换与预检绑定 | EditorStatePolicyTests |
| LibraryLocationTests.swift | 验证旧格式库位置迁移、冲突保护与失败回退 | LibraryLocationTests |
| PackDeletionPolicyTests.swift | 验证 Mac 格式库删除的路径、链接和扩展名边界 | PackDeletionPolicyTests |
| make_fixtures.py | 生成含标题编号、字体、表格和内容语义的回归样本 | ROOT, FIXTURES, set_cell_shading(), set_table_borders(), set_table_cell_margins(), set_cell_margins(), set_row_height(), set_default_table_style(), append_styles_extension(), set_paragraph_border(), set_style_font(), set_style_outline_level(), set_direct_paragraph_numbering(), set_style_numbering(), add_heading_multilevel_numbering(), add_single_level_numbering(), add_numbering_style_proxy(), mirror_numbering_to_styles_with_effects(), mirror_heading_numbering_to_styles_with_effects(), add_hyperlink(), make_source(), make_target(), format_heading_source_styles(), make_three_level_heading_logic_source(), make_rich_numbering_format_source(), make_multi_numid_heading_source(), make_manual_heading_prefix_target(), make_five_level_heading_target(), make_heading_numbering_source(), make_direct_heading_numbering_source(), make_custom_outline_numbering_source(), make_explicitly_cancelled_heading_source(), make_num_style_link_heading_source(), make_plain_heading_target() |
| test_body_list_numbering.py | 验证正文列表、编号隔离、重启和图片项目符号保留 | TEST_DIR, PROJECT_DIR, FIXTURES, NS, W_VAL, BodyListNumberingTests |
| test_direct_table_fallback.py | 验证直接迁移在模板无表格时保留目标表格 | TEST_DIR, PROJECT_DIR, FIXTURES, NS, read_zip(), canonical_nodes(), DirectTableFallbackTests |
| test_font_alias_theme_resolution.py | 验证字体别名与主题字体的解析和格式包兼容 | TEST_DIR, PROJECT_DIR, FIXTURES, read_zip(), write_zip(), set_font_alias(), used_format(), FontAliasThemeResolutionTests |
| test_heading_demotion.py | 验证直接大纲标题映射、编号与可选单次降级 | TEST_DIR, PROJECT_DIR, NS, DEEPEST_HEADING, HEADER_HEADING, SOURCE_LEFT_BY_LEVEL, qn(), read_zip(), xml(), paragraph_for_text(), paragraph_style(), direct_numbering(), direct_left_indent(), HeadingDemotionTests |
| test_heading_inference.py | 验证标题层级补全的字体、尺寸、段落及编号逻辑 | TEST_DIR, PROJECT_DIR, NS, HEADING_TEXT, VISUAL_RUN_PROPERTIES, qn(), read_zip(), xml(), style_for_id(), paragraph_for_text(), effective_style_properties(), bool_value(), half_points(), twips(), effective_numbering_for_paragraph(), HeadingInferenceTests |
| test_heading_left_indent.py | 验证模板标题段落缩进与编号定位的独立保真 | TEST_DIR, PROJECT_DIR, FIXTURES, NS, HEADING_TEXT, HEADING_STYLE_ID, REPORTED_LEFT_TWIPS, ABSENT_DIRECT_INDENT_CASES, qn(), read_zip(), write_zip(), remove_manifest_fields_from_pack(), xml(), style_for_id(), paragraph_for_text(), effective_style_left(), paragraph_numbering_reference(), active_numbering_level(), effective_word_left(), canonical(), make_reported_source(), HeadingLeftIndentTests |
| test_heading_numbering.py | 验证标题样式和直接编号规则的迁移 | TEST_DIR, PROJECT_DIR, FIXTURES, NS, TARGET_HEADINGS, qn(), read_zip(), xml(), paragraph_for_text(), style_for_id(), effective_numbering_for_paragraph(), HeadingNumberingTests |
| test_heading_paragraph_properties.py | 验证标题对齐、间距、行距和缩进汇总 | TEST_DIR, PROJECT_DIR, FIXTURES, NS, qn(), read_zip(), write_zip(), xml(), paragraph_for_text(), style_for_id(), replace_direct_property(), set_paragraph_text(), make_source_with_direct_heading_properties(), preview_for(), HeadingParagraphPropertyTests |
| test_numbering_format_fidelity.py | 验证编号字体、标点、几何和手工前缀保真 | TEST_DIR, PROJECT_DIR, NS, qn(), read_zip(), xml(), style_for_id(), active_numbering_levels(), style_num_id(), paragraph_for_text_fragment(), canonical(), child_value(), geometry(), NumberingFormatFidelityTests, SharedNumberLabelFontTests, MultiNumIdAndManualPrefixTests |
| test_package_resource_limits.py | 验证 Word ZIP 成员、体积及压缩资源边界 | TEST_DIR, PROJECT_DIR, FIXTURES, synthetic_info(), PackageResourceLimitTests |
| test_style_pack.py | 验证格式包创建、应用、隐私白名单与命名 | TEST_DIR, PROJECT_DIR, FIXTURES, W_NS, R_NS, NS, qn(), read_zip(), xml(), paragraph_for_text(), numbering_definition(), StylePackTests, PackNamingTests |
| test_style_pack_derivation.py | 验证多样式编辑派生与原格式资产保护 | TEST_DIR, PROJECT_DIR, FIXTURES, style_node(), write_pack_unchecked(), StylePackDerivationTests |
| test_style_pack_input_limits.py | 验证格式包清单及编辑输入的资源限制 | TEST_DIR, PROJECT_DIR, FIXTURES, synthetic_info(), write_pack_with_manifest(), StylePackInputLimitTests |
| test_style_pack_security.py | 验证格式包仅允许格式 XML 与安全关系 | PROJECT_DIR, StylePackSecurityTests |
| test_style_pack_workflows.py | 验证预检绑定、导入导出、编号表格编辑及独立列表身份闭环 | PROJECT_DIR, StylePackWorkflowTests |
| test_table_fallback.py | 验证无表格模板下目标表格结构与样式保留 | TEST_DIR, PROJECT_DIR, FIXTURES, NS, read_zip(), document_root(), table_structure(), canonical_nodes(), table_style_node(), default_table_style(), TableFallbackTests |
| test_table_paragraph_indent.py | 验证表格两字符首行缩进清理和重复应用稳定性 | TEST_DIR, PROJECT_DIR, FIXTURES, NS, W_VAL, _CUSTOM_BODY_STYLE_SPECS, TableParagraphIndentTests |
| test_transfer.py | 验证真实 Word 迁移、CLI 与内容语义保留 | TEST_DIR, PROJECT_DIR, FIXTURES, ENGINE, W_NS, R_NS, NS, qn(), read_zip(), xml(), paragraph_for_text(), semantic_xml(), style_node(), TransferEndToEndTests |
