from __future__ import annotations

import argparse
from pathlib import Path


def convert_inline_markdown(text: str) -> str:
    return text.replace("**", "").replace("`", "").strip()


def rtf_escape(text: str) -> str:
    parts: list[str] = []
    for char in text:
        code = ord(char)
        if char == "\\":
            parts.append("\\\\")
        elif char == "{":
            parts.append("\\{")
        elif char == "}":
            parts.append("\\}")
        elif code > 127:
            signed = code if code <= 32767 else code - 65536
            parts.append(f"\\u{signed}?")
        elif char == "\n":
            parts.append("\\line ")
        else:
            parts.append(char)
    return "".join(parts)


def parse_markdown(lines: list[str]) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    title_applied = False
    subtitle_applied = False

    for raw_line in lines:
        stripped = raw_line.strip()

        if not stripped:
            blocks.append(("blank", ""))
            continue

        if stripped.startswith("# "):
            blocks.append(("title", convert_inline_markdown(stripped[2:])))
            title_applied = True
            continue

        if title_applied and not subtitle_applied and not stripped.startswith("#"):
            blocks.append(("subtitle", convert_inline_markdown(stripped)))
            subtitle_applied = True
            continue

        if stripped.startswith("## "):
            blocks.append(("h1", convert_inline_markdown(stripped[3:])))
            continue

        if stripped.startswith("### "):
            blocks.append(("h2", convert_inline_markdown(stripped[4:])))
            continue

        if stripped.startswith("#### "):
            blocks.append(("h3", convert_inline_markdown(stripped[5:])))
            continue

        if stripped.startswith("- "):
            blocks.append(("bullet", convert_inline_markdown(stripped[2:])))
            continue

        blocks.append(("p", convert_inline_markdown(stripped)))

    return blocks


def block_to_rtf(kind: str, text: str) -> str:
    safe = rtf_escape(text)
    if kind == "blank":
        return "\\par\n"
    if kind == "title":
        return f"\\pard\\qc\\sa220\\b\\f1\\fs32 {safe}\\b0\\f0\\fs22\\par\n"
    if kind == "subtitle":
        return f"\\pard\\qc\\sa240\\i\\cf2 {safe}\\i0\\cf1\\par\n"
    if kind == "h1":
        return f"\\pard\\sa180\\b\\f1\\fs28\\cf3 {safe}\\b0\\f0\\fs22\\cf1\\par\n"
    if kind == "h2":
        return f"\\pard\\sa120\\b\\f1\\fs24\\cf4 {safe}\\b0\\f0\\fs22\\cf1\\par\n"
    if kind == "h3":
        return f"\\pard\\sa80\\b\\fs22\\cf5 {safe}\\b0\\cf1\\par\n"
    if kind == "bullet":
        return f"\\pard\\li720\\fi-360\\sa80 \\'95\\tab {safe}\\par\n"
    return f"\\pard\\sa100 {safe}\\par\n"


def export_markdown_to_rtf(input_path: Path, output_path: Path) -> None:
    blocks = parse_markdown(input_path.read_text(encoding="utf-8").splitlines())
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = (
        "{\\rtf1\\ansi\\ansicpg1252\\deff0\n"
        "{\\fonttbl{\\f0 Aptos;}{\\f1 Aptos Display;}}\n"
        "{\\colortbl;"
        "\\red31\\green42\\blue55;"
        "\\red92\\green107\\blue122;"
        "\\red26\\green54\\blue93;"
        "\\red36\\green59\\blue83;"
        "\\red51\\green78\\blue104;"
        "}\n"
        "\\viewkind4\\uc1\\pard\\cf1\\f0\\fs22\n"
    )
    body = "".join(block_to_rtf(kind, text) for kind, text in blocks)
    output_path.write_text(header + body + "}", encoding="ascii", errors="ignore")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a simple markdown file to RTF.")
    parser.add_argument("--input", required=True, help="Input markdown file")
    parser.add_argument("--output", help="Output rtf file")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve() if args.output else input_path.with_suffix(".rtf")
    export_markdown_to_rtf(input_path, output_path)
    print(f"RTF_CREATED: {output_path}")


if __name__ == "__main__":
    main()
