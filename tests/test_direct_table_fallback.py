#!/usr/bin/env python3
"""Direct-transfer coverage for table-free sources and non-body tables."""

from __future__ import annotations

import copy
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from lxml import etree


TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
FIXTURES = TEST_DIR / "fixtures"
sys.path.insert(0, str(PROJECT_DIR))

import word_style_transfer as core  # noqa: E402


NS = {"w": core.W_NS}


def read_zip(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def canonical_nodes(data: bytes, xpath: str) -> list[bytes]:
    root = etree.fromstring(data)
    return [
        etree.tostring(node, method="c14n")
        for node in root.xpath(xpath, namespaces=NS)
    ]


class DirectTableFallbackTests(unittest.TestCase):
    def test_direct_transfer_preserves_target_table_formatting(self) -> None:
        with tempfile.TemporaryDirectory(prefix="word-direct-table-fallback-") as raw:
            output = Path(raw) / "output.docx"
            stats = core.transfer(
                FIXTURES / "source-no-table.docx",
                FIXTURES / "target.docx",
                output,
            )
            target = read_zip(FIXTURES / "target.docx")
            result = read_zip(output)

            for xpath in (
                "//w:tblPr",
                "//w:trPr",
                "//w:tcPr",
            ):
                self.assertEqual(
                    canonical_nodes(result["word/document.xml"], xpath),
                    canonical_nodes(target["word/document.xml"], xpath),
                )
            self.assertGreater(stats.table_formats_preserved, 0)
            self.assertTrue(
                any("保留目标文档的表格外观" in item for item in stats.warnings)
            )

    def test_collector_detects_table_style_used_only_in_header(self) -> None:
        package = core.load_package(
            FIXTURES / "source-no-table.docx", "测试格式源"
        )
        entries = copy.copy(package.entries)
        header_name = next(
            name for name in entries if name.startswith("word/header")
        )
        header = core.parse_xml(entries[header_name], header_name)
        table = etree.SubElement(header, core.qn(core.W_NS, "tbl"))
        table_properties = etree.SubElement(
            table, core.qn(core.W_NS, "tblPr")
        )
        style = etree.SubElement(
            table_properties, core.qn(core.W_NS, "tblStyle")
        )
        style.set(core.qn(core.W_NS, "val"), "TableGrid")
        entries[header_name] = core.serialize_xml(header)

        catalog = core.build_style_catalog(
            entries["word/styles.xml"], entries["word/document.xml"]
        )
        used, preferred = core.collect_used_table_styles(entries, catalog)
        self.assertIn("TableGrid", used)
        self.assertEqual(preferred, "TableGrid")


if __name__ == "__main__":
    unittest.main(verbosity=2)
