import json
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models.models import OptimizationSegment, OptimizationSession, User
from app.routes import optimization as optimization_routes
from app.routes.optimization import _build_session_export, _create_file_session
from app.services.document_roundtrip import parse_text_document


class BatchOptimizationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        database_path = Path(self.directory.name) / "test.db"
        self.engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.user = User(
            card_key="TEST-CARD",
            access_link="/access/TEST-CARD",
            usage_limit=100,
            usage_count=0,
            task_concurrency_limit=2,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        app = FastAPI()
        app.include_router(optimization_routes.router, prefix="/api")

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()
        self.directory.cleanup()

    def test_file_session_records_batch_and_format_preservation(self):
        content = "第一行\r\n第二行\r\n".encode("utf-8")
        original_text, manifest, segments = parse_text_document(content, "txt")
        prepared = {
            "filename": "sample.txt",
            "source_format": "txt",
            "content": content,
            "original_text": original_text,
            "manifest": manifest,
            "segments": segments,
        }
        source_path = Path(self.directory.name) / "source.txt"
        with patch("app.routes.optimization.source_document_path", return_value=str(source_path)):
            session, written_path = _create_file_session(
                self.db,
                self.user,
                prepared,
                "paper_polish",
                batch_id="batch-1",
                batch_index=3,
            )
            self.db.commit()

        self.assertEqual(written_path, str(source_path))
        self.assertTrue(source_path.exists())
        self.assertTrue(session.preserve_format)
        self.assertEqual(session.batch_id, "batch-1")
        self.assertEqual(session.batch_index, 3)
        self.assertEqual(
            self.db.query(OptimizationSegment).filter_by(session_id=session.id).count(),
            2,
        )

    def test_source_file_export_is_forced_to_original_format(self):
        content = b"\xef\xbb\xbf" + "  原文  \r\n".encode("utf-8")
        _, manifest, _ = parse_text_document(content, "txt")
        session = OptimizationSession(
            user_id=self.user.id,
            session_id="session-1",
            original_text="原文",
            source_format="txt",
            source_filename="source.txt",
            source_manifest=json.dumps(manifest, ensure_ascii=False),
            preserve_format=True,
            processing_mode="paper_polish",
            current_stage="polish",
            status="completed",
        )
        self.db.add(session)
        self.db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="polish",
            original_text="原文",
            polished_text="润色文本",
            status="completed",
        )
        self.db.add(segment)
        self.db.commit()
        source_path = Path(self.directory.name) / "session-1.txt"
        source_path.write_bytes(content)

        with patch("app.routes.optimization.source_document_path", return_value=str(source_path)):
            exported, media_type, filename = _build_session_export(session, [segment], "txt")
            self.assertEqual(exported, b"\xef\xbb\xbf" + "  润色文本  \r\n".encode("utf-8"))
            self.assertEqual(media_type, "text/plain")
            self.assertEqual(filename, "source_优化.txt")
            with self.assertRaises(HTTPException):
                _build_session_export(session, [segment], "docx")

    def test_batch_upload_route_accepts_valid_files_and_reports_rejections(self):
        source_directory = Path(self.directory.name) / "sources"
        source_directory.mkdir()

        def source_path(session_id, source_format):
            return str(source_directory / f"{session_id}.{source_format}")

        with (
            patch("app.routes.optimization.source_document_path", side_effect=source_path),
            patch(
                "app.routes.optimization.run_batch_optimizations",
                new_callable=AsyncMock,
            ) as run_batch,
            patch.object(
                optimization_routes.concurrency_manager,
                "get_status",
                new=AsyncMock(return_value={"max_users": 5, "current_users": 5}),
            ),
        ):
            response = self.client.post(
                "/api/optimization/start-files",
                headers={"X-Card-Key": self.user.card_key},
                data={"processing_mode": "paper_polish"},
                files=[
                    ("files", ("one.txt", "第一份有效文件".encode("utf-8"), "text/plain")),
                    ("files", ("two.md", "# 第二份有效文件".encode("utf-8"), "text/markdown")),
                    ("files", ("blocked.exe", b"not allowed", "application/octet-stream")),
                ],
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["total_files"], 3)
        self.assertEqual(len(payload["accepted"]), 2)
        self.assertEqual([item["source_filename"] for item in payload["accepted"]], ["one.txt", "two.md"])
        self.assertTrue(all(item["preserve_format"] for item in payload["accepted"]))
        self.assertEqual(payload["queued_count"], 2)
        self.assertEqual(payload["rejected"][0]["filename"], "blocked.exe")
        self.assertEqual(run_batch.await_count, 1)
        self.db.refresh(self.user)
        self.assertEqual(self.user.usage_count, 2)

    def test_batch_upload_rejects_total_size_before_creating_sessions(self):
        with (
            patch.object(optimization_routes.settings, "MAX_BATCH_TOTAL_SIZE_MB", 1),
            patch(
                "app.routes.optimization.run_batch_optimizations",
                new_callable=AsyncMock,
            ) as run_batch,
        ):
            response = self.client.post(
                "/api/optimization/start-files",
                headers={"X-Card-Key": self.user.card_key},
                data={"processing_mode": "paper_polish"},
                files=[
                    ("files", ("one.txt", b"a" * 600_000, "text/plain")),
                    ("files", ("two.txt", b"b" * 600_000, "text/plain")),
                ],
            )

        self.assertEqual(response.status_code, 413, response.text)
        self.assertEqual(self.db.query(OptimizationSession).count(), 0)
        self.db.refresh(self.user)
        self.assertEqual(self.user.usage_count, 0)
        self.assertEqual(run_batch.await_count, 0)

    def test_batch_export_route_returns_same_format_zip_and_deduplicates_names(self):
        source_directory = Path(self.directory.name) / "sources"
        source_directory.mkdir()

        def source_path(session_id, source_format):
            return str(source_directory / f"{session_id}.{source_format}")

        session_ids = []
        with patch("app.routes.optimization.source_document_path", side_effect=source_path):
            for index, optimized_text in enumerate(("润色一", "润色二")):
                content = b"\xef\xbb\xbf" + "  原文  \r\n".encode("utf-8")
                original_text, manifest, segments = parse_text_document(content, "txt")
                session, _ = _create_file_session(
                    self.db,
                    self.user,
                    {
                        "filename": "same.txt",
                        "source_format": "txt",
                        "content": content,
                        "original_text": original_text,
                        "manifest": manifest,
                        "segments": segments,
                    },
                    "paper_polish",
                    batch_id="batch-export",
                    batch_index=index,
                )
                session.status = "completed"
                segment = self.db.query(OptimizationSegment).filter_by(session_id=session.id).one()
                segment.polished_text = optimized_text
                segment.status = "completed"
                session_ids.append(session.session_id)
            self.db.commit()

            response = self.client.post(
                "/api/optimization/batch/export",
                headers={"X-Card-Key": self.user.card_key},
                json={
                    "session_ids": session_ids,
                    "acknowledge_academic_integrity": True,
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/zip")
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertEqual(archive.namelist(), ["same_优化.txt", "same_优化_2.txt"])
            self.assertEqual(
                archive.read("same_优化.txt"),
                b"\xef\xbb\xbf" + "  润色一  \r\n".encode("utf-8"),
            )
            self.assertEqual(
                archive.read("same_优化_2.txt"),
                b"\xef\xbb\xbf" + "  润色二  \r\n".encode("utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
