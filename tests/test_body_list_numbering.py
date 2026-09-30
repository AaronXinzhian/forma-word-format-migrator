#!/usr/bin/env python3
# [INPUT]: 依赖 __future__, copy, tempfile, unittest, zipfile, pathlib, lxml, sys, style_pack_manager, word_style_transfer
# [OUTPUT]: 提供 TEST_DIR, PROJECT_DIR, FIXTURES, NS, W_VAL, BodyListNumberingTests
# [POS]: 验证正文列表、编号隔离、重启和图片项目符号保留
# [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
"""Regression tests for target-owned body list numbering semantics."""

from __future__ import annotations

import copy
import tempfile
import unittest
import zipfile
from pathlib import Path

from lxml import etree


TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
FIXTURES = TEST_DIR / "fixtures"

import sys

sys.path.insert(0, str(PROJECT_DIR))

import style_pack_manager as manager  # noqa: E402
import word_style_transfer as core  # noqa: E402


NS = core.NS
W_VAL = core.qn(core.W_NS, "val")


def _read_zip(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _write_replacements(
    source: Path,
    destination: Path,
    replacements: dict[str, bytes],
) -> None:
    with zipfile.ZipFile(source) as archive:
        records = [
            (copy.copy(info), archive.read(info.filename))
            for info in archive.infolist()
        ]
    with zipfile.ZipFile(destination, "w") as archive:
        written: set[str] = set()
        for info, data in records:
            archive.writestr(info, replacements.get(info.filename, data))
            written.add(info.filename)
        for name, data in sorted(replacements.items()):
            if name not in written:
                archive.writestr(name, data)


def _write_without_numbering(source: Path, destination: Path) -> None:
    """Create a valid format source that genuinely has no numbering part."""
    with zipfile.ZipFile(source) as archive:
        records = [
            (copy.copy(info), archive.read(info.filename))
            for info in archive.infolist()
            if info.filename
            not in {
                "word/numbering.xml",
                "word/_rels/numbering.xml.rels",
            }
        ]
    replacements: dict[str, bytes] = {}
    for info, data in records:
        if info.filename == "word/_rels/document.xml.rels":
            rels = core.parse_xml(data, info.filename)
            for relationship in list(
                rels.findall(core.qn(core.PKG_REL_NS, "Relationship"))
            ):
                if core.relationship_role(relationship.get("Type", "")) == "numbering":
                    rels.remove(relationship)
            replacements[info.filename] = core.serialize_xml(rels)
        elif info.filename == "[Content_Types].xml":
            content_types = core.parse_xml(data, info.filename)
            core.remove_content_type_override(
                content_types, "word/numbering.xml"
            )
            replacements[info.filename] = core.serialize_xml(content_types)
    with zipfile.ZipFile(destination, "w") as archive:
        for info, data in records:
            archive.writestr(info, replacements.get(info.filename, data))


def _paragraph(text: str, num_id: str, level: int = 0) -> etree._Element:
    paragraph = etree.Element(core.qn(core.W_NS, "p"))
    ppr = etree.SubElement(paragraph, core.qn(core.W_NS, "pPr"))
    pstyle = etree.SubElement(ppr, core.qn(core.W_NS, "pStyle"))
    pstyle.set(W_VAL, "Normal")
    num_pr = etree.SubElement(ppr, core.qn(core.W_NS, "numPr"))
    ilvl = etree.SubElement(num_pr, core.qn(core.W_NS, "ilvl"))
    ilvl.set(W_VAL, str(level))
    concrete = etree.SubElement(num_pr, core.qn(core.W_NS, "numId"))
    concrete.set(W_VAL, num_id)
    # These visual properties must still be removed while numPr survives.
    spacing = etree.SubElement(ppr, core.qn(core.W_NS, "spacing"))
    spacing.set(core.qn(core.W_NS, "before"), "240")
    indentation = etree.SubElement(ppr, core.qn(core.W_NS, "ind"))
    indentation.set(core.qn(core.W_NS, "left"), "720")
    run = etree.SubElement(paragraph, core.qn(core.W_NS, "r"))
    run_properties = etree.SubElement(run, core.qn(core.W_NS, "rPr"))
    bold = etree.SubElement(run_properties, core.qn(core.W_NS, "b"))
    bold.set(W_VAL, "1")
    text_node = etree.SubElement(run, core.qn(core.W_NS, "t"))
    text_node.text = text
    return paragraph


def _set_level_value(level: etree._Element, tag: str, value: str) -> None:
    node = level.find("w:%s" % tag, namespaces=NS)
    if node is None:
        node = etree.SubElement(level, core.qn(core.W_NS, tag))
    node.set(W_VAL, value)


def _build_conflicting_target(base: Path, destination: Path) -> None:
    entries = _read_zip(base)
    numbering = core.parse_xml(entries["word/numbering.xml"], "numbering.xml")

    # Re-purpose target numId=1 as a distinctive bullet.  The format source
    # also owns numId=1, but with another definition, reproducing the collision
    # that made a coarse numPr-preservation fix unsafe.
    target_num = numbering.find("w:num[@w:numId='1']", namespaces=NS)
    assert target_num is not None
    target_abstract_id = target_num.xpath(
        "string(w:abstractNumId/@w:val)", namespaces=NS
    )
    target_abstract = numbering.find(
        "w:abstractNum[@w:abstractNumId='%s']" % target_abstract_id,
        namespaces=NS,
    )
    assert target_abstract is not None
    target_level = target_abstract.find("w:lvl[@w:ilvl='0']", namespaces=NS)
    assert target_level is not None
    _set_level_value(target_level, "numFmt", "bullet")
    _set_level_value(target_level, "lvlText", "◆")
    level_rpr = target_level.find("w:rPr", namespaces=NS)
    if level_rpr is None:
        level_rpr = etree.SubElement(target_level, core.qn(core.W_NS, "rPr"))
    fonts = level_rpr.find("w:rFonts", namespaces=NS)
    if fonts is None:
        fonts = etree.SubElement(level_rpr, core.qn(core.W_NS, "rFonts"))
    fonts.set(core.qn(core.W_NS, "ascii"), "Arial")
    fonts.set(core.qn(core.W_NS, "hAnsi"), "Arial")

    # A second abstract carries decimal numbering.  Two concrete instances
    # share it but must remain distinct sequences after transfer.
    decimal_abstract = copy.deepcopy(target_abstract)
    decimal_abstract.set(core.qn(core.W_NS, "abstractNumId"), "77")
    decimal_level = decimal_abstract.find(
        "w:lvl[@w:ilvl='0']", namespaces=NS
    )
    assert decimal_level is not None
    _set_level_value(decimal_level, "numFmt", "decimal")
    _set_level_value(decimal_level, "lvlText", "%1)")
    numbering.insert(numbering.index(target_num), decimal_abstract)

    first_decimal = etree.Element(core.qn(core.W_NS, "num"))
    first_decimal.set(core.qn(core.W_NS, "numId"), "77")
    reference = etree.SubElement(
        first_decimal, core.qn(core.W_NS, "abstractNumId")
    )
    reference.set(W_VAL, "77")
    override = etree.SubElement(
        first_decimal, core.qn(core.W_NS, "lvlOverride")
    )
    override.set(core.qn(core.W_NS, "ilvl"), "0")
    start = etree.SubElement(override, core.qn(core.W_NS, "startOverride"))
    start.set(W_VAL, "7")

    second_decimal = copy.deepcopy(first_decimal)
    second_decimal.set(core.qn(core.W_NS, "numId"), "78")
    second_override = second_decimal.find("w:lvlOverride", namespaces=NS)
    assert second_override is not None
    second_decimal.remove(second_override)
    numbering.append(first_decimal)
    numbering.append(second_decimal)

    document = core.parse_xml(entries["word/document.xml"], "document.xml")
    body = document.find("w:body", namespaces=NS)
    assert body is not None
    section = body.find("w:sectPr", namespaces=NS)
    insertion = body.index(section) if section is not None else len(body)
    for text, num_id in (
        ("保留项目甲", "1"),
        ("保留项目乙", "1"),
        ("从七开始", "77"),
        ("独立序列", "78"),
        ("明确取消编号", "0"),
    ):
        body.insert(insertion, _paragraph(text, num_id))
        insertion += 1

    # A heading's target direct list is not body-list semantics.  It must obey
    # the source heading system instead of retaining the target bullet.
    heading = _paragraph_for_text(document, "目标文档主标题")
    heading_ppr = heading.find("w:pPr", namespaces=NS)
    assert heading_ppr is not None
    heading_num = heading_ppr.find("w:numPr", namespaces=NS)
    if heading_num is not None:
        heading_ppr.remove(heading_num)
    heading_ppr.insert(1, copy.deepcopy(_paragraph("x", "1").find("w:pPr/w:numPr", namespaces=NS)))

    replacements = {
        "word/document.xml": core.serialize_xml(document),
        "word/numbering.xml": core.serialize_xml(numbering),
    }

    header_names = sorted(
        name
        for name in entries
        if name.startswith("word/header") and name.endswith(".xml")
    )
    if header_names:
        header_name = header_names[0]
        header = core.parse_xml(entries[header_name], header_name)
        header.append(_paragraph("页眉项目", "78"))
        replacements[header_name] = core.serialize_xml(header)

    _write_replacements(base, destination, replacements)


def _add_picture_bullet(source: Path, destination: Path) -> None:
    entries = _read_zip(source)
    numbering = core.parse_xml(entries["word/numbering.xml"], "numbering.xml")
    concrete = numbering.find("w:num[@w:numId='1']", namespaces=NS)
    assert concrete is not None
    abstract_id = concrete.xpath(
        "string(w:abstractNumId/@w:val)", namespaces=NS
    )
    abstract = numbering.find(
        "w:abstractNum[@w:abstractNumId='%s']" % abstract_id,
        namespaces=NS,
    )
    assert abstract is not None
    level = abstract.find("w:lvl[@w:ilvl='0']", namespaces=NS)
    assert level is not None

    picture_id = "91"
    picture_ref = etree.Element(core.qn(core.W_NS, "lvlPicBulletId"))
    picture_ref.set(W_VAL, picture_id)
    number_format = level.find("w:numFmt", namespaces=NS)
    level.insert(level.index(number_format) if number_format is not None else 0, picture_ref)

    vml_namespace = "urn:schemas-microsoft-com:vml"
    picture = etree.Element(core.qn(core.W_NS, "numPicBullet"))
    picture.set(core.qn(core.W_NS, "numPicBulletId"), picture_id)
    pict = etree.SubElement(picture, core.qn(core.W_NS, "pict"))
    shape = etree.SubElement(pict, "{%s}shape" % vml_namespace)
    shape.set("style", "width:8pt;height:8pt")
    image = etree.SubElement(shape, "{%s}imagedata" % vml_namespace)
    image.set(core.qn(core.R_NS, "id"), "rIdPictureBullet")
    numbering.insert(0, picture)

    relationships = etree.Element(
        core.qn(core.PKG_REL_NS, "Relationships"),
        nsmap={None: core.PKG_REL_NS},
    )
    relationship = etree.SubElement(
        relationships, core.qn(core.PKG_REL_NS, "Relationship")
    )
    relationship.set("Id", "rIdPictureBullet")
    relationship.set("Type", core.R_NS + "/image")
    relationship.set("Target", "media/image1.png")

    _write_replacements(
        source,
        destination,
        {
            "word/numbering.xml": core.serialize_xml(numbering),
            "word/_rels/numbering.xml.rels": core.serialize_xml(relationships),
        },
    )


def _append_paragraph_style(
    styles: etree._Element,
    style_id: str,
    based_on: str,
    *,
    num_id: str | None = None,
    level: int | None = None,
    outline: int | None = None,
) -> None:
    style = etree.Element(core.qn(core.W_NS, "style"))
    style.set(core.qn(core.W_NS, "type"), "paragraph")
    style.set(core.qn(core.W_NS, "customStyle"), "1")
    style.set(core.qn(core.W_NS, "styleId"), style_id)
    name = etree.SubElement(style, core.qn(core.W_NS, "name"))
    name.set(W_VAL, style_id)
    based = etree.SubElement(style, core.qn(core.W_NS, "basedOn"))
    based.set(W_VAL, based_on)
    ppr = etree.SubElement(style, core.qn(core.W_NS, "pPr"))
    if num_id is not None or level is not None:
        num_pr = etree.SubElement(ppr, core.qn(core.W_NS, "numPr"))
        if level is not None:
            ilvl = etree.SubElement(num_pr, core.qn(core.W_NS, "ilvl"))
            ilvl.set(W_VAL, str(level))
        if num_id is not None:
            concrete = etree.SubElement(num_pr, core.qn(core.W_NS, "numId"))
            concrete.set(W_VAL, num_id)
    if outline is not None:
        outline_node = etree.SubElement(ppr, core.qn(core.W_NS, "outlineLvl"))
        outline_node.set(W_VAL, str(outline))
    ext_list = styles.find("w:extLst", namespaces=NS)
    styles.insert(styles.index(ext_list) if ext_list is not None else len(styles), style)


def _styled_paragraph(
    text: str,
    style_id: str,
    direct_level: int | None = None,
) -> etree._Element:
    paragraph = etree.Element(core.qn(core.W_NS, "p"))
    ppr = etree.SubElement(paragraph, core.qn(core.W_NS, "pPr"))
    pstyle = etree.SubElement(ppr, core.qn(core.W_NS, "pStyle"))
    pstyle.set(W_VAL, style_id)
    if direct_level is not None:
        num_pr = etree.SubElement(ppr, core.qn(core.W_NS, "numPr"))
        ilvl = etree.SubElement(num_pr, core.qn(core.W_NS, "ilvl"))
        ilvl.set(W_VAL, str(direct_level))
    run = etree.SubElement(paragraph, core.qn(core.W_NS, "r"))
    text_node = etree.SubElement(run, core.qn(core.W_NS, "t"))
    text_node.text = text
    return paragraph


def _build_style_numbered_target(source: Path, destination: Path) -> None:
    entries = _read_zip(source)
    styles = core.parse_xml(entries["word/styles.xml"], "styles.xml")
    _append_paragraph_style(
        styles, "BodyListBase", "Normal", num_id="1", level=0
    )
    _append_paragraph_style(
        styles, "BodyListDerived", "BodyListBase", level=1
    )
    _append_paragraph_style(
        styles, "BodyListCancelled", "BodyListBase", num_id="0"
    )
    _append_paragraph_style(
        styles, "OutlineListStyle", "BodyListBase", outline=2
    )
    _append_paragraph_style(
        styles,
        "HeadingBasedBodyList",
        "Heading1",
        num_id="1",
        level=0,
        outline=9,
    )

    numbering = core.parse_xml(entries["word/numbering.xml"], "numbering.xml")
    concrete = numbering.find("w:num[@w:numId='1']", namespaces=NS)
    assert concrete is not None
    abstract_id = concrete.xpath(
        "string(w:abstractNumId/@w:val)", namespaces=NS
    )
    abstract = numbering.find(
        "w:abstractNum[@w:abstractNumId='%s']" % abstract_id,
        namespaces=NS,
    )
    assert abstract is not None
    level_zero = abstract.find("w:lvl[@w:ilvl='0']", namespaces=NS)
    assert level_zero is not None
    level_one = copy.deepcopy(level_zero)
    level_one.set(core.qn(core.W_NS, "ilvl"), "1")
    for linked_style in level_one.findall("w:pStyle", namespaces=NS):
        level_one.remove(linked_style)
    _set_level_value(level_one, "lvlText", "◇")
    abstract.append(level_one)

    document = core.parse_xml(entries["word/document.xml"], "document.xml")
    body = document.find("w:body", namespaces=NS)
    assert body is not None
    section = body.find("w:sectPr", namespaces=NS)
    insertion = body.index(section) if section is not None else len(body)
    for paragraph in (
        _styled_paragraph("样式列表基础", "BodyListBase"),
        _styled_paragraph("样式列表继承", "BodyListDerived"),
        _styled_paragraph("段落层级覆盖", "BodyListBase", direct_level=1),
        _styled_paragraph("样式取消编号", "BodyListCancelled"),
        _styled_paragraph("大纲列表必须排除", "OutlineListStyle"),
        _styled_paragraph("标题基式正文列表", "HeadingBasedBodyList"),
    ):
        body.insert(insertion, paragraph)
        insertion += 1

    _write_replacements(
        source,
        destination,
        {
            "word/styles.xml": core.serialize_xml(styles),
            "word/numbering.xml": core.serialize_xml(numbering),
            "word/document.xml": core.serialize_xml(document),
        },
    )


def _paragraph_for_text(root: etree._Element, text: str) -> etree._Element:
    for paragraph in root.xpath("//w:p", namespaces=NS):
        value = "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))
        if value == text:
            return paragraph
    raise AssertionError("paragraph not found: %s" % text)


def _paragraph_num_id(root: etree._Element, text: str) -> str:
    paragraph = _paragraph_for_text(root, text)
    values = paragraph.xpath("w:pPr/w:numPr/w:numId/@w:val", namespaces=NS)
    if len(values) != 1:
        raise AssertionError("paragraph has no unique numId: %s" % text)
    return str(values[0])


def _paragraph_level(root: etree._Element, text: str) -> int:
    paragraph = _paragraph_for_text(root, text)
    values = paragraph.xpath("w:pPr/w:numPr/w:ilvl/@w:val", namespaces=NS)
    if len(values) != 1:
        raise AssertionError("paragraph has no unique ilvl: %s" % text)
    return int(str(values[0]))


def _numbering_definition(
    numbering: etree._Element,
    num_id: str,
) -> tuple[etree._Element, etree._Element]:
    nums = numbering.xpath(
        "./w:num[@w:numId=$num_id]",
        namespaces=NS,
        num_id=num_id,
    )
    if len(nums) != 1:
        raise AssertionError("concrete numbering not found: %s" % num_id)
    abstract_id = nums[0].xpath(
        "string(w:abstractNumId/@w:val)", namespaces=NS
    )
    abstracts = numbering.xpath(
        "./w:abstractNum[@w:abstractNumId=$abstract_id]",
        namespaces=NS,
        abstract_id=abstract_id,
    )
    if len(abstracts) != 1:
        raise AssertionError("abstract numbering not found: %s" % abstract_id)
    return nums[0], abstracts[0]


class BodyListNumberingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tempdir = tempfile.TemporaryDirectory(
            prefix="forma-body-list-numbering-"
        )
        cls.work = Path(cls.tempdir.name)
        cls.target = cls.work / "target-conflict.docx"
        _build_conflicting_target(FIXTURES / "target.docx", cls.target)
        cls.pack = cls.work / "source.wfstyle"
        manager.create_style_pack(FIXTURES / "source.docx", cls.pack)
        cls.source_without_numbering = cls.work / "source-no-numbering.docx"
        _write_without_numbering(
            FIXTURES / "source.docx", cls.source_without_numbering
        )
        cls.picture_target = cls.work / "target-picture-bullet.docx"
        _add_picture_bullet(cls.target, cls.picture_target)
        cls.style_numbered_target = cls.work / "target-style-numbered.docx"
        _build_style_numbered_target(cls.target, cls.style_numbered_target)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tempdir.cleanup()

    def _assert_preserved_lists(
        self,
        output: Path,
        stats: core.TransferStats,
    ) -> None:
        entries = _read_zip(output)
        document = core.parse_xml(entries["word/document.xml"], "document.xml")
        numbering = core.parse_xml(entries["word/numbering.xml"], "numbering.xml")

        bullet_a = _paragraph_num_id(document, "保留项目甲")
        bullet_b = _paragraph_num_id(document, "保留项目乙")
        decimal_seven = _paragraph_num_id(document, "从七开始")
        decimal_independent = _paragraph_num_id(document, "独立序列")
        self.assertEqual(bullet_a, bullet_b)
        self.assertNotEqual(bullet_a, "1")
        self.assertNotEqual(decimal_seven, decimal_independent)
        self.assertEqual(_paragraph_num_id(document, "明确取消编号"), "0")

        heading = _paragraph_for_text(document, "目标文档主标题")
        self.assertIsNone(heading.find("w:pPr/w:numPr", namespaces=NS))

        bullet_num, bullet_abstract = _numbering_definition(numbering, bullet_a)
        self.assertIsNotNone(bullet_num)
        self.assertEqual(
            bullet_abstract.xpath(
                "string(w:lvl[@w:ilvl='0']/w:numFmt/@w:val)", namespaces=NS
            ),
            "bullet",
        )
        self.assertEqual(
            bullet_abstract.xpath(
                "string(w:lvl[@w:ilvl='0']/w:lvlText/@w:val)", namespaces=NS
            ),
            "◆",
        )

        seven_num, seven_abstract = _numbering_definition(
            numbering, decimal_seven
        )
        independent_num, independent_abstract = _numbering_definition(
            numbering, decimal_independent
        )
        self.assertEqual(
            seven_abstract.get(core.qn(core.W_NS, "abstractNumId")),
            independent_abstract.get(core.qn(core.W_NS, "abstractNumId")),
        )
        self.assertEqual(
            seven_abstract.xpath(
                "string(w:lvl[@w:ilvl='0']/w:numFmt/@w:val)", namespaces=NS
            ),
            "decimal",
        )
        self.assertEqual(
            seven_abstract.xpath(
                "string(w:lvl[@w:ilvl='0']/w:lvlText/@w:val)", namespaces=NS
            ),
            "%1)",
        )
        self.assertEqual(
            seven_num.xpath(
                "string(w:lvlOverride[@w:ilvl='0']/w:startOverride/@w:val)",
                namespaces=NS,
            ),
            "7",
        )
        self.assertFalse(
            independent_num.xpath("w:lvlOverride", namespaces=NS)
        )

        # The target numId=1 definition was isolated under a fresh ID, so the
        # source-owned numId=1 remains present instead of being overwritten.
        source_num_one, source_abstract_one = _numbering_definition(
            numbering, "1"
        )
        self.assertIsNotNone(source_num_one)
        self.assertNotEqual(
            source_abstract_one.xpath(
                "string(w:lvl[@w:ilvl='0']/w:lvlText/@w:val)", namespaces=NS
            ),
            "◆",
        )

        for text in ("保留项目甲", "保留项目乙", "从七开始", "独立序列"):
            paragraph = _paragraph_for_text(document, text)
            ppr = paragraph.find("w:pPr", namespaces=NS)
            self.assertIsNotNone(ppr)
            self.assertIsNone(ppr.find("w:spacing", namespaces=NS))
            self.assertIsNone(ppr.find("w:ind", namespaces=NS))
            run_properties = paragraph.find("w:r/w:rPr", namespaces=NS)
            self.assertIsNone(run_properties)

        header_names = sorted(
            name
            for name in entries
            if name.startswith("word/header") and name.endswith(".xml")
        )
        if header_names:
            header = core.parse_xml(entries[header_names[0]], header_names[0])
            header_num_id = _paragraph_num_id(header, "页眉项目")
            self.assertEqual(header_num_id, decimal_independent)

        inherited_fixture_num_id = _paragraph_num_id(
            document, "目标编号列表项目"
        )
        _numbering_definition(numbering, inherited_fixture_num_id)
        self.assertEqual(_paragraph_level(document, "目标编号列表项目"), 0)
        self.assertEqual(stats.style_list_paragraphs_materialized, 1)
        self.assertEqual(stats.body_list_paragraphs_preserved, 6)
        self.assertEqual(stats.target_numbering_definitions_imported, 4)
        self.assertEqual(stats.target_numbering_abstracts_imported, 3)
        self.assertTrue(
            any("避免与模板编号冲突" in warning for warning in stats.warnings)
        )

    def test_direct_transfer_preserves_body_lists_across_num_id_conflicts(self) -> None:
        output = self.work / "direct-output.docx"
        stats = core.transfer(
            FIXTURES / "source.docx",
            self.target,
            output,
            force=True,
        )
        self._assert_preserved_lists(output, stats)

    def test_style_pack_apply_preserves_body_lists_across_num_id_conflicts(self) -> None:
        output = self.work / "pack-output.docx"
        _manifest, stats = manager.apply_style_pack(
            self.pack,
            self.target,
            output,
            force=True,
        )
        self._assert_preserved_lists(output, stats)

    def test_source_without_numbering_gets_a_valid_numbering_part(self) -> None:
        output = self.work / "source-no-numbering-output.docx"
        stats = core.transfer(
            self.source_without_numbering,
            self.target,
            output,
            force=True,
        )
        entries = _read_zip(output)
        self.assertIn("word/numbering.xml", entries)
        rels = core.parse_xml(
            entries["word/_rels/document.xml.rels"], "document.xml.rels"
        )
        numbering_relationships = [
            relationship
            for relationship in rels.findall(
                core.qn(core.PKG_REL_NS, "Relationship")
            )
            if core.relationship_role(relationship.get("Type", ""))
            == "numbering"
        ]
        self.assertEqual(len(numbering_relationships), 1)
        document = core.parse_xml(entries["word/document.xml"], "document.xml")
        numbering = core.parse_xml(entries["word/numbering.xml"], "numbering.xml")
        for text in ("保留项目甲", "保留项目乙", "从七开始", "独立序列"):
            paragraph = _paragraph_for_text(document, text)
            _resolved_num_id = _paragraph_num_id(document, text)
            _numbering_definition(numbering, _resolved_num_id)
            self.assertIsNotNone(paragraph.find("w:pPr/w:numPr", namespaces=NS))
        self.assertEqual(stats.body_list_paragraphs_preserved, 6)
        self.assertEqual(stats.target_numbering_definitions_imported, 4)

    def test_picture_bullet_relationship_and_media_are_preserved(self) -> None:
        output = self.work / "picture-bullet-output.docx"
        stats = core.transfer(
            FIXTURES / "source.docx",
            self.picture_target,
            output,
            force=True,
        )
        entries = _read_zip(output)
        document = core.parse_xml(entries["word/document.xml"], "document.xml")
        numbering = core.parse_xml(entries["word/numbering.xml"], "numbering.xml")
        bullet_num_id = _paragraph_num_id(document, "保留项目甲")
        _concrete, abstract = _numbering_definition(numbering, bullet_num_id)
        picture_ids = abstract.xpath(
            ".//w:lvlPicBulletId/@w:val", namespaces=NS
        )
        self.assertEqual(len(picture_ids), 1)
        picture_nodes = numbering.xpath(
            "./w:numPicBullet[@w:numPicBulletId=$picture_id]",
            namespaces=NS,
            picture_id=str(picture_ids[0]),
        )
        self.assertEqual(len(picture_nodes), 1)
        relationship_ids = {
            value
            for node in picture_nodes[0].iter()
            for attribute, value in node.attrib.items()
            if attribute.startswith("{%s}" % core.R_NS)
        }
        self.assertEqual(len(relationship_ids), 1)
        rels_path = "word/_rels/numbering.xml.rels"
        self.assertIn(rels_path, entries)
        relationships = core.parse_xml(entries[rels_path], rels_path)
        matching = [
            relationship
            for relationship in relationships.findall(
                core.qn(core.PKG_REL_NS, "Relationship")
            )
            if relationship.get("Id") in relationship_ids
        ]
        self.assertEqual(len(matching), 1)
        dependency = core.resolve_relationship_target(
            "word/numbering.xml", matching[0].get("Target", "")
        )
        self.assertIn(dependency, entries)
        self.assertEqual(
            entries[dependency], _read_zip(self.picture_target)["word/media/image1.png"]
        )
        self.assertEqual(stats.target_picture_bullets_imported, 1)

    def test_style_inherited_body_lists_materialize_and_repeat_idempotently(self) -> None:
        target_entries = _read_zip(self.style_numbered_target)
        target_catalog = core.build_style_catalog(
            target_entries["word/styles.xml"],
            target_entries["word/document.xml"],
        )
        self.assertEqual(
            target_catalog.styles["HeadingBasedBodyList"].own_outline_level,
            9,
        )
        self.assertIsNone(
            target_catalog.resolved_outline["HeadingBasedBodyList"],
            "explicit outlineLvl=9 must stop Heading1 inheritance",
        )
        self.assertEqual(target_catalog.resolved_outline["Heading1"], 0)

        first_output = self.work / "style-list-first.docx"
        _manifest, first_stats = manager.apply_style_pack(
            self.pack,
            self.style_numbered_target,
            first_output,
            force=True,
        )
        first_entries = _read_zip(first_output)
        first_document = core.parse_xml(
            first_entries["word/document.xml"], "document.xml"
        )
        first_numbering = core.parse_xml(
            first_entries["word/numbering.xml"], "numbering.xml"
        )

        base_num_id = _paragraph_num_id(first_document, "样式列表基础")
        self.assertEqual(
            _paragraph_num_id(first_document, "样式列表继承"), base_num_id
        )
        self.assertEqual(
            _paragraph_num_id(first_document, "段落层级覆盖"), base_num_id
        )
        self.assertEqual(
            _paragraph_num_id(first_document, "标题基式正文列表"), base_num_id
        )
        self.assertNotEqual(base_num_id, "1")
        self.assertEqual(_paragraph_level(first_document, "样式列表基础"), 0)
        self.assertEqual(_paragraph_level(first_document, "样式列表继承"), 1)
        self.assertEqual(_paragraph_level(first_document, "段落层级覆盖"), 1)
        self.assertEqual(_paragraph_level(first_document, "标题基式正文列表"), 0)
        _concrete, abstract = _numbering_definition(first_numbering, base_num_id)
        self.assertEqual(
            abstract.xpath(
                "string(w:lvl[@w:ilvl='1']/w:lvlText/@w:val)", namespaces=NS
            ),
            "◇",
        )

        cancelled = _paragraph_for_text(first_document, "样式取消编号")
        self.assertEqual(
            cancelled.xpath("w:pPr/w:numPr/w:numId/@w:val", namespaces=NS),
            ["0"],
        )
        outline = _paragraph_for_text(first_document, "大纲列表必须排除")
        self.assertIsNone(outline.find("w:pPr/w:numPr", namespaces=NS))
        self.assertEqual(
            outline.xpath("w:pPr/w:pStyle/@w:val", namespaces=NS),
            ["Heading3"],
        )
        heading_based_body = _paragraph_for_text(
            first_document, "标题基式正文列表"
        )
        self.assertEqual(
            heading_based_body.xpath(
                "w:pPr/w:pStyle/@w:val", namespaces=NS
            ),
            ["Normal"],
        )
        self.assertEqual(first_stats.style_list_paragraphs_materialized, 5)
        self.assertTrue(
            any("来自目标段落样式继承" in warning for warning in first_stats.warnings)
        )

        second_output = self.work / "style-list-second.docx"
        _manifest, second_stats = manager.apply_style_pack(
            self.pack,
            first_output,
            second_output,
            force=True,
        )
        second_entries = _read_zip(second_output)
        second_document = core.parse_xml(
            second_entries["word/document.xml"], "document.xml"
        )
        second_numbering = core.parse_xml(
            second_entries["word/numbering.xml"], "numbering.xml"
        )
        for text in (
            "样式列表基础",
            "样式列表继承",
            "段落层级覆盖",
            "标题基式正文列表",
        ):
            self.assertEqual(
                (
                    _paragraph_num_id(second_document, text),
                    _paragraph_level(second_document, text),
                ),
                (
                    _paragraph_num_id(first_document, text),
                    _paragraph_level(first_document, text),
                ),
            )
            _numbering_definition(
                second_numbering, _paragraph_num_id(second_document, text)
            )
        self.assertEqual(second_stats.style_list_paragraphs_materialized, 0)
        self.assertEqual(
            _paragraph_num_id(second_document, "样式取消编号"), "0"
        )
        self.assertIsNone(
            _paragraph_for_text(
                second_document, "大纲列表必须排除"
            ).find("w:pPr/w:numPr", namespaces=NS)
        )


if __name__ == "__main__":
    unittest.main()
