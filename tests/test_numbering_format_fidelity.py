#!/usr/bin/env python3
# [INPUT]: 依赖 __future__, hashlib, json, sys, tempfile, unittest, zipfile, pathlib, typing, lxml, make_fixtures, style_pack_manager, word_style_transfer
# [OUTPUT]: 提供 TEST_DIR, PROJECT_DIR, NS, qn(), read_zip(), xml(), style_for_id(), active_numbering_levels(), style_num_id(), paragraph_for_text_fragment(), canonical(), child_value(), geometry(), NumberingFormatFidelityTests, SharedNumberLabelFontTests, MultiNumIdAndManualPrefixTests
# [POS]: 验证编号字体、标点、几何和手工前缀保真
# [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
"""Regression tests for exact heading-number label format migration."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Callable, Dict

from lxml import etree


TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(PROJECT_DIR))

import make_fixtures as fixtures  # noqa: E402
import style_pack_manager as manager  # noqa: E402
import word_style_transfer as core  # noqa: E402


NS = {"w": core.W_NS}


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


def active_numbering_levels(
    entries: Dict[str, bytes], style_id: str = "Heading1"
) -> Dict[int, etree._Element]:
    styles = xml(entries, "word/styles.xml")
    style = style_for_id(styles, style_id)
    num_id_node = style.find("w:pPr/w:numPr/w:numId", namespaces=NS)
    if num_id_node is None:
        raise AssertionError("numbered style has no numId: %s" % style_id)
    num_id = num_id_node.get(qn("val"))

    numbering = xml(entries, "word/numbering.xml")
    concrete = numbering.xpath(
        "./w:num[@w:numId=$num_id]", namespaces=NS, num_id=num_id
    )
    if len(concrete) != 1:
        raise AssertionError("concrete numId not found exactly once: %s" % num_id)
    abstract_id = concrete[0].find(
        "w:abstractNumId", namespaces=NS
    ).get(qn("val"))
    abstract = numbering.xpath(
        "./w:abstractNum[@w:abstractNumId=$abstract_id]",
        namespaces=NS,
        abstract_id=abstract_id,
    )
    if len(abstract) != 1:
        raise AssertionError(
            "abstract numbering not found exactly once: %s" % abstract_id
        )
    return {
        int(level.get(qn("ilvl"))): level
        for level in abstract[0].findall("w:lvl", namespaces=NS)
    }


def style_num_id(entries: Dict[str, bytes], style_id: str) -> str:
    styles = xml(entries, "word/styles.xml")
    style = style_for_id(styles, style_id)
    node = style.find("w:pPr/w:numPr/w:numId", namespaces=NS)
    if node is None:
        raise AssertionError("numbered style has no numId: %s" % style_id)
    return node.get(qn("val"))


def paragraph_for_text_fragment(
    document: etree._Element, fragment: str
) -> etree._Element:
    for paragraph in document.xpath("//w:p", namespaces=NS):
        text = "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))
        if fragment in text:
            return paragraph
    raise AssertionError("paragraph not found for fragment: %s" % fragment)


def canonical(node: etree._Element) -> bytes:
    return etree.tostring(node, method="c14n", exclusive=True)


def child_value(level: etree._Element, child: str) -> str:
    node = level.find("w:%s" % child, namespaces=NS)
    if node is None:
        raise AssertionError("numbering level has no %s" % child)
    return node.get(qn("val"))


def geometry(level: etree._Element) -> tuple[int, int, int, str]:
    tab = level.find("w:pPr/w:tabs/w:tab", namespaces=NS)
    indentation = level.find("w:pPr/w:ind", namespaces=NS)
    if tab is None or indentation is None:
        raise AssertionError("numbering level has incomplete paragraph geometry")
    return (
        int(indentation.get(qn("left"))),
        int(indentation.get(qn("hanging"))),
        int(tab.get(qn("pos"))),
        tab.get(qn("val")),
    )


def _active_numbering_abstract(
    entries: Dict[str, bytes],
    styles_member: str,
    numbering_member: str,
    style_id: str = "Heading1",
) -> tuple[etree._Element, etree._Element]:
    styles = etree.fromstring(entries[styles_member])
    style = style_for_id(styles, style_id)
    num_id_node = style.find("w:pPr/w:numPr/w:numId", namespaces=NS)
    if num_id_node is None:
        raise AssertionError("numbered style has no numId: %s" % style_id)
    num_id = num_id_node.get(qn("val"))

    numbering = etree.fromstring(entries[numbering_member])
    concrete = numbering.xpath(
        "./w:num[@w:numId=$num_id]", namespaces=NS, num_id=num_id
    )
    if len(concrete) != 1:
        raise AssertionError("concrete numId not found exactly once: %s" % num_id)
    abstract_id = concrete[0].find(
        "w:abstractNumId", namespaces=NS
    ).get(qn("val"))
    abstract = numbering.xpath(
        "./w:abstractNum[@w:abstractNumId=$abstract_id]",
        namespaces=NS,
        abstract_id=abstract_id,
    )
    if len(abstract) != 1:
        raise AssertionError(
            "abstract numbering not found exactly once: %s" % abstract_id
        )
    return numbering, abstract[0]


def _rewrite_active_numbering(
    path: Path,
    styles_member: str,
    numbering_member: str,
    mutate: Callable[[etree._Element], None],
    *,
    update_style_pack_checksums: bool = False,
) -> None:
    """Rewrite one fixture's active heading abstract without production helpers."""
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        entries = {info.filename: archive.read(info.filename) for info in infos}

    numbering, abstract = _active_numbering_abstract(
        entries, styles_member, numbering_member
    )
    mutate(abstract)
    entries[numbering_member] = etree.tostring(
        numbering,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )

    if update_style_pack_checksums:
        manifest = json.loads(entries["manifest.json"].decode("utf-8"))
        packed_parts = {
            name[len("parts/") :]: data
            for name, data in entries.items()
            if name.startswith("parts/") and not name.endswith("/")
        }
        checksums = {
            name: hashlib.sha256(data).hexdigest()
            for name, data in sorted(packed_parts.items())
        }
        manifest["part_sha256"] = checksums
        digest = hashlib.sha256()
        for name, checksum in sorted(checksums.items()):
            digest.update(name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(checksum.encode("ascii"))
            digest.update(b"\n")
        manifest["format_fingerprint"] = digest.hexdigest()
        entries["manifest.json"] = json.dumps(
            manifest,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

    temporary = path.with_name(".%s.rewrite" % path.name)
    if temporary.exists():
        temporary.unlink()
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for info in infos:
                archive.writestr(info, entries[info.filename])
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _set_h1_h2_common_songti_fonts(abstract: etree._Element) -> None:
    expected = {
        "ascii": "宋体",
        "hAnsi": "宋体",
        "eastAsia": "宋体",
        "cs": "宋体",
    }
    for level in (0, 1):
        level_node = abstract.find(
            "w:lvl[@w:ilvl='%d']" % level, namespaces=NS
        )
        if level_node is None:
            raise AssertionError("missing source numbering level %d" % level)
        fonts = level_node.find("w:rPr/w:rFonts", namespaces=NS)
        if fonts is None:
            raise AssertionError("source numbering level has no rFonts: %d" % level)
        fonts.attrib.clear()
        for name, value in expected.items():
            fonts.set(qn(name), value)


def _strip_deeper_number_label_run_properties(abstract: etree._Element) -> None:
    for level_node in abstract.findall("w:lvl", namespaces=NS):
        level = int(level_node.get(qn("ilvl")))
        if level < 3:
            continue
        run_properties = level_node.find("w:rPr", namespaces=NS)
        if run_properties is not None:
            level_node.remove(run_properties)


def _font_attributes(fonts: etree._Element) -> Dict[str, str]:
    return {
        etree.QName(name).localname: value
        for name, value in fonts.attrib.items()
    }


class NumberingFormatFidelityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(
            prefix="word-numbering-format-fidelity-"
        )
        cls.working_dir = Path(cls._temporary.name)
        cls.source = cls.working_dir / "rich-number-format-source.docx"
        cls.target = cls.working_dir / "five-level-target.docx"
        cls.pack = cls.working_dir / "rich-number-format.wfstyle"
        cls.output = cls.working_dir / "output.docx"
        fixtures.make_rich_numbering_format_source(cls.source)
        fixtures.make_five_level_heading_target(cls.target)
        manager.create_style_pack(cls.source, cls.pack, display_name="序号格式保真")
        manager.apply_style_pack(cls.pack, cls.target, cls.output)
        cls.source_entries = read_zip(cls.source)
        cls.output_entries = read_zip(cls.output)
        cls.source_levels = active_numbering_levels(cls.source_entries)
        cls.output_levels = active_numbering_levels(cls.output_entries)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_source_fixture_has_three_distinct_explicit_label_styles(self) -> None:
        self.assertEqual(set(self.source_levels), {0, 1, 2})
        expected = {
            0: ("Aptos Display", "STSong", "8A1538", "34", "b"),
            1: ("Courier New", "SimHei", "1F4E78", "30", "i"),
            2: ("Georgia", "KaiTi", "C00000", "56", "smallCaps"),
        }
        for level, (latin, east_asia, color, size, emphasis) in expected.items():
            r_pr = self.source_levels[level].find("w:rPr", namespaces=NS)
            self.assertIsNotNone(r_pr)
            fonts = r_pr.find("w:rFonts", namespaces=NS)
            self.assertEqual(fonts.get(qn("ascii")), latin)
            self.assertEqual(fonts.get(qn("hAnsi")), latin)
            self.assertEqual(fonts.get(qn("eastAsia")), east_asia)
            self.assertEqual(
                r_pr.find("w:color", namespaces=NS).get(qn("val")), color
            )
            self.assertEqual(
                r_pr.find("w:sz", namespaces=NS).get(qn("val")), size
            )
            self.assertIsNotNone(r_pr.find("w:%s" % emphasis, namespaces=NS))

    def test_h1_h2_h3_number_label_rpr_is_copied_exactly(self) -> None:
        self.assertTrue({0, 1, 2, 3, 4}.issubset(self.output_levels))
        for level in (0, 1, 2):
            source_r_pr = self.source_levels[level].find("w:rPr", namespaces=NS)
            output_r_pr = self.output_levels[level].find("w:rPr", namespaces=NS)
            self.assertIsNotNone(source_r_pr)
            self.assertIsNotNone(output_r_pr)
            self.assertEqual(
                canonical(output_r_pr),
                canonical(source_r_pr),
                "number-label rPr drifted at heading level %d" % (level + 1),
            )

    def test_inferred_h4_h5_do_not_clone_h3_number_label_rpr(self) -> None:
        h3_r_pr = self.output_levels[2].find("w:rPr", namespaces=NS)
        self.assertIsNotNone(h3_r_pr)
        for level, style_id in ((3, "Heading4"), (4, "Heading5")):
            generated_r_pr = self.output_levels[level].find(
                "w:rPr", namespaces=NS
            )
            self.assertIsNone(
                generated_r_pr,
                "%s number label must inherit %s instead of retaining "
                "Heading3's independent label formatting"
                % (style_id, style_id),
            )

        # The corresponding generated paragraph styles are real and distinct,
        # so an absent lvl/rPr has an intentional style-format authority.
        styles = xml(self.output_entries, "word/styles.xml")
        h4 = style_for_id(styles, "Heading4")
        h5 = style_for_id(styles, "Heading5")
        self.assertEqual(
            h4.find("w:rPr/w:sz", namespaces=NS).get(qn("val")), "24"
        )
        self.assertEqual(
            h5.find("w:rPr/w:sz", namespaces=NS).get(qn("val")), "20"
        )

    def test_numbering_geometry_suffix_and_alignment_are_preserved_and_extended(self) -> None:
        expected_geometry = {
            0: (600, 300, 600, "num"),
            1: (960, 300, 960, "num"),
            2: (1320, 300, 1320, "num"),
            3: (1680, 300, 1680, "num"),
            4: (2040, 300, 2040, "num"),
        }
        for level in range(5):
            output_level = self.output_levels[level]
            self.assertEqual(geometry(output_level), expected_geometry[level])
            self.assertEqual(child_value(output_level, "suff"), "space")
            self.assertEqual(child_value(output_level, "lvlJc"), "right")

        # The original three levels must remain byte-for-byte equivalent for
        # paragraph geometry and marker layout controls.
        for level in (0, 1, 2):
            self.assertEqual(
                canonical(
                    self.output_levels[level].find("w:pPr", namespaces=NS)
                ),
                canonical(
                    self.source_levels[level].find("w:pPr", namespaces=NS)
                ),
            )
            for child in ("suff", "lvlJc"):
                self.assertEqual(
                    child_value(self.output_levels[level], child),
                    child_value(self.source_levels[level], child),
                )

        self.assertEqual(child_value(self.output_levels[3], "lvlText"), "%1.%2.%3.%4")
        self.assertEqual(child_value(self.output_levels[4], "lvlText"), "%1.%2.%3.%4.%5")


class SharedNumberLabelFontTests(unittest.TestCase):
    EXPECTED_FONTS = {
        "ascii": "宋体",
        "hAnsi": "宋体",
        "eastAsia": "宋体",
        "cs": "宋体",
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(
            prefix="word-shared-number-label-font-tests-"
        )
        cls.working_dir = Path(cls._temporary.name)
        cls.source = cls.working_dir / "shared-h1-h2-number-font.docx"
        cls.target = cls.working_dir / "five-level-target.docx"
        cls.fresh_pack = cls.working_dir / "fresh.wfstyle"
        cls.fresh_output = cls.working_dir / "fresh-output.docx"
        cls.legacy_pack = cls.working_dir / "v231-no-deeper-rpr.wfstyle"
        cls.legacy_output = cls.working_dir / "legacy-output.docx"

        fixtures.make_rich_numbering_format_source(cls.source)
        _rewrite_active_numbering(
            cls.source,
            "word/styles.xml",
            "word/numbering.xml",
            _set_h1_h2_common_songti_fonts,
        )
        fixtures.make_five_level_heading_target(cls.target)

        manager.create_style_pack(
            cls.source,
            cls.fresh_pack,
            display_name="一二级共同序号字体",
        )
        _, cls.fresh_stats = manager.apply_style_pack(
            cls.fresh_pack, cls.target, cls.fresh_output
        )
        cls.source_entries = read_zip(cls.source)
        cls.fresh_entries = read_zip(cls.fresh_output)

        cls.legacy_pack.write_bytes(cls.fresh_pack.read_bytes())
        _rewrite_active_numbering(
            cls.legacy_pack,
            "parts/word/styles.xml",
            "parts/word/numbering.xml",
            _strip_deeper_number_label_run_properties,
            update_style_pack_checksums=True,
        )
        _, cls.legacy_pack_entries = manager.load_style_pack(cls.legacy_pack)
        _, cls.legacy_stats = manager.apply_style_pack(
            cls.legacy_pack, cls.target, cls.legacy_output
        )
        cls.legacy_output_entries = read_zip(cls.legacy_output)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def assert_deeper_levels_inherit_only_common_fonts(
        self, entries: Dict[str, bytes]
    ) -> None:
        levels = active_numbering_levels(entries)
        self.assertTrue({3, 4}.issubset(levels))
        deeper_levels = {
            level: level_node
            for level, level_node in levels.items()
            if level >= 3
        }
        self.assertTrue(deeper_levels)
        for level, level_node in sorted(deeper_levels.items()):
            with self.subTest(level=level):
                run_properties = level_node.find("w:rPr", namespaces=NS)
                self.assertIsNotNone(
                    run_properties,
                    "Heading %d number label lost the shared H1/H2 font"
                    % (level + 1),
                )
                self.assertEqual(
                    [
                        etree.QName(child).localname
                        for child in run_properties
                    ],
                    ["rFonts"],
                    "deeper number labels may inherit only the common font; "
                    "size, colour and emphasis must remain style-driven",
                )
                fonts = run_properties.find("w:rFonts", namespaces=NS)
                self.assertIsNotNone(fonts)
                self.assertEqual(
                    _font_attributes(fonts), self.EXPECTED_FONTS
                )
                for forbidden in ("sz", "szCs", "color", "b", "bCs"):
                    self.assertIsNone(
                        run_properties.find("w:%s" % forbidden, namespaces=NS)
                    )

    def test_fixture_has_common_h1_h2_songti_but_different_h3_font(self) -> None:
        levels = active_numbering_levels(self.source_entries)
        for level in (0, 1):
            fonts = levels[level].find("w:rPr/w:rFonts", namespaces=NS)
            self.assertIsNotNone(fonts)
            self.assertEqual(_font_attributes(fonts), self.EXPECTED_FONTS)

        h3_fonts = levels[2].find("w:rPr/w:rFonts", namespaces=NS)
        self.assertIsNotNone(h3_fonts)
        self.assertNotEqual(_font_attributes(h3_fonts), self.EXPECTED_FONTS)
        self.assertEqual(h3_fonts.get(qn("ascii")), "Georgia")
        self.assertEqual(h3_fonts.get(qn("eastAsia")), "KaiTi")

    def test_fresh_pack_applies_only_common_h1_h2_fonts_to_every_deeper_level(
        self,
    ) -> None:
        self.assert_deeper_levels_inherit_only_common_fonts(self.fresh_entries)

    def test_v231_pack_without_deeper_rpr_is_repaired_during_apply(self) -> None:
        packed_levels = active_numbering_levels(self.legacy_pack_entries)
        for level in (3, 4):
            self.assertIsNone(
                packed_levels[level].find("w:rPr", namespaces=NS),
                "legacy fixture must represent v2.3.1's missing deeper rPr",
            )

        self.assert_deeper_levels_inherit_only_common_fonts(
            self.legacy_output_entries
        )
        self.assertTrue(
            any("序号字体" in warning for warning in self.legacy_stats.warnings),
            self.legacy_stats.warnings,
        )


class MultiNumIdAndManualPrefixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(
            prefix="word-multi-numid-prefix-"
        )
        cls.working_dir = Path(cls._temporary.name)
        cls.source = cls.working_dir / "multi-numid-source.docx"
        cls.target = cls.working_dir / "typed-prefix-target.docx"
        cls.pack = cls.working_dir / "multi-numid.wfstyle"
        cls.output = cls.working_dir / "output.docx"
        fixtures.make_multi_numid_heading_source(cls.source)
        fixtures.make_manual_heading_prefix_target(cls.target)
        cls.manifest = manager.create_style_pack(
            cls.source, cls.pack, display_name="多 numId 与手工前缀"
        )
        manager.apply_style_pack(cls.pack, cls.target, cls.output)
        cls.source_entries = read_zip(cls.source)
        cls.target_entries = read_zip(cls.target)
        cls.output_entries = read_zip(cls.output)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_fixture_has_three_numids_start_override_and_split_prefix(self) -> None:
        source_num_ids = {
            style_num_id(self.source_entries, style_id)
            for style_id in ("Heading1", "Heading2", "Heading3")
        }
        self.assertEqual(len(source_num_ids), 3)

        h1_num_id = style_num_id(self.source_entries, "Heading1")
        numbering = xml(self.source_entries, "word/numbering.xml")
        start_override = numbering.xpath(
            "./w:num[@w:numId=$num_id]/w:lvlOverride[@w:ilvl='0']"
            "/w:startOverride/@w:val",
            namespaces=NS,
            num_id=h1_num_id,
        )
        self.assertEqual(start_override, ["3"])

        target_document = xml(self.target_entries, "word/document.xml")
        split = paragraph_for_text_fragment(target_document, "技术路线")
        self.assertEqual(
            "".join(split.xpath(".//w:t/text()", namespaces=NS)),
            "3.1.1  技术路线",
        )
        self.assertGreaterEqual(len(split.xpath("./w:r", namespaces=NS)), 4)
        self.assertGreaterEqual(len(split.xpath(".//w:t", namespaces=NS)), 4)

    def test_compatible_multi_numids_are_unified_for_h1_through_h5(self) -> None:
        output_num_ids = {
            style_num_id(self.output_entries, style_id)
            for style_id in (
                "Heading1",
                "Heading2",
                "Heading3",
                "Heading4",
                "Heading5",
            )
        }
        self.assertEqual(
            len(output_num_ids),
            1,
            "compatible H1-H3 schemes must be materialized into one list",
        )
        levels = active_numbering_levels(self.output_entries, "Heading1")
        self.assertTrue({0, 1, 2, 3, 4}.issubset(levels))

        manifest_rules = self.manifest["heading_numbering"]
        self.assertEqual(
            set(manifest_rules),
            {"Heading1", "Heading2", "Heading3", "Heading4", "Heading5"},
        )
        self.assertEqual(
            len({str(rule["num_id"]) for rule in manifest_rules.values()}), 1
        )

    def test_each_source_numid_contributes_its_authoritative_level_format(self) -> None:
        children = (
            "start",
            "numFmt",
            "pStyle",
            "suff",
            "lvlText",
            "lvlJc",
            "pPr",
            "rPr",
        )
        for level, style_id in enumerate(
            ("Heading1", "Heading2", "Heading3")
        ):
            source_level = active_numbering_levels(
                self.source_entries, style_id
            )[level]
            output_level = active_numbering_levels(
                self.output_entries, style_id
            )[level]
            for child in children:
                source_child = source_level.find("w:%s" % child, namespaces=NS)
                output_child = output_level.find("w:%s" % child, namespaces=NS)
                with self.subTest(style_id=style_id, child=child):
                    self.assertEqual(
                        canonical(output_child),
                        canonical(source_child),
                        "%s drifted while merging %s" % (child, style_id),
                    )

        # These values come from three different source abstracts.  Checking
        # them explicitly makes a wrong "copy every level from H1 numId" merge
        # easy to diagnose.
        unified = active_numbering_levels(self.output_entries, "Heading1")
        self.assertEqual(child_value(unified[0], "lvlText"), "第%1章")
        self.assertEqual(child_value(unified[1], "lvlText"), "%1.%2")
        self.assertEqual(child_value(unified[2], "lvlText"), "%1.%2.%3")
        expected_colors = {0: "8A1538", 1: "1F4E78", 2: "C00000"}
        for level, color in expected_colors.items():
            self.assertEqual(
                unified[level].find("w:rPr/w:color", namespaces=NS).get(qn("val")),
                color,
            )

    def test_unified_numbering_preserves_h1_start_override_three(self) -> None:
        unified_num_id = style_num_id(self.output_entries, "Heading1")
        numbering = xml(self.output_entries, "word/numbering.xml")
        start_override = numbering.xpath(
            "./w:num[@w:numId=$num_id]/w:lvlOverride[@w:ilvl='0']"
            "/w:startOverride/@w:val",
            namespaces=NS,
            num_id=unified_num_id,
        )
        self.assertEqual(start_override, ["3"])
        self.assertEqual(
            self.manifest["heading_numbering"]["Heading1"]["start"], 3
        )

    def test_typed_heading_prefixes_are_removed_across_runs_but_body_numbers_remain(self) -> None:
        document = xml(self.output_entries, "word/document.xml")
        output_paragraphs = [
            "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))
            for paragraph in document.xpath("//w:body/w:p", namespaces=NS)
        ]
        self.assertEqual(
            output_paragraphs,
            [
                "项目总览",
                "建设范围",
                "技术路线",
                "接口设计",
                "字段校验",
                "正文保留数字 3.1、3.1.1，以及第三章的历史说明。",
                "2026 年第 3 季度数据也必须保持不变。",
            ],
        )
        for removed in ("第三章", "3.1  ", "3.1.1  "):
            self.assertNotIn(removed, output_paragraphs[:3])

        # Prefix cleanup must not flatten the heading or remove its automatic
        # numbering association.
        for style_id, text in zip(
            ("Heading1", "Heading2", "Heading3"),
            ("项目总览", "建设范围", "技术路线"),
        ):
            paragraph = paragraph_for_text_fragment(document, text)
            self.assertEqual(
                paragraph.find("w:pPr/w:pStyle", namespaces=NS).get(qn("val")),
                style_id,
            )
            self.assertIsNotNone(
                paragraph.find("w:pPr/w:numPr", namespaces=NS)
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
