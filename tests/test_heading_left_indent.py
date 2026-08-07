#!/usr/bin/env python3
"""Regression coverage for numbered headings gaining a list-level left indent.

The source of the reported 0.49-inch value is not the Heading 3 paragraph
style.  It is ``w:lvl/w:pPr/w:ind/@w:left`` in the multilevel-numbering
definition (709 twips = 0.49236 inches).  A style pack must preserve that list
definition, including its tab and hanging geometry, while making the copied
heading paragraph obey the source heading style's zero/absent Left setting.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Dict, Optional, Tuple

from lxml import etree


TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
FIXTURES = TEST_DIR / "fixtures"
sys.path.insert(0, str(PROJECT_DIR))

import style_pack_manager as manager  # noqa: E402
import word_style_transfer as core  # noqa: E402


NS = {"w": core.W_NS}
HEADING_TEXT = "技术路线"
HEADING_STYLE_ID = "Heading3"
REPORTED_LEFT_TWIPS = 709  # 709 / 1440 = 0.49236 inches (Word shows 0.49")
ABSENT_DIRECT_INDENT_CASES = (
    ("Heading1", "格式源一级标题", "项目概述", 0, 432),
    ("Heading2", "格式源二级标题", "建设目标", 1, 576),
    ("Heading3", "格式源三级标题", "技术路线", 2, 720),
)


def qn(local: str) -> str:
    return "{%s}%s" % (core.W_NS, local)


def read_zip(path: Path) -> Dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise AssertionError("damaged DOCX member: %s" % bad)
        return {name: archive.read(name) for name in archive.namelist()}


def write_zip(path: Path, entries: Dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def remove_manifest_field_from_pack(
    source_pack: Path, legacy_pack: Path, field_name: str
) -> Dict[str, object]:
    """Clone a valid pack while simulating a manifest from an older release."""
    with zipfile.ZipFile(source_pack, "r") as archive:
        members = {name: archive.read(name) for name in archive.namelist()}

    manifest = json.loads(members["manifest.json"].decode("utf-8"))
    if field_name not in manifest:
        raise AssertionError("new pack did not contain field: %s" % field_name)
    manifest.pop(field_name)
    members["manifest.json"] = json.dumps(
        manifest,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    write_zip(legacy_pack, members)
    return manifest


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


def paragraph_for_text(document: etree._Element, text: str) -> etree._Element:
    for paragraph in document.xpath("//w:p", namespaces=NS):
        value = "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))
        if value == text:
            return paragraph
    raise AssertionError("paragraph not found: %s" % text)


def _integer_attribute(
    node: Optional[etree._Element], *local_names: str
) -> Optional[int]:
    if node is None:
        return None
    for local_name in local_names:
        raw = node.get(qn(local_name))
        if raw is not None:
            return int(raw)
    return None


def effective_style_left(styles: etree._Element, style_id: str) -> int:
    """Resolve the style hierarchy's Left value, defaulting to Word's zero."""
    seen = set()
    current_id: Optional[str] = style_id
    while current_id and current_id not in seen:
        seen.add(current_id)
        style = style_for_id(styles, current_id)
        left = _integer_attribute(
            style.find("w:pPr/w:ind", namespaces=NS), "start", "left"
        )
        if left is not None:
            return left
        based_on = style.find("w:basedOn", namespaces=NS)
        current_id = based_on.get(qn("val")) if based_on is not None else None

    default_left = _integer_attribute(
        styles.find("w:docDefaults/w:pPrDefault/w:pPr/w:ind", namespaces=NS),
        "start",
        "left",
    )
    return default_left if default_left is not None else 0


def paragraph_numbering_reference(
    entries: Dict[str, bytes], paragraph: etree._Element
) -> Tuple[str, int]:
    num_pr = paragraph.find("w:pPr/w:numPr", namespaces=NS)
    if num_pr is None:
        style_ref = paragraph.find("w:pPr/w:pStyle", namespaces=NS)
        if style_ref is None:
            raise AssertionError("heading has neither direct nor styled numbering")
        styles = xml(entries, "word/styles.xml")
        style = style_for_id(styles, style_ref.get(qn("val")))
        num_pr = style.find("w:pPr/w:numPr", namespaces=NS)
    if num_pr is None:
        raise AssertionError("heading numbering reference is missing")
    num_id = num_pr.find("w:numId", namespaces=NS)
    ilvl = num_pr.find("w:ilvl", namespaces=NS)
    if num_id is None or ilvl is None:
        raise AssertionError("heading numbering reference is incomplete")
    return num_id.get(qn("val")), int(ilvl.get(qn("val")))


def active_numbering_level(
    entries: Dict[str, bytes], paragraph: etree._Element
) -> etree._Element:
    num_id, level_index = paragraph_numbering_reference(entries, paragraph)
    numbering = xml(entries, "word/numbering.xml")
    concrete = numbering.xpath(
        "./w:num[@w:numId=$num_id]", namespaces=NS, num_id=num_id
    )
    if len(concrete) != 1:
        raise AssertionError("numId not found exactly once: %s" % num_id)
    abstract_ref = concrete[0].find("w:abstractNumId", namespaces=NS)
    if abstract_ref is None:
        raise AssertionError("numId has no abstract numbering reference")
    abstract_id = abstract_ref.get(qn("val"))
    levels = numbering.xpath(
        "./w:abstractNum[@w:abstractNumId=$abstract_id]/w:lvl[@w:ilvl=$level]",
        namespaces=NS,
        abstract_id=abstract_id,
        level=str(level_index),
    )
    if len(levels) != 1:
        raise AssertionError(
            "numbering level not found exactly once: %s/%d"
            % (abstract_id, level_index)
        )
    return levels[0]


def effective_word_left(
    entries: Dict[str, bytes], paragraph: etree._Element
) -> int:
    """Model the value Word exposes as Paragraph > Indentation > Left.

    A direct paragraph value wins.  Without one, the active numbering level's
    list indentation wins over the paragraph style and is the exact path that
    produced the reported 0.49-inch value.
    """
    direct_left = _integer_attribute(
        paragraph.find("w:pPr/w:ind", namespaces=NS), "start", "left"
    )
    if direct_left is not None:
        return direct_left

    level_left = _integer_attribute(
        active_numbering_level(entries, paragraph).find(
            "w:pPr/w:ind", namespaces=NS
        ),
        "start",
        "left",
    )
    if level_left is not None:
        return level_left

    style_ref = paragraph.find("w:pPr/w:pStyle", namespaces=NS)
    if style_ref is None:
        return 0
    return effective_style_left(
        xml(entries, "word/styles.xml"), style_ref.get(qn("val"))
    )


def canonical(node: Optional[etree._Element]) -> Optional[bytes]:
    if node is None:
        return None
    return etree.tostring(node, method="c14n", exclusive=True)


def make_reported_source(
    source_path: Path,
    direct_left_attribute: Optional[str] = None,
    direct_left_value: Optional[int] = None,
) -> None:
    """Create a stable fixture with the real 709-twip (0.49-inch) trigger.

    The real template headings carry a direct ``firstLineChars=0`` even though
    their Left value is absent.  Optional ``left``/``start`` arguments create
    the counterexample where a template intentionally requests a non-zero
    direct Left and that explicit choice must win over the zero default.
    """
    if (direct_left_attribute is None) != (direct_left_value is None):
        raise ValueError("direct Left attribute and value must be supplied together")
    if direct_left_attribute not in {None, "left", "start"}:
        raise ValueError("unsupported direct Left attribute: %s" % direct_left_attribute)

    entries = read_zip(FIXTURES / "source-numbered-headings.docx")
    styles = xml(entries, "word/styles.xml")
    heading_style = style_for_id(styles, HEADING_STYLE_ID)
    style_indentation = heading_style.find("w:pPr/w:ind", namespaces=NS)
    if style_indentation is not None:
        for attribute in ("start", "left", "startChars", "leftChars"):
            style_indentation.attrib.pop(qn(attribute), None)
    entries["word/styles.xml"] = etree.tostring(
        styles, xml_declaration=True, encoding="UTF-8", standalone=True
    )

    document = xml(entries, "word/document.xml")
    source_heading = paragraph_for_text(document, "格式源三级标题")
    source_heading_properties = source_heading.find("w:pPr", namespaces=NS)
    if source_heading_properties is None:
        raise AssertionError("source heading has no paragraph properties")
    source_heading_indentation = source_heading_properties.find(
        "w:ind", namespaces=NS
    )
    if source_heading_indentation is None:
        source_heading_indentation = etree.SubElement(
            source_heading_properties, qn("ind")
        )
    source_heading_indentation.set(qn("firstLineChars"), "0")
    if direct_left_attribute is not None and direct_left_value is not None:
        source_heading_indentation.set(
            qn(direct_left_attribute), str(direct_left_value)
        )

    # Use two actual Heading 3 paragraphs so the manifest field exercises a
    # genuine per-style consensus rather than accepting a one-item sample.
    matching_heading = copy.deepcopy(source_heading)
    matching_text = matching_heading.find(".//w:t", namespaces=NS)
    if matching_text is None:
        raise AssertionError("source heading has no text node")
    matching_text.text = "格式源三级标题补充"
    source_heading.addnext(matching_heading)
    entries["word/document.xml"] = etree.tostring(
        document, xml_declaration=True, encoding="UTF-8", standalone=True
    )

    source_level = active_numbering_level(entries, source_heading)
    level_indentation = source_level.find("w:pPr/w:ind", namespaces=NS)
    if level_indentation is None:
        raise AssertionError("source numbering level has no indentation")
    level_indentation.set(qn("left"), str(REPORTED_LEFT_TWIPS))
    level_indentation.set(qn("hanging"), str(REPORTED_LEFT_TWIPS))
    level_tab = source_level.find("w:pPr/w:tabs/w:tab", namespaces=NS)
    if level_tab is None:
        raise AssertionError("source numbering level has no number tab")
    level_tab.set(qn("pos"), str(REPORTED_LEFT_TWIPS))
    numbering = source_level.getroottree().getroot()
    entries["word/numbering.xml"] = etree.tostring(
        numbering, xml_declaration=True, encoding="UTF-8", standalone=True
    )
    write_zip(source_path, entries)


class HeadingLeftIndentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(
            prefix="word-heading-left-indent-"
        )
        cls.working_dir = Path(cls._temporary.name)
        cls.source = cls.working_dir / "source-heading-left-zero.docx"
        cls.pack = cls.working_dir / "heading-left-zero.wfstyle"
        cls.output = cls.working_dir / "output.docx"
        make_reported_source(cls.source)
        cls.created_manifest = manager.create_style_pack(
            cls.source, cls.pack, display_name="标题左缩进回归"
        )
        cls.applied_manifest, cls.stats = manager.apply_style_pack(
            cls.pack,
            FIXTURES / "target-plain-headings.docx",
            cls.output,
        )
        cls.source_entries = read_zip(cls.source)
        cls.output_entries = read_zip(cls.output)
        cls.source_document = xml(cls.source_entries, "word/document.xml")
        cls.output_document = xml(cls.output_entries, "word/document.xml")
        cls.source_heading = paragraph_for_text(
            cls.source_document, "格式源三级标题"
        )
        cls.output_heading = paragraph_for_text(cls.output_document, HEADING_TEXT)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_fixture_reproduces_numbering_left_without_style_left(self) -> None:
        source_styles = xml(self.source_entries, "word/styles.xml")
        self.assertEqual(
            effective_style_left(source_styles, HEADING_STYLE_ID),
            0,
            "the template Heading 3 style must define no non-zero Left indent",
        )
        source_level = active_numbering_level(
            self.source_entries, self.source_heading
        )
        source_level_indentation = source_level.find(
            "w:pPr/w:ind", namespaces=NS
        )
        self.assertEqual(
            _integer_attribute(source_level_indentation, "start", "left"),
            REPORTED_LEFT_TWIPS,
        )
        self.assertEqual(
            _integer_attribute(source_level_indentation, "hanging"),
            REPORTED_LEFT_TWIPS,
        )
        self.assertAlmostEqual(REPORTED_LEFT_TWIPS / 1440.0, 0.49, places=2)
        source_direct_indentation = self.source_heading.find(
            "w:pPr/w:ind", namespaces=NS
        )
        self.assertIsNotNone(source_direct_indentation)
        self.assertEqual(
            source_direct_indentation.get(qn("firstLineChars")), "0"
        )
        self.assertIsNone(
            _integer_attribute(source_direct_indentation, "start", "left"),
            "the real template paragraph has no direct Left value",
        )

    def test_absent_direct_indent_remains_absent_and_uses_numbering_geometry(
        self,
    ) -> None:
        """Distinguish an absent direct setting from an explicit zero.

        The stock numbered-heading fixture intentionally has no direct
        ``w:ind`` on H1/H2/H3.  Its list geometry is therefore authoritative;
        creating a new pack must not invent paragraph-level zero overrides.
        """
        source = FIXTURES / "source-numbered-headings.docx"
        pack = self.working_dir / "absent-direct-heading-indents.wfstyle"
        output = self.working_dir / "absent-direct-heading-indents.docx"
        source_entries = read_zip(source)
        source_document = xml(source_entries, "word/document.xml")

        for style_id, source_text, _target_text, level_index, expected_left in (
            ABSENT_DIRECT_INDENT_CASES
        ):
            source_heading = paragraph_for_text(source_document, source_text)
            self.assertIsNone(
                source_heading.find("w:pPr/w:ind", namespaces=NS), style_id
            )
            source_num_id, source_level_index = paragraph_numbering_reference(
                source_entries, source_heading
            )
            self.assertNotEqual(source_num_id, "0", style_id)
            self.assertEqual(source_level_index, level_index, style_id)
            source_level_indentation = active_numbering_level(
                source_entries, source_heading
            ).find("w:pPr/w:ind", namespaces=NS)
            self.assertEqual(
                _integer_attribute(
                    source_level_indentation, "start", "left"
                ),
                expected_left,
                style_id,
            )
            self.assertEqual(
                _integer_attribute(source_level_indentation, "hanging"),
                expected_left,
                style_id,
            )

        manifest = manager.create_style_pack(
            source, pack, display_name="标题未设置直接缩进"
        )
        saved_profiles = manifest.get("heading_paragraph_indents", {})
        self.assertIsInstance(saved_profiles, dict)
        for style_id, _source_text, _target_text, _level, _left in (
            ABSENT_DIRECT_INDENT_CASES
        ):
            with self.subTest(stage="created_manifest", style_id=style_id):
                self.assertNotIn(
                    style_id,
                    saved_profiles,
                    "%s has no direct source w:ind and must not gain a manifest "
                    "profile" % style_id,
                )

        applied_manifest, _stats = manager.apply_style_pack(
            pack,
            FIXTURES / "target-plain-headings.docx",
            output,
        )
        applied_profiles = applied_manifest.get("heading_paragraph_indents", {})
        output_entries = read_zip(output)
        output_document = xml(output_entries, "word/document.xml")
        for style_id, _source_text, target_text, level_index, expected_left in (
            ABSENT_DIRECT_INDENT_CASES
        ):
            output_heading = paragraph_for_text(output_document, target_text)
            with self.subTest(stage="applied_manifest", style_id=style_id):
                self.assertNotIn(style_id, applied_profiles)
            with self.subTest(stage="output", style_id=style_id):
                self.assertIsNone(
                    output_heading.find("w:pPr/w:ind", namespaces=NS),
                    "%s must continue inheriting its indentation from numbering.xml"
                    % style_id,
                )
                _num_id, output_level_index = paragraph_numbering_reference(
                    output_entries, output_heading
                )
                self.assertEqual(output_level_index, level_index, style_id)
                output_level_indentation = active_numbering_level(
                    output_entries, output_heading
                ).find("w:pPr/w:ind", namespaces=NS)
                self.assertEqual(
                    _integer_attribute(
                        output_level_indentation, "start", "left"
                    ),
                    expected_left,
                    style_id,
                )
                self.assertEqual(
                    _integer_attribute(output_level_indentation, "hanging"),
                    expected_left,
                    style_id,
                )
                self.assertEqual(
                    effective_word_left(output_entries, output_heading),
                    expected_left,
                    style_id,
                )

    def test_manifest_saves_and_applies_heading_paragraph_indent_consensus(
        self,
    ) -> None:
        expected = {
            "left": "0",
            "firstLineChars": "0",
            "hanging": "0",
        }
        self.assertIn("heading_paragraph_indents", self.created_manifest)
        self.assertEqual(
            self.created_manifest["heading_paragraph_indents"][HEADING_STYLE_ID],
            expected,
        )
        self.assertEqual(
            self.applied_manifest["heading_paragraph_indents"][HEADING_STYLE_ID],
            expected,
        )

        output_indentation = self.output_heading.find(
            "w:pPr/w:ind", namespaces=NS
        )
        self.assertIsNotNone(output_indentation)
        for attribute, value in expected.items():
            self.assertEqual(
                output_indentation.get(qn(attribute)), value, attribute
            )

    def test_applied_heading_left_follows_template_style_zero(self) -> None:
        source_style_left = effective_style_left(
            xml(self.source_entries, "word/styles.xml"), HEADING_STYLE_ID
        )
        self.assertEqual(source_style_left, 0)
        self.assertEqual(
            effective_word_left(self.output_entries, self.output_heading),
            source_style_left,
            "the copied heading must not expose the numbering level's 0.49-inch "
            "Left value in Word's paragraph dialog",
        )

        # The narrow override belongs on the copied heading paragraph.  The
        # reusable numbering definition remains intact for label/tab fidelity.
        direct_indentation = self.output_heading.find(
            "w:pPr/w:ind", namespaces=NS
        )
        self.assertIsNotNone(
            direct_indentation,
            "a direct zero indentation is required to override list geometry",
        )
        self.assertEqual(
            _integer_attribute(direct_indentation, "start", "left"), 0
        )
        self.assertEqual(
            _integer_attribute(
                direct_indentation, "hanging", "hangingChars"
            ),
            0,
        )
        self.assertEqual(direct_indentation.get(qn("firstLineChars")), "0")

    def test_legacy_pack_without_heading_indent_manifest_requires_reimport(
        self,
    ) -> None:
        legacy_pack = self.working_dir / "legacy-heading-left-zero.wfstyle"
        legacy_output = self.working_dir / "legacy-output.docx"
        legacy_manifest = remove_manifest_field_from_pack(
            self.pack,
            legacy_pack,
            "heading_paragraph_indents",
        )
        self.assertNotIn("heading_paragraph_indents", legacy_manifest)

        loaded_manifest, _entries = manager.load_style_pack(legacy_pack)
        self.assertNotIn("heading_paragraph_indents", loaded_manifest)
        _manifest, stats = manager.apply_style_pack(
            legacy_pack,
            FIXTURES / "target-plain-headings.docx",
            legacy_output,
        )
        self.assertTrue(
            any("重新导入一次格式源" in warning for warning in stats.warnings)
        )

        legacy_entries = read_zip(legacy_output)
        legacy_heading = paragraph_for_text(
            xml(legacy_entries, "word/document.xml"), HEADING_TEXT
        )
        direct_indentation = legacy_heading.find("w:pPr/w:ind", namespaces=NS)
        self.assertIsNone(
            direct_indentation,
            "an old pack has no evidence for a safe direct-indent override",
        )
        self.assertEqual(
            effective_word_left(legacy_entries, legacy_heading),
            REPORTED_LEFT_TWIPS,
        )

        # The original multilevel-list geometry remains byte-faithful.  Because
        # v2.3.0 packs did not retain source paragraph indentation, the safe
        # path is to request a one-time re-import instead of guessing zero.
        legacy_level = active_numbering_level(legacy_entries, legacy_heading)
        legacy_level_indentation = legacy_level.find(
            "w:pPr/w:ind", namespaces=NS
        )
        self.assertEqual(
            _integer_attribute(legacy_level_indentation, "start", "left"),
            REPORTED_LEFT_TWIPS,
        )
        self.assertEqual(
            _integer_attribute(legacy_level_indentation, "hanging"),
            REPORTED_LEFT_TWIPS,
        )
        legacy_tab = legacy_level.find("w:pPr/w:tabs/w:tab", namespaces=NS)
        self.assertIsNotNone(legacy_tab)
        self.assertEqual(
            _integer_attribute(legacy_tab, "pos"), REPORTED_LEFT_TWIPS
        )
        self.assertEqual(
            canonical(legacy_level.find("w:pPr", namespaces=NS)),
            canonical(
                active_numbering_level(
                    self.source_entries, self.source_heading
                ).find("w:pPr", namespaces=NS)
            ),
        )

    def test_explicit_nonzero_direct_left_or_start_is_preserved(self) -> None:
        cases = (("left", 360), ("start", 480))
        for attribute, value in cases:
            with self.subTest(attribute=attribute, value=value):
                source = self.working_dir / ("source-explicit-%s.docx" % attribute)
                pack = self.working_dir / ("explicit-%s.wfstyle" % attribute)
                output = self.working_dir / ("output-explicit-%s.docx" % attribute)
                make_reported_source(source, attribute, value)
                manifest = manager.create_style_pack(
                    source,
                    pack,
                    display_name="标题明确非零%s" % attribute,
                )
                applied_manifest, _stats = manager.apply_style_pack(
                    pack,
                    FIXTURES / "target-plain-headings.docx",
                    output,
                )
                output_entries = read_zip(output)
                output_heading = paragraph_for_text(
                    xml(output_entries, "word/document.xml"), HEADING_TEXT
                )

                saved = manifest["heading_paragraph_indents"][HEADING_STYLE_ID]
                self.assertEqual(saved[attribute], str(value))
                self.assertEqual(saved["firstLineChars"], "0")
                self.assertEqual(
                    applied_manifest["heading_paragraph_indents"][
                        HEADING_STYLE_ID
                    ][attribute],
                    str(value),
                )

                output_indentation = output_heading.find(
                    "w:pPr/w:ind", namespaces=NS
                )
                self.assertIsNotNone(output_indentation)
                self.assertEqual(
                    output_indentation.get(qn(attribute)), str(value)
                )
                self.assertEqual(
                    effective_word_left(output_entries, output_heading), value
                )
                num_id, level_index = paragraph_numbering_reference(
                    output_entries, output_heading
                )
                self.assertNotEqual(num_id, "0")
                self.assertEqual(level_index, 2)

    def test_numbering_remains_visible_and_format_faithful(self) -> None:
        num_id, level_index = paragraph_numbering_reference(
            self.output_entries, self.output_heading
        )
        self.assertNotEqual(num_id, "0")
        self.assertEqual(level_index, 2)

        source_level = active_numbering_level(
            self.source_entries, self.source_heading
        )
        output_level = active_numbering_level(
            self.output_entries, self.output_heading
        )
        for child in ("start", "numFmt", "suff", "lvlText", "lvlJc"):
            source_node = source_level.find("w:%s" % child, namespaces=NS)
            output_node = output_level.find("w:%s" % child, namespaces=NS)
            self.assertIsNotNone(source_node, child)
            self.assertIsNotNone(output_node, child)
            self.assertEqual(
                output_node.get(qn("val")), source_node.get(qn("val")), child
            )
        self.assertEqual(
            output_level.find("w:lvlText", namespaces=NS).get(qn("val")),
            "%1.%2.%3",
        )
        self.assertEqual(
            canonical(output_level.find("w:rPr", namespaces=NS)),
            canonical(source_level.find("w:rPr", namespaces=NS)),
        )
        self.assertEqual(
            canonical(output_level.find("w:pPr", namespaces=NS)),
            canonical(source_level.find("w:pPr", namespaces=NS)),
            "numbering tabs and hanging geometry must not be deleted to fix "
            "the paragraph-format Left value",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
