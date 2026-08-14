from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


def convert_inline_markdown(text: str) -> str:
    return text.replace("**", "").replace("`", "").strip()


def parse_markdown(lines: list[str]) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    title_applied = False
    subtitle_applied = False

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

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


def paragraph_xml(style_id: str, text: str) -> str:
    safe_text = escape(text)
    return (
        f"<w:p>"
        f"<w:pPr><w:pStyle w:val=\"{style_id}\"/></w:pPr>"
        f"<w:r><w:t xml:space=\"preserve\">{safe_text}</w:t></w:r>"
        f"</w:p>"
    )


def build_document_xml(blocks: list[tuple[str, str]]) -> str:
    style_map = {
        "title": "Title",
        "subtitle": "Subtitle",
        "h1": "Heading1",
        "h2": "Heading2",
        "h3": "Heading3",
        "p": "Normal",
        "bullet": "BulletCustom",
    }

    paragraphs: list[str] = []
    for kind, text in blocks:
        if kind == "blank":
            paragraphs.append("<w:p/>")
            continue

        if kind == "bullet":
            text = f"• {text}"

        paragraphs.append(paragraph_xml(style_map[kind], text))

    body = "".join(paragraphs)
    sect = (
        "<w:sectPr>"
        "<w:pgSz w:w=\"11906\" w:h=\"16838\"/>"
        "<w:pgMar w:top=\"1247\" w:right=\"1247\" w:bottom=\"1247\" w:left=\"1247\" "
        "w:header=\"708\" w:footer=\"708\" w:gutter=\"0\"/>"
        "</w:sectPr>"
    )

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        f"<w:body>{body}{sect}</w:body>"
        "</w:document>"
    )


def build_styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Aptos" w:hAnsi="Aptos" w:eastAsia="Aptos" w:cs="Aptos"/>
        <w:sz w:val="22"/>
        <w:szCs w:val="22"/>
        <w:color w:val="1F2A37"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:after="120" w:line="276" w:lineRule="auto"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:uiPriority w:val="10"/>
    <w:qFormat/>
    <w:pPr>
      <w:jc w:val="center"/>
      <w:spacing w:before="120" w:after="220"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Aptos Display" w:hAnsi="Aptos Display"/>
      <w:b/>
      <w:sz w:val="34"/>
      <w:color w:val="162334"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle">
    <w:name w:val="Subtitle"/>
    <w:basedOn w:val="Normal"/>
    <w:uiPriority w:val="11"/>
    <w:qFormat/>
    <w:pPr>
      <w:jc w:val="center"/>
      <w:spacing w:after="240"/>
    </w:pPr>
    <w:rPr>
      <w:i/>
      <w:sz w:val="22"/>
      <w:color w:val="5C6B7A"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:uiPriority w:val="9"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="260" w:after="140"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Aptos Display" w:hAnsi="Aptos Display"/>
      <w:b/>
      <w:sz w:val="28"/>
      <w:color w:val="1A365D"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:uiPriority w:val="9"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="180" w:after="90"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Aptos Display" w:hAnsi="Aptos Display"/>
      <w:b/>
      <w:sz w:val="24"/>
      <w:color w:val="243B53"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:uiPriority w:val="9"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="140" w:after="60"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:sz w:val="22"/>
      <w:color w:val="334E68"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="BulletCustom">
    <w:name w:val="Bullet Custom"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:ind w:left="540" w:hanging="240"/>
      <w:spacing w:after="80"/>
    </w:pPr>
  </w:style>
</w:styles>
"""


def build_content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


def build_root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def build_document_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""


def build_core_xml(title: str) -> str:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    safe_title = escape(title)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcmitype="http://purl.org/dc/dcmitype/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{safe_title}</dc:title>
  <dc:creator>OpenAI Codex</dc:creator>
  <cp:lastModifiedBy>OpenAI Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:modified>
</cp:coreProperties>
"""


def build_app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Office Word</Application>
  <DocSecurity>0</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <Company>OpenAI</Company>
  <LinksUpToDate>false</LinksUpToDate>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>16.0000</AppVersion>
</Properties>
"""


def export_markdown_to_docx(input_path: Path, output_path: Path) -> None:
    lines = input_path.read_text(encoding="utf-8").splitlines()
    blocks = parse_markdown(lines)
    title = next((text for kind, text in blocks if kind == "title"), input_path.stem)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", build_content_types_xml())
        archive.writestr("_rels/.rels", build_root_rels_xml())
        archive.writestr("docProps/core.xml", build_core_xml(title))
        archive.writestr("docProps/app.xml", build_app_xml())
        archive.writestr("word/document.xml", build_document_xml(blocks))
        archive.writestr("word/styles.xml", build_styles_xml())
        archive.writestr("word/_rels/document.xml.rels", build_document_rels_xml())


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a simple markdown document to DOCX.")
    parser.add_argument("--input", required=True, help="Input markdown file")
    parser.add_argument("--output", help="Output docx file")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve() if args.output else input_path.with_suffix(".docx")

    export_markdown_to_docx(input_path, output_path)
    print(f"DOCX_CREATED: {output_path}")


if __name__ == "__main__":
    main()
