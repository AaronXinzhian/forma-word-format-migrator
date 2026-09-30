#!/usr/bin/env python3
# [INPUT]: 依赖 __future__, json, sys, tempfile, unittest, zipfile, pathlib, typing, lxml, style_pack_manager, word_style_transfer
# [OUTPUT]: 提供 TEST_DIR, PROJECT_DIR, FIXTURES, NS, read_zip(), document_root(), table_structure(), canonical_nodes(), table_style_node(), default_table_style(), TableFallbackTests
# [POS]: 验证无表格模板下目标表格结构与样式保留
# [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
"""Regression coverage for targets with tables and table-free style sources."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Optional

from lxml import etree


TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
FIXTURES = TEST_DIR / "fixtures"
sys.path.insert(0, str(PROJECT_DIR))

import style_pack_manager as manager  # noqa: E402
import word_style_transfer as core  # noqa: E402


NS = {"w": core.W_NS}


def read_zip(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def document_root(entries: dict[str, bytes]) -> etree._Element:
    return etree.fromstring(entries["word/document.xml"])


def table_structure(root: etree._Element) -> list[tuple[tuple[str, ...], ...]]:
    structures: list[tuple[tuple[str, ...], ...]] = []
    for table in root.xpath("//w:tbl", namespaces=NS):
        rows: list[tuple[str, ...]] = []
        for row in table.findall("w:tr", namespaces=NS):
            rows.append(
                tuple(
                    "".join(cell.xpath(".//w:t/text()", namespaces=NS))
                    for cell in row.findall("w:tc", namespaces=NS)
                )
            )
        structures.append(tuple(rows))
    return structures


def canonical_nodes(root: etree._Element, xpath: str) -> list[bytes]:
    return [
        etree.tostring(node, method="c14n", exclusive=True)
        for node in root.xpath(xpath, namespaces=NS)
    ]


def table_style_node(
    entries: dict[str, bytes], style_id: str
) -> Optional[etree._Element]:
    styles = etree.fromstring(entries["word/styles.xml"])
    nodes = styles.xpath(
        "//w:style[@w:type='table' and @w:styleId=$style_id]",
        namespaces=NS,
        style_id=style_id,
    )
    return nodes[0] if nodes else None


def default_table_style(entries: dict[str, bytes]) -> list[str]:
    settings = etree.fromstring(entries["word/settings.xml"])
    return settings.xpath("//w:defaultTableStyle/@w:val", namespaces=NS)


class TableFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(
            prefix="word-table-fallback-tests-"
        )
        cls.working_dir = Path(cls._temporary.name)

        cls.no_table_pack = cls.working_dir / "no-table.wfstyle"
        cls.no_table_manifest = manager.create_style_pack(
            FIXTURES / "source-no-table.docx",
            cls.no_table_pack,
        )
        cls.no_table_output_path = cls.working_dir / "no-table-output.docx"
        manager.apply_style_pack(
            cls.no_table_pack,
            FIXTURES / "target.docx",
            cls.no_table_output_path,
        )

        cls.with_table_pack = cls.working_dir / "with-table.wfstyle"
        manager.create_style_pack(
            FIXTURES / "source.docx",
            cls.with_table_pack,
        )
        cls.with_table_output_path = cls.working_dir / "with-table-output.docx"
        manager.apply_style_pack(
            cls.with_table_pack,
            FIXTURES / "target.docx",
            cls.with_table_output_path,
        )

        cls.target_entries = read_zip(FIXTURES / "target.docx")
        cls.no_table_source_entries = read_zip(
            FIXTURES / "source-no-table.docx"
        )
        cls.no_table_output_entries = read_zip(cls.no_table_output_path)
        cls.with_table_output_entries = read_zip(cls.with_table_output_path)
        cls.target_document = document_root(cls.target_entries)
        cls.no_table_document = document_root(cls.no_table_output_entries)
        cls.with_table_document = document_root(cls.with_table_output_entries)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_table_free_source_exposes_no_used_table_styles(self) -> None:
        self.assertEqual(
            self.no_table_manifest["document_summary"]["table_count"], 0
        )
        self.assertEqual(self.no_table_manifest["used_table_styles"], [])
        self.assertFalse(
            any(
                item["type"] == "table"
                for item in self.no_table_manifest["used_formats"]
            )
        )
        candidate = self.no_table_manifest.get("table_style_edit_candidate")
        self.assertIsInstance(candidate, dict)
        self.assertEqual(candidate["style_id"], "TableNormal")
        self.assertEqual(candidate["type"], "table")
        self.assertEqual(candidate["usage_count"], 0)
        self.assertTrue(candidate["inferred"])
        self.assertEqual(candidate["inference_label"], "可选表格方案")

    def test_unedited_table_candidate_stays_optional_in_derived_pack(self) -> None:
        output_pack = self.working_dir / "no-table-text-edit.wfstyle"
        derived = manager.derive_style_pack(
            self.no_table_pack,
            output_pack,
            {
                "styles": [
                    {"style_id": "Normal", "font_east_asia": "宋体"}
                ]
            },
        )
        self.assertEqual(derived["used_table_styles"], [])
        self.assertFalse(
            any(item["type"] == "table" for item in derived["used_formats"])
        )
        candidate = derived.get("table_style_edit_candidate")
        self.assertIsInstance(candidate, dict)
        self.assertEqual(candidate["style_id"], "TableNormal")

        output_docx = self.working_dir / "no-table-text-edit-output.docx"
        manager.apply_style_pack(output_pack, FIXTURES / "target.docx", output_docx)
        output_entries = read_zip(output_docx)
        output_document = document_root(output_entries)
        self.assertEqual(
            output_document.xpath("//w:tblPr/w:tblStyle/@w:val", namespaces=NS),
            ["TargetCustomTable"],
        )
        self.assertEqual(
            table_structure(output_document), table_structure(self.target_document)
        )

    def test_edited_table_candidate_becomes_active_and_styles_target(self) -> None:
        output_pack = self.working_dir / "no-table-custom-table.wfstyle"
        derived = manager.derive_style_pack(
            self.no_table_pack,
            output_pack,
            {
                "styles": [
                    {
                        "style_id": "TableNormal",
                        "table_fill_hex": "F2F7F5",
                        "table_accent_hex": "27685D",
                    }
                ]
            },
        )
        self.assertEqual(derived["used_table_styles"], ["TableNormal"])
        self.assertEqual(derived["preferred_table_style"], "TableNormal")
        self.assertNotIn("table_style_edit_candidate", derived)
        active = [
            item
            for item in derived["used_formats"]
            if item["style_id"] == "TableNormal"
        ]
        self.assertEqual(len(active), 1)
        self.assertTrue(active[0]["inferred"])
        self.assertEqual(active[0]["inference_label"], "自定义表格方案")
        self.assertEqual(active[0]["table_fill_hex"], "F2F7F5")
        self.assertEqual(active[0]["table_accent_hex"], "27685D")

        output_docx = self.working_dir / "no-table-custom-table-output.docx"
        manager.apply_style_pack(output_pack, FIXTURES / "target.docx", output_docx)
        output_entries = read_zip(output_docx)
        output_document = document_root(output_entries)
        self.assertEqual(
            output_document.xpath("//w:tblPr/w:tblStyle/@w:val", namespaces=NS),
            ["TableNormal"],
        )
        self.assertEqual(
            table_structure(output_document), table_structure(self.target_document)
        )
        style = table_style_node(output_entries, "TableNormal")
        self.assertIsNotNone(style)
        self.assertEqual(
            style.xpath("w:tblPr/w:shd/@w:fill", namespaces=NS),
            ["F2F7F5"],
        )
        self.assertEqual(
            style.xpath(
                "w:tblStylePr[@w:type='firstRow']/w:tcPr/w:shd/@w:fill",
                namespaces=NS,
            ),
            ["27685D"],
        )

    def test_hidden_table_style_remains_rejected_by_editor_protocol(self) -> None:
        candidate_id = self.no_table_manifest["table_style_edit_candidate"][
            "style_id"
        ]
        hidden_table_id = next(
            style_id
            for style_id in ("TableGrid", "LightShading", "LightList")
            if style_id != candidate_id
        )
        with self.assertRaisesRegex(core.TransferError, "可编辑清单"):
            manager.derive_style_pack(
                self.no_table_pack,
                self.working_dir / "hidden-table-edit.wfstyle",
                {
                    "styles": [
                        {
                            "style_id": hidden_table_id,
                            "table_accent_hex": "27685D",
                        }
                    ]
                },
            )

    def test_legacy_no_table_pack_gets_in_memory_edit_candidate(self) -> None:
        legacy_pack = self.working_dir / "legacy-no-table.wfstyle"
        with zipfile.ZipFile(self.no_table_pack, "r") as source_archive:
            with zipfile.ZipFile(legacy_pack, "w") as legacy_archive:
                for info in source_archive.infolist():
                    data = source_archive.read(info.filename)
                    if info.filename == "manifest.json":
                        raw_manifest = json.loads(data.decode("utf-8"))
                        raw_manifest.pop("table_style_edit_candidate", None)
                        raw_manifest.pop("custom_style_count", None)
                        data = json.dumps(
                            raw_manifest,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    legacy_archive.writestr(info, data)

        with zipfile.ZipFile(legacy_pack, "r") as archive:
            persisted = json.loads(archive.read("manifest.json").decode("utf-8"))
        self.assertNotIn("table_style_edit_candidate", persisted)

        loaded, _entries = manager.load_style_pack(legacy_pack)
        candidate = loaded.get("table_style_edit_candidate")
        self.assertIsInstance(candidate, dict)
        self.assertEqual(candidate["style_id"], "TableNormal")
        listed = manager.list_library(self.working_dir)["packs"]
        legacy_listed = next(
            item
            for item in listed
            if Path(str(item.get("pack_path"))).name == legacy_pack.name
        )
        self.assertEqual(
            legacy_listed["table_style_edit_candidate"]["style_id"],
            "TableNormal",
        )

        derived = manager.derive_style_pack(
            legacy_pack,
            self.working_dir / "legacy-custom-table.wfstyle",
            {
                "styles": [
                    {
                        "style_id": "TableNormal",
                        "table_accent_hex": "27685D",
                    }
                ]
            },
        )
        self.assertEqual(derived["used_table_styles"], ["TableNormal"])
        self.assertEqual(derived["custom_style_count"], 1)
        self.assertEqual(
            [
                item["inference_label"]
                for item in derived["used_formats"]
                if item.get("configured") is True
            ],
            ["自定义表格方案"],
        )
        with zipfile.ZipFile(legacy_pack, "r") as archive:
            persisted_after = json.loads(
                archive.read("manifest.json").decode("utf-8")
            )
        self.assertNotIn("table_style_edit_candidate", persisted_after)

    def test_table_free_source_preserves_table_cells_and_text(self) -> None:
        target_structure = table_structure(self.target_document)
        output_structure = table_structure(self.no_table_document)
        self.assertTrue(target_structure)
        self.assertEqual(output_structure, target_structure)
        self.assertEqual(
            sum(len(row) for table in output_structure for row in table),
            sum(len(row) for table in target_structure for row in table),
        )

    def test_table_free_source_preserves_valid_target_table_style(self) -> None:
        target_ids = self.target_document.xpath(
            "//w:tblPr/w:tblStyle/@w:val", namespaces=NS
        )
        output_ids = self.no_table_document.xpath(
            "//w:tblPr/w:tblStyle/@w:val", namespaces=NS
        )
        self.assertEqual(target_ids, ["TargetCustomTable"])
        self.assertEqual(output_ids, target_ids)
        self.assertIsNone(
            table_style_node(
                self.no_table_source_entries, "TargetCustomTable"
            ),
            "custom table style must be target-only",
        )

        target_style = table_style_node(
            self.target_entries, "TargetCustomTable"
        )
        output_style = table_style_node(
            self.no_table_output_entries, "TargetCustomTable"
        )
        self.assertIsNotNone(target_style)
        self.assertIsNotNone(output_style, "输出必须保留目标独有表格样式定义")
        self.assertEqual(
            etree.tostring(output_style, method="c14n", exclusive=True),
            etree.tostring(target_style, method="c14n", exclusive=True),
        )

    def test_table_free_source_preserves_target_default_table_style(self) -> None:
        self.assertEqual(
            default_table_style(self.target_entries), ["TargetCustomTable"]
        )
        self.assertEqual(
            default_table_style(self.no_table_output_entries),
            ["TargetCustomTable"],
        )

    def test_table_free_source_preserves_direct_borders_and_shading(self) -> None:
        target_borders = canonical_nodes(
            self.target_document, "//w:tblPr/w:tblBorders"
        )
        output_borders = canonical_nodes(
            self.no_table_document, "//w:tblPr/w:tblBorders"
        )
        target_shading = canonical_nodes(
            self.target_document, "//w:tcPr/w:shd"
        )
        output_shading = canonical_nodes(
            self.no_table_document, "//w:tcPr/w:shd"
        )

        self.assertTrue(target_borders, "fixture must contain direct table borders")
        self.assertTrue(target_shading, "fixture must contain direct cell shading")
        self.assertEqual(output_borders, target_borders)
        self.assertEqual(output_shading, target_shading)

    def test_table_free_source_preserves_table_row_and_cell_properties(self) -> None:
        property_paths = (
            "//w:tblPr/w:tblCellMar",
            "//w:trPr/w:trHeight",
            "//w:tcPr/w:tcMar",
            "//w:tcPr/w:vAlign",
            "//w:tcPr/w:gridSpan",
        )
        for path in property_paths:
            with self.subTest(path=path):
                expected = canonical_nodes(self.target_document, path)
                actual = canonical_nodes(self.no_table_document, path)
                self.assertTrue(expected, "fixture is missing %s" % path)
                self.assertEqual(actual, expected)

    def test_styles_extension_list_remains_last_root_child(self) -> None:
        for label, entries in (
            ("source", self.no_table_source_entries),
            ("output", self.no_table_output_entries),
        ):
            with self.subTest(label=label):
                root = etree.fromstring(entries["word/styles.xml"])
                children = [etree.QName(child).localname for child in root]
                self.assertEqual(children.count("extLst"), 1)
                self.assertEqual(children[-1], "extLst")

    def test_source_with_table_still_replaces_target_table_format(self) -> None:
        table_ids = self.with_table_document.xpath(
            "//w:tblPr/w:tblStyle/@w:val", namespaces=NS
        )
        self.assertEqual(table_ids, ["LightShading-Accent1"])
        self.assertFalse(
            self.with_table_document.xpath(
                "//w:tblPr/w:tblBorders", namespaces=NS
            )
        )
        self.assertFalse(
            self.with_table_document.xpath("//w:tcPr/w:shd", namespaces=NS)
        )
        for removed_path in (
            "//w:tblPr/w:tblCellMar",
            "//w:trPr/w:trHeight",
            "//w:tcPr/w:tcMar",
            "//w:tcPr/w:vAlign",
        ):
            self.assertFalse(
                self.with_table_document.xpath(removed_path, namespaces=NS),
                removed_path,
            )
        self.assertTrue(
            self.with_table_document.xpath(
                "//w:tcPr/w:gridSpan", namespaces=NS
            ),
            "gridSpan is merge semantics and must survive style replacement",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
