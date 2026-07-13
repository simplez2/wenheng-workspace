import io
import json
import tempfile
import unittest
from pathlib import Path

from docx import Document

from app.services.document_roundtrip import (
    build_docx_from_source,
    parse_docx_document,
)


def _fixture_document() -> bytes:
    document = Document()
    document.add_paragraph("正文之前")
    table = document.add_table(rows=2, cols=2)
    merged = table.cell(0, 0).merge(table.cell(0, 1))
    merged.text = "合并单元格中的长段落，需要且只能处理一次。"
    table.cell(1, 0).text = "左下内容"
    table.cell(1, 1).text = "右下内容"
    document.add_paragraph("正文之后")
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


class DocumentRoundtripTests(unittest.TestCase):
    def test_docx_blocks_follow_document_order_and_skip_merged_duplicates(self):
        content = _fixture_document()
        text, manifest, segments = parse_docx_document(content)

        self.assertEqual(
            [block["text"] for block in manifest["blocks"]],
            [
                "正文之前",
                "合并单元格中的长段落，需要且只能处理一次。",
                "左下内容",
                "右下内容",
                "正文之后",
            ],
        )
        self.assertEqual(text.count("合并单元格中的长段落"), 1)
        self.assertEqual(len(segments), 5)

    def test_docx_export_updates_merged_cell_once(self):
        content = _fixture_document()
        _, manifest, segments = parse_docx_document(content)
        optimized = [f"优化：{segment}" for segment in segments]

        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "source.docx"
            source_path.write_bytes(content)
            result = build_docx_from_source(
                str(source_path),
                json.dumps(manifest, ensure_ascii=False),
                optimized,
            )

        document = Document(io.BytesIO(result))
        self.assertEqual(document.paragraphs[0].text, "优化：正文之前")
        self.assertEqual(
            document.tables[0].cell(0, 0).text,
            "优化：合并单元格中的长段落，需要且只能处理一次。",
        )
        self.assertEqual(document.paragraphs[-1].text, "优化：正文之后")


if __name__ == "__main__":
    unittest.main()
