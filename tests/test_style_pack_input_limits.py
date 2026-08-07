#!/usr/bin/env python3
"""Pre-decompression safety checks for persistent .wfstyle files."""

from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
FIXTURES = TEST_DIR / "fixtures"
sys.path.insert(0, str(PROJECT_DIR))

import style_pack_manager as manager  # noqa: E402
import word_style_transfer as core  # noqa: E402


def synthetic_info(
    name: str,
    *,
    file_size: int = 0,
    compress_size: int | None = None,
    flag_bits: int = 0,
    compress_type: int = zipfile.ZIP_DEFLATED,
) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.file_size = file_size
    info.compress_size = file_size if compress_size is None else compress_size
    info.flag_bits = flag_bits
    info.compress_type = compress_type
    return info


def write_pack_with_manifest(
    path: Path, manifest: dict[str, object], entries: dict[str, bytes]
) -> None:
    """Write a checksum-correct pack while bypassing production validation."""
    persisted = copy.deepcopy(manifest)
    persisted.pop("pack_path", None)
    checksums = manager._part_checksums(entries)
    persisted["format_part_count"] = len(entries)
    persisted["part_sha256"] = checksums
    persisted["format_fingerprint"] = manager._format_fingerprint(checksums)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            manager._zip_info("manifest.json"),
            json.dumps(persisted, ensure_ascii=False).encode("utf-8"),
        )
        for name, data in sorted(entries.items()):
            archive.writestr(manager._zip_info(manager.PART_PREFIX + name), data)


class StylePackInputLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory(
            prefix="word-style-pack-input-limits-"
        )
        cls.working_dir = Path(cls._temporary.name)
        cls.normal_pack = cls.working_dir / "normal.wfstyle"
        manager.create_style_pack(
            FIXTURES / "source.docx",
            cls.normal_pack,
            display_name="安全加载测试",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def assert_rejected_before_decompression(
        self, members: list[zipfile.ZipInfo], expected: str
    ) -> None:
        with mock.patch.object(
            zipfile.ZipFile, "infolist", return_value=members
        ), mock.patch.object(
            zipfile.ZipFile,
            "testzip",
            side_effect=AssertionError("testzip must not run"),
        ), mock.patch.object(
            zipfile.ZipFile,
            "read",
            side_effect=AssertionError("read must not run"),
        ):
            with self.assertRaisesRegex(core.TransferError, expected):
                manager.load_style_pack(self.normal_pack)

    def test_oversized_member_is_rejected_before_decompression(self) -> None:
        self.assert_rejected_before_decompression(
            [
                synthetic_info("manifest.json", file_size=100),
                synthetic_info(
                    "parts/word/styles.xml",
                    file_size=manager.MAX_PACK_MEMBER_BYTES + 1,
                    compress_size=manager.MAX_PACK_MEMBER_BYTES + 1,
                ),
            ],
            "条目过大",
        )

    def test_oversized_total_is_rejected_before_decompression(self) -> None:
        members = [synthetic_info("manifest.json", file_size=100)]
        members.extend(
            synthetic_info(
                "parts/word/media-%d.bin" % index,
                file_size=15 * 1024 * 1024,
                compress_size=15 * 1024 * 1024,
            )
            for index in range(5)
        )
        self.assert_rejected_before_decompression(members, "体积异常")

    def test_high_ratio_member_is_rejected_before_decompression(self) -> None:
        self.assert_rejected_before_decompression(
            [
                synthetic_info("manifest.json", file_size=100),
                synthetic_info(
                    "parts/word/styles.xml",
                    file_size=8 * 1024 * 1024,
                    compress_size=1024,
                ),
            ],
            "压缩率异常",
        )

    def test_unsafe_path_is_rejected_before_decompression(self) -> None:
        self.assert_rejected_before_decompression(
            [
                synthetic_info("manifest.json", file_size=100),
                synthetic_info("parts/../outside.xml", file_size=100),
            ],
            "不安全的路径",
        )

    def test_encryption_and_unsupported_compression_are_rejected_early(self) -> None:
        self.assert_rejected_before_decompression(
            [synthetic_info("manifest.json", file_size=100, flag_bits=0x1)],
            "加密条目",
        )
        self.assert_rejected_before_decompression(
            [
                synthetic_info(
                    "manifest.json",
                    file_size=100,
                    compress_type=zipfile.ZIP_BZIP2,
                )
            ],
            "不支持的压缩方式",
        )

    def test_excessive_member_count_is_rejected_early(self) -> None:
        members = [synthetic_info("manifest.json", file_size=100)]
        members.extend(
            synthetic_info("parts/word/part-%03d.xml" % index)
            for index in range(manager.MAX_PACK_MEMBERS)
        )
        self.assert_rejected_before_decompression(members, "过多条目")

    def test_normal_and_legacy_packs_remain_loadable(self) -> None:
        normal_manifest, entries = manager.load_style_pack(self.normal_pack)
        self.assertEqual(normal_manifest["schema_version"], manager.PACK_SCHEMA_VERSION)

        legacy_manifest = copy.deepcopy(normal_manifest)
        for field in (
            "heading_numbering",
            "heading_paragraph_indents",
            "heading_authorities",
            "heading_number_label_shared_fonts",
            "table_style_edit_candidate",
        ):
            legacy_manifest.pop(field, None)
        legacy_pack = self.working_dir / "legacy.wfstyle"
        manager._write_style_pack_archive(
            legacy_pack, legacy_manifest, entries, force=True
        )
        loaded, loaded_entries = manager.load_style_pack(legacy_pack)
        self.assertEqual(loaded["id"], normal_manifest["id"])
        self.assertEqual(loaded_entries, entries)

        no_fingerprint_manifest = copy.deepcopy(normal_manifest)
        no_fingerprint_manifest.pop("format_fingerprint", None)
        no_fingerprint_pack = self.working_dir / "legacy-no-fingerprint.wfstyle"
        write_pack_with_manifest(
            no_fingerprint_pack, no_fingerprint_manifest, entries
        )
        # The helper normally refreshes the fingerprint. Remove it in-place
        # by rewriting only this legacy compatibility case.
        persisted = copy.deepcopy(no_fingerprint_manifest)
        persisted.pop("pack_path", None)
        persisted["format_part_count"] = len(entries)
        persisted["part_sha256"] = manager._part_checksums(entries)
        with zipfile.ZipFile(
            no_fingerprint_pack, "w", zipfile.ZIP_DEFLATED
        ) as archive:
            archive.writestr(
                manager._zip_info("manifest.json"),
                json.dumps(persisted, ensure_ascii=False).encode("utf-8"),
            )
            for name, data in sorted(entries.items()):
                archive.writestr(
                    manager._zip_info(manager.PART_PREFIX + name), data
                )
        manager.load_style_pack(no_fingerprint_pack)

    def test_checksum_correct_malformed_manifests_are_rejected(self) -> None:
        manifest, entries = manager.load_style_pack(self.normal_pack)
        duplicate_formats = copy.deepcopy(manifest["used_formats"])
        duplicate_formats.append(copy.deepcopy(duplicate_formats[0]))
        variants: list[tuple[str, str, object]] = [
            ("id-array", "id", ["not", "text"]),
            ("formats-int", "used_formats", 7),
            ("duplicate-format", "used_formats", duplicate_formats),
            ("tables-int", "used_table_styles", 3),
            ("bool-count", "used_style_count", True),
            ("manual-list", "manual_formatting", []),
            ("summary-string", "document_summary", "bad"),
            ("layout-list", "page_layout", []),
            ("privacy-string", "privacy", "bad"),
            ("candidate-string", "table_style_edit_candidate", "bad"),
        ]
        for label, field, value in variants:
            with self.subTest(label=label):
                malformed = copy.deepcopy(manifest)
                malformed[field] = value
                path = self.working_dir / ("malformed-%s.wfstyle" % label)
                write_pack_with_manifest(path, malformed, entries)
                with self.assertRaises(core.TransferError):
                    manager.load_style_pack(path)

    def test_fingerprint_mismatch_is_rejected(self) -> None:
        manifest, entries = manager.load_style_pack(self.normal_pack)
        path = self.working_dir / "bad-fingerprint.wfstyle"
        write_pack_with_manifest(path, manifest, entries)
        with zipfile.ZipFile(path, "r") as archive:
            archived = {
                name: archive.read(name) for name in archive.namelist()
            }
        persisted = json.loads(archived["manifest.json"].decode("utf-8"))
        persisted["format_fingerprint"] = "0" * 64
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                manager._zip_info("manifest.json"),
                json.dumps(persisted, ensure_ascii=False).encode("utf-8"),
            )
            for name, data in archived.items():
                if name != "manifest.json":
                    archive.writestr(manager._zip_info(name), data)
        with self.assertRaisesRegex(core.TransferError, "格式指纹"):
            manager.load_style_pack(path)

    def test_bad_pack_is_skipped_without_hiding_valid_library_pack(self) -> None:
        manifest, entries = manager.load_style_pack(self.normal_pack)
        library = self.working_dir / "mixed-library"
        library.mkdir()
        valid_path = library / "valid.wfstyle"
        shutil.copy2(self.normal_pack, valid_path)
        malformed = copy.deepcopy(manifest)
        malformed["used_formats"] = 42
        invalid_path = library / "invalid.wfstyle"
        write_pack_with_manifest(invalid_path, malformed, entries)

        with self.assertRaisesRegex(core.TransferError, "used_formats"):
            manager.load_style_pack(invalid_path)
        result = manager.list_library(library)
        self.assertEqual(len(result["packs"]), 1)
        self.assertEqual(
            Path(result["packs"][0]["pack_path"]).resolve(),
            valid_path.resolve(),
        )
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(
            Path(result["errors"][0]["path"]).resolve(),
            invalid_path.resolve(),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
