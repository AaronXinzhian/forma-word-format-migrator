#!/usr/bin/env python3
"""Regression coverage for the table-only two-character indent cleanup."""

from __future__ import annotations

import copy
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


NS = {"w": core.W_NS}
W_VAL = core.qn(core.W_NS, "val")


def _read_zip(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _write_docx_with_replacements(
    source: Path,
    destination: Path,
    replacements: dict[str, bytes],
) -> None:
    """Copy a fixture while replacing a small set of package entries."""
    with zipfile.ZipFile(source) as archive:
        records = [(copy.copy(info), archive.read(info.filename)) for info in archive.infolist()]
    with zipfile.ZipFile(destination, "w") as archive:
        for info, data in records:
            archive.writestr(info, replacements.get(info.filename, data))


def _paragraph_for_text(root: etree._Element, text: str) -> etree._Element:
    for paragraph in root.xpath("//w:p", namespaces=NS):
        value = "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))
        if text in value:
            return paragraph
    raise AssertionError("paragraph not found: %s" % text)


def _ensure_ppr(paragraph: etree._Element) -> etree._Element:
    ppr = paragraph.find("w:pPr", namespaces=NS)
    if ppr is None:
        ppr = etree.Element(core.qn(core.W_NS, "pPr"))
        paragraph.insert(0, ppr)
    return ppr


def _set_two_character_indent_fixture(paragraph: etree._Element) -> None:
    """Give a paragraph realistic Word UI `first line: 2 characters` XML.

    Word commonly writes both a character-unit value (200 hundredths of a
    character) and a twip fallback.  Other indentation, alignment, spacing,
    and numbering are deliberately present so the cleanup cannot delete the
    whole paragraph-property block as a shortcut.
    """
    ppr = _ensure_ppr(paragraph)
    for tag in ("numPr", "spacing", "ind", "jc"):
        old = ppr.find("w:%s" % tag, namespaces=NS)
        if old is not None:
            ppr.remove(old)

    num_pr = etree.SubElement(ppr, core.qn(core.W_NS, "numPr"))
    ilvl = etree.SubElement(num_pr, core.qn(core.W_NS, "ilvl"))
    ilvl.set(W_VAL, "0")
    num_id = etree.SubElement(num_pr, core.qn(core.W_NS, "numId"))
    num_id.set(W_VAL, "5")

    spacing = etree.SubElement(ppr, core.qn(core.W_NS, "spacing"))
    spacing.set(core.qn(core.W_NS, "before"), "120")
    spacing.set(core.qn(core.W_NS, "after"), "80")
    spacing.set(core.qn(core.W_NS, "line"), "360")
    spacing.set(core.qn(core.W_NS, "lineRule"), "auto")

    indentation = etree.SubElement(ppr, core.qn(core.W_NS, "ind"))
    indentation.set(core.qn(core.W_NS, "left"), "240")
    indentation.set(core.qn(core.W_NS, "right"), "120")
    indentation.set(core.qn(core.W_NS, "firstLine"), "420")
    indentation.set(core.qn(core.W_NS, "firstLineChars"), "200")

    alignment = etree.SubElement(ppr, core.qn(core.W_NS, "jc"))
    alignment.set(W_VAL, "center")


def _canonical(node: etree._Element) -> bytes:
    return etree.tostring(node, method="c14n", exclusive=True)


def _expected_ppr_after_indent_cleanup(paragraph: etree._Element) -> bytes:
    ppr = copy.deepcopy(paragraph.find("w:pPr", namespaces=NS))
    assert ppr is not None
    indentation = ppr.find("w:ind", namespaces=NS)
    assert indentation is not None
    # Zeroes are required instead of deleting the attributes: once the source
    # Normal style is installed, omission would allow its two-character indent
    # to become effective again through inheritance.
    indentation.set(core.qn(core.W_NS, "firstLine"), "0")
    indentation.set(core.qn(core.W_NS, "firstLineChars"), "0")
    return _canonical(ppr)


def _canonical_nodes(root: etree._Element, xpath: str) -> list[bytes]:
    return [
        _canonical(node)
        for node in root.xpath(xpath, namespaces=NS)
    ]


def _source_with_normal_first_line_indent(source: Path, destination: Path) -> None:
    """Add a two-character first-line indent to the source Normal style."""
    entries = _read_zip(source)
    replacements: dict[str, bytes] = {}
    for part_name in ("word/styles.xml", "word/stylesWithEffects.xml"):
        data = entries.get(part_name)
        if data is None:
            continue
        root = etree.fromstring(data)
        normal = root.find(
            "w:style[@w:type='paragraph'][@w:styleId='Normal']",
            namespaces=NS,
        )
        if normal is None:
            raise AssertionError("source fixture is missing its Normal style")
        ppr = normal.find("w:pPr", namespaces=NS)
        if ppr is None:
            ppr = etree.SubElement(normal, core.qn(core.W_NS, "pPr"))
        indentation = ppr.find("w:ind", namespaces=NS)
        if indentation is None:
            indentation = etree.SubElement(ppr, core.qn(core.W_NS, "ind"))
        indentation.set(core.qn(core.W_NS, "firstLine"), "480")
        indentation.set(core.qn(core.W_NS, "firstLineChars"), "200")
        replacements[part_name] = core.serialize_xml(root)
    _write_docx_with_replacements(source, destination, replacements)


_CUSTOM_BODY_STYLE_SPECS = {
    "BodyA": {
        "font": "Arial",
        "east_asia": "SimSun",
        "size": "20",
        "before": "111",
        "after": "11",
        "alignment": "left",
    },
    "BodyB": {
        "font": "Courier New",
        "east_asia": "KaiTi",
        "size": "24",
        "before": "222",
        "after": "22",
        "alignment": "center",
    },
    "BodyC": {
        "font": "Georgia",
        "east_asia": "FangSong",
        "size": "28",
        "before": "333",
        "after": "33",
        "alignment": "right",
    },
}


def _append_two_character_body_style(
    styles_root: etree._Element,
    style_id: str,
) -> None:
    """Append a visibly distinct custom body style with a two-char indent."""
    spec = _CUSTOM_BODY_STYLE_SPECS[style_id]
    existing = _paragraph_style_node(styles_root, style_id)
    if existing is not None:
        existing.getparent().remove(existing)

    style = etree.Element(core.qn(core.W_NS, "style"))
    style.set(core.qn(core.W_NS, "type"), "paragraph")
    style.set(core.qn(core.W_NS, "customStyle"), "1")
    style.set(core.qn(core.W_NS, "styleId"), style_id)

    name = etree.SubElement(style, core.qn(core.W_NS, "name"))
    name.set(W_VAL, "Custom %s" % style_id)
    based_on = etree.SubElement(style, core.qn(core.W_NS, "basedOn"))
    based_on.set(W_VAL, "Normal")
    next_style = etree.SubElement(style, core.qn(core.W_NS, "next"))
    next_style.set(W_VAL, style_id)

    ppr = etree.SubElement(style, core.qn(core.W_NS, "pPr"))
    spacing = etree.SubElement(ppr, core.qn(core.W_NS, "spacing"))
    spacing.set(core.qn(core.W_NS, "before"), spec["before"])
    spacing.set(core.qn(core.W_NS, "after"), spec["after"])
    indentation = etree.SubElement(ppr, core.qn(core.W_NS, "ind"))
    indentation.set(core.qn(core.W_NS, "firstLine"), "480")
    indentation.set(core.qn(core.W_NS, "firstLineChars"), "200")
    alignment = etree.SubElement(ppr, core.qn(core.W_NS, "jc"))
    alignment.set(W_VAL, spec["alignment"])

    rpr = etree.SubElement(style, core.qn(core.W_NS, "rPr"))
    fonts = etree.SubElement(rpr, core.qn(core.W_NS, "rFonts"))
    fonts.set(core.qn(core.W_NS, "ascii"), spec["font"])
    fonts.set(core.qn(core.W_NS, "hAnsi"), spec["font"])
    fonts.set(core.qn(core.W_NS, "eastAsia"), spec["east_asia"])
    size = etree.SubElement(rpr, core.qn(core.W_NS, "sz"))
    size.set(W_VAL, spec["size"])

    ext_list = styles_root.find("w:extLst", namespaces=NS)
    insertion = (
        styles_root.index(ext_list)
        if ext_list is not None
        else len(styles_root)
    )
    styles_root.insert(insertion, style)


def _docx_with_two_character_body_styles(
    source: Path,
    destination: Path,
    style_ids: tuple[str, ...],
    paragraph_assignments: dict[str, str] | None = None,
) -> None:
    """Build source/target fixtures with selected custom paragraph styles."""
    entries = _read_zip(source)
    replacements: dict[str, bytes] = {}
    for part_name in ("word/styles.xml", "word/stylesWithEffects.xml"):
        data = entries.get(part_name)
        if data is None:
            continue
        styles_root = etree.fromstring(data)
        for style_id in style_ids:
            _append_two_character_body_style(styles_root, style_id)
        replacements[part_name] = core.serialize_xml(styles_root)

    document_root = etree.fromstring(entries["word/document.xml"])
    assignments = paragraph_assignments or {}
    for text, style_id in assignments.items():
        paragraph = _paragraph_for_text(document_root, text)
        ppr = _ensure_ppr(paragraph)
        old = ppr.find("w:pStyle", namespaces=NS)
        if old is not None:
            ppr.remove(old)
        pstyle = etree.Element(core.qn(core.W_NS, "pStyle"))
        pstyle.set(W_VAL, style_id)
        ppr.insert(0, pstyle)

    # Source examples make the custom styles genuinely used by the template,
    # mirroring format libraries captured from real Word documents.
    if not assignments:
        body = document_root.find("w:body", namespaces=NS)
        if body is None:
            raise AssertionError("fixture is missing w:body")
        section = body.find("w:sectPr", namespaces=NS)
        insertion = body.index(section) if section is not None else len(body)
        for offset, style_id in enumerate(style_ids):
            paragraph = etree.Element(core.qn(core.W_NS, "p"))
            ppr = etree.SubElement(paragraph, core.qn(core.W_NS, "pPr"))
            pstyle = etree.SubElement(ppr, core.qn(core.W_NS, "pStyle"))
            pstyle.set(W_VAL, style_id)
            run = etree.SubElement(paragraph, core.qn(core.W_NS, "r"))
            text_node = etree.SubElement(run, core.qn(core.W_NS, "t"))
            text_node.text = "格式库 %s 样例" % style_id
            body.insert(insertion + offset, paragraph)

    replacements["word/document.xml"] = core.serialize_xml(document_root)
    _write_docx_with_replacements(source, destination, replacements)


def _paragraph_style_id(
    paragraph: etree._Element,
    styles_root: etree._Element,
) -> str:
    """Return the paragraph's explicit style or the document default style."""
    explicit = paragraph.xpath("string(w:pPr/w:pStyle/@w:val)", namespaces=NS)
    if explicit:
        return explicit
    defaults = styles_root.xpath(
        "//w:style[@w:type='paragraph'][@w:default='1']/@w:styleId",
        namespaces=NS,
    )
    return defaults[0] if defaults else "Normal"


def _effective_first_line_chars(
    paragraph: etree._Element,
    styles_root: etree._Element,
) -> int | None:
    """Resolve first-line character indentation through style inheritance.

    This deliberately models the narrow property under test.  ``w:ind``
    attributes merge across docDefaults, basedOn styles, and direct paragraph
    formatting, so a new table paragraph with no direct ``w:ind`` still
    exposes whether its assigned style can reintroduce a two-character indent.
    """
    attributes: dict[str, str] = {}

    default_indent = styles_root.find(
        "w:docDefaults/w:pPrDefault/w:pPr/w:ind", namespaces=NS
    )
    if default_indent is not None:
        attributes.update(default_indent.attrib)

    nodes = {
        node.get(core.qn(core.W_NS, "styleId")): node
        for node in styles_root.xpath(
            "//w:style[@w:type='paragraph']", namespaces=NS
        )
    }
    chain: list[etree._Element] = []
    current = _paragraph_style_id(paragraph, styles_root)
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        node = nodes.get(current)
        if node is None:
            break
        chain.append(node)
        current = node.xpath("string(w:basedOn/@w:val)", namespaces=NS)
    for node in reversed(chain):
        indentation = node.find("w:pPr/w:ind", namespaces=NS)
        if indentation is not None:
            attributes.update(indentation.attrib)

    direct = paragraph.find("w:pPr/w:ind", namespaces=NS)
    if direct is not None:
        attributes.update(direct.attrib)

    value = attributes.get(core.qn(core.W_NS, "firstLineChars"))
    return int(value) if value is not None else None


def _paragraph_style_node(
    styles_root: etree._Element,
    style_id: str,
) -> etree._Element | None:
    matches = styles_root.xpath(
        "//w:style[@w:type='paragraph'][@w:styleId=$style_id]",
        namespaces=NS,
        style_id=style_id,
    )
    return matches[0] if matches else None


def _set_numbering_without_indent(paragraph: etree._Element) -> None:
    ppr = _ensure_ppr(paragraph)
    old = ppr.find("w:numPr", namespaces=NS)
    if old is not None:
        ppr.remove(old)
    num_pr = etree.SubElement(ppr, core.qn(core.W_NS, "numPr"))
    ilvl = etree.SubElement(num_pr, core.qn(core.W_NS, "ilvl"))
    ilvl.set(W_VAL, "0")
    num_id = etree.SubElement(num_pr, core.qn(core.W_NS, "numId"))
    num_id.set(W_VAL, "5")


def _set_hanging_indent(paragraph: etree._Element) -> None:
    ppr = _ensure_ppr(paragraph)
    indentation = ppr.find("w:ind", namespaces=NS)
    if indentation is None:
        indentation = etree.SubElement(ppr, core.qn(core.W_NS, "ind"))
    indentation.set(core.qn(core.W_NS, "left"), "360")
    indentation.set(core.qn(core.W_NS, "hanging"), "360")


def _append_direct_outline_paragraphs(
    root: etree._Element,
) -> list[str]:
    cells = root.xpath("//w:tbl/w:tr/w:tc", namespaces=NS)
    if not cells:
        raise AssertionError("target fixture is missing a table cell")
    texts: list[str] = []
    for level in range(9):
        text = "表格直接大纲级别 %d" % level
        paragraph = etree.Element(core.qn(core.W_NS, "p"))
        ppr = etree.SubElement(paragraph, core.qn(core.W_NS, "pPr"))
        outline = etree.SubElement(ppr, core.qn(core.W_NS, "outlineLvl"))
        outline.set(W_VAL, str(level))
        run = etree.SubElement(paragraph, core.qn(core.W_NS, "r"))
        text_node = etree.SubElement(run, core.qn(core.W_NS, "t"))
        text_node.text = text
        cells[0].append(paragraph)
        texts.append(text)
    return texts


def _set_numbered_heading_table_fixture(paragraph: etree._Element) -> None:
    ppr = _ensure_ppr(paragraph)
    for child in list(ppr):
        ppr.remove(child)
    pstyle = etree.SubElement(ppr, core.qn(core.W_NS, "pStyle"))
    pstyle.set(W_VAL, "Heading1")
    spacing = etree.SubElement(ppr, core.qn(core.W_NS, "spacing"))
    spacing.set(core.qn(core.W_NS, "after"), "120")
    indentation = etree.SubElement(ppr, core.qn(core.W_NS, "ind"))
    indentation.set(core.qn(core.W_NS, "left"), "240")
    alignment = etree.SubElement(ppr, core.qn(core.W_NS, "jc"))
    alignment.set(W_VAL, "right")


class TableParagraphIndentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(
            prefix="word-table-paragraph-indent-tests-"
        )
        cls.working_dir = Path(cls._temporary.name)

        target_entries = _read_zip(FIXTURES / "target.docx")
        target_root = etree.fromstring(target_entries["word/document.xml"])
        cls.table_paragraph_text = "目标表头 A"
        cls.one_character_table_paragraph_text = "目标表头 B"
        cls.twip_only_table_paragraph_text = "目标值 3"
        cls.body_paragraph_text = "正文含有手工粗体"
        table_paragraph = _paragraph_for_text(
            target_root, cls.table_paragraph_text
        )
        one_character_table_paragraph = _paragraph_for_text(
            target_root, cls.one_character_table_paragraph_text
        )
        twip_only_table_paragraph = _paragraph_for_text(
            target_root, cls.twip_only_table_paragraph_text
        )
        body_paragraph = _paragraph_for_text(
            target_root, cls.body_paragraph_text
        )
        _set_two_character_indent_fixture(table_paragraph)
        _set_two_character_indent_fixture(body_paragraph)
        one_character_ppr = _ensure_ppr(one_character_table_paragraph)
        one_character_ind = etree.SubElement(
            one_character_ppr, core.qn(core.W_NS, "ind")
        )
        one_character_ind.set(core.qn(core.W_NS, "firstLine"), "210")
        one_character_ind.set(core.qn(core.W_NS, "firstLineChars"), "100")
        twip_only_ppr = _ensure_ppr(twip_only_table_paragraph)
        twip_only_ind = etree.SubElement(
            twip_only_ppr, core.qn(core.W_NS, "ind")
        )
        # 480 twips alone is not authoritative evidence of two characters;
        # font metrics vary.  Only firstLineChars=200 triggers the feature.
        twip_only_ind.set(core.qn(core.W_NS, "firstLine"), "480")

        cls.target_path = cls.working_dir / "target-with-two-char-indent.docx"
        _write_docx_with_replacements(
            FIXTURES / "target.docx",
            cls.target_path,
            {"word/document.xml": core.serialize_xml(target_root)},
        )
        cls.target_root = target_root
        cls.expected_table_ppr = _expected_ppr_after_indent_cleanup(
            table_paragraph
        )
        cls.original_body_ppr = _canonical(
            body_paragraph.find("w:pPr", namespaces=NS)
        )
        cls.original_one_character_table_ppr = _canonical(
            one_character_table_paragraph.find("w:pPr", namespaces=NS)
        )
        cls.original_twip_only_table_ppr = _canonical(
            twip_only_table_paragraph.find("w:pPr", namespaces=NS)
        )

        cls.no_table_pack = cls.working_dir / "no-table.wfstyle"
        manager.create_style_pack(
            FIXTURES / "source-no-table.docx", cls.no_table_pack
        )
        cls.no_table_output = cls.working_dir / "no-table-output.docx"
        _manifest, cls.no_table_stats = manager.apply_style_pack(
            cls.no_table_pack,
            cls.target_path,
            cls.no_table_output,
        )
        cls.no_table_root = etree.fromstring(
            _read_zip(cls.no_table_output)["word/document.xml"]
        )
        cls.no_table_second_output = (
            cls.working_dir / "no-table-output-second-pass.docx"
        )
        _manifest, cls.no_table_second_stats = manager.apply_style_pack(
            cls.no_table_pack,
            cls.no_table_output,
            cls.no_table_second_output,
        )
        cls.no_table_second_root = etree.fromstring(
            _read_zip(cls.no_table_second_output)["word/document.xml"]
        )

        cls.with_table_pack = cls.working_dir / "with-table.wfstyle"
        manager.create_style_pack(
            FIXTURES / "source.docx", cls.with_table_pack
        )
        cls.with_table_output = cls.working_dir / "with-table-output.docx"
        manager.apply_style_pack(
            cls.with_table_pack,
            cls.target_path,
            cls.with_table_output,
        )
        cls.with_table_root = etree.fromstring(
            _read_zip(cls.with_table_output)["word/document.xml"]
        )

        # A template can legitimately provide a table style while its Normal
        # body style also carries Word's "first line: 2 characters" setting.
        # Table-style presence must not disable the table-paragraph safeguard.
        cls.with_table_indented_source = (
            cls.working_dir / "source-with-table-normal-indented.docx"
        )
        _source_with_normal_first_line_indent(
            FIXTURES / "source.docx", cls.with_table_indented_source
        )
        cls.with_table_indented_pack = (
            cls.working_dir / "with-table-normal-indented.wfstyle"
        )
        manager.create_style_pack(
            cls.with_table_indented_source,
            cls.with_table_indented_pack,
        )
        cls.with_table_indented_output = (
            cls.working_dir / "with-table-normal-indented-output.docx"
        )
        manager.apply_style_pack(
            cls.with_table_indented_pack,
            FIXTURES / "target.docx",
            cls.with_table_indented_output,
        )
        with_table_indented_entries = _read_zip(
            cls.with_table_indented_output
        )
        cls.with_table_indented_root = etree.fromstring(
            with_table_indented_entries["word/document.xml"]
        )
        cls.with_table_indented_styles_root = etree.fromstring(
            with_table_indented_entries["word/styles.xml"]
        )

        numbered_target_entries = _read_zip(FIXTURES / "target.docx")
        numbered_target_root = etree.fromstring(
            numbered_target_entries["word/document.xml"]
        )
        cls.numbered_heading_table_text = "目标表头 A"
        _set_numbered_heading_table_fixture(
            _paragraph_for_text(
                numbered_target_root, cls.numbered_heading_table_text
            )
        )
        cls.numbered_heading_target = (
            cls.working_dir / "target-table-numbered-heading.docx"
        )
        _write_docx_with_replacements(
            FIXTURES / "target.docx",
            cls.numbered_heading_target,
            {"word/document.xml": core.serialize_xml(numbered_target_root)},
        )
        cls.numbered_heading_pack = (
            cls.working_dir / "numbered-heading.wfstyle"
        )
        manager.create_style_pack(
            FIXTURES / "source-numbered-headings.docx",
            cls.numbered_heading_pack,
        )
        cls.numbered_heading_output = (
            cls.working_dir / "table-numbered-heading-output.docx"
        )
        manager.apply_style_pack(
            cls.numbered_heading_pack,
            cls.numbered_heading_target,
            cls.numbered_heading_output,
        )
        cls.numbered_heading_root = etree.fromstring(
            _read_zip(cls.numbered_heading_output)["word/document.xml"]
        )

        cls.inherited_source = cls.working_dir / "source-normal-indented.docx"
        _source_with_normal_first_line_indent(
            FIXTURES / "source-no-table.docx", cls.inherited_source
        )
        inherited_target_entries = _read_zip(FIXTURES / "target.docx")
        inherited_target_root = etree.fromstring(
            inherited_target_entries["word/document.xml"]
        )
        cls.inherited_plain_text = "目标值 3"
        cls.inherited_numbered_text = "目标值 1"
        cls.inherited_twip_fallback_text = "目标值 2"
        cls.inherited_hanging_text = "目标值 4"
        # The plain table paragraph deliberately has no pPr/w:ind at all.
        plain = _paragraph_for_text(
            inherited_target_root, cls.inherited_plain_text
        )
        plain_ppr = plain.find("w:pPr", namespaces=NS)
        if plain_ppr is not None:
            plain_ind = plain_ppr.find("w:ind", namespaces=NS)
            if plain_ind is not None:
                plain_ppr.remove(plain_ind)
            if len(plain_ppr) == 0:
                plain.remove(plain_ppr)
        numbered = _paragraph_for_text(
            inherited_target_root, cls.inherited_numbered_text
        )
        _set_numbering_without_indent(numbered)
        twip_fallback = _paragraph_for_text(
            inherited_target_root, cls.inherited_twip_fallback_text
        )
        twip_fallback_ppr = _ensure_ppr(twip_fallback)
        twip_fallback_ind = etree.SubElement(
            twip_fallback_ppr, core.qn(core.W_NS, "ind")
        )
        # Real Word files can retain only this twip fallback while the applied
        # body style supplies firstLineChars=200.  The inherited character-unit
        # value still wins, so this combination must be normalized to zero.
        twip_fallback_ind.set(core.qn(core.W_NS, "firstLine"), "240")
        hanging = _paragraph_for_text(
            inherited_target_root, cls.inherited_hanging_text
        )
        _set_hanging_indent(hanging)
        cls.direct_outline_texts = _append_direct_outline_paragraphs(
            inherited_target_root
        )
        cls.original_numbered_ppr = _canonical(
            numbered.find("w:pPr", namespaces=NS)
        )
        cls.original_hanging_ppr = _canonical(
            hanging.find("w:pPr", namespaces=NS)
        )
        cls.inherited_target = cls.working_dir / "target-inherited-indent.docx"
        _write_docx_with_replacements(
            FIXTURES / "target.docx",
            cls.inherited_target,
            {"word/document.xml": core.serialize_xml(inherited_target_root)},
        )
        cls.inherited_pack = cls.working_dir / "inherited-indent.wfstyle"
        manager.create_style_pack(cls.inherited_source, cls.inherited_pack)
        cls.inherited_output = cls.working_dir / "inherited-output.docx"
        _manifest, cls.inherited_stats = manager.apply_style_pack(
            cls.inherited_pack,
            cls.inherited_target,
            cls.inherited_output,
        )
        inherited_entries = _read_zip(cls.inherited_output)
        cls.inherited_root = etree.fromstring(
            inherited_entries["word/document.xml"]
        )
        cls.inherited_styles_root = etree.fromstring(
            inherited_entries["word/styles.xml"]
        )
        cls.inherited_second_output = (
            cls.working_dir / "inherited-output-second-pass.docx"
        )
        manager.apply_style_pack(
            cls.inherited_pack,
            cls.inherited_output,
            cls.inherited_second_output,
        )
        inherited_second_entries = _read_zip(cls.inherited_second_output)
        cls.inherited_second_root = etree.fromstring(
            inherited_second_entries["word/document.xml"]
        )
        cls.inherited_second_styles_root = etree.fromstring(
            inherited_second_entries["word/styles.xml"]
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def test_table_free_source_neutralizes_two_character_first_line_indent(self) -> None:
        paragraph = _paragraph_for_text(
            self.no_table_root, self.table_paragraph_text
        )
        ppr = paragraph.find("w:pPr", namespaces=NS)
        self.assertIsNotNone(ppr)
        self.assertEqual(_canonical(ppr), self.expected_table_ppr)

        indentation = ppr.find("w:ind", namespaces=NS)
        self.assertEqual(
            indentation.get(core.qn(core.W_NS, "left")), "240"
        )
        self.assertEqual(
            indentation.get(core.qn(core.W_NS, "right")), "120"
        )
        self.assertEqual(
            indentation.get(core.qn(core.W_NS, "firstLine")), "0"
        )
        self.assertEqual(
            indentation.get(core.qn(core.W_NS, "firstLineChars")), "0"
        )
        self.assertEqual(self.no_table_stats.table_paragraph_indents_cleared, 1)

    def test_table_free_source_preserves_other_table_paragraph_properties(self) -> None:
        paragraph = _paragraph_for_text(
            self.no_table_root, self.table_paragraph_text
        )
        ppr = paragraph.find("w:pPr", namespaces=NS)
        self.assertIsNotNone(ppr)
        self.assertEqual(
            ppr.xpath("w:jc/@w:val", namespaces=NS), ["center"]
        )
        self.assertEqual(
            ppr.xpath("w:spacing/@w:before", namespaces=NS), ["120"]
        )
        self.assertEqual(
            ppr.xpath("w:spacing/@w:after", namespaces=NS), ["80"]
        )
        self.assertEqual(
            ppr.xpath("w:spacing/@w:line", namespaces=NS), ["360"]
        )
        self.assertEqual(
            ppr.xpath("w:numPr/w:ilvl/@w:val", namespaces=NS), ["0"]
        )
        self.assertEqual(
            ppr.xpath("w:numPr/w:numId/@w:val", namespaces=NS), ["5"]
        )

    def test_table_free_source_does_not_remove_other_indent_sizes(self) -> None:
        paragraph = _paragraph_for_text(
            self.no_table_root, self.one_character_table_paragraph_text
        )
        ppr = paragraph.find("w:pPr", namespaces=NS)
        self.assertIsNotNone(ppr)
        self.assertEqual(
            _canonical(ppr), self.original_one_character_table_ppr
        )

    def test_twip_value_without_two_character_unit_is_not_neutralized(self) -> None:
        paragraph = _paragraph_for_text(
            self.no_table_root, self.twip_only_table_paragraph_text
        )
        ppr = paragraph.find("w:pPr", namespaces=NS)
        self.assertIsNotNone(ppr)
        self.assertEqual(_canonical(ppr), self.original_twip_only_table_ppr)

    def test_table_free_source_preserves_table_geometry_and_visual_design(self) -> None:
        paths = (
            "//w:tblPr",
            "//w:tblGrid",
            "//w:trPr",
            "//w:tcPr",
        )
        for xpath in paths:
            with self.subTest(xpath=xpath):
                expected = _canonical_nodes(self.target_root, xpath)
                actual = _canonical_nodes(self.no_table_root, xpath)
                self.assertTrue(expected, "fixture missing %s" % xpath)
                self.assertEqual(actual, expected)

        self.assertTrue(
            self.no_table_root.xpath("//w:tblPr/w:tblBorders", namespaces=NS)
        )
        self.assertTrue(
            self.no_table_root.xpath("//w:tcPr/w:shd", namespaces=NS)
        )
        self.assertTrue(
            self.no_table_root.xpath("//w:tcPr/w:gridSpan", namespaces=NS)
        )

    def test_body_paragraphs_keep_existing_full_format_replacement(self) -> None:
        paragraph = _paragraph_for_text(
            self.no_table_root, self.body_paragraph_text
        )
        ppr = paragraph.find("w:pPr", namespaces=NS)
        if ppr is not None:
            self.assertFalse(
                ppr.xpath("w:ind | w:jc | w:spacing | w:numPr", namespaces=NS)
            )

    def test_inherited_two_character_indent_is_neutralized_in_plain_table_cell(self) -> None:
        paragraph = _paragraph_for_text(
            self.inherited_root, self.inherited_plain_text
        )
        self.assertTrue(
            paragraph.xpath(
                "ancestor::w:tbl and not(w:pPr/w:numPr)", namespaces=NS
            )
        )
        self.assertEqual(
            paragraph.xpath("w:pPr/w:ind/@w:firstLine", namespaces=NS),
            ["0"],
        )
        self.assertEqual(
            paragraph.xpath("w:pPr/w:ind/@w:firstLineChars", namespaces=NS),
            ["0"],
        )

    def test_twip_fallback_is_zeroed_when_style_inherits_two_characters(self) -> None:
        paragraph = _paragraph_for_text(
            self.inherited_root, self.inherited_twip_fallback_text
        )
        self.assertEqual(
            paragraph.xpath("w:pPr/w:ind/@w:firstLine", namespaces=NS),
            ["0"],
        )
        self.assertEqual(
            paragraph.xpath("w:pPr/w:ind/@w:firstLineChars", namespaces=NS),
            ["0"],
        )
        self.assertTrue(
            _paragraph_style_id(paragraph, self.inherited_styles_root).startswith(
                "WordFormatTableNoIndent_"
            )
        )

    def test_plain_table_cell_uses_self_contained_zero_indent_style(self) -> None:
        paragraph = _paragraph_for_text(
            self.inherited_root, self.inherited_plain_text
        )
        style_ids = paragraph.xpath(
            "w:pPr/w:pStyle/@w:val", namespaces=NS
        )
        self.assertEqual(
            len(style_ids),
            1,
            "a plain table paragraph must use the generated safe style",
        )
        safe_style_id = style_ids[0]
        self.assertNotEqual(safe_style_id, "Normal")

        safe_style = _paragraph_style_node(
            self.inherited_styles_root, safe_style_id
        )
        self.assertIsNotNone(safe_style)
        self.assertEqual(
            safe_style.xpath("w:basedOn/@w:val", namespaces=NS),
            ["Normal"],
        )
        self.assertEqual(
            safe_style.xpath("w:next/@w:val", namespaces=NS),
            [safe_style_id],
        )
        self.assertEqual(
            safe_style.xpath("w:pPr/w:ind/@w:firstLine", namespaces=NS),
            ["0"],
        )
        self.assertEqual(
            safe_style.xpath(
                "w:pPr/w:ind/@w:firstLineChars", namespaces=NS
            ),
            ["0"],
        )

        # Simulate Word creating another paragraph in a new row/cell.  Such a
        # paragraph normally carries only the current style, without copying
        # the existing paragraph's direct indentation override.
        new_paragraph = etree.Element(core.qn(core.W_NS, "p"))
        ppr = etree.SubElement(new_paragraph, core.qn(core.W_NS, "pPr"))
        pstyle = etree.SubElement(ppr, core.qn(core.W_NS, "pStyle"))
        pstyle.set(W_VAL, safe_style_id)
        self.assertFalse(new_paragraph.xpath("w:pPr/w:ind", namespaces=NS))
        self.assertEqual(
            _effective_first_line_chars(
                new_paragraph, self.inherited_styles_root
            ),
            0,
        )

    def test_zero_indent_table_style_is_not_duplicated_on_second_application(self) -> None:
        first_paragraph = _paragraph_for_text(
            self.inherited_root, self.inherited_plain_text
        )
        second_paragraph = _paragraph_for_text(
            self.inherited_second_root, self.inherited_plain_text
        )
        first_style_id = _paragraph_style_id(
            first_paragraph, self.inherited_styles_root
        )
        second_style_id = _paragraph_style_id(
            second_paragraph, self.inherited_second_styles_root
        )
        self.assertNotEqual(first_style_id, "Normal")
        self.assertEqual(second_style_id, first_style_id)

        first_matches = self.inherited_styles_root.xpath(
            "//w:style[@w:type='paragraph'][@w:styleId=$style_id]",
            namespaces=NS,
            style_id=first_style_id,
        )
        second_matches = self.inherited_second_styles_root.xpath(
            "//w:style[@w:type='paragraph'][@w:styleId=$style_id]",
            namespaces=NS,
            style_id=first_style_id,
        )
        self.assertEqual(len(first_matches), 1)
        self.assertEqual(len(second_matches), 1)
        self.assertEqual(
            _canonical(second_matches[0]), _canonical(first_matches[0])
        )

        second_style_ids = self.inherited_second_styles_root.xpath(
            "//w:style/@w:styleId", namespaces=NS
        )
        self.assertEqual(len(second_style_ids), len(set(second_style_ids)))

    def test_wrapper_identity_survives_switching_multi_base_format_libraries(self) -> None:
        """A wrapper ID reused by another pack must not change its base style.

        Pack A allocates wrappers in BodyA/BodyB order, while pack B allocates
        the same IDs in BodyB/BodyC order.  The second wrapper therefore means
        BodyB in A but BodyC in B.  Applying B over A must resolve the original
        base style instead of trusting that positional wrapper ID.
        """
        source_a = self.working_dir / "source-body-a-b.docx"
        source_b = self.working_dir / "source-body-b-c.docx"
        target = self.working_dir / "target-body-b-table.docx"
        _docx_with_two_character_body_styles(
            FIXTURES / "source-no-table.docx",
            source_a,
            ("BodyA", "BodyB"),
        )
        _docx_with_two_character_body_styles(
            FIXTURES / "source-no-table.docx",
            source_b,
            ("BodyB", "BodyC"),
        )
        _docx_with_two_character_body_styles(
            FIXTURES / "target.docx",
            target,
            ("BodyB",),
            {self.inherited_plain_text: "BodyB"},
        )

        pack_a = self.working_dir / "body-a-b.wfstyle"
        pack_b = self.working_dir / "body-b-c.wfstyle"
        manager.create_style_pack(source_a, pack_a)
        manager.create_style_pack(source_b, pack_b)
        after_a = self.working_dir / "body-b-after-pack-a.docx"
        after_b = self.working_dir / "body-b-after-pack-a-then-b.docx"
        manager.apply_style_pack(pack_a, target, after_a)
        manager.apply_style_pack(pack_b, after_a, after_b)

        after_a_entries = _read_zip(after_a)
        after_a_root = etree.fromstring(after_a_entries["word/document.xml"])
        after_a_styles = etree.fromstring(after_a_entries["word/styles.xml"])
        paragraph_after_a = _paragraph_for_text(
            after_a_root, self.inherited_plain_text
        )
        wrapper_after_a = _paragraph_style_id(
            paragraph_after_a, after_a_styles
        )
        wrapper_after_a_node = _paragraph_style_node(
            after_a_styles, wrapper_after_a
        )
        self.assertIsNotNone(wrapper_after_a_node)
        self.assertEqual(
            wrapper_after_a_node.xpath("w:basedOn/@w:val", namespaces=NS),
            ["BodyB"],
        )

        after_b_entries = _read_zip(after_b)
        after_b_root = etree.fromstring(after_b_entries["word/document.xml"])
        after_b_styles = etree.fromstring(after_b_entries["word/styles.xml"])
        paragraph_after_b = _paragraph_for_text(
            after_b_root, self.inherited_plain_text
        )
        wrapper_after_b = _paragraph_style_id(
            paragraph_after_b, after_b_styles
        )
        wrapper_after_b_node = _paragraph_style_node(
            after_b_styles, wrapper_after_b
        )
        self.assertIsNotNone(wrapper_after_b_node)
        self.assertEqual(
            wrapper_after_b_node.xpath("w:basedOn/@w:val", namespaces=NS),
            ["BodyB"],
            "the second format library must keep the paragraph on BodyB",
        )
        self.assertEqual(
            _effective_first_line_chars(paragraph_after_b, after_b_styles),
            0,
        )

        paragraph_properties, run_properties = core._effective_style_properties(
            after_b_styles, wrapper_after_b
        )
        body_b = _CUSTOM_BODY_STYLE_SPECS["BodyB"]
        body_c = _CUSTOM_BODY_STYLE_SPECS["BodyC"]
        self.assertEqual(
            paragraph_properties["spacing"].get(
                core.qn(core.W_NS, "before")
            ),
            body_b["before"],
        )
        self.assertNotEqual(
            paragraph_properties["spacing"].get(
                core.qn(core.W_NS, "before")
            ),
            body_c["before"],
        )
        self.assertEqual(
            paragraph_properties["jc"].get(W_VAL),
            body_b["alignment"],
        )
        self.assertEqual(
            run_properties["rFonts"].get(core.qn(core.W_NS, "ascii")),
            body_b["font"],
        )
        self.assertEqual(
            run_properties["rFonts"].get(core.qn(core.W_NS, "eastAsia")),
            body_b["east_asia"],
        )
        self.assertEqual(run_properties["sz"].get(W_VAL), body_b["size"])

    def test_inherited_indent_neutralization_skips_numbered_table_paragraph(self) -> None:
        paragraph = _paragraph_for_text(
            self.inherited_root, self.inherited_numbered_text
        )
        ppr = paragraph.find("w:pPr", namespaces=NS)
        self.assertIsNotNone(ppr)
        self.assertEqual(_canonical(ppr), self.original_numbered_ppr)
        self.assertFalse(ppr.xpath("w:ind", namespaces=NS))

    def test_inherited_indent_neutralization_skips_hanging_indent(self) -> None:
        paragraph = _paragraph_for_text(
            self.inherited_root, self.inherited_hanging_text
        )
        ppr = paragraph.find("w:pPr", namespaces=NS)
        self.assertIsNotNone(ppr)
        self.assertEqual(_canonical(ppr), self.original_hanging_ppr)
        self.assertEqual(
            ppr.xpath("w:ind/@w:hanging", namespaces=NS), ["360"]
        )

    def test_table_run_cleanup_is_unchanged(self) -> None:
        paragraph = _paragraph_for_text(
            self.no_table_root, self.table_paragraph_text
        )
        for rpr in paragraph.xpath(".//w:rPr", namespaces=NS):
            self.assertTrue(
                {
                    etree.QName(child).localname
                    for child in rpr
                }.issubset(core.RUN_SEMANTIC_KEEP)
            )

    def test_inherited_indent_neutralization_skips_direct_outline_levels(self) -> None:
        for level, text in enumerate(self.direct_outline_texts):
            with self.subTest(level=level):
                paragraph = _paragraph_for_text(self.inherited_root, text)
                self.assertTrue(
                    paragraph.xpath("ancestor::w:tbl", namespaces=NS)
                )
                self.assertEqual(
                    paragraph.xpath(
                        "w:pPr/w:outlineLvl/@w:val", namespaces=NS
                    ),
                    [str(level)],
                )
                self.assertFalse(
                    paragraph.xpath("w:pPr/w:ind", namespaces=NS)
                )

    def test_repeated_application_is_idempotent_for_table_indentation(self) -> None:
        first = _paragraph_for_text(
            self.no_table_root, self.table_paragraph_text
        )
        second = _paragraph_for_text(
            self.no_table_second_root, self.table_paragraph_text
        )
        first_ppr = first.find("w:pPr", namespaces=NS)
        second_ppr = second.find("w:pPr", namespaces=NS)
        self.assertIsNotNone(first_ppr)
        self.assertIsNotNone(second_ppr)
        self.assertEqual(_canonical(second_ppr), _canonical(first_ppr))
        self.assertEqual(
            len(second_ppr.findall("w:ind", namespaces=NS)), 1
        )
        self.assertEqual(
            second_ppr.xpath("w:ind/@w:firstLine", namespaces=NS), ["0"]
        )
        self.assertEqual(
            second_ppr.xpath("w:ind/@w:firstLineChars", namespaces=NS),
            ["0"],
        )
        self.assertEqual(
            _canonical_nodes(
                self.no_table_second_root, "//w:tbl//w:p/w:pPr/w:ind"
            ),
            _canonical_nodes(
                self.no_table_root, "//w:tbl//w:p/w:pPr/w:ind"
            ),
        )
        self.assertEqual(
            self.no_table_second_stats.table_paragraph_indents_cleared, 0
        )

    def test_table_heading_numbering_preserves_word_ppr_child_order(self) -> None:
        paragraph = _paragraph_for_text(
            self.numbered_heading_root, self.numbered_heading_table_text
        )
        ppr = paragraph.find("w:pPr", namespaces=NS)
        self.assertIsNotNone(ppr)
        child_names = [etree.QName(child).localname for child in ppr]
        for required in ("pStyle", "numPr", "spacing", "ind", "jc"):
            self.assertIn(required, child_names)

        order = {name: index for index, name in enumerate(core.PPR_CHILD_ORDER)}
        ordered_children = [name for name in child_names if name in order]
        self.assertEqual(
            [order[name] for name in ordered_children],
            sorted(order[name] for name in ordered_children),
            child_names,
        )
        self.assertLess(child_names.index("numPr"), child_names.index("spacing"))
        self.assertLess(child_names.index("numPr"), child_names.index("ind"))
        self.assertLess(child_names.index("numPr"), child_names.index("jc"))

    def test_source_with_used_table_style_keeps_existing_full_cleanup(self) -> None:
        paragraph = _paragraph_for_text(
            self.with_table_root, self.table_paragraph_text
        )
        ppr = paragraph.find("w:pPr", namespaces=NS)
        if ppr is not None:
            self.assertFalse(
                ppr.xpath("w:ind | w:jc | w:spacing | w:numPr", namespaces=NS)
            )
        self.assertEqual(
            self.with_table_root.xpath(
                "//w:tblPr/w:tblStyle/@w:val", namespaces=NS
            ),
            ["LightShading-Accent1"],
        )

    def test_used_table_style_does_not_reintroduce_normal_two_character_indent(self) -> None:
        table_paragraphs = self.with_table_indented_root.xpath(
            "//w:tbl//w:p[.//w:t]", namespaces=NS
        )
        self.assertEqual(len(table_paragraphs), 6)
        for paragraph in table_paragraphs:
            text = "".join(
                paragraph.xpath(".//w:t/text()", namespaces=NS)
            )
            with self.subTest(text=text):
                self.assertFalse(
                    paragraph.xpath(
                        "w:pPr/w:numPr | w:pPr/w:outlineLvl",
                        namespaces=NS,
                    ),
                    "fixture paragraph must remain an ordinary table paragraph",
                )
                self.assertEqual(
                    _effective_first_line_chars(
                        paragraph, self.with_table_indented_styles_root
                    ),
                    0,
                )

        body = _paragraph_for_text(
            self.with_table_indented_root, self.body_paragraph_text
        )
        self.assertFalse(
            body.xpath(
                "w:pPr/w:ind/@w:firstLineChars", namespaces=NS
            )
        )
        self.assertEqual(
            _effective_first_line_chars(
                body, self.with_table_indented_styles_root
            ),
            200,
        )

        self.assertEqual(
            self.with_table_indented_root.xpath(
                "//w:tblPr/w:tblStyle/@w:val", namespaces=NS
            ),
            ["LightShading-Accent1"],
        )
        self.assertEqual(
            len(
                self.with_table_indented_styles_root.xpath(
                    "//w:style[@w:type='table']"
                    "[@w:styleId='LightShading-Accent1']",
                    namespaces=NS,
                )
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
