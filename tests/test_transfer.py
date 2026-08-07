#!/usr/bin/env python3
"""End-to-end release-gate coverage for direct source/target transfer."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from lxml import etree


TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
FIXTURES = TEST_DIR / "fixtures"
ENGINE = PROJECT_DIR / "word_style_transfer.py"

spec = importlib.util.spec_from_file_location("word_style_transfer", ENGINE)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)

W_NS = module.W_NS
R_NS = module.R_NS
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


def semantic_xml(node: etree._Element) -> tuple[object, ...]:
    """Compare OOXML meaning without depending on prefixes or serialization."""
    return (
        node.tag,
        tuple(sorted(node.attrib.items())),
        node.text or "",
        tuple(semantic_xml(child) for child in node),
    )


def style_node(root: etree._Element, style_id: str) -> etree._Element:
    nodes = root.xpath(
        "./w:style[@w:styleId=$style_id]",
        namespaces=NS,
        style_id=style_id,
    )
    if len(nodes) != 1:
        raise AssertionError("style not found exactly once: %s" % style_id)
    return nodes[0]


class TransferEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(
            prefix="forma-transfer-release-gate-"
        )
        self.output = Path(self.tempdir.name) / "transferred.docx"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def assert_clean_visual_format(self, entries: dict[str, bytes]) -> None:
        allowed_run = module.RUN_SEMANTIC_KEEP
        for name, data in entries.items():
            if not module.is_content_part(name):
                continue
            root = etree.fromstring(data)
            for ppr in root.xpath("//w:p/w:pPr", namespaces=NS):
                self.assertTrue(
                    {
                        etree.QName(child).localname for child in ppr
                    }.issubset({"pStyle", "sectPr", "numPr"}),
                    name,
                )
            for rpr in root.xpath("//w:r/w:rPr", namespaces=NS):
                self.assertTrue(
                    {
                        etree.QName(child).localname for child in rpr
                    }.issubset(allowed_run),
                    name,
                )
            self.assertFalse(root.xpath("//w:tcPr/w:shd", namespaces=NS), name)
            self.assertFalse(
                root.xpath("//w:tblPr/w:tblBorders", namespaces=NS), name
            )

    def test_transfer_preserves_target_content_and_imports_format_semantics(self) -> None:
        stats = module.transfer(
            FIXTURES / "source.docx",
            FIXTURES / "target.docx",
            self.output,
        )
        source = read_zip(FIXTURES / "source.docx")
        target = read_zip(FIXTURES / "target.docx")
        output = read_zip(self.output)

        # H4/H5 are intentionally synthesized from the source hierarchy, so
        # styles.xml is not expected to be byte-for-byte identical.  The
        # source-owned styles that are already authoritative must remain
        # structurally equal.
        source_styles = xml(source, "word/styles.xml")
        output_styles = xml(output, "word/styles.xml")
        for style_id in (
            "Normal",
            "Heading1",
            "Heading2",
            "Heading3",
            "LightShading-Accent1",
        ):
            self.assertEqual(
                semantic_xml(style_node(output_styles, style_id)),
                semantic_xml(style_node(source_styles, style_id)),
                style_id,
            )
        for style_id, level in (("Heading4", "3"), ("Heading5", "4")):
            generated = style_node(output_styles, style_id)
            self.assertEqual(
                generated.xpath(
                    "string(w:pPr/w:outlineLvl/@w:val)", namespaces=NS
                ),
                level,
            )

        for optional in (
            "word/theme/theme1.xml",
            "word/fontTable.xml",
        ):
            if optional in source:
                self.assertIn(optional, output)
                self.assertEqual(
                    semantic_xml(xml(output, optional)),
                    semantic_xml(xml(source, optional)),
                    optional,
                )
        source_numbering = xml(source, "word/numbering.xml")
        output_numbering = xml(output, "word/numbering.xml")
        for node in source_numbering:
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
                semantic_xml(matches[0]), semantic_xml(node), identifier
            )

        document = xml(output, "word/document.xml")
        text = "".join(document.xpath("//w:t/text()", namespaces=NS))
        self.assertIn("目标文档主标题", text)
        self.assertIn("目标独有样式段落", text)
        self.assertNotIn("格式源示例", text)

        heading = paragraph_for_text(document, "目标文档主标题")
        self.assertEqual(
            heading.find("w:pPr/w:pStyle", NS).get(qn("val")), "Heading1"
        )

        target_only = paragraph_for_text(document, "目标独有样式段落")
        pstyle = target_only.find("w:pPr/w:pStyle", NS)
        self.assertIsNotNone(pstyle)
        self.assertEqual(pstyle.get(qn("val")), "Normal")

        inherited_list = paragraph_for_text(document, "目标编号列表项目")
        inherited_num_ids = inherited_list.xpath(
            "w:pPr/w:numPr/w:numId/@w:val", namespaces=NS
        )
        self.assertEqual(len(inherited_num_ids), 1)
        concrete = output_numbering.xpath(
            "./w:num[@w:numId=$num_id]",
            namespaces=NS,
            num_id=str(inherited_num_ids[0]),
        )
        self.assertEqual(len(concrete), 1)
        self.assertEqual(stats.style_list_paragraphs_materialized, 1)

        # Target header/footer content and image media remain target-owned.
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
        target_media = {
            name: data
            for name, data in target.items()
            if name.startswith("word/media/")
        }
        for name, data in target_media.items():
            self.assertEqual(output.get(name), data, name)

        # Page geometry comes from source, while target header/footer
        # relationships stay attached to target-owned stories.
        source_doc = xml(source, "word/document.xml")
        target_doc = xml(target, "word/document.xml")
        source_sect = source_doc.xpath("//w:sectPr", namespaces=NS)[-1]
        target_sect = target_doc.xpath("//w:sectPr", namespaces=NS)[-1]
        output_sect = document.xpath("//w:sectPr", namespaces=NS)[-1]
        for tag in ("pgSz", "pgMar", "cols", "docGrid"):
            source_node = source_sect.find("w:%s" % tag, NS)
            output_node = output_sect.find("w:%s" % tag, NS)
            if source_node is None:
                self.assertIsNone(output_node)
            else:
                self.assertIsNotNone(output_node)
                self.assertEqual(
                    semantic_xml(output_node), semantic_xml(source_node), tag
                )
        for tag in ("headerReference", "footerReference"):
            target_refs = [
                node.get("{%s}id" % R_NS)
                for node in target_sect.findall("w:%s" % tag, NS)
            ]
            output_refs = [
                node.get("{%s}id" % R_NS)
                for node in output_sect.findall("w:%s" % tag, NS)
            ]
            self.assertEqual(output_refs, target_refs)

        table_styles = document.xpath(
            "//w:tblPr/w:tblStyle/@w:val", namespaces=NS
        )
        self.assertTrue(table_styles)
        self.assertEqual(table_styles[0], "LightShading-Accent1")

        self.assert_clean_visual_format(output)
        self.assertGreaterEqual(stats.content_parts_cleaned, 3)
        self.assertGreater(stats.paragraph_properties_removed, 0)
        self.assertGreater(stats.run_properties_removed, 0)
        self.assertGreater(stats.table_properties_removed, 0)
        self.assertGreaterEqual(stats.source_format_parts_copied, 4)


if __name__ == "__main__":
    unittest.main()
