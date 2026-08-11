#!/usr/bin/env python3
"""Regression coverage for persisted and editable heading paragraph formats."""

from __future__ import annotations

import copy
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Dict, Optional

from lxml import etree


TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
FIXTURES = TEST_DIR / "fixtures"
sys.path.insert(0, str(PROJECT_DIR))

import style_pack_manager as manager  # noqa: E402
import word_style_transfer as core  # noqa: E402


NS = {"w": core.W_NS}


def qn(local: str) -> str:
    return core.qn(core.W_NS, local)


def read_zip(path: Path) -> Dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise AssertionError("damaged archive member: %s" % bad)
        return {name: archive.read(name) for name in archive.namelist()}


def write_zip(path: Path, entries: Dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def xml(entries: Dict[str, bytes], name: str) -> etree._Element:
    return core.parse_xml(entries[name], name)


def paragraph_for_text(root: etree._Element, text: str) -> etree._Element:
    for paragraph in root.xpath("//w:p", namespaces=NS):
        if "".join(paragraph.xpath(".//w:t/text()", namespaces=NS)) == text:
            return paragraph
    raise AssertionError("paragraph not found: %s" % text)


def style_for_id(root: etree._Element, style_id: str) -> etree._Element:
    matches = root.xpath(
        "./w:style[@w:styleId=$style_id]",
        namespaces=NS,
        style_id=style_id,
    )
    if len(matches) != 1:
        raise AssertionError("style not found exactly once: %s" % style_id)
    return matches[0]


def replace_direct_property(
    paragraph_properties: etree._Element,
    local: str,
    attributes: Dict[str, str],
) -> etree._Element:
    existing = paragraph_properties.find("w:%s" % local, namespaces=NS)
    if existing is not None:
        paragraph_properties.remove(existing)
    node = etree.Element(qn(local))
    for attribute, value in attributes.items():
        node.set(qn(attribute), value)
    core._ordered_insert(paragraph_properties, node, core.PPR_CHILD_ORDER)
    return node


def set_paragraph_text(paragraph: etree._Element, text: str) -> None:
    nodes = paragraph.xpath(".//w:t", namespaces=NS)
    if not nodes:
        raise AssertionError("paragraph has no text node")
    nodes[0].text = text
    for node in nodes[1:]:
        node.text = ""


def make_source_with_direct_heading_properties(
    base: Path,
    destination: Path,
    *,
    majority_vote: bool,
) -> None:
    entries = read_zip(base)
    document = xml(entries, "word/document.xml")
    heading = paragraph_for_text(document, "格式源一级标题")
    heading_properties = heading.find("w:pPr", namespaces=NS)
    if heading_properties is None:
        raise AssertionError("Heading 1 has no paragraph properties")
    replace_direct_property(
        heading_properties,
        "spacing",
        {"before": "240", "after": "120", "line": "360", "lineRule": "auto"},
    )
    replace_direct_property(
        heading_properties,
        "ind",
        {"left": "0", "firstLineChars": "200", "hanging": "0"},
    )
    replace_direct_property(heading_properties, "jc", {"val": "both"})

    if majority_vote:
        body = document.find("w:body", namespaces=NS)
        if body is None:
            raise AssertionError("document body is missing")
        insertion = body.index(heading) + 1
        matching = copy.deepcopy(heading)
        set_paragraph_text(matching, "格式源一级标题副本")
        body.insert(insertion, matching)
        absent = copy.deepcopy(heading)
        set_paragraph_text(absent, "格式源一级标题无直接格式")
        absent_properties = absent.find("w:pPr", namespaces=NS)
        if absent_properties is None:
            raise AssertionError("copied heading properties are missing")
        for local in ("spacing", "ind", "jc"):
            node = absent_properties.find("w:%s" % local, namespaces=NS)
            if node is not None:
                absent_properties.remove(node)
        body.insert(insertion + 1, absent)

    body_paragraph = next(
        paragraph
        for paragraph in document.xpath("//w:body/w:p", namespaces=NS)
        if "正文" in "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))
    )
    body_properties = body_paragraph.find("w:pPr", namespaces=NS)
    if body_properties is None:
        body_properties = etree.Element(qn("pPr"))
        body_paragraph.insert(0, body_properties)
    replace_direct_property(body_properties, "spacing", {"before": "999"})
    replace_direct_property(body_properties, "ind", {"firstLineChars": "300"})
    replace_direct_property(body_properties, "jc", {"val": "center"})

    entries["word/document.xml"] = core.serialize_xml(document)
    write_zip(destination, entries)


def preview_for(manifest: Dict[str, object], style_id: str) -> Dict[str, object]:
    for raw in manifest["used_formats"]:
        if isinstance(raw, dict) and raw.get("style_id") == style_id:
            return raw
    raise AssertionError("preview not found: %s" % style_id)


class HeadingParagraphPropertyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(
            prefix="word-heading-paragraph-properties-"
        )
        cls.working_dir = Path(cls._temporary.name)
        cls.source = cls.working_dir / "source-direct-paragraph.docx"
        cls.pack = cls.working_dir / "direct-paragraph.wfstyle"
        make_source_with_direct_heading_properties(
            FIXTURES / "source-plain-headings.docx",
            cls.source,
            majority_vote=True,
        )
        cls.manifest = manager.create_style_pack(
            cls.source, cls.pack, display_name="标题段落格式"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_majority_heading_properties_are_previewed_and_applied_to_plain_headings(
        self,
    ) -> None:
        properties = self.manifest["heading_paragraph_properties"]
        self.assertNotIn("Normal", properties)
        self.assertEqual(
            properties["Heading1"],
            {
                "ind": {
                    "left": "0",
                    "firstLineChars": "200",
                    "hanging": "0",
                },
                "spacing": {
                    "before": "240",
                    "after": "120",
                    "line": "360",
                    "lineRule": "auto",
                },
                "jc": "both",
            },
        )
        preview = preview_for(self.manifest, "Heading1")
        self.assertEqual(preview["alignment"], "both")
        self.assertEqual(preview["space_before_pt"], 12.0)
        self.assertEqual(preview["space_after_pt"], 6.0)
        self.assertEqual(preview["line_spacing"], 1.5)
        self.assertEqual(preview["line_rule"], "auto")
        self.assertEqual(preview["left_indent_pt"], 0.0)
        self.assertEqual(preview["first_line_indent_chars"], 2.0)
        self.assertIsNone(preview["first_line_indent_pt"])
        self.assertIsNone(preview["hanging_indent_pt"])

        first_output = self.working_dir / "plain-output.docx"
        _manifest, stats = manager.apply_style_pack(
            self.pack,
            FIXTURES / "target-plain-headings.docx",
            first_output,
        )
        first_entries = read_zip(first_output)
        first_document = xml(first_entries, "word/document.xml")
        for text in ("项目概述", "实施安排"):
            paragraph = paragraph_for_text(first_document, text)
            self.assertIsNone(paragraph.find("w:pPr/w:numPr", namespaces=NS))
            self.assertEqual(
                paragraph.find("w:pPr/w:spacing", namespaces=NS).attrib,
                {
                    qn("before"): "240",
                    qn("after"): "120",
                    qn("line"): "360",
                    qn("lineRule"): "auto",
                },
            )
            self.assertEqual(
                paragraph.find("w:pPr/w:jc", namespaces=NS).get(qn("val")),
                "both",
            )
            self.assertEqual(
                paragraph.find("w:pPr/w:ind", namespaces=NS).get(
                    qn("firstLineChars")
                ),
                "200",
            )
        self.assertGreaterEqual(stats.heading_indents_applied, 2)

        body = paragraph_for_text(first_document, "目标正文必须原样保留。")
        self.assertIsNone(body.find("w:pPr/w:jc", namespaces=NS))
        self.assertIsNone(body.find("w:pPr/w:ind", namespaces=NS))
        self.assertIsNone(body.find("w:pPr/w:spacing", namespaces=NS))

        second_output = self.working_dir / "plain-output-second.docx"
        manager.apply_style_pack(self.pack, first_output, second_output)
        second_document = xml(read_zip(second_output), "word/document.xml")
        first_properties = paragraph_for_text(first_document, "项目概述").find(
            "w:pPr", namespaces=NS
        )
        second_properties = paragraph_for_text(second_document, "项目概述").find(
            "w:pPr", namespaces=NS
        )
        self.assertEqual(
            etree.tostring(first_properties, method="c14n"),
            etree.tostring(second_properties, method="c14n"),
        )

    def test_derived_paragraph_edit_syncs_both_style_parts_and_direct_override(
        self,
    ) -> None:
        numbered_source = self.working_dir / "numbered-direct-paragraph.docx"
        numbered_pack = self.working_dir / "numbered-direct-paragraph.wfstyle"
        make_source_with_direct_heading_properties(
            FIXTURES / "source-numbered-headings.docx",
            numbered_source,
            majority_vote=False,
        )
        manager.create_style_pack(numbered_source, numbered_pack)
        _source_manifest, source_entries = manager.load_style_pack(numbered_pack)

        derived_pack = self.working_dir / "derived-paragraph.wfstyle"
        derived = manager.derive_style_pack(
            numbered_pack,
            derived_pack,
            {
                "styles": [
                    {
                        "style_id": "Heading1",
                        "alignment": "center",
                        "space_before_pt": 18.0,
                        "space_after_pt": 9.0,
                        "line_spacing": 1.75,
                        "line_rule": "auto",
                        "left_indent_chars": 1.5,
                        "first_line_indent_chars": 2.0,
                    }
                ]
            },
        )
        _loaded, derived_entries = manager.load_style_pack(derived_pack)
        self.assertEqual(
            source_entries["word/numbering.xml"],
            derived_entries["word/numbering.xml"],
            "paragraph edits must not mutate numbering-level geometry",
        )

        for part_name in ("word/styles.xml", "word/stylesWithEffects.xml"):
            style = style_for_id(xml(derived_entries, part_name), "Heading1")
            spacing = style.find("w:pPr/w:spacing", namespaces=NS)
            self.assertEqual(spacing.get(qn("before")), "360", part_name)
            self.assertEqual(spacing.get(qn("after")), "180", part_name)
            self.assertEqual(spacing.get(qn("line")), "420", part_name)
            self.assertEqual(spacing.get(qn("lineRule")), "auto", part_name)
            indentation = style.find("w:pPr/w:ind", namespaces=NS)
            self.assertEqual(indentation.get(qn("leftChars")), "150", part_name)
            self.assertEqual(indentation.get(qn("startChars")), "150", part_name)
            self.assertEqual(indentation.get(qn("firstLineChars")), "200", part_name)
            self.assertEqual(
                style.find("w:pPr/w:jc", namespaces=NS).get(qn("val")),
                "center",
                part_name,
            )

        direct = derived["heading_paragraph_properties"]["Heading1"]
        self.assertEqual(direct["spacing"]["before"], "360")
        self.assertEqual(direct["spacing"]["after"], "180")
        self.assertEqual(direct["spacing"]["line"], "420")
        self.assertEqual(direct["jc"], "center")
        self.assertEqual(direct["ind"]["leftChars"], "150")
        self.assertEqual(direct["ind"]["firstLineChars"], "200")
        self.assertEqual(
            derived["heading_paragraph_indents"]["Heading1"], direct["ind"]
        )
        preview = preview_for(derived, "Heading1")
        self.assertEqual(preview["alignment"], "center")
        self.assertEqual(preview["space_before_pt"], 18.0)
        self.assertEqual(preview["space_after_pt"], 9.0)
        self.assertEqual(preview["line_spacing"], 1.75)
        self.assertIsNone(preview["left_indent_pt"])
        self.assertEqual(preview["left_indent_chars"], 1.5)
        self.assertEqual(preview["first_line_indent_chars"], 2.0)
        self.assertIsNone(preview["hanging_indent_chars"])

        output = self.working_dir / "numbered-output.docx"
        manager.apply_style_pack(
            derived_pack,
            FIXTURES / "target-plain-headings.docx",
            output,
        )
        heading = paragraph_for_text(xml(read_zip(output), "word/document.xml"), "项目概述")
        self.assertIsNotNone(heading.find("w:pPr/w:numPr", namespaces=NS))
        self.assertEqual(
            heading.find("w:pPr/w:spacing", namespaces=NS).get(qn("before")),
            "360",
        )
        self.assertEqual(
            heading.find("w:pPr/w:jc", namespaces=NS).get(qn("val")),
            "center",
        )

    def test_direct_transfer_uses_the_same_heading_property_pipeline(self) -> None:
        output = self.working_dir / "direct-transfer.docx"
        stats = core.transfer(
            self.source,
            FIXTURES / "target-plain-headings.docx",
            output,
        )
        heading = paragraph_for_text(
            xml(read_zip(output), "word/document.xml"), "项目概述"
        )
        self.assertEqual(
            heading.find("w:pPr/w:spacing", namespaces=NS).get(qn("line")),
            "360",
        )
        self.assertEqual(
            heading.find("w:pPr/w:ind", namespaces=NS).get(
                qn("firstLineChars")
            ),
            "200",
        )
        self.assertEqual(
            heading.find("w:pPr/w:jc", namespaces=NS).get(qn("val")),
            "both",
        )
        self.assertGreater(stats.heading_indents_applied, 0)

    def test_legacy_indent_only_pack_remains_compatible(self) -> None:
        manifest, entries = manager.load_style_pack(self.pack)
        legacy_manifest = copy.deepcopy(manifest)
        legacy_manifest.pop("pack_path", None)
        legacy_manifest.pop("heading_paragraph_properties", None)
        legacy_pack = self.working_dir / "legacy-indent-only.wfstyle"
        manager._write_style_pack_archive(
            legacy_pack, legacy_manifest, entries, force=True
        )

        output = self.working_dir / "legacy-indent-only.docx"
        _loaded, stats = manager.apply_style_pack(
            legacy_pack,
            FIXTURES / "target-plain-headings.docx",
            output,
        )
        self.assertFalse(
            any("重新导入一次格式源" in warning for warning in stats.warnings)
        )
        heading = paragraph_for_text(xml(read_zip(output), "word/document.xml"), "项目概述")
        self.assertEqual(
            heading.find("w:pPr/w:ind", namespaces=NS).get(qn("firstLineChars")),
            "200",
        )
        self.assertIsNone(heading.find("w:pPr/w:spacing", namespaces=NS))
        self.assertIsNone(heading.find("w:pPr/w:jc", namespaces=NS))

    def test_edit_protocol_validates_units_pairs_ranges_and_line_conversions(
        self,
    ) -> None:
        for rule, value, expected in (
            ("auto", 1.25, "300"),
            ("exact", 18.0, "360"),
            ("atLeast", 18.0, "360"),
        ):
            with self.subTest(rule=rule):
                edit = manager._normalize_style_edits(
                    {
                        "styles": [
                            {
                                "style_id": "Heading1",
                                "line_spacing": value,
                                "line_rule": rule,
                            }
                        ]
                    }
                )[0]
                paragraph_properties = etree.Element(qn("pPr"))
                manager._apply_paragraph_edits(paragraph_properties, edit)
                spacing = paragraph_properties.find("w:spacing", namespaces=NS)
                self.assertEqual(spacing.get(qn("line")), expected)
                self.assertEqual(spacing.get(qn("lineRule")), rule)

        special_indent_cases = (
            (
                {
                    "first_line_indent_chars": 3.0,
                    "hanging_indent_chars": 0.0,
                },
                "firstLineChars",
                "300",
            ),
            (
                {
                    "first_line_indent_chars": 0.0,
                    "hanging_indent_chars": 1.5,
                },
                "hangingChars",
                "150",
            ),
            (
                {
                    "first_line_indent_chars": 0.0,
                    "hanging_indent_chars": 0.0,
                },
                "firstLineChars",
                "0",
            ),
        )
        for fields, expected_attribute, expected_value in special_indent_cases:
            with self.subTest(fields=fields):
                edit = manager._normalize_style_edits(
                    {"styles": [{"style_id": "Heading1", **fields}]}
                )[0]
                paragraph_properties = etree.Element(qn("pPr"))
                manager._apply_paragraph_edits(paragraph_properties, edit)
                indentation = paragraph_properties.find(
                    "w:ind", namespaces=NS
                )
                self.assertEqual(
                    indentation.get(qn(expected_attribute)), expected_value
                )
                opposite = (
                    "hangingChars"
                    if expected_attribute == "firstLineChars"
                    else "firstLineChars"
                )
                self.assertIsNone(indentation.get(qn(opposite)))

    def test_point_indents_round_trip_with_character_tombstones(
        self,
    ) -> None:
        point_pack = self.working_dir / "point-indent.wfstyle"
        point_manifest = manager.derive_style_pack(
            self.pack,
            point_pack,
            {
                "styles": [
                    {
                        "style_id": "Heading1",
                        "left_indent_pt": 12.0,
                        "right_indent_pt": 6.0,
                        "first_line_indent_pt": 18.0,
                        "hanging_indent_pt": 0.0,
                    }
                ]
            },
        )
        expected_first_line = {
            "left": "240",
            "start": "240",
            "leftChars": "0",
            "startChars": "0",
            "right": "120",
            "end": "120",
            "rightChars": "0",
            "endChars": "0",
            "firstLine": "360",
            "firstLineChars": "0",
        }
        self.assertEqual(
            point_manifest["heading_paragraph_properties"]["Heading1"]["ind"],
            expected_first_line,
        )
        point_preview = preview_for(point_manifest, "Heading1")
        self.assertEqual(point_preview["left_indent_pt"], 12.0)
        self.assertEqual(point_preview["right_indent_pt"], 6.0)
        self.assertEqual(point_preview["first_line_indent_pt"], 18.0)
        self.assertIsNone(point_preview["left_indent_chars"])
        self.assertIsNone(point_preview["right_indent_chars"])
        self.assertIsNone(point_preview["first_line_indent_chars"])

        _loaded, point_entries = manager.load_style_pack(point_pack)
        for part_name in ("word/styles.xml", "word/stylesWithEffects.xml"):
            indentation = style_for_id(
                xml(point_entries, part_name), "Heading1"
            ).find("w:pPr/w:ind", namespaces=NS)
            self.assertIsNotNone(indentation, part_name)
            for attribute, expected in expected_first_line.items():
                self.assertEqual(
                    indentation.get(qn(attribute)), expected, part_name
                )
            for attribute in (
                "hanging",
                "hangingChars",
            ):
                self.assertIsNone(indentation.get(qn(attribute)), part_name)

        point_output = self.working_dir / "point-indent.docx"
        manager.apply_style_pack(
            point_pack,
            FIXTURES / "target-plain-headings.docx",
            point_output,
        )
        output_indentation = paragraph_for_text(
            xml(read_zip(point_output), "word/document.xml"), "项目概述"
        ).find("w:pPr/w:ind", namespaces=NS)
        self.assertEqual(output_indentation.attrib, {
            qn(attribute): value
            for attribute, value in expected_first_line.items()
        })

        hanging_pack = self.working_dir / "point-hanging-indent.wfstyle"
        hanging_manifest = manager.derive_style_pack(
            point_pack,
            hanging_pack,
            {
                "styles": [
                    {
                        "style_id": "Heading1",
                        "first_line_indent_pt": 0.0,
                        "hanging_indent_pt": 9.0,
                    }
                ]
            },
        )
        hanging_indent = hanging_manifest[
            "heading_paragraph_properties"
        ]["Heading1"]["ind"]
        self.assertEqual(hanging_indent["hanging"], "180")
        self.assertNotIn("firstLine", hanging_indent)
        self.assertNotIn("firstLineChars", hanging_indent)
        hanging_preview = preview_for(hanging_manifest, "Heading1")
        self.assertEqual(hanging_preview["hanging_indent_pt"], 9.0)
        self.assertIsNone(hanging_preview["first_line_indent_pt"])

    def test_inherited_units_and_opposite_special_indent_are_overridden(
        self,
    ) -> None:
        base_pack = self.working_dir / "hierarchy-base.wfstyle"
        manager.create_style_pack(
            FIXTURES / "source-no-table.docx", base_pack
        )

        parent_hanging_pack = self.working_dir / "parent-hanging.wfstyle"
        manager.derive_style_pack(
            base_pack,
            parent_hanging_pack,
            {
                "styles": [
                    {
                        "style_id": "Normal",
                        "left_indent_chars": 2.0,
                        "right_indent_chars": 1.0,
                        "first_line_indent_chars": 0.0,
                        "hanging_indent_chars": 1.5,
                    }
                ]
            },
        )
        child_first_pack = self.working_dir / "child-first-line.wfstyle"
        child_first = manager.derive_style_pack(
            parent_hanging_pack,
            child_first_pack,
            {
                "styles": [
                    {
                        "style_id": "Heading1",
                        "left_indent_pt": 12.0,
                        "right_indent_pt": 6.0,
                        "first_line_indent_pt": 18.0,
                        "hanging_indent_pt": 0.0,
                    }
                ]
            },
        )
        first_preview = preview_for(child_first, "Heading1")
        self.assertEqual(first_preview["left_indent_pt"], 12.0)
        self.assertEqual(first_preview["right_indent_pt"], 6.0)
        self.assertEqual(first_preview["first_line_indent_pt"], 18.0)
        self.assertIsNone(first_preview["left_indent_chars"])
        self.assertIsNone(first_preview["right_indent_chars"])
        self.assertIsNone(first_preview["first_line_indent_chars"])
        self.assertIsNone(first_preview["hanging_indent_pt"])
        self.assertIsNone(first_preview["hanging_indent_chars"])
        first_direct = child_first["heading_paragraph_properties"][
            "Heading1"
        ]["ind"]
        self.assertEqual(first_direct["firstLine"], "360")
        self.assertEqual(first_direct["firstLineChars"], "0")
        self.assertNotIn("hanging", first_direct)
        self.assertNotIn("hangingChars", first_direct)

        parent_first_pack = self.working_dir / "parent-first-line.wfstyle"
        manager.derive_style_pack(
            base_pack,
            parent_first_pack,
            {
                "styles": [
                    {
                        "style_id": "Normal",
                        "first_line_indent_chars": 2.0,
                        "hanging_indent_chars": 0.0,
                    }
                ]
            },
        )
        child_hanging_pack = self.working_dir / "child-hanging.wfstyle"
        child_hanging = manager.derive_style_pack(
            parent_first_pack,
            child_hanging_pack,
            {
                "styles": [
                    {
                        "style_id": "Heading1",
                        "first_line_indent_pt": 0.0,
                        "hanging_indent_pt": 9.0,
                    }
                ]
            },
        )
        hanging_preview = preview_for(child_hanging, "Heading1")
        self.assertEqual(hanging_preview["hanging_indent_pt"], 9.0)
        self.assertIsNone(hanging_preview["hanging_indent_chars"])
        self.assertIsNone(hanging_preview["first_line_indent_pt"])
        self.assertIsNone(hanging_preview["first_line_indent_chars"])
        hanging_direct = child_hanging[
            "heading_paragraph_properties"
        ]["Heading1"]["ind"]
        self.assertEqual(hanging_direct["hanging"], "180")
        self.assertEqual(hanging_direct["hangingChars"], "0")
        self.assertNotIn("firstLine", hanging_direct)
        self.assertNotIn("firstLineChars", hanging_direct)

        invalid_payloads = (
            {"style_id": "Heading1", "line_spacing": 1.5},
            {
                "style_id": "Heading1",
                "left_indent_pt": 12.0,
                "left_indent_chars": 2.0,
            },
            {
                "style_id": "Heading1",
                "first_line_indent_chars": 2.0,
                "hanging_indent_pt": 12.0,
            },
            {"style_id": "Heading1", "space_before_pt": -0.05},
            {"style_id": "Heading1", "alignment": "diagonal"},
        )
        for raw in invalid_payloads:
            with self.subTest(raw=raw), self.assertRaises(core.TransferError):
                manager._normalize_style_edits({"styles": [raw]})

        malformed = copy.deepcopy(self.manifest)
        malformed.pop("pack_path", None)
        malformed["heading_paragraph_properties"]["Heading1"]["rPr"] = {}
        with self.assertRaisesRegex(core.TransferError, "未知属性"):
            manager._validate_style_pack_manifest(malformed)


if __name__ == "__main__":
    unittest.main()
