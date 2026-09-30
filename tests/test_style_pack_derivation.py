#!/usr/bin/env python3
# [INPUT]: 依赖 __future__, contextlib, copy, io, json, math, os, shutil, sys, tempfile, unittest, zipfile, pathlib, lxml, style_pack_manager, word_style_transfer
# [OUTPUT]: 提供 TEST_DIR, PROJECT_DIR, FIXTURES, style_node(), write_pack_unchecked(), StylePackDerivationTests
# [POS]: 验证多样式编辑派生与原格式资产保护
# [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
"""Regression tests for safe, non-destructive style-pack editing."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import math
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from lxml import etree


TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
FIXTURES = TEST_DIR / "fixtures"
sys.path.insert(0, str(PROJECT_DIR))

import style_pack_manager as manager  # noqa: E402
import word_style_transfer as core  # noqa: E402


def style_node(entries: dict[str, bytes], part: str, style_id: str) -> etree._Element:
    root = core.parse_xml(entries[part], part)
    matches = root.xpath(
        "./w:style[@w:styleId=$style_id]",
        namespaces=core.NS,
        style_id=style_id,
    )
    if not matches:
        raise AssertionError("missing style %s in %s" % (style_id, part))
    return matches[0]


def write_pack_unchecked(
    path: Path, manifest: dict[str, object], entries: dict[str, bytes]
) -> None:
    """Write a test-only pack, allowing deliberately invalid metadata."""
    persisted = copy.deepcopy(manifest)
    persisted.pop("pack_path", None)
    persisted["format_part_count"] = len(entries)
    persisted["part_sha256"] = manager._part_checksums(entries)
    persisted["format_fingerprint"] = manager._format_fingerprint(
        persisted["part_sha256"]
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            manager._zip_info("manifest.json"),
            json.dumps(persisted, ensure_ascii=False).encode("utf-8"),
        )
        for name, data in sorted(entries.items()):
            archive.writestr(manager._zip_info(manager.PART_PREFIX + name), data)


class StylePackDerivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(
            prefix="word-style-pack-derivation-tests-"
        )
        cls.working_dir = Path(cls._temporary.name)
        cls.source_pack = cls.working_dir / "source.wfstyle"
        cls.numbered_pack = cls.working_dir / "numbered.wfstyle"
        manager.create_style_pack(
            FIXTURES / "source.docx",
            cls.source_pack,
            display_name="原始格式方案",
        )
        manager.create_style_pack(
            FIXTURES / "source-numbered-headings.docx",
            cls.numbered_pack,
            display_name="编号格式方案",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_run_and_table_edits_create_a_new_integrity_checked_pack(self) -> None:
        original_bytes = self.source_pack.read_bytes()
        original_manifest, _original_entries = manager.load_style_pack(
            self.source_pack
        )
        derived_path = self.working_dir / "customized.wfstyle"
        derived = manager.derive_style_pack(
            self.source_pack,
            derived_path,
            {
                "styles": [
                    {
                        "style_id": "Heading1",
                        "font_east_asia": "Songti SC",
                        "font_latin": "Helvetica Neue",
                        "size_pt": 18.5,
                        "bold": False,
                        "color_hex": "#123456",
                    },
                    {
                        "style_id": "LightShading-Accent1",
                        "table_fill_hex": "F7F7F7",
                        "table_accent_hex": "165D52",
                    },
                ]
            },
            display_name="自定义格式方案",
        )

        self.assertEqual(self.source_pack.read_bytes(), original_bytes)
        self.assertNotEqual(derived["id"], original_manifest["id"])
        self.assertNotEqual(
            derived["format_fingerprint"],
            original_manifest["format_fingerprint"],
        )
        self.assertEqual(derived["name"], "自定义格式方案")
        self.assertEqual(
            derived["derivation"]["source_pack_id"], original_manifest["id"]
        )
        self.assertTrue(derived["privacy"]["derived_without_source_document"])
        self.assertIs(
            derived["privacy"]["display_name_derived_from_source"], False
        )

        loaded, entries = manager.load_style_pack(derived_path)
        self.assertEqual(loaded["part_sha256"], manager._part_checksums(entries))
        self.assertEqual(
            loaded["format_fingerprint"],
            manager._format_fingerprint(loaded["part_sha256"]),
        )
        previews = {item["style_id"]: item for item in loaded["used_formats"]}
        heading = previews["Heading1"]
        self.assertEqual(heading["font_east_asia"], "Songti SC")
        self.assertEqual(heading["font_latin"], "Helvetica Neue")
        self.assertEqual(heading["size_pt"], 18.5)
        self.assertIs(heading["bold"], False)
        self.assertEqual(heading["color_hex"], "123456")
        table = previews["LightShading-Accent1"]
        self.assertEqual(table["table_fill_hex"], "F7F7F7")
        self.assertEqual(table["table_accent_hex"], "165D52")

        for part in ("word/styles.xml", "word/stylesWithEffects.xml"):
            heading_node = style_node(entries, part, "Heading1")
            fonts = heading_node.find("w:rPr/w:rFonts", namespaces=core.NS)
            self.assertEqual(
                fonts.get(core.qn(core.W_NS, "eastAsia")), "Songti SC"
            )
            self.assertEqual(
                fonts.get(core.qn(core.W_NS, "ascii")), "Helvetica Neue"
            )
            self.assertIsNone(fonts.get(core.qn(core.W_NS, "asciiTheme")))
            self.assertEqual(
                heading_node.find("w:rPr/w:sz", namespaces=core.NS).get(
                    core.qn(core.W_NS, "val")
                ),
                "37",
            )
            self.assertEqual(
                heading_node.find("w:rPr/w:b", namespaces=core.NS).get(
                    core.qn(core.W_NS, "val")
                ),
                "0",
            )

            table_node = style_node(entries, part, "LightShading-Accent1")
            self.assertEqual(
                table_node.find("w:tblPr/w:shd", namespaces=core.NS).get(
                    core.qn(core.W_NS, "fill")
                ),
                "F7F7F7",
            )
            self.assertEqual(
                table_node.find(
                    "w:tblStylePr[@w:type='firstRow']/w:tcPr/w:shd",
                    namespaces=core.NS,
                ).get(core.qn(core.W_NS, "fill")),
                "165D52",
            )

        font_table = core.parse_xml(entries["word/fontTable.xml"], "fontTable.xml")
        font_names = set(
            font_table.xpath("./w:font/@w:name", namespaces=core.NS)
        )
        self.assertIn("Songti SC", font_names)
        self.assertIn("Helvetica Neue", font_names)

        with zipfile.ZipFile(derived_path) as archive:
            names = set(archive.namelist())
        self.assertNotIn("parts/word/document.xml", names)
        self.assertFalse(any("/media/" in name for name in names))
        self.assertFalse(any("vbaProject" in name for name in names))

    def test_heading_font_edit_also_updates_its_number_label(self) -> None:
        derived_path = self.working_dir / "numbered-customized.wfstyle"
        manager.derive_style_pack(
            self.numbered_pack,
            derived_path,
            {
                "styles": [
                    {
                        "style_id": "Heading2",
                        "font_east_asia": "PingFang SC",
                        "font_latin": "Aptos",
                        "size_pt": 16,
                        "bold": True,
                        "color_hex": "2F5597",
                    }
                ]
            },
        )
        manifest, entries = manager.load_style_pack(derived_path)
        rule = manifest["heading_numbering"]["Heading2"]
        _root, abstracts, nums, styles = core._numbering_index(entries)
        num_node = nums[str(rule["num_id"])]
        abstract = core._abstract_for_num(num_node, abstracts, nums, styles)
        level = core._level_node(abstract, int(rule["level"]))
        run_properties = level.find("w:rPr", namespaces=core.NS)
        fonts = run_properties.find("w:rFonts", namespaces=core.NS)
        self.assertEqual(fonts.get(core.qn(core.W_NS, "ascii")), "Aptos")
        self.assertEqual(
            fonts.get(core.qn(core.W_NS, "eastAsia")), "PingFang SC"
        )
        self.assertEqual(
            run_properties.find("w:sz", namespaces=core.NS).get(
                core.qn(core.W_NS, "val")
            ),
            "32",
        )
        self.assertEqual(
            run_properties.find("w:color", namespaces=core.NS).get(
                core.qn(core.W_NS, "val")
            ),
            "2F5597",
        )

    def test_legacy_pack_infers_and_persists_heading_numbering_for_font_edit(
        self,
    ) -> None:
        manifest, entries = manager.load_style_pack(self.numbered_pack)
        manifest.pop("heading_numbering", None)
        legacy_pack = self.working_dir / "legacy-numbered.wfstyle"
        write_pack_unchecked(legacy_pack, manifest, entries)

        derived_path = self.working_dir / "legacy-numbered-derived.wfstyle"
        manager.derive_style_pack(
            legacy_pack,
            derived_path,
            {
                "styles": [
                    {
                        "style_id": "Heading2",
                        "font_east_asia": "PingFang SC",
                        "font_latin": "Aptos",
                    }
                ]
            },
        )

        derived, derived_entries = manager.load_style_pack(derived_path)
        self.assertIn("Heading2", derived["heading_numbering"])
        rule = derived["heading_numbering"]["Heading2"]
        _root, abstracts, nums, styles = core._numbering_index(derived_entries)
        num_node = nums[str(rule["num_id"])]
        abstract = core._abstract_for_num(num_node, abstracts, nums, styles)
        level = core._level_node(abstract, int(rule["level"]))
        fonts = level.find("w:rPr/w:rFonts", namespaces=core.NS)
        self.assertEqual(fonts.get(core.qn(core.W_NS, "ascii")), "Aptos")
        self.assertEqual(
            fonts.get(core.qn(core.W_NS, "eastAsia")), "PingFang SC"
        )

    def test_new_table_first_row_style_is_inserted_before_extension_list(
        self,
    ) -> None:
        manifest, entries = manager.load_style_pack(self.source_pack)
        for part in ("word/styles.xml", "word/stylesWithEffects.xml"):
            root = core.parse_xml(entries[part], part)
            table_style = root.xpath(
                "./w:style[@w:styleId='LightShading-Accent1']",
                namespaces=core.NS,
            )[0]
            for node in list(
                table_style.xpath(
                    "./w:tblStylePr[@w:type='firstRow']", namespaces=core.NS
                )
            ):
                table_style.remove(node)
            extension_list = table_style.find("w:extLst", namespaces=core.NS)
            if extension_list is None:
                extension_list = etree.SubElement(
                    table_style, core.qn(core.W_NS, "extLst")
                )
            entries[part] = core.serialize_xml(root)
        source = self.working_dir / "table-ext-list-source.wfstyle"
        write_pack_unchecked(source, manifest, entries)

        output = self.working_dir / "table-ext-list-derived.wfstyle"
        manager.derive_style_pack(
            source,
            output,
            {
                "styles": [
                    {
                        "style_id": "LightShading-Accent1",
                        "table_accent_hex": "165D52",
                    }
                ]
            },
        )
        _derived, derived_entries = manager.load_style_pack(output)
        for part in ("word/styles.xml", "word/stylesWithEffects.xml"):
            table_style = style_node(
                derived_entries, part, "LightShading-Accent1"
            )
            children = [etree.QName(child).localname for child in table_style]
            self.assertLess(children.index("tblStylePr"), children.index("extLst"))

    def test_default_derived_name_inherits_source_privacy_marker(self) -> None:
        manifest, entries = manager.load_style_pack(self.source_pack)
        manifest["privacy"]["display_name_derived_from_source"] = True
        source_derived_name = self.working_dir / "source-derived-name.wfstyle"
        write_pack_unchecked(source_derived_name, manifest, entries)
        inherited_output = self.working_dir / "name-inherited.wfstyle"
        inherited = manager.derive_style_pack(
            source_derived_name,
            inherited_output,
            {"styles": [{"style_id": "Normal", "size_pt": 12}]},
        )
        self.assertIs(
            inherited["privacy"]["display_name_derived_from_source"], True
        )

        manifest["privacy"]["display_name_derived_from_source"] = False
        independent_source = self.working_dir / "independent-name-source.wfstyle"
        write_pack_unchecked(independent_source, manifest, entries)
        independent_output = self.working_dir / "independent-name-derived.wfstyle"
        independent = manager.derive_style_pack(
            independent_source,
            independent_output,
            {"styles": [{"style_id": "Normal", "size_pt": 12}]},
        )
        self.assertIs(
            independent["privacy"]["display_name_derived_from_source"], False
        )

    def test_derived_pack_applies_without_the_original_template(self) -> None:
        disposable_pack = self.working_dir / "disposable.wfstyle"
        shutil.copy2(self.source_pack, disposable_pack)
        derived_path = self.working_dir / "standalone-derived.wfstyle"
        manager.derive_style_pack(
            disposable_pack,
            derived_path,
            {"styles": [{"style_id": "Normal", "size_pt": 12}]},
        )
        disposable_pack.unlink()

        output = self.working_dir / "derived-output.docx"
        manager.apply_style_pack(derived_path, FIXTURES / "target.docx", output)
        self.assertTrue(output.is_file())
        with zipfile.ZipFile(output) as archive:
            styles = core.parse_xml(archive.read("word/styles.xml"), "styles.xml")
        normal = styles.xpath(
            "./w:style[@w:styleId='Normal']", namespaces=core.NS
        )[0]
        self.assertEqual(
            normal.find("w:rPr/w:sz", namespaces=core.NS).get(
                core.qn(core.W_NS, "val")
            ),
            "24",
        )

    def test_invalid_edits_are_rejected_without_creating_output(self) -> None:
        cases = (
            ({"styles": [{"style_id": "UnknownStyle", "size_pt": 12}]},),
            ({"styles": [{"style_id": "Heading1", "size_pt": 12.25}]},),
            ({"styles": [{"style_id": "Heading1", "color_hex": "red"}]},),
            (
                {
                    "styles": [
                        {"style_id": "Heading1", "table_fill_hex": "FFFFFF"}
                    ]
                },
            ),
            (
                {
                    "styles": [
                        {
                            "style_id": "LightShading-Accent1",
                            "font_latin": "Arial",
                        }
                    ]
                },
            ),
            ({"styles": [{"style_id": "Heading1", "shadow": True}]},),
        )
        for index, (payload,) in enumerate(cases):
            with self.subTest(payload=payload):
                output = self.working_dir / ("invalid-%d.wfstyle" % index)
                with self.assertRaises(core.TransferError):
                    manager.derive_style_pack(self.source_pack, output, payload)
                self.assertFalse(output.exists())

        for index, size in enumerate((math.nan, math.inf, -math.inf, 10**400)):
            with self.subTest(size=size):
                output = self.working_dir / ("invalid-number-%d.wfstyle" % index)
                with self.assertRaisesRegex(core.TransferError, "字号"):
                    manager.derive_style_pack(
                        self.source_pack,
                        output,
                        {"styles": [{"style_id": "Heading1", "size_pt": size}]},
                    )
                self.assertFalse(output.exists())

        with self.assertRaisesRegex(core.TransferError, "超过 1 MB"):
            manager._read_edits_payload(
                " " * (manager.MAX_EDITS_JSON_BYTES + 1), None
            )

    def test_input_pack_can_never_be_overwritten(self) -> None:
        original = self.source_pack.read_bytes()
        with self.assertRaisesRegex(core.TransferError, "不能覆盖原文件"):
            manager.derive_style_pack(
                self.source_pack,
                self.source_pack,
                {"styles": [{"style_id": "Normal", "size_pt": 12}]},
                force=True,
            )
        self.assertEqual(self.source_pack.read_bytes(), original)

        hard_link = self.working_dir / "source-hard-link.wfstyle"
        os.link(self.source_pack, hard_link)
        with self.assertRaisesRegex(core.TransferError, "不能覆盖原文件"):
            manager.derive_style_pack(
                self.source_pack,
                hard_link,
                {"styles": [{"style_id": "Normal", "size_pt": 12}]},
                force=True,
            )
        self.assertEqual(self.source_pack.read_bytes(), original)

    def test_duplicate_style_id_is_rejected_even_when_types_differ(self) -> None:
        manifest, entries = manager.load_style_pack(self.source_pack)
        root = core.parse_xml(entries["word/styles.xml"], "styles.xml")
        duplicate = copy.deepcopy(
            root.xpath(
                "./w:style[@w:styleId='Heading1']", namespaces=core.NS
            )[0]
        )
        duplicate.set(core.qn(core.W_NS, "type"), "character")
        root.append(duplicate)
        entries["word/styles.xml"] = core.serialize_xml(root)
        malformed = self.working_dir / "duplicate-style-id.wfstyle"
        write_pack_unchecked(malformed, manifest, entries)

        output = self.working_dir / "duplicate-style-output.wfstyle"
        with self.assertRaisesRegex(core.TransferError, "重复的样式 ID"):
            manager.derive_style_pack(
                malformed,
                output,
                {"styles": [{"style_id": "Heading1", "size_pt": 12}]},
            )
        self.assertFalse(output.exists())

    def test_atomic_write_failure_cleans_temporary_pack(self) -> None:
        output = self.working_dir / "atomic-failure.wfstyle"
        original = self.source_pack.read_bytes()
        with mock.patch.object(
            manager.os, "replace", side_effect=OSError("simulated rename failure")
        ):
            with self.assertRaisesRegex(OSError, "simulated rename failure"):
                manager.derive_style_pack(
                    self.source_pack,
                    output,
                    {"styles": [{"style_id": "Normal", "size_pt": 12}]},
                )
        self.assertFalse(output.exists())
        self.assertFalse(
            list(self.working_dir.glob(".atomic-failure.wfstyle.*.tmp"))
        )
        self.assertEqual(self.source_pack.read_bytes(), original)

    def test_schema_validation_and_same_schema_legacy_compatibility(self) -> None:
        manifest, entries = manager.load_style_pack(self.source_pack)

        legacy_manifest = copy.deepcopy(manifest)
        for field in (
            "heading_authorities",
            "heading_numbering",
            "heading_paragraph_indents",
            "inferred_heading_styles",
            "inferred_style_count",
            "privacy",
        ):
            legacy_manifest.pop(field, None)
        legacy_path = self.working_dir / "legacy-v1.wfstyle"
        write_pack_unchecked(legacy_path, legacy_manifest, entries)
        legacy_output = self.working_dir / "legacy-v1-derived.wfstyle"
        derived = manager.derive_style_pack(
            legacy_path,
            legacy_output,
            {"styles": [{"style_id": "Normal", "size_pt": 12}]},
        )
        self.assertEqual(derived["schema_version"], manager.PACK_SCHEMA_VERSION)
        self.assertTrue(derived["privacy"]["derived_without_source_document"])
        manager.load_style_pack(legacy_output)

        for label, schema in (
            ("future", manager.PACK_SCHEMA_VERSION + 1),
            ("boolean", True),
        ):
            unsupported_manifest = copy.deepcopy(manifest)
            unsupported_manifest["schema_version"] = schema
            unsupported_path = self.working_dir / (label + "-schema.wfstyle")
            write_pack_unchecked(unsupported_path, unsupported_manifest, entries)
            unsupported_output = self.working_dir / (
                label + "-schema-derived.wfstyle"
            )
            with self.assertRaisesRegex(core.TransferError, "版本不受支持"):
                manager.derive_style_pack(
                    unsupported_path,
                    unsupported_output,
                    {"styles": [{"style_id": "Normal", "size_pt": 12}]},
                )
            self.assertFalse(unsupported_output.exists())

    def test_derive_pack_cli_returns_the_new_manifest(self) -> None:
        output = self.working_dir / "cli-derived.wfstyle"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = manager.main(
                [
                    "derive-pack",
                    "--pack",
                    str(self.source_pack),
                    "--out",
                    str(output),
                    "--name",
                    "命令行派生方案",
                    "--edits-json",
                    json.dumps(
                        {
                            "styles": [
                                {"style_id": "Normal", "size_pt": 12.5}
                            ]
                        },
                        ensure_ascii=False,
                    ),
                ]
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["pack"]["name"], "命令行派生方案")
        self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
