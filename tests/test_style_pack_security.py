#!/usr/bin/env python3
"""Re-signed format packs must still satisfy the formatting-only contract.

[INPUT]: 依赖 __future__, base64, copy, json, sys, tempfile, unittest, zipfile, pathlib, lxml, style_pack_manager, word_style_transfer
[OUTPUT] Loader rejection and valid legacy/create/derive workflow regressions
[POS] Format library trust boundary regression suite
[PROTOCOL] Keep this header and the project indexes synchronized after edits.
"""

from __future__ import annotations

import base64
import copy
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from lxml import etree

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
import style_pack_manager as manager
import word_style_transfer as core


class StylePackSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="forma-pack-contract-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.pack = self.root / "safe.wfstyle"
        manager.create_style_pack(PROJECT_DIR / "tests/fixtures/source.docx", self.pack)
        self.manifest, self.entries = manager.load_style_pack(self.pack)

    def write_unchecked(self, entries=None, manifest=None) -> Path:
        entries = self.entries if entries is None else entries
        manifest = copy.deepcopy(self.manifest if manifest is None else manifest)
        manifest.pop("pack_path", None)
        manifest["part_sha256"] = manager._part_checksums(entries)
        manifest["format_fingerprint"] = manager._format_fingerprint(manifest["part_sha256"])
        manifest["format_part_count"] = len(entries)
        path = self.root / "hostile.wfstyle"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest).encode())
            for name, data in entries.items():
                archive.writestr("parts/" + name, data)
        return path

    def test_extra_binary_or_nested_relationship_parts_are_rejected(self):
        for name, data in (
            ("word/media/picture.png", b"PNG payload"),
            ("word/theme/_rels/theme1.xml.rels", b'<Relationships xmlns="%s"/>' % core.PKG_REL_NS.encode()),
            ("word/document.xml", b'<w:document xmlns:w="%s"/>' % core.W_NS.encode()),
        ):
            with self.subTest(name=name):
                entries = dict(self.entries, **{name: data})
                with self.assertRaises(core.TransferError):
                    manager.load_style_pack(self.write_unchecked(entries))

    def test_relationship_type_namespace_external_duplicate_and_role_mismatch_rejected(self):
        for mutation in ("fake-type", "external", "duplicate-role", "duplicate-id", "wrong-root", "binary-role"):
            with self.subTest(mutation=mutation):
                entries = dict(self.entries)
                root = core.parse_xml(entries["word/_rels/document.xml.rels"], "rels")
                rel = root[0]
                if mutation == "fake-type":
                    rel.set("Type", "https://example.invalid/styles")
                elif mutation == "external":
                    rel.set("TargetMode", "External")
                elif mutation == "duplicate-role":
                    duplicate = copy.deepcopy(rel)
                    duplicate.set("Id", "different-id")
                    root.append(duplicate)
                elif mutation == "duplicate-id":
                    root[1].set("Id", rel.get("Id"))
                elif mutation == "wrong-root":
                    entries["word/styles.xml"] = b'<styles xmlns="urn:untrusted"/>'
                else:
                    entries["word/styles.xml"] = b"not XML"
                entries["word/_rels/document.xml.rels"] = core.serialize_xml(root)
                with self.assertRaises(core.TransferError):
                    manager.load_style_pack(self.write_unchecked(entries))

    def test_relationship_hooks_and_embedded_binary_format_nodes_are_rejected(self):
        for part, tag in (("word/styles.xml", "drawing"), ("word/fontTable.xml", "embedRegular"), ("word/numbering.xml", "numPicBullet")):
            if part not in self.entries:
                continue
            with self.subTest(part=part):
                entries = dict(self.entries)
                root = core.parse_xml(entries[part], part)
                etree.SubElement(root, core.qn(core.W_NS, tag))
                entries[part] = core.serialize_xml(root)
                with self.assertRaises(core.TransferError):
                    manager.load_style_pack(self.write_unchecked(entries))
        entries = dict(self.entries)
        root = core.parse_xml(entries["word/styles.xml"], "styles")
        root[0].set(core.qn(core.R_NS, "id"), "rIdImage")
        entries["word/styles.xml"] = core.serialize_xml(root)
        with self.assertRaises(core.TransferError):
            manager.load_style_pack(self.write_unchecked(entries))

    def test_settings_and_layout_namespace_and_tags_are_checked(self):
        for tag in (core.qn(core.W_NS, "attachedTemplate"), "{urn:untrusted}pgMar"):
            with self.subTest(tag=tag):
                manifest = copy.deepcopy(self.manifest)
                manifest["section_layouts"] = [[base64.b64encode(core.serialize_xml(etree.Element(tag))).decode()]]
                with self.assertRaises(core.TransferError):
                    manager.load_style_pack(self.write_unchecked(manifest=manifest))
        entries = dict(self.entries)
        root = core.parse_xml(entries["word/settings.xml"], "settings")
        etree.SubElement(root, core.qn(core.W_NS, "attachedTemplate"))
        entries["word/settings.xml"] = core.serialize_xml(root)
        with self.assertRaises(core.TransferError):
            manager.load_style_pack(self.write_unchecked(entries))

    def test_valid_legacy_and_derived_pack_can_be_loaded(self):
        legacy = copy.deepcopy(self.manifest)
        for key in ("heading_numbering", "heading_authorities", "heading_paragraph_properties", "format_fingerprint"):
            legacy.pop(key, None)
        manager.load_style_pack(self.write_unchecked(manifest=legacy))
        derived = self.root / "derived.wfstyle"
        manager.derive_style_pack(self.pack, derived, {"styles": [{"style_id": "Heading1", "size_pt": 18}]})
        manager.load_style_pack(derived)


if __name__ == "__main__":
    unittest.main()
