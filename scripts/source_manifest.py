#!/usr/bin/env python3
"""
[INPUT]: 依赖 __future__, argparse, datetime, hashlib, json, pathlib, plistlib, subprocess, xml.etree.ElementTree
[OUTPUT]: 提供绑定源码树摘要、版本、Git 提交和构建环境的 source-manifest.json，拒绝未解决合并
[POS]: 构建层-跨平台产物来源记录与构建首尾一致性输入，不写入本机路径或源码正文
[PROTOCOL]: 修改时更新此头部与 FOLDER_INDEX.md
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import xml.etree.ElementTree as ET


def git(root: Path, *arguments: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *arguments])


def source_manifest(root: Path, platform: str, toolchain: str, sdk: str, channel: str) -> dict:
    root = root.resolve()
    if git(root, "ls-files", "--unmerged", "-z"):
        raise ValueError("构建输入仍有未解决的 Git 合并冲突。")
    commit = git(root, "rev-parse", "HEAD").decode().strip()
    paths = sorted(set(git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").decode("utf-8").split("\0")) - {""})
    hashes = {}
    for relative in paths:
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("构建输入不能是链接或位于仓库外：%s" % relative)
        if not path.is_file():
            continue
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    if git(root, "rev-parse", "HEAD").decode().strip() != commit:
        raise ValueError("生成来源记录期间 Git 提交发生变化。")
    canonical_hashes = json.dumps(hashes, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with (root / "swift-app/Info.plist").open("rb") as stream:
        mac_version = plistlib.load(stream)["CFBundleShortVersionString"]
    windows = ET.parse(root / "windows-app/FormaFushi.Windows/FormaFushi.Windows.csproj")
    return {
        "schema": "forma.build.v1",
        "product": "Forma 赋式",
        "platform": platform,
        "versions": {"macOS": mac_version, "Windows": windows.findtext(".//Version")},
        "source_commit": commit,
        "source_dirty": bool(git(root, "status", "--porcelain").strip()),
        "source_sha256": hashes,
        "source_tree_sha256": hashlib.sha256(canonical_hashes).hexdigest(),
        "toolchain": toolchain,
        "sdk": sdk,
        "channel": channel,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="记录实际构建输入与工具链")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--toolchain", required=True)
    parser.add_argument("--sdk", default="")
    parser.add_argument("--channel", required=True)
    arguments = parser.parse_args()
    result = source_manifest(arguments.root.resolve(), arguments.platform, arguments.toolchain, arguments.sdk, arguments.channel)
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
