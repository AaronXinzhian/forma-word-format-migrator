#!/usr/bin/env python3
# [INPUT]: 依赖 __future__, argparse, json, re, sys, pathlib
# [OUTPUT]: 提供 REPO_ROOT, SOURCE, SWIFT_OUTPUT, CSHARP_OUTPUT, PLACEHOLDER, PLATFORM_KEYS, BANNER, GeneratorError, load_catalog(), is_platform_variant(), resolve(), placeholders(), validate(), split_template(), literal(), expression(), pascal(), camel(), render_swift(), render_csharp(), main()
# [POS]: 从共享文案源生成两平台类型安全常量
# [PROTOCOL]: 变更时更新此头部,然后检查上级 FOLDER_INDEX.md
"""从 shared/ui-strings.json 生成两端的界面文案常量。

    python3 scripts/gen_ui_strings.py            # 写入生成物
    python3 scripts/gen_ui_strings.py --check    # 只校验生成物是否与 JSON 同步

选代码生成而不是运行时读 JSON，是为了让写错的 key 在编译期就报错，
而不是变成线上界面里的一块空白。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "shared" / "ui-strings.json"
SWIFT_OUTPUT = REPO_ROOT / "swift-app" / "Generated" / "UIStrings.swift"
CSHARP_OUTPUT = (
    REPO_ROOT / "windows-app" / "FormaFushi.Windows" / "Generated" / "UIStrings.g.cs"
)

PLACEHOLDER = re.compile(r"\{([A-Za-z][A-Za-z0-9]*)\}")
PLATFORM_KEYS = {"mac", "windows"}

BANNER = (
    "// 本文件由 scripts/gen_ui_strings.py 从 shared/ui-strings.json 生成，请勿手工编辑。\n"
    "// 改文案请改 shared/ui-strings.json，然后重新运行生成器。\n"
)


class GeneratorError(Exception):
    pass


# ---------------------------------------------------------------- 读取与校验


def load_catalog() -> dict:
    try:
        raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise GeneratorError(f"找不到文案来源：{SOURCE}") from error
    except json.JSONDecodeError as error:
        raise GeneratorError(f"{SOURCE} 不是合法 JSON：{error}") from error
    if not isinstance(raw, dict):
        raise GeneratorError("文案来源的顶层必须是对象。")
    return raw


def is_platform_variant(value: object) -> bool:
    return isinstance(value, dict) and set(value) == PLATFORM_KEYS


def resolve(value: object, platform: str, path: str) -> str:
    if isinstance(value, str):
        return value
    if is_platform_variant(value):
        return value[platform]
    raise GeneratorError(
        f"{path} 既不是字符串也不是 {{\"mac\": …, \"windows\": …}} 平台变体。"
    )


def placeholders(template: str) -> list[str]:
    seen: list[str] = []
    for name in PLACEHOLDER.findall(template):
        if name not in seen:
            seen.append(name)
    return seen


def validate(catalog: dict) -> None:
    """平台变体的占位符必须一致，否则两端调用点会长得不一样。"""
    problems: list[str] = []

    def walk(node: dict, prefix: str) -> None:
        for key, value in node.items():
            if key.startswith("_"):
                continue
            path = f"{prefix}{key}"
            if is_platform_variant(value):
                mac, windows = placeholders(value["mac"]), placeholders(value["windows"])
                if mac != windows:
                    problems.append(
                        f"{path}：mac 占位符 {mac} 与 windows 占位符 {windows} 不一致。"
                    )
            elif isinstance(value, dict):
                walk(value, f"{path}.")
            elif not isinstance(value, str):
                problems.append(f"{path}：只允许字符串、平台变体或分组对象。")

    walk(catalog, "")
    if problems:
        raise GeneratorError("文案来源存在问题：\n  " + "\n  ".join(problems))


# ---------------------------------------------------------------- 字面量拼装


def split_template(template: str) -> list[tuple[str, str]]:
    """把模板拆成 ("text", 字面量) / ("arg", 占位符名) 的片段序列。"""
    parts: list[tuple[str, str]] = []
    cursor = 0
    for match in PLACEHOLDER.finditer(template):
        if match.start() > cursor:
            parts.append(("text", template[cursor : match.start()]))
        parts.append(("arg", match.group(1)))
        cursor = match.end()
    if cursor < len(template):
        parts.append(("text", template[cursor:]))
    return parts


def literal(text: str) -> str:
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def expression(template: str, arg_name) -> str:
    parts = split_template(template)
    if not parts:
        return '""'
    rendered = [
        literal(text) if kind == "text" else arg_name(text) for kind, text in parts
    ]
    return " + ".join(rendered)


def pascal(name: str) -> str:
    return name[:1].upper() + name[1:]


def camel(name: str) -> str:
    return name[:1].lower() + name[1:]


# ---------------------------------------------------------------- Swift


def render_swift(catalog: dict) -> str:
    lines = [BANNER, "import Foundation", "", "enum UIStrings {"]

    def emit(node: dict, indent: int) -> None:
        pad = "    " * indent
        for key, value in node.items():
            if key.startswith("_"):
                continue
            if isinstance(value, dict) and not is_platform_variant(value):
                lines.append(f"{pad}enum {pascal(key)} {{")
                emit(value, indent + 1)
                lines.append(f"{pad}}}")
                lines.append("")
                continue

            template = resolve(value, "mac", key)
            names = placeholders(template)
            body = expression(template, camel)
            if not names:
                lines.append(f"{pad}static let {camel(key)} = {body}")
            else:
                signature = ", ".join(f"{camel(name)}: String" for name in names)
                lines.append(f"{pad}static func {camel(key)}({signature}) -> String {{")
                lines.append(f"{pad}    {body}")
                lines.append(f"{pad}}}")

    emit(catalog, 1)
    while lines and lines[-1] == "":
        lines.pop()
    lines.append("}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- C#


def render_csharp(catalog: dict) -> str:
    lines = [
        BANNER,
        "namespace FormaFushi.Windows.Generated;",
        "",
        "internal static class UIStrings",
        "{",
    ]

    def emit(node: dict, indent: int) -> None:
        pad = "    " * indent
        for key, value in node.items():
            if key.startswith("_"):
                continue
            if isinstance(value, dict) and not is_platform_variant(value):
                lines.append(f"{pad}internal static class {pascal(key)}")
                lines.append(f"{pad}{{")
                emit(value, indent + 1)
                lines.append(f"{pad}}}")
                lines.append("")
                continue

            template = resolve(value, "windows", key)
            names = placeholders(template)
            body = expression(template, camel)
            if not names:
                lines.append(f"{pad}public const string {pascal(key)} = {body};")
            else:
                signature = ", ".join(f"string {camel(name)}" for name in names)
                lines.append(
                    f"{pad}public static string {pascal(key)}({signature}) => {body};"
                )

    emit(catalog, 1)
    while lines and lines[-1] == "":
        lines.pop()
    lines.append("}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- 入口


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="只比对生成物，不写入；有差异时以非零码退出。",
    )
    args = parser.parse_args()

    try:
        catalog = load_catalog()
        validate(catalog)
        outputs = {
            SWIFT_OUTPUT: render_swift(catalog),
            CSHARP_OUTPUT: render_csharp(catalog),
        }
    except GeneratorError as error:
        print(f"生成失败：{error}", file=sys.stderr)
        return 2

    stale: list[Path] = []
    for path, content in outputs.items():
        if args.check:
            current = path.read_text(encoding="utf-8") if path.exists() else None
            if current != content:
                stale.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
            print(f"已更新 {path.relative_to(REPO_ROOT)}")

    if stale:
        print("以下生成物与 shared/ui-strings.json 不同步：", file=sys.stderr)
        for path in stale:
            print(f"  {path.relative_to(REPO_ROOT)}", file=sys.stderr)
        print("请运行 python3 scripts/gen_ui_strings.py 后提交。", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
