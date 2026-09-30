#!/usr/bin/env python3
# [INPUT]: 依赖 __future__, sys, tempfile, unittest, zipfile, pathlib, word_style_transfer
# [OUTPUT]: 提供 TEST_DIR, PROJECT_DIR, FIXTURES, synthetic_info(), PackageResourceLimitTests
# [POS]: 验证 Word ZIP 成员、体积及压缩资源边界
# [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
"""Security limits for loading DOCX/OOXML ZIP packages."""

from __future__ import annotations

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

import word_style_transfer as core  # noqa: E402


def synthetic_info(
    name: str,
    *,
    file_size: int = 0,
    compress_size: int | None = None,
    flag_bits: int = 0,
) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.file_size = file_size
    info.compress_size = file_size if compress_size is None else compress_size
    info.flag_bits = flag_bits
    return info


class PackageResourceLimitTests(unittest.TestCase):
    def test_normal_fixture_still_loads(self) -> None:
        package = core.load_package(FIXTURES / "target.docx", "正常文档")
        self.assertIn("word/document.xml", package.entries)
        self.assertIn("word/styles.xml", package.entries)

    def test_rejects_too_many_members_from_metadata(self) -> None:
        members = [
            synthetic_info("word/media/image-%05d.png" % index)
            for index in range(core.MAX_PACKAGE_MEMBERS + 1)
        ]
        with self.assertRaisesRegex(core.TransferError, "过多压缩条目"):
            core.validate_package_members(members, "测试文档")

    def test_rejects_oversized_single_member_without_allocating_it(self) -> None:
        member = synthetic_info(
            "word/media/large-video.bin",
            file_size=core.MAX_PACKAGE_MEMBER_BYTES + 1,
            compress_size=core.MAX_PACKAGE_MEMBER_BYTES + 1,
        )
        with self.assertRaisesRegex(core.TransferError, "单个文件过大"):
            core.validate_package_members([member], "测试文档")

    def test_rejects_oversized_xml_member(self) -> None:
        member = synthetic_info(
            "word/document.xml",
            file_size=core.MAX_PACKAGE_XML_BYTES + 1,
            compress_size=core.MAX_PACKAGE_XML_BYTES + 1,
        )
        with self.assertRaisesRegex(core.TransferError, "XML 部件过大"):
            core.validate_package_members([member], "测试文档")

    def test_rejects_oversized_total_without_allocating_it(self) -> None:
        members = [
            synthetic_info(
                "word/media/large-%d.bin" % index,
                file_size=400 * 1024 * 1024,
                compress_size=400 * 1024 * 1024,
            )
            for index in range(3)
        ]
        with self.assertRaisesRegex(core.TransferError, "总大小过大"):
            core.validate_package_members(members, "测试文档")

    def test_rejects_extreme_compression_ratio(self) -> None:
        member = synthetic_info(
            "word/media/suspicious.bin",
            file_size=8 * 1024 * 1024,
            compress_size=1024,
        )
        with self.assertRaisesRegex(core.TransferError, "压缩率异常"):
            core.validate_package_members([member], "测试文档")

    def test_rejects_encrypted_member(self) -> None:
        member = synthetic_info(
            "word/document.xml", file_size=100, compress_size=80, flag_bits=0x1
        )
        with self.assertRaisesRegex(core.TransferError, "加密条目"):
            core.validate_package_members([member], "测试文档")

    def test_rejects_unsafe_path_before_testzip_or_read(self) -> None:
        with tempfile.TemporaryDirectory(prefix="word-package-limits-") as raw:
            path = Path(raw) / "unsafe.docx"
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("../outside.xml", b"<root/>")

            with mock.patch.object(
                zipfile.ZipFile,
                "testzip",
                side_effect=AssertionError("testzip must not run"),
            ), mock.patch.object(
                zipfile.ZipFile,
                "read",
                side_effect=AssertionError("read must not run"),
            ):
                with self.assertRaisesRegex(core.TransferError, "不安全的路径"):
                    core.load_package(path, "测试文档")

    def test_rejects_duplicate_member_names(self) -> None:
        members = [
            synthetic_info("word/document.xml"),
            synthetic_info("word/document.xml"),
        ]
        with self.assertRaisesRegex(core.TransferError, "重复条目"):
            core.validate_package_members(members, "测试文档")

    def test_allows_explicit_empty_directories_and_large_media(self) -> None:
        directory = synthetic_info("word/media/")
        directory.external_attr = 0o40775 << 16
        large_media = synthetic_info(
            "word/media/large-image.tiff",
            file_size=256 * 1024 * 1024,
            compress_size=250 * 1024 * 1024,
        )
        core.validate_package_members([directory, large_media], "测试文档")


if __name__ == "__main__":
    unittest.main(verbosity=2)
