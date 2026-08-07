#!/usr/bin/env python3
"""Regression tests for persistent, privacy-safe Word style packs."""

from __future__ import annotations

import json
import shutil
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

import style_pack_manager as manager  # noqa: E402
import word_style_transfer as core  # noqa: E402


W_NS = core.W_NS
R_NS = core.R_NS
NS = {"w": W_NS, "r": R_NS}


def qn(local: str) -> str:
    return "{%s}%s" % (W_NS, local)


def read_zip(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def xml(entries: dict[str, bytes], name: str) -> etree._Element:
    return etree.fromstring(entries[name])


def paragraph_for_text(root: etree._Element, text: str) -> etree._Element:
    for paragraph in root.xpath("//w:p", namespaces=NS):
        value = "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))
        if text in value:
            return paragraph
    raise AssertionError("paragraph not found: %s" % text)


def numbering_definition(
    root: etree._Element, num_id: str
) -> tuple[etree._Element, etree._Element]:
    concrete = root.xpath(
        "./w:num[@w:numId=$num_id]", namespaces=NS, num_id=num_id
    )
    if len(concrete) != 1:
        raise AssertionError("numId does not resolve: %s" % num_id)
    abstract_id = concrete[0].xpath(
        "string(w:abstractNumId/@w:val)", namespaces=NS
    )
    abstract = root.xpath(
        "./w:abstractNum[@w:abstractNumId=$abstract_id]",
        namespaces=NS,
        abstract_id=abstract_id,
    )
    if len(abstract) != 1:
        raise AssertionError("abstractNum does not resolve: %s" % abstract_id)
    return concrete[0], abstract[0]


class StylePackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(prefix="word-style-pack-tests-")
        cls.working_dir = Path(cls._temporary.name)
        cls.library_dir = cls.working_dir / "library"
        cls.library_dir.mkdir()

        # Use a disposable source and remove it immediately after creating the
        # pack.  Every application assertion below therefore exercises the
        # stored pack without passing or retaining the original source path.
        cls.source_copy = cls.working_dir / "disposable-format-source.docx"
        shutil.copy2(FIXTURES / "source.docx", cls.source_copy)
        cls.expected_source_entries = read_zip(cls.source_copy)
        cls.pack_path = cls.library_dir / "fixture-style.wfstyle"
        cls.created_manifest = manager.create_style_pack(
            cls.source_copy,
            cls.pack_path,
            display_name="测试格式库",
        )
        cls.source_copy.unlink()

        cls.manifest, cls.pack_entries = manager.load_style_pack(cls.pack_path)
        cls.target_entries = read_zip(FIXTURES / "target.docx")
        cls.output_path = cls.working_dir / "pack-transferred.docx"
        cls.applied_manifest, cls.stats = manager.apply_style_pack(
            cls.pack_path,
            FIXTURES / "target.docx",
            cls.output_path,
        )
        cls.output_entries = read_zip(cls.output_path)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_default_display_name_is_marked_as_source_derived(self) -> None:
        with tempfile.TemporaryDirectory(prefix="default-pack-name-") as root:
            default_pack = Path(root) / "default-name.wfstyle"
            created = manager.create_style_pack(
                FIXTURES / "source.docx",
                default_pack,
            )
            self.assertEqual(created["name"], "source")
            self.assertIs(
                created["privacy"]["display_name_derived_from_source"],
                True,
            )

    def test_only_actually_used_styles_are_exposed(self) -> None:
        formats = self.manifest["used_formats"]
        used_ids = [
            item["style_id"]
            for item in formats
            if not item.get("inferred", False)
        ]
        self.assertEqual(
            used_ids,
            [
                "Heading1",
                "Heading2",
                "Heading3",
                "Normal",
                "Footer",
                "Header",
                "SourceCallout",
                "LightShading-Accent1",
            ],
        )
        self.assertEqual(self.manifest["used_style_count"], len(used_ids))
        inferred_ids = [
            item["style_id"]
            for item in formats
            if item.get("inferred", False)
        ]
        self.assertEqual(inferred_ids, ["Heading4", "Heading5"])
        self.assertEqual(self.manifest["inferred_style_count"], 2)

        # The source template defines many built-in styles that it never uses;
        # they must not leak into the user-facing list.
        styles_root = xml(self.expected_source_entries, "word/styles.xml")
        defined_ids = set(
            styles_root.xpath("//w:style/@w:styleId", namespaces=NS)
        )
        for unused in ("Title", "Subtitle", "Quote", "Emphasis", "ListNumber"):
            self.assertIn(unused, defined_ids)
            self.assertNotIn(unused, used_ids)

        by_id = {item["style_id"]: item for item in formats}
        self.assertEqual(by_id["Heading1"]["usage_count"], 1)
        self.assertEqual(by_id["Normal"]["usage_count"], 5)
        self.assertEqual(by_id["Header"]["usage_count"], 1)
        self.assertEqual(by_id["Footer"]["usage_count"], 1)
        self.assertEqual(by_id["LightShading-Accent1"]["usage_count"], 1)

    def test_preview_resolves_effective_size_font_and_color(self) -> None:
        by_id = {
            item["style_id"]: item for item in self.manifest["used_formats"]
        }
        expected_headings = {
            "Heading1": (20.0, "165D52", 0),
            "Heading2": (15.0, "2F5597", 1),
            "Heading3": (12.0, "703A13", 2),
        }
        for style_id, (size, color, outline) in expected_headings.items():
            preview = by_id[style_id]
            self.assertEqual(preview["size_pt"], size)
            self.assertEqual(preview["color_hex"], color)
            self.assertEqual(preview["outline_level"], outline)
            self.assertIs(preview["bold"], True)
            self.assertEqual(preview["font_latin"], "Arial")
            self.assertEqual(preview["font_east_asia"], "Hiragino Sans GB")

        self.assertEqual(by_id["Normal"]["size_pt"], 11.0)
        self.assertEqual(by_id["Normal"]["color_hex"], "222222")
        self.assertEqual(by_id["Normal"]["line_spacing"], 1.25)
        self.assertEqual(by_id["SourceCallout"]["size_pt"], 10.0)
        self.assertEqual(by_id["SourceCallout"]["color_hex"], "165D52")
        self.assertIs(by_id["SourceCallout"]["italic"], True)

    def test_pack_contains_formatting_only_and_no_source_content(self) -> None:
        self.assertFalse(self.source_copy.exists())
        raw_pack = read_zip(self.pack_path)
        names = {name.casefold() for name in raw_pack}
        self.assertIn("manifest.json", names)
        self.assertIn("parts/word/styles.xml", names)

        forbidden_exact = {
            "parts/word/document.xml",
            "parts/word/document2.xml",
        }
        self.assertTrue(forbidden_exact.isdisjoint(names))
        forbidden_fragments = (
            "/header",
            "/footer",
            "/comments",
            "/footnotes",
            "/endnotes",
            "/media/",
            "/embeddings/",
            "/customxml/",
            "vbaproject",
            "vbaData".casefold(),
        )
        for name in names:
            for fragment in forbidden_fragments:
                self.assertNotIn(fragment, name, name)

        combined = b"\n".join(raw_pack.values())
        source_only_text = (
            "格式源示例",
            "这段内容只用于定义源文件的正文外观。",
            "源文件提示框样式",
            "源表头 A",
            "源值 2",
            "源文件页眉格式示例",
            "源文件页脚格式示例",
        )
        for text in source_only_text:
            self.assertNotIn(text.encode("utf-8"), combined, text)

        privacy = self.manifest["privacy"]
        self.assertIs(privacy["source_path_stored"], False)
        self.assertIs(privacy["source_file_name_stored"], False)
        self.assertIs(privacy["source_text_stored"], False)
        self.assertIs(privacy["source_media_stored"], False)
        self.assertIs(privacy["embedded_fonts_stored"], False)
        self.assertIs(privacy["generic_samples_only"], True)
        self.assertIs(privacy["display_name_derived_from_source"], False)

    def test_pack_applies_after_source_is_deleted_and_preserves_target(self) -> None:
        self.assertFalse(self.source_copy.exists())
        self.assertTrue(self.output_path.is_file())
        self.assertEqual(self.applied_manifest["id"], self.manifest["id"])

        output = self.output_entries
        document = xml(output, "word/document.xml")
        document_text = "".join(document.xpath("//w:t/text()", namespaces=NS))
        self.assertIn("目标文档主标题", document_text)
        self.assertIn("目标独有样式段落", document_text)
        self.assertIn("正文含有手工粗体、斜体、字号和颜色。", document_text)
        self.assertNotIn("格式源示例", document_text)

        headers = "".join(
            "".join(xml(output, name).xpath("//w:t/text()", namespaces=NS))
            for name in output
            if name.startswith("word/header") and name.endswith(".xml")
        )
        footers = "".join(
            "".join(xml(output, name).xpath("//w:t/text()", namespaces=NS))
            for name in output
            if name.startswith("word/footer") and name.endswith(".xml")
        )
        self.assertIn("必须保留的目标页眉内容", headers)
        self.assertIn("必须保留的目标页脚内容", footers)
        self.assertNotIn("源文件页眉格式示例", headers)
        self.assertNotIn("源文件页脚格式示例", footers)

        target_media = {
            name: data
            for name, data in self.target_entries.items()
            if name.startswith("word/media/")
        }
        self.assertTrue(target_media)
        for name, data in target_media.items():
            self.assertEqual(output.get(name), data, name)

    def test_output_uses_packed_format_parts_and_page_geometry(self) -> None:
        output = self.output_entries
        source = self.expected_source_entries
        packed = self.pack_entries
        self.assertEqual(
            etree.tostring(etree.fromstring(output["word/styles.xml"])),
            etree.tostring(etree.fromstring(packed["word/styles.xml"])),
        )
        for name in ("word/theme/theme1.xml", "word/fontTable.xml"):
            self.assertIn(name, packed)
            # Repackaging may normalize harmless trailing XML whitespace.
            self.assertEqual(
                etree.tostring(etree.fromstring(output[name])),
                etree.tostring(etree.fromstring(packed[name])),
                name,
            )
        packed_numbering = xml(packed, "word/numbering.xml")
        output_numbering = xml(output, "word/numbering.xml")
        for node in packed_numbering:
            local = etree.QName(node).localname
            attribute = {
                "abstractNum": "abstractNumId",
                "num": "numId",
            }.get(local)
            if attribute is None:
                continue
            identifier = node.get(qn(attribute))
            matches = output_numbering.xpath(
                "./w:%s[@w:%s=$identifier]" % (local, attribute),
                namespaces=NS,
                identifier=identifier,
            )
            self.assertEqual(len(matches), 1, (local, identifier))
            self.assertEqual(
                etree.tostring(matches[0]), etree.tostring(node), identifier
            )

        source_doc = xml(source, "word/document.xml")
        target_doc = xml(self.target_entries, "word/document.xml")
        output_doc = xml(output, "word/document.xml")
        source_section = source_doc.xpath("//w:sectPr", namespaces=NS)[-1]
        target_section = target_doc.xpath("//w:sectPr", namespaces=NS)[-1]
        output_section = output_doc.xpath("//w:sectPr", namespaces=NS)[-1]
        for tag in ("pgSz", "pgMar", "cols", "docGrid"):
            source_node = source_section.find("w:%s" % tag, NS)
            output_node = output_section.find("w:%s" % tag, NS)
            if source_node is None:
                self.assertIsNone(output_node, tag)
            else:
                self.assertEqual(
                    etree.tostring(output_node), etree.tostring(source_node), tag
                )

        # Applying source page geometry must not replace target header/footer
        # relationships or their content parts.
        for tag in ("headerReference", "footerReference"):
            target_refs = [
                node.get("{%s}id" % R_NS)
                for node in target_section.findall("w:%s" % tag, NS)
            ]
            output_refs = [
                node.get("{%s}id" % R_NS)
                for node in output_section.findall("w:%s" % tag, NS)
            ]
            self.assertEqual(output_refs, target_refs, tag)

        heading = paragraph_for_text(output_doc, "目标文档主标题")
        self.assertEqual(
            heading.find("w:pPr/w:pStyle", NS).get(qn("val")), "Heading1"
        )
        unknown = paragraph_for_text(output_doc, "目标独有样式段落")
        self.assertEqual(
            unknown.find("w:pPr/w:pStyle", NS).get(qn("val")), "Normal"
        )
        table_styles = output_doc.xpath(
            "//w:tblPr/w:tblStyle/@w:val", namespaces=NS
        )
        self.assertEqual(table_styles[0], "LightShading-Accent1")

        self.assertGreaterEqual(self.stats.source_format_parts_copied, 4)
        self.assertGreater(self.stats.paragraph_properties_removed, 0)
        self.assertGreater(self.stats.run_properties_removed, 0)
        self.assertGreater(self.stats.table_properties_removed, 0)

    def test_direct_visual_formatting_is_cleared(self) -> None:
        allowed_run = core.RUN_SEMANTIC_KEEP
        for name, data in self.output_entries.items():
            if not core.is_content_part(name):
                continue
            root = etree.fromstring(data)
            for ppr in root.xpath("//w:p/w:pPr", namespaces=NS):
                self.assertTrue(
                    {etree.QName(node).localname for node in ppr}.issubset(
                        {"pStyle", "sectPr", "numPr"}
                    ),
                    name,
                )
            for rpr in root.xpath("//w:r/w:rPr", namespaces=NS):
                self.assertTrue(
                    {etree.QName(node).localname for node in rpr}.issubset(
                        allowed_run
                    ),
                    name,
                )
            self.assertFalse(root.xpath("//w:tcPr/w:shd", namespaces=NS), name)
            self.assertFalse(
                root.xpath("//w:tblPr/w:tblBorders", namespaces=NS), name
            )

        document = xml(self.output_entries, "word/document.xml")
        list_paragraph = paragraph_for_text(document, "目标编号列表项目")
        num_ids = list_paragraph.xpath(
            "w:pPr/w:numPr/w:numId/@w:val", namespaces=NS
        )
        self.assertEqual(len(num_ids), 1)
        numbering_definition(
            xml(self.output_entries, "word/numbering.xml"), str(num_ids[0])
        )
        self.assertEqual(self.stats.style_list_paragraphs_materialized, 1)

    def test_list_library_returns_valid_pack(self) -> None:
        result = manager.list_library(self.library_dir)
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["packs"]), 1)
        listed = result["packs"][0]
        self.assertEqual(listed["id"], self.manifest["id"])
        self.assertEqual(listed["name"], "测试格式库")
        self.assertEqual(Path(listed["pack_path"]).resolve(), self.pack_path.resolve())
        self.assertEqual(listed["used_style_count"], 8)

    def test_damaged_and_unsupported_packs_are_rejected(self) -> None:
        invalid_dir = self.working_dir / "invalid"
        invalid_dir.mkdir(exist_ok=True)

        damaged = invalid_dir / "damaged.wfstyle"
        damaged.write_bytes(b"not a zip archive")
        with self.assertRaisesRegex(core.TransferError, "损坏"):
            manager.load_style_pack(damaged)

        unsupported = invalid_dir / "future.wfstyle"
        with zipfile.ZipFile(unsupported, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "manifest.json",
                json.dumps({"schema_version": manager.PACK_SCHEMA_VERSION + 1}),
            )
        with self.assertRaisesRegex(core.TransferError, "版本不受支持"):
            manager.load_style_pack(unsupported)


if __name__ == "__main__":
    unittest.main(verbosity=2)
