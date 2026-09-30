#!/usr/bin/env python3
"""
[INPUT]: 依赖 __future__, argparse, importlib, pathlib, re, shutil, subprocess, sys, tempfile
[OUTPUT]: 提供只检查 Git 源码快照的 GEB 同构检查，排除忽略的历史包与生成代码
[POS]: 文档验证层-让已有本机构建归档不进入 L1/L2/L3 的维护范围
[PROTOCOL]: 修改检查范围时同步 PROJECT_INDEX.md 与 FOLDER_INDEX.md
"""
from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def source_paths(root: Path) -> list[str]:
    data = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"])
    return sorted(set(data.decode("utf-8").split("\0")) - {""})


def main() -> int:
    parser = argparse.ArgumentParser(description="验证受版本控制的源码文档快照")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--skill-dir", type=Path, default=Path.home() / ".codex/skills/fugue-docs")
    parser.add_argument("--scaffold", action="store_true", help="首次生成源码文档骨架；语义字段仍须人工核实")
    parser.add_argument("--sync", action="store_true", help="同步官方工具生成的机器字段")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    tools = arguments.skill_dir / "scripts"
    if not (tools / "geb_check.py").is_file():
        parser.error("找不到 fugue-docs 工具，请设置 --skill-dir")
    sys.path.insert(0, str(tools))
    checker = importlib.import_module("geb_check")
    # 协议明确豁免生成文件；仍复制它们以保持索引路径和语义边完整。
    checker.EXCLUDED_DIRS.add("Generated")
    checker.CODE_EXTENSIONS.add(".ps1")
    # 官方工具在导入时编译引用正则；扩展扫描后同步引用口径。
    checker._FILE_REF_PATTERN = re.compile(
        r"(?:[\w][\w.\-]*/)*[\w][\w.\-]*\.(?:%s)(?!\w)"
        % "|".join(re.escape(extension.lstrip(".")) for extension in sorted(checker.CODE_EXTENSIONS))
    )
    with tempfile.TemporaryDirectory(prefix="forma-geb-source-") as temporary:
        snapshot = Path(temporary)
        for relative in source_paths(root):
            original = root / relative
            if not original.is_file():
                continue
            if original.is_symlink() or not original.resolve().is_relative_to(root):
                raise ValueError("源码快照不接受链接：%s" % relative)
            copied = snapshot / relative
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, copied)
        if arguments.scaffold or arguments.sync:
            module = importlib.import_module("geb_scaffold" if arguments.scaffold else "geb_sync")
            previous = sys.argv
            try:
                sys.argv = [str(tools / (module.__name__ + ".py")), str(snapshot)]
                module.main()
            finally:
                sys.argv = previous
            # 官方同步/脚手架只产生文档与机器字段；这里是机械回写，不改业务实现。
            for copied in snapshot.rglob("*"):
                if copied.is_file():
                    destination = root / copied.relative_to(snapshot)
                    if not destination.is_file() or destination.read_bytes() != copied.read_bytes():
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(copied, destination)
        violations, statistics = checker.run_checks(str(snapshot), strict=True, complete=True)
        for violation in violations:
            print("%s %s: %s" % (violation["level"], violation["path"], violation["problem"]))
        print("源码快照：%d 个代码文件，%d 个代码目录，%d 项违规" % (statistics["code_files"], statistics["code_dirs"], len(violations)))
        if not violations:
            print("GEB 回环：L3 ✓ | L2 ✓ | L1 ✓（源码范围；生成文件与忽略的构建归档豁免）")
        return bool(violations)


if __name__ == "__main__":
    raise SystemExit(main())
