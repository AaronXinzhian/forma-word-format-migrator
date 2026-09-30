#!/usr/bin/env python3
# [INPUT]: 依赖 __future__, sys, tempfile, unittest, zipfile, pathlib, typing, lxml, style_pack_manager, word_style_transfer
# [OUTPUT]: 提供 TEST_DIR, PROJECT_DIR, FIXTURES, NS, TARGET_HEADINGS, qn(), read_zip(), xml(), paragraph_for_text(), style_for_id(), effective_numbering_for_paragraph(), HeadingNumberingTests
# [POS]: 验证标题样式和直接编号规则的迁移
# [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
"""Regression coverage for transferring real multilevel heading numbering."""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Optional, Tuple

from lxml import etree


TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
FIXTURES = TEST_DIR / "fixtures"
sys.path.insert(0, str(PROJECT_DIR))

import style_pack_manager as manager  # noqa: E402
import word_style_transfer as core  # noqa: E402


NS = {"w": core.W_NS, "r": core.R_NS}
TARGET_HEADINGS = (
    (0, "项目概述"),
    (1, "建设目标"),
    (2, "技术路线"),
    (1, "验收标准"),
    (0, "实施安排"),
    (1, "交付清单"),
    (2, "质量要求"),
)


def qn(local: str) -> str:
    return "{%s}%s" % (core.W_NS, local)


def read_zip(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise AssertionError("damaged DOCX member: %s" % bad)
        return {name: archive.read(name) for name in archive.namelist()}


def xml(entries: dict[str, bytes], name: str) -> etree._Element:
    return etree.fromstring(entries[name])


def paragraph_for_text(root: etree._Element, text: str) -> etree._Element:
    for paragraph in root.xpath("//w:p", namespaces=NS):
        value = "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))
        if value == text:
            return paragraph
    raise AssertionError("paragraph not found: %s" % text)


def style_for_id(styles: etree._Element, style_id: str) -> etree._Element:
    matches = styles.xpath(
        "//w:style[@w:styleId=$style_id]",
        namespaces=NS,
        style_id=style_id,
    )
    if len(matches) != 1:
        raise AssertionError("style not found exactly once: %s" % style_id)
    return matches[0]


def _num_pr_values(num_pr: etree._Element) -> Tuple[str, int]:
    num_id = num_pr.find("w:numId", namespaces=NS)
    ilvl = num_pr.find("w:ilvl", namespaces=NS)
    if num_id is None or ilvl is None:
        raise AssertionError("incomplete numPr")
    return num_id.get(qn("val")), int(ilvl.get(qn("val")))


def effective_numbering_for_paragraph(
    entries: dict[str, bytes], text: str
) -> Optional[Tuple[str, int, str]]:
    document = xml(entries, "word/document.xml")
    paragraph = paragraph_for_text(document, text)
    direct = paragraph.find("w:pPr/w:numPr", namespaces=NS)
    if direct is not None:
        direct_num_id = direct.find("w:numId", namespaces=NS)
        if (
            direct_num_id is not None
            and direct_num_id.get(qn("val")) == "0"
        ):
            return None
        num_id, level = _num_pr_values(direct)
        return num_id, level, "paragraph"

    style_ref = paragraph.find("w:pPr/w:pStyle", namespaces=NS)
    if style_ref is None:
        return None
    style_id = style_ref.get(qn("val"))
    styles = xml(entries, "word/styles.xml")
    style = style_for_id(styles, style_id)
    inherited = style.find("w:pPr/w:numPr", namespaces=NS)
    if inherited is None:
        return None
    num_id, level = _num_pr_values(inherited)
    return num_id, level, "style"


class HeadingNumberingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(
            prefix="word-heading-numbering-tests-"
        )
        cls.working_dir = Path(cls._temporary.name)

        cls.numbered_pack = cls.working_dir / "numbered-headings.wfstyle"
        cls.numbered_manifest = manager.create_style_pack(
            FIXTURES / "source-numbered-headings.docx",
            cls.numbered_pack,
            display_name="多级标题编号",
        )
        cls.numbered_output = cls.working_dir / "numbered-output.docx"
        cls.numbered_applied_manifest, cls.numbered_stats = manager.apply_style_pack(
            cls.numbered_pack,
            FIXTURES / "target-plain-headings.docx",
            cls.numbered_output,
        )
        cls.numbered_entries = read_zip(cls.numbered_output)

        cls.plain_pack = cls.working_dir / "plain-headings.wfstyle"
        cls.plain_manifest = manager.create_style_pack(
            FIXTURES / "source-plain-headings.docx",
            cls.plain_pack,
            display_name="无编号标题",
        )
        cls.plain_output = cls.working_dir / "plain-output.docx"
        cls.plain_applied_manifest, cls.plain_stats = manager.apply_style_pack(
            cls.plain_pack,
            FIXTURES / "target-plain-headings.docx",
            cls.plain_output,
        )
        cls.plain_entries = read_zip(cls.plain_output)

        cls.direct_pack = cls.working_dir / "direct-numbered-headings.wfstyle"
        cls.direct_manifest = manager.create_style_pack(
            FIXTURES / "source-direct-numbered-headings.docx",
            cls.direct_pack,
            display_name="段落直接多级编号",
        )
        cls.direct_output = cls.working_dir / "direct-numbered-output.docx"
        _, cls.direct_stats = manager.apply_style_pack(
            cls.direct_pack,
            FIXTURES / "target-plain-headings.docx",
            cls.direct_output,
        )
        cls.direct_entries = read_zip(cls.direct_output)

        cls.custom_pack = cls.working_dir / "custom-outline-numbered.wfstyle"
        cls.custom_manifest = manager.create_style_pack(
            FIXTURES / "source-custom-outline-numbered.docx",
            cls.custom_pack,
            display_name="自定义大纲编号",
        )
        cls.custom_output = cls.working_dir / "custom-outline-output.docx"
        _, cls.custom_stats = manager.apply_style_pack(
            cls.custom_pack,
            FIXTURES / "target-plain-headings.docx",
            cls.custom_output,
        )
        cls.custom_entries = read_zip(cls.custom_output)

        cls.cancelled_pack = cls.working_dir / "cancelled-heading.wfstyle"
        cls.cancelled_manifest = manager.create_style_pack(
            FIXTURES / "source-heading-numbering-cancelled.docx",
            cls.cancelled_pack,
            display_name="显式取消标题编号",
        )
        cls.cancelled_output = cls.working_dir / "cancelled-output.docx"
        _, cls.cancelled_stats = manager.apply_style_pack(
            cls.cancelled_pack,
            FIXTURES / "target-plain-headings.docx",
            cls.cancelled_output,
        )
        cls.cancelled_entries = read_zip(cls.cancelled_output)

        cls.proxy_pack = cls.working_dir / "num-style-link-heading.wfstyle"
        cls.proxy_manifest = manager.create_style_pack(
            FIXTURES / "source-num-style-link-heading.docx",
            cls.proxy_pack,
            display_name="编号样式代理",
        )
        cls.proxy_output = cls.working_dir / "num-style-link-output.docx"
        _, cls.proxy_stats = manager.apply_style_pack(
            cls.proxy_pack,
            FIXTURES / "target-plain-headings.docx",
            cls.proxy_output,
        )
        cls.proxy_entries = read_zip(cls.proxy_output)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_pack_detects_numbered_heading_styles_and_keeps_numbering_part(self) -> None:
        formats = {
            item["style_id"]: item
            for item in self.numbered_manifest["used_formats"]
        }
        for style_id in ("Heading1", "Heading2", "Heading3"):
            self.assertIn(style_id, formats)
            self.assertIs(formats[style_id]["numbered"], True)

        pack_entries = read_zip(self.numbered_pack)
        self.assertIn("parts/word/numbering.xml", pack_entries)
        numbering = xml(pack_entries, "parts/word/numbering.xml")
        self.assertEqual(etree.QName(numbering).localname, "numbering")
        self.assertTrue(numbering.xpath("./w:abstractNum", namespaces=NS))
        self.assertTrue(numbering.xpath("./w:num", namespaces=NS))

    def test_applied_headings_keep_text_and_resolve_to_expected_levels(self) -> None:
        target_entries = read_zip(FIXTURES / "target-plain-headings.docx")
        target_text = xml(target_entries, "word/document.xml").xpath(
            "//w:t/text()", namespaces=NS
        )
        output_text = xml(self.numbered_entries, "word/document.xml").xpath(
            "//w:t/text()", namespaces=NS
        )
        self.assertEqual(output_text, target_text)

        resolved_num_ids = set()
        for expected_level, text in TARGET_HEADINGS:
            association = effective_numbering_for_paragraph(
                self.numbered_entries, text
            )
            self.assertIsNotNone(association, text)
            num_id, level, origin = association
            self.assertEqual(level, expected_level, text)
            self.assertIn(origin, {"style", "paragraph"})
            resolved_num_ids.add(num_id)
        self.assertEqual(len(resolved_num_ids), 1)
        self.assertEqual(
            self.numbered_stats.heading_numbers_applied, len(TARGET_HEADINGS)
        )

    def test_numbering_definition_is_a_valid_three_level_heading_scheme(self) -> None:
        numbering = xml(self.numbered_entries, "word/numbering.xml")
        num_ids = {
            node.get(qn("numId")): node
            for node in numbering.findall("w:num", namespaces=NS)
        }
        abstracts = {
            node.get(qn("abstractNumId")): node
            for node in numbering.findall("w:abstractNum", namespaces=NS)
        }
        self.assertTrue(num_ids)
        self.assertTrue(abstracts)

        for concrete in num_ids.values():
            abstract_ref = concrete.find("w:abstractNumId", namespaces=NS)
            self.assertIsNotNone(abstract_ref)
            self.assertIn(abstract_ref.get(qn("val")), abstracts)

        num_id, _level, _origin = effective_numbering_for_paragraph(
            self.numbered_entries, "项目概述"
        )
        concrete = num_ids[num_id]
        abstract_id = concrete.find("w:abstractNumId", namespaces=NS).get(qn("val"))
        abstract = abstracts[abstract_id]
        self.assertEqual(
            abstract.find("w:multiLevelType", namespaces=NS).get(qn("val")),
            "multilevel",
        )

        levels = {
            int(level.get(qn("ilvl"))): level
            for level in abstract.findall("w:lvl", namespaces=NS)
        }
        self.assertTrue({0, 1, 2}.issubset(levels))
        expected = {
            0: ("%1", "Heading1"),
            1: ("%1.%2", "Heading2"),
            2: ("%1.%2.%3", "Heading3"),
        }
        for level, (level_text, style_id) in expected.items():
            node = levels[level]
            self.assertEqual(
                node.find("w:start", namespaces=NS).get(qn("val")), "1"
            )
            self.assertEqual(
                node.find("w:numFmt", namespaces=NS).get(qn("val")), "decimal"
            )
            self.assertEqual(
                node.find("w:lvlText", namespaces=NS).get(qn("val")),
                level_text,
            )
            self.assertEqual(
                node.find("w:pStyle", namespaces=NS).get(qn("val")), style_id
            )

        # Both style systems shipped by modern Word must reference the same
        # concrete numbering definition, avoiding Word/LibreOffice divergence.
        for part in ("word/styles.xml", "word/stylesWithEffects.xml"):
            if part not in self.numbered_entries:
                continue
            styles = xml(self.numbered_entries, part)
            for expected_level, style_id in enumerate(
                ("Heading1", "Heading2", "Heading3")
            ):
                num_pr = style_for_id(styles, style_id).find(
                    "w:pPr/w:numPr", namespaces=NS
                )
                self.assertIsNotNone(num_pr, "%s %s" % (part, style_id))
                linked_num_id, linked_level = _num_pr_values(num_pr)
                self.assertEqual(linked_num_id, num_id)
                self.assertEqual(linked_level, expected_level)

    def test_plain_source_does_not_accidentally_number_target_headings(self) -> None:
        formats = {
            item["style_id"]: item for item in self.plain_manifest["used_formats"]
        }
        for style_id in ("Heading1", "Heading2", "Heading3"):
            self.assertIn(style_id, formats)
            self.assertIs(formats[style_id]["numbered"], False)

        for _expected_level, text in TARGET_HEADINGS:
            self.assertIsNone(
                effective_numbering_for_paragraph(self.plain_entries, text), text
            )
        self.assertEqual(self.plain_stats.heading_numbers_applied, 0)

        for part in ("word/styles.xml", "word/stylesWithEffects.xml"):
            if part not in self.plain_entries:
                continue
            styles = xml(self.plain_entries, part)
            for style_id in ("Heading1", "Heading2", "Heading3"):
                self.assertIsNone(
                    style_for_id(styles, style_id).find(
                        "w:pPr/w:numPr", namespaces=NS
                    ),
                    "%s %s" % (part, style_id),
                )

        target_entries = read_zip(FIXTURES / "target-plain-headings.docx")
        self.assertEqual(
            xml(self.plain_entries, "word/document.xml").xpath(
                "//w:t/text()", namespaces=NS
            ),
            xml(target_entries, "word/document.xml").xpath(
                "//w:t/text()", namespaces=NS
            ),
        )

    def test_direct_paragraph_numbering_is_captured_without_style_numpr(self) -> None:
        source_entries = read_zip(
            FIXTURES / "source-direct-numbered-headings.docx"
        )
        source_styles = xml(source_entries, "word/styles.xml")
        for style_id in ("Heading1", "Heading2", "Heading3"):
            self.assertIsNone(
                style_for_id(source_styles, style_id).find(
                    "w:pPr/w:numPr", namespaces=NS
                )
            )

        source_document = xml(source_entries, "word/document.xml")
        direct_values = source_document.xpath(
            "//w:p/w:pPr/w:numPr/w:numId/@w:val", namespaces=NS
        )
        self.assertEqual(len(direct_values), 3)
        self.assertEqual(len(set(direct_values)), 1)
        source_numbering = xml(source_entries, "word/numbering.xml")
        self.assertFalse(
            source_numbering.xpath(
                "//w:abstractNum/w:lvl/w:pStyle["
                "@w:val='Heading1' or @w:val='Heading2' or @w:val='Heading3']",
                namespaces=NS,
            )
        )

        manifest_rules = self.direct_manifest["heading_numbering"]
        self.assertEqual(
            {style_id: rule["level"] for style_id, rule in manifest_rules.items()},
            {
                "Heading1": 0,
                "Heading2": 1,
                "Heading3": 2,
                "Heading4": 3,
                "Heading5": 4,
            },
        )
        formats = {
            item["style_id"]: item
            for item in self.direct_manifest["used_formats"]
        }
        for style_id in (
            "Heading1",
            "Heading2",
            "Heading3",
            "Heading4",
            "Heading5",
        ):
            self.assertIs(formats[style_id]["numbered"], True)

        for expected_level, text in TARGET_HEADINGS:
            association = effective_numbering_for_paragraph(
                self.direct_entries, text
            )
            self.assertIsNotNone(association, text)
            _num_id, level, _origin = association
            self.assertEqual(level, expected_level, text)
        self.assertEqual(
            self.direct_stats.heading_numbers_applied, len(TARGET_HEADINGS)
        )

    def test_used_custom_outline_style_replaces_unused_builtin_heading(self) -> None:
        used_ids = {
            item["style_id"] for item in self.custom_manifest["used_formats"]
        }
        self.assertIn("CustomOutlineOne", used_ids)
        self.assertNotIn("Heading1", used_ids)
        self.assertEqual(
            set(self.custom_manifest["heading_numbering"]),
            {"CustomOutlineOne"},
        )

        source_entries = read_zip(
            FIXTURES / "source-custom-outline-numbered.docx"
        )
        source_styles = xml(source_entries, "word/styles.xml")
        self.assertIsNotNone(style_for_id(source_styles, "Heading1"))
        custom_source = style_for_id(source_styles, "CustomOutlineOne")
        self.assertEqual(
            custom_source.find("w:pPr/w:outlineLvl", namespaces=NS).get(qn("val")),
            "0",
        )

        output_document = xml(self.custom_entries, "word/document.xml")
        for text in ("项目概述", "实施安排"):
            paragraph = paragraph_for_text(output_document, text)
            self.assertEqual(
                paragraph.find("w:pPr/w:pStyle", namespaces=NS).get(qn("val")),
                "CustomOutlineOne",
            )
            association = effective_numbering_for_paragraph(
                self.custom_entries, text
            )
            self.assertIsNotNone(association, text)
            self.assertEqual(association[1], 0)

        for text in ("建设目标", "技术路线", "验收标准", "交付清单", "质量要求"):
            self.assertIsNone(
                effective_numbering_for_paragraph(self.custom_entries, text), text
            )
        self.assertEqual(self.custom_stats.heading_numbers_applied, 2)

    def test_explicit_numid_zero_cancellation_does_not_number_target(self) -> None:
        source_entries = read_zip(
            FIXTURES / "source-heading-numbering-cancelled.docx"
        )
        source_styles = xml(source_entries, "word/styles.xml")
        inherited_num_id = style_for_id(source_styles, "Heading1").find(
            "w:pPr/w:numPr/w:numId", namespaces=NS
        )
        self.assertIsNotNone(inherited_num_id)
        self.assertNotEqual(inherited_num_id.get(qn("val")), "0")
        source_document = xml(source_entries, "word/document.xml")
        cancelled = paragraph_for_text(
            source_document, "显式取消编号的一级标题"
        ).find("w:pPr/w:numPr/w:numId", namespaces=NS)
        self.assertIsNotNone(cancelled)
        self.assertEqual(cancelled.get(qn("val")), "0")

        self.assertNotIn(
            "Heading1", self.cancelled_manifest["heading_numbering"]
        )
        for _level, text in TARGET_HEADINGS:
            self.assertIsNone(
                effective_numbering_for_paragraph(self.cancelled_entries, text),
                text,
            )
        self.assertEqual(self.cancelled_stats.heading_numbers_applied, 0)

        target_entries = read_zip(FIXTURES / "target-plain-headings.docx")
        self.assertEqual(
            xml(self.cancelled_entries, "word/document.xml").xpath(
                "//w:t/text()", namespaces=NS
            ),
            xml(target_entries, "word/document.xml").xpath(
                "//w:t/text()", namespaces=NS
            ),
        )

    def test_num_style_link_proxy_chain_is_resolved_and_applied(self) -> None:
        rules = self.proxy_manifest["heading_numbering"]
        self.assertEqual(set(rules), {"Heading1"})
        proxy_num_id = str(rules["Heading1"]["num_id"])
        self.assertEqual(rules["Heading1"]["level"], 0)

        source_entries = read_zip(
            FIXTURES / "source-num-style-link-heading.docx"
        )
        numbering = xml(source_entries, "word/numbering.xml")
        styles = xml(source_entries, "word/styles.xml")
        proxy_nums = numbering.xpath(
            "./w:num[@w:numId=$num_id]",
            namespaces=NS,
            num_id=proxy_num_id,
        )
        self.assertEqual(len(proxy_nums), 1)
        proxy_abstract_id = proxy_nums[0].find(
            "w:abstractNumId", namespaces=NS
        ).get(qn("val"))
        proxy_abstract = numbering.xpath(
            "./w:abstractNum[@w:abstractNumId=$abstract_id]",
            namespaces=NS,
            abstract_id=proxy_abstract_id,
        )[0]
        style_link = proxy_abstract.find("w:numStyleLink", namespaces=NS)
        self.assertIsNotNone(style_link)
        proxy_style_id = style_link.get(qn("val"))
        proxy_style = style_for_id(styles, proxy_style_id)
        self.assertEqual(proxy_style.get(qn("type")), "numbering")
        actual_num_id = proxy_style.find(
            "w:pPr/w:numPr/w:numId", namespaces=NS
        ).get(qn("val"))
        self.assertNotEqual(actual_num_id, proxy_num_id)
        actual_nums = numbering.xpath(
            "./w:num[@w:numId=$num_id]",
            namespaces=NS,
            num_id=actual_num_id,
        )
        self.assertEqual(len(actual_nums), 1)
        actual_abstract_id = actual_nums[0].find(
            "w:abstractNumId", namespaces=NS
        ).get(qn("val"))
        actual_abstract = numbering.xpath(
            "./w:abstractNum[@w:abstractNumId=$abstract_id]",
            namespaces=NS,
            abstract_id=actual_abstract_id,
        )[0]
        self.assertEqual(
            actual_abstract.xpath("./w:lvl/w:lvlText/@w:val", namespaces=NS),
            ["%1", "%1.%2", "%1.%2.%3"],
        )
        self.assertEqual(
            actual_abstract.xpath("./w:lvl/w:pStyle/@w:val", namespaces=NS),
            ["Heading1", "Heading2", "Heading3"],
        )

        for text in ("项目概述", "实施安排"):
            association = effective_numbering_for_paragraph(
                self.proxy_entries, text
            )
            self.assertIsNotNone(association, text)
            self.assertEqual(association[0], proxy_num_id)
            self.assertEqual(association[1], 0)
        for text in ("建设目标", "技术路线", "验收标准", "交付清单", "质量要求"):
            self.assertIsNone(
                effective_numbering_for_paragraph(self.proxy_entries, text), text
            )
        self.assertEqual(self.proxy_stats.heading_numbers_applied, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
