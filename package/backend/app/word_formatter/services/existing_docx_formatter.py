"""Structure-preserving formatting for uploaded DOCX files."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from lxml import etree

from ..models.stylespec import StyleDef, StyleSpec
from ..utils.ooxml import DocxPackage
from .compiler import CompileOptions, CompilePhase, CompileProgress, CompileResult
from .spec_generator import build_generic_spec, builtin_specs
from .template_generator import _patch_styles_xml
from .validator import validate_docx


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NSMAP = {"w": W_NS}


def _qn(local: str) -> str:
    return f"{{{W_NS}}}{local}"


@dataclass(frozen=True)
class DocumentSignature:
    tables: int
    sections: int
    drawings: int
    paragraphs: int
    text: str


def _signature(root: etree._Element) -> DocumentSignature:
    return DocumentSignature(
        tables=len(root.findall(".//w:tbl", namespaces=NSMAP)),
        sections=len(root.findall(".//w:sectPr", namespaces=NSMAP)),
        drawings=len(root.findall(".//w:drawing", namespaces=NSMAP))
        + len(root.findall(".//w:pict", namespaces=NSMAP)),
        paragraphs=len(root.findall(".//w:p", namespaces=NSMAP)),
        text="".join(root.xpath(".//w:t/text()", namespaces=NSMAP)),
    )


def _paragraph_text(paragraph: etree._Element) -> str:
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=NSMAP)).strip()


def _is_in_table(paragraph: etree._Element) -> bool:
    return bool(paragraph.xpath("ancestor::w:tc", namespaces=NSMAP))


def _is_centered(paragraph: etree._Element) -> bool:
    p_pr = paragraph.find("w:pPr", namespaces=NSMAP)
    if p_pr is None:
        return False
    jc = p_pr.find("w:jc", namespaces=NSMAP)
    return jc is not None and jc.get(_qn("val")) == "center"


def _load_spec(options: CompileOptions) -> StyleSpec:
    if options.custom_spec:
        return options.custom_spec
    specs = builtin_specs()
    if options.spec_name and options.spec_name in specs:
        return specs[options.spec_name]
    return build_generic_spec()


def _style_roles(spec: StyleSpec) -> Dict[str, Optional[str]]:
    styles = spec.styles
    headings = sorted(
        (
            (style.outline_level if style.outline_level is not None else 99, style_id)
            for style_id, style in styles.items()
            if style.is_heading
        ),
        key=lambda item: item[0],
    )

    def first_existing(*candidates: str) -> Optional[str]:
        return next((item for item in candidates if item in styles), None)

    non_headings = [style_id for style_id, style in styles.items() if not style.is_heading]
    return {
        "title": first_existing("TitleCN", "TitleEN", "Title"),
        "body": first_existing("Body", "Normal") or (non_headings[0] if non_headings else None),
        "table": first_existing("TableText", "Body", "Normal"),
        "caption": first_existing("TableTitle", "FigureCaption", "Caption"),
        "h1": first_existing("H1") or (headings[0][1] if headings else None),
        "h2": first_existing("H2") or (headings[1][1] if len(headings) > 1 else None),
        "h3": first_existing("H3") or (headings[2][1] if len(headings) > 2 else None),
    }


_NUMBER_TOKEN = (
    r"[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b"
    r"\u4e5d\u5341\u767e\u96f6\u3007\d]+"
)
_H3_RE = re.compile(r"^\s*\d+\.\d+\.\d+(?:\D|$)")
_H2_RE = re.compile(
    rf"^\s*(?:\d+\.\d+(?:\D|$)|[\(\uff08]{_NUMBER_TOKEN}[\)\uff09])"
)
_H1_RE = re.compile(
    rf"^\s*(?:\u7b2c{_NUMBER_TOKEN}[\u7ae0\u8282]|{_NUMBER_TOKEN}[\u3001\uff0e\.])"
)
_CAPTION_RE = re.compile(r"^\s*[\u56fe\u8868]\s*\d+")


def _classify(text: str, in_table: bool, first_content: bool, centered: bool) -> str:
    if in_table:
        if _H3_RE.match(text):
            return "h3"
        if len(text) <= 80 and _H2_RE.match(text):
            return "h2"
        if len(text) <= 80 and _H1_RE.match(text):
            return "h1"
        return "table"
    if first_content and len(text) <= 120:
        return "title"
    if _CAPTION_RE.match(text) and len(text) <= 120:
        return "caption"
    if len(text) <= 100 and _H3_RE.match(text):
        return "h3"
    if len(text) <= 100 and _H2_RE.match(text):
        return "h2"
    if len(text) <= 100 and _H1_RE.match(text):
        return "h1"
    if centered and len(text) <= 60:
        return "title"
    return "body"


def _ensure_child(parent: etree._Element, local: str, first: bool = False) -> etree._Element:
    child = parent.find(f"w:{local}", namespaces=NSMAP)
    if child is None:
        child = etree.Element(_qn(local))
        if first:
            parent.insert(0, child)
        else:
            parent.append(child)
    return child


def _set_bool(parent: etree._Element, local: str, value: bool) -> None:
    element = _ensure_child(parent, local)
    element.set(_qn("val"), "1" if value else "0")


def _apply_run_style(paragraph: etree._Element, style: StyleDef) -> None:
    for run in paragraph.findall(".//w:r", namespaces=NSMAP):
        if not run.findall(".//w:t", namespaces=NSMAP):
            continue
        r_pr = run.find("w:rPr", namespaces=NSMAP)
        if r_pr is None:
            r_pr = etree.Element(_qn("rPr"))
            run.insert(0, r_pr)

        fonts = _ensure_child(r_pr, "rFonts", first=True)
        fonts.set(_qn("eastAsia"), style.run.font.eastAsia)
        fonts.set(_qn("ascii"), style.run.font.ascii)
        fonts.set(_qn("hAnsi"), style.run.font.hAnsi)

        half_points = str(int(round(style.run.size_pt * 2)))
        _ensure_child(r_pr, "sz").set(_qn("val"), half_points)
        _ensure_child(r_pr, "szCs").set(_qn("val"), half_points)
        _set_bool(r_pr, "b", style.run.bold)
        _set_bool(r_pr, "bCs", style.run.bold)
        _set_bool(r_pr, "i", style.run.italic)
        _set_bool(r_pr, "iCs", style.run.italic)
        underline = _ensure_child(r_pr, "u")
        underline.set(_qn("val"), "single" if style.run.underline else "none")


def _clear_run_overrides(paragraph: etree._Element) -> None:
    override_tags = {"rFonts", "sz", "szCs", "b", "bCs", "i", "iCs", "u"}
    for r_pr in paragraph.findall(".//w:rPr", namespaces=NSMAP):
        for child in list(r_pr):
            if etree.QName(child).localname in override_tags:
                r_pr.remove(child)


def _set_paragraph_style(paragraph: etree._Element, style_id: str) -> None:
    p_pr = paragraph.find("w:pPr", namespaces=NSMAP)
    if p_pr is None:
        p_pr = etree.Element(_qn("pPr"))
        paragraph.insert(0, p_pr)
    p_style = p_pr.find("w:pStyle", namespaces=NSMAP)
    if p_style is None:
        p_style = etree.Element(_qn("pStyle"))
        p_pr.insert(0, p_style)
    p_style.set(_qn("val"), style_id)


def _set_or_remove(parent: etree._Element, local: str, enabled: bool) -> None:
    element = parent.find(f"w:{local}", namespaces=NSMAP)
    if enabled:
        if element is None:
            parent.append(etree.Element(_qn(local)))
    elif element is not None:
        parent.remove(element)


def _apply_paragraph_format(paragraph: etree._Element, style: StyleDef) -> None:
    p_pr = paragraph.find("w:pPr", namespaces=NSMAP)
    if p_pr is None:
        p_pr = etree.Element(_qn("pPr"))
        paragraph.insert(0, p_pr)

    _ensure_child(p_pr, "jc").set(
        _qn("val"),
        {"justify": "both"}.get(style.paragraph.alignment, style.paragraph.alignment),
    )
    spacing = _ensure_child(p_pr, "spacing")
    before = style.paragraph.space_before_pt
    after = style.paragraph.space_after_pt
    if style.paragraph.space_before_lines is not None:
        before = style.paragraph.space_before_lines * style.run.size_pt
    if style.paragraph.space_after_lines is not None:
        after = style.paragraph.space_after_lines * style.run.size_pt
    spacing.set(_qn("before"), str(int(round(before * 20))))
    spacing.set(_qn("after"), str(int(round(after * 20))))
    if style.paragraph.line_spacing_rule == "single":
        spacing.set(_qn("line"), "240")
        spacing.set(_qn("lineRule"), "auto")
    elif style.paragraph.line_spacing_rule == "1.5":
        spacing.set(_qn("line"), "360")
        spacing.set(_qn("lineRule"), "auto")
    elif style.paragraph.line_spacing_rule == "double":
        spacing.set(_qn("line"), "480")
        spacing.set(_qn("lineRule"), "auto")
    else:
        spacing.set(_qn("line"), str(int(round((style.paragraph.line_spacing or style.run.size_pt) * 20))))
        spacing.set(_qn("lineRule"), "exact")

    indent = _ensure_child(p_pr, "ind")
    indent.set(
        _qn("firstLineChars"),
        str(int(round(style.paragraph.first_line_indent_chars * 100))),
    )
    indent.set(
        _qn("hangingChars"),
        str(int(round(style.paragraph.hanging_indent_chars * 100))),
    )
    _set_or_remove(p_pr, "keepNext", style.paragraph.keep_with_next)
    _set_or_remove(p_pr, "keepLines", style.paragraph.keep_lines)
    _set_or_remove(p_pr, "pageBreakBefore", style.paragraph.page_break_before)
    _set_or_remove(p_pr, "widowControl", style.paragraph.widows_control)


def _apply_page_spec(root: etree._Element, spec: StyleSpec) -> None:
    margins = spec.page.margins_mm
    for section in root.findall(".//w:sectPr", namespaces=NSMAP):
        page_size = _ensure_child(section, "pgSz")
        page_size.set(_qn("w"), "11906")
        page_size.set(_qn("h"), "16838")
        page_margins = _ensure_child(section, "pgMar")
        values = {
            "top": margins.top,
            "bottom": margins.bottom,
            "left": margins.left,
            "right": margins.right,
            "gutter": margins.binding,
            "header": spec.page.header_mm,
            "footer": spec.page.footer_mm,
        }
        for name, millimeters in values.items():
            page_margins.set(_qn(name), str(int(round(millimeters / 25.4 * 1440))))


def format_existing_docx(
    source_bytes: bytes,
    options: Optional[CompileOptions] = None,
    progress_callback: Optional[Callable[[CompileProgress], None]] = None,
) -> CompileResult:
    """Apply a formatting spec without rebuilding the uploaded document."""
    options = options or CompileOptions()
    warnings = []

    def notify(phase: CompilePhase, progress: float, message: str, detail: str = None) -> None:
        if progress_callback:
            progress_callback(CompileProgress(phase, progress, message, detail))

    try:
        notify(CompilePhase.PARSE, 0.0, "正在检查上传的 Word 文档...")
        package = DocxPackage.from_bytes(source_bytes)
        document_root = package.read_xml("word/document.xml")
        before = _signature(document_root)
        if not before.text.strip():
            raise ValueError("上传的 Word 文档不包含可读取的文本")

        body_paragraphs = document_root.findall(".//w:body/w:p", namespaces=NSMAP)
        table_paragraphs = document_root.findall(".//w:tbl//w:p", namespaces=NSMAP)
        structured = before.tables > 0 and (
            len(table_paragraphs) >= max(10, len(body_paragraphs)) or before.sections > 1
        )
        notify(
            CompilePhase.PARSE,
            1.0,
            "文档结构检查完成",
            f"tables={before.tables}, sections={before.sections}, drawings={before.drawings}",
        )

        notify(CompilePhase.SPEC, 0.0, "正在加载排版规范...")
        spec = _load_spec(options)
        roles = _style_roles(spec)
        notify(CompilePhase.SPEC, 1.0, "排版规范已加载", spec.meta.get("name", "自定义规范"))

        notify(CompilePhase.TEMPLATE, 0.0, "正在保留原 Word 模板结构...")
        styles_root = package.read_xml("word/styles.xml")
        _patch_styles_xml(styles_root, spec)
        package.write_xml("word/styles.xml", styles_root)
        if not structured:
            _apply_page_spec(document_root, spec)
        notify(CompilePhase.TEMPLATE, 1.0, "原 Word 模板结构已保留")

        notify(CompilePhase.RENDER, 0.0, "正在原文档内应用排版规范...")
        first_content = True
        changed = 0
        for paragraph in document_root.findall(".//w:body//w:p", namespaces=NSMAP):
            text = _paragraph_text(paragraph)
            if not text:
                continue
            in_table = _is_in_table(paragraph)
            if structured and in_table:
                first_content = False
                continue
            centered = _is_centered(paragraph)
            role = _classify(text, in_table, first_content, centered)
            first_content = False
            style_id = roles.get(role) or roles.get("body")
            if not style_id or style_id not in spec.styles:
                continue
            style = spec.styles[style_id]

            if structured:
                should_format = (
                    role in {"h1", "h2", "h3"}
                    or (role == "body" and len(text) >= 40 and not centered)
                )
                if not should_format:
                    continue
                _apply_run_style(paragraph, style)
                _apply_paragraph_format(paragraph, style)
            else:
                _set_paragraph_style(paragraph, style_id)
                _clear_run_overrides(paragraph)
            changed += 1

        package.write_xml("word/document.xml", document_root)
        output = package.to_bytes()
        notify(CompilePhase.RENDER, 1.0, "排版规范已应用", f"已处理 {changed} 个段落")

        notify(CompilePhase.VALIDATE, 0.0, "正在校验文档结构...")
        output_root = DocxPackage.from_bytes(output).read_xml("word/document.xml")
        after = _signature(output_root)
        if after != before:
            raise ValueError(
                "结构保留校验失败：表格、分节、图片、段落或文本发生了变化"
            )

        report = None
        try:
            report = validate_docx(output, spec)
        except Exception as exc:
            warnings.append(f"样式校验已跳过：{exc}")

        if structured:
            warnings.append(
                "检测到模板型 Word，已保留表格、合并单元格、图片、分节、页眉和页脚。"
            )
            if options.include_cover or options.include_toc:
                warnings.append(
                    "为避免破坏上传模板，本次未重新生成封面和目录。"
                )
        notify(CompilePhase.VALIDATE, 1.0, "文档结构校验通过")
        notify(CompilePhase.DONE, 1.0, "Word 排版完成")
        return CompileResult(
            success=True,
            docx_bytes=output,
            spec=spec,
            report=report,
            warnings=warnings,
        )
    except Exception as exc:
        return CompileResult(success=False, error=str(exc), warnings=warnings)
