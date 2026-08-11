#!/usr/bin/env python3
"""Theme-font and cross-locale font-alias regressions for style packs."""

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


def read_zip(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def write_zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def set_font_alias(
    entries: dict[str, bytes], primary: str, alternate: str
) -> None:
    part_name = "word/fontTable.xml"
    root = core.parse_xml(entries[part_name], part_name)
    matches = root.xpath(
        "./w:font[@w:name=$name]", namespaces=core.NS, name=primary
    )
    if matches:
        font = matches[0]
    else:
        font = etree.SubElement(root, core.qn(core.W_NS, "font"))
        font.set(core.qn(core.W_NS, "name"), primary)
    alt_name = font.find("w:altName", namespaces=core.NS)
    if alt_name is None:
        alt_name = etree.SubElement(font, core.qn(core.W_NS, "altName"))
    alt_name.set(core.qn(core.W_NS, "val"), alternate)
    entries[part_name] = core.serialize_xml(root)


def used_format(manifest: dict[str, object], style_id: str) -> dict[str, object]:
    return next(
        item
        for item in manifest["used_formats"]
        if item["style_id"] == style_id
    )


class FontAliasThemeResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(
            prefix="forma-font-alias-theme-"
        )
        self.working_dir = Path(self._temporary.name)

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def test_theme_fonts_override_same_level_fallbacks(self) -> None:
        _package, _catalog, manifest = manager.inspect_source(
            FIXTURES / "source.docx"
        )
        heading = used_format(manifest, "Heading1")
        self.assertEqual(heading["font_latin"], "Calibri")
        self.assertEqual(heading["font_east_asia"], "ＭＳ ゴシック")
        self.assertNotIn(
            heading["font_latin"], {"majorHAnsi", "majorAscii"}
        )
        self.assertNotIn(
            heading["font_east_asia"], {"majorEastAsia"}
        )

        # Normal declares explicit fonts at a more specific style level.  A
        # theme reference inherited from docDefaults must not override them.
        normal = used_format(manifest, "Normal")
        self.assertEqual(normal["font_latin"], "Arial")
        self.assertEqual(normal["font_east_asia"], "Hiragino Sans GB")
        self.assertNotIn("font_latin_aliases", normal)
        self.assertNotIn("font_east_asia_aliases", normal)

    def test_theme_font_lang_selects_east_asian_supplemental_face(self) -> None:
        entries = read_zip(FIXTURES / "source.docx")
        settings = core.parse_xml(entries["word/settings.xml"], "settings.xml")
        language = settings.find("w:themeFontLang", namespaces=core.NS)
        self.assertIsNotNone(language)
        expected = {
            "ja-JP": "ＭＳ ゴシック",
            "zh-CN": "宋体",
            "zh-Hant": "新細明體",
            "ko-KR": "맑은 고딕",
        }
        for locale, font_name in expected.items():
            with self.subTest(locale=locale):
                language.set(core.qn(core.W_NS, "eastAsia"), locale)
                entries["word/settings.xml"] = core.serialize_xml(settings)
                theme = manager._theme_metadata(entries)
                self.assertEqual(theme["fonts"]["majorEastAsia"], font_name)

    def test_unresolved_theme_reference_never_becomes_a_font_name(self) -> None:
        package = core.load_package(FIXTURES / "source.docx", "fixture")
        entries = package.entries
        catalog = core.build_style_catalog(
            entries["word/styles.xml"], entries["word/document.xml"]
        )
        styles_root = core.parse_xml(entries["word/styles.xml"], "styles.xml")
        latin, east_asia = manager._effective_style_fonts(
            "Heading1", catalog, styles_root, {"fonts": {}, "colors": {}}
        )
        self.assertEqual(latin, "Arial")
        self.assertEqual(east_asia, "Hiragino Sans GB")
        self.assertNotIn(latin, {"majorHAnsi", "majorAscii"})
        self.assertNotEqual(east_asia, "majorEastAsia")

    def test_font_table_aliases_are_bidirectional_nfkc_and_not_split(self) -> None:
        entries = read_zip(FIXTURES / "source.docx")
        set_font_alias(entries, "Calibri", "Calibri, Corporate")
        set_font_alias(entries, "ＭＳ ゴシック", "MS Gothic")

        aliases = manager._font_aliases(entries)
        self.assertEqual(
            aliases[manager._font_alias_key("Calibri")],
            ["Calibri, Corporate"],
        )
        self.assertEqual(
            aliases[manager._font_alias_key("Calibri, Corporate")],
            ["Calibri"],
        )
        self.assertEqual(
            aliases[manager._font_alias_key("MS ゴシック")],
            ["MS Gothic"],
        )
        self.assertEqual(
            aliases[manager._font_alias_key("ms gothic")],
            ["ＭＳ ゴシック"],
        )

        source = self.working_dir / "font-aliases.docx"
        write_zip(source, entries)
        _package, _catalog, manifest = manager.inspect_source(source)
        heading = used_format(manifest, "Heading1")
        self.assertEqual(
            heading["font_latin_aliases"], ["Calibri, Corporate"]
        )
        self.assertEqual(heading["font_east_asia_aliases"], ["MS Gothic"])

    def test_aliases_refresh_after_derivation_and_old_packs_still_load(self) -> None:
        entries = read_zip(FIXTURES / "source.docx")
        set_font_alias(entries, "Calibri", "Calibri Display Alias")
        source = self.working_dir / "alias-source.docx"
        write_zip(source, entries)
        pack = self.working_dir / "alias-source.wfstyle"
        manager.create_style_pack(source, pack, display_name="字体别名")

        derived = self.working_dir / "alias-derived.wfstyle"
        manager.derive_style_pack(
            pack,
            derived,
            {"styles": [{"style_id": "Heading1", "size_pt": 19.5}]},
            display_name="字体别名派生",
        )
        derived_manifest, _derived_entries = manager.load_style_pack(derived)
        self.assertEqual(
            used_format(derived_manifest, "Heading1")["font_latin_aliases"],
            ["Calibri Display Alias"],
        )

        legacy_manifest, pack_entries = manager.load_style_pack(pack)
        for item in legacy_manifest["used_formats"]:
            item.pop("font_latin_aliases", None)
            item.pop("font_east_asia_aliases", None)
        legacy = self.working_dir / "legacy-no-alias-fields.wfstyle"
        manager._write_style_pack_archive(
            legacy, legacy_manifest, pack_entries, force=True
        )
        loaded, _loaded_entries = manager.load_style_pack(legacy)
        self.assertEqual(loaded["id"], legacy_manifest["id"])
        self.assertEqual(
            used_format(loaded, "Heading1")["font_latin_aliases"],
            ["Calibri Display Alias"],
        )

    def test_alias_manifest_fields_are_bounded_and_normalized(self) -> None:
        pack = self.working_dir / "validation-base.wfstyle"
        manager.create_style_pack(
            FIXTURES / "source.docx", pack, display_name="别名校验"
        )
        manifest, _entries = manager.load_style_pack(pack)
        heading = used_format(manifest, "Heading1")

        invalid_values = (
            "not-a-list",
            ["同名字体", "同名字体"],
            ["ＭＳ ゴシック", "MS ゴシック"],
            ["Ｃａｌｉｂｒｉ"],
            ["Alias %d" % index for index in range(65)],
        )
        for value in invalid_values:
            with self.subTest(value_type=type(value).__name__, value=value):
                malformed = copy.deepcopy(manifest)
                candidate = used_format(malformed, "Heading1")
                candidate["font_latin_aliases"] = value
                if value == ["Ｃａｌｉｂｒｉ"]:
                    candidate["font_latin"] = "Calibri"
                with self.assertRaises(core.TransferError):
                    manager._validate_style_pack_manifest(malformed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
