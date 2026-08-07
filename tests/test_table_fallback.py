#!/usr/bin/env python3
"""Regression coverage for targets with tables and table-free style sources."""

from __future__ import annotations

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
