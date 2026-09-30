#!/usr/bin/env python3
"""Persistent, privacy-conscious style packs for Forma Fushi.

The pack stores only allow-listed Word formatting XML plus a JSON manifest.
It never retains source body/story text, pictures, macros, embedded fonts, or
other document-owned binary objects.  UI samples are generated locally.

[INPUT]: 依赖 __future__, argparse, base64, copy, hashlib, io, json, math, os, re, sys, tempfile, unicodedata, uuid, zipfile, collections, datetime, pathlib, typing, lxml, word_style_transfer
[OUTPUT] Format-only packs, read-only preflights, atomic derived/document outputs
[POS] Persistent format-library trust boundary and application command interface
[PROTOCOL] Keep this header and the project indexes synchronized after edits.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import io
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
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
MAX_FONT_ALIASES_PER_FORMAT = 64
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
A = {"a": A_NS}

FORMAT_ROOT_TAGS = {
    "styles": core.qn(core.W_NS, "styles"),
    "stylesWithEffects": core.qn(core.W_NS, "styles"),
    "theme": core.qn(A_NS, "theme"),
    "fontTable": core.qn(core.W_NS, "fonts"),
    "numbering": core.qn(core.W_NS, "numbering"),
}
FORMAT_CONTENT_TYPES = {
    "styles": "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml",
    "stylesWithEffects": "application/vnd.ms-word.stylesWithEffects+xml",
    "theme": "application/vnd.openxmlformats-officedocument.theme+xml",
    "fontTable": "application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml",
    "numbering": "application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml",
    "settings": "application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml",
}
FORBIDDEN_FORMAT_TAGS = {
    core.qn(core.W_NS, name)
    for name in (
        "embedRegular", "embedBold", "embedItalic", "embedBoldItalic",
        "numPicBullet", "lvlPicBulletId", "drawing", "pict", "object",
        "altChunk", "document", "body", "p", "r", "t", "instrText", "tbl",
    )
} | {core.qn(A_NS, "blip"), core.qn(A_NS, "blipFill")}


def _validate_format_xml_hooks(root: etree._Element, label: str) -> None:
    """Reject data-bearing nodes and relationship attributes at every depth."""
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        if node.tag in FORBIDDEN_FORMAT_TAGS:
            raise core.TransferError("格式库包含非格式内容或二进制挂钩：%s。" % label)
        if any(attribute.startswith("{%s}" % core.R_NS) for attribute in node.attrib):
            raise core.TransferError("格式库包含不允许的关系挂钩：%s。" % label)


def _validate_format_entries(entries: Dict[str, bytes]) -> None:
    """Reconstruct the exact format-only part set independently of checksums.

    A checksum is corruption detection, not permission to add another package
    graph.  Never follow a format part's own .rels or trust relationship tails.
    """
    rel_path = "word/_rels/document.xml.rels"
    root = core.parse_xml(entries[rel_path], rel_path)
    if root.tag != core.qn(core.PKG_REL_NS, "Relationships"):
        raise core.TransferError("格式库主关系根节点无效。")
    expected = {"[Content_Types].xml", rel_path}
    roles: Dict[str, str] = {}
    ids: Set[str] = set()
    type_roles = {_relationship_type_for_role(role): role for role in core.ROLE_NAMES}
    for rel in root:
        if rel.tag != core.qn(core.PKG_REL_NS, "Relationship"):
            raise core.TransferError("格式库包含未知主关系节点。")
        if set(rel.attrib).difference({"Id", "Type", "Target", "TargetMode"}):
            raise core.TransferError("格式库主关系属性无效。")
        role = type_roles.get(rel.get("Type", ""))
        rel_id = rel.get("Id", "")
        target = rel.get("Target", "")
        if not role or not rel_id or not target:
            raise core.TransferError("格式库包含不允许的主关系。")
        if rel.get("TargetMode") not in {None, "Internal"}:
            raise core.TransferError("格式库不能包含外部关系。")
        if role in roles or rel_id in ids:
            raise core.TransferError("格式库包含重复的格式角色或关系 ID。")
        # URI fragments, queries and backslashes are never package part paths.
        if any(character in target for character in ("\\", "#", "?", ":", "%")):
            raise core.TransferError("格式库关系路径无效。")
        part = core.resolve_relationship_target("word/document.xml", target)
        if not part.startswith("word/") or not part.endswith(".xml") or "/_rels/" in part:
            raise core.TransferError("格式库格式关系只能指向 Word XML 部件。")
        if part in expected:
            raise core.TransferError("格式库多个角色指向同一部件。")
        if part not in entries:
            raise core.TransferError("格式库关系指向缺失部件：%s。" % part)
        part_root = core.parse_xml(entries[part], part)
        if part_root.tag != FORMAT_ROOT_TAGS[role]:
            raise core.TransferError("格式库部件角色或 XML 命名空间无效：%s。" % part)
        _validate_format_xml_hooks(part_root, part)
        roles[role] = part
        expected.add(part)
        ids.add(rel_id)
    if roles.get("styles") != "word/styles.xml":
        raise core.TransferError("格式库缺少规范主样式关系。")
    if "word/settings.xml" in entries:
        expected.add("word/settings.xml")
        settings = core.parse_xml(entries["word/settings.xml"], "settings.xml")
        if settings.tag != core.qn(core.W_NS, "settings"):
            raise core.TransferError("格式库设置根节点无效。")
        if any(child.tag not in {core.qn(core.W_NS, tag) for tag in core.SETTINGS_FORMAT_TAGS} for child in settings):
            raise core.TransferError("格式库设置包含不允许的标签。")
        _validate_format_xml_hooks(settings, "settings.xml")
    unknown = set(entries).difference(expected)
    if unknown:
        raise core.TransferError("格式库包含非白名单部件：%s。" % "、".join(sorted(unknown)))
    content_types = core.parse_xml(entries["[Content_Types].xml"], "[Content_Types].xml")
    if content_types.tag != core.qn(core.CT_NS, "Types"):
        raise core.TransferError("格式库内容类型根节点无效。")
    role_by_part = {part: role for role, part in roles.items()}
    role_by_part["word/settings.xml"] = "settings"
    seen_types: Set[Tuple[str, str]] = set()
    for child in content_types:
        if child.tag == core.qn(core.CT_NS, "Default"):
            extension = child.get("Extension", "").casefold()
            allowed_type = (
                {"application/xml", "text/xml"} if extension == "xml"
                else {"application/vnd.openxmlformats-package.relationships+xml"} if extension == "rels"
                else set()
            )
            identity = ("Default", extension)
            valid = set(child.attrib) == {"Extension", "ContentType"} and child.get("ContentType") in allowed_type
        elif child.tag == core.qn(core.CT_NS, "Override"):
            part = child.get("PartName", "").removeprefix("/")
            role = role_by_part.get(part)
            identity = ("Override", part)
            valid = (
                set(child.attrib) == {"PartName", "ContentType"}
                and child.get("PartName") == "/" + part
                and role is not None
                and child.get("ContentType") == FORMAT_CONTENT_TYPES[role]
            )
        else:
            raise core.TransferError("格式库包含未知内容类型节点。")
        if not valid or identity in seen_types or len(child):
            raise core.TransferError("格式库内容类型声明无效或重复。")
        seen_types.add(identity)


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


def _hundredths_to_units(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(int(value) / 100.0, 2)
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


def _east_asian_theme_script(language: Optional[str]) -> Optional[str]:
    """Map a themeFontLang BCP-47 value to a DrawingML script tag."""
    if not language:
        return None
    subtags = [
        value.casefold()
        for value in language.replace("_", "-").split("-")
        if value
    ]
    if not subtags:
        return None
    primary = subtags[0]
    if primary == "ja":
        return "Jpan"
    if primary == "ko":
        return "Hang"
    if primary != "zh":
        return None
    if "hant" in subtags or any(
        region in subtags for region in ("tw", "hk", "mo")
    ):
        return "Hant"
    if "hans" in subtags or any(
        region in subtags for region in ("cn", "sg")
    ):
        return "Hans"
    # Word's unqualified zh theme language conventionally denotes simplified
    # Chinese.  Keeping that deterministic is preferable to using the Mac UI
    # locale, which would make a saved format pack machine-dependent.
    return "Hans"


def _theme_font_language(entries: Dict[str, bytes]) -> Optional[str]:
    settings = entries.get("word/settings.xml")
    if settings is None:
        return None
    root = core.parse_xml(settings, "settings.xml")
    node = root.find("w:themeFontLang", namespaces=core.NS)
    if node is None:
        return None
    return (
        node.get(core.qn(core.W_NS, "eastAsia"))
        or node.get(core.qn(core.W_NS, "val"))
    )


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

    east_asian_script = _east_asian_theme_script(
        _theme_font_language(entries)
    )
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
        supplemental_fonts: Dict[str, str] = {}
        for supplemental in group.findall("a:font", namespaces=A):
            script = supplemental.get("script", "")
            typeface = supplemental.get("typeface", "")
            if script and typeface:
                supplemental_fonts[script] = typeface
        fonts["%sHAnsi" % group_name] = latin_name
        fonts["%sAscii" % group_name] = latin_name
        east_asian_name = (
            supplemental_fonts.get(east_asian_script or "", "")
            or east_name
            # Preserve the historical deterministic fallback for old packs
            # whose settings omit themeFontLang, while preferring an explicit
            # language-specific supplemental face whenever one is available.
            or supplemental_fonts.get("Hans", "")
            or supplemental_fonts.get("Hant", "")
            or latin_name
        )
        fonts["%sEastAsia" % group_name] = east_asian_name

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


def _font_alias_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value.strip()).casefold()


def _font_aliases(entries: Dict[str, bytes]) -> Dict[str, List[str]]:
    """Return a case-insensitive, bidirectional fontTable alias index."""
    _rels, roles = core.collect_format_relationships(entries)
    record = roles.get("fontTable")
    part_name = (
        record[0]
        if record is not None
        else core.ROLE_FALLBACK_PARTS["fontTable"]
    )
    if part_name not in entries:
        return {}
    root = core.parse_xml(entries[part_name], part_name)

    # Font-table records can overlap (an alternate name in one record can be
    # the primary name in another), so build connected components instead of
    # a one-way primary-name dictionary.
    graph: Dict[str, Set[str]] = {}
    display_names: Dict[str, str] = {}

    def add_name(raw: Optional[str]) -> Optional[str]:
        if raw is None:
            return None
        name = raw.strip()
        if (
            not name
            or len(name) > 1024
            or any(ord(character) < 32 or ord(character) == 127 for character in name)
        ):
            return None
        key = _font_alias_key(name)
        graph.setdefault(key, set())
        display_names.setdefault(key, name)
        return key

    for font in root.findall("w:font", namespaces=core.NS):
        primary_key = add_name(font.get(core.qn(core.W_NS, "name")))
        if primary_key is None:
            continue
        alternate = font.find("w:altName", namespaces=core.NS)
        raw_alternate = (
            alternate.get(core.qn(core.W_NS, "val"))
            if alternate is not None
            else None
        )
        alias_key = add_name(raw_alternate)
        if alias_key is None or alias_key == primary_key:
            continue
        graph[primary_key].add(alias_key)
        graph[alias_key].add(primary_key)

    result: Dict[str, List[str]] = {}
    visited: Set[str] = set()
    for start in graph:
        if start in visited:
            continue
        stack = [start]
        component: List[str] = []
        visited.add(start)
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in graph[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        if len(component) < 2:
            continue
        ordered = sorted(
            component,
            key=lambda key: (display_names[key].casefold(), display_names[key]),
        )
        for key in ordered:
            result[key] = [
                display_names[other]
                for other in ordered
                if other != key
            ][:MAX_FONT_ALIASES_PER_FORMAT]
    return result


def _effective_style_fonts(
    style_id: str,
    catalog: core.StyleCatalog,
    styles_root: etree._Element,
    theme: Dict[str, Dict[str, str]],
) -> Tuple[Optional[str], Optional[str]]:
    """Resolve fonts level-by-level without leaking lower-level theme refs."""
    style_nodes = {
        node.get(core.qn(core.W_NS, "styleId")): node
        for node in styles_root.findall("w:style", namespaces=core.NS)
        if node.get(core.qn(core.W_NS, "styleId"))
    }
    run_property_levels: List[Optional[etree._Element]] = [
        styles_root.find(
            "w:docDefaults/w:rPrDefault/w:rPr", namespaces=core.NS
        )
    ]
    run_property_levels.extend(
        style_nodes[chain_item.style_id].find("w:rPr", namespaces=core.NS)
        for chain_item in _style_chain(style_id, catalog)
        if chain_item.style_id in style_nodes
    )

    font_latin: Optional[str] = None
    font_east_asia: Optional[str] = None
    theme_fonts = theme.get("fonts", {})
    for run_properties in run_property_levels:
        if run_properties is None:
            continue
        rfonts = run_properties.find("w:rFonts", namespaces=core.NS)
        if rfonts is None:
            continue

        explicit_latin = (
            rfonts.get(core.qn(core.W_NS, "ascii"))
            or rfonts.get(core.qn(core.W_NS, "hAnsi"))
        )
        latin_theme_key = (
            rfonts.get(core.qn(core.W_NS, "asciiTheme"))
            or rfonts.get(core.qn(core.W_NS, "hAnsiTheme"))
        )
        if latin_theme_key is not None:
            font_latin = theme_fonts.get(latin_theme_key) or explicit_latin
        elif explicit_latin is not None:
            font_latin = explicit_latin

        explicit_east_asia = rfonts.get(core.qn(core.W_NS, "eastAsia"))
        east_asia_theme_key = rfonts.get(
            core.qn(core.W_NS, "eastAsiaTheme")
        )
        if east_asia_theme_key is not None:
            font_east_asia = (
                theme_fonts.get(east_asia_theme_key) or explicit_east_asia
            )
        elif explicit_east_asia is not None:
            font_east_asia = explicit_east_asia
    return font_latin, font_east_asia


def _merge_property_children(
    destination: Dict[str, etree._Element],
    parent: Optional[etree._Element],
) -> None:
    if parent is None:
        return
    for child in parent:
        key = etree.QName(child).localname
        if key == "ind":
            destination[key] = core.merge_style_hierarchy_indentation(
                destination.get(key), child
            )
        elif key in {"rFonts", "spacing"} and key in destination:
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
    font_aliases: Optional[Dict[str, List[str]]] = None,
    numbering_rule: Optional[core.HeadingNumberingRule] = None,
    inferred: bool = False,
    inference_label: Optional[str] = None,
    paragraph_override: Optional[Dict[str, object]] = None,
    numbering_restart: Optional[bool] = None,
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

    if paragraph_override:
        override_properties = etree.Element(core.qn(core.W_NS, "pPr"))
        raw_indent = paragraph_override.get("ind")
        if isinstance(raw_indent, dict) and raw_indent:
            indentation = etree.SubElement(
                override_properties, core.qn(core.W_NS, "ind")
            )
            for attribute in core.HEADING_INDENT_ATTRIBUTES:
                value = raw_indent.get(attribute)
                if value is not None:
                    indentation.set(core.qn(core.W_NS, attribute), str(value))
        raw_spacing = paragraph_override.get("spacing")
        if isinstance(raw_spacing, dict) and raw_spacing:
            spacing_node = etree.SubElement(
                override_properties, core.qn(core.W_NS, "spacing")
            )
            for attribute in core.HEADING_SPACING_ATTRIBUTES:
                value = raw_spacing.get(attribute)
                if value is not None:
                    spacing_node.set(core.qn(core.W_NS, attribute), str(value))
        alignment = paragraph_override.get("jc")
        if isinstance(alignment, str):
            alignment_node = etree.SubElement(
                override_properties, core.qn(core.W_NS, "jc")
            )
            alignment_node.set(core.qn(core.W_NS, "val"), alignment)
        _merge_property_children(paragraph_properties, override_properties)

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

    font_latin, font_east_asia = _effective_style_fonts(
        style_id, catalog, styles_root, theme
    )

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
                line_rule = line_rule or "auto"
                line_spacing = (
                    round(int(raw_line) / 240.0, 2)
                    if line_rule == "auto"
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
    indentation = paragraph_properties.get("ind")

    def indent_attribute(*names: str) -> Optional[str]:
        if indentation is None:
            return None
        for name in names:
            value = indentation.get(core.qn(core.W_NS, name))
            if value is not None:
                return value
        return None

    def horizontal_indent(
        point_names: Sequence[str], character_names: Sequence[str]
    ) -> Tuple[Optional[float], Optional[float]]:
        character_value = indent_attribute(*character_names)
        if character_value is not None:
            # OOXML character-unit attributes take precedence over their
            # twip counterparts.  Hide the neutralising twip zero written by
            # the editor so callers never round-trip both units at once.
            return None, _hundredths_to_units(character_value)
        return _twips_to_pt(indent_attribute(*point_names)), None

    left_indent_pt, left_indent_chars = horizontal_indent(
        ("start", "left"), ("startChars", "leftChars")
    )
    right_indent_pt, right_indent_chars = horizontal_indent(
        ("end", "right"), ("endChars", "rightChars")
    )

    first_line_indent_pt, first_line_indent_chars = horizontal_indent(
        ("firstLine",), ("firstLineChars",)
    )
    hanging_indent_pt, hanging_indent_chars = horizontal_indent(
        ("hanging",), ("hangingChars",)
    )
    first_line_nonzero = any(
        value not in {None, 0.0}
        for value in (first_line_indent_pt, first_line_indent_chars)
    )
    hanging_nonzero = any(
        value not in {None, 0.0}
        for value in (hanging_indent_pt, hanging_indent_chars)
    )
    if hanging_nonzero:
        first_line_indent_pt = None
        first_line_indent_chars = None
    elif first_line_nonzero:
        hanging_indent_pt = None
        hanging_indent_chars = None
    elif first_line_indent_pt is not None or first_line_indent_chars is not None:
        hanging_indent_pt = None
        hanging_indent_chars = None

    outline_level = catalog.resolved_outline.get(style_id)
    numbering_example = _numbering_example(numbering_rule)

    preview: Dict[str, object] = {
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
        "left_indent_pt": left_indent_pt,
        "right_indent_pt": right_indent_pt,
        "first_line_indent_pt": first_line_indent_pt,
        "hanging_indent_pt": hanging_indent_pt,
        "left_indent_chars": left_indent_chars,
        "right_indent_chars": right_indent_chars,
        "first_line_indent_chars": first_line_indent_chars,
        "hanging_indent_chars": hanging_indent_chars,
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
        "numbering_start": numbering_rule.start if numbering_rule is not None else None,
        "numbering_restart": numbering_restart,
        "table_fill_hex": table_fill,
        "table_accent_hex": table_accent,
    }
    if style_node is not None and style_type == "table":
        border = style_node.find("w:tblPr/w:tblBorders/w:top", namespaces=core.NS)
        if border is not None:
            preview["table_border_style"] = border.get(core.qn(core.W_NS, "val"))
            preview["table_border_color_hex"] = _safe_hex(border.get(core.qn(core.W_NS, "color")))
            try:
                preview["table_border_width_pt"] = int(border.get(core.qn(core.W_NS, "sz"))) / 8.0
            except (TypeError, ValueError):
                pass
        for side in ("top", "bottom", "left", "right"):
            margin = style_node.find("w:tblPr/w:tblCellMar/w:%s" % side, namespaces=core.NS)
            if margin is not None and margin.get(core.qn(core.W_NS, "type"), "dxa") == "dxa":
                preview["table_cell_margin_%s_pt" % side] = _twips_to_pt(margin.get(core.qn(core.W_NS, "w")))
    aliases = font_aliases or {}
    if font_latin:
        latin_aliases = aliases.get(_font_alias_key(font_latin), [])
        if latin_aliases:
            preview["font_latin_aliases"] = list(latin_aliases)
    if font_east_asia:
        east_asia_aliases = aliases.get(
            _font_alias_key(font_east_asia), []
        )
        if east_asia_aliases:
            preview["font_east_asia_aliases"] = list(east_asia_aliases)
    return preview


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
    font_aliases = _font_aliases(entries)

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
    heading_paragraph_properties = core.collect_heading_paragraph_properties(
        entries,
        catalog,
        set(heading_numbering) | set(heading_authorities.values()),
        part_names=active_parts,
        inherited_style_ids=inferred_heading_styles.values(),
        heading_authorities=heading_authorities,
    )
    heading_paragraph_indents = {
        style_id: dict(indentation)
        for style_id, profile in heading_paragraph_properties.items()
        for indentation in [profile.get("ind")]
        if isinstance(indentation, dict)
    }

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
                    font_aliases=font_aliases,
                    numbering_rule=heading_numbering.get(style_id),
                    numbering_restart=_numbering_restarts(package.entries, heading_numbering.get(style_id)),
                    paragraph_override=heading_paragraph_properties.get(
                        style_id
                    ),
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
                font_aliases=font_aliases,
                numbering_rule=heading_numbering.get(style_id),
                numbering_restart=_numbering_restarts(package.entries, heading_numbering.get(style_id)),
                inferred=True,
                inference_label="智能补全",
                paragraph_override=heading_paragraph_properties.get(style_id),
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
                font_aliases=font_aliases,
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
        "heading_paragraph_properties": heading_paragraph_properties,
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
    if root.tag != FORMAT_ROOT_TAGS[role]:
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
    if source_root.tag != core.qn(core.W_NS, "settings"):
        raise core.TransferError("源设置部件命名空间无效。")
    target_root = etree.Element(source_root.tag, nsmap=source_root.nsmap)
    for child in source_root:
        if child.tag in {core.qn(core.W_NS, tag) for tag in core.SETTINGS_FORMAT_TAGS}:
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
        # Construct relationships from the collected role, not source XML.
        # Source .rels may contain extension attributes or external fallback
        # records which have no authority inside a portable format pack.
        rel = etree.SubElement(
            filtered_rels, core.qn(core.PKG_REL_NS, "Relationship")
        )
        rel.set("Id", "rIdFmtPack%d" % relationship_index)
        relationship_index += 1
        rel.set("Type", _relationship_type_for_role(role))
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


def pack_file_stem(display_name: Optional[str]) -> str:
    """把格式包的展示名收敛成两端通用、跨文件系统安全的文件名主干。

    命名规则由引擎统一决定，客户端不再各自拼接，否则 Mac 与 Windows 的
    格式库目录会长出两套互不兼容的文件名。
    """
    cleaned: List[str] = []
    for character in (display_name or "").strip():
        cleaned.append(character if character.isalnum() or character in "-_" else "-")
    stem = re.sub(r"-{2,}", "-", "".join(cleaned)).strip("-")
    return stem[:48] if stem else "word-format"


def allocate_pack_path(library_dir: Path, display_name: Optional[str]) -> Path:
    """在格式库目录里分配一个未占用的 .wfstyle 路径。"""
    library_dir = library_dir.expanduser().resolve()
    stem = pack_file_stem(display_name)
    while True:
        candidate = library_dir / (
            "%s-%s%s" % (stem, uuid.uuid4().hex, PACK_SUFFIX)
        )
        if not candidate.exists():
            return candidate


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

    for key in ("inferred", "configured", "bold", "italic", "numbering_restart"):
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
        "table_border_style",
        "table_border_color_hex",
    ):
        value = raw.get(key)
        if value is not None:
            _manifest_string(
                value, "%s.%s" % (field, key), maximum=1024,
                allow_empty=True,
            )
    for key, font_key in (
        ("font_latin_aliases", "font_latin"),
        ("font_east_asia_aliases", "font_east_asia"),
    ):
        if key not in raw:
            continue
        aliases = raw[key]
        _validate_font_alias_list(aliases, "%s.%s" % (field, key))
        effective_font = raw.get(font_key)
        if isinstance(effective_font, str) and any(
            _font_alias_key(alias) == _font_alias_key(effective_font)
            for alias in aliases
        ):
            raise core.TransferError(
                "格式库字段 %s.%s 不能重复主字体名称。" % (field, key)
            )
    for key in (
        "size_pt",
        "space_before_pt",
        "space_after_pt",
        "line_spacing",
        "left_indent_pt",
        "right_indent_pt",
        "first_line_indent_pt",
        "hanging_indent_pt",
        "left_indent_chars",
        "right_indent_chars",
        "first_line_indent_chars",
        "hanging_indent_chars",
        "table_border_width_pt",
        "table_cell_margin_top_pt",
        "table_cell_margin_bottom_pt",
        "table_cell_margin_left_pt",
        "table_cell_margin_right_pt",
    ):
        _manifest_optional_number(raw.get(key), "%s.%s" % (field, key))
    if raw.get("numbering_start") is not None:
        start = _manifest_nonnegative_int(raw["numbering_start"], "%s.numbering_start" % field)
        if start > 32767:
            raise core.TransferError("格式库编号起始值超出范围。")
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


def _validate_font_alias_list(value: object, field: str) -> None:
    if not isinstance(value, list):
        raise core.TransferError("格式库字段 %s 必须是文本数组。" % field)
    if len(value) > MAX_FONT_ALIASES_PER_FORMAT:
        raise core.TransferError(
            "格式库字段 %s 最多包含 %d 个字体别名。"
            % (field, MAX_FONT_ALIASES_PER_FORMAT)
        )
    seen: Set[str] = set()
    for index, item in enumerate(value):
        alias = _manifest_string(
            item, "%s[%d]" % (field, index), maximum=1024
        )
        key = _font_alias_key(alias)
        if key in seen:
            raise core.TransferError("格式库字段 %s 包含重复字体别名。" % field)
        seen.add(key)


def _validate_count_object(
    value: object, field: str, required_keys: Sequence[str]
) -> None:
    if not isinstance(value, dict):
        raise core.TransferError("格式库字段 %s 必须是对象。" % field)
    for key in required_keys:
        _manifest_nonnegative_int(value.get(key), "%s.%s" % (field, key))


def _validate_manifest_integer_text(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise core.TransferError(
            "格式库字段 %s 必须是整数文本。" % field
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise core.TransferError(
            "格式库字段 %s 必须是整数文本。" % field
        ) from exc
    if not -(2**31) <= parsed <= 2**31 - 1:
        raise core.TransferError("格式库字段 %s 超出整数范围。" % field)


def _validate_heading_indent_manifest(value: object, field: str) -> None:
    if not isinstance(value, dict) or not value:
        raise core.TransferError("格式库字段 %s 必须是非空对象。" % field)
    for raw_attribute, raw_value in value.items():
        attribute = _manifest_string(
            raw_attribute, "%s 键" % field, maximum=64
        )
        if attribute not in core.HEADING_INDENT_ATTRIBUTES:
            raise core.TransferError(
                "格式库字段 %s.%s 不受支持。" % (field, attribute)
            )
        _validate_manifest_integer_text(
            raw_value, "%s.%s" % (field, attribute)
        )


def _validate_heading_paragraph_properties_manifest(
    value: object, field: str
) -> None:
    if not isinstance(value, dict):
        raise core.TransferError("格式库字段 %s 必须是对象。" % field)
    for raw_style_id, raw_profile in value.items():
        style_id = _manifest_string(
            raw_style_id, "%s 样式 ID" % field, maximum=255
        )
        item_field = "%s.%s" % (field, style_id)
        if not isinstance(raw_profile, dict) or not raw_profile:
            raise core.TransferError(
                "格式库字段 %s 必须是非空对象。" % item_field
            )
        unknown = set(raw_profile).difference({"ind", "spacing", "jc"})
        if unknown:
            raise core.TransferError(
                "格式库字段 %s 包含未知属性：%s。"
                % (item_field, "、".join(sorted(str(key) for key in unknown)))
            )
        if "ind" in raw_profile:
            _validate_heading_indent_manifest(
                raw_profile["ind"], "%s.ind" % item_field
            )
        if "spacing" in raw_profile:
            raw_spacing = raw_profile["spacing"]
            spacing_field = "%s.spacing" % item_field
            if not isinstance(raw_spacing, dict) or not raw_spacing:
                raise core.TransferError(
                    "格式库字段 %s 必须是非空对象。" % spacing_field
                )
            for raw_attribute, raw_value in raw_spacing.items():
                attribute = _manifest_string(
                    raw_attribute, "%s 键" % spacing_field, maximum=64
                )
                item = "%s.%s" % (spacing_field, attribute)
                if attribute in core.HEADING_SPACING_INTEGER_ATTRIBUTES:
                    _validate_manifest_integer_text(raw_value, item)
                elif attribute in core.HEADING_SPACING_BOOLEAN_ATTRIBUTES:
                    if core._canonical_on_off_attribute(str(raw_value)) is None:
                        raise core.TransferError(
                            "格式库字段 %s 必须是开关值。" % item
                        )
                elif attribute == "lineRule":
                    line_rule = _manifest_string(
                        raw_value, item, maximum=16
                    )
                    if line_rule not in core.LINE_SPACING_RULES:
                        raise core.TransferError(
                            "格式库字段 %s 的行距规则无效。" % item
                        )
                else:
                    raise core.TransferError(
                        "格式库字段 %s 不受支持。" % item
                    )
        if "jc" in raw_profile:
            alignment = _manifest_string(
                raw_profile["jc"], "%s.jc" % item_field, maximum=64
            )
            if alignment not in core.PARAGRAPH_ALIGNMENT_VALUES:
                raise core.TransferError(
                    "格式库字段 %s.jc 的对齐方式无效。" % item_field
                )


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
    raw_heading_indents = manifest.get("heading_paragraph_indents")
    if isinstance(raw_heading_indents, dict):
        for raw_style_id, raw_indent in raw_heading_indents.items():
            style_id = _manifest_string(
                raw_style_id,
                "heading_paragraph_indents 样式 ID",
                maximum=255,
            )
            _validate_heading_indent_manifest(
                raw_indent,
                "heading_paragraph_indents.%s" % style_id,
            )
    if "heading_paragraph_properties" in manifest:
        _validate_heading_paragraph_properties_manifest(
            manifest["heading_paragraph_properties"],
            "heading_paragraph_properties",
        )
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


def load_style_pack(pack_path: Path, expected_sha256: Optional[str] = None) -> Tuple[Dict[str, object], Dict[str, bytes]]:
    pack_path = pack_path.expanduser().resolve()
    # Hash and parse the same bounded bytes.  Separate pathname hash/read
    # operations permit A -> B -> A substitution between the two checks.
    snapshot = core.read_package_snapshot(pack_path, "格式库", max_bytes=MAX_PACK_TOTAL_BYTES + 2 * 1024 * 1024, expected_sha256=expected_sha256)
    stream = io.BytesIO(snapshot)
    if not zipfile.is_zipfile(stream):
        raise core.TransferError("格式库不存在或已损坏：%s" % pack_path)
    with zipfile.ZipFile(stream, "r") as archive:
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
    _validate_format_entries(entries)
    # Section XML is stored in the manifest rather than the parts ZIP.  It
    # needs the same namespace and relationship checks before any application.
    _decode_layouts(manifest)
    manifest = dict(manifest)
    # Older schema-1 packs did not persist a fingerprint, but exchange must
    # still compare the verified formatting parts rather than a file name.
    manifest.setdefault("format_fingerprint", _format_fingerprint(actual_checksums))
    manifest["pack_path"] = str(pack_path)
    _synthesize_legacy_font_aliases(manifest, entries)
    _synthesize_legacy_table_edit_candidate(manifest, entries)
    if "heading_numbering_user_edits" in manifest:
        runtime_entries = dict(entries)
        runtime_entries["word/document.xml"] = _placeholder_document()
        catalog = core.build_style_catalog(runtime_entries["word/styles.xml"], runtime_entries["word/document.xml"])
        _numbering_user_edits(manifest, runtime_entries, catalog)
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
                if len(data) > MAX_PACK_MEMBER_BYTES:
                    raise core.TransferError("格式库页面设置过大。")
                node = core.parse_xml(data, "格式库页面设置")
                if node.tag not in {core.qn(core.W_NS, tag) for tag in core.SECTION_LAYOUT_TAGS}:
                    raise core.TransferError("格式库页面设置包含不允许的标签或命名空间。")
                _validate_format_xml_hooks(node, "页面设置")
                layout.append(node)
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
_PARAGRAPH_STYLE_EDIT_FIELDS = {
    "alignment",
    "space_before_pt",
    "space_after_pt",
    "line_spacing",
    "line_rule",
    "left_indent_pt",
    "right_indent_pt",
    "first_line_indent_pt",
    "hanging_indent_pt",
    "left_indent_chars",
    "right_indent_chars",
    "first_line_indent_chars",
    "hanging_indent_chars",
}
_NUMBERING_STYLE_EDIT_FIELDS = {
    "numbering_format", "numbering_pattern", "numbering_start", "numbering_restart",
}
NUMBERING_FORMATS = {
    "decimal", "decimalZero", "upperRoman", "lowerRoman", "upperLetter", "lowerLetter",
    "chineseCounting", "chineseCountingThousand", "chineseLegalSimplified", "ideographTraditional",
}
TABLE_BORDER_STYLES = {"nil", "none", "single", "double", "dotted", "dashed", "dotDash", "dotDotDash"}
_TABLE_STYLE_EDIT_FIELDS = {
    "table_fill_hex", "table_accent_hex", "table_border_style", "table_border_color_hex",
    "table_border_width_pt", *{"table_cell_margin_%s_pt" % side for side in ("top", "bottom", "left", "right")},
}
_STYLE_EDIT_FIELDS = (
    _RUN_STYLE_EDIT_FIELDS
    | _PARAGRAPH_STYLE_EDIT_FIELDS
    | _TABLE_STYLE_EDIT_FIELDS
    | _NUMBERING_STYLE_EDIT_FIELDS
)
_DERIVED_MANIFEST_COPY_FIELDS = {
    "heading_authorities",
    "heading_completion_warnings",
    "heading_numbering",
    "heading_numbering_user_edits",
    "heading_paragraph_indents",
    "heading_paragraph_properties",
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


def _validated_edit_number(
    value: object,
    label: str,
    minimum: float,
    maximum: float,
    step: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise core.TransferError(
            "%s必须是 %.2f–%.2f 之间的数字。" % (label, minimum, maximum)
        )
    try:
        parsed = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise core.TransferError(
            "%s必须是 %.2f–%.2f 之间的数字。" % (label, minimum, maximum)
        ) from exc
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        raise core.TransferError(
            "%s必须在 %.2f–%.2f 之间。" % (label, minimum, maximum)
        )
    steps = parsed / step
    if not math.isclose(steps, round(steps), abs_tol=1e-7):
        raise core.TransferError(
            "%s必须以 %.2f 为步进。" % (label, step)
        )
    return round(parsed, 8)


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
        if "table_border_color_hex" in raw_edit:
            edit["table_border_color_hex"] = _validated_edit_color(raw_edit["table_border_color_hex"], "表格边框颜色")
        if "table_border_style" in raw_edit:
            value = _validated_short_text(raw_edit["table_border_style"], "表格边框类型", maximum=32)
            if value not in TABLE_BORDER_STYLES:
                raise core.TransferError("表格边框类型不受支持。")
            edit["table_border_style"] = value
        if "table_border_width_pt" in raw_edit:
            edit["table_border_width_pt"] = _validated_edit_number(raw_edit["table_border_width_pt"], "表格边框宽度", 0.25, 12.0, 0.125)
        for side in ("top", "bottom", "left", "right"):
            field = "table_cell_margin_%s_pt" % side
            if field in raw_edit:
                edit[field] = _validated_edit_number(raw_edit[field], "表格单元格边距", 0.0, 1584.0, 0.05)
        if "numbering_format" in raw_edit:
            value = _validated_short_text(raw_edit["numbering_format"], "标题编号格式", maximum=32)
            if value not in NUMBERING_FORMATS:
                raise core.TransferError("标题编号格式不受支持。")
            edit["numbering_format"] = value
        if "numbering_pattern" in raw_edit:
            edit["numbering_pattern"] = _validated_short_text(raw_edit["numbering_pattern"], "标题编号模式", maximum=128)
        if "numbering_start" in raw_edit:
            value = raw_edit["numbering_start"]
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 32767:
                raise core.TransferError("标题编号起始值必须是 1–32767 之间的整数。")
            edit["numbering_start"] = value
        if "numbering_restart" in raw_edit:
            if not isinstance(raw_edit["numbering_restart"], bool):
                raise core.TransferError("标题编号重启设置必须是 true 或 false。")
            edit["numbering_restart"] = raw_edit["numbering_restart"]

        if "alignment" in raw_edit:
            alignment = _validated_short_text(
                raw_edit["alignment"], "段落对齐方式", maximum=32
            )
            if alignment not in core.PARAGRAPH_ALIGNMENT_VALUES:
                raise core.TransferError("段落对齐方式不受支持：%s。" % alignment)
            edit["alignment"] = alignment
        for field, label in (
            ("space_before_pt", "段前间距"),
            ("space_after_pt", "段后间距"),
        ):
            if field in raw_edit:
                edit[field] = _validated_edit_number(
                    raw_edit[field], label, 0.0, 1584.0, 0.05
                )

        has_line_spacing = "line_spacing" in raw_edit
        has_line_rule = "line_rule" in raw_edit
        if has_line_spacing != has_line_rule:
            raise core.TransferError("行距数值与行距规则必须同时提供。")
        if has_line_spacing:
            line_rule = _validated_short_text(
                raw_edit["line_rule"], "行距规则", maximum=16
            )
            if line_rule not in core.LINE_SPACING_RULES:
                raise core.TransferError(
                    "行距规则只支持 auto、exact 或 atLeast。"
                )
            if line_rule == "auto":
                line_spacing = _validated_edit_number(
                    raw_edit["line_spacing"],
                    "多倍行距",
                    0.5,
                    10.0,
                    0.01,
                )
            else:
                line_spacing = _validated_edit_number(
                    raw_edit["line_spacing"],
                    "固定行距",
                    1.0,
                    1584.0,
                    0.05,
                )
            edit["line_rule"] = line_rule
            edit["line_spacing"] = line_spacing

        point_indent_fields = (
            ("left_indent_pt", "左缩进", -1584.0, 1584.0),
            ("right_indent_pt", "右缩进", -1584.0, 1584.0),
            ("first_line_indent_pt", "首行缩进", 0.0, 1584.0),
            ("hanging_indent_pt", "悬挂缩进", 0.0, 1584.0),
        )
        character_indent_fields = (
            ("left_indent_chars", "左缩进字符数", -100.0, 100.0),
            ("right_indent_chars", "右缩进字符数", -100.0, 100.0),
            ("first_line_indent_chars", "首行缩进字符数", 0.0, 100.0),
            ("hanging_indent_chars", "悬挂缩进字符数", 0.0, 100.0),
        )
        for field, label, minimum, maximum in point_indent_fields:
            if field in raw_edit:
                edit[field] = _validated_edit_number(
                    raw_edit[field], label, minimum, maximum, 0.05
                )
        for field, label, minimum, maximum in character_indent_fields:
            if field in raw_edit:
                edit[field] = _validated_edit_number(
                    raw_edit[field], label, minimum, maximum, 0.01
                )

        for point_field, character_field, label in (
            ("left_indent_pt", "left_indent_chars", "左缩进"),
            ("right_indent_pt", "right_indent_chars", "右缩进"),
            (
                "first_line_indent_pt",
                "first_line_indent_chars",
                "首行缩进",
            ),
            (
                "hanging_indent_pt",
                "hanging_indent_chars",
                "悬挂缩进",
            ),
        ):
            if point_field in raw_edit and character_field in raw_edit:
                raise core.TransferError(
                    "%s不能同时使用磅值和字符单位。" % label
                )
        first_line_fields = (
            "first_line_indent_pt",
            "first_line_indent_chars",
        )
        hanging_fields = (
            "hanging_indent_pt",
            "hanging_indent_chars",
        )
        first_line_value = next(
            (float(edit[field]) for field in first_line_fields if field in edit),
            None,
        )
        hanging_value = next(
            (float(edit[field]) for field in hanging_fields if field in edit),
            None,
        )
        if (
            first_line_value is not None
            and hanging_value is not None
            and not math.isclose(first_line_value, 0.0, abs_tol=1e-9)
            and not math.isclose(hanging_value, 0.0, abs_tol=1e-9)
        ):
            raise core.TransferError("首行缩进与悬挂缩进不能同时为非零值。")
        if len(edit) == 1:
            raise core.TransferError("样式 %s 没有提供任何可修改字段。" % style_id)
        normalized_edits.append(edit)
    return normalized_edits


def _numbering_user_edits(
    manifest: Dict[str, object],
    entries: Dict[str, bytes],
    catalog: core.StyleCatalog,
) -> List[Dict[str, object]]:
    """Recover explicit numbering choices, including pre-marker derived packs.

    Only user-edited fields are replayed after legacy hierarchy/font repair.
    Unedited inferred levels continue to receive the existing calibration.
    """
    saved = manifest.get("heading_numbering_user_edits")
    if saved is not None:
        if not isinstance(saved, dict):
            raise core.TransferError("格式库的用户标题编号编辑清单无效。")
        raw_edits: List[Dict[str, object]] = []
        for style_id, fields in saved.items():
            if not isinstance(fields, dict) or not fields or set(fields).difference(_NUMBERING_STYLE_EDIT_FIELDS):
                raise core.TransferError("格式库的用户标题编号字段无效。")
            raw_edits.append({"style_id": style_id, **fields})
        edits = _normalize_style_edits({"styles": raw_edits}) if raw_edits else []
    else:
        # Older derivatives recorded field names but not an accumulated edit
        # map.  Recover their values from the verified, effective number rules.
        edits = []
        derivation = manifest.get("derivation")
        records = derivation.get("edited_styles", []) if isinstance(derivation, dict) else []
        rules = core.heading_numbering_from_manifest(manifest.get("heading_numbering"), entries, catalog)
        if isinstance(records, list):
            for record in records:
                if not isinstance(record, dict) or not isinstance(record.get("fields"), list):
                    continue
                style_id = str(record.get("style_id", ""))
                rule = rules.get(style_id)
                if rule is None:
                    continue
                values = {"numbering_format": rule.number_format, "numbering_pattern": rule.level_text, "numbering_start": rule.start, "numbering_restart": _numbering_restarts(entries, rule)}
                fields = {field: values[field] for field in record["fields"] if isinstance(field, str) and field in _NUMBERING_STYLE_EDIT_FIELDS and values[field] is not None}
                if fields:
                    edits.extend(_normalize_style_edits({"styles": [{"style_id": style_id, **fields}]}))
    exposed = {str(item.get("style_id")) for item in manifest.get("used_formats", []) if isinstance(item, dict) and item.get("type") == "paragraph" and item.get("outline_level") is not None}
    for edit in edits:
        style_id = str(edit["style_id"])
        if style_id not in exposed or catalog.resolved_outline.get(style_id) is None:
            raise core.TransferError("用户编号编辑指向的标题样式不可用：%s。" % style_id)
    return edits


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


def _pt_to_twips(value: object) -> str:
    return str(int(round(float(value) * 20.0)))


def _characters_to_hundredths(value: object) -> str:
    return str(int(round(float(value) * 100.0)))


def _apply_paragraph_edits(
    paragraph_properties: etree._Element,
    edit: Dict[str, object],
) -> None:
    if "alignment" in edit:
        alignment = _ensure_ordered_child(
            paragraph_properties, "jc", core.PPR_CHILD_ORDER
        )
        alignment.set(core.qn(core.W_NS, "val"), str(edit["alignment"]))

    spacing_fields = {
        "space_before_pt",
        "space_after_pt",
        "line_spacing",
        "line_rule",
    }.intersection(edit)
    if spacing_fields:
        spacing = _ensure_ordered_child(
            paragraph_properties, "spacing", core.PPR_CHILD_ORDER
        )
        if "space_before_pt" in edit:
            spacing.set(
                core.qn(core.W_NS, "before"),
                _pt_to_twips(edit["space_before_pt"]),
            )
            # These attributes otherwise inherit independently and can make a
            # newly-selected point value ineffective.
            spacing.set(core.qn(core.W_NS, "beforeLines"), "0")
            spacing.set(core.qn(core.W_NS, "beforeAutospacing"), "0")
        if "space_after_pt" in edit:
            spacing.set(
                core.qn(core.W_NS, "after"),
                _pt_to_twips(edit["space_after_pt"]),
            )
            spacing.set(core.qn(core.W_NS, "afterLines"), "0")
            spacing.set(core.qn(core.W_NS, "afterAutospacing"), "0")
        if "line_spacing" in edit and "line_rule" in edit:
            line_rule = str(edit["line_rule"])
            raw_line = (
                int(round(float(edit["line_spacing"]) * 240.0))
                if line_rule == "auto"
                else int(round(float(edit["line_spacing"]) * 20.0))
            )
            spacing.set(core.qn(core.W_NS, "line"), str(raw_line))
            spacing.set(core.qn(core.W_NS, "lineRule"), line_rule)

    indent_fields = {
        "left_indent_pt",
        "right_indent_pt",
        "first_line_indent_pt",
        "hanging_indent_pt",
        "left_indent_chars",
        "right_indent_chars",
        "first_line_indent_chars",
        "hanging_indent_chars",
    }.intersection(edit)
    if not indent_fields:
        return
    indentation = _ensure_ordered_child(
        paragraph_properties, "ind", core.PPR_CHILD_ORDER
    )

    if "left_indent_pt" in edit:
        value = _pt_to_twips(edit["left_indent_pt"])
        for attribute in ("left", "start"):
            indentation.set(core.qn(core.W_NS, attribute), value)
        for attribute in ("leftChars", "startChars"):
            indentation.set(core.qn(core.W_NS, attribute), "0")
    elif "left_indent_chars" in edit:
        value = _characters_to_hundredths(edit["left_indent_chars"])
        for attribute in ("leftChars", "startChars"):
            indentation.set(core.qn(core.W_NS, attribute), value)
        for attribute in ("left", "start"):
            indentation.set(core.qn(core.W_NS, attribute), "0")

    if "right_indent_pt" in edit:
        value = _pt_to_twips(edit["right_indent_pt"])
        for attribute in ("right", "end"):
            indentation.set(core.qn(core.W_NS, attribute), value)
        for attribute in ("rightChars", "endChars"):
            indentation.set(core.qn(core.W_NS, attribute), "0")
    elif "right_indent_chars" in edit:
        value = _characters_to_hundredths(edit["right_indent_chars"])
        for attribute in ("rightChars", "endChars"):
            indentation.set(core.qn(core.W_NS, attribute), value)
        for attribute in ("right", "end"):
            indentation.set(core.qn(core.W_NS, attribute), "0")

    first_line_field = next(
        (
            field
            for field in ("first_line_indent_pt", "first_line_indent_chars")
            if field in edit
        ),
        None,
    )
    hanging_field = next(
        (
            field
            for field in ("hanging_indent_pt", "hanging_indent_chars")
            if field in edit
        ),
        None,
    )
    use_hanging = (
        hanging_field is not None
        and not math.isclose(float(edit[hanging_field]), 0.0, abs_tol=1e-9)
        and (
            first_line_field is None
            or math.isclose(
                float(edit[first_line_field]), 0.0, abs_tol=1e-9
            )
        )
    )

    if use_hanging and hanging_field == "hanging_indent_pt":
        indentation.set(
            core.qn(core.W_NS, "hanging"),
            _pt_to_twips(edit[hanging_field]),
        )
        indentation.set(core.qn(core.W_NS, "hangingChars"), "0")
        for attribute in ("firstLine", "firstLineChars"):
            indentation.attrib.pop(core.qn(core.W_NS, attribute), None)
    elif use_hanging and hanging_field == "hanging_indent_chars":
        indentation.set(
            core.qn(core.W_NS, "hangingChars"),
            _characters_to_hundredths(edit[hanging_field]),
        )
        indentation.set(core.qn(core.W_NS, "hanging"), "0")
        for attribute in ("firstLine", "firstLineChars"):
            indentation.attrib.pop(core.qn(core.W_NS, attribute), None)
    elif "first_line_indent_pt" in edit:
        indentation.set(
            core.qn(core.W_NS, "firstLine"),
            _pt_to_twips(edit["first_line_indent_pt"]),
        )
        indentation.set(core.qn(core.W_NS, "firstLineChars"), "0")
        for attribute in ("hanging", "hangingChars"):
            indentation.attrib.pop(core.qn(core.W_NS, attribute), None)
    elif "first_line_indent_chars" in edit:
        indentation.set(
            core.qn(core.W_NS, "firstLineChars"),
            _characters_to_hundredths(edit["first_line_indent_chars"]),
        )
        indentation.set(core.qn(core.W_NS, "firstLine"), "0")
        for attribute in ("hanging", "hangingChars"):
            indentation.attrib.pop(core.qn(core.W_NS, attribute), None)
    elif "hanging_indent_pt" in edit:
        indentation.set(
            core.qn(core.W_NS, "hanging"),
            _pt_to_twips(edit["hanging_indent_pt"]),
        )
        indentation.set(core.qn(core.W_NS, "hangingChars"), "0")
        for attribute in ("firstLine", "firstLineChars"):
            indentation.attrib.pop(core.qn(core.W_NS, attribute), None)
    elif "hanging_indent_chars" in edit:
        indentation.set(
            core.qn(core.W_NS, "hangingChars"),
            _characters_to_hundredths(edit["hanging_indent_chars"]),
        )
        indentation.set(core.qn(core.W_NS, "hanging"), "0")
        for attribute in ("firstLine", "firstLineChars"):
            indentation.attrib.pop(core.qn(core.W_NS, attribute), None)


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
    paragraph_fields = _PARAGRAPH_STYLE_EDIT_FIELDS.intersection(edit)
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
    if paragraph_fields:
        if style_type != "paragraph":
            raise core.TransferError(
                "样式 %s 不是段落样式，不能修改段落属性。"
                % edit["style_id"]
            )
        paragraph_properties = _ensure_ordered_child(
            style_node, "pPr", core.STYLE_CHILD_ORDER
        )
        _apply_paragraph_edits(paragraph_properties, edit)
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
        border_fields = {"table_border_style", "table_border_color_hex", "table_border_width_pt"}.intersection(edit)
        if border_fields:
            table_properties = _ensure_ordered_child(style_node, "tblPr", core.STYLE_CHILD_ORDER)
            borders = _ensure_ordered_child(table_properties, "tblBorders", _TABLE_PROPERTY_ORDER)
            for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
                border = _ensure_ordered_child(borders, side, ("top", "left", "bottom", "right", "insideH", "insideV"))
                # Missing borders get a complete single-line definition rather
                # than inheriting an undocumented Word default.
                if border.get(core.qn(core.W_NS, "val")) is None:
                    border.set(core.qn(core.W_NS, "val"), "single")
            # Conditional cell/table borders override the root table border in
            # Word.  Apply the requested fields to every existing border in
            # this same style, without creating conditional regions or changing
            # unrelated fields such as spacing, shading and omitted attributes.
            border_sides = {"top", "start", "left", "bottom", "end", "right", "insideH", "insideV", "tl2br", "tr2bl"}
            for border in style_node.xpath(".//w:tblBorders/* | .//w:tcBorders/*", namespaces=core.NS):
                if border.tag not in {core.qn(core.W_NS, side) for side in border_sides}:
                    continue
                if "table_border_style" in edit:
                    border.set(core.qn(core.W_NS, "val"), str(edit["table_border_style"]))
                if "table_border_color_hex" in edit:
                    for attribute in ("themeColor", "themeTint", "themeShade"):
                        border.attrib.pop(core.qn(core.W_NS, attribute), None)
                    border.set(core.qn(core.W_NS, "color"), str(edit["table_border_color_hex"]))
                if "table_border_width_pt" in edit:
                    border.set(core.qn(core.W_NS, "sz"), str(round(float(edit["table_border_width_pt"]) * 8)))
        margin_fields = {"table_cell_margin_%s_pt" % side for side in ("top", "bottom", "left", "right")}.intersection(edit)
        if margin_fields:
            table_properties = _ensure_ordered_child(style_node, "tblPr", core.STYLE_CHILD_ORDER)
            margins = _ensure_ordered_child(table_properties, "tblCellMar", _TABLE_PROPERTY_ORDER)
            for side in ("top", "left", "bottom", "right"):
                field = "table_cell_margin_%s_pt" % side
                if field in edit:
                    margin = _ensure_ordered_child(margins, side, ("top", "left", "bottom", "right"))
                    margin.set(core.qn(core.W_NS, "w"), _pt_to_twips(edit[field]))
                    margin.set(core.qn(core.W_NS, "type"), "dxa")


def _synchronize_heading_paragraph_properties(
    manifest: Dict[str, object],
    catalog: core.StyleCatalog,
    edits: Sequence[Dict[str, object]],
) -> None:
    """Keep direct heading overrides aligned with paragraph-style edits."""
    properties = core.heading_paragraph_properties_from_manifest(
        manifest.get("heading_paragraph_properties"),
        catalog,
        legacy_indents=manifest.get("heading_paragraph_indents"),
    )
    for edit in edits:
        if not _PARAGRAPH_STYLE_EDIT_FIELDS.intersection(edit):
            continue
        style_id = str(edit["style_id"])
        info = catalog.styles.get(style_id)
        if (
            info is None
            or info.style_type != "paragraph"
            or catalog.resolved_outline.get(style_id) is None
        ):
            continue
        paragraph_properties = etree.Element(core.qn(core.W_NS, "pPr"))
        existing = properties.get(style_id)
        if existing:
            core._set_heading_paragraph_properties(
                paragraph_properties, existing
            )
        _apply_paragraph_edits(paragraph_properties, edit)
        updated = core._heading_paragraph_property_profile(
            paragraph_properties
        )
        if updated:
            properties[style_id] = updated

    manifest["heading_paragraph_properties"] = properties
    manifest["heading_paragraph_indents"] = {
        style_id: dict(indentation)
        for style_id, profile in properties.items()
        for indentation in [profile.get("ind")]
        if isinstance(indentation, dict)
    }


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
    """Edit real heading number definitions and keep their label fonts aligned.

    The public protocol cannot create an arbitrary numbering graph: a request
    must point to an exposed heading with an existing concrete numbering rule.
    """
    raw_rules = manifest.get("heading_numbering")
    if not isinstance(raw_rules, dict):
        raw_rules = {}
    numbering_root, abstract_by_id, num_by_id, styles_by_id = core._numbering_index(
        entries
    )
    changed = False
    for edit in edits:
        run_edit = {
            key: value for key, value in edit.items() if key in _RUN_STYLE_EDIT_FIELDS
        }
        numbering_edit = {key: value for key, value in edit.items() if key in _NUMBERING_STYLE_EDIT_FIELDS}
        if not run_edit and not numbering_edit:
            continue
        raw_rule = raw_rules.get(str(edit["style_id"]))
        if not isinstance(raw_rule, dict):
            if numbering_edit:
                raise core.TransferError("样式 %s 没有可编辑的标题编号规则。" % edit["style_id"])
            continue
        raw_num_id = raw_rule.get("num_id")
        raw_level = raw_rule.get("level")
        try:
            level = int(raw_level)
        except (TypeError, ValueError):
            continue
        num_node = num_by_id.get(str(raw_num_id))
        if num_node is None or not 0 <= level <= 8:
            if numbering_edit:
                raise core.TransferError("样式 %s 的标题编号规则无效。" % edit["style_id"])
            continue
        abstract = core._abstract_for_num(
            num_node, abstract_by_id, num_by_id, styles_by_id
        )
        if abstract is None:
            if numbering_edit:
                raise core.TransferError("样式 %s 的标题编号定义不存在。" % edit["style_id"])
            continue
        if numbering_edit:
            pattern = numbering_edit.get("numbering_pattern")
            if pattern is not None:
                placeholders = re.findall(r"%([1-9])", str(pattern))
                if (
                    re.search(r"%(?![1-9])", str(pattern))
                    or not placeholders
                    or any(int(value) > level + 1 for value in placeholders)
                    or str(level + 1) not in placeholders
                ):
                    raise core.TransferError("标题编号模式必须包含当前层级 %%%d，且不能引用更深的层级。" % (level + 1))
            if level == 0 and numbering_edit.get("numbering_restart") is True:
                raise core.TransferError("最高一级标题没有上一级，不能设置随上一级重新编号。")
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
        if numbering_edit and not level_nodes:
            raise core.TransferError("样式 %s 的标题编号层级不存在。" % edit["style_id"])
        for level_node in level_nodes:
            for field, tag in (("numbering_format", "numFmt"), ("numbering_pattern", "lvlText"), ("numbering_start", "start")):
                if field in numbering_edit:
                    core._set_level_child_value(level_node, tag, numbering_edit[field])
            if "numbering_restart" in numbering_edit:
                core._set_level_child_value(level_node, "lvlRestart", level if numbering_edit["numbering_restart"] else 0)
            if run_edit:
                run_properties = level_node.find("w:rPr", namespaces=core.NS)
                if run_properties is None:
                    run_properties = etree.SubElement(level_node, core.qn(core.W_NS, "rPr"))
                _apply_run_edits(run_properties, run_edit)
            changed = True
        # A concrete startOverride takes precedence over w:lvl/w:start.  Update
        # both so a visible editor change is not shadowed by the old instance.
        if "numbering_start" in numbering_edit and override is not None:
            start_override = override.find("w:startOverride", namespaces=core.NS)
            if start_override is not None:
                start_override.set(core.qn(core.W_NS, "val"), str(numbering_edit["numbering_start"]))
    if changed:
        _rels, roles = core.collect_format_relationships(entries)
        record = roles.get("numbering")
        part_name = (
            record[0]
            if record is not None
            else core.ROLE_FALLBACK_PARTS["numbering"]
        )
        entries[part_name] = core.serialize_xml(numbering_root)
        catalog_entries = dict(entries)
        catalog_entries["word/document.xml"] = _placeholder_document()
        catalog = core.build_style_catalog(catalog_entries["word/styles.xml"], catalog_entries["word/document.xml"])
        manifest["heading_numbering"] = core.heading_numbering_manifest(core.heading_numbering_from_manifest(raw_rules, catalog_entries, catalog))


def _numbering_restarts(entries: Dict[str, bytes], rule: Optional[core.HeadingNumberingRule]) -> Optional[bool]:
    """Read the effective restart value rather than an editor-only flag."""
    if rule is None or rule.level == 0:
        return None
    _root, abstracts, nums, styles = core._numbering_index(entries)
    num = nums.get(rule.num_id)
    if num is None:
        return None
    abstract = core._abstract_for_num(num, abstracts, nums, styles)
    override = core._override_for_level(num, rule.level)
    overridden = override.find("w:lvl", namespaces=core.NS) if override is not None else None
    base = core._level_node(abstract, rule.level) if abstract is not None else None
    for node in (overridden, base):
        if node is None:
            continue
        restart = node.find("w:lvlRestart", namespaces=core.NS)
        if restart is not None:
            value = core._safe_int(restart.get(core.qn(core.W_NS, "val")))
            return value != 0 if value is not None else None
    # Word's default is to restart after the immediately preceding level.
    return True


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
    font_aliases = _font_aliases(runtime_entries)
    numbering = core.heading_numbering_from_manifest(
        manifest.get("heading_numbering"), runtime_entries, catalog
    )
    heading_paragraph_properties = (
        core.heading_paragraph_properties_from_manifest(
            manifest.get("heading_paragraph_properties"),
            catalog,
            legacy_indents=manifest.get("heading_paragraph_indents"),
        )
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
            font_aliases=font_aliases,
            numbering_rule=numbering.get(style_id),
            inferred=inferred,
            inference_label=(
                "自定义表格方案"
                if configured
                else "智能补全"
                if inferred
                else None
            ),
            paragraph_override=heading_paragraph_properties.get(style_id),
            numbering_restart=_numbering_restarts(runtime_entries, numbering.get(style_id)),
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
        font_aliases=_font_aliases(entries),
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


def _synthesize_legacy_font_aliases(
    manifest: Dict[str, object], entries: Dict[str, bytes]
) -> None:
    """Enrich old packs with fontTable aliases in memory only.

    Packs created before the alias preview fields were introduced already
    retain the allow-listed fontTable part.  Reusing it here gives those packs
    the same cross-locale font discovery as newly imported templates without
    modifying the archive or invalidating its integrity metadata.
    """
    aliases = _font_aliases(entries)
    if not aliases:
        return

    records: List[object] = []
    used_formats = manifest.get("used_formats")
    if isinstance(used_formats, list):
        records.extend(used_formats)
    candidate = manifest.get("table_style_edit_candidate")
    if candidate is not None:
        records.append(candidate)

    for raw in records:
        if not isinstance(raw, dict):
            continue
        for font_field, alias_field in (
            ("font_latin", "font_latin_aliases"),
            ("font_east_asia", "font_east_asia_aliases"),
        ):
            if alias_field in raw:
                continue
            font_name = raw.get(font_field)
            if not isinstance(font_name, str) or not font_name.strip():
                continue
            values = aliases.get(_font_alias_key(font_name), [])
            if values:
                raw[alias_field] = list(values)


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
        if _NUMBERING_STYLE_EDIT_FIELDS.intersection(edit) and (info.style_type != "paragraph" or catalog.resolved_outline.get(style_id) is None):
            raise core.TransferError("样式 %s 不是标题，不能编辑标题编号。" % style_id)
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

    saved_numbering_edits = {
        str(edit["style_id"]): {field: value for field, value in edit.items() if field in _NUMBERING_STYLE_EDIT_FIELDS}
        for edit in _numbering_user_edits(effective_manifest, entries, catalog)
    }
    _apply_heading_numbering_edits(entries, effective_manifest, edits)
    for edit in edits:
        fields = {field: value for field, value in edit.items() if field in _NUMBERING_STYLE_EDIT_FIELDS}
        if fields:
            saved_numbering_edits.setdefault(str(edit["style_id"]), {}).update(fields)
    if saved_numbering_edits:
        effective_manifest["heading_numbering_user_edits"] = saved_numbering_edits
    _append_missing_font_records(entries, edits)
    _synchronize_heading_paragraph_properties(
        effective_manifest, catalog, edits
    )
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


def _file_sha256(path: Path, label: str) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise core.TransferError("无法读取%s：%s" % (label, exc)) from exc
    return digest.hexdigest()


def _check_preflight_hash(actual: str, expected: Optional[str], label: str) -> None:
    if expected is not None and (not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected) or actual != expected):
        raise core.TransferError("%s在预检后发生变化，请重新预检再应用。" % label)


def _same_file(first: Path, second: Path) -> bool:
    if first == second:
        return True
    try:
        return first.exists() and second.exists() and os.path.samefile(first, second)
    except OSError:
        return False


def _pack_application_identity(manifest: Dict[str, object]) -> str:
    """Include applied metadata absent from the legacy part-only fingerprint."""
    fields = ("section_layouts", "heading_authorities", "heading_numbering", "heading_numbering_user_edits", "heading_paragraph_indents", "heading_paragraph_properties", "used_table_styles", "preferred_table_style")
    value = {key: manifest.get(key) for key in fields}
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def import_style_pack(pack_path: Path, library_dir: Path) -> Tuple[Dict[str, object], bool]:
    """Validate a shared pack, deduplicate equivalent rules, reject ID reuse."""
    pack_path = pack_path.expanduser().resolve()
    manifest, entries = load_style_pack(pack_path)
    library_dir = library_dir.expanduser().resolve()
    existing: List[Dict[str, object]] = []
    if library_dir.exists() and not library_dir.is_dir():
        raise core.TransferError("格式库位置不是文件夹。")
    for candidate in sorted(library_dir.glob("*" + PACK_SUFFIX)):
        try:
            saved, _saved_entries = load_style_pack(candidate)
        except core.TransferError:
            # list-library exposes these individual failures to the GUI.
            continue
        existing.append(saved)
    fingerprint = manifest["format_fingerprint"]
    identity = _pack_application_identity(manifest)
    for saved in existing:
        equivalent = saved["format_fingerprint"] == fingerprint and _pack_application_identity(saved) == identity
        if saved["id"] == manifest["id"] and not equivalent:
            raise core.TransferError("格式库 ID 冲突：同一方案标识对应不同格式，导入已停止。")
    for saved in existing:
        if saved["format_fingerprint"] == fingerprint and _pack_application_identity(saved) == identity:
            return saved, False
    destination = allocate_pack_path(library_dir, str(manifest["name"]))
    return _write_style_pack_archive(destination, manifest, entries), True


def export_style_pack(pack_path: Path, output: Path, force: bool = False) -> Dict[str, object]:
    """Export a fully validated, portable pack without modifying its source."""
    source = pack_path.expanduser().resolve()
    output = output.expanduser().resolve()
    if _same_file(source, output):
        raise core.TransferError("为保护原格式方案，导出位置不能覆盖原文件。")
    manifest, entries = load_style_pack(source)
    return _write_style_pack_archive(output, manifest, entries, force=force)


def preflight_style_pack(
    pack_path: Path,
    target: Path,
    demote_headings: bool = False,
    preserve_page_layout: bool = False,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Read actual inputs and bind a non-writing impact report to their bytes."""
    pack_path, target = pack_path.expanduser().resolve(), target.expanduser().resolve()
    if target.suffix.lower() not in core.TARGET_SUFFIXES:
        raise core.TransferError("内容目标文件只支持 .docx 或 .docm。")
    if not isinstance(demote_headings, bool) or not isinstance(preserve_page_layout, bool):
        raise core.TransferError("预检选项必须是布尔值。")
    pack_hash = _file_sha256(pack_path, "格式方案")
    target_hash = _file_sha256(target, "目标文件")
    manifest, format_entries = load_style_pack(pack_path, expected_sha256=pack_hash)
    package = core.load_package(target, "内容目标文件", expected_sha256=target_hash)
    catalog = core.build_style_catalog(package.entries["word/styles.xml"], package.entries["word/document.xml"])
    summary = {key: 0 for key in ("paragraph_count", "run_count", "table_count", "section_count", "character_count")}
    levels: Counter[int] = Counter()
    manual_paragraphs = manual_runs = 0
    revisions = False
    for name, data in package.entries.items():
        if not core.is_content_part(name):
            continue
        root = core.parse_xml(data, name)
        paragraphs = root.xpath("//w:p", namespaces=core.NS)
        summary["paragraph_count"] += len(paragraphs)
        summary["run_count"] += len(root.xpath("//w:r", namespaces=core.NS))
        summary["table_count"] += len(root.xpath("//w:tbl", namespaces=core.NS))
        summary["section_count"] += len(root.xpath("//w:sectPr", namespaces=core.NS))
        summary["character_count"] += sum(len(value) for value in root.xpath("//w:t/text()", namespaces=core.NS))
        revisions = revisions or bool(root.xpath("//w:ins | //w:del | //w:pPrChange | //w:rPrChange", namespaces=core.NS))
        manual_runs += len(root.xpath("//w:r/w:rPr", namespaces=core.NS))
        for paragraph in paragraphs:
            properties = paragraph.find("w:pPr", namespaces=core.NS)
            if properties is not None and any(core.local_name(node) not in {"pStyle", "sectPr"} for node in properties):
                manual_paragraphs += 1
            if name == "word/document.xml":
                level = core.paragraph_outline_level(properties, catalog)
                if level is not None:
                    levels[level] += 1
    fonts = sorted({str(item[field]) for item in manifest.get("used_formats", []) if isinstance(item, dict) for field in ("font_latin", "font_east_asia") if item.get(field)}, key=str.casefold)
    has_tables = bool(manifest.get("used_table_styles"))
    warnings = [str(value) for value in manifest.get("heading_completion_warnings", [])]
    runtime_inferred_levels: List[int] = []
    if demote_headings and levels:
        source_entries = dict(format_entries)
        source_entries["word/document.xml"] = _placeholder_document()
        source_catalog = core.build_style_catalog(source_entries["word/styles.xml"], source_entries["word/document.xml"])
        authorities = {
            int(level): str(style_id)
            for level, style_id in manifest.get("heading_authorities", {}).items()
            if str(level).isdigit() and 0 <= int(level) <= 8 and source_catalog.resolved_outline.get(str(style_id)) == int(level)
        }
        if not authorities:
            for item in manifest.get("used_formats", []):
                if isinstance(item, dict) and item.get("type") == "paragraph" and isinstance(item.get("outline_level"), int) and not isinstance(item.get("outline_level"), bool):
                    style_id, level = str(item.get("style_id")), int(item["outline_level"])
                    if source_catalog.resolved_outline.get(style_id) == level:
                        authorities.setdefault(level, style_id)
        desired_levels = {min(8, level + 1) for level in levels}
        missing = desired_levels.difference(authorities)
        if missing and max(missing) >= 3:
            rules = core.heading_numbering_from_manifest(manifest.get("heading_numbering"), source_entries, source_catalog)
            if "heading_numbering" not in manifest:
                rules = core.infer_heading_numbering_rules(source_entries, source_catalog, authorities.values())
            completion = core.complete_heading_hierarchy(source_entries, source_catalog, authorities, rules, max_level=max(missing), extend_numbering=False)
            authorities.update(completion.inferred_styles)
            warnings.extend(completion.warnings)
            runtime_inferred_levels = [level + 1 for level in sorted(completion.inferred_styles)]
        unresolved = sorted(desired_levels.difference(authorities))
        if unresolved:
            raise core.TransferError("当前格式库无法生成%s，不能安全地把全部标题下调一级；请重新导入连续设置了标题一、标题二、标题三的模板。" % "、".join("标题%d" % (level + 1) for level in unresolved))
    if summary["table_count"] and not has_tables:
        warnings.append("格式方案没有实际使用的表格样式，将保留目标表格外观，仅移除单元格两字符首行缩进。")
    if demote_headings and levels.get(8):
        warnings.append("Word 最多支持标题9，%d 个标题9将保持原级别。" % levels[8])
    if revisions:
        warnings.append("目标文件包含修订，生成后请在 Word 中核对修订显示和格式。")
    if any(name.lower().startswith("_xmlsignatures/") for name in package.entries):
        warnings.append("目标文件带有数字签名，修改格式会使原签名失效，请使用未签名副本。")
    if any(name.lower().endswith("vbaproject.bin") for name in package.entries):
        warnings.append("目标文件包含宏，输出将保留宏部件，请在 Word 中核对。")
    _check_preflight_hash(_file_sha256(pack_path, "格式方案"), pack_hash, "格式方案")
    _check_preflight_hash(_file_sha256(target, "目标文件"), target_hash, "目标文件")
    report: Dict[str, object] = {
        "summary": summary,
        "heading_level_counts": {str(level + 1): count for level, count in sorted(levels.items())},
        "heading_demotion_count": sum(count for level, count in levels.items() if level < 8) if demote_headings else 0,
        "runtime_inferred_heading_levels": runtime_inferred_levels,
        "table_action": "apply_pack_table_style" if has_tables else "preserve_target_remove_two_character_indent",
        "page_layout_action": "preserve_target" if preserve_page_layout else "apply_pack",
        "font_names": fonts,
        "manual_formatting": {"paragraph_count": manual_paragraphs, "run_count": manual_runs},
        "warnings": list(dict.fromkeys(warnings)),
        "input_binding": {"pack_sha256": pack_hash, "target_sha256": target_hash, "demote_headings": demote_headings, "preserve_page_layout": preserve_page_layout},
    }
    return manifest, report


def apply_style_pack(
    pack_path: Path,
    target: Path,
    output: Path,
    force: bool = False,
    preserve_page_layout: bool = False,
    demote_headings: bool = False,
    expected_pack_sha256: Optional[str] = None,
    expected_target_sha256: Optional[str] = None,
) -> Tuple[Dict[str, object], core.TransferStats]:
    pack_path = pack_path.expanduser().resolve()
    target = target.expanduser().resolve()
    pack_hash = _file_sha256(pack_path, "格式方案")
    target_hash = _file_sha256(target, "目标文件")
    _check_preflight_hash(pack_hash, expected_pack_sha256, "格式方案")
    _check_preflight_hash(target_hash, expected_target_sha256, "目标文件")
    manifest, source_entries = load_style_pack(pack_path, expected_sha256=pack_hash)
    target = target.expanduser().resolve()
    output = output.expanduser().resolve()
    if target.suffix.lower() not in core.TARGET_SUFFIXES:
        raise core.TransferError("内容目标文件只支持 .docx 或 .docm。")
    if output.suffix.lower() != target.suffix.lower():
        raise core.TransferError("输出扩展名必须与目标文件一致。")
    if _same_file(output, target) or _same_file(output, pack_path):
        raise core.TransferError("为保护原文件，输出位置不能覆盖目标文件。")
    if output.exists() and not force:
        raise core.TransferError("输出文件已存在。")

    source_entries = dict(source_entries)
    source_entries["word/document.xml"] = _placeholder_document()
    target_package = core.load_package(target, "内容目标文件", expected_sha256=target_hash)
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
        target_heading_levels = core.collect_used_heading_levels(
            target_entries,
            target_catalog,
            part_names=("word/document.xml",),
        )
        desired_heading_levels = {
            min(8, level + 1) for level in target_heading_levels
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
    saved_numbering_edits = _numbering_user_edits(manifest, source_entries, source_catalog)
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
    if saved_numbering_edits:
        # Hierarchy repair rebuilds inferred levels (including starts/patterns)
        # and calibrates legacy label fonts.  Reapply accumulated explicit
        # number choices to the new rules without disabling that repair.
        edited_manifest = {"heading_numbering": core.heading_numbering_manifest(heading_numbering)}
        _apply_heading_numbering_edits(source_entries, edited_manifest, saved_numbering_edits)
        heading_numbering = core.heading_numbering_from_manifest(edited_manifest["heading_numbering"], source_entries, source_catalog)
    used_heading_style_ids = set(heading_authorities.values())
    core.align_heading_style_numbering(
        source_entries, used_heading_style_ids, heading_numbering
    )
    heading_paragraph_properties = (
        core.heading_paragraph_properties_from_manifest(
            manifest.get("heading_paragraph_properties"),
            source_catalog,
            legacy_indents=manifest.get("heading_paragraph_indents"),
        )
    )
    for level, style_id in sorted(runtime_inferred_headings.items()):
        parent_style_id = heading_authorities.get(level - 1)
        parent_profile = heading_paragraph_properties.get(
            parent_style_id or ""
        )
        parent_indent = (
            parent_profile.get("ind")
            if isinstance(parent_profile, dict)
            else None
        )
        if isinstance(parent_indent, dict):
            heading_paragraph_properties[style_id] = {
                "ind": copy.deepcopy(parent_indent)
            }
    heading_paragraph_indents = {
        style_id: dict(indentation)
        for style_id, profile in heading_paragraph_properties.items()
        for indentation in [profile.get("ind")]
        if isinstance(indentation, dict)
    }
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
    if (
        "heading_paragraph_properties" not in manifest
        and "heading_paragraph_indents" not in manifest
        and heading_numbering
    ):
        stats.warnings.append(
            "此格式库由旧版本创建，未保存标题段落的实际缩进、"
            "间距和对齐；如需精确复制，请用当前版本重新导入一次格式源。"
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
            heading_paragraph_properties=heading_paragraph_properties,
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
    _check_preflight_hash(_file_sha256(pack_path, "格式方案"), pack_hash, "格式方案")
    _check_preflight_hash(_file_sha256(target, "目标文件"), target_hash, "目标文件")
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
    create_destination = create_parser.add_mutually_exclusive_group(required=True)
    # --dir 让引擎决定文件名，是客户端应当使用的方式；--out 保留给脚本与测试。
    create_destination.add_argument("--dir")
    create_destination.add_argument("--out")
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

    import_parser = subparsers.add_parser("import-pack")
    import_parser.add_argument("--pack", required=True)
    import_parser.add_argument("--dir", required=True)

    export_parser = subparsers.add_parser("export-pack")
    export_parser.add_argument("--pack", required=True)
    export_parser.add_argument("--out", required=True)
    export_parser.add_argument("--force", action="store_true")

    preflight_parser = subparsers.add_parser("preflight-pack")
    preflight_parser.add_argument("--pack", required=True)
    preflight_parser.add_argument("--target", required=True)
    preflight_parser.add_argument("--preserve-page-layout", action="store_true")
    preflight_parser.add_argument("--demote-headings", action="store_true")

    apply_parser = subparsers.add_parser("apply-pack")
    apply_parser.add_argument("--pack", required=True)
    apply_parser.add_argument("--target", required=True)
    apply_parser.add_argument("--out", required=True)
    apply_parser.add_argument("--force", action="store_true")
    apply_parser.add_argument("--preserve-page-layout", action="store_true")
    apply_parser.add_argument("--demote-headings", action="store_true")
    apply_parser.add_argument("--expected-pack-sha256")
    apply_parser.add_argument("--expected-target-sha256")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            _package, _catalog, manifest = inspect_source(Path(args.source))
            _json_result({"ok": True, "pack": manifest})
        elif args.command == "create-pack":
            if args.dir:
                library_dir = Path(args.dir).expanduser()
                library_dir.mkdir(parents=True, exist_ok=True)
                destination = allocate_pack_path(library_dir, args.name)
            else:
                destination = Path(args.out)
            manifest = create_style_pack(
                Path(args.source),
                destination,
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
        elif args.command == "import-pack":
            manifest, imported = import_style_pack(Path(args.pack), Path(args.dir))
            _json_result({"ok": True, "pack": manifest, "imported": imported})
        elif args.command == "export-pack":
            manifest = export_style_pack(Path(args.pack), Path(args.out), force=args.force)
            _json_result({"ok": True, "pack": manifest, "output": str(Path(args.out).expanduser().resolve())})
        elif args.command == "preflight-pack":
            manifest, preflight = preflight_style_pack(Path(args.pack), Path(args.target), demote_headings=args.demote_headings, preserve_page_layout=args.preserve_page_layout)
            _json_result({"ok": True, "pack": manifest, "preflight": preflight})
        elif args.command == "apply-pack":
            manifest, stats = apply_style_pack(
                Path(args.pack),
                Path(args.target),
                Path(args.out),
                force=args.force,
                preserve_page_layout=args.preserve_page_layout,
                demote_headings=args.demote_headings,
                expected_pack_sha256=args.expected_pack_sha256,
                expected_target_sha256=args.expected_target_sha256,
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
