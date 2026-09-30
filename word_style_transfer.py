#!/usr/bin/env python3
"""Transfer the formatting system from one modern Word file to another.

The source document is the formatting authority.  The target document keeps
its content and document relationships, while the output receives the source
styles, theme, fonts, numbering definitions and page geometry.  Direct visual
formatting in the target is removed so the imported styles control appearance.

Supported source files: .docx, .docm, .dotx, .dotm
Supported target/output files: .docx, .docm

This utility intentionally never edits either input file in place.

[INPUT]: 依赖 __future__, argparse, copy, hashlib, io, json, os, posixpath, re, sys, tempfile, zipfile, collections, dataclasses, pathlib, typing
[OUTPUT]: 提供有界不可变输入快照、格式迁移、有效大纲解析、独立编号身份与安全输出接口
[POS]: 文档格式引擎，保持目标内容语义并应用源样式、编号和页面布局
[PROTOCOL]: 变更时更新此头部，然后检查上级 FOLDER_INDEX.md
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
import posixpath
import re
import sys
import tempfile
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

try:
    from lxml import etree
except ImportError as exc:  # pragma: no cover - exercised by launcher checks
    raise SystemExit(
        "缺少 Word 文档解析组件 lxml。若使用 Forma 赋式安装版，请重新安装应用；"
        "若通过命令行运行，请在当前 Python 环境中安装 lxml。"
        "\n原始错误：%s" % exc
    )


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
XML_NS = "http://www.w3.org/XML/1998/namespace"

NS = {"w": W_NS, "r": R_NS, "pr": PKG_REL_NS, "ct": CT_NS}

SOURCE_SUFFIXES = {".docx", ".docm", ".dotx", ".dotm"}
TARGET_SUFFIXES = {".docx", ".docm"}

ROLE_NAMES = {
    "styles",
    "stylesWithEffects",
    "theme",
    "fontTable",
    "numbering",
}

ROLE_FALLBACK_PARTS = {
    "styles": "word/styles.xml",
    "stylesWithEffects": "word/stylesWithEffects.xml",
    "theme": "word/theme/theme1.xml",
    "fontTable": "word/fontTable.xml",
    "numbering": "word/numbering.xml",
}

# These run properties affect language, visibility or mathematical meaning more
# than visual styling.  They survive the visual-format reset.
RUN_SEMANTIC_KEEP = {
    "rStyle",
    "rtl",
    "cs",
    "lang",
    "noProof",
    "vanish",
    "specVanish",
    "webHidden",
    "vertAlign",
    "oMath",
}

# Keep table geometry and merge semantics, while removing visual borders,
# fills, alignment, padding and other direct styling.
TABLE_PROPERTY_KEEP = {
    "tblStyle",
    "tblW",
    "tblInd",
    "tblLayout",
    "tblLook",
    "tblOverlap",
    "tblpPr",
    "bidiVisual",
}
ROW_PROPERTY_KEEP = {
    "cantSplit",
    "tblHeader",
    "gridBefore",
    "gridAfter",
    "wBefore",
    "wAfter",
    "cnfStyle",
    "hidden",
}
CELL_PROPERTY_KEEP = {
    "tcW",
    "gridSpan",
    "hMerge",
    "vMerge",
    "textDirection",
    "tcFitText",
    "noWrap",
    "hideMark",
    "cnfStyle",
}

# Header/footer references belong to the target content.  Everything in this
# whitelist can safely be copied from a source section without importing the
# source header/footer text or invalid relationship IDs.
SECTION_LAYOUT_TAGS = {
    "pgSz",
    "pgMar",
    "paperSrc",
    "pgBorders",
    "lnNumType",
    "pgNumType",
    "cols",
    "formProt",
    "vAlign",
    "noEndnote",
    "titlePg",
    "textDirection",
    "bidi",
    "rtlGutter",
    "docGrid",
}

SETTINGS_FORMAT_TAGS = {
    "defaultTableStyle",
    "defaultTabStop",
    "characterSpacingControl",
    "themeFontLang",
    "decimalSymbol",
    "listSeparator",
    "evenAndOddHeaders",
    "mirrorMargins",
    "gutterAtTop",
    "bordersDoNotSurroundHeader",
    "bordersDoNotSurroundFooter",
    "alignBordersAndEdges",
    "displayBackgroundShape",
}

CONTENT_PART_PATTERNS = (
    re.compile(r"^word/document\.xml$"),
    re.compile(r"^word/header\d*\.xml$"),
    re.compile(r"^word/footer\d*\.xml$"),
    re.compile(r"^word/footnotes\.xml$"),
    re.compile(r"^word/endnotes\.xml$"),
    re.compile(r"^word/comments\.xml$"),
    re.compile(r"^word/glossary/document\.xml$"),
)

# DOCX is a ZIP-based OPC package.  These limits are intentionally generous
# enough for image-heavy, real-world Word documents while preventing a corrupt
# or hostile package from making the app allocate unbounded memory.  The
# loader keeps every part in memory, so the total uncompressed limit is the
# most important last line of defence.
MAX_PACKAGE_MEMBERS = 10_000
MAX_PACKAGE_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024  # 1 GiB
MAX_PACKAGE_MEMBER_BYTES = 512 * 1024 * 1024  # 512 MiB (large media is valid)
MAX_PACKAGE_XML_BYTES = 64 * 1024 * 1024  # 64 MiB per XML/relationships part
MAX_PACKAGE_COMPRESSION_RATIO = 1000
COMPRESSION_RATIO_MIN_BYTES = 1024 * 1024
MAX_PACKAGE_MEMBER_NAME_BYTES = 1024
ALLOWED_PACKAGE_COMPRESSIONS = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}


class TransferError(RuntimeError):
    """User-facing transfer error."""


def qn(namespace: str, local: str) -> str:
    return "{%s}%s" % (namespace, local)


def local_name(element: etree._Element) -> str:
    return etree.QName(element).localname


def parse_xml(data: bytes, label: str) -> etree._Element:
    try:
        parser = etree.XMLParser(
            remove_blank_text=False,
            resolve_entities=False,
            no_network=True,
            recover=False,
            huge_tree=True,
        )
        return etree.fromstring(data, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise TransferError("无法解析 %s：%s" % (label, exc)) from exc


def serialize_xml(root: etree._Element) -> bytes:
    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )


def normalize_style_name(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"[\s_\-–—]+", "", value).casefold()


def relationship_part_path(part_name: str) -> str:
    folder = posixpath.dirname(part_name)
    filename = posixpath.basename(part_name)
    return posixpath.join(folder, "_rels", filename + ".rels")


def resolve_relationship_target(base_part: str, target: str) -> str:
    if target.startswith("/"):
        resolved = posixpath.normpath(target.lstrip("/"))
    else:
        resolved = posixpath.normpath(
            posixpath.join(posixpath.dirname(base_part), target)
        )
    if resolved == ".." or resolved.startswith("../"):
        raise TransferError("检测到超出 DOCX 包范围的关系路径：%s" % target)
    return resolved


def relative_relationship_target(base_part: str, target_part: str) -> str:
    return posixpath.relpath(target_part, posixpath.dirname(base_part))


def relationship_role(rel_type: str) -> Optional[str]:
    tail = rel_type.rstrip("/").rsplit("/", 1)[-1]
    return tail if tail in ROLE_NAMES else None


def is_content_part(name: str) -> bool:
    return any(pattern.match(name) for pattern in CONTENT_PART_PATTERNS)


@dataclass
class Package:
    entries: Dict[str, bytes]
    infos: Dict[str, zipfile.ZipInfo]
    order: List[str]


def _is_xml_package_part(name: str) -> bool:
    lowered = name.casefold()
    return lowered.endswith(".xml") or lowered.endswith(".rels")


def _validate_package_member_name(name: str, role: str) -> None:
    if not name:
        raise TransferError("%s包含空名称的异常条目。" % role)
    if len(name.encode("utf-8")) > MAX_PACKAGE_MEMBER_NAME_BYTES:
        raise TransferError(
            "%s包含名称过长的异常条目（最多 %d 字节）。"
            % (role, MAX_PACKAGE_MEMBER_NAME_BYTES)
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise TransferError("%s包含带控制字符的异常条目。" % role)
    if "\\" in name:
        raise TransferError("%s包含使用反斜杠的异常条目：%s" % (role, name))
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise TransferError("%s包含绝对路径条目：%s" % (role, name))

    # Empty components allow ambiguous spellings such as word//styles.xml.
    # A final empty component is permitted only for an explicit directory.
    parts = name.split("/")
    components = parts[:-1] if name.endswith("/") else parts
    if not components or any(part in {"", ".", ".."} for part in components):
        raise TransferError("%s包含不安全的路径条目：%s" % (role, name))


def validate_package_members(
    members: Sequence[zipfile.ZipInfo], role: str
) -> None:
    """Validate ZIP metadata before any member is decompressed or tested."""

    if len(members) > MAX_PACKAGE_MEMBERS:
        raise TransferError(
            "%s包含过多压缩条目（%d 个，最多允许 %d 个）。"
            % (role, len(members), MAX_PACKAGE_MEMBERS)
        )

    seen: Set[str] = set()
    total_uncompressed = 0
    for info in members:
        name = info.filename
        _validate_package_member_name(name, role)
        if name in seen:
            raise TransferError("%s包含重复条目：%s" % (role, name))
        seen.add(name)

        if info.flag_bits & 0x1:
            raise TransferError(
                "%s包含加密条目，无法安全读取：%s" % (role, name)
            )
        if info.compress_type not in ALLOWED_PACKAGE_COMPRESSIONS:
            raise TransferError(
                "%s包含 Word 不支持的压缩方式：%s" % (role, name)
            )
        if info.file_size < 0 or info.compress_size < 0:
            raise TransferError("%s包含大小信息异常的条目：%s" % (role, name))

        if info.is_dir():
            if info.file_size != 0 or info.compress_size != 0:
                raise TransferError("%s包含带数据的异常目录条目：%s" % (role, name))
            continue

        if info.file_size > MAX_PACKAGE_MEMBER_BYTES:
            raise TransferError(
                "%s中的单个文件过大（%s，最多允许 512 MiB）：%s"
                % (role, _human_size(info.file_size), name)
            )
        if _is_xml_package_part(name) and info.file_size > MAX_PACKAGE_XML_BYTES:
            raise TransferError(
                "%s中的 XML 部件过大（%s，最多允许 64 MiB）：%s"
                % (role, _human_size(info.file_size), name)
            )

        total_uncompressed += info.file_size
        if total_uncompressed > MAX_PACKAGE_UNCOMPRESSED_BYTES:
            raise TransferError(
                "%s解压后的总大小过大（最多允许 1 GiB）。" % role
            )

        if info.file_size >= COMPRESSION_RATIO_MIN_BYTES:
            if info.compress_size == 0:
                raise TransferError(
                    "%s包含压缩率异常的条目：%s" % (role, name)
                )
            ratio = info.file_size / info.compress_size
            if ratio > MAX_PACKAGE_COMPRESSION_RATIO:
                raise TransferError(
                    "%s包含压缩率异常的条目（约 %.0f:1，最多允许 %d:1）：%s"
                    % (role, ratio, MAX_PACKAGE_COMPRESSION_RATIO, name)
                )


def _human_size(size: int) -> str:
    if size >= 1024 * 1024:
        return "%.1f MiB" % (size / (1024 * 1024))
    if size >= 1024:
        return "%.1f KiB" % (size / 1024)
    return "%d B" % size


def read_package_snapshot(
    path: Path,
    role: str,
    max_bytes: int,
    expected_sha256: Optional[str] = None,
) -> bytes:
    """Hash and parse one bounded immutable snapshot, not two pathname reads."""
    try:
        with path.open("rb") as stream:
            data = stream.read(max_bytes + 1)
    except OSError as exc:
        raise TransferError("无法读取%s：%s" % (role, exc)) from exc
    if len(data) > max_bytes:
        raise TransferError("%s压缩包体积过大，已停止读取。" % role)
    if (
        expected_sha256 is not None
        and hashlib.sha256(data).hexdigest() != expected_sha256
    ):
        raise TransferError("%s在预检后发生变化，请重新预检。" % role)
    return data


def load_package(
    path: Path, role: str, expected_sha256: Optional[str] = None
) -> Package:
    if not path.exists():
        raise TransferError("%s不存在：%s" % (role, path))
    data = read_package_snapshot(
        path, role, MAX_PACKAGE_UNCOMPRESSED_BYTES + 16 * 1024 * 1024,
        expected_sha256=expected_sha256,
    )
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise TransferError(
            "%s不是可处理的现代 Word 文件；如果是 .doc，请先在 Word 中另存为 .docx。"
            % role
        )

    entries: Dict[str, bytes] = {}
    infos: Dict[str, zipfile.ZipInfo] = {}
    order: List[str] = []
    with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
        member_list = archive.infolist()
        validate_package_members(member_list, role)
        bad = archive.testzip()
        if bad:
            raise TransferError("%s压缩包已损坏，首个异常条目：%s" % (role, bad))
        for info in member_list:
            if info.is_dir():
                continue
            entries[info.filename] = archive.read(info.filename)
            infos[info.filename] = info
            order.append(info.filename)

    required = {"[Content_Types].xml", "word/document.xml", "word/styles.xml"}
    missing = sorted(required.difference(entries))
    if missing:
        raise TransferError("%s缺少 Word 必需部件：%s" % (role, ", ".join(missing)))
    return Package(entries=entries, infos=infos, order=order)


@dataclass
class StyleInfo:
    style_id: str
    style_type: str
    name: str
    aliases: Tuple[str, ...]
    based_on: Optional[str]
    own_outline_level: Optional[int]
    is_default: bool


@dataclass
class StyleCatalog:
    styles: Dict[str, StyleInfo]
    by_name: Dict[Tuple[str, str], str]
    defaults: Dict[str, str]
    heading_by_level: Dict[int, str]
    # A heading that is known to be meaningful for a level because it is
    # actually used in the source document, or was deliberately synthesized
    # by the hierarchy-completion pass.  This is intentionally distinct from
    # ``heading_by_level``: Word templates commonly contain unused built-in
    # Heading 4/5 definitions which should not outrank the source's real
    # hierarchy.
    authoritative_heading_by_level: Dict[int, str]
    resolved_outline: Dict[str, Optional[int]]
    preferred_table_style: Optional[str]
    used_table_styles: Set[str]
    used_paragraph_styles: Set[str]
    two_character_first_line_styles: Set[str]

    def fallback(self, style_type: str) -> Optional[str]:
        return self.defaults.get(style_type)


@dataclass(frozen=True)
class HeadingNumberingRule:
    """A reusable numbering reference for one outline-heading style."""

    style_id: str
    num_id: str
    level: int
    number_format: Optional[str] = None
    level_text: Optional[str] = None
    start: Optional[int] = None


@dataclass
class HeadingCompletionResult:
    """Styles and numbering created to complete a source heading hierarchy."""

    inferred_styles: Dict[int, str] = field(default_factory=dict)
    heading_numbering: Dict[str, HeadingNumberingRule] = field(default_factory=dict)
    numbering_extended: bool = False
    warnings: List[str] = field(default_factory=list)


def _read_outline(style_node: etree._Element) -> Optional[int]:
    outline = style_node.find("w:pPr/w:outlineLvl", namespaces=NS)
    if outline is None:
        return None
    raw = outline.get(qn(W_NS, "val"))
    try:
        value = int(raw) if raw is not None else None
    except ValueError:
        return None
    # Word uses 0..8 for Heading 1..9 and the explicit value 9 for
    # "Body Text".  Returning 9 here is important even though callers do not
    # treat it as a heading: it must stop a basedOn chain from inheriting an
    # ancestor heading level.
    return value if value is not None and 0 <= value <= 9 else None


def build_style_catalog(styles_bytes: bytes, document_bytes: bytes) -> StyleCatalog:
    root = parse_xml(styles_bytes, "styles.xml")
    styles: Dict[str, StyleInfo] = {}
    by_name: Dict[Tuple[str, str], str] = {}
    defaults: Dict[str, str] = {}

    for node in root.findall("w:style", namespaces=NS):
        style_id = node.get(qn(W_NS, "styleId"))
        if not style_id:
            continue
        style_type = node.get(qn(W_NS, "type"), "paragraph")
        name_node = node.find("w:name", namespaces=NS)
        name = (
            name_node.get(qn(W_NS, "val"), style_id)
            if name_node is not None
            else style_id
        )
        aliases_node = node.find("w:aliases", namespaces=NS)
        aliases: Tuple[str, ...] = ()
        if aliases_node is not None:
            raw_aliases = aliases_node.get(qn(W_NS, "val"), "")
            aliases = tuple(x.strip() for x in raw_aliases.split(",") if x.strip())
        based_node = node.find("w:basedOn", namespaces=NS)
        based_on = (
            based_node.get(qn(W_NS, "val")) if based_node is not None else None
        )
        is_default = node.get(qn(W_NS, "default")) in {"1", "true", "on"}
        info = StyleInfo(
            style_id=style_id,
            style_type=style_type,
            name=name,
            aliases=aliases,
            based_on=based_on,
            own_outline_level=_read_outline(node),
            is_default=is_default,
        )
        styles[style_id] = info
        for candidate in (style_id, name) + aliases:
            normalized = normalize_style_name(candidate)
            if normalized:
                by_name.setdefault((style_type, normalized), style_id)
        if is_default:
            defaults.setdefault(style_type, style_id)

    # Tolerate templates that omit explicit default flags.
    paragraph_candidates = ("Normal", "normal", "正文")
    character_candidates = ("DefaultParagraphFont", "defaultparagraphfont", "默认段落字体")
    table_candidates = ("TableNormal", "tablenormal", "普通表格")
    for style_type, candidates in (
        ("paragraph", paragraph_candidates),
        ("character", character_candidates),
        ("table", table_candidates),
    ):
        if style_type not in defaults:
            for candidate in candidates:
                normalized = normalize_style_name(candidate)
                match = by_name.get((style_type, normalized))
                if match:
                    defaults[style_type] = match
                    break
        if style_type not in defaults:
            for info in styles.values():
                if info.style_type == style_type:
                    defaults[style_type] = info.style_id
                    break

    resolved_outline: Dict[str, Optional[int]] = {}

    def resolve_outline(style_id: str, trail: Optional[Set[str]] = None) -> Optional[int]:
        if style_id in resolved_outline:
            return resolved_outline[style_id]
        if trail is None:
            trail = set()
        if style_id in trail:
            resolved_outline[style_id] = None
            return None
        info = styles.get(style_id)
        if info is None:
            return None
        if info.own_outline_level is not None:
            value = (
                info.own_outline_level
                if 0 <= info.own_outline_level <= 8
                else None
            )
            resolved_outline[style_id] = value
            return value
        if info.based_on:
            value = resolve_outline(info.based_on, trail | {style_id})
            resolved_outline[style_id] = value
            return value
        resolved_outline[style_id] = None
        return None

    heading_by_level: Dict[int, str] = {}
    for style_id, info in styles.items():
        if info.style_type != "paragraph":
            continue
        level = resolve_outline(style_id)
        if level is None:
            continue
        current = heading_by_level.get(level)
        # Prefer canonical Heading styles over custom outline styles.
        canonical = bool(
            re.match(r"^heading[1-9]$", normalize_style_name(style_id))
            or re.match(r"^heading[1-9]$", normalize_style_name(info.name))
            or re.match(r"^标题[1-9]$", normalize_style_name(info.name))
        )
        if current is None or canonical:
            heading_by_level[level] = style_id

    preferred_table_style: Optional[str] = None
    used_table_styles: Set[str] = set()
    document_root = parse_xml(document_bytes, "document.xml")
    paragraph_style_values = [
        str(value)
        for value in document_root.xpath(
            "//w:pPr/w:pStyle/@w:val", namespaces=NS
        )
    ]
    used_paragraph_styles: Set[str] = {
        value
        for value in paragraph_style_values
        if value in styles and styles[value].style_type == "paragraph"
    }
    heading_votes: Dict[int, Counter[str]] = {}
    for style_id in paragraph_style_values:
        level = resolved_outline.get(style_id)
        if level is not None:
            heading_votes.setdefault(level, Counter())[style_id] += 1
    authoritative_heading_by_level = {
        level: votes.most_common(1)[0][0]
        for level, votes in heading_votes.items()
        if votes
    }
    for value in document_root.xpath("//w:tblPr/w:tblStyle/@w:val", namespaces=NS):
        info = styles.get(str(value))
        if info is not None and info.style_type == "table":
            used_table_styles.add(info.style_id)
            if preferred_table_style is None:
                preferred_table_style = info.style_id

    # A body style with firstLineChars=200 means "first line: 2 characters"
    # in Word's UI.  Keep this knowledge separate from the style transfer so
    # table cells can explicitly opt out without changing body paragraphs that
    # should continue to inherit the source's normal first-line indentation.
    two_character_first_line_styles: Set[str] = set()
    for style_id, info in styles.items():
        if info.style_type != "paragraph":
            continue
        paragraph, _run = _effective_style_properties(root, style_id)
        indentation = paragraph.get("ind")
        first_line_chars = (
            _safe_int(indentation.get(qn(W_NS, "firstLineChars")))
            if indentation is not None
            else None
        )
        has_hanging = bool(
            indentation is not None
            and any(
                (_safe_int(indentation.get(qn(W_NS, attribute))) or 0) != 0
                for attribute in ("hanging", "hangingChars")
            )
        )
        if (
            first_line_chars == 200
            and not has_hanging
            and paragraph.get("numPr") is None
            and resolved_outline.get(style_id) is None
        ):
            two_character_first_line_styles.add(style_id)

    return StyleCatalog(
        styles=styles,
        by_name=by_name,
        defaults=defaults,
        heading_by_level=heading_by_level,
        authoritative_heading_by_level=authoritative_heading_by_level,
        resolved_outline=resolved_outline,
        preferred_table_style=preferred_table_style,
        used_table_styles=used_table_styles,
        used_paragraph_styles=used_paragraph_styles,
        two_character_first_line_styles=two_character_first_line_styles,
    )


def collect_used_table_styles(
    entries: Dict[str, bytes],
    catalog: StyleCatalog,
) -> Tuple[Set[str], Optional[str]]:
    """Find table styles used in every Word story, including implicit defaults."""
    default_table_style = catalog.fallback("table")
    settings_data = entries.get("word/settings.xml")
    if settings_data is not None:
        settings_root = parse_xml(settings_data, "word/settings.xml")
        default_node = settings_root.find("w:defaultTableStyle", namespaces=NS)
        if default_node is not None:
            candidate = default_node.get(qn(W_NS, "val"))
            info = catalog.styles.get(candidate or "")
            if info is not None and info.style_type == "table":
                default_table_style = info.style_id

    used: Set[str] = set()
    preferred: Optional[str] = None
    for name in sorted(entries):
        if not is_content_part(name):
            continue
        root = parse_xml(entries[name], name)
        for table in root.xpath("//w:tbl", namespaces=NS):
            style_node = table.find("w:tblPr/w:tblStyle", namespaces=NS)
            style_id = (
                style_node.get(qn(W_NS, "val"))
                if style_node is not None
                else default_table_style
            )
            info = catalog.styles.get(style_id or "")
            if info is None or info.style_type != "table":
                continue
            used.add(info.style_id)
            if preferred is None:
                preferred = info.style_id
    return used, preferred


def _word_value(node: Optional[etree._Element]) -> Optional[str]:
    return node.get(qn(W_NS, "val")) if node is not None else None


def _safe_int(value: Optional[str]) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


PPR_CHILD_ORDER = (
    "pStyle",
    "keepNext",
    "keepLines",
    "pageBreakBefore",
    "framePr",
    "widowControl",
    "numPr",
    "suppressLineNumbers",
    "pBdr",
    "shd",
    "tabs",
    "suppressAutoHyphens",
    "kinsoku",
    "wordWrap",
    "overflowPunct",
    "topLinePunct",
    "autoSpaceDE",
    "autoSpaceDN",
    "bidi",
    "adjustRightInd",
    "snapToGrid",
    "spacing",
    "ind",
    "contextualSpacing",
    "mirrorIndents",
    "suppressOverlap",
    "jc",
    "textDirection",
    "textAlignment",
    "textboxTightWrap",
    "outlineLvl",
    "divId",
    "cnfStyle",
)

# ``w:ind`` is a single paragraph property whose values can be expressed in
# either legacy (left/right) or logical (start/end) coordinates.  Persist only
# the numeric OOXML attributes: this is enough to reproduce a template's
# heading geometry without retaining any source text.
HEADING_INDENT_ATTRIBUTES = (
    "left",
    "start",
    "leftChars",
    "startChars",
    "right",
    "end",
    "rightChars",
    "endChars",
    "firstLine",
    "firstLineChars",
    "hanging",
    "hangingChars",
)

# Direct paragraph formatting is normally discarded so the imported style
# system remains authoritative.  Headings are the narrow exception: real Word
# templates frequently keep their visible spacing/alignment/indentation on the
# paragraph instances instead of in the Heading style.  Persist only these
# allow-listed, text-free attributes in a style pack.
HEADING_SPACING_INTEGER_ATTRIBUTES = (
    "before",
    "beforeLines",
    "after",
    "afterLines",
    "line",
)
HEADING_SPACING_BOOLEAN_ATTRIBUTES = (
    "beforeAutospacing",
    "afterAutospacing",
)
HEADING_SPACING_ATTRIBUTES = (
    "before",
    "beforeLines",
    "beforeAutospacing",
    "after",
    "afterLines",
    "afterAutospacing",
    "line",
    "lineRule",
)
LINE_SPACING_RULES = {"auto", "atLeast", "exact"}
PARAGRAPH_ALIGNMENT_VALUES = {
    "both",
    "center",
    "distribute",
    "end",
    "highKashida",
    "left",
    "lowKashida",
    "mediumKashida",
    "numTab",
    "right",
    "start",
    "thaiDistribute",
}

RPR_CHILD_ORDER = (
    "rStyle",
    "rFonts",
    "b",
    "bCs",
    "i",
    "iCs",
    "caps",
    "smallCaps",
    "strike",
    "dstrike",
    "outline",
    "shadow",
    "emboss",
    "imprint",
    "noProof",
    "snapToGrid",
    "vanish",
    "webHidden",
    "color",
    "spacing",
    "w",
    "kern",
    "position",
    "sz",
    "szCs",
    "highlight",
    "u",
    "effect",
    "bdr",
    "shd",
    "fitText",
    "vertAlign",
    "rtl",
    "cs",
    "em",
    "lang",
    "eastAsianLayout",
    "specVanish",
    "oMath",
)


def _shared_number_label_fonts(
    levels: Sequence[etree._Element],
) -> Optional[etree._Element]:
    """Return the stable H1/H2 number-label font authority, if present.

    A generated level must not clone the whole preceding ``w:rPr``: a source
    may give Heading 3 an exceptional size, colour or emphasis that says
    nothing about Heading 4+.  Font family is different.  When Heading 1 and
    Heading 2 explicitly agree on ``w:rFonts`` (or only one of them needs an
    explicit override), that is a reliable list-wide typography rule and is
    copied verbatim, including theme and hint attributes.

    Conflicting explicit H1/H2 font definitions are left unresolved so the
    generated marker can inherit its own heading style instead of guessing.
    """
    if not levels:
        return None
    candidates = [
        level.find("w:rPr/w:rFonts", namespaces=NS)
        for level in levels[:2]
    ]
    explicit = [node for node in candidates if node is not None]
    if not explicit:
        return None
    if len(explicit) == 2:
        first = etree.tostring(explicit[0], method="c14n", exclusive=True)
        second = etree.tostring(explicit[1], method="c14n", exclusive=True)
        if first != second:
            return None
    return copy.deepcopy(explicit[-1])

STYLE_CHILD_ORDER = (
    "name",
    "aliases",
    "basedOn",
    "next",
    "link",
    "autoRedefine",
    "hidden",
    "uiPriority",
    "semiHidden",
    "unhideWhenUsed",
    "qFormat",
    "locked",
    "personal",
    "personalCompose",
    "personalReply",
    "rsid",
    "pPr",
    "rPr",
    "tblPr",
    "trPr",
    "tcPr",
)


def collect_used_heading_styles(
    entries: Dict[str, bytes],
    catalog: StyleCatalog,
    part_names: Optional[Iterable[str]] = None,
) -> Dict[int, str]:
    """Return the most-used real source heading style for every outline level."""
    selected_parts = (
        list(part_names)
        if part_names is not None
        else [name for name in sorted(entries) if is_content_part(name)]
    )
    votes: Dict[int, Counter[str]] = {}
    first_seen: Dict[Tuple[int, str], int] = {}
    ordinal = 0
    for name in selected_parts:
        if name not in entries or not is_content_part(name):
            continue
        root = parse_xml(entries[name], name)
        for paragraph in root.xpath("//w:p", namespaces=NS):
            style_id = _word_value(
                paragraph.find("w:pPr/w:pStyle", namespaces=NS)
            ) or catalog.fallback("paragraph")
            level = catalog.resolved_outline.get(style_id or "")
            if style_id and level is not None:
                votes.setdefault(level, Counter())[style_id] += 1
                first_seen.setdefault((level, style_id), ordinal)
            ordinal += 1
    result: Dict[int, str] = {}
    for level, counter in votes.items():
        result[level] = min(
            counter,
            key=lambda style_id: (
                -counter[style_id],
                first_seen.get((level, style_id), sys.maxsize),
                style_id,
            ),
        )
    return result


def _direct_paragraph_outline_level(
    paragraph_properties: Optional[etree._Element],
) -> Optional[int]:
    if paragraph_properties is None:
        return None
    value = _safe_int(
        _word_value(paragraph_properties.find("w:outlineLvl", namespaces=NS))
    )
    return value if value is not None and 0 <= value <= 9 else None


def paragraph_outline_level(
    paragraph_properties: Optional[etree._Element],
    catalog: StyleCatalog,
) -> Optional[int]:
    """Resolve semantic heading level, honoring direct Body Text overrides.

    A legal direct outline setting overrides the paragraph style.  Word's
    value 9 explicitly means Body Text and therefore stops inheritance from
    a heading style; malformed values cannot create a heading.
    """
    direct = _direct_paragraph_outline_level(paragraph_properties)
    if direct is not None:
        return direct if direct <= 8 else None
    style_id = (
        _word_value(paragraph_properties.find("w:pStyle", namespaces=NS))
        if paragraph_properties is not None
        else None
    ) or catalog.fallback("paragraph")
    return catalog.resolved_outline.get(style_id or "")


def collect_used_heading_levels(
    entries: Dict[str, bytes],
    catalog: StyleCatalog,
    part_names: Optional[Iterable[str]] = None,
) -> Set[int]:
    """Collect actual target heading levels without inventing style authority."""
    selected_parts = (
        list(part_names)
        if part_names is not None
        else [name for name in sorted(entries) if is_content_part(name)]
    )
    result: Set[int] = set()
    for name in selected_parts:
        if name not in entries or not is_content_part(name):
            continue
        root = parse_xml(entries[name], name)
        for paragraph in root.xpath("//w:p", namespaces=NS):
            level = paragraph_outline_level(
                paragraph.find("w:pPr", namespaces=NS), catalog
            )
            if level is not None:
                result.add(level)
    return result


def _nodes_by_style_id(root: etree._Element) -> Dict[str, etree._Element]:
    return {
        str(node.get(qn(W_NS, "styleId"))): node
        for node in root.findall("w:style", namespaces=NS)
        if node.get(qn(W_NS, "styleId"))
    }


def _ordered_insert(
    parent: etree._Element,
    node: etree._Element,
    order: Sequence[str],
) -> None:
    rank = {name: index for index, name in enumerate(order)}
    node_rank = rank.get(local_name(node), len(rank))
    insertion = len(parent)
    for index, child in enumerate(parent):
        if rank.get(local_name(child), len(rank)) > node_rank:
            insertion = index
            break
    parent.insert(insertion, node)


def _replace_ordered_child(
    parent: etree._Element,
    local: str,
    replacement: Optional[etree._Element],
    order: Sequence[str],
) -> None:
    for child in list(parent):
        if local_name(child) == local:
            parent.remove(child)
    if replacement is not None:
        _ordered_insert(parent, replacement, order)


def _merge_property_map(
    destination: Dict[str, etree._Element],
    parent: Optional[etree._Element],
) -> None:
    if parent is None:
        return
    for child in parent:
        local = local_name(child)
        if local == "ind":
            destination[local] = merge_style_hierarchy_indentation(
                destination.get(local), child
            )
        elif local in {"rFonts", "spacing"} and local in destination:
            merged = copy.deepcopy(destination[local])
            for attribute, value in child.attrib.items():
                merged.set(attribute, value)
            destination[local] = merged
        else:
            destination[local] = copy.deepcopy(child)


_INDENT_HIERARCHY_GROUPS = (
    ("left", "start"),
    ("leftChars", "startChars"),
    ("right", "end"),
    ("rightChars", "endChars"),
    ("firstLine",),
    ("firstLineChars",),
    ("hanging",),
    ("hangingChars",),
)
_INDENT_CHARACTER_GROUPS = {
    "leftChars",
    "startChars",
    "rightChars",
    "endChars",
    "firstLineChars",
    "hangingChars",
}


def merge_style_hierarchy_indentation(
    inherited: Optional[etree._Element],
    current: etree._Element,
) -> etree._Element:
    """Apply Word's style-hierarchy rules for ``w:ind`` attributes.

    Word treats a zero character-unit value as a tombstone: it removes the
    related character indent inherited from an earlier style and then falls
    back to the corresponding point/twip value.  A non-zero character value
    remains authoritative over a point value.  First-line and hanging indents
    are mutually exclusive choices, so a later explicit choice also removes
    the opposite choice inherited from an earlier style.

    This helper resolves only an effective in-memory view.  The original XML
    keeps zero character-unit attributes because Word needs those tombstones
    when the style is applied to a real document.
    """

    merged = (
        copy.deepcopy(inherited)
        if inherited is not None
        else etree.Element(qn(W_NS, "ind"))
    )

    def raw(local: str) -> Optional[str]:
        return current.get(qn(W_NS, local))

    def nonzero(local: str) -> bool:
        value = _safe_int(raw(local))
        return value is not None and value != 0

    first_line_selected = (
        raw("firstLine") is not None or nonzero("firstLineChars")
    )
    hanging_selected = raw("hanging") is not None or nonzero("hangingChars")
    if first_line_selected and not hanging_selected:
        for local in ("hanging", "hangingChars"):
            merged.attrib.pop(qn(W_NS, local), None)
    elif hanging_selected and not first_line_selected:
        for local in ("firstLine", "firstLineChars"):
            merged.attrib.pop(qn(W_NS, local), None)
    elif first_line_selected and hanging_selected:
        for local in ("firstLine", "firstLineChars", "hanging", "hangingChars"):
            merged.attrib.pop(qn(W_NS, local), None)

    handled: Set[str] = set()
    for group in _INDENT_HIERARCHY_GROUPS:
        present = [(local, raw(local)) for local in group if raw(local) is not None]
        if not present:
            continue
        handled.update(group)
        for local in group:
            merged.attrib.pop(qn(W_NS, local), None)
        is_character_group = any(
            local in _INDENT_CHARACTER_GROUPS for local in group
        )
        for local, value in present:
            if is_character_group and _safe_int(value) == 0:
                continue
            merged.set(qn(W_NS, local), str(value))

    for attribute, value in current.attrib.items():
        if etree.QName(attribute).localname not in handled:
            merged.set(attribute, value)
    return merged


def _effective_style_properties(
    root: etree._Element,
    style_id: str,
) -> Tuple[Dict[str, etree._Element], Dict[str, etree._Element]]:
    """Resolve docDefaults + basedOn into explicit paragraph/run properties."""
    paragraph: Dict[str, etree._Element] = {}
    run: Dict[str, etree._Element] = {}
    _merge_property_map(
        paragraph,
        root.find("w:docDefaults/w:pPrDefault/w:pPr", namespaces=NS),
    )
    _merge_property_map(
        run,
        root.find("w:docDefaults/w:rPrDefault/w:rPr", namespaces=NS),
    )
    nodes = _nodes_by_style_id(root)
    chain: List[etree._Element] = []
    current = style_id
    seen: Set[str] = set()
    while current and current not in seen:
        seen.add(current)
        node = nodes.get(current)
        if node is None:
            break
        chain.append(node)
        current = _word_value(node.find("w:basedOn", namespaces=NS)) or ""
    for node in reversed(chain):
        _merge_property_map(paragraph, node.find("w:pPr", namespaces=NS))
        _merge_property_map(run, node.find("w:rPr", namespaces=NS))
    return paragraph, run


def _heading_indent_profile(
    indentation: Optional[etree._Element],
) -> Dict[str, str]:
    """Return a validated, stable manifest representation of ``w:ind``."""
    if indentation is None:
        return {}
    result: Dict[str, str] = {}
    for attribute in HEADING_INDENT_ATTRIBUTES:
        value = _safe_int(indentation.get(qn(W_NS, attribute)))
        if value is not None:
            result[attribute] = str(value)
    return result


def _normalize_heading_indent_profile(
    profile: Dict[str, str],
) -> Dict[str, str]:
    """Make a source heading indent reliably override list-level geometry.

    Numbering levels legitimately retain their list tab/hanging measurements.
    Word can expose those measurements as Paragraph > Left when the source
    paragraph's direct ``w:ind`` is discarded.  An explicit paragraph-level
    zero is therefore added only where the template did not provide its own
    horizontal value.  Intentional non-zero ``left``/``start`` values survive.
    """
    cleaned: Dict[str, str] = {}
    for attribute in HEADING_INDENT_ATTRIBUTES:
        value = _safe_int(profile.get(attribute))
        if value is not None:
            cleaned[attribute] = str(value)

    if not any(
        attribute in cleaned
        for attribute in ("left", "start", "leftChars", "startChars")
    ):
        cleaned["left"] = "0"

    has_nonzero_first_line = any(
        (_safe_int(cleaned.get(attribute)) or 0) != 0
        for attribute in ("firstLine", "firstLineChars")
    )
    if (
        not has_nonzero_first_line
        and not any(
            attribute in cleaned for attribute in ("hanging", "hangingChars")
        )
    ):
        cleaned["hanging"] = "0"

    # Rebuild in schema order so manifests and generated XML are deterministic.
    return {
        attribute: cleaned[attribute]
        for attribute in HEADING_INDENT_ATTRIBUTES
        if attribute in cleaned
    }


def _canonical_on_off_attribute(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "on"}:
        return "1"
    if normalized in {"0", "false", "off"}:
        return "0"
    return None


def _heading_spacing_profile(
    spacing: Optional[etree._Element],
) -> Dict[str, str]:
    if spacing is None:
        return {}
    result: Dict[str, str] = {}
    for attribute in HEADING_SPACING_INTEGER_ATTRIBUTES:
        value = _safe_int(spacing.get(qn(W_NS, attribute)))
        if value is not None:
            result[attribute] = str(value)
    for attribute in HEADING_SPACING_BOOLEAN_ATTRIBUTES:
        value = _canonical_on_off_attribute(
            spacing.get(qn(W_NS, attribute))
        )
        if value is not None:
            result[attribute] = value
    line_rule = spacing.get(qn(W_NS, "lineRule"))
    if line_rule in LINE_SPACING_RULES:
        result["lineRule"] = str(line_rule)
    return {
        attribute: result[attribute]
        for attribute in HEADING_SPACING_ATTRIBUTES
        if attribute in result
    }


def _heading_paragraph_property_profile(
    paragraph_properties: Optional[etree._Element],
) -> Dict[str, object]:
    """Return direct, text-free heading paragraph properties."""
    if paragraph_properties is None:
        return {}
    result: Dict[str, object] = {}
    indentation = paragraph_properties.find("w:ind", namespaces=NS)
    if indentation is not None:
        # An explicit empty w:ind is meaningful in the same way as the legacy
        # heading-indent collector: turn it into stable zero overrides rather
        # than confusing it with an absent direct property.
        result["ind"] = _normalize_heading_indent_profile(
            _heading_indent_profile(indentation)
        )
    spacing = _heading_spacing_profile(
        paragraph_properties.find("w:spacing", namespaces=NS)
    )
    if spacing:
        result["spacing"] = spacing
    alignment = _word_value(
        paragraph_properties.find("w:jc", namespaces=NS)
    )
    if alignment in PARAGRAPH_ALIGNMENT_VALUES:
        result["jc"] = alignment
    return result


def collect_heading_paragraph_properties(
    entries: Dict[str, bytes],
    catalog: StyleCatalog,
    style_ids: Iterable[str],
    part_names: Optional[Iterable[str]] = None,
    inherited_style_ids: Optional[Iterable[str]] = None,
    heading_authorities: Optional[Dict[int, str]] = None,
) -> Dict[str, Dict[str, object]]:
    """Resolve representative direct paragraph properties per heading style.

    Actual source paragraphs vote independently for indentation, spacing and
    alignment, including absence.  Independent votes preserve a stable indent
    even if one heading has exceptional spacing (and vice versa).  An observed
    absence is meaningful: it leaves the style and numbering level
    authoritative.  Generated Heading 4/5 styles inherit only indentation from
    their authoritative immediate parent; their spacing remains governed by
    the hierarchy-completion algorithm in styles.xml.
    """
    requested = {
        str(style_id)
        for style_id in style_ids
        if str(style_id) in catalog.styles
    }
    inherited = {str(style_id) for style_id in (inherited_style_ids or ())}
    selected_parts = (
        list(part_names)
        if part_names is not None
        else [name for name in sorted(entries) if is_content_part(name)]
    )
    votes: Dict[str, Dict[str, Counter[Optional[object]]]] = {}
    first_seen: Dict[Tuple[str, str, Optional[object]], int] = {}
    observed_values: Dict[Tuple[str, str, object], object] = {}
    ordinal = 0
    for name in selected_parts:
        if name not in entries or not is_content_part(name):
            continue
        root = parse_xml(entries[name], name)
        for paragraph in root.xpath("//w:p", namespaces=NS):
            style_id = _word_value(
                paragraph.find("w:pPr/w:pStyle", namespaces=NS)
            ) or catalog.fallback("paragraph")
            if style_id not in requested:
                ordinal += 1
                continue
            paragraph_properties = paragraph.find("w:pPr", namespaces=NS)
            profile = _heading_paragraph_property_profile(
                paragraph_properties
            )
            raw_indent = profile.get("ind")
            raw_spacing = profile.get("spacing")
            components: Dict[str, Tuple[Optional[object], Optional[object]]] = {
                "ind": (
                    tuple(raw_indent.items())
                    if isinstance(raw_indent, dict)
                    else None,
                    raw_indent if isinstance(raw_indent, dict) else None,
                ),
                "spacing": (
                    tuple(raw_spacing.items())
                    if isinstance(raw_spacing, dict)
                    else None,
                    raw_spacing if isinstance(raw_spacing, dict) else None,
                ),
                "jc": (
                    profile.get("jc")
                    if isinstance(profile.get("jc"), str)
                    else None,
                    profile.get("jc")
                    if isinstance(profile.get("jc"), str)
                    else None,
                ),
            }
            style_votes = votes.setdefault(style_id, {})
            for property_name, (signature, value) in components.items():
                style_votes.setdefault(property_name, Counter())[signature] += 1
                first_seen.setdefault(
                    (style_id, property_name, signature), ordinal
                )
                if signature is not None and value is not None:
                    observed_values.setdefault(
                        (style_id, property_name, signature),
                        copy.deepcopy(value),
                    )
            ordinal += 1

    result: Dict[str, Dict[str, object]] = {}
    ordered_styles = sorted(
        requested,
        key=lambda style_id: (
            catalog.resolved_outline.get(style_id)
            if catalog.resolved_outline.get(style_id) is not None
            else 99,
            style_id,
        ),
    )
    for style_id in ordered_styles:
        profile: Dict[str, object] = {}
        observed = False
        style_votes = votes.get(style_id)
        if style_votes:
            observed = True
            for property_name in ("ind", "spacing", "jc"):
                counter = style_votes[property_name]
                winning = min(
                    counter,
                    key=lambda signature: (
                        -counter[signature],
                        first_seen.get(
                            (style_id, property_name, signature), sys.maxsize
                        ),
                        repr(signature),
                    ),
                )
                if winning is not None:
                    profile[property_name] = copy.deepcopy(
                        observed_values[(style_id, property_name, winning)]
                    )

        if not observed and not profile and style_id in inherited:
            level = catalog.resolved_outline.get(style_id)
            parent_style = (
                heading_authorities.get(level - 1)
                if heading_authorities is not None and level is not None
                else None
            )
            if parent_style is None and level is not None:
                immediate = sorted(
                    candidate
                    for candidate in result
                    if catalog.resolved_outline.get(candidate) == level - 1
                )
                parent_style = immediate[0] if immediate else None
            if parent_style in result:
                parent_indent = result[parent_style].get("ind")
                if isinstance(parent_indent, dict):
                    profile = {"ind": copy.deepcopy(parent_indent)}

        if profile:
            result[style_id] = profile
    return result


def collect_heading_paragraph_indents(
    entries: Dict[str, bytes],
    catalog: StyleCatalog,
    style_ids: Iterable[str],
    part_names: Optional[Iterable[str]] = None,
    inherited_style_ids: Optional[Iterable[str]] = None,
    heading_authorities: Optional[Dict[int, str]] = None,
) -> Dict[str, Dict[str, str]]:
    """Compatibility view of the heading-property collector."""
    properties = collect_heading_paragraph_properties(
        entries,
        catalog,
        style_ids,
        part_names=part_names,
        inherited_style_ids=inherited_style_ids,
        heading_authorities=heading_authorities,
    )
    return {
        style_id: dict(indentation)
        for style_id, profile in properties.items()
        for indentation in [profile.get("ind")]
        if isinstance(indentation, dict)
    }


def heading_paragraph_indents_from_manifest(
    raw: object,
    catalog: StyleCatalog,
) -> Dict[str, Dict[str, str]]:
    """Validate the optional heading-indent field from a persisted style pack."""
    if not isinstance(raw, dict):
        return {}
    result: Dict[str, Dict[str, str]] = {}
    for raw_style_id, raw_profile in raw.items():
        style_id = str(raw_style_id)
        if style_id not in catalog.styles or not isinstance(raw_profile, dict):
            continue
        profile: Dict[str, str] = {}
        invalid = False
        for attribute, value in raw_profile.items():
            name = str(attribute)
            if name not in HEADING_INDENT_ATTRIBUTES:
                continue
            numeric = _safe_int(str(value))
            if numeric is None:
                invalid = True
                break
            profile[name] = str(numeric)
        if profile and not invalid:
            result[style_id] = _normalize_heading_indent_profile(profile)
    return result


def heading_paragraph_properties_from_manifest(
    raw: object,
    catalog: StyleCatalog,
    legacy_indents: object = None,
) -> Dict[str, Dict[str, object]]:
    """Validate direct heading properties and merge the legacy indent field.

    The pack loader performs strict structural validation.  This runtime
    decoder remains defensive as the direct CLI can call the engine with data
    assembled by older code.
    """
    result: Dict[str, Dict[str, object]] = {}
    if isinstance(raw, dict):
        for raw_style_id, raw_profile in raw.items():
            style_id = str(raw_style_id)
            info = catalog.styles.get(style_id)
            if (
                info is None
                or info.style_type != "paragraph"
                or not isinstance(raw_profile, dict)
            ):
                continue
            profile: Dict[str, object] = {}
            raw_indent = raw_profile.get("ind")
            if isinstance(raw_indent, dict):
                indentation: Dict[str, str] = {}
                valid = True
                for raw_attribute, raw_value in raw_indent.items():
                    attribute = str(raw_attribute)
                    if attribute not in HEADING_INDENT_ATTRIBUTES:
                        valid = False
                        break
                    value = _safe_int(str(raw_value))
                    if value is None:
                        valid = False
                        break
                    indentation[attribute] = str(value)
                if valid and indentation:
                    profile["ind"] = _normalize_heading_indent_profile(
                        indentation
                    )

            raw_spacing = raw_profile.get("spacing")
            if isinstance(raw_spacing, dict):
                spacing: Dict[str, str] = {}
                valid = True
                for raw_attribute, raw_value in raw_spacing.items():
                    attribute = str(raw_attribute)
                    if attribute in HEADING_SPACING_INTEGER_ATTRIBUTES:
                        value = _safe_int(str(raw_value))
                        if value is None:
                            valid = False
                            break
                        spacing[attribute] = str(value)
                    elif attribute in HEADING_SPACING_BOOLEAN_ATTRIBUTES:
                        value = _canonical_on_off_attribute(str(raw_value))
                        if value is None:
                            valid = False
                            break
                        spacing[attribute] = value
                    elif attribute == "lineRule":
                        value = str(raw_value)
                        if value not in LINE_SPACING_RULES:
                            valid = False
                            break
                        spacing[attribute] = value
                    else:
                        valid = False
                        break
                if valid and spacing:
                    profile["spacing"] = {
                        attribute: spacing[attribute]
                        for attribute in HEADING_SPACING_ATTRIBUTES
                        if attribute in spacing
                    }

            raw_alignment = raw_profile.get("jc")
            if isinstance(raw_alignment, str) and raw_alignment in PARAGRAPH_ALIGNMENT_VALUES:
                profile["jc"] = raw_alignment
            if profile:
                result[style_id] = profile

    legacy = heading_paragraph_indents_from_manifest(
        legacy_indents, catalog
    )
    for style_id, indentation in legacy.items():
        profile = result.setdefault(style_id, {})
        profile.setdefault("ind", dict(indentation))
    return result


def _property_container(
    local: str,
    properties: Dict[str, etree._Element],
    order: Sequence[str],
) -> etree._Element:
    parent = etree.Element(qn(W_NS, local))
    ranks = {name: index for index, name in enumerate(order)}
    for name, node in sorted(
        properties.items(), key=lambda item: (ranks.get(item[0], len(ranks)), item[0])
    ):
        parent.append(copy.deepcopy(node))
    return parent


def _set_property_value(
    properties: Dict[str, etree._Element],
    local: str,
    value: object,
) -> None:
    node = properties.get(local)
    if node is None:
        node = etree.Element(qn(W_NS, local))
        properties[local] = node
    node.set(qn(W_NS, "val"), str(value))


def _half_point_size(run: Dict[str, etree._Element]) -> Optional[int]:
    for key in ("sz", "szCs"):
        node = run.get(key)
        if node is not None:
            value = _safe_int(node.get(qn(W_NS, "val")))
            if value is not None and value > 0:
                return value
    return None


def _spacing_value(
    paragraph: Dict[str, etree._Element], attribute: str
) -> Optional[int]:
    spacing = paragraph.get("spacing")
    return (
        _safe_int(spacing.get(qn(W_NS, attribute)))
        if spacing is not None
        else None
    )


def _deeper_size(
    previous_previous: Optional[int],
    previous: Optional[int],
    body: Optional[int],
    level: int,
) -> int:
    prior = previous or ((body or 22) + 2)
    raw_step = (
        previous_previous - prior
        if previous_previous is not None and previous_previous > prior
        else 2
    )
    # Half-point units: preserve a clear source progression (for example
    # 21/18/15 pt becomes 12 pt) while bounding pathological templates.  The
    # body-size floor below remains the final safety guard.
    step = max(1, min(12, raw_step))
    floor = (body + 1 if level == 3 else body) if body is not None else 16
    return max(floor, prior - step)


def _deeper_spacing(
    previous_previous: Optional[int],
    previous: Optional[int],
    floor: int,
    default_step: int,
) -> int:
    prior = previous if previous is not None else floor
    delta = (
        prior - previous_previous
        if previous_previous is not None
        else -default_step
    )
    # A deeper heading should not gain more surrounding whitespace merely
    # because an upstream template has an irregular value.
    delta = min(0, max(-120, delta))
    return max(floor, prior + delta)


def _heading_style_id_for_completion(
    root: etree._Element,
    catalog: StyleCatalog,
    level: int,
) -> str:
    nodes = _nodes_by_style_id(root)
    candidate = catalog.heading_by_level.get(level)
    if (
        candidate
        and candidate in nodes
        and nodes[candidate].get(qn(W_NS, "type"), "paragraph") == "paragraph"
    ):
        return candidate
    preferred = "Heading%d" % (level + 1)
    existing = nodes.get(preferred)
    if existing is None or existing.get(qn(W_NS, "type"), "paragraph") == "paragraph":
        return preferred
    base = "InferredHeading%d" % (level + 1)
    candidate = base
    suffix = 2
    while candidate in nodes:
        candidate = "%s%d" % (base, suffix)
        suffix += 1
    return candidate


def _insert_style_node(root: etree._Element, node: etree._Element) -> None:
    ext_list = root.find("w:extLst", namespaces=NS)
    insertion = root.index(ext_list) if ext_list is not None else len(root)
    root.insert(insertion, node)


TABLE_NO_FIRST_LINE_STYLE_PREFIX = "WordFormatTableNoIndent"
TABLE_NO_FIRST_LINE_STYLE_NAME = "表格正文（无首行缩进）"


def _is_generated_table_no_indent_style(
    node: etree._Element,
    base_style_id: str,
) -> bool:
    """Return whether ``node`` is one of our stable table paragraph styles."""
    if node.get(qn(W_NS, "type"), "paragraph") != "paragraph":
        return False
    name = node.find("w:name", namespaces=NS)
    based_on = node.find("w:basedOn", namespaces=NS)
    next_style = node.find("w:next", namespaces=NS)
    indentation = node.find("w:pPr/w:ind", namespaces=NS)
    style_id = node.get(qn(W_NS, "styleId"))
    return bool(
        style_id
        and name is not None
        and name.get(qn(W_NS, "val"), "").startswith(
            TABLE_NO_FIRST_LINE_STYLE_NAME
        )
        and based_on is not None
        and based_on.get(qn(W_NS, "val")) == base_style_id
        and next_style is not None
        and next_style.get(qn(W_NS, "val")) == style_id
        and indentation is not None
        and indentation.get(qn(W_NS, "firstLine")) == "0"
        and indentation.get(qn(W_NS, "firstLineChars")) == "0"
    )


def _new_table_no_indent_style(
    style_id: str,
    base_style_id: str,
    display_name: str,
) -> etree._Element:
    """Create a paragraph style that inherits everything except first-line indent."""
    style = etree.Element(qn(W_NS, "style"))
    style.set(qn(W_NS, "type"), "paragraph")
    style.set(qn(W_NS, "customStyle"), "1")
    style.set(qn(W_NS, "styleId"), style_id)

    name = etree.SubElement(style, qn(W_NS, "name"))
    name.set(qn(W_NS, "val"), display_name)
    based_on = etree.SubElement(style, qn(W_NS, "basedOn"))
    based_on.set(qn(W_NS, "val"), base_style_id)
    # Word uses w:next when Enter creates another paragraph.  Pointing back to
    # this style prevents a newly-added row/cell paragraph from falling back to
    # an indented Normal style after the direct zero override is discarded.
    next_style = etree.SubElement(style, qn(W_NS, "next"))
    next_style.set(qn(W_NS, "val"), style_id)
    priority = etree.SubElement(style, qn(W_NS, "uiPriority"))
    priority.set(qn(W_NS, "val"), "99")
    etree.SubElement(style, qn(W_NS, "semiHidden"))

    paragraph_properties = etree.SubElement(style, qn(W_NS, "pPr"))
    indentation = etree.SubElement(paragraph_properties, qn(W_NS, "ind"))
    indentation.set(qn(W_NS, "firstLine"), "0")
    indentation.set(qn(W_NS, "firstLineChars"), "0")
    return style


def ensure_table_no_first_line_indent_styles(
    entries: Dict[str, bytes],
    catalog: StyleCatalog,
) -> Dict[str, str]:
    """Add stable zero-first-line variants for indented source body styles.

    Direct ``w:ind`` zeroes fix existing table paragraphs, but Word can discard
    direct formatting when a row is added, pasted or rebuilt.  The generated
    paragraph style inherits the source style's font, spacing and alignment and
    changes only first-line indentation.  A map from base style ID to generated
    style ID is returned for the content-cleaning pass.
    """
    base_style_ids = sorted(
        style_id
        for style_id in catalog.two_character_first_line_styles
        if style_id in catalog.styles
        and catalog.styles[style_id].style_type == "paragraph"
    )
    if not base_style_ids:
        return {}

    _rels, roles = collect_format_relationships(entries)
    style_parts: List[str] = []
    for role in ("styles", "stylesWithEffects"):
        record = roles.get(role)
        fallback = ROLE_FALLBACK_PARTS[role]
        part = record[0] if record is not None else fallback
        if part in entries and part not in style_parts:
            style_parts.append(part)
    if not style_parts:
        return {}

    primary_part = style_parts[0]
    primary_root = parse_xml(entries[primary_part], primary_part)
    primary_nodes = _nodes_by_style_id(primary_root)
    mapping: Dict[str, str] = {}

    # Bind each generated ID to its base style instead of assigning IDs by the
    # current sort order.  This matters when a document is processed by two
    # different format libraries: an exact style-ID match must never redirect
    # a former BodyB paragraph to a new wrapper based on BodyA merely because
    # the two libraries contain different sets of indented body styles.
    for base_style_id in base_style_ids:
        base_digest = hashlib.sha256(
            base_style_id.encode("utf-8")
        ).hexdigest()[:12]
        preferred = "%s_%s" % (
            TABLE_NO_FIRST_LINE_STYLE_PREFIX,
            base_digest,
        )
        candidate = preferred
        existing = primary_nodes.get(candidate)
        if existing is not None and _is_generated_table_no_indent_style(
            existing, base_style_id
        ):
            mapping[base_style_id] = candidate
            continue
        suffix = 2
        while candidate in primary_nodes:
            candidate = "%s_%d" % (preferred, suffix)
            suffix += 1

        display_name = TABLE_NO_FIRST_LINE_STYLE_NAME
        if len(base_style_ids) > 1:
            display_name = "%s - %s" % (
                display_name,
                catalog.styles[base_style_id].name,
            )
        generated = _new_table_no_indent_style(
            candidate,
            base_style_id,
            display_name,
        )
        _insert_style_node(primary_root, generated)
        primary_nodes[candidate] = generated
        mapping[base_style_id] = candidate

    entries[primary_part] = serialize_xml(primary_root)

    # Keep stylesWithEffects aligned with the primary style definitions.  Some
    # versions of Word consult this compatibility part while editing even
    # though styles.xml remains authoritative for display.
    for part in style_parts[1:]:
        root = parse_xml(entries[part], part)
        nodes = _nodes_by_style_id(root)
        for base_style_id, generated_style_id in mapping.items():
            if base_style_id not in nodes and base_style_id in primary_nodes:
                _insert_style_node(
                    root, copy.deepcopy(primary_nodes[base_style_id])
                )
                nodes = _nodes_by_style_id(root)
            generated = copy.deepcopy(primary_nodes[generated_style_id])
            existing = nodes.get(generated_style_id)
            if existing is not None:
                root.replace(existing, generated)
            else:
                _insert_style_node(root, generated)
            nodes = _nodes_by_style_id(root)
        entries[part] = serialize_xml(root)

    return mapping


def _synthesize_style_in_part(
    root: etree._Element,
    style_id: str,
    level: int,
    base_style_id: str,
    body_style_id: str,
    size: int,
    before: int,
    after: int,
) -> None:
    nodes = _nodes_by_style_id(root)
    base_node = nodes.get(base_style_id)
    if base_node is None:
        raise TransferError("无法找到用于推导标题的上一级样式：%s" % base_style_id)
    existing = nodes.get(style_id)
    if existing is not None and existing.get(qn(W_NS, "type"), "paragraph") != "paragraph":
        raise TransferError("标题补全样式 ID 与非段落样式冲突：%s" % style_id)

    style_node = copy.deepcopy(base_node)
    style_node.set(qn(W_NS, "styleId"), style_id)
    style_node.set(qn(W_NS, "type"), "paragraph")
    style_node.attrib.pop(qn(W_NS, "default"), None)

    name_node = etree.Element(qn(W_NS, "name"))
    name_node.set(qn(W_NS, "val"), "heading %d" % (level + 1))
    _replace_ordered_child(style_node, "name", name_node, STYLE_CHILD_ORDER)

    based_on = etree.Element(qn(W_NS, "basedOn"))
    based_on.set(qn(W_NS, "val"), body_style_id)
    _replace_ordered_child(style_node, "basedOn", based_on, STYLE_CHILD_ORDER)
    next_node = etree.Element(qn(W_NS, "next"))
    next_node.set(qn(W_NS, "val"), body_style_id)
    _replace_ordered_child(style_node, "next", next_node, STYLE_CHILD_ORDER)

    # Linked character styles are optional and often contain independent,
    # unused defaults.  Removing the inherited Heading 3 link ensures the
    # generated paragraph style is self-contained and deterministic.
    _replace_ordered_child(style_node, "link", None, STYLE_CHILD_ORDER)
    for unsafe_metadata in ("autoRedefine", "semiHidden", "rsid"):
        _replace_ordered_child(style_node, unsafe_metadata, None, STYLE_CHILD_ORDER)
    ui_priority = etree.Element(qn(W_NS, "uiPriority"))
    ui_priority.set(qn(W_NS, "val"), "9")
    _replace_ordered_child(style_node, "uiPriority", ui_priority, STYLE_CHILD_ORDER)
    _replace_ordered_child(
        style_node,
        "unhideWhenUsed",
        etree.Element(qn(W_NS, "unhideWhenUsed")),
        STYLE_CHILD_ORDER,
    )
    _replace_ordered_child(
        style_node,
        "qFormat",
        etree.Element(qn(W_NS, "qFormat")),
        STYLE_CHILD_ORDER,
    )

    paragraph, run = _effective_style_properties(root, base_style_id)
    paragraph.pop("numPr", None)
    _set_property_value(paragraph, "keepNext", 1)
    _set_property_value(paragraph, "keepLines", 1)
    _set_property_value(paragraph, "outlineLvl", level)
    spacing = paragraph.get("spacing")
    if spacing is None:
        spacing = etree.Element(qn(W_NS, "spacing"))
        paragraph["spacing"] = spacing
    spacing.set(qn(W_NS, "before"), str(before))
    spacing.set(qn(W_NS, "after"), str(after))

    _set_property_value(run, "sz", size)
    _set_property_value(run, "szCs", size)
    if "b" in run and "bCs" not in run:
        run["bCs"] = copy.deepcopy(run["b"])
        run["bCs"].tag = qn(W_NS, "bCs")
    if "i" in run and "iCs" not in run:
        run["iCs"] = copy.deepcopy(run["i"])
        run["iCs"].tag = qn(W_NS, "iCs")
    _replace_ordered_child(
        style_node,
        "pPr",
        _property_container("pPr", paragraph, PPR_CHILD_ORDER),
        STYLE_CHILD_ORDER,
    )
    _replace_ordered_child(
        style_node,
        "rPr",
        _property_container("rPr", run, RPR_CHILD_ORDER),
        STYLE_CHILD_ORDER,
    )

    if existing is not None:
        root.replace(existing, style_node)
    else:
        _insert_style_node(root, style_node)


def _extend_level_text(pattern: Optional[str], previous_level: int) -> str:
    next_placeholder = "%%%d" % (previous_level + 2)
    current_placeholder = "%%%d" % (previous_level + 1)
    if not pattern or current_placeholder not in pattern:
        return ".".join("%%%d" % index for index in range(1, previous_level + 3))
    current_position = pattern.rfind(current_placeholder)
    current_end = current_position + len(current_placeholder)
    separator = "."
    if previous_level >= 1:
        prior_placeholder = "%%%d" % previous_level
        prior_position = pattern.rfind(prior_placeholder, 0, current_position)
        if prior_position >= 0:
            candidate = pattern[
                prior_position + len(prior_placeholder) : current_position
            ]
            if candidate:
                separator = candidate
    return pattern[:current_end] + separator + next_placeholder + pattern[current_end:]


def _set_level_child_value(
    level_node: etree._Element,
    local: str,
    value: object,
) -> None:
    existing = level_node.find("w:%s" % local, namespaces=NS)
    if existing is None:
        existing = etree.Element(qn(W_NS, local))
        order = (
            "start",
            "numFmt",
            "lvlRestart",
            "pStyle",
            "isLgl",
            "suff",
            "lvlText",
            "lvlPicBulletId",
            "legacy",
            "lvlJc",
            "pPr",
            "rPr",
        )
        _ordered_insert(level_node, existing, order)
    existing.set(qn(W_NS, "val"), str(value))


def _level_numeric_attribute(
    level_node: Optional[etree._Element],
    path: str,
    attribute: str,
) -> Optional[int]:
    if level_node is None:
        return None
    node = level_node.find(path, namespaces=NS)
    return _safe_int(node.get(qn(W_NS, attribute))) if node is not None else None


def _extrapolate_level_geometry(
    previous_previous: Optional[etree._Element],
    previous: etree._Element,
    generated: etree._Element,
) -> None:
    generated_ind = generated.find("w:pPr/w:ind", namespaces=NS)
    if generated_ind is not None:
        for attribute in ("left", "start", "hanging", "firstLine"):
            prior = _level_numeric_attribute(previous, "w:pPr/w:ind", attribute)
            if prior is None:
                continue
            older = _level_numeric_attribute(
                previous_previous, "w:pPr/w:ind", attribute
            )
            default_delta = 360 if attribute in {"left", "start"} else 0
            delta = prior - older if older is not None else default_delta
            generated_ind.set(
                qn(W_NS, attribute), str(min(4320, max(0, prior + delta)))
            )

    generated_tab = generated.find("w:pPr/w:tabs/w:tab", namespaces=NS)
    previous_tab = previous.find("w:pPr/w:tabs/w:tab", namespaces=NS)
    older_tab = (
        previous_previous.find("w:pPr/w:tabs/w:tab", namespaces=NS)
        if previous_previous is not None
        else None
    )
    if generated_tab is not None and previous_tab is not None:
        prior = _safe_int(previous_tab.get(qn(W_NS, "pos")))
        older = _safe_int(older_tab.get(qn(W_NS, "pos"))) if older_tab is not None else None
        if prior is not None:
            delta = prior - older if older is not None else 360
            generated_tab.set(
                qn(W_NS, "pos"), str(min(4320, max(0, prior + delta)))
            )


def _insert_numbering_level(
    abstract: etree._Element,
    generated: etree._Element,
) -> None:
    level = _safe_int(generated.get(qn(W_NS, "ilvl"))) or 0
    insertion = len(abstract)
    for index, child in enumerate(abstract):
        if local_name(child) != "lvl":
            continue
        child_level = _safe_int(child.get(qn(W_NS, "ilvl")))
        if child_level is not None and child_level > level:
            insertion = index
            break
    abstract.insert(insertion, generated)


def _materialized_numbering_level(
    abstract: etree._Element,
    num_node: etree._Element,
    level: int,
) -> Optional[etree._Element]:
    base = _level_node(abstract, level)
    override = _override_for_level(num_node, level)
    override_level = (
        override.find("w:lvl", namespaces=NS) if override is not None else None
    )
    authority = override_level if override_level is not None else base
    if authority is None:
        return None
    result = copy.deepcopy(authority)
    result.set(qn(W_NS, "ilvl"), str(level))
    if override is not None:
        start_override = _word_value(
            override.find("w:startOverride", namespaces=NS)
        )
        if start_override is not None:
            _set_level_child_value(result, "start", start_override)
    return result


def _repeatable_numbering_pattern(
    base_rules: Sequence[HeadingNumberingRule],
) -> Optional[str]:
    pattern = base_rules[2].level_text
    if not pattern:
        return None
    positions = [pattern.find("%%%d" % index) for index in (1, 2, 3)]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        return None
    end1 = positions[0] + 2
    end2 = positions[1] + 2
    end3 = positions[2] + 2
    separator12 = pattern[end1 : positions[1]]
    separator23 = pattern[end2 : positions[2]]
    prefix = pattern[: positions[0]]
    suffix = pattern[end3:]
    if not separator12 or separator12 != separator23:
        return None
    # Punctuation wrappers such as "(%1.%2.%3)" are repeatable.  Semantic
    # words/units such as "第…章/节/款" are not: the next unit name cannot be
    # inferred safely from typography alone.
    if any(re.search(r"[\w\u3400-\u9fff]", value) for value in (prefix, suffix, separator12)):
        return None
    return pattern


def _heading_numbering_levels_are_hierarchical(
    base_rules: Sequence[HeadingNumberingRule],
) -> bool:
    """Return whether H1-H3 describe one parent-aware outline sequence.

    Some Word documents save each heading level under a different ``numId``
    even though Heading 2 explicitly contains ``%1.%2`` and Heading 3
    contains ``%1.%2.%3``.  Those definitions are visually compatible but
    their counters are independent until they are materialized into one list.
    Requiring the exact parent placeholders keeps that repair narrow: three
    unrelated single-level lists are never joined merely because they happen
    to use decimal numbers.
    """
    if len(base_rules) != 3:
        return False
    for level, rule in enumerate(base_rules):
        if rule.level != level or not rule.level_text:
            return False
        placeholders = [
            int(value)
            for value in re.findall(r"%([1-9])", rule.level_text)
        ]
        if placeholders != list(range(1, level + 2)):
            return False
    return True


def _numbering_nsids(root: etree._Element) -> Set[str]:
    return {
        value.upper()
        for value in root.xpath("./w:abstractNum/w:nsid/@w:val", namespaces=NS)
    }


def _assign_independent_numbering_identity(
    abstract: etree._Element,
    occupied_nsids: Set[str],
) -> None:
    """Give a cloned list its own Word identity, not just a new numeric ID.

    Word can coalesce abstract lists with the same nsid even when their
    abstractNumId values differ.  Reusing an H1-H3 identity for an extended
    H1-H5 definition makes the additional levels disappear in Word.  Only
    the clone's identity changes; authored levels, counters and tmpl stay
    untouched.  Stable content-based allocation also keeps repeated builds
    reproducible and reserves identities for clones not yet in the tree.
    """
    seed = hashlib.sha256(b"Forma independent numbering\0" + serialize_xml(abstract)).digest()
    candidate = int.from_bytes(seed[:4], "big")
    while candidate == 0 or "%08X" % candidate in occupied_nsids:
        candidate = (candidate + 1) % (1 << 32)
    identity = "%08X" % candidate
    occupied_nsids.add(identity)
    node = abstract.find("w:nsid", namespaces=NS)
    if node is None:
        node = etree.Element(qn(W_NS, "nsid"))
        abstract.insert(0, node)
    node.set(qn(W_NS, "val"), identity)


def _extend_heading_numbering(
    entries: Dict[str, bytes],
    authority: Dict[int, str],
    inferred: Dict[int, str],
    rules: Dict[str, HeadingNumberingRule],
) -> Tuple[Dict[str, HeadingNumberingRule], bool, Optional[str]]:
    result = dict(rules)
    generated_levels = sorted(
        level for level in inferred if 3 <= level <= 8
    )
    base_rules = [result.get(authority[level]) for level in (0, 1, 2)]
    present = [rule for rule in base_rules if rule is not None]
    if not present:
        return result, False, None
    if (
        len(present) != 3
        or any(rule.level != level for level, rule in enumerate(base_rules) if rule is not None)
        or not _heading_numbering_levels_are_hierarchical(present)
    ):
        return (
            result,
            False,
            "标题一至标题三的编号规则不一致，已补全标题样式，但未自动扩展更深层编号。",
        )

    repeatable_pattern = _repeatable_numbering_pattern(
        [rule for rule in base_rules if rule is not None]
    )
    if repeatable_pattern is None:
        return (
            result,
            False,
            "标题一至标题三的编号文字含有无法可靠推导的语义或模式，已保留现有编号，未自动编造更深层编号。",
        )

    numbering_root, abstract_by_id, num_by_id, numbering_styles = _numbering_index(entries)
    if numbering_root is None:
        return result, False, "源文件缺少可扩展的多级编号定义。"
    first_generated_level = generated_levels[0] if generated_levels else 3
    if generated_levels and generated_levels != list(
        range(first_generated_level, generated_levels[-1] + 1)
    ):
        return result, False, "需要补全的标题编号层级不连续。"

    # Keep every existing level before the first generated one.  This matters
    # when an actual template already authored H4/H5 and a one-level demotion
    # only needs H6: those real levels must remain byte-faithful rather than be
    # re-inferred from H3.
    materialized_base: List[
        Tuple[int, HeadingNumberingRule, etree._Element, etree._Element]
    ] = []
    for level in range(first_generated_level):
        style_id = authority.get(level)
        rule = result.get(style_id or "")
        if style_id is None or rule is None or rule.level != level:
            return (
                result,
                False,
                "源文件缺少可衔接到标题%d的第%d级编号定义。"
                % (first_generated_level + 1, level + 1),
            )
        num_node = num_by_id.get(rule.num_id)
        abstract = (
            _abstract_for_num(
                num_node, abstract_by_id, num_by_id, numbering_styles
            )
            if num_node is not None
            else None
        )
        if num_node is None or abstract is None:
            return result, False, "源文件的多级编号定义无法解析。"
        materialized = _materialized_numbering_level(
            abstract, num_node, level
        )
        if materialized is None:
            return result, False, "源文件的多级编号缺少可复制的前置层级。"
        materialized_base.append((level, rule, abstract, materialized))
    new_abstract_id = str(
        max(
            [_safe_int(value) or 0 for value in abstract_by_id] + [0]
        )
        + 1
    )
    new_num_id = str(
        max([_safe_int(value) or 0 for value in num_by_id] + [0]) + 1
    )
    # The deepest existing level is the best metadata authority for a
    # multi-level list.  Every concrete preceding level is still copied from
    # its own numId below, so source-authored typography and geometry stay
    # byte-faithful even when Word split the hierarchy across list instances.
    generated_abstract = copy.deepcopy(materialized_base[-1][2])
    generated_abstract.set(qn(W_NS, "abstractNumId"), new_abstract_id)
    for child in list(generated_abstract):
        if local_name(child) in {"lvl", "numStyleLink", "styleLink"}:
            generated_abstract.remove(child)
    generated_result = dict(result)
    preserved_start_overrides: Dict[int, int] = {}

    for level, rule, abstract, materialized in materialized_base:
        source_num = num_by_id[rule.num_id]
        source_override = _override_for_level(source_num, level)
        source_start_override = (
            _safe_int(
                _word_value(
                    source_override.find("w:startOverride", namespaces=NS)
                )
            )
            if source_override is not None
            else None
        )
        if source_start_override is not None:
            preserved_start_overrides[level] = source_start_override
            # _materialized_numbering_level exposes an override as w:start.
            # The new independent list must instead keep the abstract level's
            # authored start and reproduce the concrete startOverride below.
            source_override_level = source_override.find(
                "w:lvl", namespaces=NS
            )
            source_level = (
                source_override_level
                if source_override_level is not None
                else _level_node(abstract, level)
            )
            authored_start = _word_value(
                source_level.find("w:start", namespaces=NS)
                if source_level is not None
                else None
            )
            start_node = materialized.find("w:start", namespaces=NS)
            if authored_start is None:
                if start_node is not None:
                    materialized.remove(start_node)
            else:
                _set_level_child_value(materialized, "start", authored_start)
        materialized.attrib.pop(qn(W_NS, "tentative"), None)
        _set_level_child_value(materialized, "pStyle", authority[level])
        _insert_numbering_level(generated_abstract, materialized)
        generated_result[authority[level]] = HeadingNumberingRule(
            style_id=authority[level],
            num_id=new_num_id,
            level=level,
            number_format=_word_value(
                materialized.find("w:numFmt", namespaces=NS)
            ),
            level_text=_word_value(
                materialized.find("w:lvlText", namespaces=NS)
            ),
            start=(
                source_start_override
                if source_start_override is not None
                else _safe_int(
                    _word_value(materialized.find("w:start", namespaces=NS))
                )
            ),
        )

    shared_label_fonts = _shared_number_label_fonts(
        [item[3] for item in materialized_base[:2]]
    )
    previous_pattern = (
        _word_value(
            materialized_base[-1][3].find("w:lvlText", namespaces=NS)
        )
        or repeatable_pattern
    )
    for level in generated_levels:
        previous = _level_node(generated_abstract, level - 1)
        if previous is None:
            return result, False, "源文件的多级编号缺少上一级定义。"
        previous_previous = _level_node(generated_abstract, level - 2)
        generated = copy.deepcopy(previous)
        generated.set(qn(W_NS, "ilvl"), str(level))
        generated.attrib.pop(qn(W_NS, "tentative"), None)
        # Never clone an exceptional H3/Hn size, colour or emphasis.  Preserve
        # only the stable H1/H2 list-font rule; every other marker property is
        # inherited from the generated heading's own paragraph style.
        generated_run_properties = generated.find("w:rPr", namespaces=NS)
        if generated_run_properties is not None:
            generated.remove(generated_run_properties)
        if shared_label_fonts is not None:
            generated_run_properties = etree.Element(qn(W_NS, "rPr"))
            generated_run_properties.append(copy.deepcopy(shared_label_fonts))
            generated.append(generated_run_properties)
        _set_level_child_value(generated, "start", 1)
        _set_level_child_value(generated, "pStyle", inferred[level])
        previous_pattern = _extend_level_text(previous_pattern, level - 1)
        _set_level_child_value(generated, "lvlText", previous_pattern)
        restart = generated.find("w:lvlRestart", namespaces=NS)
        if restart is not None:
            restart.set(qn(W_NS, "val"), str(level))
        _extrapolate_level_geometry(previous_previous, previous, generated)
        _insert_numbering_level(generated_abstract, generated)
        generated_result[inferred[level]] = HeadingNumberingRule(
            style_id=inferred[level],
            num_id=new_num_id,
            level=level,
            number_format=_word_value(generated.find("w:numFmt", namespaces=NS)),
            level_text=previous_pattern,
            start=1,
        )

    first_num = numbering_root.find("w:num", namespaces=NS)
    abstract_insertion = (
        numbering_root.index(first_num) if first_num is not None else len(numbering_root)
    )
    _assign_independent_numbering_identity(
        generated_abstract, _numbering_nsids(numbering_root)
    )
    numbering_root.insert(abstract_insertion, generated_abstract)
    generated_num = etree.Element(qn(W_NS, "num"))
    generated_num.set(qn(W_NS, "numId"), new_num_id)
    abstract_reference = etree.SubElement(
        generated_num, qn(W_NS, "abstractNumId")
    )
    abstract_reference.set(qn(W_NS, "val"), new_abstract_id)
    for level, start_value in sorted(preserved_start_overrides.items()):
        level_override = etree.SubElement(
            generated_num, qn(W_NS, "lvlOverride")
        )
        level_override.set(qn(W_NS, "ilvl"), str(level))
        start_override = etree.SubElement(
            level_override, qn(W_NS, "startOverride")
        )
        start_override.set(qn(W_NS, "val"), str(start_value))
    cleanup = numbering_root.find("w:numIdMacAtCleanup", namespaces=NS)
    num_insertion = (
        numbering_root.index(cleanup) if cleanup is not None else len(numbering_root)
    )
    numbering_root.insert(num_insertion, generated_num)

    _rels, roles = collect_format_relationships(entries)
    numbering_record = roles.get("numbering")
    numbering_part = (
        numbering_record[0]
        if numbering_record is not None
        else ROLE_FALLBACK_PARTS["numbering"]
    )
    entries[numbering_part] = serialize_xml(numbering_root)
    return generated_result, bool(inferred), None


def complete_heading_hierarchy(
    entries: Dict[str, bytes],
    catalog: StyleCatalog,
    used_heading_by_level: Dict[int, str],
    heading_numbering: Optional[Dict[str, HeadingNumberingRule]] = None,
    max_level: int = 4,
    extend_numbering: bool = True,
) -> HeadingCompletionResult:
    """Synthesize missing Heading 4..N styles from the source's real H1-H3.

    Normal pack creation stops at Heading 5.  Applying the optional one-level
    demotion can request deeper styles through Word's Heading 9 limit.  The
    pass deliberately ignores unused gallery definitions and runs only when
    levels 1–3 are authoritative, so a sparse source cannot accidentally
    invent an unsupported hierarchy.
    """
    rules = dict(heading_numbering or {})
    max_level = min(8, max(3, int(max_level)))
    if not all(level in used_heading_by_level for level in (0, 1, 2)):
        return HeadingCompletionResult(heading_numbering=rules)
    missing_levels = [
        level
        for level in range(3, max_level + 1)
        if level not in used_heading_by_level
    ]
    if not missing_levels:
        return HeadingCompletionResult(heading_numbering=rules)

    _rels, roles = collect_format_relationships(entries)
    style_parts: List[str] = []
    for role in ("styles", "stylesWithEffects"):
        record = roles.get(role)
        fallback = ROLE_FALLBACK_PARTS[role]
        part = record[0] if record is not None else fallback
        if part in entries and part not in style_parts:
            style_parts.append(part)
    if not style_parts:
        return HeadingCompletionResult(
            heading_numbering=rules,
            warnings=["源文件没有可写入的样式部件，无法自动补全更深层标题。"],
        )

    primary_root = parse_xml(entries[style_parts[0]], style_parts[0])
    inferred: Dict[int, str] = {
        level: _heading_style_id_for_completion(primary_root, catalog, level)
        for level in missing_levels
    }
    authority = dict(used_heading_by_level)
    authority.update(inferred)

    for part in style_parts:
        root = parse_xml(entries[part], part)
        nodes = _nodes_by_style_id(root)
        if part != style_parts[0]:
            # stylesWithEffects is frequently a stale compatibility snapshot
            # (notably after python-docx or other non-Word editors change the
            # primary styles.xml).  The user-visible source authority and the
            # app preview both come from styles.xml, so copy the deterministic
            # generated nodes into the companion part instead of extrapolating
            # from its potentially unrelated dormant defaults.
            primary_nodes = _nodes_by_style_id(primary_root)
            for level in missing_levels:
                style_id = inferred[level]
                generated = copy.deepcopy(primary_nodes[style_id])
                existing = nodes.get(style_id)
                if existing is not None:
                    root.replace(existing, generated)
                else:
                    _insert_style_node(root, generated)
                nodes = _nodes_by_style_id(root)
            entries[part] = serialize_xml(root)
            continue
        # stylesWithEffects normally mirrors styles.xml.  If it does not,
        # copy the real H1-H3 authorities from the primary style part first.
        primary_nodes = _nodes_by_style_id(primary_root)
        for level in (0, 1, 2):
            style_id = authority[level]
            if style_id not in nodes and style_id in primary_nodes:
                _insert_style_node(root, copy.deepcopy(primary_nodes[style_id]))
                nodes = _nodes_by_style_id(root)

        body_style = catalog.fallback("paragraph") or "Normal"
        _body_paragraph, body_run = _effective_style_properties(root, body_style)
        body_size = _half_point_size(body_run)
        part_authority = dict(used_heading_by_level)
        for level in missing_levels:
            base_level = level - 1
            base_style_id = part_authority.get(base_level) or authority[base_level]
            previous_paragraph, previous_run = _effective_style_properties(
                root, base_style_id
            )
            older_style_id = part_authority.get(level - 2) or authority.get(level - 2)
            older_paragraph: Dict[str, etree._Element] = {}
            older_run: Dict[str, etree._Element] = {}
            if older_style_id:
                older_paragraph, older_run = _effective_style_properties(
                    root, older_style_id
                )
            size = _deeper_size(
                _half_point_size(older_run),
                _half_point_size(previous_run),
                body_size,
                level,
            )
            before = _deeper_spacing(
                _spacing_value(older_paragraph, "before"),
                _spacing_value(previous_paragraph, "before"),
                40,
                40,
            )
            after = _deeper_spacing(
                _spacing_value(older_paragraph, "after"),
                _spacing_value(previous_paragraph, "after"),
                0,
                20,
            )
            _synthesize_style_in_part(
                root,
                inferred[level],
                level,
                base_style_id,
                body_style,
                size,
                before,
                after,
            )
            part_authority[level] = inferred[level]
        entries[part] = serialize_xml(root)
        if part == style_parts[0]:
            primary_root = root

    if extend_numbering:
        extended_rules, numbering_extended, numbering_warning = _extend_heading_numbering(
            entries, authority, inferred, rules
        )
        align_heading_style_numbering(
            entries,
            set(used_heading_by_level.values()) | set(inferred.values()),
            extended_rules,
        )
    else:
        extended_rules = rules
        numbering_extended = False
        numbering_warning = None
    warnings = [numbering_warning] if numbering_warning else []
    return HeadingCompletionResult(
        inferred_styles=inferred,
        heading_numbering=extended_rules,
        numbering_extended=numbering_extended,
        warnings=warnings,
    )


def _numbering_index(
    entries: Dict[str, bytes],
) -> Tuple[
    Optional[etree._Element],
    Dict[str, etree._Element],
    Dict[str, etree._Element],
    Dict[str, etree._Element],
]:
    _rels, roles = collect_format_relationships(entries)
    numbering_record = roles.get("numbering")
    numbering_part = (
        numbering_record[0]
        if numbering_record is not None
        else ROLE_FALLBACK_PARTS["numbering"]
    )
    if numbering_part not in entries:
        return None, {}, {}, {}
    root = parse_xml(entries[numbering_part], numbering_part)
    abstract_by_id = {
        str(node.get(qn(W_NS, "abstractNumId"))): node
        for node in root.findall("w:abstractNum", namespaces=NS)
        if node.get(qn(W_NS, "abstractNumId")) is not None
    }
    num_by_id = {
        str(node.get(qn(W_NS, "numId"))): node
        for node in root.findall("w:num", namespaces=NS)
        if node.get(qn(W_NS, "numId")) is not None
    }
    styles_by_id: Dict[str, etree._Element] = {}
    if "word/styles.xml" in entries:
        styles_root = parse_xml(entries["word/styles.xml"], "word/styles.xml")
        styles_by_id = {
            str(node.get(qn(W_NS, "styleId"))): node
            for node in styles_root.findall("w:style", namespaces=NS)
            if node.get(qn(W_NS, "styleId"))
        }
    return root, abstract_by_id, num_by_id, styles_by_id


def _abstract_for_num(
    num_node: etree._Element,
    abstract_by_id: Dict[str, etree._Element],
    num_by_id: Optional[Dict[str, etree._Element]] = None,
    styles_by_id: Optional[Dict[str, etree._Element]] = None,
    trail: Optional[Set[str]] = None,
) -> Optional[etree._Element]:
    num_id = num_node.get(qn(W_NS, "numId"), "")
    if trail is None:
        trail = set()
    if num_id in trail:
        return None
    abstract_id = _word_value(
        num_node.find("w:abstractNumId", namespaces=NS)
    )
    abstract = abstract_by_id.get(abstract_id or "")
    if abstract is None:
        return None
    style_link = _word_value(
        abstract.find("w:numStyleLink", namespaces=NS)
    )
    if style_link and num_by_id is not None and styles_by_id is not None:
        numbering_style = styles_by_id.get(style_link)
        linked_num_id = _word_value(
            numbering_style.find("w:pPr/w:numPr/w:numId", namespaces=NS)
            if numbering_style is not None
            else None
        )
        linked_num = num_by_id.get(linked_num_id or "")
        if linked_num is not None:
            resolved = _abstract_for_num(
                linked_num,
                abstract_by_id,
                num_by_id,
                styles_by_id,
                trail | {num_id},
            )
            if resolved is not None:
                return resolved
    return abstract


def _level_node(
    authority: etree._Element,
    level: int,
) -> Optional[etree._Element]:
    matches = authority.xpath(
        "./w:lvl[@w:ilvl=$level]",
        namespaces=NS,
        level=str(level),
    )
    return matches[0] if matches else None


def _override_for_level(
    num_node: etree._Element,
    level: int,
) -> Optional[etree._Element]:
    matches = num_node.xpath(
        "./w:lvlOverride[@w:ilvl=$level]",
        namespaces=NS,
        level=str(level),
    )
    return matches[0] if matches else None


def _style_numbering_reference(
    style_id: str,
    styles_by_id: Dict[str, etree._Element],
    catalog: StyleCatalog,
) -> Optional[Tuple[Optional[str], Optional[int]]]:
    current = style_id
    seen: Set[str] = set()
    while current and current not in seen:
        seen.add(current)
        style_node = styles_by_id.get(current)
        if style_node is not None:
            num_pr = style_node.find("w:pPr/w:numPr", namespaces=NS)
            if num_pr is not None:
                return (
                    _word_value(num_pr.find("w:numId", namespaces=NS)),
                    _safe_int(
                        _word_value(num_pr.find("w:ilvl", namespaces=NS))
                    ),
                )
        info = catalog.styles.get(current)
        current = info.based_on if info is not None and info.based_on else ""
    return None


def _build_heading_numbering_rule(
    style_id: str,
    num_id: Optional[str],
    level_hint: Optional[int],
    catalog: StyleCatalog,
    abstract_by_id: Dict[str, etree._Element],
    num_by_id: Dict[str, etree._Element],
    styles_by_id: Dict[str, etree._Element],
) -> Optional[HeadingNumberingRule]:
    if not num_id or num_id == "0" or not re.fullmatch(r"\d+", num_id):
        return None
    num_node = num_by_id.get(num_id)
    if num_node is None:
        return None
    abstract_node = _abstract_for_num(
        num_node, abstract_by_id, num_by_id, styles_by_id
    )
    if abstract_node is None:
        return None

    linked_level: Optional[int] = None
    for node in abstract_node.findall("w:lvl", namespaces=NS):
        pstyle = _word_value(node.find("w:pStyle", namespaces=NS))
        if pstyle == style_id:
            linked_level = _safe_int(node.get(qn(W_NS, "ilvl")))
            break

    outline_level = catalog.resolved_outline.get(style_id)
    candidates: List[int] = []
    for candidate in (level_hint, linked_level, outline_level, 0):
        if candidate is not None and 0 <= candidate <= 8 and candidate not in candidates:
            candidates.append(candidate)
    for node in abstract_node.findall("w:lvl", namespaces=NS):
        candidate = _safe_int(node.get(qn(W_NS, "ilvl")))
        if candidate is not None and 0 <= candidate <= 8 and candidate not in candidates:
            candidates.append(candidate)

    selected_level: Optional[int] = None
    base_level: Optional[etree._Element] = None
    override: Optional[etree._Element] = None
    override_level: Optional[etree._Element] = None
    for candidate in candidates:
        candidate_base = _level_node(abstract_node, candidate)
        candidate_override = _override_for_level(num_node, candidate)
        candidate_override_level = (
            candidate_override.find("w:lvl", namespaces=NS)
            if candidate_override is not None
            else None
        )
        if candidate_base is not None or candidate_override_level is not None:
            selected_level = candidate
            base_level = candidate_base
            override = candidate_override
            override_level = candidate_override_level
            break
    if selected_level is None:
        return None

    def level_value(tag: str) -> Optional[str]:
        value = _word_value(
            override_level.find("w:%s" % tag, namespaces=NS)
            if override_level is not None
            else None
        )
        if value is not None:
            return value
        return _word_value(
            base_level.find("w:%s" % tag, namespaces=NS)
            if base_level is not None
            else None
        )

    number_format = level_value("numFmt")
    if number_format == "none":
        return None
    level_text = level_value("lvlText")
    start_override = (
        _safe_int(
            _word_value(override.find("w:startOverride", namespaces=NS))
        )
        if override is not None
        else None
    )
    start = start_override
    if start is None:
        start = _safe_int(level_value("start"))
    return HeadingNumberingRule(
        style_id=style_id,
        num_id=num_id,
        level=selected_level,
        number_format=number_format,
        level_text=level_text,
        start=start,
    )


def infer_heading_numbering_rules(
    entries: Dict[str, bytes],
    catalog: StyleCatalog,
    style_ids: Iterable[str],
) -> Dict[str, HeadingNumberingRule]:
    """Infer style-linked heading numbering without needing source text."""
    _root, abstract_by_id, num_by_id, numbering_styles = _numbering_index(entries)
    if not num_by_id:
        return {}
    styles_root = parse_xml(entries["word/styles.xml"], "word/styles.xml")
    styles_by_id = {
        str(node.get(qn(W_NS, "styleId"))): node
        for node in styles_root.findall("w:style", namespaces=NS)
        if node.get(qn(W_NS, "styleId"))
    }

    def num_sort_key(value: str) -> Tuple[int, str]:
        parsed = _safe_int(value)
        return (parsed if parsed is not None else sys.maxsize, value)

    rules: Dict[str, HeadingNumberingRule] = {}
    for style_id in style_ids:
        info = catalog.styles.get(style_id)
        if (
            info is None
            or info.style_type != "paragraph"
            or catalog.resolved_outline.get(style_id) is None
        ):
            continue
        reference = _style_numbering_reference(
            style_id, styles_by_id, catalog
        )
        if reference is not None:
            if reference[0] == "0":
                continue
            rule = _build_heading_numbering_rule(
                style_id,
                reference[0],
                reference[1],
                catalog,
                abstract_by_id,
                num_by_id,
                numbering_styles,
            )
            if rule is not None:
                rules[style_id] = rule
                continue
            if reference[0] is not None:
                continue

        for num_id in sorted(num_by_id, key=num_sort_key):
            num_node = num_by_id[num_id]
            abstract_node = _abstract_for_num(
                num_node, abstract_by_id, num_by_id, numbering_styles
            )
            if abstract_node is None:
                continue
            linked_levels = [
                _safe_int(node.get(qn(W_NS, "ilvl")))
                for node in abstract_node.findall("w:lvl", namespaces=NS)
                if _word_value(node.find("w:pStyle", namespaces=NS)) == style_id
            ]
            for level in linked_levels:
                rule = _build_heading_numbering_rule(
                    style_id,
                    num_id,
                    level,
                    catalog,
                    abstract_by_id,
                    num_by_id,
                    numbering_styles,
                )
                if rule is not None:
                    rules[style_id] = rule
                    break
            if style_id in rules:
                break
    return rules


def extract_heading_numbering_rules(
    entries: Dict[str, bytes],
    catalog: StyleCatalog,
    part_names: Optional[Iterable[str]] = None,
    conflicts: Optional[Set[str]] = None,
) -> Dict[str, HeadingNumberingRule]:
    """Read numbering actually applied to used Heading 1/2/3-style paragraphs."""
    _root, abstract_by_id, num_by_id, numbering_styles = _numbering_index(entries)
    if not num_by_id:
        return {}
    selected_parts = (
        list(part_names)
        if part_names is not None
        else [name for name in sorted(entries) if is_content_part(name)]
    )
    used_heading_styles: Set[str] = set()
    default_paragraph = catalog.fallback("paragraph")
    for name in selected_parts:
        if name not in entries or not is_content_part(name):
            continue
        root = parse_xml(entries[name], name)
        for paragraph in root.xpath("//w:p", namespaces=NS):
            style_id = _word_value(
                paragraph.find("w:pPr/w:pStyle", namespaces=NS)
            ) or default_paragraph
            if (
                style_id
                and catalog.resolved_outline.get(style_id) is not None
            ):
                used_heading_styles.add(style_id)

    inferred = infer_heading_numbering_rules(
        entries, catalog, used_heading_styles
    )
    votes: Dict[str, Counter[HeadingNumberingRule]] = {}
    suppressed: Counter[str] = Counter()
    for name in selected_parts:
        if name not in entries or not is_content_part(name):
            continue
        root = parse_xml(entries[name], name)
        for paragraph in root.xpath("//w:p", namespaces=NS):
            style_id = _word_value(
                paragraph.find("w:pPr/w:pStyle", namespaces=NS)
            ) or default_paragraph
            if not style_id or style_id not in used_heading_styles:
                continue
            num_pr = paragraph.find("w:pPr/w:numPr", namespaces=NS)
            if num_pr is None:
                rule = inferred.get(style_id)
            else:
                num_id = _word_value(num_pr.find("w:numId", namespaces=NS))
                level = _safe_int(
                    _word_value(num_pr.find("w:ilvl", namespaces=NS))
                )
                if num_id == "0":
                    rule = None
                    suppressed[style_id] += 1
                else:
                    inherited = inferred.get(style_id)
                    if num_id is None and inherited is not None:
                        num_id = inherited.num_id
                    rule = _build_heading_numbering_rule(
                        style_id,
                        num_id,
                        level,
                        catalog,
                        abstract_by_id,
                        num_by_id,
                        numbering_styles,
                    )
            if rule is not None:
                votes.setdefault(style_id, Counter())[rule] += 1

    result: Dict[str, HeadingNumberingRule] = {}
    for style_id, counter in votes.items():
        if len(counter) > 1 and conflicts is not None:
            conflicts.add(style_id)
        if sum(counter.values()) > suppressed[style_id]:
            result[style_id] = counter.most_common(1)[0][0]
    return result


def heading_numbering_manifest(
    rules: Dict[str, HeadingNumberingRule],
) -> Dict[str, Dict[str, object]]:
    return {
        style_id: {
            "num_id": rule.num_id,
            "level": rule.level,
            "number_format": rule.number_format,
            "level_text": rule.level_text,
            "start": rule.start,
        }
        for style_id, rule in sorted(rules.items())
    }


def heading_numbering_from_manifest(
    raw: object,
    entries: Dict[str, bytes],
    catalog: StyleCatalog,
) -> Dict[str, HeadingNumberingRule]:
    if not isinstance(raw, dict):
        return {}
    _root, abstract_by_id, num_by_id, numbering_styles = _numbering_index(entries)
    rules: Dict[str, HeadingNumberingRule] = {}
    for raw_style_id, raw_rule in raw.items():
        style_id = str(raw_style_id)
        if not isinstance(raw_rule, dict):
            continue
        raw_level = raw_rule.get("level")
        level = (
            raw_level
            if isinstance(raw_level, int) and not isinstance(raw_level, bool)
            else _safe_int(str(raw_level)) if raw_level is not None else None
        )
        rule = _build_heading_numbering_rule(
            style_id,
            str(raw_rule.get("num_id", "")),
            level,
            catalog,
            abstract_by_id,
            num_by_id,
            numbering_styles,
        )
        if rule is not None:
            rules[style_id] = rule
    return rules


def _set_style_numbering_rule(
    style_node: etree._Element,
    rule: Optional[HeadingNumberingRule],
) -> bool:
    paragraph_properties = style_node.find("w:pPr", namespaces=NS)
    existing = (
        paragraph_properties.find("w:numPr", namespaces=NS)
        if paragraph_properties is not None
        else None
    )
    if rule is None:
        if existing is None or paragraph_properties is None:
            return False
        paragraph_properties.remove(existing)
        if len(paragraph_properties) == 0:
            style_node.remove(paragraph_properties)
        return True

    if paragraph_properties is None:
        paragraph_properties = etree.Element(qn(W_NS, "pPr"))
        insertion = len(style_node)
        for index, child in enumerate(style_node):
            if local_name(child) in {"rPr", "tblPr", "trPr", "tcPr"}:
                insertion = index
                break
        style_node.insert(insertion, paragraph_properties)
    if existing is not None:
        paragraph_properties.remove(existing)

    num_pr = etree.Element(qn(W_NS, "numPr"))
    level = etree.SubElement(num_pr, qn(W_NS, "ilvl"))
    level.set(qn(W_NS, "val"), str(rule.level))
    num_id = etree.SubElement(num_pr, qn(W_NS, "numId"))
    num_id.set(qn(W_NS, "val"), rule.num_id)
    insert_before = {
        "suppressLineNumbers",
        "pBdr",
        "shd",
        "tabs",
        "spacing",
        "ind",
        "contextualSpacing",
        "mirrorIndents",
        "suppressOverlap",
        "jc",
        "textDirection",
        "textAlignment",
        "textboxTightWrap",
        "outlineLvl",
        "divId",
        "cnfStyle",
    }
    insertion = len(paragraph_properties)
    for index, child in enumerate(paragraph_properties):
        if local_name(child) in insert_before:
            insertion = index
            break
    paragraph_properties.insert(insertion, num_pr)
    return True


def align_heading_style_numbering(
    entries: Dict[str, bytes],
    used_heading_style_ids: Iterable[str],
    rules: Dict[str, HeadingNumberingRule],
) -> int:
    """Align both Word style parts with numbering observed in source headings."""
    used = {str(value) for value in used_heading_style_ids}
    if not used:
        return 0
    _rels, roles = collect_format_relationships(entries)
    parts: List[str] = []
    for role in ("styles", "stylesWithEffects"):
        record = roles.get(role)
        fallback = ROLE_FALLBACK_PARTS[role]
        part = record[0] if record is not None else fallback
        if part in entries and part not in parts:
            parts.append(part)

    changed = 0
    for part in parts:
        root = parse_xml(entries[part], part)
        part_changed = False
        for style_node in root.findall("w:style", namespaces=NS):
            style_id = style_node.get(qn(W_NS, "styleId"))
            if style_id not in used:
                continue
            if _set_style_numbering_rule(style_node, rules.get(style_id)):
                changed += 1
                part_changed = True
        if part_changed:
            entries[part] = serialize_xml(root)
    return changed


def map_style_id(
    target_style_id: Optional[str],
    expected_type: str,
    target_catalog: StyleCatalog,
    source_catalog: StyleCatalog,
    heading_level_shift: int = 0,
) -> Optional[str]:
    if not target_style_id:
        return source_catalog.fallback(expected_type)

    target_info = target_catalog.styles.get(target_style_id)
    if expected_type == "paragraph" and target_info is not None:
        outline = target_catalog.resolved_outline.get(target_style_id)
        if outline is not None:
            desired_outline = min(8, outline + max(0, heading_level_shift))
            authority = source_catalog.authoritative_heading_by_level.get(
                desired_outline
            )
            if authority:
                return authority
            if heading_level_shift and desired_outline != outline:
                raise TransferError(
                    "格式库缺少标题%d，无法把目标标题%d安全地下调一级。"
                    % (desired_outline + 1, outline + 1)
                )

    direct = source_catalog.styles.get(target_style_id)
    if direct is not None and direct.style_type == expected_type:
        return direct.style_id

    if target_info is not None:
        for candidate in (target_info.name,) + target_info.aliases + (target_info.style_id,):
            match = source_catalog.by_name.get(
                (expected_type, normalize_style_name(candidate))
            )
            if match:
                return match

        if expected_type == "paragraph":
            outline = target_catalog.resolved_outline.get(target_style_id)
            if outline is not None:
                desired_outline = min(8, outline + max(0, heading_level_shift))
                authority = source_catalog.authoritative_heading_by_level.get(
                    desired_outline
                )
                if authority:
                    return authority
                heading = source_catalog.heading_by_level.get(desired_outline)
                if heading:
                    return heading

    # The style may be referenced without a definition in a malformed file.
    match = source_catalog.by_name.get(
        (expected_type, normalize_style_name(target_style_id))
    )
    if match:
        return match

    return source_catalog.fallback(expected_type)


@dataclass
class TransferStats:
    content_parts_cleaned: int = 0
    paragraphs_seen: int = 0
    runs_seen: int = 0
    tables_seen: int = 0
    table_formats_preserved: int = 0
    table_paragraph_indents_cleared: int = 0
    table_paragraph_styles_hardened: int = 0
    heading_numbers_applied: int = 0
    heading_indents_applied: int = 0
    heading_prefixes_removed: int = 0
    heading_levels_demoted: int = 0
    heading_level9_unchanged: int = 0
    heading_numbering_start: Optional[int] = None
    style_list_paragraphs_materialized: int = 0
    body_list_paragraphs_preserved: int = 0
    target_numbering_definitions_imported: int = 0
    target_numbering_abstracts_imported: int = 0
    target_picture_bullets_imported: int = 0
    sections_updated: int = 0
    paragraph_properties_removed: int = 0
    run_properties_removed: int = 0
    table_properties_removed: int = 0
    styles_remapped: int = 0
    source_format_parts_copied: int = 0
    dependent_parts_copied: int = 0
    settings_items_imported: int = 0
    warnings: List[str] = field(default_factory=list)


@dataclass
class BodyNumberingMergeResult:
    """Target list instances copied into the source-owned numbering system."""

    num_id_map: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


def _remove_children_except(
    parent: etree._Element,
    keep: Set[str],
) -> int:
    removed = 0
    for child in list(parent):
        if local_name(child) not in keep:
            parent.remove(child)
            removed += 1
    return removed


def _ensure_child_first(parent: etree._Element, tag_local: str) -> etree._Element:
    found = parent.find("w:%s" % tag_local, namespaces=NS)
    if found is not None:
        return found
    created = etree.Element(qn(W_NS, tag_local))
    parent.insert(0, created)
    return created


def _set_paragraph_numbering(
    paragraph_properties: etree._Element,
    rule: HeadingNumberingRule,
) -> None:
    existing = paragraph_properties.find("w:numPr", namespaces=NS)
    if existing is not None:
        paragraph_properties.remove(existing)
    num_pr = etree.Element(qn(W_NS, "numPr"))
    level = etree.SubElement(num_pr, qn(W_NS, "ilvl"))
    level.set(qn(W_NS, "val"), str(rule.level))
    num_id = etree.SubElement(num_pr, qn(W_NS, "numId"))
    num_id.set(qn(W_NS, "val"), rule.num_id)
    _ordered_insert(paragraph_properties, num_pr, PPR_CHILD_ORDER)


def _remapped_body_numbering(
    original: etree._Element,
    num_id_map: Dict[str, str],
) -> Optional[etree._Element]:
    """Clone one semantic list reference and point it at an imported instance.

    A direct ``w:numPr`` is content semantics, not merely visual paragraph
    formatting.  Its ``w:numId`` cannot, however, survive a wholesale
    numbering-part replacement: the same numeric ID can describe a completely
    different list in the format source.  Only references whose definitions
    were deliberately merged are restored here.
    """
    num_id = original.find("w:numId", namespaces=NS)
    old_num_id = _word_value(num_id)
    mapped_num_id = num_id_map.get(old_num_id or "")
    if num_id is None or mapped_num_id is None:
        return None
    restored = copy.deepcopy(original)
    restored_num_id = restored.find("w:numId", namespaces=NS)
    if restored_num_id is None:  # Defensive; the original was checked above.
        return None
    restored_num_id.set(qn(W_NS, "val"), mapped_num_id)
    return restored


def _replace_direct_numbering(
    paragraph_properties: etree._Element,
    replacement: Optional[etree._Element],
) -> None:
    existing = paragraph_properties.find("w:numPr", namespaces=NS)
    if existing is not None:
        paragraph_properties.remove(existing)
    if replacement is not None:
        _ordered_insert(paragraph_properties, replacement, PPR_CHILD_ORDER)


def _set_heading_paragraph_indent(
    paragraph_properties: etree._Element,
    profile: Dict[str, str],
) -> None:
    existing = paragraph_properties.find("w:ind", namespaces=NS)
    if existing is not None:
        paragraph_properties.remove(existing)
    indentation = etree.Element(qn(W_NS, "ind"))
    for attribute in HEADING_INDENT_ATTRIBUTES:
        value = profile.get(attribute)
        if value is not None:
            indentation.set(qn(W_NS, attribute), value)
    _ordered_insert(paragraph_properties, indentation, PPR_CHILD_ORDER)


def _set_heading_paragraph_properties(
    paragraph_properties: etree._Element,
    profile: Dict[str, object],
) -> None:
    raw_indent = profile.get("ind")
    if isinstance(raw_indent, dict) and raw_indent:
        _set_heading_paragraph_indent(
            paragraph_properties,
            {
                str(attribute): str(value)
                for attribute, value in raw_indent.items()
            },
        )

    raw_spacing = profile.get("spacing")
    if isinstance(raw_spacing, dict) and raw_spacing:
        existing = paragraph_properties.find("w:spacing", namespaces=NS)
        if existing is not None:
            paragraph_properties.remove(existing)
        spacing = etree.Element(qn(W_NS, "spacing"))
        for attribute in HEADING_SPACING_ATTRIBUTES:
            value = raw_spacing.get(attribute)
            if value is not None:
                spacing.set(qn(W_NS, attribute), str(value))
        _ordered_insert(paragraph_properties, spacing, PPR_CHILD_ORDER)

    alignment = profile.get("jc")
    if isinstance(alignment, str) and alignment in PARAGRAPH_ALIGNMENT_VALUES:
        existing = paragraph_properties.find("w:jc", namespaces=NS)
        if existing is not None:
            paragraph_properties.remove(existing)
        justification = etree.Element(qn(W_NS, "jc"))
        justification.set(qn(W_NS, "val"), alignment)
        _ordered_insert(paragraph_properties, justification, PPR_CHILD_ORDER)


def _has_nonzero_hanging(indentation: etree._Element) -> bool:
    return any(
        (_safe_int(indentation.get(qn(W_NS, attribute))) or 0) != 0
        for attribute in ("hanging", "hangingChars")
    )


def _neutralize_table_two_character_indent(
    paragraph_properties: etree._Element,
    effective_style_id: Optional[str],
    source_catalog: StyleCatalog,
) -> bool:
    """Override exactly two-character first-line indentation in a table cell.

    Removing ``w:ind`` is not sufficient: the imported Normal style can carry
    ``firstLineChars=200``, so the cell would immediately inherit the same
    indentation again.  A direct zero-character/zero-twip override is the
    narrowest reliable fix and leaves every unrelated paragraph property
    untouched.
    """
    indentation = paragraph_properties.find("w:ind", namespaces=NS)
    if indentation is not None and _has_nonzero_hanging(indentation):
        return False

    direct_chars: Optional[int] = None
    direct_twips: Optional[int] = None
    has_direct_chars = False
    has_direct_twips = False
    if indentation is not None:
        chars_attribute = qn(W_NS, "firstLineChars")
        twips_attribute = qn(W_NS, "firstLine")
        has_direct_chars = chars_attribute in indentation.attrib
        has_direct_twips = twips_attribute in indentation.attrib
        direct_chars = _safe_int(indentation.get(chars_attribute))
        direct_twips = _safe_int(indentation.get(twips_attribute))

    explicit_two_characters = has_direct_chars and direct_chars == 200
    inherits_two_characters = (
        effective_style_id in source_catalog.two_character_first_line_styles
    )

    if not explicit_two_characters:
        # An explicit character-unit value other than 0/200 is intentional and
        # already overrides the source style.  A zero-character value is safe
        # to normalize together with its twip fallback.
        if has_direct_chars and direct_chars != 0:
            return False
        # Numbered paragraphs use indentation for their list geometry.  Only
        # change those when the paragraph itself explicitly says 200 chars.
        if paragraph_properties.find("w:numPr", namespaces=NS) is not None:
            return False
        direct_outline = paragraph_properties.find("w:outlineLvl", namespaces=NS)
        direct_outline_level = _safe_int(
            direct_outline.get(qn(W_NS, "val"))
            if direct_outline is not None
            else None
        )
        if direct_outline_level is not None and 0 <= direct_outline_level <= 8:
            return False
        if not inherits_two_characters:
            # A non-zero twip-only value is not enough evidence by itself that
            # the user selected "2 characters"; font metrics vary.  It becomes
            # unsafe only in combination with an imported style that actually
            # supplies firstLineChars=200.  In that real-world combination the
            # character-unit value remains effective in Word, so both units
            # must be overridden with zero.
            return False

    if indentation is None:
        indentation = etree.Element(qn(W_NS, "ind"))
        _ordered_insert(paragraph_properties, indentation, PPR_CHILD_ORDER)

    chars_attribute = qn(W_NS, "firstLineChars")
    twips_attribute = qn(W_NS, "firstLine")
    changed = (
        indentation.get(chars_attribute) != "0"
        or indentation.get(twips_attribute) != "0"
    )
    indentation.set(chars_attribute, "0")
    indentation.set(twips_attribute, "0")
    return changed


def _can_apply_table_no_indent_style(
    paragraph_properties: etree._Element,
) -> bool:
    """Protect plain table text without rewriting list/outline geometry."""
    indentation = paragraph_properties.find("w:ind", namespaces=NS)
    if indentation is not None:
        if _has_nonzero_hanging(indentation):
            return False
        chars_attribute = qn(W_NS, "firstLineChars")
        twips_attribute = qn(W_NS, "firstLine")
        if chars_attribute in indentation.attrib:
            chars = _safe_int(indentation.get(chars_attribute))
            if chars not in {0, 200}:
                return False
        elif twips_attribute in indentation.attrib:
            twips = _safe_int(indentation.get(twips_attribute))
            if twips not in {None, 0}:
                return False
    if paragraph_properties.find("w:numPr", namespaces=NS) is not None:
        return False
    direct_outline = paragraph_properties.find("w:outlineLvl", namespaces=NS)
    direct_outline_level = _safe_int(
        direct_outline.get(qn(W_NS, "val"))
        if direct_outline is not None
        else None
    )
    return not (
        direct_outline_level is not None and 0 <= direct_outline_level <= 8
    )


def _set_paragraph_style(
    paragraph_properties: etree._Element,
    style_id: str,
) -> bool:
    style = paragraph_properties.find("w:pStyle", namespaces=NS)
    if style is None:
        style = etree.Element(qn(W_NS, "pStyle"))
        _ordered_insert(paragraph_properties, style, PPR_CHILD_ORDER)
    if style.get(qn(W_NS, "val")) == style_id:
        return False
    style.set(qn(W_NS, "val"), style_id)
    return True


@dataclass(frozen=True)
class ManualHeadingPrefix:
    consumed: int
    numbers: Tuple[int, ...]


_ARABIC_HEADING_PREFIX = re.compile(
    r"^\s*(?P<numbers>\d{1,3}(?:[\.．]\d{1,3})*)"
    r"(?:[\.．、])?[ \t\u3000]+(?=\S)"
)
_PAREN_HEADING_PREFIX = re.compile(
    r"^\s*[（(](?P<numbers>\d{1,3}(?:[\.．]\d{1,3})*)[）)]"
    r"[ \t\u3000]+(?=\S)"
)
_CHINESE_HEADING_PREFIX = re.compile(
    r"^\s*第(?P<number>[零〇一二两三四五六七八九十百千万]+)"
    r"(?P<unit>章|篇|部|卷|节|条|款|项)[ \t\u3000]+(?=\S)"
)


def _parse_chinese_integer(value: str) -> Optional[int]:
    digits = {
        "零": 0,
        "〇": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    if not value or any(character not in digits and character not in units for character in value):
        return None
    if not any(character in units for character in value):
        try:
            parsed = int("".join(str(digits[character]) for character in value))
        except ValueError:
            return None
        return parsed if parsed > 0 else None

    total = 0
    section = 0
    number = 0
    for character in value:
        if character in digits:
            number = digits[character]
            continue
        unit = units[character]
        if unit == 10000:
            section += number
            total += (section or 1) * unit
            section = 0
            number = 0
        else:
            section += (number or 1) * unit
            number = 0
    parsed = total + section + number
    return parsed if parsed > 0 else None


def _plain_heading_text_segments(
    paragraph: etree._Element,
) -> List[Tuple[etree._Element, str, bool]]:
    """Collect direct, ordinary run text without crossing semantic objects."""
    segments: List[Tuple[etree._Element, str, bool]] = []
    harmless_paragraph_children = {
        "pPr",
        "bookmarkStart",
        "bookmarkEnd",
        "commentRangeStart",
        "commentRangeEnd",
        "proofErr",
        "permStart",
        "permEnd",
    }
    for child in paragraph:
        child_name = local_name(child)
        if child_name in harmless_paragraph_children:
            continue
        if child_name != "r":
            # Hyperlinks, fields, revisions, content controls and drawings are
            # content-bearing boundaries.  A prefix crossing them is left
            # untouched rather than risking semantic damage.
            return []
        for run_child in child:
            run_name = local_name(run_child)
            if run_name == "rPr":
                continue
            if run_name == "t":
                segments.append((run_child, run_child.text or "", False))
            elif run_name == "tab":
                segments.append((run_child, "\t", True))
            else:
                return []
    return segments


def _manual_heading_prefix_candidate(
    paragraph: etree._Element,
    level: int,
) -> Tuple[Optional[ManualHeadingPrefix], List[Tuple[etree._Element, str, bool]]]:
    segments = _plain_heading_text_segments(paragraph)
    if not segments:
        return None, segments
    visible = "".join(value for _node, value, _is_tab in segments)
    for expression in (_PAREN_HEADING_PREFIX, _ARABIC_HEADING_PREFIX):
        match = expression.match(visible)
        if match is None:
            continue
        numbers = tuple(
            int(component)
            for component in re.split(r"[\.．]", match.group("numbers"))
        )
        if len(numbers) == level + 1:
            return ManualHeadingPrefix(match.end(), numbers), segments
        return None, segments

    chinese = _CHINESE_HEADING_PREFIX.match(visible)
    if chinese is None:
        return None, segments
    units_by_level = {
        0: {"章", "篇", "部", "卷"},
        1: {"节"},
        2: {"条", "款", "项"},
    }
    if chinese.group("unit") not in units_by_level.get(level, set()):
        return None, segments
    number = _parse_chinese_integer(chinese.group("number"))
    if number is None:
        return None, segments
    return ManualHeadingPrefix(chinese.end(), (number,)), segments


def _remove_plain_prefix(
    segments: Sequence[Tuple[etree._Element, str, bool]],
    characters: int,
) -> None:
    remaining = characters
    for node, value, is_tab in segments:
        if remaining <= 0:
            break
        consumed = min(remaining, len(value))
        remaining -= consumed
        if consumed < len(value):
            node.text = value[consumed:]
            if node.text and (node.text[0].isspace() or node.text[-1].isspace()):
                node.set(qn(XML_NS, "space"), "preserve")
            else:
                node.attrib.pop(qn(XML_NS, "space"), None)
            break
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)


def _advance_heading_counter(
    counters: Dict[int, int],
    rule: HeadingNumberingRule,
    candidate: Optional[ManualHeadingPrefix],
) -> Tuple[Tuple[int, ...], bool, bool]:
    """Simulate Word's outline counter and validate a typed prefix.

    The third return value marks a first-level prefix that safely establishes
    a non-default starting chapter for the output list.
    """
    level = rule.level
    start = rule.start if rule.start is not None and rule.start > 0 else 1
    seeded_start = False
    if level == 0:
        if 0 in counters:
            next_value = counters[0] + 1
        elif candidate is not None and len(candidate.numbers) == 1:
            next_value = candidate.numbers[0]
            seeded_start = True
        else:
            next_value = start
    else:
        # Without a known parent path, a numeric-looking title cannot be
        # distinguished safely from content such as "3.14 圆周率".
        if any(parent not in counters for parent in range(level)):
            next_value = start
            expected = tuple(counters.get(parent, start) for parent in range(level)) + (next_value,)
            counters[level] = next_value
            for deeper in [key for key in counters if key > level]:
                del counters[deeper]
            return expected, False, False
        next_value = counters.get(level, start - 1) + 1

    counters[level] = next_value
    for deeper in [key for key in counters if key > level]:
        del counters[deeper]
    expected = tuple(counters[parent] for parent in range(level + 1))
    matches = candidate is not None and candidate.numbers == expected
    return expected, matches, seeded_start and matches


def set_heading_numbering_start_override(
    entries: Dict[str, bytes],
    rules: Dict[str, HeadingNumberingRule],
    start_value: Optional[int],
) -> None:
    if start_value is None or start_value <= 0:
        return
    numbering_root, _abstract_by_id, num_by_id, _styles = _numbering_index(entries)
    if numbering_root is None:
        return
    changed = False
    for num_id in sorted({rule.num_id for rule in rules.values()}):
        num_node = num_by_id.get(num_id)
        if num_node is None:
            continue
        override = _override_for_level(num_node, 0)
        if override is None:
            override = etree.SubElement(num_node, qn(W_NS, "lvlOverride"))
            override.set(qn(W_NS, "ilvl"), "0")
        start_override = override.find("w:startOverride", namespaces=NS)
        if start_override is None:
            start_override = etree.Element(qn(W_NS, "startOverride"))
            override.insert(0, start_override)
        start_override.set(qn(W_NS, "val"), str(start_value))
        changed = True
    if not changed:
        return
    _rels, roles = collect_format_relationships(entries)
    numbering_record = roles.get("numbering")
    numbering_part = (
        numbering_record[0]
        if numbering_record is not None
        else ROLE_FALLBACK_PARTS["numbering"]
    )
    entries[numbering_part] = serialize_xml(numbering_root)


def extract_source_section_layout(
    document_bytes: bytes,
) -> List[List[etree._Element]]:
    root = parse_xml(document_bytes, "源文件 document.xml")
    sections = root.xpath("//w:sectPr", namespaces=NS)
    if not sections:
        return []
    return [
        [
            copy.deepcopy(child)
            for child in authority
            if local_name(child) in SECTION_LAYOUT_TAGS
        ]
        for authority in sections
    ]


def apply_section_layout(
    root: etree._Element,
    source_layouts: Sequence[Sequence[etree._Element]],
    stats: TransferStats,
) -> None:
    if not source_layouts:
        return
    target_sections = root.xpath("//w:sectPr", namespaces=NS)
    for section_index, sect in enumerate(target_sections):
        source_layout = source_layouts[min(section_index, len(source_layouts) - 1)]
        for child in list(sect):
            if local_name(child) in SECTION_LAYOUT_TAGS:
                sect.remove(child)

        change_node = sect.find("w:sectPrChange", namespaces=NS)
        insert_at = sect.index(change_node) if change_node is not None else len(sect)
        for item in source_layout:
            sect.insert(insert_at, copy.deepcopy(item))
            insert_at += 1
        stats.sections_updated += 1


def clean_content_xml(
    data: bytes,
    label: str,
    target_catalog: StyleCatalog,
    source_catalog: StyleCatalog,
    source_layouts: Sequence[Sequence[etree._Element]],
    stats: TransferStats,
    heading_numbering: Optional[Dict[str, HeadingNumberingRule]] = None,
    heading_paragraph_indents: Optional[
        Dict[str, Dict[str, str]]
    ] = None,
    heading_paragraph_properties: Optional[
        Dict[str, Dict[str, object]]
    ] = None,
    heading_level_shift: int = 0,
    table_no_indent_styles: Optional[Dict[str, str]] = None,
    body_numbering_map: Optional[Dict[str, str]] = None,
) -> bytes:
    root = parse_xml(data, label)
    heading_counters: Dict[int, int] = {}
    original_heading_counters: Dict[int, int] = {}
    heading_level_shift = max(0, min(8, int(heading_level_shift)))
    preserve_target_table_formatting = not source_catalog.used_table_styles
    table_no_indent_styles = table_no_indent_styles or {}
    body_numbering_map = body_numbering_map or {}
    effective_heading_properties: Dict[str, Dict[str, object]] = {
        style_id: copy.deepcopy(profile)
        for style_id, profile in (heading_paragraph_properties or {}).items()
    }
    for style_id, indentation in (heading_paragraph_indents or {}).items():
        profile = effective_heading_properties.setdefault(style_id, {})
        profile.setdefault("ind", copy.deepcopy(indentation))

    for paragraph in root.xpath("//w:p", namespaces=NS):
        stats.paragraphs_seen += 1
        inside_table = bool(
            paragraph.xpath("ancestor::w:tc", namespaces=NS)
        )
        inside_preserved_table = bool(
            preserve_target_table_formatting and inside_table
        )
        ppr = paragraph.find("w:pPr", namespaces=NS)
        mapped_style_id: Optional[str] = None
        target_outline: Optional[int] = None
        desired_outline: Optional[int] = None
        original_num_pr: Optional[etree._Element] = None
        if ppr is not None:
            direct_num_pr = ppr.find("w:numPr", namespaces=NS)
            if direct_num_pr is not None:
                original_num_pr = copy.deepcopy(direct_num_pr)
            pstyle = ppr.find("w:pStyle", namespaces=NS)
            old = _word_value(pstyle)
            direct_outline_level = _direct_paragraph_outline_level(ppr)
            target_outline = paragraph_outline_level(ppr, target_catalog)
            desired_outline = (
                min(8, target_outline + heading_level_shift)
                if target_outline is not None
                else None
            )
            if pstyle is not None or target_outline is not None:
                if direct_outline_level is not None and target_outline is not None:
                    new = (
                        source_catalog.authoritative_heading_by_level.get(desired_outline)
                        or source_catalog.heading_by_level.get(desired_outline)
                    )
                    if new is None:
                        raise TransferError(
                            "格式库缺少标题%d，无法安全转换目标的大纲标题。"
                            % (desired_outline + 1)
                        )
                elif direct_outline_level == 9:
                    # Clearing an explicit Body Text override must not expose
                    # the heading level inherited from the old paragraph style.
                    new = map_style_id(
                        old, "paragraph", target_catalog, source_catalog
                    )
                    if source_catalog.resolved_outline.get(new or "") is not None:
                        new = source_catalog.fallback("paragraph")
                else:
                    new = map_style_id(
                        old,
                        "paragraph",
                        target_catalog,
                        source_catalog,
                        heading_level_shift=heading_level_shift,
                    )
                if (
                    new
                    and heading_numbering
                    and new not in heading_numbering
                    and new not in source_catalog.used_paragraph_styles
                    and desired_outline is not None
                ):
                    numbered_peers = sorted(
                        style_id
                        for style_id in heading_numbering
                        if source_catalog.resolved_outline.get(style_id)
                        == desired_outline
                    )
                    if numbered_peers:
                        new = numbered_peers[0]
                if new:
                    if new != old:
                        stats.styles_remapped += 1
                    _set_paragraph_style(ppr, new)
                    mapped_style_id = new
                    if target_outline is not None and heading_level_shift:
                        mapped_outline = source_catalog.resolved_outline.get(new)
                        if target_outline >= 8:
                            stats.heading_level9_unchanged += 1
                        elif mapped_outline == desired_outline:
                            stats.heading_levels_demoted += 1
                else:
                    if pstyle is not None:
                        ppr.remove(pstyle)
                # Even a preserved table must not retain an old direct level
                # which would override the newly mapped or demoted heading.
                if (
                    mapped_style_id is not None
                    and target_outline is not None
                    and source_catalog.resolved_outline.get(mapped_style_id)
                    == desired_outline
                ):
                    direct_outline = ppr.find("w:outlineLvl", namespaces=NS)
                    if direct_outline is not None:
                        ppr.remove(direct_outline)
                        stats.paragraph_properties_removed += 1
            if not inside_preserved_table:
                stats.paragraph_properties_removed += _remove_children_except(
                    ppr, {"pStyle", "sectPr"}
                )
            if direct_outline_level == 9:
                # Explicit Body Text also overrides a same-ID source style
                # or even a heading-valued template default paragraph style.
                body_outline = ppr.find("w:outlineLvl", namespaces=NS)
                if body_outline is None:
                    body_outline = etree.Element(qn(W_NS, "outlineLvl"))
                    _ordered_insert(ppr, body_outline, PPR_CHILD_ORDER)
                body_outline.set(qn(W_NS, "val"), "9")
            rule = (
                heading_numbering.get(mapped_style_id)
                if heading_numbering is not None and mapped_style_id is not None
                else None
            )
            if rule is not None:
                prefix_level = (
                    target_outline
                    if heading_level_shift and target_outline is not None
                    else rule.level
                )
                candidate, prefix_segments = _manual_heading_prefix_candidate(
                    paragraph, prefix_level
                )
                if heading_level_shift and target_outline is not None:
                    original_rule = HeadingNumberingRule(
                        style_id=rule.style_id,
                        num_id=rule.num_id,
                        level=target_outline,
                        number_format=rule.number_format,
                        level_text=rule.level_text,
                        start=rule.start,
                    )
                    _expected, prefix_matches, seeded_start = _advance_heading_counter(
                        original_heading_counters, original_rule, candidate
                    )
                    _advance_heading_counter(heading_counters, rule, None)
                else:
                    _expected, prefix_matches, seeded_start = _advance_heading_counter(
                        heading_counters, rule, candidate
                    )
                if prefix_matches and candidate is not None:
                    _remove_plain_prefix(prefix_segments, candidate.consumed)
                    stats.heading_prefixes_removed += 1
                    if (
                        seeded_start
                        and label == "word/document.xml"
                        and stats.heading_numbering_start is None
                    ):
                        stats.heading_numbering_start = candidate.numbers[0]
                _set_paragraph_numbering(ppr, rule)
                stats.heading_numbers_applied += 1
            elif original_num_pr is not None:
                # Ordinary lists remain target-owned content semantics.  A
                # target heading's direct numbering is intentionally not
                # restored: the source heading system (numbered or plain) is
                # authoritative for headings.
                restored_num_pr = (
                    _remapped_body_numbering(
                        original_num_pr, body_numbering_map
                    )
                    if target_outline is None
                    else None
                )
                _replace_direct_numbering(ppr, restored_num_pr)
                restored_num_id = (
                    _word_value(
                        restored_num_pr.find("w:numId", namespaces=NS)
                    )
                    if restored_num_pr is not None
                    else None
                )
                if restored_num_id not in {None, "0"}:
                    stats.body_list_paragraphs_preserved += 1

            # Direct heading paragraph geometry belongs to the source format,
            # regardless of whether the heading is numbered.  Apply it after
            # list handling so a paragraph-level indent can intentionally
            # override the numbering level without mutating numbering.xml.
            heading_profile = (
                effective_heading_properties.get(mapped_style_id)
                if mapped_style_id is not None
                and source_catalog.resolved_outline.get(mapped_style_id)
                is not None
                else None
            )
            if heading_profile:
                _set_heading_paragraph_properties(ppr, heading_profile)
                if isinstance(heading_profile.get("ind"), dict):
                    stats.heading_indents_applied += 1

        if inside_table:
            effective_style_id = (
                mapped_style_id or source_catalog.fallback("paragraph")
            )
            if (
                ppr is None
                and effective_style_id
                in source_catalog.two_character_first_line_styles
            ):
                ppr = etree.Element(qn(W_NS, "pPr"))
                paragraph.insert(0, ppr)
            if ppr is not None and _neutralize_table_two_character_indent(
                ppr, effective_style_id, source_catalog
            ):
                stats.table_paragraph_indents_cleared += 1
            stable_style_id = table_no_indent_styles.get(
                effective_style_id or ""
            )
            if (
                stable_style_id
                and ppr is not None
                and _can_apply_table_no_indent_style(ppr)
                and _set_paragraph_style(ppr, stable_style_id)
            ):
                mapped_style_id = stable_style_id
                stats.table_paragraph_styles_hardened += 1

        if ppr is not None:
            if len(ppr) == 0:
                paragraph.remove(ppr)

    for run in root.xpath("//w:r", namespaces=NS):
        stats.runs_seen += 1
        rpr = run.find("w:rPr", namespaces=NS)
        if rpr is None:
            continue
        rstyle = rpr.find("w:rStyle", namespaces=NS)
        if rstyle is not None:
            old = rstyle.get(qn(W_NS, "val"))
            new = map_style_id(old, "character", target_catalog, source_catalog)
            if new and new != source_catalog.fallback("character"):
                if new != old:
                    stats.styles_remapped += 1
                rstyle.set(qn(W_NS, "val"), new)
            elif new and old in source_catalog.styles:
                rstyle.set(qn(W_NS, "val"), old)
            else:
                rpr.remove(rstyle)
                stats.styles_remapped += 1
        stats.run_properties_removed += _remove_children_except(
            rpr, RUN_SEMANTIC_KEEP
        )
        if len(rpr) == 0:
            run.remove(rpr)

    table_fallback = (
        source_catalog.preferred_table_style
        or source_catalog.fallback("table")
    )
    for table in root.xpath("//w:tbl", namespaces=NS):
        stats.tables_seen += 1
        tbl_pr = table.find("w:tblPr", namespaces=NS)
        if preserve_target_table_formatting:
            # A format source that never uses a table has no table design to
            # contribute.  Keep the target's borders, fills, cell margins,
            # row/cell properties and table style instead of normalizing it to
            # borderless TableNormal (which makes many tables look deleted).
            stats.table_formats_preserved += 1
            continue

        if tbl_pr is None:
            tbl_pr = etree.Element(qn(W_NS, "tblPr"))
            table.insert(0, tbl_pr)
        tbl_style = tbl_pr.find("w:tblStyle", namespaces=NS)
        old = tbl_style.get(qn(W_NS, "val")) if tbl_style is not None else None
        new = map_style_id(old, "table", target_catalog, source_catalog)
        # A style merely present in a Word style gallery is not evidence that
        # it belongs to the source document's actual visual system.  Preserve
        # an exact/mapped table style only when the source document uses it;
        # otherwise normalize to the source's first used table style.
        if new not in source_catalog.used_table_styles:
            new = table_fallback or new
        if new:
            tbl_style = _ensure_child_first(tbl_pr, "tblStyle")
            if old != new:
                stats.styles_remapped += 1
            tbl_style.set(qn(W_NS, "val"), new)
        elif tbl_style is not None:
            tbl_pr.remove(tbl_style)
        stats.table_properties_removed += _remove_children_except(
            tbl_pr, TABLE_PROPERTY_KEEP
        )

        for row_pr in table.xpath(".//w:trPr", namespaces=NS):
            stats.table_properties_removed += _remove_children_except(
                row_pr, ROW_PROPERTY_KEEP
            )
        for cell_pr in table.xpath(".//w:tcPr", namespaces=NS):
            stats.table_properties_removed += _remove_children_except(
                cell_pr, CELL_PROPERTY_KEEP
            )

    if local_name(root) == "document":
        apply_section_layout(root, source_layouts, stats)

    return serialize_xml(root)


def merge_settings(
    source_data: bytes,
    target_data: bytes,
    stats: TransferStats,
    preserve_target_table_default: bool = False,
) -> bytes:
    source_root = parse_xml(source_data, "源文件 settings.xml")
    target_root = parse_xml(target_data, "目标文件 settings.xml")

    for child in list(target_root):
        if (
            local_name(child) in SETTINGS_FORMAT_TAGS
            and not (
                preserve_target_table_default
                and local_name(child) == "defaultTableStyle"
            )
        ):
            target_root.remove(child)

    # Insert before compatibility/protection/tracking blocks when possible.
    preferred_before = {"compat", "docVars", "rsids", "mathPr", "attachedSchema"}
    insertion = len(target_root)
    for index, child in enumerate(target_root):
        if local_name(child) in preferred_before:
            insertion = index
            break

    for child in source_root:
        if (
            local_name(child) in SETTINGS_FORMAT_TAGS
            and not (
                preserve_target_table_default
                and local_name(child) == "defaultTableStyle"
            )
        ):
            target_root.insert(insertion, copy.deepcopy(child))
            insertion += 1
            stats.settings_items_imported += 1

    return serialize_xml(target_root)


def parse_content_types(entries: Dict[str, bytes], role: str) -> etree._Element:
    return parse_xml(entries["[Content_Types].xml"], "%s [Content_Types].xml" % role)


def content_type_for(
    root: etree._Element,
    part_name: str,
) -> Optional[str]:
    wanted = "/" + part_name.lstrip("/")
    for node in root.findall(qn(CT_NS, "Override")):
        if node.get("PartName") == wanted:
            return node.get("ContentType")
    extension = posixpath.splitext(part_name)[1].lstrip(".").lower()
    for node in root.findall(qn(CT_NS, "Default")):
        if node.get("Extension", "").lower() == extension:
            return node.get("ContentType")
    return None


def ensure_content_type_override(
    root: etree._Element,
    part_name: str,
    content_type: Optional[str],
) -> None:
    if not content_type:
        return
    wanted = "/" + part_name.lstrip("/")
    for node in root.findall(qn(CT_NS, "Override")):
        if node.get("PartName") == wanted:
            node.set("ContentType", content_type)
            return
    node = etree.SubElement(root, qn(CT_NS, "Override"))
    node.set("PartName", wanted)
    node.set("ContentType", content_type)


def remove_content_type_override(root: etree._Element, part_name: str) -> None:
    wanted = "/" + part_name.lstrip("/")
    for node in list(root.findall(qn(CT_NS, "Override"))):
        if node.get("PartName") == wanted:
            root.remove(node)


def parse_relationship_root(
    entries: Dict[str, bytes], rels_path: str
) -> etree._Element:
    if rels_path in entries:
        return parse_xml(entries[rels_path], rels_path)
    return etree.Element(qn(PKG_REL_NS, "Relationships"), nsmap={None: PKG_REL_NS})


def unique_relationship_id(root: etree._Element, preferred: str = "rIdFmt") -> str:
    used = {
        node.get("Id")
        for node in root.findall(qn(PKG_REL_NS, "Relationship"))
        if node.get("Id")
    }
    if preferred not in used:
        return preferred
    index = 1
    while "%s%d" % (preferred, index) in used:
        index += 1
    return "%s%d" % (preferred, index)


def unique_part_name(entries: Dict[str, bytes], desired: str) -> str:
    if desired not in entries:
        return desired
    folder = posixpath.dirname(desired)
    stem, suffix = posixpath.splitext(posixpath.basename(desired))
    index = 1
    while True:
        candidate = posixpath.join(
            folder, "fmt_source_%s_%d%s" % (stem, index, suffix)
        )
        if candidate not in entries:
            return candidate
        index += 1


def copy_part_graph(
    source_entries: Dict[str, bytes],
    target_entries: Dict[str, bytes],
    source_part: str,
    destination_part: str,
    source_content_types: etree._Element,
    target_content_types: etree._Element,
    copied: Dict[str, str],
    stats: TransferStats,
    is_primary: bool = False,
) -> str:
    if source_part in copied:
        return copied[source_part]
    if source_part not in source_entries:
        raise TransferError("源格式部件不存在：%s" % source_part)

    copied[source_part] = destination_part
    target_entries[destination_part] = source_entries[source_part]
    ensure_content_type_override(
        target_content_types,
        destination_part,
        content_type_for(source_content_types, source_part),
    )
    if is_primary:
        stats.source_format_parts_copied += 1
    else:
        stats.dependent_parts_copied += 1

    source_rels_path = relationship_part_path(source_part)
    if source_rels_path not in source_entries:
        return destination_part

    rel_root = parse_xml(source_entries[source_rels_path], source_rels_path)
    for rel in rel_root.findall(qn(PKG_REL_NS, "Relationship")):
        if rel.get("TargetMode") == "External":
            continue
        target = rel.get("Target")
        if not target:
            continue
        dependency_source = resolve_relationship_target(source_part, target)
        if dependency_source not in source_entries:
            stats.warnings.append(
                "源部件关系指向缺失内容：%s -> %s" % (source_part, dependency_source)
            )
            continue

        if dependency_source in copied:
            dependency_destination = copied[dependency_source]
        else:
            desired = dependency_source
            if (
                desired in target_entries
                and target_entries[desired] != source_entries[dependency_source]
            ):
                desired = unique_part_name(target_entries, desired)
            dependency_destination = copy_part_graph(
                source_entries,
                target_entries,
                dependency_source,
                desired,
                source_content_types,
                target_content_types,
                copied,
                stats,
                is_primary=False,
            )
        rel.set(
            "Target",
            relative_relationship_target(destination_part, dependency_destination),
        )

    destination_rels_path = relationship_part_path(destination_part)
    target_entries[destination_rels_path] = serialize_xml(rel_root)
    ensure_content_type_override(
        target_content_types,
        destination_rels_path,
        content_type_for(source_content_types, source_rels_path),
    )
    return destination_part


def collect_format_relationships(
    entries: Dict[str, bytes],
) -> Tuple[etree._Element, Dict[str, Tuple[str, str]]]:
    rels_path = "word/_rels/document.xml.rels"
    root = parse_relationship_root(entries, rels_path)
    roles: Dict[str, Tuple[str, str]] = {}
    for rel in root.findall(qn(PKG_REL_NS, "Relationship")):
        rel_type = rel.get("Type", "")
        role = relationship_role(rel_type)
        target = rel.get("Target")
        if role and target and rel.get("TargetMode") != "External":
            roles[role] = (
                resolve_relationship_target("word/document.xml", target),
                rel_type,
            )
    return root, roles


def _replace_table_style_nodes(
    source_data: bytes,
    target_data: bytes,
    label: str,
    fallback_target_data: Optional[bytes] = None,
) -> Tuple[bytes, int]:
    """Replace only the table-style family in a styles part."""
    source_root = parse_xml(source_data, "源文件 %s" % label)
    target_root = parse_xml(target_data, "目标文件 %s" % label)
    target_roots = [target_root]
    if fallback_target_data is not None:
        target_roots.append(
            parse_xml(fallback_target_data, "目标文件主 styles.xml")
        )
    target_table_styles: List[etree._Element] = []
    seen_style_ids: Set[str] = set()
    for authority in target_roots:
        for node in authority.findall("w:style", namespaces=NS):
            style_id = node.get(qn(W_NS, "styleId"))
            if (
                node.get(qn(W_NS, "type"), "paragraph") != "table"
                or not style_id
                or style_id in seen_style_ids
            ):
                continue
            seen_style_ids.add(style_id)
            target_table_styles.append(copy.deepcopy(node))
    if not target_table_styles:
        return source_data, 0

    for node in list(source_root.findall("w:style", namespaces=NS)):
        if node.get(qn(W_NS, "type"), "paragraph") == "table":
            source_root.remove(node)
    ext_list = source_root.find("w:extLst", namespaces=NS)
    insertion = (
        source_root.index(ext_list) if ext_list is not None else len(source_root)
    )
    for node in target_table_styles:
        source_root.insert(insertion, node)
        insertion += 1
    return serialize_xml(source_root), len(target_table_styles)


def merge_target_table_style_system(
    source_entries: Dict[str, bytes],
    target_entries: Dict[str, bytes],
) -> int:
    """Make the target's table styles authoritative without touching text styles.

    This is used only when the format source has no actually-used table style.
    Keeping the target style definitions prevents a custom or built-in target
    table style from becoming a dangling reference after styles.xml is replaced.
    """
    _source_rels, source_roles = collect_format_relationships(source_entries)
    _target_rels, target_roles = collect_format_relationships(target_entries)
    source_styles = source_roles.get(
        "styles", (ROLE_FALLBACK_PARTS["styles"], "")
    )[0]
    target_styles = target_roles.get(
        "styles", (ROLE_FALLBACK_PARTS["styles"], "")
    )[0]
    if source_styles not in source_entries or target_styles not in target_entries:
        return 0

    merged, count = _replace_table_style_nodes(
        source_entries[source_styles],
        target_entries[target_styles],
        "styles.xml",
    )
    source_entries[source_styles] = merged

    source_effects = source_roles.get("stylesWithEffects")
    if source_effects is not None and source_effects[0] in source_entries:
        target_effects = target_roles.get("stylesWithEffects")
        target_effect_data = (
            target_entries[target_effects[0]]
            if target_effects is not None and target_effects[0] in target_entries
            else target_entries[target_styles]
        )
        merged_effects, _ = _replace_table_style_nodes(
            source_entries[source_effects[0]],
            target_effect_data,
            "stylesWithEffects.xml",
            fallback_target_data=(
                target_entries[target_styles]
                if target_effects is not None
                and target_effects[0] in target_entries
                else None
            ),
        )
        source_entries[source_effects[0]] = merged_effects
    return count


def transfer_format_parts(
    source_entries: Dict[str, bytes],
    target_entries: Dict[str, bytes],
    stats: TransferStats,
) -> None:
    source_ct = parse_content_types(source_entries, "源文件")
    target_ct = parse_content_types(target_entries, "目标文件")
    source_rels_root, source_roles = collect_format_relationships(source_entries)
    target_rels_root, target_roles = collect_format_relationships(target_entries)

    # Fill in conventional paths for valid files whose relationship collection
    # is incomplete.  Styles are mandatory; the rest are optional.
    for role, fallback in ROLE_FALLBACK_PARTS.items():
        if role not in source_roles and fallback in source_entries:
            default_type = {
                "styles": R_NS + "/styles",
                "stylesWithEffects": "http://schemas.microsoft.com/office/2007/relationships/stylesWithEffects",
                "theme": R_NS + "/theme",
                "fontTable": R_NS + "/fontTable",
                "numbering": R_NS + "/numbering",
            }[role]
            source_roles[role] = (fallback, default_type)

    if "styles" not in source_roles:
        raise TransferError("源文件缺少样式关系，无法作为格式来源。")

    # Remove the target's existing style-system relationships.  Other
    # relationships (images, hyperlinks, headers, macros, embedded files) stay.
    old_primary_parts: Set[str] = set()
    for rel in list(target_rels_root.findall(qn(PKG_REL_NS, "Relationship"))):
        role = relationship_role(rel.get("Type", ""))
        target = rel.get("Target")
        if role in ROLE_NAMES and target and rel.get("TargetMode") != "External":
            old_primary_parts.add(
                resolve_relationship_target("word/document.xml", target)
            )
            target_rels_root.remove(rel)

    copied: Dict[str, str] = {}
    new_primary_parts: Set[str] = set()
    for role in ("styles", "stylesWithEffects", "theme", "fontTable", "numbering"):
        source_record = source_roles.get(role)
        if source_record is None:
            continue
        source_part, rel_type = source_record
        destination_part = source_part
        copy_part_graph(
            source_entries,
            target_entries,
            source_part,
            destination_part,
            source_ct,
            target_ct,
            copied,
            stats,
            is_primary=True,
        )
        new_primary_parts.add(destination_part)
        rel = etree.SubElement(target_rels_root, qn(PKG_REL_NS, "Relationship"))
        rel.set("Id", unique_relationship_id(target_rels_root, "rIdFmt"))
        rel.set("Type", rel_type)
        rel.set(
            "Target",
            relative_relationship_target("word/document.xml", destination_part),
        )

    for old_part in old_primary_parts.difference(new_primary_parts):
        target_entries.pop(old_part, None)
        target_entries.pop(relationship_part_path(old_part), None)
        remove_content_type_override(target_ct, old_part)
        remove_content_type_override(target_ct, relationship_part_path(old_part))

    target_entries["word/_rels/document.xml.rels"] = serialize_xml(
        target_rels_root
    )
    target_entries["[Content_Types].xml"] = serialize_xml(target_ct)


NUMBERING_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument."
    "wordprocessingml.numbering+xml"
)


NUMPR_CHILD_ORDER = ("ilvl", "numId", "numberingChange", "ins")


def _merge_num_pr_children(
    destination: Dict[str, etree._Element],
    num_pr: Optional[etree._Element],
) -> None:
    if num_pr is None:
        return
    for child in num_pr:
        destination[local_name(child)] = copy.deepcopy(child)


def _effective_target_num_pr(
    paragraph: etree._Element,
    styles_root: etree._Element,
    target_catalog: StyleCatalog,
) -> Tuple[Optional[etree._Element], bool]:
    """Resolve docDefaults, basedOn and direct numPr child-by-child.

    Word list styles frequently put ``w:numId`` on a base style and only an
    ``w:ilvl`` override on a derived style or paragraph.  Treating ``numPr`` as
    one replace-only property loses that inheritance, so the two semantic
    children are resolved independently here.
    """
    ppr = paragraph.find("w:pPr", namespaces=NS)
    direct = ppr.find("w:numPr", namespaces=NS) if ppr is not None else None
    pstyle = (
        _word_value(ppr.find("w:pStyle", namespaces=NS))
        if ppr is not None
        else None
    )
    style_id = pstyle or target_catalog.fallback("paragraph")
    nodes = _nodes_by_style_id(styles_root)
    chain: List[etree._Element] = []
    current = style_id or ""
    seen: Set[str] = set()
    while current and current not in seen:
        seen.add(current)
        style = nodes.get(current)
        if style is None:
            break
        chain.append(style)
        current = _word_value(style.find("w:basedOn", namespaces=NS)) or ""

    properties: Dict[str, etree._Element] = {}
    defaults = styles_root.find(
        "w:docDefaults/w:pPrDefault/w:pPr/w:numPr", namespaces=NS
    )
    _merge_num_pr_children(properties, defaults)
    style_contributed = False
    for style in reversed(chain):
        style_num_pr = style.find("w:pPr/w:numPr", namespaces=NS)
        if style_num_pr is not None:
            style_contributed = True
            _merge_num_pr_children(properties, style_num_pr)
    _merge_num_pr_children(properties, direct)

    num_id = properties.get("numId")
    if num_id is None or _word_value(num_id) is None:
        return None, False
    raw_num_id = _word_value(num_id)
    if raw_num_id != "0" and not re.fullmatch(r"\d+", raw_num_id or ""):
        return None, False

    level = properties.get("ilvl")
    parsed_level = _safe_int(_word_value(level))
    if raw_num_id != "0" and (
        parsed_level is None or not 0 <= parsed_level <= 8
    ):
        level = etree.Element(qn(W_NS, "ilvl"))
        level.set(qn(W_NS, "val"), "0")
        properties["ilvl"] = level

    result = etree.Element(qn(W_NS, "numPr"))
    for name in NUMPR_CHILD_ORDER:
        child = properties.get(name)
        if child is not None:
            result.append(copy.deepcopy(child))
    for name, child in properties.items():
        if name not in NUMPR_CHILD_ORDER:
            result.append(copy.deepcopy(child))
    inherited = style_contributed and (
        direct is None
        or _word_value(direct.find("w:numId", namespaces=NS)) is None
        or _word_value(direct.find("w:ilvl", namespaces=NS)) is None
    )
    return result, inherited


def materialize_target_body_numbering(
    target_entries: Dict[str, bytes],
    target_catalog: StyleCatalog,
    stats: TransferStats,
) -> int:
    """Turn effective target body-list styles into direct semantic numPr.

    The target paragraph style is about to be replaced by the format source,
    so an inherited list association must first become paragraph-owned.  This
    deliberately skips outline paragraphs; headings continue to obey the
    source heading system.
    """
    styles_data = target_entries.get("word/styles.xml")
    if styles_data is None:
        return 0
    styles_root = parse_xml(styles_data, "目标文件 styles.xml")
    materialized_lists = 0
    for name in sorted(target_entries):
        if not is_content_part(name):
            continue
        root = parse_xml(target_entries[name], name)
        changed = False
        for paragraph in root.xpath("//w:p", namespaces=NS):
            ppr = paragraph.find("w:pPr", namespaces=NS)
            outline = paragraph_outline_level(ppr, target_catalog)
            if outline is not None:
                continue

            effective, inherited = _effective_target_num_pr(
                paragraph, styles_root, target_catalog
            )
            if effective is None:
                continue
            existing = (
                ppr.find("w:numPr", namespaces=NS)
                if ppr is not None
                else None
            )
            if existing is not None and serialize_xml(existing) == serialize_xml(effective):
                continue
            if ppr is None:
                ppr = etree.Element(qn(W_NS, "pPr"))
                paragraph.insert(0, ppr)
            _replace_direct_numbering(ppr, effective)
            changed = True
            num_id = _word_value(effective.find("w:numId", namespaces=NS))
            if inherited and num_id not in {None, "0"}:
                materialized_lists += 1
        if changed:
            target_entries[name] = serialize_xml(root)
    stats.style_list_paragraphs_materialized += materialized_lists
    return materialized_lists


def _direct_content_num_ids(
    entries: Dict[str, bytes],
    target_catalog: Optional[StyleCatalog] = None,
) -> Set[str]:
    """Collect concrete list instances referenced directly by target content."""
    result: Set[str] = set()
    for name in sorted(entries):
        if not is_content_part(name):
            continue
        root = parse_xml(entries[name], name)
        for paragraph in root.xpath("//w:p[w:pPr/w:numPr]", namespaces=NS):
            ppr = paragraph.find("w:pPr", namespaces=NS)
            if ppr is None:
                continue
            outline = (
                paragraph_outline_level(ppr, target_catalog)
                if target_catalog is not None
                else _direct_paragraph_outline_level(ppr)
            )
            if outline is not None and 0 <= outline <= 8:
                continue
            value = _word_value(ppr.find("w:numPr/w:numId", namespaces=NS))
            if value is not None:
                result.add(value)
    return result


def _fresh_numeric_id(
    used: Set[str],
    minimum: int,
    preferred: Optional[str] = None,
) -> str:
    if preferred is not None and re.fullmatch(r"\d+", preferred):
        parsed_preferred = int(preferred)
        if parsed_preferred >= minimum and preferred not in used:
            used.add(preferred)
            return preferred
    numeric = [int(value) for value in used if re.fullmatch(r"\d+", value)]
    candidate = max([minimum - 1] + numeric) + 1
    while str(candidate) in used:
        candidate += 1
    result = str(candidate)
    used.add(result)
    return result


def _numbering_part(
    entries: Dict[str, bytes],
) -> Tuple[Optional[str], Optional[etree._Element]]:
    _rels, roles = collect_format_relationships(entries)
    record = roles.get("numbering")
    part = record[0] if record is not None else ROLE_FALLBACK_PARTS["numbering"]
    if part not in entries:
        return None, None
    return part, parse_xml(entries[part], part)


def _ensure_numbering_part(
    entries: Dict[str, bytes],
) -> Tuple[str, etree._Element]:
    rels_path = "word/_rels/document.xml.rels"
    rels_root, roles = collect_format_relationships(entries)
    record = roles.get("numbering")
    part = record[0] if record is not None else ROLE_FALLBACK_PARTS["numbering"]
    if part in entries:
        root = parse_xml(entries[part], part)
    else:
        root = etree.Element(qn(W_NS, "numbering"), nsmap={"w": W_NS})
        entries[part] = serialize_xml(root)

    if record is None:
        rel = etree.SubElement(rels_root, qn(PKG_REL_NS, "Relationship"))
        rel.set("Id", unique_relationship_id(rels_root, "rIdFmtNumbering"))
        rel.set("Type", R_NS + "/numbering")
        rel.set(
            "Target", relative_relationship_target("word/document.xml", part)
        )
        entries[rels_path] = serialize_xml(rels_root)

    content_types = parse_content_types(entries, "格式源")
    ensure_content_type_override(content_types, part, NUMBERING_CONTENT_TYPE)
    entries["[Content_Types].xml"] = serialize_xml(content_types)
    return part, root


def _insert_numbering_root_child(
    root: etree._Element,
    node: etree._Element,
) -> None:
    name = local_name(node)
    allowed_after: Dict[str, Set[str]] = {
        "numPicBullet": {"numPicBullet"},
        "abstractNum": {"numPicBullet", "abstractNum"},
        "num": {"numPicBullet", "abstractNum", "num"},
    }
    predecessors = allowed_after.get(name)
    if predecessors is None:
        root.append(node)
        return
    insertion = 0
    for index, child in enumerate(root):
        if local_name(child) in predecessors:
            insertion = index + 1
    root.insert(insertion, node)


def _sanitize_imported_list_abstract(
    abstract: etree._Element,
    abstract_id: str,
) -> etree._Element:
    """Materialize list appearance without binding it to target style IDs."""
    result = copy.deepcopy(abstract)
    result.set(qn(W_NS, "abstractNumId"), abstract_id)
    for tag in ("numStyleLink", "styleLink"):
        for node in list(result.findall("w:%s" % tag, namespaces=NS)):
            result.remove(node)
    for node in result.xpath("./w:lvl/w:pStyle", namespaces=NS):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)
    return result


def _relationship_attributes(root: etree._Element) -> Set[str]:
    result: Set[str] = set()
    prefix = "{%s}" % R_NS
    for node in root.iter():
        for attribute, value in node.attrib.items():
            if attribute.startswith(prefix) and value:
                result.add(value)
    return result


def _copy_numbering_relationships(
    picture_nodes: Sequence[etree._Element],
    target_entries: Dict[str, bytes],
    source_entries: Dict[str, bytes],
    target_numbering_part: str,
    source_numbering_part: str,
    stats: TransferStats,
) -> None:
    referenced_ids: Set[str] = set()
    for node in picture_nodes:
        referenced_ids.update(_relationship_attributes(node))
    if not referenced_ids:
        return

    target_rels_path = relationship_part_path(target_numbering_part)
    target_rels = parse_relationship_root(target_entries, target_rels_path)
    target_by_id = {
        str(node.get("Id")): node
        for node in target_rels.findall(qn(PKG_REL_NS, "Relationship"))
        if node.get("Id")
    }
    missing = sorted(referenced_ids.difference(target_by_id))
    if missing:
        raise TransferError(
            "目标文档的图片项目符号关系不完整：%s。" % "、".join(missing)
        )

    source_rels_path = relationship_part_path(source_numbering_part)
    source_rels = parse_relationship_root(source_entries, source_rels_path)
    target_content_types = parse_content_types(target_entries, "内容目标文件")
    source_content_types = parse_content_types(source_entries, "格式源")
    copied: Dict[str, str] = {}
    relationship_map: Dict[str, str] = {}

    for old_id in sorted(referenced_ids):
        target_rel = target_by_id[old_id]
        new_id = unique_relationship_id(source_rels, "rIdTargetList")
        relationship_map[old_id] = new_id
        new_rel = etree.SubElement(
            source_rels, qn(PKG_REL_NS, "Relationship")
        )
        new_rel.set("Id", new_id)
        new_rel.set("Type", target_rel.get("Type", ""))
        target_mode = target_rel.get("TargetMode")
        target_value = target_rel.get("Target")
        if target_mode == "External":
            if target_value is not None:
                new_rel.set("Target", target_value)
            new_rel.set("TargetMode", "External")
            continue
        if not target_value:
            raise TransferError("目标文档的图片项目符号关系缺少目标。")
        dependency_source = resolve_relationship_target(
            target_numbering_part, target_value
        )
        if dependency_source not in target_entries:
            raise TransferError(
                "目标文档的图片项目符号资源缺失：%s。" % dependency_source
            )
        dependency_destination = dependency_source
        if (
            dependency_destination in source_entries
            and source_entries[dependency_destination]
            != target_entries[dependency_source]
        ):
            dependency_destination = unique_part_name(
                source_entries, dependency_destination
            )
        dependency_destination = copy_part_graph(
            target_entries,
            source_entries,
            dependency_source,
            dependency_destination,
            target_content_types,
            source_content_types,
            copied,
            stats,
            is_primary=False,
        )
        new_rel.set(
            "Target",
            relative_relationship_target(
                source_numbering_part, dependency_destination
            ),
        )

    for picture in picture_nodes:
        prefix = "{%s}" % R_NS
        for node in picture.iter():
            for attribute, value in list(node.attrib.items()):
                if attribute.startswith(prefix) and value in relationship_map:
                    node.set(attribute, relationship_map[value])

    source_entries[source_rels_path] = serialize_xml(source_rels)
    source_entries["[Content_Types].xml"] = serialize_xml(source_content_types)


def merge_target_body_numbering(
    source_entries: Dict[str, bytes],
    target_entries: Dict[str, bytes],
    stats: TransferStats,
    target_catalog: Optional[StyleCatalog] = None,
) -> BodyNumberingMergeResult:
    """Import target-owned list instances under collision-free numbering IDs.

    The output style system comes from ``source_entries``, but ordinary lists
    belong to the target's content.  Every referenced concrete ``w:num`` gets
    its own fresh instance so separate target sequences do not accidentally
    continue a source heading/list sequence that happens to use the same ID.
    """
    referenced = _direct_content_num_ids(target_entries, target_catalog)
    result = BodyNumberingMergeResult()
    if "0" in referenced:
        # numId=0 is Word's explicit numbering cancellation and has no concrete
        # definition.  Keeping it protects a paragraph from a numbered style.
        result.num_id_map["0"] = "0"
    requested = {
        value for value in referenced if value != "0" and re.fullmatch(r"\d+", value)
    }
    invalid = sorted(referenced.difference(requested).difference({"0"}))
    if invalid:
        result.warnings.append(
            "目标文档包含无法识别的列表编号引用，已跳过：%s。"
            % "、".join(invalid)
        )
    if not requested:
        return result

    target_part, target_root = _numbering_part(target_entries)
    if target_part is None or target_root is None:
        result.warnings.append(
            "目标文档包含列表段落，但缺少 numbering.xml；这些损坏的列表引用未保留。"
        )
        return result

    target_abstracts = {
        str(node.get(qn(W_NS, "abstractNumId"))): node
        for node in target_root.findall("w:abstractNum", namespaces=NS)
        if node.get(qn(W_NS, "abstractNumId")) is not None
    }
    target_nums = {
        str(node.get(qn(W_NS, "numId"))): node
        for node in target_root.findall("w:num", namespaces=NS)
        if node.get(qn(W_NS, "numId")) is not None
    }
    target_styles: Dict[str, etree._Element] = {}
    if "word/styles.xml" in target_entries:
        target_styles_root = parse_xml(
            target_entries["word/styles.xml"], "目标文件 styles.xml"
        )
        target_styles = {
            str(node.get(qn(W_NS, "styleId"))): node
            for node in target_styles_root.findall("w:style", namespaces=NS)
            if node.get(qn(W_NS, "styleId"))
        }

    source_part, source_root = _ensure_numbering_part(source_entries)
    used_num_ids = {
        str(node.get(qn(W_NS, "numId")))
        for node in source_root.findall("w:num", namespaces=NS)
        if node.get(qn(W_NS, "numId")) is not None
    }
    used_abstract_ids = {
        str(node.get(qn(W_NS, "abstractNumId")))
        for node in source_root.findall("w:abstractNum", namespaces=NS)
        if node.get(qn(W_NS, "abstractNumId")) is not None
    }
    occupied_nsids = _numbering_nsids(source_root)
    used_picture_ids = {
        str(node.get(qn(W_NS, "numPicBulletId")))
        for node in source_root.findall("w:numPicBullet", namespaces=NS)
        if node.get(qn(W_NS, "numPicBulletId")) is not None
    }
    target_pictures = {
        str(node.get(qn(W_NS, "numPicBulletId"))): node
        for node in target_root.findall("w:numPicBullet", namespaces=NS)
        if node.get(qn(W_NS, "numPicBulletId")) is not None
    }

    abstract_id_map: Dict[str, str] = {}
    picture_id_map: Dict[str, str] = {}
    abstract_clones: List[etree._Element] = []
    num_clones: List[etree._Element] = []
    picture_clones: List[etree._Element] = []
    unresolved: List[str] = []

    for old_num_id in sorted(requested, key=lambda value: int(value)):
        target_num = target_nums.get(old_num_id)
        if target_num is None:
            unresolved.append(old_num_id)
            continue
        authority = _abstract_for_num(
            target_num, target_abstracts, target_nums, target_styles
        )
        if authority is None or not authority.findall("w:lvl", namespaces=NS):
            unresolved.append(old_num_id)
            continue
        authority_id = authority.get(qn(W_NS, "abstractNumId"))
        if authority_id is None:
            unresolved.append(old_num_id)
            continue

        new_abstract_id = abstract_id_map.get(authority_id)
        if new_abstract_id is None:
            new_abstract_id = _fresh_numeric_id(
                used_abstract_ids, 0, preferred=authority_id
            )
            abstract_id_map[authority_id] = new_abstract_id
            abstract_clone = _sanitize_imported_list_abstract(
                authority, new_abstract_id
            )
            for picture_ref in abstract_clone.xpath(
                ".//w:lvlPicBulletId", namespaces=NS
            ):
                old_picture_id = _word_value(picture_ref)
                if not old_picture_id:
                    continue
                new_picture_id = picture_id_map.get(old_picture_id)
                if new_picture_id is None:
                    target_picture = target_pictures.get(old_picture_id)
                    if target_picture is None:
                        parent = picture_ref.getparent()
                        if parent is not None:
                            parent.remove(picture_ref)
                        result.warnings.append(
                            "目标列表引用了缺失的图片项目符号 %s，已使用其文本符号回退。"
                            % old_picture_id
                        )
                        continue
                    new_picture_id = _fresh_numeric_id(
                        used_picture_ids, 0, preferred=old_picture_id
                    )
                    picture_id_map[old_picture_id] = new_picture_id
                    picture_clone = copy.deepcopy(target_picture)
                    picture_clone.set(
                        qn(W_NS, "numPicBulletId"), new_picture_id
                    )
                    picture_clones.append(picture_clone)
                picture_ref.set(qn(W_NS, "val"), new_picture_id)
            _assign_independent_numbering_identity(abstract_clone, occupied_nsids)
            abstract_clones.append(abstract_clone)

        new_num_id = _fresh_numeric_id(used_num_ids, 1)
        num_clone = copy.deepcopy(target_num)
        num_clone.set(qn(W_NS, "numId"), new_num_id)
        abstract_reference = num_clone.find("w:abstractNumId", namespaces=NS)
        if abstract_reference is None:
            unresolved.append(old_num_id)
            continue
        abstract_reference.set(qn(W_NS, "val"), new_abstract_id)
        num_clones.append(num_clone)
        result.num_id_map[old_num_id] = new_num_id

    if picture_clones:
        _copy_numbering_relationships(
            picture_clones,
            target_entries,
            source_entries,
            target_part,
            source_part,
            stats,
        )
    for node in picture_clones:
        _insert_numbering_root_child(source_root, node)
    for node in abstract_clones:
        _insert_numbering_root_child(source_root, node)
    for node in num_clones:
        _insert_numbering_root_child(source_root, node)
    source_entries[source_part] = serialize_xml(source_root)

    stats.target_numbering_definitions_imported += len(num_clones)
    stats.target_numbering_abstracts_imported += len(abstract_clones)
    stats.target_picture_bullets_imported += len(picture_clones)
    if unresolved:
        result.warnings.append(
            "目标文档中部分列表定义缺失或无法解析，已跳过编号实例：%s。"
            % "、".join(sorted(unresolved, key=lambda value: int(value)))
        )
    return result


def write_package(package: Package, entries: Dict[str, bytes], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=".%s." % output.name,
        suffix=".tmp",
        dir=str(output.parent),
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(
            str(temp_path), "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            written: Set[str] = set()
            for name in package.order:
                if name not in entries or name in written:
                    continue
                info = package.infos.get(name)
                if info is not None:
                    archive.writestr(info, entries[name])
                else:
                    archive.writestr(name, entries[name])
                written.add(name)
            for name in sorted(set(entries).difference(written)):
                archive.writestr(name, entries[name])

        with zipfile.ZipFile(str(temp_path), "r") as verify:
            bad = verify.testzip()
            if bad:
                raise TransferError("输出文件校验失败，异常条目：%s" % bad)
            for required in (
                "[Content_Types].xml",
                "word/document.xml",
                "word/styles.xml",
            ):
                if required not in verify.namelist():
                    raise TransferError("输出文件缺少必需部件：%s" % required)
            parse_xml(verify.read("word/document.xml"), "输出 document.xml")
            parse_xml(verify.read("word/styles.xml"), "输出 styles.xml")
        os.replace(str(temp_path), str(output))
    finally:
        if temp_path.exists():
            temp_path.unlink()


def transfer(
    source: Path,
    target: Path,
    output: Path,
    force: bool = False,
    preserve_page_layout: bool = False,
    demote_headings: bool = False,
) -> TransferStats:
    source = source.expanduser().resolve()
    target = target.expanduser().resolve()
    output = output.expanduser().resolve()

    if source.suffix.lower() not in SOURCE_SUFFIXES:
        raise TransferError("格式源文件只支持：%s" % ", ".join(sorted(SOURCE_SUFFIXES)))
    if target.suffix.lower() not in TARGET_SUFFIXES:
        raise TransferError("内容目标文件只支持 .docx 或 .docm。")
    if output.suffix.lower() != target.suffix.lower():
        raise TransferError("输出文件扩展名必须与目标文件一致，以避免宏或内容类型损坏。")
    if source == target:
        raise TransferError("格式源文件和内容目标文件不能是同一个文件。")
    if output in {source, target}:
        raise TransferError("为保护原文件，输出位置不能覆盖任一输入文件。")
    if output.exists() and not force:
        raise TransferError("输出文件已存在；请选择新名称，或在命令行使用 --force。")

    source_package = load_package(source, "格式源文件")
    target_package = load_package(target, "内容目标文件")
    source_entries = dict(source_package.entries)
    target_entries = dict(target_package.entries)

    source_catalog = build_style_catalog(
        source_entries["word/styles.xml"], source_entries["word/document.xml"]
    )
    source_used_paragraph_styles = set(source_catalog.used_paragraph_styles)
    source_heading_authority = collect_used_heading_styles(
        source_entries, source_catalog
    )
    source_catalog.authoritative_heading_by_level = dict(
        source_heading_authority
    )
    (
        source_catalog.used_table_styles,
        source_catalog.preferred_table_style,
    ) = collect_used_table_styles(source_entries, source_catalog)
    numbering_conflicts: Set[str] = set()
    source_heading_numbering = extract_heading_numbering_rules(
        source_entries, source_catalog, conflicts=numbering_conflicts
    )
    heading_completion = complete_heading_hierarchy(
        source_entries,
        source_catalog,
        source_heading_authority,
        source_heading_numbering,
    )
    source_heading_numbering = heading_completion.heading_numbering
    source_heading_authority.update(heading_completion.inferred_styles)
    source_used_paragraph_styles.update(
        heading_completion.inferred_styles.values()
    )
    source_catalog = build_style_catalog(
        source_entries["word/styles.xml"], source_entries["word/document.xml"]
    )
    source_catalog.used_paragraph_styles = set(source_used_paragraph_styles)
    source_catalog.authoritative_heading_by_level = dict(
        source_heading_authority
    )
    (
        source_catalog.used_table_styles,
        source_catalog.preferred_table_style,
    ) = collect_used_table_styles(source_entries, source_catalog)
    target_catalog = build_style_catalog(
        target_entries["word/styles.xml"], target_entries["word/document.xml"]
    )
    runtime_inferred_headings: Dict[int, str] = {}
    runtime_completion_warnings: List[str] = []
    if demote_headings:
        target_heading_levels = collect_used_heading_levels(
            target_entries,
            target_catalog,
            part_names=("word/document.xml",),
        )
        desired_heading_levels = {
            min(8, level + 1) for level in target_heading_levels
        }
        missing_heading_levels = sorted(
            desired_heading_levels.difference(source_heading_authority)
        )
        if missing_heading_levels and max(missing_heading_levels) >= 3:
            runtime_completion = complete_heading_hierarchy(
                source_entries,
                source_catalog,
                source_heading_authority,
                source_heading_numbering,
                max_level=max(missing_heading_levels),
                extend_numbering=False,
            )
            runtime_inferred_headings.update(
                runtime_completion.inferred_styles
            )
            runtime_completion_warnings.extend(runtime_completion.warnings)
            source_heading_authority.update(
                runtime_completion.inferred_styles
            )
            source_used_paragraph_styles.update(
                runtime_completion.inferred_styles.values()
            )

            combined_inferred = dict(heading_completion.inferred_styles)
            combined_inferred.update(runtime_completion.inferred_styles)
            if combined_inferred:
                repaired_rules, _extended, warning = _extend_heading_numbering(
                    source_entries,
                    source_heading_authority,
                    combined_inferred,
                    source_heading_numbering,
                )
                source_heading_numbering = repaired_rules
                align_heading_style_numbering(
                    source_entries,
                    source_heading_authority.values(),
                    source_heading_numbering,
                )
                if warning:
                    runtime_completion_warnings.append(warning)

            source_catalog = build_style_catalog(
                source_entries["word/styles.xml"],
                source_entries["word/document.xml"],
            )
            source_catalog.used_paragraph_styles = set(
                source_used_paragraph_styles
            )
            source_catalog.authoritative_heading_by_level = dict(
                source_heading_authority
            )
            (
                source_catalog.used_table_styles,
                source_catalog.preferred_table_style,
            ) = collect_used_table_styles(source_entries, source_catalog)

        unresolved = sorted(
            desired_heading_levels.difference(source_heading_authority)
        )
        if unresolved:
            raise TransferError(
                "格式源无法生成%s，不能安全地把全部标题下调一级；"
                "请确保格式源连续使用了标题一、标题二、标题三。"
                % "、".join("标题%d" % (level + 1) for level in unresolved)
            )
    preserve_target_tables = not source_catalog.used_table_styles
    if preserve_target_tables:
        merge_target_table_style_system(source_entries, target_entries)
        source_catalog = build_style_catalog(
            source_entries["word/styles.xml"], source_entries["word/document.xml"]
        )
        source_catalog.used_paragraph_styles = source_used_paragraph_styles
        source_catalog.authoritative_heading_by_level = dict(
            source_heading_authority
        )
        (
            source_catalog.used_table_styles,
            source_catalog.preferred_table_style,
        ) = collect_used_table_styles(source_entries, source_catalog)
    table_no_indent_styles = ensure_table_no_first_line_indent_styles(
        source_entries,
        source_catalog,
    )
    if table_no_indent_styles:
        source_catalog = build_style_catalog(
            source_entries["word/styles.xml"],
            source_entries["word/document.xml"],
        )
        source_catalog.used_paragraph_styles = (
            set(source_used_paragraph_styles)
            | set(table_no_indent_styles.values())
        )
        source_catalog.authoritative_heading_by_level = dict(
            source_heading_authority
        )
        (
            source_catalog.used_table_styles,
            source_catalog.preferred_table_style,
        ) = collect_used_table_styles(source_entries, source_catalog)
    heading_paragraph_properties = collect_heading_paragraph_properties(
        source_entries,
        source_catalog,
        set(source_heading_numbering) | set(source_heading_authority.values()),
        inherited_style_ids=(
            set(heading_completion.inferred_styles.values())
            | set(runtime_inferred_headings.values())
        ),
        heading_authorities=source_heading_authority,
    )
    heading_paragraph_indents = {
        style_id: dict(indentation)
        for style_id, profile in heading_paragraph_properties.items()
        for indentation in [profile.get("ind")]
        if isinstance(indentation, dict)
    }
    source_layouts = (
        []
        if preserve_page_layout
        else extract_source_section_layout(source_entries["word/document.xml"])
    )

    stats = TransferStats()
    materialize_target_body_numbering(target_entries, target_catalog, stats)
    body_numbering = merge_target_body_numbering(
        source_entries, target_entries, stats, target_catalog
    )
    stats.warnings.extend(body_numbering.warnings)
    if preserve_target_tables:
        stats.warnings.append(
            "格式源未使用表格样式，已保留目标文档的表格外观，并取消表格单元格中的两字符首行缩进。"
        )
    if numbering_conflicts:
        stats.warnings.append(
            "部分标题样式使用了多套编号实例，已采用最常用规则：%s。"
            % "、".join(sorted(numbering_conflicts))
        )
    if heading_completion.inferred_styles:
        stats.warnings.append(
            "已根据标题一至标题三智能补全：%s。"
            % "、".join(
                "标题%d" % (level + 1)
                for level in sorted(heading_completion.inferred_styles)
            )
        )
    stats.warnings.extend(heading_completion.warnings)
    stats.warnings.extend(runtime_completion_warnings)
    for name in sorted(list(target_entries)):
        if not is_content_part(name):
            continue
        target_entries[name] = clean_content_xml(
            target_entries[name],
            name,
            target_catalog,
            source_catalog,
            source_layouts,
            stats,
            heading_numbering=source_heading_numbering,
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

    set_heading_numbering_start_override(
        source_entries,
        source_heading_numbering,
        stats.heading_numbering_start,
    )

    if "word/settings.xml" in source_entries and "word/settings.xml" in target_entries:
        target_entries["word/settings.xml"] = merge_settings(
            source_entries["word/settings.xml"],
            target_entries["word/settings.xml"],
            stats,
            preserve_target_table_default=preserve_target_tables,
        )

    transfer_format_parts(source_entries, target_entries, stats)
    write_package(target_package, target_entries, output)
    return stats


def human_summary(output: Path, stats: TransferStats) -> str:
    lines = [
        "处理完成",
        "输出：%s" % output,
        "清理内容部件：%d" % stats.content_parts_cleaned,
        "处理段落/文字片段/表格：%d / %d / %d"
        % (stats.paragraphs_seen, stats.runs_seen, stats.tables_seen),
        "应用标题编号：%d" % stats.heading_numbers_applied,
        "恢复标题段落缩进：%d" % stats.heading_indents_applied,
        "清理重复手工标题序号：%d" % stats.heading_prefixes_removed,
        "取消表格两字符首行缩进：%d"
        % stats.table_paragraph_indents_cleared,
        "加固表格零首行缩进样式：%d"
        % stats.table_paragraph_styles_hardened,
        "清除直接格式属性：%d"
        % (
            stats.paragraph_properties_removed
            + stats.run_properties_removed
            + stats.table_properties_removed
        ),
        "导入格式部件：%d" % stats.source_format_parts_copied,
    ]
    if stats.warnings:
        lines.append("提示：" + "；".join(stats.warnings))
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把一个 Word 文件的格式系统迁移到另一个文件，同时保留目标内容。"
    )
    parser.add_argument("--source", required=True, help="格式源 .docx/.docm/.dotx/.dotm")
    parser.add_argument("--target", required=True, help="保留内容的目标 .docx/.docm")
    parser.add_argument("--out", required=True, help="新输出文件；不能覆盖输入文件")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的输出文件")
    parser.add_argument(
        "--preserve-page-layout",
        action="store_true",
        help="保留目标文件的纸张、页边距和分栏，而不是从源文件导入",
    )
    parser.add_argument(
        "--demote-headings",
        action="store_true",
        help="把正文中的标题一至标题八依次向下调整一级",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 结果，便于其他脚本调用",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output = Path(args.out)
    try:
        stats = transfer(
            Path(args.source),
            Path(args.target),
            output,
            force=args.force,
            preserve_page_layout=args.preserve_page_layout,
            demote_headings=args.demote_headings,
        )
    except TransferError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print("处理失败：%s" % exc, file=sys.stderr)
        return 2
    except Exception as exc:  # last-resort guard for double-click use
        if args.json:
            print(
                json.dumps(
                    {"ok": False, "error": "未预期错误：%s" % exc},
                    ensure_ascii=False,
                )
            )
        else:
            print("处理失败（未预期错误）：%s" % exc, file=sys.stderr)
        return 3

    if args.json:
        print(
            json.dumps(
                {"ok": True, "output": str(output.resolve()), "stats": asdict(stats)},
                ensure_ascii=False,
            )
        )
    else:
        print(human_summary(output.resolve(), stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
