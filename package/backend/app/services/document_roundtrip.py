import io
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import fitz
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.config import get_exe_dir
from app.services.ai_service import split_text_into_segments


SUPPORTED_SOURCE_FORMATS = {"txt", "md", "docx", "pdf"}


def source_document_path(session_id: str, source_format: str) -> str:
    directory = os.path.join(get_exe_dir(), "source_documents")
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, f"{session_id}.{source_format}")


def _build_segment_manifest(blocks: List[Dict[str, Any]]) -> Tuple[List[str], List[int]]:
    segments: List[str] = []
    segment_blocks: List[int] = []
    for block_index, block in enumerate(blocks):
        for segment in split_text_into_segments(block["text"]):
            segments.append(segment)
            segment_blocks.append(block_index)
    return segments, segment_blocks


def parse_text_document(content: bytes, source_format: str) -> Tuple[str, Dict[str, Any], List[str]]:
    text = content.decode("utf-8-sig", errors="replace")
    blocks = [{"text": line.strip()} for line in text.splitlines() if line.strip()]
    segments, segment_blocks = _build_segment_manifest(blocks)
    return text, {"format": source_format, "blocks": blocks, "segment_blocks": segment_blocks}, segments


def parse_docx_document(content: bytes) -> Tuple[str, Dict[str, Any], List[str]]:
    document = Document(io.BytesIO(content))
    blocks: List[Dict[str, Any]] = []

    paragraph_indexes = {
        paragraph._p: paragraph_index
        for paragraph_index, paragraph in enumerate(document.paragraphs)
    }
    table_indexes = {
        table._tbl: table_index
        for table_index, table in enumerate(document.tables)
    }

    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            text = item.text.strip()
            if text:
                blocks.append({
                    "text": text,
                    "locator": {
                        "kind": "body",
                        "paragraph": paragraph_indexes[item._p],
                    },
                })
            continue

        if not isinstance(item, Table):
            continue

        table_index = table_indexes[item._tbl]
        seen_cells = set()
        for row_index, row in enumerate(item.rows):
            for cell_index, cell in enumerate(row.cells):
                # python-docx returns the same underlying cell once for every
                # grid position covered by a merge. Process that cell only at
                # its first visual position or its text is duplicated and the
                # export is overwritten repeatedly.
                if cell._tc in seen_cells:
                    continue
                seen_cells.add(cell._tc)

                for paragraph_index, paragraph in enumerate(cell.paragraphs):
                    text = paragraph.text.strip()
                    if text:
                        blocks.append({
                            "text": text,
                            "locator": {
                                "kind": "table",
                                "table": table_index,
                                "row": row_index,
                                "cell": cell_index,
                                "paragraph": paragraph_index,
                            },
                        })

    segments, segment_blocks = _build_segment_manifest(blocks)
    text = "\n\n".join(block["text"] for block in blocks)
    return text, {"format": "docx", "blocks": blocks, "segment_blocks": segment_blocks}, segments


def parse_pdf_document(content: bytes) -> Tuple[str, Dict[str, Any], List[str]]:
    document = fitz.open(stream=content, filetype="pdf")
    if document.page_count > 100:
        raise ValueError("PDF 页数不能超过 100 页")

    blocks: List[Dict[str, Any]] = []
    for page_index, page in enumerate(document):
        page_data = page.get_text("dict")
        for block in page_data.get("blocks", []):
            if block.get("type") != 0:
                continue
            lines = block.get("lines", [])
            spans = [span for line in lines for span in line.get("spans", []) if span.get("text", "").strip()]
            text = "\n".join(
                "".join(span.get("text", "") for span in line.get("spans", [])).strip()
                for line in lines
            ).strip()
            if not text or not spans:
                continue
            first_span = spans[0]
            blocks.append({
                "text": text,
                "locator": {
                    "page": page_index,
                    "bbox": [float(value) for value in block["bbox"]],
                    "font_size": float(first_span.get("size", 11)),
                    "color": int(first_span.get("color", 0)),
                },
            })
    document.close()
    segments, segment_blocks = _build_segment_manifest(blocks)
    text = "\n\n".join(block["text"] for block in blocks)
    return text, {"format": "pdf", "blocks": blocks, "segment_blocks": segment_blocks}, segments


def parse_source_document(content: bytes, source_format: str):
    if source_format in {"txt", "md"}:
        return parse_text_document(content, source_format)
    if source_format == "docx":
        return parse_docx_document(content)
    if source_format == "pdf":
        return parse_pdf_document(content)
    raise ValueError("不支持的文件格式")


def _group_optimized_blocks(manifest: Dict[str, Any], optimized_segments: List[str]) -> List[str]:
    block_count = len(manifest.get("blocks", []))
    grouped: List[List[str]] = [[] for _ in range(block_count)]
    for segment_index, block_index in enumerate(manifest.get("segment_blocks", [])):
        if segment_index < len(optimized_segments) and 0 <= block_index < block_count:
            grouped[block_index].append(optimized_segments[segment_index])
    return [
        "".join(parts) if parts else manifest["blocks"][index]["text"]
        for index, parts in enumerate(grouped)
    ]


def _get_docx_paragraph(document: Document, locator: Dict[str, Any]):
    if locator["kind"] == "body":
        return document.paragraphs[locator["paragraph"]]
    return document.tables[locator["table"]].rows[locator["row"]].cells[locator["cell"]].paragraphs[locator["paragraph"]]


def _replace_runs_preserving_style(paragraph, text: str):
    runs = list(paragraph.runs)
    if not runs:
        paragraph.add_run(text)
        return
    original_lengths = [max(len(run.text), 1) for run in runs]
    total = sum(original_lengths)
    cursor = 0
    for index, run in enumerate(runs):
        end = len(text) if index == len(runs) - 1 else round(len(text) * sum(original_lengths[:index + 1]) / total)
        run.text = text[cursor:end]
        cursor = end


def build_docx_from_source(source_path: str, manifest_json: str, optimized_segments: List[str]) -> bytes:
    manifest = json.loads(manifest_json)
    document = Document(source_path)
    optimized_blocks = _group_optimized_blocks(manifest, optimized_segments)
    for block, text in zip(manifest["blocks"], optimized_blocks):
        paragraph = _get_docx_paragraph(document, block["locator"])
        _replace_runs_preserving_style(paragraph, text)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def _pdf_color(value: int) -> Tuple[float, float, float]:
    return (
        ((value >> 16) & 255) / 255,
        ((value >> 8) & 255) / 255,
        (value & 255) / 255,
    )


def build_pdf_from_source(source_path: str, manifest_json: str, optimized_segments: List[str]) -> bytes:
    manifest = json.loads(manifest_json)
    optimized_blocks = _group_optimized_blocks(manifest, optimized_segments)
    document = fitz.open(source_path)
    font_path = next((
        path for path in (
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "C:/Windows/Fonts/simhei.ttf",
        )
        if os.path.exists(path)
    ), None)
    if not font_path:
        raise RuntimeError("服务器缺少可用于 PDF 回写的中文字体")

    page_blocks: Dict[int, List[Tuple[Dict[str, Any], str]]] = {}
    for block, text in zip(manifest["blocks"], optimized_blocks):
        locator = block["locator"]
        page_blocks.setdefault(locator["page"], []).append((locator, text))

    for page_index, items in page_blocks.items():
        page = document[page_index]
        for locator, _ in items:
            page.add_redact_annot(fitz.Rect(locator["bbox"]), fill=(1, 1, 1))
        page.apply_redactions(
            images=fitz.PDF_REDACT_IMAGE_NONE,
            graphics=fitz.PDF_REDACT_LINE_ART_NONE,
        )
        page.insert_font(fontname="WenHengCJK", fontfile=font_path)
        for locator, text in items:
            rect = fitz.Rect(locator["bbox"])
            font_size = min(max(locator.get("font_size", 11), 6), 24)
            while font_size >= 6:
                remaining = page.insert_textbox(
                    rect,
                    text,
                    fontname="WenHengCJK",
                    fontsize=font_size,
                    color=_pdf_color(locator.get("color", 0)),
                    lineheight=1.15,
                )
                if remaining >= 0:
                    break
                font_size -= 0.5
            if font_size < 6:
                page.insert_textbox(rect, text, fontname="WenHengCJK", fontsize=6, color=(0, 0, 0))

    output = document.tobytes(garbage=4, deflate=True)
    document.close()
    return output


def delete_source_document(session_id: str, source_format: str):
    if not source_format:
        return
    path = Path(source_document_path(session_id, source_format))
    if path.exists():
        path.unlink()
