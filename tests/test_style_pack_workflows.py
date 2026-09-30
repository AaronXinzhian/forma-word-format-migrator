#!/usr/bin/env python3
"""End-to-end format-library exchange, preflight and constrained edits.

[INPUT]: 依赖 __future__, contextlib, copy, hashlib, io, json, os, shutil, sys, tempfile, unittest, pathlib, lxml, style_pack_manager, word_style_transfer
[OUTPUT] Exchange preservation, stale-preflight rejection, edited DOCX and independent list identity checks
[POS] Format-library workflow regression suite including cloned heading and body-list identity isolation
[PROTOCOL] Keep this header and the project indexes synchronized after edits.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lxml import etree

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
import style_pack_manager as manager
import word_style_transfer as core


class StylePackWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="forma-library-flow-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.pack = self.root / "source.wfstyle"
        manager.create_style_pack(PROJECT_DIR / "tests/fixtures/source-numbered-headings.docx", self.pack)
        self.target = self.root / "target.docx"
        shutil.copy2(PROJECT_DIR / "tests/fixtures/target.docx", self.target)

    def _append_target_paragraphs(self, paragraphs):
        package = core.load_package(self.target, "target")
        document = core.parse_xml(package.entries["word/document.xml"], "document")
        body = document.find("w:body", namespaces=core.NS)
        section = body.find("w:sectPr", namespaces=core.NS)
        insertion = body.index(section) if section is not None else len(body)
        for text, style_id, num_id in paragraphs:
            paragraph = etree.Element(core.qn(core.W_NS, "p"))
            properties = etree.SubElement(paragraph, core.qn(core.W_NS, "pPr"))
            style = etree.SubElement(properties, core.qn(core.W_NS, "pStyle"))
            style.set(core.qn(core.W_NS, "val"), style_id)
            if num_id is not None:
                numbering = etree.SubElement(properties, core.qn(core.W_NS, "numPr"))
                for tag, value in (("ilvl", "0"), ("numId", num_id)):
                    node = etree.SubElement(numbering, core.qn(core.W_NS, tag))
                    node.set(core.qn(core.W_NS, "val"), value)
            run = etree.SubElement(paragraph, core.qn(core.W_NS, "r"))
            etree.SubElement(run, core.qn(core.W_NS, "t")).text = text
            body.insert(insertion, paragraph)
            insertion += 1
        package.entries["word/document.xml"] = core.serialize_xml(document)
        core.write_package(package, package.entries, self.target)

    def _active_heading_abstract(self, entries, style_id):
        catalog = core.build_style_catalog(entries["word/styles.xml"], entries.get("word/document.xml", manager._placeholder_document()))
        rule = core.infer_heading_numbering_rules(entries, catalog, [style_id])[style_id]
        _root, abstracts, nums, styles = core._numbering_index(entries)
        abstract = core._abstract_for_num(nums[rule.num_id], abstracts, nums, styles)
        self.assertIsNotNone(abstract)
        return rule, abstract

    def _assert_original_abstracts_and_fresh_clone_nsids(self, before_entries, after_entries):
        before_root, before, _nums, _styles = core._numbering_index(before_entries)
        _after_root, after, _nums, _styles = core._numbering_index(after_entries)
        for abstract_id, original in before.items():
            self.assertIn(abstract_id, after)
            self.assertEqual(etree.tostring(after[abstract_id], method="c14n"), etree.tostring(original, method="c14n"))
        occupied = {value.upper() for value in before_root.xpath("./w:abstractNum/w:nsid/@w:val", namespaces=core.NS)}
        clone_nsids = []
        for abstract_id in set(after).difference(before):
            value = after[abstract_id].xpath("string(w:nsid/@w:val)", namespaces=core.NS)
            self.assertRegex(value, r"^[0-9A-Fa-f]{8}$")
            self.assertNotIn(value.upper(), occupied)
            clone_nsids.append(value.upper())
        self.assertTrue(clone_nsids, "the workflow must actually create an independent abstract list")
        self.assertEqual(len(clone_nsids), len(set(clone_nsids)))

    def test_created_and_applied_inferred_headings_have_independent_list_identity(self):
        source = core.load_package(PROJECT_DIR / "tests/fixtures/source-numbered-headings.docx", "source")
        _manifest, pack_entries = manager.load_style_pack(self.pack)
        self._assert_original_abstracts_and_fresh_clone_nsids(source.entries, pack_entries)
        _rule, original = self._active_heading_abstract(source.entries, "Heading3")
        original_nsid = original.xpath("string(w:nsid/@w:val)", namespaces=core.NS)
        original_template = original.xpath("string(w:tmpl/@w:val)", namespaces=core.NS)
        for style_id in ("Heading4", "Heading5"):
            rule, abstract = self._active_heading_abstract(pack_entries, style_id)
            self.assertEqual(rule.level, int(style_id[-1]) - 1)
            self.assertNotEqual(abstract.xpath("string(w:nsid/@w:val)", namespaces=core.NS), original_nsid)
            self.assertEqual(abstract.xpath("string(w:tmpl/@w:val)", namespaces=core.NS), original_template)
        self._append_target_paragraphs([("identity " + style_id, style_id, None) for style_id in ("Heading4", "Heading5")])
        output = self.root / "independent-inferred.docx"
        manager.apply_style_pack(self.pack, self.target, output)
        result = core.load_package(output, "result")
        self._assert_original_abstracts_and_fresh_clone_nsids(pack_entries, result.entries)
        for style_id in ("Heading4", "Heading5"):
            rule, abstract = self._active_heading_abstract(result.entries, style_id)
            self.assertEqual(rule.level_text, ".".join("%%%d" % level for level in range(1, int(style_id[-1]) + 1)))
            self.assertEqual(abstract.xpath("string(w:tmpl/@w:val)", namespaces=core.NS), original_template)

    def test_edited_h4_demotion_uses_fresh_identity_and_preserves_numbering_pattern(self):
        derived = self.root / "hyphen-h4.wfstyle"
        manager.derive_style_pack(self.pack, derived, {"styles": [{"style_id": "Heading4", "numbering_pattern": "%1-%2-%3-%4"}]})
        _manifest, entries = manager.load_style_pack(derived)
        self._append_target_paragraphs([("demote into edited H4", "Heading3", None), ("extend to H6", "Heading5", None)])
        output = self.root / "hyphen-h4-demoted.docx"
        manager.apply_style_pack(derived, self.target, output, demote_headings=True)
        result = core.load_package(output, "result")
        self._assert_original_abstracts_and_fresh_clone_nsids(entries, result.entries)
        rule, abstract = self._active_heading_abstract(result.entries, "Heading4")
        self.assertEqual(rule.level_text, "%1-%2-%3-%4")
        self.assertEqual(core._level_node(abstract, 3).xpath("string(w:lvlText/@w:val)", namespaces=core.NS), "%1-%2-%3-%4")
        document = core.parse_xml(result.entries["word/document.xml"], "document")
        paragraph = next(node for node in document.xpath("//w:p", namespaces=core.NS) if "".join(node.xpath(".//w:t/text()", namespaces=core.NS)) == "demote into edited H4")
        self.assertEqual(paragraph.xpath("string(w:pPr/w:pStyle/@w:val)", namespaces=core.NS), "Heading4")
        self.assertEqual(paragraph.xpath("string(w:pPr/w:numPr/w:numId/@w:val)", namespaces=core.NS), rule.num_id)
        self.assertEqual(paragraph.xpath("string(w:pPr/w:numPr/w:ilvl/@w:val)", namespaces=core.NS), "3")
        self.assertEqual(self._active_heading_abstract(result.entries, "Heading6")[0].level, 5)

    def test_duplicate_nsid_legacy_pack_runtime_repair_keeps_user_numbering_edits(self):
        edits = {
            "Heading4": {"numbering_format": "upperRoman", "numbering_pattern": "%1-%2-%3-%4", "numbering_start": 4, "numbering_restart": False},
            "Heading5": {"numbering_format": "lowerLetter", "numbering_pattern": "第%5节", "numbering_start": 3, "numbering_restart": True},
        }
        derived = self.root / "legacy-edited.wfstyle"
        manager.derive_style_pack(self.pack, derived, {"styles": [{"style_id": style_id, **fields} for style_id, fields in edits.items()]})
        manifest, entries = manager.load_style_pack(derived)
        manifest.pop("heading_numbering_user_edits")
        root, abstracts, nums, styles = core._numbering_index(entries)
        rule = core.heading_numbering_from_manifest(manifest["heading_numbering"], entries, core.build_style_catalog(entries["word/styles.xml"], manager._placeholder_document()))["Heading4"]
        clone = core._abstract_for_num(nums[rule.num_id], abstracts, nums, styles)
        source = core.load_package(PROJECT_DIR / "tests/fixtures/source-numbered-headings.docx", "source")
        original = self._active_heading_abstract(source.entries, "Heading3")[1]
        duplicate_nsid = original.xpath("string(w:nsid/@w:val)", namespaces=core.NS)
        clone.find("w:nsid", namespaces=core.NS).set(core.qn(core.W_NS, "val"), duplicate_nsid)
        self.assertGreater(len(root.xpath("./w:abstractNum[w:nsid/@w:val=$nsid]", namespaces=core.NS, nsid=duplicate_nsid)), 1)
        entries["word/numbering.xml"] = core.serialize_xml(root)
        legacy = self.root / "duplicate-nsid-legacy.wfstyle"
        manager._write_style_pack_archive(legacy, manifest, entries)
        before = legacy.read_bytes()
        self._append_target_paragraphs([("legacy identity " + style_id, style_id, None) for style_id in edits])
        output = self.root / "duplicate-nsid-repaired.docx"
        manager.apply_style_pack(legacy, self.target, output)
        result = core.load_package(output, "result")
        self._assert_original_abstracts_and_fresh_clone_nsids(entries, result.entries)
        for style_id, fields in edits.items():
            rule, abstract = self._active_heading_abstract(result.entries, style_id)
            self.assertNotEqual(abstract.xpath("string(w:nsid/@w:val)", namespaces=core.NS), duplicate_nsid)
            self.assertEqual(rule.number_format, fields["numbering_format"])
            self.assertEqual(rule.level_text, fields["numbering_pattern"])
            self.assertEqual(rule.start, fields["numbering_start"])
            self.assertIs(manager._numbering_restarts(result.entries, rule), fields["numbering_restart"])
        self.assertEqual(legacy.read_bytes(), before)

    def test_body_list_import_collision_changes_only_identity_and_preserves_shared_abstract(self):
        _manifest, source_entries = manager.load_style_pack(self.pack)
        _source_root, source_abstracts, _nums, _styles = core._numbering_index(source_entries)
        target = core.load_package(self.target, "target")
        root, abstracts, nums, styles = core._numbering_index(target.entries)
        authority = core._abstract_for_num(nums["1"], abstracts, nums, styles)
        imported = copy.deepcopy(authority)
        imported.set(core.qn(core.W_NS, "abstractNumId"), "777")
        conflicting_nsid = next(iter(source_abstracts.values())).xpath("string(w:nsid/@w:val)", namespaces=core.NS)
        imported.find("w:nsid", namespaces=core.NS).set(core.qn(core.W_NS, "val"), conflicting_nsid)
        imported.find("w:tmpl", namespaces=core.NS).set(core.qn(core.W_NS, "val"), "AA001122")
        level = core._level_node(imported, 0)
        for node in list(level.findall("w:pStyle", namespaces=core.NS)):
            level.remove(node)
        for tag, value in (("numFmt", "decimal"), ("lvlText", "%1)"), ("lvlJc", "right")):
            core._set_level_child_value(level, tag, value)
        properties = level.find("w:pPr", namespaces=core.NS)
        if properties is None:
            properties = etree.SubElement(level, core.qn(core.W_NS, "pPr"))
        indent = properties.find("w:ind", namespaces=core.NS)
        if indent is None:
            indent = etree.SubElement(properties, core.qn(core.W_NS, "ind"))
        indent.set(core.qn(core.W_NS, "left"), "1234")
        indent.set(core.qn(core.W_NS, "hanging"), "321")
        core._insert_numbering_root_child(root, imported)
        original_nums = {}
        for num_id in ("777", "778"):
            instance = etree.Element(core.qn(core.W_NS, "num"), nsmap={"w": core.W_NS})
            instance.set(core.qn(core.W_NS, "numId"), num_id)
            etree.SubElement(instance, core.qn(core.W_NS, "abstractNumId")).set(core.qn(core.W_NS, "val"), "777")
            if num_id == "777":
                override = etree.SubElement(instance, core.qn(core.W_NS, "lvlOverride"))
                override.set(core.qn(core.W_NS, "ilvl"), "0")
                etree.SubElement(override, core.qn(core.W_NS, "startOverride")).set(core.qn(core.W_NS, "val"), "7")
            original_nums[num_id] = copy.deepcopy(instance)
            core._insert_numbering_root_child(root, instance)
        target.entries["word/numbering.xml"] = core.serialize_xml(root)
        core.write_package(target, target.entries, self.target)
        self._append_target_paragraphs([("body from seven", "Normal", "777"), ("body continuation", "Normal", "777"), ("body independent", "Normal", "778")])
        output = self.root / "body-identity-isolated.docx"
        manager.apply_style_pack(self.pack, self.target, output)
        result = core.load_package(output, "result")
        self._assert_original_abstracts_and_fresh_clone_nsids(source_entries, result.entries)
        document = core.parse_xml(result.entries["word/document.xml"], "document")
        mapped = {}
        for text in ("body from seven", "body continuation", "body independent"):
            paragraph = next(node for node in document.xpath("//w:p", namespaces=core.NS) if "".join(node.xpath(".//w:t/text()", namespaces=core.NS)) == text)
            mapped[text] = paragraph.xpath("string(w:pPr/w:numPr/w:numId/@w:val)", namespaces=core.NS)
        self.assertEqual(mapped["body from seven"], mapped["body continuation"])
        self.assertNotEqual(mapped["body from seven"], mapped["body independent"])
        _root, result_abstracts, result_nums, result_styles = core._numbering_index(result.entries)
        shared = core._abstract_for_num(result_nums[mapped["body from seven"]], result_abstracts, result_nums, result_styles)
        independent = core._abstract_for_num(result_nums[mapped["body independent"]], result_abstracts, result_nums, result_styles)
        self.assertEqual(shared.get(core.qn(core.W_NS, "abstractNumId")), independent.get(core.qn(core.W_NS, "abstractNumId")))
        self.assertNotEqual(shared.xpath("string(w:nsid/@w:val)", namespaces=core.NS), conflicting_nsid)
        self.assertEqual(shared.xpath("string(w:tmpl/@w:val)", namespaces=core.NS), "AA001122")
        self.assertEqual(etree.tostring(core._level_node(shared, 0), method="c14n"), etree.tostring(level, method="c14n"))
        for old_id, text in (("777", "body from seven"), ("778", "body independent")):
            actual = copy.deepcopy(result_nums[mapped[text]])
            actual.set(core.qn(core.W_NS, "numId"), old_id)
            actual.find("w:abstractNumId", namespaces=core.NS).set(core.qn(core.W_NS, "val"), "777")
            self.assertEqual(etree.tostring(actual, method="c14n"), etree.tostring(original_nums[old_id], method="c14n"))

    def test_export_import_is_validated_deduplicated_and_preserves_source(self):
        original = self.pack.read_bytes()
        export = self.root / "share.wfstyle"
        exported = manager.export_style_pack(self.pack, export)
        imported, changed = manager.import_style_pack(export, self.root / "library")
        repeated, changed_again = manager.import_style_pack(export, self.root / "library")
        self.assertTrue(changed)
        self.assertFalse(changed_again)
        self.assertEqual(imported["pack_path"], repeated["pack_path"])
        self.assertEqual(imported["format_fingerprint"], exported["format_fingerprint"])
        self.assertEqual(self.pack.read_bytes(), original)
        with self.assertRaises(core.TransferError):
            manager.export_style_pack(self.pack, self.pack, force=True)

    def test_preflight_reads_actual_input_binds_options_and_does_not_write(self):
        pack_bytes, target_bytes = self.pack.read_bytes(), self.target.read_bytes()
        _manifest, report = manager.preflight_style_pack(self.pack, self.target, demote_headings=True, preserve_page_layout=True)
        self.assertGreater(report["summary"]["paragraph_count"], 0)
        self.assertGreater(report["summary"]["table_count"], 0)
        self.assertGreater(report["heading_demotion_count"], 0)
        self.assertEqual(report["page_layout_action"], "preserve_target")
        self.assertEqual(report["input_binding"]["target_sha256"], hashlib.sha256(target_bytes).hexdigest())
        self.assertTrue(report["input_binding"]["demote_headings"])
        self.assertEqual(self.pack.read_bytes(), pack_bytes)
        self.assertEqual(self.target.read_bytes(), target_bytes)

    def test_apply_rejects_stale_target_or_pack_before_output(self):
        _manifest, report = manager.preflight_style_pack(self.pack, self.target)
        binding = report["input_binding"]
        for field in ("expected_pack_sha256", "expected_target_sha256"):
            kwargs = {"expected_pack_sha256": binding["pack_sha256"], "expected_target_sha256": binding["target_sha256"]}
            kwargs[field] = "0" * 64
            output = self.root / (field + ".docx")
            with self.assertRaisesRegex(core.TransferError, "预检|变化"):
                manager.apply_style_pack(self.pack, self.target, output, **kwargs)
            self.assertFalse(output.exists())
        output = self.root / "fresh.docx"
        manager.apply_style_pack(self.pack, self.target, output, expected_pack_sha256=binding["pack_sha256"], expected_target_sha256=binding["target_sha256"])
        self.assertTrue(output.is_file())

    def test_numbering_edit_persists_rule_and_generated_document(self):
        derived = self.root / "numbering.wfstyle"
        manager.derive_style_pack(self.pack, derived, {"styles": [{"style_id": "Heading2", "numbering_format": "upperRoman", "numbering_pattern": "%1-%2", "numbering_start": 4, "numbering_restart": False}]})
        manifest, entries = manager.load_style_pack(derived)
        preview = next(item for item in manifest["used_formats"] if item["style_id"] == "Heading2")
        self.assertEqual(preview["numbering_format"], "upperRoman")
        self.assertEqual(preview["numbering_pattern"], "%1-%2")
        self.assertEqual(preview["numbering_start"], 4)
        self.assertIs(preview["numbering_restart"], False)
        output = self.root / "numbering.docx"
        manager.apply_style_pack(derived, self.target, output)
        package = core.load_package(output, "result")
        self.assertIn(b'upperRoman', package.entries["word/numbering.xml"])
        self.assertIn(b'%1-%2', package.entries["word/numbering.xml"])

    def test_table_borders_and_cell_margins_reach_generated_document(self):
        source = self.root / "tables.wfstyle"
        manager.create_style_pack(PROJECT_DIR / "tests/fixtures/source.docx", source)
        derived = self.root / "table-edited.wfstyle"
        manager.derive_style_pack(source, derived, {"styles": [{"style_id": "LightShading-Accent1", "table_border_style": "double", "table_border_color_hex": "123456", "table_border_width_pt": 1.25, "table_cell_margin_top_pt": 5.5, "table_cell_margin_left_pt": 6}]})
        manifest, entries = manager.load_style_pack(derived)
        preview = next(item for item in manifest["used_formats"] if item["style_id"] == "LightShading-Accent1")
        self.assertEqual(preview["table_border_width_pt"], 1.25)
        self.assertEqual(preview["table_cell_margin_top_pt"], 5.5)
        output = self.root / "tables.docx"
        manager.apply_style_pack(derived, self.target, output)
        styles = core.parse_xml(core.load_package(output, "result").entries["word/styles.xml"], "styles")
        node = styles.xpath("./w:style[@w:styleId='LightShading-Accent1']", namespaces=core.NS)[0]
        self.assertEqual(node.find("w:tblPr/w:tblBorders/w:top", namespaces=core.NS).get(core.qn(core.W_NS, "sz")), "10")
        self.assertEqual(node.find("w:tblPr/w:tblCellMar/w:left", namespaces=core.NS).get(core.qn(core.W_NS, "w")), "120")
        first_row = node.xpath("./w:tblStylePr[@w:type='firstRow']/w:tcPr/w:tcBorders/*", namespaces=core.NS)
        self.assertTrue(first_row, "source.docx must exercise actual firstRow border overrides")
        conditional = node.xpath("./w:tblStylePr//w:tblBorders/* | ./w:tblStylePr//w:tcBorders/*", namespaces=core.NS)
        self.assertTrue(conditional)
        for border in node.xpath(".//w:tblBorders/* | .//w:tcBorders/*", namespaces=core.NS):
            self.assertEqual(border.get(core.qn(core.W_NS, "val")), "double")
            self.assertEqual(border.get(core.qn(core.W_NS, "sz")), "10")
            self.assertEqual(border.get(core.qn(core.W_NS, "color")), "123456")
            for attribute in ("themeColor", "themeTint", "themeShade"):
                self.assertNotIn(core.qn(core.W_NS, attribute), border.attrib)

    def test_table_border_disable_reaches_root_and_conditional_regions(self):
        source = self.root / "disable-source.wfstyle"
        manager.create_style_pack(PROJECT_DIR / "tests/fixtures/source.docx", source)
        for disabled in ("nil", "none"):
            with self.subTest(disabled=disabled):
                derived = self.root / ("disabled-%s.wfstyle" % disabled)
                manager.derive_style_pack(source, derived, {"styles": [{"style_id": "LightShading-Accent1", "table_border_style": disabled}]})
                output = self.root / ("disabled-%s.docx" % disabled)
                manager.apply_style_pack(derived, self.target, output)
                styles = core.parse_xml(core.load_package(output, "result").entries["word/styles.xml"], "styles")
                node = styles.xpath("./w:style[@w:styleId='LightShading-Accent1']", namespaces=core.NS)[0]
                self.assertTrue(node.xpath("./w:tblStylePr[@w:type='firstRow']/w:tcPr/w:tcBorders/*", namespaces=core.NS))
                for border in node.xpath(".//w:tblBorders/* | .//w:tcBorders/*", namespaces=core.NS):
                    self.assertEqual(border.get(core.qn(core.W_NS, "val")), disabled)

    def test_partial_table_border_edits_preserve_omitted_fields_and_shading(self):
        source = self.root / "partial-border-source.wfstyle"
        manager.create_style_pack(PROJECT_DIR / "tests/fixtures/source.docx", source)
        _manifest, source_entries = manager.load_style_pack(source)
        original = core.parse_xml(source_entries["word/styles.xml"], "styles").xpath("./w:style[@w:styleId='LightShading-Accent1']", namespaces=core.NS)[0]
        requests = (({"table_border_style": "double"}, {core.qn(core.W_NS, "val"): "double"}), ({"table_border_width_pt": 1.25}, {core.qn(core.W_NS, "sz"): "10"}), ({"table_border_color_hex": "123456"}, {core.qn(core.W_NS, "color"): "123456"}))
        for index, (fields, changed) in enumerate(requests):
            with self.subTest(fields=fields):
                derived = self.root / ("partial-border-%d.wfstyle" % index)
                manager.derive_style_pack(source, derived, {"styles": [{"style_id": "LightShading-Accent1", **fields}]})
                _manifest, entries = manager.load_style_pack(derived)
                edited = core.parse_xml(entries["word/styles.xml"], "styles").xpath("./w:style[@w:styleId='LightShading-Accent1']", namespaces=core.NS)[0]
                old_borders = original.xpath("./w:tblStylePr//w:tblBorders/* | ./w:tblStylePr//w:tcBorders/*", namespaces=core.NS)
                new_borders = edited.xpath("./w:tblStylePr//w:tblBorders/* | ./w:tblStylePr//w:tcBorders/*", namespaces=core.NS)
                self.assertTrue(old_borders)
                self.assertEqual(len(old_borders), len(new_borders))
                for before, after in zip(old_borders, new_borders):
                    expected = dict(before.attrib)
                    expected.update(changed)
                    if "table_border_color_hex" in fields:
                        for attribute in ("themeColor", "themeTint", "themeShade"):
                            expected.pop(core.qn(core.W_NS, attribute), None)
                    self.assertEqual(dict(after.attrib), expected)
                self.assertEqual([dict(node.attrib) for node in original.xpath(".//w:shd", namespaces=core.NS)], [dict(node.attrib) for node in edited.xpath(".//w:shd", namespaces=core.NS)])

    def test_numbering_and_table_edit_constraints_reject_invalid_requests(self):
        variants = [
            {"style_id": "Heading2", "numbering_pattern": "%1-%3"},
            {"style_id": "Heading2", "numbering_start": True},
            {"style_id": "Heading2", "numbering_format": "arbitrary"},
            {"style_id": "Normal", "numbering_start": 1},
            {"style_id": "Heading1", "numbering_restart": True},
            {"style_id": "LightShading-Accent1", "table_border_width_pt": 1},
        ]
        for index, edit in enumerate(variants):
            with self.subTest(edit=edit), self.assertRaises(core.TransferError):
                manager.derive_style_pack(self.pack, self.root / (str(index) + ".wfstyle"), {"styles": [edit]})

    def test_preflight_import_export_cli_return_real_envelopes(self):
        for args, key in ((["preflight-pack", "--pack", str(self.pack), "--target", str(self.target)], "preflight"), (["export-pack", "--pack", str(self.pack), "--out", str(self.root / "cli.wfstyle")], "pack"), (["import-pack", "--pack", str(self.pack), "--dir", str(self.root / "cli-library")], "pack")):
            with self.subTest(command=args[0]):
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream):
                    code = manager.main(args)
                result = json.loads(stream.getvalue())
                self.assertEqual(code, 0)
                self.assertTrue(result["ok"])
                self.assertIn(key, result)

    def test_real_post_preflight_change_is_rejected_and_inputs_preserved(self):
        _manifest, report = manager.preflight_style_pack(self.pack, self.target)
        binding = report["input_binding"]
        original_pack = self.pack.read_bytes()
        # Extra trailing bytes leave a readable ZIP but change its actual input
        # identity.  The bound preflight must fail before parsing or exporting.
        altered_target = self.target.read_bytes() + b"changed after preflight"
        self.target.write_bytes(altered_target)
        output = self.root / "stale.docx"
        with self.assertRaisesRegex(core.TransferError, "预检后发生变化"):
            manager.apply_style_pack(self.pack, self.target, output, expected_pack_sha256=binding["pack_sha256"], expected_target_sha256=binding["target_sha256"])
        self.assertFalse(output.exists())
        self.assertEqual(self.target.read_bytes(), altered_target)
        self.assertEqual(self.pack.read_bytes(), original_pack)

    def test_aba_input_substitution_is_rejected_for_pack_and_target(self):
        """A restored path cannot authenticate the different bytes parsed."""
        alternate_pack = self.root / "alternate.wfstyle"
        manager.create_style_pack(PROJECT_DIR / "tests/fixtures/source.docx", alternate_pack)
        original_pack, original_target = self.pack.read_bytes(), self.target.read_bytes()
        _manifest, report = manager.preflight_style_pack(self.pack, self.target)
        binding = report["input_binding"]
        for operation in ("preflight", "apply"):
            for input_kind in ("pack", "target"):
                with self.subTest(operation=operation, input_kind=input_kind):
                    observed_path = self.pack if input_kind == "pack" else self.target
                    original = original_pack if input_kind == "pack" else original_target
                    substituted = alternate_pack.read_bytes() if input_kind == "pack" else (PROJECT_DIR / "tests/fixtures/source.docx").read_bytes()
                    self.assertNotEqual(original, substituted)
                    owner = manager if input_kind == "pack" else core
                    method_name = "load_style_pack" if input_kind == "pack" else "load_package"
                    actual_load = getattr(owner, method_name)

                    def load_replaced(path, *args, **kwargs):
                        if Path(path).resolve() != observed_path.resolve():
                            return actual_load(path, *args, **kwargs)
                        observed_path.write_bytes(substituted)
                        try:
                            return actual_load(path, *args, **kwargs)
                        finally:
                            observed_path.write_bytes(original)

                    output = self.root / ("aba-%s-%s.docx" % (operation, input_kind))
                    before = set(self.root.iterdir())
                    with mock.patch.object(owner, method_name, side_effect=load_replaced), self.assertRaisesRegex(core.TransferError, "预检|变化"):
                        if operation == "preflight":
                            manager.preflight_style_pack(self.pack, self.target)
                        else:
                            manager.apply_style_pack(self.pack, self.target, output, expected_pack_sha256=binding["pack_sha256"], expected_target_sha256=binding["target_sha256"])
                    self.assertFalse(output.exists())
                    self.assertEqual(set(self.root.iterdir()), before)
                    self.assertEqual(self.pack.read_bytes(), original_pack)
                    self.assertEqual(self.target.read_bytes(), original_target)

    def test_import_rejects_same_id_with_different_rules_before_writing(self):
        library = self.root / "library"
        original, _changed = manager.import_style_pack(self.pack, library)
        manifest, entries = manager.load_style_pack(self.pack)
        derived = self.root / "edited.wfstyle"
        manager.derive_style_pack(self.pack, derived, {"styles": [{"style_id": "Heading2", "numbering_start": 4}]})
        edited_manifest, edited_entries = manager.load_style_pack(derived)
        edited_manifest["id"] = manifest["id"]
        hostile = self.root / "same-id.wfstyle"
        manager._write_style_pack_archive(hostile, edited_manifest, edited_entries)
        original_bytes = Path(original["pack_path"]).read_bytes()
        with self.assertRaisesRegex(core.TransferError, "ID 冲突"):
            manager.import_style_pack(hostile, library)
        self.assertEqual(len(list(library.glob("*.wfstyle"))), 1)
        self.assertEqual(Path(original["pack_path"]).read_bytes(), original_bytes)

    def test_equal_parts_with_different_page_layout_are_not_deduplicated(self):
        library = self.root / "library"
        manager.import_style_pack(self.pack, library)
        manifest, entries = manager.load_style_pack(self.pack)
        modified = copy.deepcopy(manifest)
        modified["id"] = "page-layout-copy"
        modified["section_layouts"] = []
        other = self.root / "different-layout.wfstyle"
        manager._write_style_pack_archive(other, modified, entries)
        _new, changed = manager.import_style_pack(other, library)
        self.assertTrue(changed)
        self.assertEqual(len(list(library.glob("*.wfstyle"))), 2)

    def test_export_protects_hardlink_source_and_existing_destination(self):
        original = self.pack.read_bytes()
        alias = self.root / "same-file.wfstyle"
        os.link(self.pack, alias)
        with self.assertRaises(core.TransferError):
            manager.export_style_pack(self.pack, alias, force=True)
        destination = self.root / "existing.wfstyle"
        destination.write_bytes(b"must remain unchanged")
        with self.assertRaises(core.TransferError):
            manager.export_style_pack(self.pack, destination)
        self.assertEqual(destination.read_bytes(), b"must remain unchanged")
        self.assertEqual(self.pack.read_bytes(), original)

    def test_preflight_uses_current_target_outline_and_warns_on_h9(self):
        package = core.load_package(self.target, "target")
        root = core.parse_xml(package.entries["word/document.xml"], "document")
        paragraph = root.find("w:body/w:p", namespaces=core.NS)
        properties = paragraph.find("w:pPr", namespaces=core.NS)
        if properties is None:
            properties = etree.Element(core.qn(core.W_NS, "pPr"))
            paragraph.insert(0, properties)
        for node in list(properties):
            if node.tag == core.qn(core.W_NS, "outlineLvl"):
                properties.remove(node)
        outline = etree.SubElement(properties, core.qn(core.W_NS, "outlineLvl"))
        outline.set(core.qn(core.W_NS, "val"), "8")
        package.entries["word/document.xml"] = core.serialize_xml(root)
        core.write_package(package, package.entries, self.target)
        _manifest, report = manager.preflight_style_pack(self.pack, self.target, demote_headings=True)
        self.assertGreaterEqual(report["heading_level_counts"]["9"], 1)
        self.assertTrue(any("标题9" in warning for warning in report["warnings"]))
        self.assertIn(9, report["runtime_inferred_heading_levels"])

    def test_preflight_rejects_demotion_when_source_hierarchy_is_incomplete(self):
        manifest, entries = manager.load_style_pack(self.pack)
        manifest["heading_authorities"] = {"0": "Heading1"}
        manifest["used_formats"] = [item for item in manifest["used_formats"] if item.get("outline_level") in (None, 0)]
        incomplete = self.root / "incomplete.wfstyle"
        manager._write_style_pack_archive(incomplete, manifest, entries)
        before = set(self.root.iterdir())
        with self.assertRaisesRegex(core.TransferError, "不能安全地"):
            manager.preflight_style_pack(incomplete, self.target, demote_headings=True)
        self.assertEqual(set(self.root.iterdir()), before)

    def test_numbering_metadata_and_restart_match_persisted_definition(self):
        derived = self.root / "restart.wfstyle"
        manager.derive_style_pack(self.pack, derived, {"styles": [{"style_id": "Heading2", "numbering_pattern": "第%2节", "numbering_start": 4, "numbering_restart": True}]})
        manifest, _entries = manager.load_style_pack(derived)
        self.assertEqual(manifest["heading_numbering"]["Heading2"]["start"], 4)
        self.assertEqual(manifest["heading_numbering"]["Heading2"]["level_text"], "第%2节")
        preview = next(item for item in manifest["used_formats"] if item["style_id"] == "Heading2")
        self.assertIs(preview["numbering_restart"], True)

    def test_inferred_heading_numbering_choices_survive_apply_and_later_derivation(self):
        requested = {
            "Heading4": {"numbering_format": "upperRoman", "numbering_pattern": "%1-%4", "numbering_start": 4, "numbering_restart": False},
            "Heading5": {"numbering_format": "lowerLetter", "numbering_pattern": "第%5节", "numbering_start": 3, "numbering_restart": True},
        }
        derived = self.root / "edited-inferred.wfstyle"
        manager.derive_style_pack(self.pack, derived, {"styles": [{"style_id": style_id, **fields} for style_id, fields in requested.items()]})
        second = self.root / "edited-inferred-second.wfstyle"
        manager.derive_style_pack(derived, second, {"styles": [{"style_id": "Normal", "size_pt": 12}]})
        # Older derivative archives only recorded the edited field names.
        legacy_manifest, legacy_entries = manager.load_style_pack(derived)
        legacy_manifest.pop("heading_numbering_user_edits")
        legacy = self.root / "edited-inferred-legacy.wfstyle"
        manager._write_style_pack_archive(legacy, legacy_manifest, legacy_entries)

        target = core.load_package(self.target, "target")
        document = core.parse_xml(target.entries["word/document.xml"], "document")
        body = document.find("w:body", namespaces=core.NS)
        for style_id in requested:
            paragraph = etree.Element(core.qn(core.W_NS, "p"))
            properties = etree.SubElement(paragraph, core.qn(core.W_NS, "pPr"))
            style = etree.SubElement(properties, core.qn(core.W_NS, "pStyle"))
            style.set(core.qn(core.W_NS, "val"), style_id)
            run = etree.SubElement(paragraph, core.qn(core.W_NS, "r"))
            text = etree.SubElement(run, core.qn(core.W_NS, "t"))
            text.text = "edited heading " + style_id
            body.insert(max(0, len(body) - 1), paragraph)
        target.entries["word/document.xml"] = core.serialize_xml(document)
        core.write_package(target, target.entries, self.target)

        for pack in (derived, second, legacy):
            with self.subTest(pack=pack.name):
                output = self.root / (pack.stem + ".docx")
                manager.apply_style_pack(pack, self.target, output)
                result = core.load_package(output, "result")
                catalog = core.build_style_catalog(result.entries["word/styles.xml"], result.entries["word/document.xml"])
                rules = core.infer_heading_numbering_rules(result.entries, catalog, requested)
                content = core.parse_xml(result.entries["word/document.xml"], "document")
                for style_id, fields in requested.items():
                    rule = rules[style_id]
                    self.assertEqual(rule.number_format, fields["numbering_format"])
                    self.assertEqual(rule.level_text, fields["numbering_pattern"])
                    self.assertEqual(rule.start, fields["numbering_start"])
                    self.assertIs(manager._numbering_restarts(result.entries, rule), fields["numbering_restart"])
                    paragraph = next(node for node in content.xpath("//w:p", namespaces=core.NS) if "".join(node.xpath(".//w:t/text()", namespaces=core.NS)) == "edited heading " + style_id)
                    self.assertEqual(paragraph.find("w:pPr/w:pStyle", namespaces=core.NS).get(core.qn(core.W_NS, "val")), style_id)
                    self.assertEqual(paragraph.find("w:pPr/w:numPr/w:numId", namespaces=core.NS).get(core.qn(core.W_NS, "val")), rule.num_id)
                    self.assertEqual(paragraph.find("w:pPr/w:numPr/w:ilvl", namespaces=core.NS).get(core.qn(core.W_NS, "val")), str(rule.level))

    def test_unedited_legacy_inferred_heading_still_repairs_label_font(self):
        manifest, entries = manager.load_style_pack(self.pack)
        catalog = core.build_style_catalog(entries["word/styles.xml"], manager._placeholder_document())
        rules = core.heading_numbering_from_manifest(manifest["heading_numbering"], entries, catalog)
        root, abstracts, nums, styles = core._numbering_index(entries)
        rule = rules["Heading4"]
        abstract = core._abstract_for_num(nums[rule.num_id], abstracts, nums, styles)
        level = core._level_node(abstract, rule.level)
        run = level.find("w:rPr", namespaces=core.NS)
        if run is None:
            run = etree.SubElement(level, core.qn(core.W_NS, "rPr"))
        fonts = run.find("w:rFonts", namespaces=core.NS)
        if fonts is None:
            fonts = etree.SubElement(run, core.qn(core.W_NS, "rFonts"))
        fonts.set(core.qn(core.W_NS, "ascii"), "LegacyWrongLabelFont")
        fonts.set(core.qn(core.W_NS, "eastAsia"), "LegacyWrongLabelFont")
        entries["word/numbering.xml"] = core.serialize_xml(root)
        legacy = self.root / "legacy-font.wfstyle"
        manager._write_style_pack_archive(legacy, manifest, entries)
        output = self.root / "legacy-font.docx"
        manager.apply_style_pack(legacy, self.target, output)
        result = core.load_package(output, "result")
        catalog = core.build_style_catalog(result.entries["word/styles.xml"], result.entries["word/document.xml"])
        rule = core.infer_heading_numbering_rules(result.entries, catalog, ["Heading4"])["Heading4"]
        _root, abstracts, nums, styles = core._numbering_index(result.entries)
        abstract = core._abstract_for_num(nums[rule.num_id], abstracts, nums, styles)
        level = core._level_node(abstract, rule.level)
        self.assertNotIn(b"LegacyWrongLabelFont", core.serialize_xml(level))


if __name__ == "__main__":
    unittest.main()
