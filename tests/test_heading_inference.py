#!/usr/bin/env python3
# [INPUT]: 依赖 __future__, sys, tempfile, unittest, zipfile, pathlib, typing, lxml, make_fixtures, style_pack_manager, word_style_transfer
# [OUTPUT]: 提供 TEST_DIR, PROJECT_DIR, NS, HEADING_TEXT, VISUAL_RUN_PROPERTIES, qn(), read_zip(), xml(), style_for_id(), paragraph_for_text(), effective_style_properties(), bool_value(), half_points(), twips(), effective_numbering_for_paragraph(), HeadingInferenceTests
# [POS]: 验证标题层级补全的字体、尺寸、段落及编号逻辑
# [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
"""Regression coverage for synthesizing missing Heading 4/5 definitions."""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Dict, Optional, Tuple

from lxml import etree


TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(PROJECT_DIR))

import make_fixtures as fixtures  # noqa: E402
import style_pack_manager as manager  # noqa: E402
import word_style_transfer as core  # noqa: E402


NS = {"w": core.W_NS}
HEADING_TEXT = (
    (0, "项目总览"),
    (1, "建设范围"),
    (2, "实施路径"),
    (3, "接口设计"),
    (4, "字段校验"),
)
VISUAL_RUN_PROPERTIES = {
    "b",
    "bCs",
    "i",
    "iCs",
    "color",
    "highlight",
    "rFonts",
    "shd",
    "sz",
    "szCs",
    "u",
}


def qn(local: str) -> str:
    return "{%s}%s" % (core.W_NS, local)


def read_zip(path: Path) -> Dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise AssertionError("damaged package member: %s" % bad)
        return {name: archive.read(name) for name in archive.namelist()}


def xml(entries: Dict[str, bytes], name: str) -> etree._Element:
    return etree.fromstring(entries[name])


def style_for_id(styles: etree._Element, style_id: str) -> etree._Element:
    matches = styles.xpath(
        "./w:style[@w:styleId=$style_id]",
        namespaces=NS,
        style_id=style_id,
    )
    if len(matches) != 1:
        raise AssertionError("style not found exactly once: %s" % style_id)
    return matches[0]


def paragraph_for_text(root: etree._Element, text: str) -> etree._Element:
    for paragraph in root.xpath("//w:p", namespaces=NS):
        value = "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))
        if value == text:
            return paragraph
    raise AssertionError("paragraph not found: %s" % text)


def _merge_children(
    destination: Dict[str, etree._Element],
    parent: Optional[etree._Element],
) -> None:
    if parent is None:
        return
    for child in parent:
        key = etree.QName(child).localname
        if key in {"rFonts", "spacing"} and key in destination:
            merged = etree.fromstring(etree.tostring(destination[key]))
            for attribute, value in child.attrib.items():
                merged.set(attribute, value)
            destination[key] = merged
        else:
            destination[key] = child


def effective_style_properties(
    styles: etree._Element, style_id: str
) -> Tuple[Dict[str, etree._Element], Dict[str, etree._Element]]:
    """Resolve docDefaults + basedOn so tests check rendered style semantics."""
    nodes = {
        node.get(qn("styleId")): node
        for node in styles.findall("w:style", namespaces=NS)
        if node.get(qn("styleId"))
    }
    chain = []
    seen = set()
    current = style_id
    while current and current not in seen:
        seen.add(current)
        node = nodes.get(current)
        if node is None:
            break
        chain.append(node)
        based_on = node.find("w:basedOn", namespaces=NS)
        current = based_on.get(qn("val")) if based_on is not None else ""
    chain.reverse()

    run_properties: Dict[str, etree._Element] = {}
    paragraph_properties: Dict[str, etree._Element] = {}
    _merge_children(
        run_properties,
        styles.find("w:docDefaults/w:rPrDefault/w:rPr", namespaces=NS),
    )
    _merge_children(
        paragraph_properties,
        styles.find("w:docDefaults/w:pPrDefault/w:pPr", namespaces=NS),
    )
    for node in chain:
        _merge_children(run_properties, node.find("w:rPr", namespaces=NS))
        _merge_children(
            paragraph_properties, node.find("w:pPr", namespaces=NS)
        )
    return run_properties, paragraph_properties


def bool_value(node: Optional[etree._Element]) -> Optional[bool]:
    if node is None:
        return None
    value = node.get(qn("val"))
    if value is None:
        return True
    return value.casefold() not in {"0", "false", "off", "no"}


def half_points(node: etree._Element) -> float:
    return int(node.get(qn("val"))) / 2.0


def twips(node: etree._Element, attribute: str) -> float:
    return int(node.get(qn(attribute))) / 20.0


def effective_numbering_for_paragraph(
    entries: Dict[str, bytes], text: str
) -> Optional[Tuple[str, int]]:
    document = xml(entries, "word/document.xml")
    paragraph = paragraph_for_text(document, text)
    num_pr = paragraph.find("w:pPr/w:numPr", namespaces=NS)
    if num_pr is None:
        style_ref = paragraph.find("w:pPr/w:pStyle", namespaces=NS)
        if style_ref is None:
            return None
        styles = xml(entries, "word/styles.xml")
        style = style_for_id(styles, style_ref.get(qn("val")))
        num_pr = style.find("w:pPr/w:numPr", namespaces=NS)
    if num_pr is None:
        return None
    num_id = num_pr.find("w:numId", namespaces=NS)
    level = num_pr.find("w:ilvl", namespaces=NS)
    if num_id is None or num_id.get(qn("val")) == "0" or level is None:
        return None
    return num_id.get(qn("val")), int(level.get(qn("val")))


class HeadingInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(
            prefix="word-heading-inference-tests-"
        )
        cls.working_dir = Path(cls._temporary.name)
        cls.numbered_source = cls.working_dir / "three-level-numbered.docx"
        cls.plain_source = cls.working_dir / "three-level-plain.docx"
        cls.target = cls.working_dir / "five-level-target.docx"
        fixtures.make_three_level_heading_logic_source(
            cls.numbered_source, numbered=True
        )
        fixtures.make_three_level_heading_logic_source(
            cls.plain_source, numbered=False
        )
        fixtures.make_five_level_heading_target(cls.target)

        cls.numbered_pack = cls.working_dir / "numbered.wfstyle"
        cls.numbered_manifest = manager.create_style_pack(
            cls.numbered_source,
            cls.numbered_pack,
            display_name="三级编号智能补全",
        )
        cls.numbered_output = cls.working_dir / "numbered-output.docx"
        _, cls.numbered_stats = manager.apply_style_pack(
            cls.numbered_pack, cls.target, cls.numbered_output
        )
        cls.numbered_entries = read_zip(cls.numbered_output)

        cls.plain_pack = cls.working_dir / "plain.wfstyle"
        cls.plain_manifest = manager.create_style_pack(
            cls.plain_source,
            cls.plain_pack,
            display_name="三级无编号智能补全",
        )
        cls.plain_output = cls.working_dir / "plain-output.docx"
        _, cls.plain_stats = manager.apply_style_pack(
            cls.plain_pack, cls.target, cls.plain_output
        )
        cls.plain_entries = read_zip(cls.plain_output)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_fixture_uses_only_h1_h2_h3_and_dormant_h4_h5_are_bad(self) -> None:
        entries = read_zip(self.numbered_source)
        document = xml(entries, "word/document.xml")
        used = set(
            document.xpath("//w:pPr/w:pStyle/@w:val", namespaces=NS)
        )
        self.assertEqual(used, {"Heading1", "Heading2", "Heading3"})

        styles = xml(entries, "word/styles.xml")
        expected_bad = {
            "Heading4": (31.0, "FF00FF", "7"),
            "Heading5": (29.0, "00FF00", "8"),
        }
        for style_id, (size, color, outline) in expected_bad.items():
            style = style_for_id(styles, style_id)
            self.assertEqual(
                half_points(style.find("w:rPr/w:sz", namespaces=NS)), size
            )
            self.assertEqual(
                style.find("w:rPr/w:color", namespaces=NS).get(qn("val")),
                color,
            )
            self.assertEqual(
                style.find("w:pPr/w:outlineLvl", namespaces=NS).get(qn("val")),
                outline,
            )

    def test_manifest_marks_two_intelligently_completed_heading_styles(self) -> None:
        for manifest in (self.numbered_manifest, self.plain_manifest):
            formats = {
                item["style_id"]: item for item in manifest["used_formats"]
            }
            self.assertEqual(manifest["inferred_style_count"], 2)
            self.assertEqual(
                set(manifest["inferred_heading_styles"]),
                {"Heading4", "Heading5"},
            )
            for style_id, level in (("Heading4", 3), ("Heading5", 4)):
                self.assertIn(style_id, formats)
                inferred = formats[style_id]
                self.assertEqual(inferred["usage_count"], 0)
                self.assertIs(inferred["inferred"], True)
                self.assertEqual(inferred["inference_label"], "智能补全")
                self.assertEqual(inferred["outline_level"], level)

            for style_id in ("Heading1", "Heading2", "Heading3"):
                self.assertFalse(formats[style_id].get("inferred", False))

    def test_inferred_typography_and_spacing_follow_source_progression(self) -> None:
        expected = {
            # H1/H2/H3 are 21/18/15pt, so H4=12pt and H5 clamps to Normal=10pt.
            "Heading4": (3, 12.0, 6.0, 2.0),
            "Heading5": (4, 10.0, 2.0, 0.0),
        }
        for entries in (self.numbered_entries, self.plain_entries):
            for part in ("word/styles.xml", "word/stylesWithEffects.xml"):
                if part not in entries:
                    continue
                styles = xml(entries, part)
                for style_id, (
                    outline,
                    size,
                    before,
                    after,
                ) in expected.items():
                    style = style_for_id(styles, style_id)
                    direct_outline = style.find(
                        "w:pPr/w:outlineLvl", namespaces=NS
                    )
                    self.assertIsNotNone(direct_outline, "%s %s" % (part, style_id))
                    self.assertEqual(direct_outline.get(qn("val")), str(outline))

                    run, paragraph = effective_style_properties(styles, style_id)
                    fonts = run["rFonts"]
                    self.assertEqual(fonts.get(qn("ascii")), "Arial")
                    self.assertEqual(fonts.get(qn("hAnsi")), "Arial")
                    self.assertEqual(fonts.get(qn("eastAsia")), "PingFang SC")
                    self.assertEqual(half_points(run["sz"]), size)
                    self.assertEqual(run["color"].get(qn("val")), "244A73")
                    self.assertIs(bool_value(run.get("b")), True)
                    self.assertIs(bool_value(run.get("i")), False)
                    self.assertEqual(twips(paragraph["spacing"], "before"), before)
                    self.assertEqual(twips(paragraph["spacing"], "after"), after)

    def test_target_text_survives_and_h4_h5_direct_junk_is_removed(self) -> None:
        target_entries = read_zip(self.target)
        expected_text = xml(target_entries, "word/document.xml").xpath(
            "//w:t/text()", namespaces=NS
        )
        for entries in (self.numbered_entries, self.plain_entries):
            document = xml(entries, "word/document.xml")
            self.assertEqual(
                document.xpath("//w:t/text()", namespaces=NS), expected_text
            )
            for text in ("接口设计", "字段校验"):
                paragraph = paragraph_for_text(document, text)
                ppr = paragraph.find("w:pPr", namespaces=NS)
                self.assertIsNotNone(ppr)
                self.assertTrue(
                    {etree.QName(child).localname for child in ppr}
                    <= {"pStyle", "numPr", "ind"}
                )
                for rpr in paragraph.findall(".//w:rPr", namespaces=NS):
                    present = {
                        etree.QName(child).localname for child in rpr
                    }
                    self.assertFalse(present & VISUAL_RUN_PROPERTIES)

    def test_three_level_numbering_is_extended_to_h4_and_h5(self) -> None:
        rules = self.numbered_manifest["heading_numbering"]
        self.assertEqual(
            {style_id: rules[style_id]["level"] for style_id in rules},
            {
                "Heading1": 0,
                "Heading2": 1,
                "Heading3": 2,
                "Heading4": 3,
                "Heading5": 4,
            },
        )
        self.assertEqual(rules["Heading4"]["level_text"], "%1.%2.%3.%4")
        self.assertEqual(
            rules["Heading5"]["level_text"], "%1.%2.%3.%4.%5"
        )

        resolved_num_ids = set()
        for expected_level, text in HEADING_TEXT:
            association = effective_numbering_for_paragraph(
                self.numbered_entries, text
            )
            self.assertIsNotNone(association, text)
            num_id, level = association
            resolved_num_ids.add(num_id)
            self.assertEqual(level, expected_level, text)
        self.assertEqual(len(resolved_num_ids), 1)
        self.assertEqual(self.numbered_stats.heading_numbers_applied, 5)

        numbering = xml(self.numbered_entries, "word/numbering.xml")
        num_id = next(iter(resolved_num_ids))
        concrete = numbering.xpath(
            "./w:num[@w:numId=$num_id]", namespaces=NS, num_id=num_id
        )
        self.assertEqual(len(concrete), 1)
        abstract_id = concrete[0].find(
            "w:abstractNumId", namespaces=NS
        ).get(qn("val"))
        abstract = numbering.xpath(
            "./w:abstractNum[@w:abstractNumId=$abstract_id]",
            namespaces=NS,
            abstract_id=abstract_id,
        )[0]
        levels = {
            int(level.get(qn("ilvl"))): level
            for level in abstract.findall("w:lvl", namespaces=NS)
        }
        for level, style_id, pattern in (
            (3, "Heading4", "%1.%2.%3.%4"),
            (4, "Heading5", "%1.%2.%3.%4.%5"),
        ):
            self.assertIn(level, levels)
            self.assertEqual(
                levels[level].find("w:numFmt", namespaces=NS).get(qn("val")),
                "decimal",
            )
            self.assertEqual(
                levels[level].find("w:lvlText", namespaces=NS).get(qn("val")),
                pattern,
            )
            self.assertEqual(
                levels[level].find("w:pStyle", namespaces=NS).get(qn("val")),
                style_id,
            )

    def test_plain_source_infers_styles_but_never_adds_numbering(self) -> None:
        self.assertEqual(self.plain_manifest["heading_numbering"], {})
        formats = {
            item["style_id"]: item
            for item in self.plain_manifest["used_formats"]
        }
        for style_id in ("Heading4", "Heading5"):
            self.assertIs(formats[style_id]["numbered"], False)
            self.assertIsNone(formats[style_id]["numbering_example"])

        for _expected_level, text in HEADING_TEXT:
            self.assertIsNone(
                effective_numbering_for_paragraph(self.plain_entries, text), text
            )
        self.assertEqual(self.plain_stats.heading_numbers_applied, 0)

    def test_semantic_chinese_units_are_not_blindly_extended(self) -> None:
        rules = [
            core.HeadingNumberingRule("Heading1", "8", 0, "decimal", "第%1章", 1),
            core.HeadingNumberingRule("Heading2", "8", 1, "decimal", "%1.%2节", 1),
            core.HeadingNumberingRule("Heading3", "8", 2, "decimal", "%1.%2.%3款", 1),
        ]
        self.assertIsNone(core._repeatable_numbering_pattern(rules))


if __name__ == "__main__":
    unittest.main(verbosity=2)
