#!/usr/bin/env python3
"""端到端回归：直接把格式源迁移到目标文档（不经过 .wfstyle 格式库）。"""

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


W_NS = core.W_NS
R_NS = core.R_NS
NS = {"w": W_NS, "r": R_NS}

# source.docx 实际只使用了标题一至标题三，引擎会按 README 描述的规则补全
# 标题四、标题五，因此这两个样式节点必然与格式源不同。
SYNTHESIZED_HEADINGS = {"Heading4": 3, "Heading5": 4}


def qn(local):
    return "{%s}%s" % (W_NS, local)


def read_zip(path):
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def xml(entries, name):
    return etree.fromstring(entries[name])


def paragraph_for_text(root, text):
    for paragraph in root.xpath("//w:p", namespaces=NS):
        value = "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))
        if text in value:
            return paragraph
    raise AssertionError("paragraph not found: %s" % text)


def styles_by_id(entries):
    root = xml(entries, "word/styles.xml")
    return {
        node.get(qn("styleId")): node
        for node in root.findall(qn("style"))
    }


def styles_without(entries, style_ids):
    """返回剔除指定样式后的 styles.xml 规范化字节，用于比较"其余部分未被改动"。"""
    root = xml(entries, "word/styles.xml")
    for node in root.findall(qn("style")):
        if node.get(qn("styleId")) in style_ids:
            root.remove(node)
    return etree.tostring(root, method="c14n")


class TransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="word-transfer-tests-")
        output_path = Path(cls._tmp.name) / "transferred.docx"
        cls.stats = core.transfer(
            FIXTURES / "source.docx",
            FIXTURES / "target.docx",
            output_path,
        )
        cls.source = read_zip(FIXTURES / "source.docx")
        cls.target = read_zip(FIXTURES / "target.docx")
        cls.output = read_zip(output_path)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_styles_come_from_source_except_synthesized_headings(self):
        source_styles = styles_by_id(self.source)
        output_styles = styles_by_id(self.output)
        self.assertEqual(set(output_styles), set(source_styles))

        # 格式源真实使用过的层级必须原样保留。
        for style_id in ("Heading1", "Heading2", "Heading3"):
            self.assertEqual(
                etree.tostring(output_styles[style_id]),
                etree.tostring(source_styles[style_id]),
                style_id,
            )

        # 除智能补全的标题外，styles.xml 的其余内容逐字节一致。
        self.assertEqual(
            styles_without(self.output, SYNTHESIZED_HEADINGS),
            styles_without(self.source, SYNTHESIZED_HEADINGS),
        )

    def test_synthesized_headings_get_correct_outline_levels(self):
        source_styles = styles_by_id(self.source)
        output_styles = styles_by_id(self.output)
        for style_id, expected_outline in SYNTHESIZED_HEADINGS.items():
            with self.subTest(style=style_id):
                self.assertNotEqual(
                    etree.tostring(output_styles[style_id]),
                    etree.tostring(source_styles[style_id]),
                    "智能补全应当重写未被真实使用的标题层级",
                )
                outline = output_styles[style_id].find(
                    "w:pPr/w:outlineLvl", NS
                )
                self.assertIsNotNone(outline)
                self.assertEqual(outline.get(qn("val")), str(expected_outline))

    def test_optional_format_parts_match_source(self):
        for optional in (
            "word/theme/theme1.xml",
            "word/fontTable.xml",
            "word/numbering.xml",
        ):
            if optional in self.source:
                with self.subTest(part=optional):
                    self.assertEqual(self.output[optional], self.source[optional])

    def test_target_content_survives(self):
        document = xml(self.output, "word/document.xml")
        text = "".join(document.xpath("//w:t/text()", namespaces=NS))
        self.assertIn("目标文档主标题", text)
        self.assertIn("目标独有样式段落", text)
        self.assertNotIn("格式源示例", text)

    def test_styles_are_remapped_on_target_paragraphs(self):
        document = xml(self.output, "word/document.xml")
        heading = paragraph_for_text(document, "目标文档主标题")
        self.assertEqual(
            heading.find("w:pPr/w:pStyle", NS).get(qn("val")), "Heading1"
        )

        target_only = paragraph_for_text(document, "目标独有样式段落")
        pstyle = target_only.find("w:pPr/w:pStyle", NS)
        self.assertIsNotNone(pstyle)
        self.assertEqual(pstyle.get(qn("val")), "Normal")

    def test_headers_footers_and_media_stay_target_owned(self):
        headers = "".join(
            "".join(xml(self.output, name).xpath("//w:t/text()", namespaces=NS))
            for name in self.output
            if name.startswith("word/header") and name.endswith(".xml")
        )
        footers = "".join(
            "".join(xml(self.output, name).xpath("//w:t/text()", namespaces=NS))
            for name in self.output
            if name.startswith("word/footer") and name.endswith(".xml")
        )
        self.assertIn("必须保留的目标页眉内容", headers)
        self.assertIn("必须保留的目标页脚内容", footers)

        for name, data in self.target.items():
            if name.startswith("word/media/"):
                with self.subTest(media=name):
                    self.assertEqual(self.output.get(name), data)

    def test_page_geometry_from_source_but_header_refs_from_target(self):
        document = xml(self.output, "word/document.xml")
        source_sect = xml(self.source, "word/document.xml").xpath(
            "//w:sectPr", namespaces=NS
        )[-1]
        target_sect = xml(self.target, "word/document.xml").xpath(
            "//w:sectPr", namespaces=NS
        )[-1]
        output_sect = document.xpath("//w:sectPr", namespaces=NS)[-1]

        for tag in ("pgSz", "pgMar", "cols", "docGrid"):
            with self.subTest(tag=tag):
                source_node = source_sect.find("w:%s" % tag, NS)
                output_node = output_sect.find("w:%s" % tag, NS)
                if source_node is None:
                    self.assertIsNone(output_node)
                else:
                    self.assertEqual(
                        etree.tostring(output_node), etree.tostring(source_node)
                    )

        for tag in ("headerReference", "footerReference"):
            with self.subTest(tag=tag):
                target_refs = [
                    node.get("{%s}id" % R_NS)
                    for node in target_sect.findall("w:%s" % tag, NS)
                ]
                output_refs = [
                    node.get("{%s}id" % R_NS)
                    for node in output_sect.findall("w:%s" % tag, NS)
                ]
                self.assertEqual(output_refs, target_refs)

    def test_unknown_target_table_style_is_replaced(self):
        document = xml(self.output, "word/document.xml")
        table_styles = document.xpath(
            "//w:tblPr/w:tblStyle/@w:val", namespaces=NS
        )
        self.assertTrue(table_styles)
        self.assertEqual(table_styles[0], "LightShading-Accent1")

    def test_direct_visual_formatting_is_cleared(self):
        for name, data in self.output.items():
            if not core.is_content_part(name):
                continue
            root = etree.fromstring(data)
            for ppr in root.xpath("//w:p/w:pPr", namespaces=NS):
                self.assertTrue(
                    {etree.QName(x).localname for x in ppr}.issubset(
                        {"pStyle", "sectPr"}
                    ),
                    name,
                )
            for rpr in root.xpath("//w:r/w:rPr", namespaces=NS):
                self.assertTrue(
                    {etree.QName(x).localname for x in rpr}.issubset(
                        core.RUN_SEMANTIC_KEEP
                    ),
                    name,
                )
            self.assertFalse(root.xpath("//w:numPr", namespaces=NS), name)
            self.assertFalse(root.xpath("//w:tcPr/w:shd", namespaces=NS), name)
            self.assertFalse(
                root.xpath("//w:tblPr/w:tblBorders", namespaces=NS), name
            )

    def test_stats_report_the_work_done(self):
        self.assertGreaterEqual(self.stats.content_parts_cleaned, 3)
        self.assertGreater(self.stats.paragraph_properties_removed, 0)
        self.assertGreater(self.stats.run_properties_removed, 0)
        self.assertGreater(self.stats.table_properties_removed, 0)
        self.assertGreaterEqual(self.stats.source_format_parts_copied, 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
