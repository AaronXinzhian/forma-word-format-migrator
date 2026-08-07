#!/usr/bin/env python3
"""Persistent, privacy-conscious style packs for Forma Fushi.

The pack stores only allow-listed Word formatting XML plus a JSON manifest.
It never retains source body/story text, pictures, macros, embedded fonts, or
other document-owned binary objects.  UI samples are generated locally.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import uuid
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from lxml import etree

import word_style_transfer as core


PACK_SCHEMA_VERSION = 1
PACK_SUFFIX = ".wfstyle"
PART_PREFIX = "parts/"
MAX_PACK_MEMBERS = 256
MAX_PACK_MEMBER_BYTES = 16 * 1024 * 1024
MAX_PACK_TOTAL_BYTES = 64 * 1024 * 1024
MAX_EDITS_JSON_BYTES = 1024 * 1024
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
A = {"a": A_NS}


def _bool_value(node: Optional[etree._Element]) -> Optional[bool]:
    if node is None:
        return None
    value = node.get(core.qn(core.W_NS, "val"))
    if value is None:
        return True
    return value.strip().casefold() not in {"0", "false", "off", "no"}


def _twips_to_pt(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(int(value) / 20.0, 2)
    except (TypeError, ValueError):
        return None


def _twips_to_cm(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(int(value) / 1440.0 * 2.54, 2)
    except (TypeError, ValueError):
        return None


def _safe_hex(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip().lstrip("#").upper()
    if re.fullmatch(r"[0-9A-F]{6}", cleaned):
        return cleaned
    return None


def _style_chain(
    style_id: str,
    catalog: core.StyleCatalog,
) -> List[core.StyleInfo]:
    chain: List[core.StyleInfo] = []
    seen: Set[str] = set()
    current = style_id
    while current and current not in seen:
        seen.add(current)
        info = catalog.styles.get(current)
        if info is None:
            break
        chain.append(info)
        current = info.based_on or ""
    chain.reverse()
    return chain


def _theme_metadata(entries: Dict[str, bytes]) -> Dict[str, Dict[str, str]]:
    _, roles = core.collect_format_relationships(entries)
    theme_record = roles.get("theme")
    if theme_record is None:
        fallback = core.ROLE_FALLBACK_PARTS["theme"]
        if fallback not in entries:
            return {"fonts": {}, "colors": {}}
        theme_path = fallback
    else:
        theme_path = theme_record[0]
    if theme_path not in entries:
        return {"fonts": {}, "colors": {}}

    root = core.parse_xml(entries[theme_path], theme_path)
    fonts: Dict[str, str] = {}
    colors: Dict[str, str] = {}

    for group_name, group_tag in (("major", "majorFont"), ("minor", "minorFont")):
        group = root.find(
            ".//a:themeElements/a:fontScheme/a:%s" % group_tag,
            namespaces=A,
        )
        if group is None:
            continue
        latin = group.find("a:latin", namespaces=A)
        east_asian = group.find("a:ea", namespaces=A)
        latin_name = latin.get("typeface", "") if latin is not None else ""
        east_name = east_asian.get("typeface", "") if east_asian is not None else ""
        hans = ""
        hant = ""
        for supplemental in group.findall("a:font", namespaces=A):
            script = supplemental.get("script", "")
            if script == "Hans":
                hans = supplemental.get("typeface", "")
            elif script == "Hant":
                hant = supplemental.get("typeface", "")
        fonts["%sHAnsi" % group_name] = latin_name
        fonts["%sAscii" % group_name] = latin_name
        fonts["%sEastAsia" % group_name] = hans or hant or east_name or latin_name

    scheme = root.find(".//a:themeElements/a:clrScheme", namespaces=A)
    if scheme is not None:
        for color_node in scheme:
            name = etree.QName(color_node).localname
            srgb = color_node.find("a:srgbClr", namespaces=A)
            sys_color = color_node.find("a:sysClr", namespaces=A)
            value = None
            if srgb is not None:
                value = srgb.get("val")
            elif sys_color is not None:
                value = sys_color.get("lastClr")
            safe = _safe_hex(value)
            if safe:
                colors[name] = safe
    return {"fonts": fonts, "colors": colors}


def _merge_property_children(
    destination: Dict[str, etree._Element],
    parent: Optional[etree._Element],
) -> None:
    if parent is None:
        return
    for child in parent:
        key = etree.QName(child).localname
        if key in {"rFonts", "spacing", "ind"} and key in destination:
            merged = copy.deepcopy(destination[key])
            for attr, value in child.attrib.items():
                merged.set(attr, value)
            destination[key] = merged
        else:
            destination[key] = copy.deepcopy(child)


def _generic_sample(
    style_type: str,
    style_name: str,
    outline_level: Optional[int],
    numbering_example: Optional[str] = None,
) -> str:
    lowered = style_name.casefold()
    if style_type == "table":
        return "表头　｜　内容　｜　数据"
    if style_type == "character":
        return "字符样式预览 · 中文 Aa 123"
    if outline_level is not None:
        heading = "%s级标题 · %s" % (outline_level + 1, style_name)
        return "%s　%s" % (numbering_example, heading) if numbering_example else heading
    if "header" in lowered or "页眉" in style_name:
        return "页眉样式预览"
    if "footer" in lowered or "页脚" in style_name:
        return "页脚样式预览"
    if any(token in lowered for token in ("list", "number", "bullet")) or "列表" in style_name:
        return "1. 列表项目预览"
    if core.normalize_style_name(style_name) in {
        "normal",
        "正文",
        "bodytext",
    }:
        return "这是一段正文预览，用于观察字体、字号与行距。"
    return "样式预览 · 中文 Aa 123"


def _numbering_example(
    rule: Optional[core.HeadingNumberingRule],
) -> Optional[str]:
    if rule is None:
        return None
    value = rule.level_text or ".".join("1" for _ in range(rule.level + 1))
    for index in range(1, 10):
        replacement = str(rule.start or 1) if index - 1 == rule.level else "1"
        value = value.replace("%%%d" % index, replacement)
    value = value.strip()
    return value or None


def _style_preview(
    style_id: str,
    style_type: str,
    usage_count: int,
    usage_by_story: Dict[str, int],
    catalog: core.StyleCatalog,
    styles_root: etree._Element,
    theme: Dict[str, Dict[str, str]],
    numbering_rule: Optional[core.HeadingNumberingRule] = None,
    inferred: bool = False,
    inference_label: Optional[str] = None,
) -> Dict[str, object]:
    info = catalog.styles.get(style_id)
    name = info.name if info is not None else style_id
    run_properties: Dict[str, etree._Element] = {}
    paragraph_properties: Dict[str, etree._Element] = {}

    doc_run = styles_root.find(
        "w:docDefaults/w:rPrDefault/w:rPr", namespaces=core.NS
    )
    doc_para = styles_root.find(
        "w:docDefaults/w:pPrDefault/w:pPr", namespaces=core.NS
    )
    _merge_property_children(run_properties, doc_run)
    _merge_property_children(paragraph_properties, doc_para)

    style_nodes = {
        node.get(core.qn(core.W_NS, "styleId")): node
        for node in styles_root.findall("w:style", namespaces=core.NS)
        if node.get(core.qn(core.W_NS, "styleId"))
    }
    for chain_item in _style_chain(style_id, catalog):
        node = style_nodes.get(chain_item.style_id)
        if node is None:
            continue
        _merge_property_children(
            run_properties, node.find("w:rPr", namespaces=core.NS)
        )
        _merge_property_children(
            paragraph_properties, node.find("w:pPr", namespaces=core.NS)
        )

    style_node = style_nodes.get(style_id)
    table_fill: Optional[str] = None
    table_accent: Optional[str] = None
    if style_node is not None and style_type == "table":
        base_fill = style_node.find("w:tblPr/w:shd", namespaces=core.NS)
        if base_fill is not None:
            table_fill = _safe_hex(
                base_fill.get(core.qn(core.W_NS, "fill"))
            )
        if table_fill is None:
            for shd in style_node.xpath(".//w:shd", namespaces=core.NS):
                table_fill = _safe_hex(shd.get(core.qn(core.W_NS, "fill")))
                if table_fill:
                    break

        # A table style's most predictable, user-visible accent is the first
        # row conditional fill.  Older packs used the first text colour as a
        # best-effort preview fallback, which remains supported here.
        header_fill = style_node.find(
            "w:tblStylePr[@w:type='firstRow']/w:tcPr/w:shd",
            namespaces=core.NS,
        )
        if header_fill is not None:
            table_accent = _safe_hex(
                header_fill.get(core.qn(core.W_NS, "fill"))
            )
        if table_accent is None:
            for color in style_node.xpath(".//w:color", namespaces=core.NS):
                table_accent = _safe_hex(color.get(core.qn(core.W_NS, "val")))
                if table_accent:
                    break

    rfonts = run_properties.get("rFonts")
    font_latin: Optional[str] = None
    font_east_asia: Optional[str] = None
    if rfonts is not None:
        font_latin = (
            rfonts.get(core.qn(core.W_NS, "ascii"))
            or rfonts.get(core.qn(core.W_NS, "hAnsi"))
        )
        font_east_asia = rfonts.get(core.qn(core.W_NS, "eastAsia"))
        if not font_latin:
            theme_key = (
                rfonts.get(core.qn(core.W_NS, "asciiTheme"))
                or rfonts.get(core.qn(core.W_NS, "hAnsiTheme"))
            )
            font_latin = theme.get("fonts", {}).get(theme_key or "") or theme_key
        if not font_east_asia:
            theme_key = rfonts.get(core.qn(core.W_NS, "eastAsiaTheme"))
            font_east_asia = theme.get("fonts", {}).get(theme_key or "") or theme_key

    size_pt: Optional[float] = None
    size_node = run_properties.get("sz")
    if size_node is None:
        size_node = run_properties.get("szCs")
    if size_node is not None:
        raw = size_node.get(core.qn(core.W_NS, "val"))
        try:
            size_pt = round(int(raw) / 2.0, 1) if raw is not None else None
        except ValueError:
            pass

    color_hex: Optional[str] = None
    color_node = run_properties.get("color")
    if color_node is not None:
        color_hex = _safe_hex(color_node.get(core.qn(core.W_NS, "val")))
        if not color_hex:
            theme_name = color_node.get(core.qn(core.W_NS, "themeColor"))
            color_hex = theme.get("colors", {}).get(theme_name or "")

    spacing = paragraph_properties.get("spacing")
    before_pt = after_pt = line_spacing = None
    line_rule = None
    if spacing is not None:
        before_pt = _twips_to_pt(spacing.get(core.qn(core.W_NS, "before")))
        after_pt = _twips_to_pt(spacing.get(core.qn(core.W_NS, "after")))
        line_rule = spacing.get(core.qn(core.W_NS, "lineRule"))
        raw_line = spacing.get(core.qn(core.W_NS, "line"))
        if raw_line:
            try:
                line_spacing = (
                    round(int(raw_line) / 240.0, 2)
                    if line_rule in {None, "auto"}
                    else round(int(raw_line) / 20.0, 2)
                )
            except ValueError:
                pass

    alignment_node = paragraph_properties.get("jc")
    alignment = (
        alignment_node.get(core.qn(core.W_NS, "val"))
        if alignment_node is not None
        else None
    )
    outline_level = catalog.resolved_outline.get(style_id)
    numbering_example = _numbering_example(numbering_rule)

    return {
        "style_id": style_id,
        "name": name,
        "type": style_type,
        "usage_count": usage_count,
        "inferred": inferred,
        "inference_label": inference_label,
        "usage_by_story": dict(sorted(usage_by_story.items())),
        "sample": _generic_sample(
            style_type, name, outline_level, numbering_example
        ),
        "font_latin": font_latin,
        "font_east_asia": font_east_asia,
        "size_pt": size_pt,
        "bold": _bool_value(run_properties.get("b")),
        "italic": _bool_value(run_properties.get("i")),
        "color_hex": color_hex,
        "alignment": alignment,
        "space_before_pt": before_pt,
        "space_after_pt": after_pt,
        "line_spacing": line_spacing,
        "line_rule": line_rule,
        "outline_level": outline_level,
        "numbered": (
            numbering_rule is not None or "numPr" in paragraph_properties
        ),
        "numbering_level": (
            numbering_rule.level if numbering_rule is not None else None
        ),
        "numbering_format": (
            numbering_rule.number_format if numbering_rule is not None else None
        ),
        "numbering_pattern": (
            numbering_rule.level_text if numbering_rule is not None else None
        ),
        "numbering_example": numbering_example,
        "table_fill_hex": table_fill,
        "table_accent_hex": table_accent,
    }


def _story_name(part_name: str) -> str:
    basename = PurePosixPath(part_name).name
    if part_name == "word/document.xml":
        return "body"
    if basename.startswith("header"):
        return "header"
    if basename.startswith("footer"):
        return "footer"
    if basename == "footnotes.xml":
        return "footnote"
    if basename == "endnotes.xml":
        return "endnote"
    if basename == "comments.xml":
        return "comment"
    return basename.rsplit(".", 1)[0]


def _active_content_parts(entries: Dict[str, bytes]) -> List[str]:
    """Return active Word stories, excluding orphan headers and glossary data."""
    active: Set[str] = {"word/document.xml"}
    rels_path = "word/_rels/document.xml.rels"
    if rels_path not in entries:
        return sorted(name for name in active if name in entries)

    rel_root = core.parse_xml(entries[rels_path], rels_path)
    relationships: Dict[str, Tuple[str, str]] = {}
    for rel in rel_root.findall(core.qn(core.PKG_REL_NS, "Relationship")):
        rel_id = rel.get("Id")
        target = rel.get("Target")
        if (
            not rel_id
            or not target
            or rel.get("TargetMode") == "External"
        ):
            continue
        relationships[rel_id] = (
            rel.get("Type", "").rstrip("/").rsplit("/", 1)[-1],
            core.resolve_relationship_target("word/document.xml", target),
        )

    document_root = core.parse_xml(entries["word/document.xml"], "word/document.xml")
    referenced_story_ids = set(
        document_root.xpath(
            "//w:sectPr/w:headerReference/@r:id | "
            "//w:sectPr/w:footerReference/@r:id",
            namespaces=core.NS,
        )
    )
    for rel_id in referenced_story_ids:
        record = relationships.get(str(rel_id))
        if record is not None and record[0] in {"header", "footer"}:
            active.add(record[1])

    for role in ("footnotes", "endnotes", "comments"):
        for rel_role, target in relationships.values():
            if rel_role == role:
                active.add(target)

    return sorted(
        name
        for name in active
        if name in entries and core.is_content_part(name)
    )


def _default_table_style(
    entries: Dict[str, bytes], catalog: core.StyleCatalog
) -> Optional[str]:
    settings = entries.get("word/settings.xml")
    if settings is not None:
        root = core.parse_xml(settings, "word/settings.xml")
        node = root.find("w:defaultTableStyle", namespaces=core.NS)
        if node is not None:
            value = node.get(core.qn(core.W_NS, "val"))
            if value in catalog.styles:
                return value
    return catalog.fallback("table")


def inspect_source(
    source_path: Path,
) -> Tuple[core.Package, core.StyleCatalog, Dict[str, object]]:
    source_path = source_path.expanduser().resolve()
    if source_path.suffix.lower() not in core.SOURCE_SUFFIXES:
        raise core.TransferError(
            "格式源文件只支持：%s" % ", ".join(sorted(core.SOURCE_SUFFIXES))
        )
    package = core.load_package(source_path, "格式源文件")
    entries = package.entries
    catalog = core.build_style_catalog(
        entries["word/styles.xml"], entries["word/document.xml"]
    )
    styles_root = core.parse_xml(entries["word/styles.xml"], "styles.xml")
    theme = _theme_metadata(entries)

    paragraph_usage: Counter[str] = Counter()
    character_usage: Counter[str] = Counter()
    table_usage: Counter[str] = Counter()
    paragraph_stories: Dict[str, Counter[str]] = {}
    character_stories: Dict[str, Counter[str]] = {}
    table_stories: Dict[str, Counter[str]] = {}
    paragraphs = runs = tables = sections = 0
    manual_paragraphs = manual_runs = 0

    default_paragraph = catalog.fallback("paragraph")
    default_table = _default_table_style(entries, catalog)
    active_parts = _active_content_parts(entries)
    numbering_conflicts: Set[str] = set()
    heading_numbering = core.extract_heading_numbering_rules(
        entries, catalog, active_parts, conflicts=numbering_conflicts
    )

    for name in active_parts:
        story = _story_name(name)
        paragraph_story = paragraph_stories.setdefault(story, Counter())
        character_story = character_stories.setdefault(story, Counter())
        table_story = table_stories.setdefault(story, Counter())
        root = core.parse_xml(entries[name], name)
        for paragraph in root.xpath("//w:p", namespaces=core.NS):
            paragraphs += 1
            pstyle = paragraph.find("w:pPr/w:pStyle", namespaces=core.NS)
            style_id = (
                pstyle.get(core.qn(core.W_NS, "val"))
                if pstyle is not None
                else default_paragraph
            )
            if style_id:
                paragraph_usage[style_id] += 1
                paragraph_story[style_id] += 1
            ppr = paragraph.find("w:pPr", namespaces=core.NS)
            if ppr is not None and any(
                etree.QName(child).localname not in {"pStyle", "sectPr"}
                for child in ppr
            ):
                manual_paragraphs += 1

        for run in root.xpath("//w:r", namespaces=core.NS):
            runs += 1
            rstyle = run.find("w:rPr/w:rStyle", namespaces=core.NS)
            if rstyle is not None:
                style_id = rstyle.get(core.qn(core.W_NS, "val"))
                if style_id:
                    character_usage[style_id] += 1
                    character_story[style_id] += 1
            rpr = run.find("w:rPr", namespaces=core.NS)
            if rpr is not None and any(
                etree.QName(child).localname
                not in (core.RUN_SEMANTIC_KEEP | {"rStyle"})
                for child in rpr
            ):
                manual_runs += 1

        for table in root.xpath("//w:tbl", namespaces=core.NS):
            tables += 1
            tbl_style = table.find("w:tblPr/w:tblStyle", namespaces=core.NS)
            style_id = (
                tbl_style.get(core.qn(core.W_NS, "val"))
                if tbl_style is not None
                else default_table
            )
            if style_id:
                table_usage[style_id] += 1
                table_story[style_id] += 1

        if name == "word/document.xml":
            sections = len(root.xpath("//w:sectPr", namespaces=core.NS))

    actual_heading_by_level: Dict[int, str] = {}
    heading_candidates: Dict[int, List[str]] = {}
    for style_id in paragraph_usage:
        level = catalog.resolved_outline.get(style_id)
        if level is not None:
            heading_candidates.setdefault(level, []).append(style_id)
    body_story = paragraph_stories.get("body", Counter())
    for level, candidates in heading_candidates.items():
        actual_heading_by_level[level] = min(
            candidates,
            key=lambda style_id: (
                -body_story[style_id],
                -paragraph_usage[style_id],
                style_id,
            ),
        )
    catalog.authoritative_heading_by_level = dict(actual_heading_by_level)
    heading_completion = core.complete_heading_hierarchy(
        entries,
        catalog,
        actual_heading_by_level,
        heading_numbering,
    )
    heading_numbering = heading_completion.heading_numbering
    inferred_heading_styles = dict(heading_completion.inferred_styles)
    heading_authorities = dict(actual_heading_by_level)
    heading_authorities.update(inferred_heading_styles)

    # The completion pass updates styles.xml/stylesWithEffects.xml in the
    # package copy.  Rebuild the catalog so previews and the persisted pack see
    # the generated properties rather than dormant Word gallery defaults.
    catalog = core.build_style_catalog(
        entries["word/styles.xml"], entries["word/document.xml"]
    )
    catalog.authoritative_heading_by_level = heading_authorities
    catalog.used_paragraph_styles = set(paragraph_usage) | set(
        inferred_heading_styles.values()
    )
    styles_root = core.parse_xml(entries["word/styles.xml"], "styles.xml")
    theme = _theme_metadata(entries)
    heading_paragraph_indents = core.collect_heading_paragraph_indents(
        entries,
        catalog,
        set(heading_numbering) | set(heading_authorities.values()),
        part_names=active_parts,
        inherited_style_ids=inferred_heading_styles.values(),
        heading_authorities=heading_authorities,
    )

    used_formats: List[Dict[str, object]] = []
    for style_type, counter in (
        ("paragraph", paragraph_usage),
        ("character", character_usage),
        ("table", table_usage),
    ):
        for style_id, count in counter.items():
            stories = {
                story: story_counter[style_id]
                for story, story_counter in (
                    paragraph_stories
                    if style_type == "paragraph"
                    else character_stories
                    if style_type == "character"
                    else table_stories
                ).items()
                if story_counter[style_id]
            }
            used_formats.append(
                _style_preview(
                    style_id,
                    style_type,
                    count,
                    stories,
                    catalog,
                    styles_root,
                    theme,
                    heading_numbering.get(style_id),
                )
            )

    for level, style_id in sorted(inferred_heading_styles.items()):
        used_formats.append(
            _style_preview(
                style_id,
                "paragraph",
                0,
                {},
                catalog,
                styles_root,
                theme,
                heading_numbering.get(style_id),
                inferred=True,
                inference_label="智能补全",
            )
        )

    def sort_key(item: Dict[str, object]) -> Tuple[int, int, str]:
        item_type = str(item.get("type"))
        outline = item.get("outline_level")
        if item_type == "paragraph" and outline is not None:
            return (0, int(outline), str(item.get("name", "")).casefold())
        if item_type == "paragraph":
            name = core.normalize_style_name(str(item.get("name", "")))
            normal_rank = 0 if name in {"normal", "正文", "bodytext"} else 1
            return (1, normal_rank, name)
        if item_type == "character":
            return (2, 0, str(item.get("name", "")).casefold())
        return (3, 0, str(item.get("name", "")).casefold())

    used_formats.sort(key=sort_key)
    table_style_edit_candidate: Optional[Dict[str, object]] = None
    if not table_usage:
        candidate_style_id = default_table
        candidate_info = (
            catalog.styles.get(candidate_style_id)
            if candidate_style_id is not None
            else None
        )
        if candidate_info is None or candidate_info.style_type != "table":
            candidate_style_id = catalog.fallback("table")
            candidate_info = (
                catalog.styles.get(candidate_style_id)
                if candidate_style_id is not None
                else None
            )
        if (
            candidate_style_id is not None
            and candidate_info is not None
            and candidate_info.style_type == "table"
        ):
            table_style_edit_candidate = _style_preview(
                candidate_style_id,
                "table",
                0,
                {},
                catalog,
                styles_root,
                theme,
                inferred=True,
                inference_label="可选表格方案",
            )
    layouts = core.extract_source_section_layout(entries["word/document.xml"])
    first_layout = layouts[0] if layouts else []
    first_layout_by_name = {etree.QName(x).localname: x for x in first_layout}
    pg_size = first_layout_by_name.get("pgSz")
    pg_margin = first_layout_by_name.get("pgMar")
    page_width_cm = _twips_to_cm(
        pg_size.get(core.qn(core.W_NS, "w")) if pg_size is not None else None
    )
    page_height_cm = _twips_to_cm(
        pg_size.get(core.qn(core.W_NS, "h")) if pg_size is not None else None
    )
    orientation = (
        pg_size.get(core.qn(core.W_NS, "orient"))
        if pg_size is not None
        else None
    )
    if not orientation and page_width_cm and page_height_cm:
        orientation = "landscape" if page_width_cm > page_height_cm else "portrait"

    manifest: Dict[str, object] = {
        "schema_version": PACK_SCHEMA_VERSION,
        "id": str(uuid.uuid4()),
        "name": source_path.stem,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "used_formats": used_formats,
        "used_style_count": len(used_formats) - len(inferred_heading_styles),
        "inferred_style_count": len(inferred_heading_styles),
        "custom_style_count": 0,
        "inferred_heading_styles": [
            inferred_heading_styles[level]
            for level in sorted(inferred_heading_styles)
        ],
        "heading_authorities": {
            str(level): style_id
            for level, style_id in sorted(heading_authorities.items())
        },
        "heading_completion_warnings": heading_completion.warnings,
        "defined_style_count": len(catalog.styles),
        "hidden_style_count": max(0, len(catalog.styles) - len(used_formats)),
        "heading_numbering": core.heading_numbering_manifest(
            heading_numbering
        ),
        "heading_paragraph_indents": heading_paragraph_indents,
        "heading_numbering_conflicts": sorted(numbering_conflicts),
        "used_table_styles": sorted(table_usage.keys()),
        "preferred_table_style": (
            table_usage.most_common(1)[0][0]
            if table_usage
            else (
                str(table_style_edit_candidate["style_id"])
                if table_style_edit_candidate is not None
                else catalog.fallback("table")
            )
        ),
        "manual_formatting": {
            "paragraph_count": manual_paragraphs,
            "run_count": manual_runs,
        },
        "document_summary": {
            "paragraph_count": paragraphs,
            "run_count": runs,
            "table_count": tables,
            "section_count": sections,
        },
        "page_layout": {
            "width_cm": page_width_cm,
            "height_cm": page_height_cm,
            "orientation": orientation,
            "margin_top_cm": _twips_to_cm(
                pg_margin.get(core.qn(core.W_NS, "top")) if pg_margin is not None else None
            ),
            "margin_bottom_cm": _twips_to_cm(
                pg_margin.get(core.qn(core.W_NS, "bottom")) if pg_margin is not None else None
            ),
            "margin_left_cm": _twips_to_cm(
                pg_margin.get(core.qn(core.W_NS, "left")) if pg_margin is not None else None
            ),
            "margin_right_cm": _twips_to_cm(
                pg_margin.get(core.qn(core.W_NS, "right")) if pg_margin is not None else None
            ),
        },
        "section_layouts": [
            [
                base64.b64encode(core.serialize_xml(node)).decode("ascii")
                for node in layout
            ]
            for layout in layouts
        ],
        "privacy": {
            "source_path_stored": False,
            "source_file_name_stored": False,
            "source_text_stored": False,
            "source_media_stored": False,
            "embedded_fonts_stored": False,
            "generic_samples_only": True,
            "display_name_derived_from_source": True,
        },
    }
    if table_style_edit_candidate is not None:
        # Keep the format overview truthful: an unused table style is not part
        # of used_formats.  The editor may expose exactly this one allow-listed
        # candidate without revealing every dormant Word gallery style.
        manifest["table_style_edit_candidate"] = table_style_edit_candidate
    return package, catalog, manifest


def _relationship_type_for_role(role: str) -> str:
    return {
        "styles": core.R_NS + "/styles",
        "stylesWithEffects": "http://schemas.microsoft.com/office/2007/relationships/stylesWithEffects",
        "theme": core.R_NS + "/theme",
        "fontTable": core.R_NS + "/fontTable",
        "numbering": core.R_NS + "/numbering",
    }[role]


def _sanitize_format_part(role: str, data: bytes, part_name: str) -> bytes:
    """Keep formatting XML while dropping every binary relationship hook."""
    root = core.parse_xml(data, part_name)
    expected_roots = {
        "styles": {"styles"},
        "stylesWithEffects": {"styles"},
        "theme": {"theme"},
        "fontTable": {"fonts"},
        "numbering": {"numbering"},
    }
    if etree.QName(root).localname not in expected_roots[role]:
        raise core.TransferError("格式部件类型异常：%s" % part_name)

    if role == "fontTable":
        for node in root.xpath(
            ".//w:embedRegular | .//w:embedBold | "
            ".//w:embedItalic | .//w:embedBoldItalic",
            namespaces=core.NS,
        ):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
    elif role == "numbering":
        # Picture bullets require a media part.  The private, portable v1 pack
        # intentionally keeps the text/numbering definitions but not images.
        for node in root.xpath(
            ".//w:numPicBullet | .//w:lvlPicBulletId", namespaces=core.NS
        ):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
    elif role == "theme":
        for node in root.xpath(".//a:blipFill | .//a:blip", namespaces=A):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)

    relationship_prefix = "{%s}" % core.R_NS
    for node in root.iter():
        for attribute in list(node.attrib):
            if attribute.startswith(relationship_prefix):
                del node.attrib[attribute]
    return core.serialize_xml(root)


def _sanitized_settings(data: bytes) -> bytes:
    source_root = core.parse_xml(data, "settings.xml")
    target_root = etree.Element(source_root.tag, nsmap=source_root.nsmap)
    for child in source_root:
        if etree.QName(child).localname in core.SETTINGS_FORMAT_TAGS:
            target_root.append(copy.deepcopy(child))
    return core.serialize_xml(target_root)


def _filtered_content_types(
    source_data: bytes,
    collected_parts: Set[str],
) -> bytes:
    source_root = core.parse_xml(source_data, "[Content_Types].xml")
    target_root = etree.Element(source_root.tag, nsmap=source_root.nsmap)
    extensions = {
        Path(name).suffix.lstrip(".").casefold()
        for name in collected_parts
        if Path(name).suffix
    }
    extensions.update({"xml", "rels"})
    for node in source_root.findall(core.qn(core.CT_NS, "Default")):
        if node.get("Extension", "").casefold() in extensions:
            target_root.append(copy.deepcopy(node))
    wanted = {"/" + name.lstrip("/") for name in collected_parts}
    for node in source_root.findall(core.qn(core.CT_NS, "Override")):
        if node.get("PartName") in wanted:
            target_root.append(copy.deepcopy(node))
    return core.serialize_xml(target_root)


def _pack_format_entries(source_entries: Dict[str, bytes]) -> Dict[str, bytes]:
    main_rels, roles = core.collect_format_relationships(source_entries)
    for role, fallback in core.ROLE_FALLBACK_PARTS.items():
        if role not in roles and fallback in source_entries:
            roles[role] = (fallback, _relationship_type_for_role(role))
    if "styles" not in roles:
        raise core.TransferError("源文件缺少样式关系，无法创建格式库。")

    collected: Set[str] = set()
    result: Dict[str, bytes] = {}
    filtered_rels = etree.Element(
        core.qn(core.PKG_REL_NS, "Relationships"), nsmap={None: core.PKG_REL_NS}
    )
    existing_by_role: Dict[str, etree._Element] = {}
    for rel in main_rels.findall(core.qn(core.PKG_REL_NS, "Relationship")):
        role = core.relationship_role(rel.get("Type", ""))
        if role in core.ROLE_NAMES:
            existing_by_role[role] = rel

    relationship_index = 1
    for role in ("styles", "stylesWithEffects", "theme", "fontTable", "numbering"):
        record = roles.get(role)
        if record is None:
            continue
        part_name, rel_type = record
        if part_name not in source_entries:
            raise core.TransferError("源格式部件不存在：%s" % part_name)
        # Only primary, known-format XML is stored.  Its .rels graph is never
        # followed, preventing theme images, embedded fonts, VBA or arbitrary
        # package objects from entering the persistent library.
        result[part_name] = _sanitize_format_part(
            role, source_entries[part_name], part_name
        )
        collected.add(part_name)
        source_rel = existing_by_role.get(role)
        if source_rel is not None:
            filtered_rels.append(copy.deepcopy(source_rel))
        else:
            rel = etree.SubElement(
                filtered_rels, core.qn(core.PKG_REL_NS, "Relationship")
            )
            rel.set("Id", "rIdFmtPack%d" % relationship_index)
            relationship_index += 1
            rel.set("Type", rel_type)
            rel.set(
                "Target",
                core.relative_relationship_target("word/document.xml", part_name),
            )

    result["word/_rels/document.xml.rels"] = core.serialize_xml(filtered_rels)
    collected.add("word/_rels/document.xml.rels")
    if "word/settings.xml" in source_entries:
        result["word/settings.xml"] = _sanitized_settings(
            source_entries["word/settings.xml"]
        )
        collected.add("word/settings.xml")
    result["[Content_Types].xml"] = _filtered_content_types(
        source_entries["[Content_Types].xml"], collected
    )
    return result


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o600 << 16
    return info


def _part_checksums(entries: Dict[str, bytes]) -> Dict[str, str]:
    return {
        name: hashlib.sha256(data).hexdigest()
        for name, data in sorted(entries.items())
    }


def _format_fingerprint(checksums: Dict[str, str]) -> str:
    digest = hashlib.sha256()
    for name, checksum in sorted(checksums.items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(checksum.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _write_style_pack_archive(
    pack_path: Path,
    manifest: Dict[str, object],
    format_entries: Dict[str, bytes],
    force: bool = False,
) -> Dict[str, object]:
    """Atomically write and verify a privacy-filtered style pack."""
    pack_path = pack_path.expanduser().resolve()
    if pack_path.suffix.lower() != PACK_SUFFIX:
        raise core.TransferError("格式库文件必须使用 %s 扩展名。" % PACK_SUFFIX)
    if pack_path.exists() and not force:
        raise core.TransferError("格式库文件已存在。")

    persisted_manifest = copy.deepcopy(manifest)
    persisted_manifest.pop("pack_path", None)
    persisted_manifest["format_part_count"] = len(format_entries)
    checksums = _part_checksums(format_entries)
    persisted_manifest["part_sha256"] = checksums
    persisted_manifest["format_fingerprint"] = _format_fingerprint(checksums)

    parent_existed = pack_path.parent.exists()
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    if not parent_existed:
        os.chmod(pack_path.parent, 0o700)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=".%s." % pack_path.name,
        suffix=".tmp",
        dir=str(pack_path.parent),
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    os.chmod(temp_path, 0o600)
    try:
        with zipfile.ZipFile(
            temp_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            archive.writestr(
                _zip_info("manifest.json"),
                json.dumps(
                    persisted_manifest,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8"),
            )
            for name, data in sorted(format_entries.items()):
                archive.writestr(_zip_info(PART_PREFIX + name), data)
        with zipfile.ZipFile(temp_path, "r") as verify:
            bad = verify.testzip()
            if bad:
                raise core.TransferError("格式库校验失败：%s" % bad)
            if "manifest.json" not in verify.namelist():
                raise core.TransferError("格式库缺少 manifest.json。")
        # Validate the complete manifest/checksum contract before the atomic
        # rename, not just the ZIP CRCs.  load_style_pack accepts the temporary
        # suffix and performs the same checks used for every later read.
        load_style_pack(temp_path)
        os.replace(temp_path, pack_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    result = dict(persisted_manifest)
    result["pack_path"] = str(pack_path)
    return result


def create_style_pack(
    source_path: Path,
    pack_path: Path,
    display_name: Optional[str] = None,
    force: bool = False,
) -> Dict[str, object]:
    pack_path = pack_path.expanduser().resolve()
    if pack_path.suffix.lower() != PACK_SUFFIX:
        raise core.TransferError("格式库文件必须使用 %s 扩展名。" % PACK_SUFFIX)
    if pack_path.exists() and not force:
        raise core.TransferError("格式库文件已存在。")

    package, _catalog, manifest = inspect_source(source_path)
    if display_name and display_name.strip():
        manifest["name"] = display_name.strip()
        privacy = manifest.get("privacy")
        if isinstance(privacy, dict):
            privacy["display_name_derived_from_source"] = False
    format_entries = _pack_format_entries(package.entries)
    return _write_style_pack_archive(
        pack_path,
        manifest,
        format_entries,
        force=force,
    )


def _manifest_string(
    value: object,
    field: str,
    *,
    maximum: int,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise core.TransferError("格式库字段 %s 必须是文本。" % field)
    if (not value and not allow_empty) or len(value) > maximum:
        raise core.TransferError(
            "格式库字段 %s 长度无效（最多 %d 个字符）。" % (field, maximum)
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise core.TransferError("格式库字段 %s 包含控制字符。" % field)
    return value


def _manifest_nonnegative_int(value: object, field: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
    ):
        raise core.TransferError("格式库字段 %s 必须是非负整数。" % field)
    return value


def _manifest_optional_number(value: object, field: str) -> None:
    if value is None:
        return
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise core.TransferError("格式库字段 %s 必须是有限数值或空值。" % field)


def _validate_used_format_record(
    raw: object, field: str
) -> Tuple[str, str]:
    if not isinstance(raw, dict):
        raise core.TransferError("格式库字段 %s 必须是对象。" % field)
    style_id = _manifest_string(
        raw.get("style_id"), "%s.style_id" % field, maximum=255
    )
    style_type = _manifest_string(
        raw.get("type"), "%s.type" % field, maximum=32
    )
    if style_type not in {"paragraph", "character", "table"}:
        raise core.TransferError("格式库字段 %s.type 不受支持。" % field)
    _manifest_string(raw.get("name"), "%s.name" % field, maximum=512)
    _manifest_nonnegative_int(
        raw.get("usage_count"), "%s.usage_count" % field
    )
    _manifest_string(
        raw.get("sample"), "%s.sample" % field, maximum=4096,
        allow_empty=True,
    )
    if not isinstance(raw.get("numbered"), bool):
        raise core.TransferError("格式库字段 %s.numbered 必须是布尔值。" % field)

    for key in ("inferred", "configured", "bold", "italic"):
        value = raw.get(key)
        if value is not None and not isinstance(value, bool):
            raise core.TransferError(
                "格式库字段 %s.%s 必须是布尔值或空值。" % (field, key)
            )
    for key in (
        "inference_label",
        "font_latin",
        "font_east_asia",
        "color_hex",
        "alignment",
        "line_rule",
        "numbering_format",
        "numbering_pattern",
        "numbering_example",
        "table_fill_hex",
        "table_accent_hex",
    ):
        value = raw.get(key)
        if value is not None:
            _manifest_string(
                value, "%s.%s" % (field, key), maximum=1024,
                allow_empty=True,
            )
    for key in (
        "size_pt",
        "space_before_pt",
        "space_after_pt",
        "line_spacing",
    ):
        _manifest_optional_number(raw.get(key), "%s.%s" % (field, key))
    for key in ("outline_level", "numbering_level"):
        value = raw.get(key)
        if value is not None:
            parsed = _manifest_nonnegative_int(value, "%s.%s" % (field, key))
            if parsed > 8:
                raise core.TransferError(
                    "格式库字段 %s.%s 必须在 0–8 之间。" % (field, key)
                )

    usage_by_story = raw.get("usage_by_story")
    if usage_by_story is not None:
        if not isinstance(usage_by_story, dict):
            raise core.TransferError(
                "格式库字段 %s.usage_by_story 必须是对象。" % field
            )
        for key, value in usage_by_story.items():
            _manifest_string(
                key, "%s.usage_by_story 键" % field, maximum=128
            )
            _manifest_nonnegative_int(
                value, "%s.usage_by_story.%s" % (field, key)
            )
    return style_type, style_id


def _validate_string_list(value: object, field: str) -> None:
    if not isinstance(value, list):
        raise core.TransferError("格式库字段 %s 必须是文本数组。" % field)
    for index, item in enumerate(value):
        _manifest_string(
            item, "%s[%d]" % (field, index), maximum=1024,
            allow_empty=True,
        )


def _validate_count_object(
    value: object, field: str, required_keys: Sequence[str]
) -> None:
    if not isinstance(value, dict):
        raise core.TransferError("格式库字段 %s 必须是对象。" % field)
    for key in required_keys:
        _manifest_nonnegative_int(value.get(key), "%s.%s" % (field, key))


def _validate_style_pack_manifest(manifest: Dict[str, object]) -> None:
    """Validate the stable subset consumed by Swift and pack operations."""

    if "pack_path" in manifest:
        raise core.TransferError("格式库不能保存本机 pack_path 字段。")
    _manifest_string(manifest.get("id"), "id", maximum=128)
    _manifest_string(manifest.get("name"), "name", maximum=512)

    raw_formats = manifest.get("used_formats")
    if not isinstance(raw_formats, list):
        raise core.TransferError("格式库字段 used_formats 必须是数组。")
    seen_formats: Set[Tuple[str, str]] = set()
    for index, raw in enumerate(raw_formats):
        identity = _validate_used_format_record(
            raw, "used_formats[%d]" % index
        )
        if identity in seen_formats:
            raise core.TransferError(
                "格式库包含重复样式：%s/%s。" % identity
            )
        seen_formats.add(identity)

    raw_table_styles = manifest.get("used_table_styles")
    _validate_string_list(raw_table_styles, "used_table_styles")
    if len(set(raw_table_styles)) != len(raw_table_styles):
        raise core.TransferError("格式库字段 used_table_styles 包含重复值。")

    for key in (
        "used_style_count",
        "inferred_style_count",
        "custom_style_count",
        "defined_style_count",
        "hidden_style_count",
        "format_part_count",
    ):
        if key == "used_style_count" or key == "format_part_count" or key in manifest:
            _manifest_nonnegative_int(manifest.get(key), key)

    _validate_count_object(
        manifest.get("manual_formatting"),
        "manual_formatting",
        ("paragraph_count", "run_count"),
    )
    _validate_count_object(
        manifest.get("document_summary"),
        "document_summary",
        ("paragraph_count", "run_count", "table_count", "section_count"),
    )

    page_layout = manifest.get("page_layout")
    if not isinstance(page_layout, dict):
        raise core.TransferError("格式库字段 page_layout 必须是对象。")
    for key in (
        "width_cm",
        "height_cm",
        "margin_top_cm",
        "margin_bottom_cm",
        "margin_left_cm",
        "margin_right_cm",
    ):
        _manifest_optional_number(page_layout.get(key), "page_layout.%s" % key)
    orientation = page_layout.get("orientation")
    if orientation is not None:
        _manifest_string(
            orientation, "page_layout.orientation", maximum=32,
            allow_empty=True,
        )

    privacy = manifest.get("privacy")
    if privacy is not None:
        if not isinstance(privacy, dict):
            raise core.TransferError("格式库字段 privacy 必须是对象。")
        for key, value in privacy.items():
            _manifest_string(key, "privacy 键", maximum=128)
            if not isinstance(value, bool):
                raise core.TransferError(
                    "格式库字段 privacy.%s 必须是布尔值。" % key
                )

    for key in (
        "inferred_heading_styles",
        "heading_numbering_conflicts",
        "heading_completion_warnings",
    ):
        if key in manifest:
            _validate_string_list(manifest[key], key)
    for key in ("created_at", "source_file_name", "source_sha256"):
        value = manifest.get(key)
        if value is not None:
            _manifest_string(value, key, maximum=1024, allow_empty=True)
    preferred_table = manifest.get("preferred_table_style")
    if preferred_table is not None:
        _manifest_string(
            preferred_table, "preferred_table_style", maximum=255,
            allow_empty=True,
        )

    candidate = manifest.get("table_style_edit_candidate")
    if candidate is not None:
        candidate_identity = _validate_used_format_record(
            candidate, "table_style_edit_candidate"
        )
        if candidate_identity[0] != "table":
            raise core.TransferError("格式库的可选表格方案必须是 table 类型。")

    for key in ("heading_numbering", "heading_paragraph_indents", "derivation"):
        if key in manifest and not isinstance(manifest[key], dict):
            raise core.TransferError("格式库字段 %s 必须是对象。" % key)
    authorities = manifest.get("heading_authorities")
    if authorities is not None:
        if not isinstance(authorities, dict):
            raise core.TransferError("格式库字段 heading_authorities 必须是对象。")
        for key, value in authorities.items():
            _manifest_string(key, "heading_authorities 键", maximum=8)
            _manifest_string(
                value, "heading_authorities.%s" % key, maximum=255
            )
    section_layouts = manifest.get("section_layouts")
    if section_layouts is not None:
        if not isinstance(section_layouts, list):
            raise core.TransferError("格式库字段 section_layouts 必须是数组。")
        for section_index, section in enumerate(section_layouts):
            if not isinstance(section, list):
                raise core.TransferError(
                    "格式库字段 section_layouts[%d] 必须是数组。"
                    % section_index
                )
            _validate_string_list(
                section, "section_layouts[%d]" % section_index
            )


def load_style_pack(pack_path: Path) -> Tuple[Dict[str, object], Dict[str, bytes]]:
    pack_path = pack_path.expanduser().resolve()
    if not pack_path.exists() or not zipfile.is_zipfile(pack_path):
        raise core.TransferError("格式库不存在或已损坏：%s" % pack_path)
    with zipfile.ZipFile(pack_path, "r") as archive:
        member_list = archive.infolist()
        # Validate every central-directory record before testzip() or read()
        # can decompress attacker-controlled data.  The shared validator
        # handles names, duplicates, encryption, compression methods and
        # compression-ratio bombs; packs then apply their tighter memory caps
        # and manifest/parts-only contract below.
        core.validate_package_members(member_list, "格式库")
        if len(member_list) > MAX_PACK_MEMBERS:
            raise core.TransferError(
                "格式库包含过多条目（%d 个，最多允许 %d 个）。"
                % (len(member_list), MAX_PACK_MEMBERS)
            )
        total_size = 0
        for info in member_list:
            name = info.filename
            if name != "manifest.json" and not name.startswith(PART_PREFIX):
                raise core.TransferError("格式库包含未知条目：%s" % name)
            if info.file_size > MAX_PACK_MEMBER_BYTES:
                raise core.TransferError("格式库条目过大：%s" % name)
            total_size += info.file_size
        if total_size > MAX_PACK_TOTAL_BYTES:
            raise core.TransferError("格式库体积异常，已停止读取。")
        bad = archive.testzip()
        if bad:
            raise core.TransferError("格式库压缩数据损坏：%s" % bad)
        try:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise core.TransferError("无法读取格式库信息：%s" % exc) from exc
        if not isinstance(manifest, dict):
            raise core.TransferError("格式库信息结构无效。")
        schema_version = manifest.get("schema_version")
        if (
            not isinstance(schema_version, int)
            or isinstance(schema_version, bool)
            or schema_version != PACK_SCHEMA_VERSION
        ):
            raise core.TransferError("格式库版本不受支持。")
        entries = {
            info.filename[len(PART_PREFIX) :]: archive.read(info.filename)
            for info in member_list
            if info.filename.startswith(PART_PREFIX) and not info.is_dir()
        }
    required = {
        "[Content_Types].xml",
        "word/styles.xml",
        "word/_rels/document.xml.rels",
    }
    missing = required.difference(entries)
    if missing:
        raise core.TransferError("格式库缺少部件：%s" % ", ".join(sorted(missing)))
    expected_checksums = manifest.get("part_sha256")
    if not isinstance(expected_checksums, dict):
        raise core.TransferError("格式库缺少完整性校验信息。")
    actual_checksums = _part_checksums(entries)
    if expected_checksums != actual_checksums:
        raise core.TransferError("格式库完整性校验失败，文件可能已被修改。")
    expected_fingerprint = manifest.get("format_fingerprint")
    if expected_fingerprint is not None:
        if (
            not isinstance(expected_fingerprint, str)
            or expected_fingerprint != _format_fingerprint(actual_checksums)
        ):
            raise core.TransferError("格式库格式指纹校验失败，文件可能已被修改。")
    _validate_style_pack_manifest(manifest)
    if manifest.get("format_part_count") != len(entries):
        raise core.TransferError("格式库部件数量与清单不一致。")
    manifest = dict(manifest)
    manifest["pack_path"] = str(pack_path)
    _synthesize_legacy_table_edit_candidate(manifest, entries)
    return manifest, entries


def _placeholder_document() -> bytes:
    root = etree.Element(
        core.qn(core.W_NS, "document"),
        nsmap={"w": core.W_NS, "r": core.R_NS},
    )
    body = etree.SubElement(root, core.qn(core.W_NS, "body"))
    etree.SubElement(body, core.qn(core.W_NS, "p"))
    etree.SubElement(body, core.qn(core.W_NS, "sectPr"))
    return core.serialize_xml(root)


def _decode_layouts(manifest: Dict[str, object]) -> List[List[etree._Element]]:
    layouts: List[List[etree._Element]] = []
    for raw_layout in manifest.get("section_layouts", []):
        layout: List[etree._Element] = []
        if not isinstance(raw_layout, list):
            continue
        for encoded in raw_layout:
            try:
                data = base64.b64decode(str(encoded), validate=True)
                layout.append(core.parse_xml(data, "格式库页面设置"))
            except (ValueError, TypeError) as exc:
                raise core.TransferError("格式库页面设置损坏：%s" % exc) from exc
        layouts.append(layout)
    return layouts


_RUN_STYLE_EDIT_FIELDS = {
    "font_east_asia",
    "font_latin",
    "size_pt",
    "bold",
    "color_hex",
}
_TABLE_STYLE_EDIT_FIELDS = {"table_fill_hex", "table_accent_hex"}
_STYLE_EDIT_FIELDS = _RUN_STYLE_EDIT_FIELDS | _TABLE_STYLE_EDIT_FIELDS
_DERIVED_MANIFEST_COPY_FIELDS = {
    "heading_authorities",
    "heading_completion_warnings",
    "heading_numbering",
    "heading_paragraph_indents",
    "heading_numbering_conflicts",
    "manual_formatting",
    "document_summary",
    "page_layout",
    "section_layouts",
}
_TABLE_PROPERTY_ORDER = (
    "tblStyle",
    "tblpPr",
    "tblOverlap",
    "bidiVisual",
    "tblStyleRowBandSize",
    "tblStyleColBandSize",
    "tblW",
    "jc",
    "tblCellSpacing",
    "tblInd",
    "tblBorders",
    "shd",
    "tblLayout",
    "tblCellMar",
    "tblLook",
    "tblCaption",
    "tblDescription",
    "tblPrChange",
)
_TABLE_STYLE_PROPERTY_ORDER = ("pPr", "rPr", "tblPr", "trPr", "tcPr")
_TABLE_CELL_PROPERTY_ORDER = (
    "cnfStyle",
    "tcW",
    "gridSpan",
    "hMerge",
    "vMerge",
    "tcBorders",
    "shd",
    "noWrap",
    "tcMar",
    "textDirection",
    "tcFitText",
    "vAlign",
    "hideMark",
    "headers",
    "cellIns",
    "cellDel",
    "cellMerge",
    "tcPrChange",
)


def _validated_short_text(value: object, label: str, maximum: int = 128) -> str:
    if not isinstance(value, str):
        raise core.TransferError("%s必须是文本。" % label)
    normalized = value.strip()
    if not normalized:
        raise core.TransferError("%s不能为空。" % label)
    if len(normalized) > maximum:
        raise core.TransferError("%s过长，最多允许 %d 个字符。" % (label, maximum))
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise core.TransferError("%s包含不允许的控制字符。" % label)
    return normalized


def _validated_edit_color(value: object, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"#?[0-9A-Fa-f]{6}", value.strip()
    ):
        raise core.TransferError("%s必须是 6 位十六进制颜色，例如 #165D52。" % label)
    return value.strip().lstrip("#").upper()


def _normalize_style_edits(payload: object) -> List[Dict[str, object]]:
    """Validate the v1 style-editor protocol and return canonical edits.

    Protocol::

        {"styles": [{"style_id": "Heading1", "font_east_asia": "宋体",
                     "font_latin": "Arial", "size_pt": 18,
                     "bold": true, "color_hex": "165D52"},
                    {"style_id": "TableGrid", "table_fill_hex": "FFFFFF",
                     "table_accent_hex": "D9EAF7"}]}

    Unknown fields are rejected deliberately so a GUI cannot accidentally
    mutate arbitrary OOXML through this interface.
    """
    if not isinstance(payload, dict):
        raise core.TransferError("格式编辑请求必须是 JSON 对象。")
    unknown_top_level = set(payload).difference({"styles"})
    if unknown_top_level:
        raise core.TransferError(
            "格式编辑请求包含未知字段：%s。"
            % "、".join(sorted(str(value) for value in unknown_top_level))
        )
    raw_edits = payload.get("styles")
    if not isinstance(raw_edits, list) or not raw_edits:
        raise core.TransferError("格式编辑请求至少需要包含一个样式。")
    if len(raw_edits) > 256:
        raise core.TransferError("单次最多编辑 256 个样式。")

    normalized_edits: List[Dict[str, object]] = []
    seen_style_ids: Set[str] = set()
    for index, raw_edit in enumerate(raw_edits, start=1):
        if not isinstance(raw_edit, dict):
            raise core.TransferError("第 %d 个样式编辑项必须是 JSON 对象。" % index)
        unknown = set(raw_edit).difference({"style_id"} | _STYLE_EDIT_FIELDS)
        if unknown:
            raise core.TransferError(
                "第 %d 个样式编辑项包含未知字段：%s。"
                % (index, "、".join(sorted(str(value) for value in unknown)))
            )
        style_id = _validated_short_text(
            raw_edit.get("style_id"), "第 %d 个样式 ID" % index
        )
        if style_id in seen_style_ids:
            raise core.TransferError("样式 %s 在编辑请求中重复出现。" % style_id)
        seen_style_ids.add(style_id)

        edit: Dict[str, object] = {"style_id": style_id}
        if "font_east_asia" in raw_edit:
            edit["font_east_asia"] = _validated_short_text(
                raw_edit["font_east_asia"], "东亚字体", maximum=127
            )
        if "font_latin" in raw_edit:
            edit["font_latin"] = _validated_short_text(
                raw_edit["font_latin"], "西文字体", maximum=127
            )
        if "size_pt" in raw_edit:
            raw_size = raw_edit["size_pt"]
            if isinstance(raw_size, bool) or not isinstance(raw_size, (int, float)):
                raise core.TransferError("字号必须是 5–200 磅之间的数字。")
            try:
                size = float(raw_size)
            except (OverflowError, TypeError, ValueError):
                raise core.TransferError("字号必须是 5–200 磅之间的数字。")
            if not math.isfinite(size):
                raise core.TransferError("字号必须是 5–200 磅之间的数字。")
            if not 5.0 <= size <= 200.0 or not (size * 2).is_integer():
                raise core.TransferError("字号必须在 5–200 磅之间，并以 0.5 磅递增。")
            edit["size_pt"] = size
        if "bold" in raw_edit:
            if not isinstance(raw_edit["bold"], bool):
                raise core.TransferError("粗体值必须是 true 或 false。")
            edit["bold"] = raw_edit["bold"]
        if "color_hex" in raw_edit:
            edit["color_hex"] = _validated_edit_color(
                raw_edit["color_hex"], "文字颜色"
            )
        if "table_fill_hex" in raw_edit:
            edit["table_fill_hex"] = _validated_edit_color(
                raw_edit["table_fill_hex"], "表格底色"
            )
        if "table_accent_hex" in raw_edit:
            edit["table_accent_hex"] = _validated_edit_color(
                raw_edit["table_accent_hex"], "表格强调色"
            )
        if len(edit) == 1:
            raise core.TransferError("样式 %s 没有提供任何可修改字段。" % style_id)
        normalized_edits.append(edit)
    return normalized_edits


def _ordered_insert_child(
    parent: etree._Element,
    node: etree._Element,
    order: Sequence[str],
) -> None:
    ranks = {name: index for index, name in enumerate(order)}
    node_rank = ranks.get(etree.QName(node).localname, len(ranks))
    insertion = len(parent)
    for index, child in enumerate(parent):
        if ranks.get(etree.QName(child).localname, len(ranks)) > node_rank:
            insertion = index
            break
    parent.insert(insertion, node)


def _ensure_ordered_child(
    parent: etree._Element,
    local: str,
    order: Sequence[str],
) -> etree._Element:
    matches = parent.findall(core.qn(core.W_NS, local))
    if matches:
        for duplicate in matches[1:]:
            parent.remove(duplicate)
        return matches[0]
    node = etree.Element(core.qn(core.W_NS, local))
    _ordered_insert_child(parent, node, order)
    return node


def _apply_run_edits(
    run_properties: etree._Element,
    edit: Dict[str, object],
) -> None:
    if "font_latin" in edit or "font_east_asia" in edit:
        fonts = _ensure_ordered_child(
            run_properties, "rFonts", core.RPR_CHILD_ORDER
        )
        if "font_latin" in edit:
            font_name = str(edit["font_latin"])
            fonts.set(core.qn(core.W_NS, "ascii"), font_name)
            fonts.set(core.qn(core.W_NS, "hAnsi"), font_name)
            for attribute in ("asciiTheme", "hAnsiTheme"):
                fonts.attrib.pop(core.qn(core.W_NS, attribute), None)
        if "font_east_asia" in edit:
            fonts.set(
                core.qn(core.W_NS, "eastAsia"), str(edit["font_east_asia"])
            )
            fonts.attrib.pop(core.qn(core.W_NS, "eastAsiaTheme"), None)

    if "bold" in edit:
        value = "1" if bool(edit["bold"]) else "0"
        for local in ("b", "bCs"):
            node = _ensure_ordered_child(
                run_properties, local, core.RPR_CHILD_ORDER
            )
            node.set(core.qn(core.W_NS, "val"), value)

    if "color_hex" in edit:
        color = _ensure_ordered_child(
            run_properties, "color", core.RPR_CHILD_ORDER
        )
        color.set(core.qn(core.W_NS, "val"), str(edit["color_hex"]))
        for attribute in ("themeColor", "themeTint", "themeShade"):
            color.attrib.pop(core.qn(core.W_NS, attribute), None)

    if "size_pt" in edit:
        half_points = str(int(round(float(edit["size_pt"]) * 2)))
        for local in ("sz", "szCs"):
            node = _ensure_ordered_child(
                run_properties, local, core.RPR_CHILD_ORDER
            )
            node.set(core.qn(core.W_NS, "val"), half_points)


def _set_solid_shading(node: etree._Element, color_hex: str) -> None:
    node.set(core.qn(core.W_NS, "val"), "clear")
    node.set(core.qn(core.W_NS, "color"), "auto")
    node.set(core.qn(core.W_NS, "fill"), color_hex)
    for attribute in (
        "themeColor",
        "themeTint",
        "themeShade",
        "themeFill",
        "themeFillTint",
        "themeFillShade",
    ):
        node.attrib.pop(core.qn(core.W_NS, attribute), None)


def _apply_style_node_edit(
    style_node: etree._Element,
    style_type: str,
    edit: Dict[str, object],
) -> None:
    run_fields = _RUN_STYLE_EDIT_FIELDS.intersection(edit)
    table_fields = _TABLE_STYLE_EDIT_FIELDS.intersection(edit)
    if run_fields:
        if style_type not in {"paragraph", "character"}:
            raise core.TransferError(
                "样式 %s 不是段落或字符样式，不能修改字体属性。"
                % edit["style_id"]
            )
        run_properties = _ensure_ordered_child(
            style_node, "rPr", core.STYLE_CHILD_ORDER
        )
        _apply_run_edits(run_properties, edit)
    if table_fields:
        if style_type != "table":
            raise core.TransferError(
                "样式 %s 不是表格样式，不能修改表格配色。"
                % edit["style_id"]
            )
        if "table_fill_hex" in edit:
            table_properties = _ensure_ordered_child(
                style_node, "tblPr", core.STYLE_CHILD_ORDER
            )
            shading = _ensure_ordered_child(
                table_properties, "shd", _TABLE_PROPERTY_ORDER
            )
            _set_solid_shading(shading, str(edit["table_fill_hex"]))
        if "table_accent_hex" in edit:
            first_row = next(
                (
                    node
                    for node in style_node.findall("w:tblStylePr", namespaces=core.NS)
                    if node.get(core.qn(core.W_NS, "type")) == "firstRow"
                ),
                None,
            )
            if first_row is None:
                first_row = etree.Element(core.qn(core.W_NS, "tblStylePr"))
                first_row.set(core.qn(core.W_NS, "type"), "firstRow")
                # w:extLst must remain the final child of w:style.  Word is
                # tolerant of many ordering mistakes, but other OOXML readers
                # validate the schema sequence strictly.
                ext_list = style_node.find("w:extLst", namespaces=core.NS)
                insertion = (
                    style_node.index(ext_list)
                    if ext_list is not None
                    else len(style_node)
                )
                style_node.insert(insertion, first_row)
            cell_properties = _ensure_ordered_child(
                first_row, "tcPr", _TABLE_STYLE_PROPERTY_ORDER
            )
            shading = _ensure_ordered_child(
                cell_properties, "shd", _TABLE_CELL_PROPERTY_ORDER
            )
            _set_solid_shading(shading, str(edit["table_accent_hex"]))


def _append_missing_font_records(
    entries: Dict[str, bytes], edits: Sequence[Dict[str, object]]
) -> None:
    requested = {
        str(edit[field])
        for edit in edits
        for field in ("font_latin", "font_east_asia")
        if field in edit
    }
    if not requested:
        return
    _rels, roles = core.collect_format_relationships(entries)
    record = roles.get("fontTable")
    part_name = (
        record[0] if record is not None else core.ROLE_FALLBACK_PARTS["fontTable"]
    )
    if part_name not in entries:
        return
    root = core.parse_xml(entries[part_name], part_name)
    existing = {
        str(node.get(core.qn(core.W_NS, "name"), "")).casefold()
        for node in root.findall("w:font", namespaces=core.NS)
    }
    for name in sorted(requested, key=str.casefold):
        if name.casefold() in existing:
            continue
        node = etree.SubElement(root, core.qn(core.W_NS, "font"))
        node.set(core.qn(core.W_NS, "name"), name)
        existing.add(name.casefold())
    entries[part_name] = core.serialize_xml(root)


def _apply_heading_numbering_edits(
    entries: Dict[str, bytes],
    manifest: Dict[str, object],
    edits: Sequence[Dict[str, object]],
) -> None:
    """Keep a heading's visible number label aligned with edited text."""
    raw_rules = manifest.get("heading_numbering")
    if not isinstance(raw_rules, dict):
        return
    numbering_root, abstract_by_id, num_by_id, styles_by_id = core._numbering_index(
        entries
    )
    if numbering_root is None:
        return
    changed = False
    for edit in edits:
        run_edit = {
            key: value for key, value in edit.items() if key in _RUN_STYLE_EDIT_FIELDS
        }
        if not run_edit:
            continue
        raw_rule = raw_rules.get(str(edit["style_id"]))
        if not isinstance(raw_rule, dict):
            continue
        raw_num_id = raw_rule.get("num_id")
        raw_level = raw_rule.get("level")
        try:
            level = int(raw_level)
        except (TypeError, ValueError):
            continue
        num_node = num_by_id.get(str(raw_num_id))
        if num_node is None or not 0 <= level <= 8:
            continue
        abstract = core._abstract_for_num(
            num_node, abstract_by_id, num_by_id, styles_by_id
        )
        if abstract is None:
            continue
        level_nodes: List[etree._Element] = []
        base_level = core._level_node(abstract, level)
        if base_level is not None:
            level_nodes.append(base_level)
        override = core._override_for_level(num_node, level)
        override_level = (
            override.find("w:lvl", namespaces=core.NS)
            if override is not None
            else None
        )
        if override_level is not None:
            level_nodes.append(override_level)
        for level_node in level_nodes:
            run_properties = level_node.find("w:rPr", namespaces=core.NS)
            if run_properties is None:
                run_properties = etree.SubElement(
                    level_node, core.qn(core.W_NS, "rPr")
                )
            _apply_run_edits(run_properties, run_edit)
            changed = True
    if changed:
        _rels, roles = core.collect_format_relationships(entries)
        record = roles.get("numbering")
        part_name = (
            record[0]
            if record is not None
            else core.ROLE_FALLBACK_PARTS["numbering"]
        )
        entries[part_name] = core.serialize_xml(numbering_root)


def _refresh_used_format_previews(
    manifest: Dict[str, object],
    entries: Dict[str, bytes],
) -> Tuple[List[Dict[str, object]], core.StyleCatalog]:
    runtime_entries = dict(entries)
    runtime_entries["word/document.xml"] = _placeholder_document()
    catalog = core.build_style_catalog(
        runtime_entries["word/styles.xml"], runtime_entries["word/document.xml"]
    )
    styles_root = core.parse_xml(runtime_entries["word/styles.xml"], "styles.xml")
    theme = _theme_metadata(runtime_entries)
    numbering = core.heading_numbering_from_manifest(
        manifest.get("heading_numbering"), runtime_entries, catalog
    )
    previews: List[Dict[str, object]] = []
    raw_formats = manifest.get("used_formats")
    if not isinstance(raw_formats, list):
        raise core.TransferError("格式库缺少可编辑样式清单。")
    for raw_item in raw_formats:
        if not isinstance(raw_item, dict):
            continue
        style_id = str(raw_item.get("style_id", ""))
        info = catalog.styles.get(style_id)
        if info is None:
            continue
        raw_count = raw_item.get("usage_count", 0)
        usage_count = (
            int(raw_count)
            if isinstance(raw_count, int) and not isinstance(raw_count, bool)
            else 0
        )
        raw_stories = raw_item.get("usage_by_story", {})
        usage_by_story = (
            {
                str(key): int(value)
                for key, value in raw_stories.items()
                if isinstance(value, int)
                and not isinstance(value, bool)
                and value >= 0
            }
            if isinstance(raw_stories, dict)
            else {}
        )
        inferred = raw_item.get("inferred") is True
        configured = raw_item.get("configured") is True
        preview = _style_preview(
            style_id,
            info.style_type,
            max(0, usage_count),
            usage_by_story,
            catalog,
            styles_root,
            theme,
            numbering.get(style_id),
            inferred=inferred,
            inference_label=(
                "自定义表格方案"
                if configured
                else "智能补全"
                if inferred
                else None
            ),
        )
        if configured:
            preview["configured"] = True
        previews.append(preview)
    return previews, catalog


def _table_edit_candidate_style_id(
    manifest: Dict[str, object],
    catalog: core.StyleCatalog,
) -> Optional[str]:
    """Return the single manifest-exposed unused table style, if present."""
    raw_candidate = manifest.get("table_style_edit_candidate")
    if raw_candidate is None:
        return None
    if not isinstance(raw_candidate, dict):
        raise core.TransferError("格式库的可选表格方案信息无效。")
    if raw_candidate.get("type") != "table":
        raise core.TransferError("格式库的可选表格方案类型无效。")
    if (
        raw_candidate.get("inferred") is not True
        or raw_candidate.get("inference_label") != "可选表格方案"
    ):
        raise core.TransferError("格式库的可选表格方案标记无效。")
    raw_usage_count = raw_candidate.get("usage_count")
    if (
        not isinstance(raw_usage_count, int)
        or isinstance(raw_usage_count, bool)
        or raw_usage_count != 0
    ):
        raise core.TransferError("可选表格方案必须明确标记为未使用。")
    style_id = _validated_short_text(
        raw_candidate.get("style_id"), "可选表格方案 ID"
    )
    info = catalog.styles.get(style_id)
    if info is None or info.style_type != "table":
        raise core.TransferError("可选表格方案指向的表格样式不存在。")
    raw_used_table_styles = manifest.get("used_table_styles", [])
    if not isinstance(raw_used_table_styles, list):
        raise core.TransferError("格式库的已用表格样式清单无效。")
    used_table_styles = {str(value) for value in raw_used_table_styles}
    raw_used_formats = manifest.get("used_formats", [])
    if not isinstance(raw_used_formats, list):
        raise core.TransferError("格式库缺少可编辑样式清单。")
    used_format_ids = {
        str(item.get("style_id"))
        for item in raw_used_formats
        if isinstance(item, dict) and item.get("type") == "table"
    }
    if used_table_styles or style_id in used_format_ids:
        raise core.TransferError("已使用的表格样式不能同时作为可选表格方案。")
    if str(manifest.get("preferred_table_style") or "") != style_id:
        raise core.TransferError("可选表格方案与首选表格样式不一致。")
    return style_id


def _refreshed_table_candidate_preview(
    style_id: str,
    entries: Dict[str, bytes],
    catalog: core.StyleCatalog,
    *,
    inferred: bool,
    label: str,
) -> Dict[str, object]:
    _rels, roles = core.collect_format_relationships(entries)
    styles_record = roles.get("styles")
    styles_part = (
        styles_record[0]
        if styles_record is not None
        else core.ROLE_FALLBACK_PARTS["styles"]
    )
    styles_root = core.parse_xml(entries[styles_part], styles_part)
    return _style_preview(
        style_id,
        "table",
        0,
        {},
        catalog,
        styles_root,
        _theme_metadata(entries),
        inferred=inferred,
        inference_label=label,
    )


def _synthesize_legacy_table_edit_candidate(
    manifest: Dict[str, object], entries: Dict[str, bytes]
) -> None:
    """Expose one safe table candidate for older same-schema no-table packs.

    This only enriches the in-memory manifest returned to list/info/derive;
    the existing archive is never rewritten.
    """
    if "table_style_edit_candidate" in manifest:
        return
    raw_used_table_styles = manifest.get("used_table_styles", [])
    raw_used_formats = manifest.get("used_formats", [])
    if (
        not isinstance(raw_used_table_styles, list)
        or raw_used_table_styles
        or not isinstance(raw_used_formats, list)
        or any(
            isinstance(item, dict) and item.get("type") == "table"
            for item in raw_used_formats
        )
    ):
        return

    runtime_entries = dict(entries)
    runtime_entries["word/document.xml"] = _placeholder_document()
    catalog = core.build_style_catalog(
        runtime_entries["word/styles.xml"], runtime_entries["word/document.xml"]
    )
    preferred = manifest.get("preferred_table_style")
    preferred_id = str(preferred) if preferred else ""
    preferred_info = catalog.styles.get(preferred_id)
    if preferred_info is None or preferred_info.style_type != "table":
        fallback = catalog.fallback("table")
        preferred_id = str(fallback) if fallback else ""
        preferred_info = catalog.styles.get(preferred_id)
    if not preferred_id or preferred_info is None or preferred_info.style_type != "table":
        return

    manifest["preferred_table_style"] = preferred_id
    manifest["table_style_edit_candidate"] = _refreshed_table_candidate_preview(
        preferred_id,
        runtime_entries,
        catalog,
        inferred=True,
        label="可选表格方案",
    )


def derive_style_pack(
    pack_path: Path,
    output_path: Path,
    edits_payload: object,
    display_name: Optional[str] = None,
    force: bool = False,
) -> Dict[str, object]:
    """Create a new style pack by applying allow-listed visual edits.

    The input pack is always read-only.  The output receives a fresh identity,
    integrity data and format fingerprint, and is written atomically.
    """
    source_path = pack_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    if source_path == output_path:
        raise core.TransferError("为保护原格式方案，派生方案不能覆盖原文件。")
    if output_path.exists() and source_path.exists():
        try:
            if os.path.samefile(source_path, output_path):
                raise core.TransferError("为保护原格式方案，派生方案不能覆盖原文件。")
        except OSError:
            pass
    if output_path.exists() and not force:
        raise core.TransferError("格式库文件已存在。")

    source_manifest, loaded_entries = load_style_pack(source_path)
    edits = _normalize_style_edits(edits_payload)
    # Re-run the same format-only collector used for source imports.  Even a
    # manually crafted, checksum-valid pack therefore cannot carry document
    # stories, media, macros, embedded fonts or relationship hooks forward.
    entries = _pack_format_entries(loaded_entries)
    runtime_entries = dict(entries)
    runtime_entries["word/document.xml"] = _placeholder_document()
    catalog = core.build_style_catalog(
        runtime_entries["word/styles.xml"], runtime_entries["word/document.xml"]
    )
    # Packs created before heading-numbering metadata was introduced still
    # contain the complete styles/numbering parts.  Derivation must use the
    # same compatibility inference as apply_style_pack so editing a heading's
    # font also edits its visible number label.  Persist the inferred rules in
    # the new pack so subsequent edits no longer depend on legacy fallback.
    effective_manifest = copy.deepcopy(source_manifest)
    if "heading_numbering" not in effective_manifest:
        legacy_heading_ids = {
            str(item.get("style_id"))
            for item in effective_manifest.get("used_formats", [])
            if isinstance(item, dict)
            and item.get("type") == "paragraph"
            and item.get("outline_level") is not None
        }
        inferred_heading_numbering = core.infer_heading_numbering_rules(
            runtime_entries, catalog, legacy_heading_ids
        )
        effective_manifest["heading_numbering"] = core.heading_numbering_manifest(
            inferred_heading_numbering
        )
    exposed_style_ids = {
        str(item.get("style_id"))
        for item in effective_manifest.get("used_formats", [])
        if isinstance(item, dict) and item.get("style_id")
    }
    candidate_style_id = _table_edit_candidate_style_id(
        effective_manifest, catalog
    )
    if candidate_style_id is not None:
        exposed_style_ids.add(candidate_style_id)
    edited_style_ids = {str(edit["style_id"]) for edit in edits}
    candidate_activated = (
        candidate_style_id is not None
        and candidate_style_id in edited_style_ids
    )

    _rels, roles = core.collect_format_relationships(entries)
    styles_record = roles.get("styles")
    styles_part = (
        styles_record[0]
        if styles_record is not None
        else core.ROLE_FALLBACK_PARTS["styles"]
    )
    if styles_part not in entries:
        raise core.TransferError("格式库缺少可编辑的样式部件。")
    primary_root = core.parse_xml(entries[styles_part], styles_part)
    primary_nodes: Dict[str, etree._Element] = {}
    for node in primary_root.findall("w:style", namespaces=core.NS):
        raw_style_id = node.get(core.qn(core.W_NS, "styleId"))
        if not raw_style_id:
            continue
        style_id = str(raw_style_id)
        if style_id in primary_nodes:
            raise core.TransferError(
                "格式方案包含重复的样式 ID：%s，不能安全编辑。" % style_id
            )
        primary_nodes[style_id] = node
    for edit in edits:
        style_id = str(edit["style_id"])
        info = catalog.styles.get(style_id)
        if info is None or style_id not in primary_nodes:
            raise core.TransferError("格式方案中不存在样式：%s。" % style_id)
        if style_id not in exposed_style_ids:
            raise core.TransferError("样式 %s 未在此格式方案的可编辑清单中。" % style_id)
        _apply_style_node_edit(primary_nodes[style_id], info.style_type, edit)
    entries[styles_part] = core.serialize_xml(primary_root)

    effects_record = roles.get("stylesWithEffects")
    effects_part = (
        effects_record[0]
        if effects_record is not None
        else core.ROLE_FALLBACK_PARTS["stylesWithEffects"]
    )
    if effects_part in entries and effects_part != styles_part:
        effects_root = core.parse_xml(entries[effects_part], effects_part)
        effects_nodes: Dict[str, etree._Element] = {}
        for node in effects_root.findall("w:style", namespaces=core.NS):
            raw_style_id = node.get(core.qn(core.W_NS, "styleId"))
            if not raw_style_id:
                continue
            style_id = str(raw_style_id)
            if style_id in effects_nodes:
                raise core.TransferError(
                    "格式方案的兼容样式部件包含重复 ID：%s，不能安全编辑。"
                    % style_id
                )
            effects_nodes[style_id] = node
        for edit in edits:
            style_id = str(edit["style_id"])
            info = catalog.styles[style_id]
            node = effects_nodes.get(style_id)
            if node is None or node.get(core.qn(core.W_NS, "type"), "paragraph") != info.style_type:
                replacement = copy.deepcopy(primary_nodes[style_id])
                if node is not None:
                    effects_root.replace(node, replacement)
                else:
                    ext_list = effects_root.find("w:extLst", namespaces=core.NS)
                    insertion = (
                        effects_root.index(ext_list)
                        if ext_list is not None
                        else len(effects_root)
                    )
                    effects_root.insert(insertion, replacement)
                effects_nodes[style_id] = replacement
            else:
                _apply_style_node_edit(node, info.style_type, edit)
        entries[effects_part] = core.serialize_xml(effects_root)

    _apply_heading_numbering_edits(entries, effective_manifest, edits)
    _append_missing_font_records(entries, edits)
    # Final privacy and relationship pass after all XML mutations.
    entries = _pack_format_entries(entries)
    previews, refreshed_catalog = _refresh_used_format_previews(
        effective_manifest, entries
    )
    refreshed_candidate: Optional[Dict[str, object]] = None
    if candidate_style_id is not None:
        refreshed_candidate = _refreshed_table_candidate_preview(
            candidate_style_id,
            entries,
            refreshed_catalog,
            inferred=True,
            label=(
                "自定义表格方案"
                if candidate_activated
                else "可选表格方案"
            ),
        )
        if candidate_activated:
            refreshed_candidate["configured"] = True
            previews.append(refreshed_candidate)

    source_name = str(source_manifest.get("name") or "格式方案")
    default_name = (source_name + " · 自定义")[:120]
    name = _validated_short_text(
        display_name if display_name is not None else default_name,
        "派生方案名称",
        maximum=120,
    )
    derived_manifest: Dict[str, object] = {
        key: copy.deepcopy(effective_manifest[key])
        for key in _DERIVED_MANIFEST_COPY_FIELDS
        if key in effective_manifest
    }
    source_privacy = source_manifest.get("privacy")
    source_name_derived = True
    if isinstance(source_privacy, dict) and isinstance(
        source_privacy.get("display_name_derived_from_source"), bool
    ):
        source_name_derived = bool(
            source_privacy["display_name_derived_from_source"]
        )
    derived_manifest.update(
        {
            "schema_version": PACK_SCHEMA_VERSION,
            "id": str(uuid.uuid4()),
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "used_formats": previews,
            "used_style_count": sum(
                1 for item in previews if item.get("inferred") is not True
            ),
            "inferred_style_count": sum(
                1
                for item in previews
                if item.get("inferred") is True
                and item.get("type") == "paragraph"
                and item.get("outline_level") is not None
            ),
            "custom_style_count": sum(
                1 for item in previews if item.get("configured") is True
            ),
            "inferred_heading_styles": [
                str(item["style_id"])
                for item in previews
                if item.get("inferred") is True
                and item.get("type") == "paragraph"
                and item.get("outline_level") is not None
            ],
            "defined_style_count": len(refreshed_catalog.styles),
            "hidden_style_count": max(
                0, len(refreshed_catalog.styles) - len(previews)
            ),
            "used_table_styles": (
                [candidate_style_id]
                if candidate_activated and candidate_style_id is not None
                else [
                    str(value)
                    for value in source_manifest.get("used_table_styles", [])
                    if str(value) in refreshed_catalog.styles
                    and refreshed_catalog.styles[str(value)].style_type == "table"
                ]
            ),
            "preferred_table_style": (
                candidate_style_id
                if candidate_activated
                else source_manifest.get("preferred_table_style")
            ),
            "derivation": {
                "source_pack_id": source_manifest.get("id"),
                "source_format_fingerprint": source_manifest.get(
                    "format_fingerprint"
                ),
                "edited_styles": [
                    {
                        "style_id": str(edit["style_id"]),
                        "fields": sorted(
                            key for key in edit if key != "style_id"
                        ),
                    }
                    for edit in edits
                ],
            },
            "privacy": {
                "source_path_stored": False,
                "source_file_name_stored": False,
                "source_text_stored": False,
                "source_media_stored": False,
                "embedded_fonts_stored": False,
                "generic_samples_only": True,
                "display_name_derived_from_source": (
                    False
                    if display_name is not None
                    else source_name_derived
                ),
                "derived_without_source_document": True,
            },
        }
    )
    if refreshed_candidate is not None and not candidate_activated:
        derived_manifest["table_style_edit_candidate"] = refreshed_candidate
    preferred_table = derived_manifest.get("preferred_table_style")
    if (
        not preferred_table
        or str(preferred_table) not in refreshed_catalog.styles
        or refreshed_catalog.styles[str(preferred_table)].style_type != "table"
    ):
        derived_manifest["preferred_table_style"] = refreshed_catalog.fallback(
            "table"
        )
    return _write_style_pack_archive(
        output_path,
        derived_manifest,
        entries,
        force=force,
    )


def apply_style_pack(
    pack_path: Path,
    target: Path,
    output: Path,
    force: bool = False,
    preserve_page_layout: bool = False,
    demote_headings: bool = False,
) -> Tuple[Dict[str, object], core.TransferStats]:
    manifest, source_entries = load_style_pack(pack_path)
    target = target.expanduser().resolve()
    output = output.expanduser().resolve()
    if target.suffix.lower() not in core.TARGET_SUFFIXES:
        raise core.TransferError("内容目标文件只支持 .docx 或 .docm。")
    if output.suffix.lower() != target.suffix.lower():
        raise core.TransferError("输出扩展名必须与目标文件一致。")
    if output == target:
        raise core.TransferError("为保护原文件，输出位置不能覆盖目标文件。")
    if output.exists() and not force:
        raise core.TransferError("输出文件已存在。")

    source_entries = dict(source_entries)
    source_entries["word/document.xml"] = _placeholder_document()
    target_package = core.load_package(target, "内容目标文件")
    target_entries = dict(target_package.entries)
    target_catalog = core.build_style_catalog(
        target_entries["word/styles.xml"], target_entries["word/document.xml"]
    )

    used_table_styles = {
        str(value) for value in manifest.get("used_table_styles", [])
    }
    preserve_target_tables = not used_table_styles
    if preserve_target_tables:
        core.merge_target_table_style_system(source_entries, target_entries)

    source_catalog = core.build_style_catalog(
        source_entries["word/styles.xml"], source_entries["word/document.xml"]
    )
    source_catalog.used_paragraph_styles = {
        str(item.get("style_id"))
        for item in manifest.get("used_formats", [])
        if isinstance(item, dict) and item.get("type") == "paragraph"
    }
    heading_numbering = core.heading_numbering_from_manifest(
        manifest.get("heading_numbering"),
        source_entries,
        source_catalog,
    )
    if "heading_numbering" not in manifest:
        legacy_heading_ids = {
            str(item.get("style_id"))
            for item in manifest.get("used_formats", [])
            if isinstance(item, dict)
            and item.get("type") == "paragraph"
            and item.get("outline_level") is not None
        }
        heading_numbering = core.infer_heading_numbering_rules(
            source_entries, source_catalog, legacy_heading_ids
        )
    raw_authorities = manifest.get("heading_authorities")
    heading_authorities: Dict[int, str] = {}
    if isinstance(raw_authorities, dict):
        for raw_level, raw_style_id in raw_authorities.items():
            try:
                level = int(str(raw_level))
            except ValueError:
                continue
            style_id = str(raw_style_id)
            if (
                0 <= level <= 8
                and style_id in source_catalog.styles
                and source_catalog.resolved_outline.get(style_id) == level
            ):
                heading_authorities[level] = style_id
    if not heading_authorities:
        # Compatibility for v2.1 packs: actual styles remain authoritative.
        # Re-importing the source in v2.2+ is still required to persist/show
        # inferred H4/H5 cards, but legacy packs will never prefer an unused
        # same-name heading over a real custom outline style.
        for item in manifest.get("used_formats", []):
            if not isinstance(item, dict) or item.get("type") != "paragraph":
                continue
            raw_level = item.get("outline_level")
            if not isinstance(raw_level, int) or isinstance(raw_level, bool):
                continue
            style_id = str(item.get("style_id"))
            if style_id in source_catalog.styles:
                heading_authorities.setdefault(raw_level, style_id)
    source_catalog.authoritative_heading_by_level = heading_authorities
    used_paragraph_style_ids = set(source_catalog.used_paragraph_styles)
    inferred_heading_by_level: Dict[int, str] = {}
    for item in manifest.get("used_formats", []):
        if not isinstance(item, dict) or item.get("inferred") is not True:
            continue
        raw_level = item.get("outline_level")
        style_id = str(item.get("style_id", ""))
        if (
            isinstance(raw_level, int)
            and not isinstance(raw_level, bool)
            and 3 <= raw_level <= 8
            and heading_authorities.get(raw_level) == style_id
        ):
            inferred_heading_by_level[raw_level] = style_id

    runtime_inferred_headings: Dict[int, str] = {}
    runtime_completion_warnings: List[str] = []
    if demote_headings:
        target_heading_by_level = core.collect_used_heading_styles(
            target_entries,
            target_catalog,
            part_names=("word/document.xml",),
        )
        desired_heading_levels = {
            min(8, level + 1) for level in target_heading_by_level
        }
        missing_heading_levels = sorted(
            desired_heading_levels.difference(heading_authorities)
        )
        if missing_heading_levels and max(missing_heading_levels) >= 3:
            completion = core.complete_heading_hierarchy(
                source_entries,
                source_catalog,
                heading_authorities,
                heading_numbering,
                max_level=max(missing_heading_levels),
                extend_numbering=False,
            )
            runtime_inferred_headings.update(completion.inferred_styles)
            runtime_completion_warnings.extend(completion.warnings)
            heading_authorities.update(completion.inferred_styles)
            inferred_heading_by_level.update(completion.inferred_styles)
            used_paragraph_style_ids.update(completion.inferred_styles.values())
            if completion.inferred_styles:
                source_catalog = core.build_style_catalog(
                    source_entries["word/styles.xml"],
                    source_entries["word/document.xml"],
                )
                source_catalog.used_paragraph_styles = set(
                    used_paragraph_style_ids
                )
                source_catalog.authoritative_heading_by_level = dict(
                    heading_authorities
                )
        unresolved = sorted(
            desired_heading_levels.difference(heading_authorities)
        )
        if unresolved:
            raise core.TransferError(
                "当前格式库无法生成%s，不能安全地把全部标题下调一级；"
                "请重新导入连续设置了标题一、标题二、标题三的模板。"
                % "、".join("标题%d" % (level + 1) for level in unresolved)
            )

    runtime_numbering_repaired = False
    runtime_numbering_warning: Optional[str] = None
    base_runtime_rules = [
        heading_numbering.get(heading_authorities.get(level, ""))
        for level in (0, 1, 2)
    ]
    needs_runtime_repair = (
        all(rule is not None for rule in base_runtime_rules)
        and (
            len({rule.num_id for rule in base_runtime_rules if rule is not None}) > 1
            or bool(inferred_heading_by_level)
        )
    )
    if needs_runtime_repair:
        original_manifest_rules = core.heading_numbering_manifest(
            heading_numbering
        )
        repaired_rules, _extended, repair_warning = core._extend_heading_numbering(
            source_entries,
            heading_authorities,
            inferred_heading_by_level,
            heading_numbering,
        )
        if core.heading_numbering_manifest(repaired_rules) != original_manifest_rules:
            heading_numbering = repaired_rules
            runtime_numbering_repaired = True
        elif repair_warning:
            runtime_numbering_warning = repair_warning
    used_heading_style_ids = set(heading_authorities.values())
    core.align_heading_style_numbering(
        source_entries, used_heading_style_ids, heading_numbering
    )
    heading_paragraph_indents = core.heading_paragraph_indents_from_manifest(
        manifest.get("heading_paragraph_indents"), source_catalog
    )
    for level, style_id in sorted(runtime_inferred_headings.items()):
        parent_style_id = heading_authorities.get(level - 1)
        if parent_style_id in heading_paragraph_indents:
            heading_paragraph_indents[style_id] = dict(
                heading_paragraph_indents[parent_style_id]
            )
    source_catalog.used_table_styles = used_table_styles
    preferred_table = manifest.get("preferred_table_style")
    source_catalog.preferred_table_style = (
        None
        if preserve_target_tables
        else str(preferred_table)
        if preferred_table
        else source_catalog.fallback("table")
    )
    table_no_indent_styles = core.ensure_table_no_first_line_indent_styles(
        source_entries,
        source_catalog,
    )
    if table_no_indent_styles:
        source_catalog = core.build_style_catalog(
            source_entries["word/styles.xml"],
            source_entries["word/document.xml"],
        )
        source_catalog.used_paragraph_styles = (
            set(used_paragraph_style_ids)
            | set(table_no_indent_styles.values())
        )
        source_catalog.authoritative_heading_by_level = dict(
            heading_authorities
        )
        source_catalog.used_table_styles = used_table_styles
        source_catalog.preferred_table_style = (
            None
            if preserve_target_tables
            else str(preferred_table)
            if preferred_table
            else source_catalog.fallback("table")
        )
    layouts = [] if preserve_page_layout else _decode_layouts(manifest)

    stats = core.TransferStats()
    core.materialize_target_body_numbering(target_entries, target_catalog, stats)
    body_numbering = core.merge_target_body_numbering(
        source_entries, target_entries, stats, target_catalog
    )
    stats.warnings.extend(body_numbering.warnings)
    if preserve_target_tables:
        stats.warnings.append(
            "格式库未包含实际使用的表格样式，已保留目标文档的表格外观，并取消表格单元格中的两字符首行缩进。"
        )
    raw_numbering_conflicts = manifest.get("heading_numbering_conflicts", [])
    numbering_conflicts = (
        [str(value) for value in raw_numbering_conflicts]
        if isinstance(raw_numbering_conflicts, list)
        else []
    )
    if numbering_conflicts:
        stats.warnings.append(
            "部分标题样式使用了多套编号实例，已采用最常用规则：%s。"
            % "、".join(numbering_conflicts)
        )
    if runtime_numbering_repaired:
        stats.warnings.append(
            "已校准智能补全标题的多级编号与序号字体。"
            if inferred_heading_by_level
            else "已统一分散保存的标题多级编号。"
        )
    elif runtime_numbering_warning:
        stats.warnings.append(runtime_numbering_warning)
    raw_completion_warnings = manifest.get("heading_completion_warnings", [])
    if isinstance(raw_completion_warnings, list):
        for value in raw_completion_warnings:
            warning = str(value)
            if runtime_numbering_repaired and "编号规则不一致" in warning:
                continue
            stats.warnings.append(warning)
    stats.warnings.extend(runtime_completion_warnings)
    if "heading_paragraph_indents" not in manifest and heading_numbering:
        stats.warnings.append(
            "此格式库由旧版本创建，未保存标题段落实际缩进；"
            "如需精确复制标题 Left、首行和悬挂，请用当前版本重新导入一次格式源。"
        )
    for name in sorted(list(target_entries)):
        if not core.is_content_part(name):
            continue
        target_entries[name] = core.clean_content_xml(
            target_entries[name],
            name,
            target_catalog,
            source_catalog,
            layouts,
            stats,
            heading_numbering=heading_numbering,
            heading_paragraph_indents=heading_paragraph_indents,
            heading_level_shift=(
                1
                if demote_headings and name == "word/document.xml"
                else 0
            ),
            table_no_indent_styles=table_no_indent_styles,
            body_numbering_map=body_numbering.num_id_map,
        )
        stats.content_parts_cleaned += 1

    if stats.heading_level9_unchanged:
        stats.warnings.append(
            "Word 最多支持标题9；正文中的 %d 个标题9已保持原级别。"
            % stats.heading_level9_unchanged
        )

    if stats.body_list_paragraphs_preserved:
        inherited_detail = (
            "，其中 %d 个来自目标段落样式继承"
            % stats.style_list_paragraphs_materialized
            if stats.style_list_paragraphs_materialized
            else ""
        )
        stats.warnings.append(
            "已保留目标文档中的 %d 个普通编号或项目符号段落%s，"
            "并隔离导入 %d 个列表实例以避免与模板编号冲突。"
            % (
                stats.body_list_paragraphs_preserved,
                inherited_detail,
                stats.target_numbering_definitions_imported,
            )
        )

    core.set_heading_numbering_start_override(
        source_entries,
        heading_numbering,
        stats.heading_numbering_start,
    )

    if "word/settings.xml" in source_entries and "word/settings.xml" in target_entries:
        target_entries["word/settings.xml"] = core.merge_settings(
            source_entries["word/settings.xml"],
            target_entries["word/settings.xml"],
            stats,
            preserve_target_table_default=preserve_target_tables,
        )

    core.transfer_format_parts(source_entries, target_entries, stats)
    core.write_package(target_package, target_entries, output)
    return manifest, stats


def list_library(library_dir: Path) -> Dict[str, object]:
    library_dir = library_dir.expanduser().resolve()
    library_dir.mkdir(parents=True, exist_ok=True)
    packs: List[Dict[str, object]] = []
    errors: List[Dict[str, str]] = []
    for path in sorted(library_dir.glob("*%s" % PACK_SUFFIX)):
        try:
            manifest, _entries = load_style_pack(path)
            packs.append(manifest)
        except core.TransferError as exc:
            errors.append({"path": str(path), "error": str(exc)})
    packs.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return {"packs": packs, "errors": errors}


def _json_result(payload: Dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _read_edits_payload(
    edits_json: Optional[str], edits_file: Optional[str]
) -> object:
    if edits_file is not None:
        path = Path(edits_file).expanduser().resolve()
        if not path.is_file():
            raise core.TransferError("格式编辑请求文件不存在：%s" % path)
        if path.stat().st_size > 1024 * 1024:
            raise core.TransferError("格式编辑请求文件过大。")
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise core.TransferError("无法读取格式编辑请求：%s" % exc) from exc
    else:
        raw = edits_json or ""
    if len(raw.encode("utf-8")) > MAX_EDITS_JSON_BYTES:
        raise core.TransferError("格式编辑请求超过 1 MB，已停止读取。")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise core.TransferError("格式编辑请求不是有效 JSON：%s" % exc) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Forma 赋式｜格式方案管理")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--source", required=True)

    create_parser = subparsers.add_parser("create-pack")
    create_parser.add_argument("--source", required=True)
    create_parser.add_argument("--out", required=True)
    create_parser.add_argument("--name")
    create_parser.add_argument("--force", action="store_true")

    derive_parser = subparsers.add_parser("derive-pack")
    derive_parser.add_argument("--pack", required=True)
    derive_parser.add_argument("--out", required=True)
    derive_parser.add_argument("--name")
    edits_group = derive_parser.add_mutually_exclusive_group(required=True)
    edits_group.add_argument("--edits-json")
    edits_group.add_argument("--edits-file")
    derive_parser.add_argument("--force", action="store_true")

    info_parser = subparsers.add_parser("pack-info")
    info_parser.add_argument("--pack", required=True)

    list_parser = subparsers.add_parser("list-library")
    list_parser.add_argument("--dir", required=True)

    apply_parser = subparsers.add_parser("apply-pack")
    apply_parser.add_argument("--pack", required=True)
    apply_parser.add_argument("--target", required=True)
    apply_parser.add_argument("--out", required=True)
    apply_parser.add_argument("--force", action="store_true")
    apply_parser.add_argument("--preserve-page-layout", action="store_true")
    apply_parser.add_argument("--demote-headings", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            _package, _catalog, manifest = inspect_source(Path(args.source))
            _json_result({"ok": True, "pack": manifest})
        elif args.command == "create-pack":
            manifest = create_style_pack(
                Path(args.source),
                Path(args.out),
                display_name=args.name,
                force=args.force,
            )
            _json_result({"ok": True, "pack": manifest})
        elif args.command == "derive-pack":
            manifest = derive_style_pack(
                Path(args.pack),
                Path(args.out),
                _read_edits_payload(args.edits_json, args.edits_file),
                display_name=args.name,
                force=args.force,
            )
            _json_result({"ok": True, "pack": manifest})
        elif args.command == "pack-info":
            manifest, _entries = load_style_pack(Path(args.pack))
            _json_result({"ok": True, "pack": manifest})
        elif args.command == "list-library":
            result = list_library(Path(args.dir))
            _json_result({"ok": True, **result})
        elif args.command == "apply-pack":
            manifest, stats = apply_style_pack(
                Path(args.pack),
                Path(args.target),
                Path(args.out),
                force=args.force,
                preserve_page_layout=args.preserve_page_layout,
                demote_headings=args.demote_headings,
            )
            _json_result(
                {
                    "ok": True,
                    "output": str(Path(args.out).expanduser().resolve()),
                    "pack": manifest,
                    "stats": core.asdict(stats),
                }
            )
        else:  # pragma: no cover
            parser.error("unknown command")
    except core.TransferError as exc:
        _json_result({"ok": False, "error": str(exc)})
        return 2
    except Exception as exc:  # last-resort guard for GUI process calls
        _json_result({"ok": False, "error": "未预期错误：%s" % exc})
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
