#!/usr/bin/env python3
import importlib.util
import sys
import zipfile
from pathlib import Path

from lxml import etree


TEST_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TEST_DIR.parent
FIXTURES = TEST_DIR / "fixtures"
OUTPUT = TEST_DIR / "out" / "transferred.docx"
ENGINE = PROJECT_DIR / "word_style_transfer.py"

spec = importlib.util.spec_from_file_location("word_style_transfer", ENGINE)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)

W_NS = module.W_NS
R_NS = module.R_NS
NS = {"w": W_NS, "r": R_NS}


def qn(local):
    return "{%s}%s" % (W_NS, local)


def read_zip(path):
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def xml(entries, name):
    return etree.fromstring(entries[name])


def paragraph_for_text(root, text):
    for paragraph in root.xpath("//w:p", namespaces=NS):
        value = "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))
        if text in value:
            return paragraph
    raise AssertionError("paragraph not found: %s" % text)


def assert_clean_visual_format(entries):
    allowed_run = module.RUN_SEMANTIC_KEEP
    for name, data in entries.items():
        if not module.is_content_part(name):
            continue
        root = etree.fromstring(data)
        for ppr in root.xpath("//w:p/w:pPr", namespaces=NS):
            assert {etree.QName(x).localname for x in ppr}.issubset(
                {"pStyle", "sectPr"}
            ), name
        for rpr in root.xpath("//w:r/w:rPr", namespaces=NS):
            assert {etree.QName(x).localname for x in rpr}.issubset(
                allowed_run
            ), name
        assert not root.xpath("//w:numPr", namespaces=NS), name
        assert not root.xpath("//w:tcPr/w:shd", namespaces=NS), name
        assert not root.xpath("//w:tblPr/w:tblBorders", namespaces=NS), name


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()

    stats = module.transfer(
        FIXTURES / "source.docx",
        FIXTURES / "target.docx",
        OUTPUT,
    )
    source = read_zip(FIXTURES / "source.docx")
    target = read_zip(FIXTURES / "target.docx")
    output = read_zip(OUTPUT)

    assert output["word/styles.xml"] == source["word/styles.xml"]
    for optional in ("word/theme/theme1.xml", "word/fontTable.xml", "word/numbering.xml"):
        if optional in source:
            assert output[optional] == source[optional], optional

    document = xml(output, "word/document.xml")
    text = "".join(document.xpath("//w:t/text()", namespaces=NS))
    assert "目标文档主标题" in text
    assert "目标独有样式段落" in text
    assert "格式源示例" not in text

    heading = paragraph_for_text(document, "目标文档主标题")
    assert heading.find("w:pPr/w:pStyle", NS).get(qn("val")) == "Heading1"

    target_only = paragraph_for_text(document, "目标独有样式段落")
    pstyle = target_only.find("w:pPr/w:pStyle", NS)
    assert pstyle is not None
    assert pstyle.get(qn("val")) == "Normal"

    # Target header/footer content and image media remain target-owned.
    headers = "".join(
        "".join(xml(output, name).xpath("//w:t/text()", namespaces=NS))
        for name in output
        if name.startswith("word/header") and name.endswith(".xml")
    )
    footers = "".join(
        "".join(xml(output, name).xpath("//w:t/text()", namespaces=NS))
        for name in output
        if name.startswith("word/footer") and name.endswith(".xml")
    )
    assert "必须保留的目标页眉内容" in headers
    assert "必须保留的目标页脚内容" in footers
    target_media = {k: v for k, v in target.items() if k.startswith("word/media/")}
    for name, data in target_media.items():
        assert output.get(name) == data, name

    # Page geometry comes from source, while target header/footer relationships stay.
    source_doc = xml(source, "word/document.xml")
    target_doc = xml(target, "word/document.xml")
    source_sect = source_doc.xpath("//w:sectPr", namespaces=NS)[-1]
    target_sect = target_doc.xpath("//w:sectPr", namespaces=NS)[-1]
    output_sect = document.xpath("//w:sectPr", namespaces=NS)[-1]
    for tag in ("pgSz", "pgMar", "cols", "docGrid"):
        source_node = source_sect.find("w:%s" % tag, NS)
        output_node = output_sect.find("w:%s" % tag, NS)
        if source_node is None:
            assert output_node is None
        else:
            assert etree.tostring(output_node) == etree.tostring(source_node)
    for tag in ("headerReference", "footerReference"):
        target_refs = [x.get("{%s}id" % R_NS) for x in target_sect.findall("w:%s" % tag, NS)]
        output_refs = [x.get("{%s}id" % R_NS) for x in output_sect.findall("w:%s" % tag, NS)]
        assert output_refs == target_refs

    # Unknown target table style is replaced by the source's used table style.
    table_styles = document.xpath("//w:tblPr/w:tblStyle/@w:val", namespaces=NS)
    assert table_styles
    assert table_styles[0] == "LightShading-Accent1"

    assert_clean_visual_format(output)
    assert stats.content_parts_cleaned >= 3
    assert stats.paragraph_properties_removed > 0
    assert stats.run_properties_removed > 0
    assert stats.table_properties_removed > 0
    assert stats.source_format_parts_copied >= 4
    print("PASS", OUTPUT)
    print(stats)


if __name__ == "__main__":
    main()
