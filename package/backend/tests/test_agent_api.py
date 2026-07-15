import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent_api import create_agent_app
from app.database import Base, get_db
from app.models.models import OptimizationSession, User
from app.routes import optimization as optimization_routes


class AgentApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        database_path = Path(self.directory.name) / "agent.db"
        self.engine = create_engine(
            f"sqlite:///{database_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.user = User(
            card_key="AGENT-CARD",
            access_link="/access/AGENT-CARD",
            usage_limit=100,
            usage_count=0,
            task_concurrency_limit=2,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        app = create_agent_app()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.headers = {"Authorization": f"Bearer {self.user.card_key}"}
        self.source_directory = Path(self.directory.name) / "sources"
        self.source_directory.mkdir()

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()
        self.directory.cleanup()

    def source_path(self, session_id, source_format):
        return str(self.source_directory / f"{session_id}.{source_format}")

    def test_openapi_and_standardized_bearer_auth(self):
        unauthorized = self.client.get("/capabilities")
        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(
            unauthorized.json()["error"]["code"], "authentication_required"
        )
        self.assertEqual(unauthorized.headers["WWW-Authenticate"], "Bearer")
        self.assertTrue(unauthorized.headers["X-Request-ID"])

        invalid = self.client.get(
            "/capabilities",
            headers={"Authorization": "Bearer INVALID-CARD"},
        )
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(invalid.headers["WWW-Authenticate"], "Bearer")

        response = self.client.get("/capabilities", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["authentication"], "bearer")
        self.assertEqual(payload["user_task_concurrency_limit"], 2)
        self.assertIn("docx", payload["input_formats"])

        schema = self.client.get("/openapi.json").json()
        self.assertIn("WenhengCardKey", schema["components"]["securitySchemes"])
        self.assertIn("/tasks/text", schema["paths"])
        self.assertIn("/batches/{batch_id}/result", schema["paths"])

    def test_agent_app_mount_exposes_docs_and_health(self):
        parent = FastAPI()
        parent.mount("/api/v1/agent", create_agent_app())
        with TestClient(parent) as client:
            health = client.get("/api/v1/agent/health")
            docs = client.get("/api/v1/agent/docs")
            schema = client.get("/api/v1/agent/openapi.json")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["api_version"], "v1")
        self.assertEqual(docs.status_code, 200)
        self.assertEqual(schema.status_code, 200)
        self.assertIn("/tasks/text", schema.json()["paths"])

    def test_text_task_status_cancel_and_resume(self):
        with patch.object(
            optimization_routes,
            "run_optimization",
            new_callable=AsyncMock,
        ) as run_optimization:
            response = self.client.post(
                "/tasks/text",
                headers=self.headers,
                json={"text": "Agent API test text", "processing_mode": "paper_polish"},
            )
            self.assertEqual(response.status_code, 202, response.text)
            task = response.json()
            self.assertEqual(task["status"], "queued")
            self.assertFalse(task["terminal"])
            self.assertEqual(run_optimization.await_count, 1)

            status = self.client.get(f"/tasks/{task['task_id']}", headers=self.headers)
            self.assertEqual(status.status_code, 200)
            self.assertEqual(status.json()["task_id"], task["task_id"])

            wait = self.client.get(
                f"/tasks/{task['task_id']}/wait?timeout_seconds=0",
                headers=self.headers,
            )
            self.assertEqual(wait.status_code, 200)
            self.assertEqual(wait.json()["status"], "queued")

            cancelled = self.client.post(
                f"/tasks/{task['task_id']}/cancel",
                headers=self.headers,
            )
            self.assertEqual(cancelled.status_code, 200)
            self.assertEqual(cancelled.json()["status"], "stopped")
            self.assertTrue(cancelled.json()["retryable"])

            resumed = self.client.post(
                f"/tasks/{task['task_id']}/resume",
                headers=self.headers,
            )
            self.assertEqual(resumed.status_code, 202)
            self.assertEqual(resumed.json()["status"], "queued")
            self.assertEqual(run_optimization.await_count, 2)

        self.db.refresh(self.user)
        self.assertEqual(self.user.usage_count, 1)

    def test_file_result_preserves_original_bytes(self):
        original = b"\xef\xbb\xbfA  \r\n\r\nB\r\n"
        with (
            patch.object(
                optimization_routes,
                "source_document_path",
                side_effect=self.source_path,
            ),
            patch.object(
                optimization_routes,
                "run_optimization",
                new_callable=AsyncMock,
            ),
        ):
            response = self.client.post(
                "/tasks/file",
                headers=self.headers,
                data={"processing_mode": "paper_polish"},
                files={"file": ("source.txt", original, "text/plain")},
            )
            self.assertEqual(response.status_code, 202, response.text)
            task_id = response.json()["task_id"]
            session = (
                self.db.query(OptimizationSession).filter_by(session_id=task_id).one()
            )
            session.status = "completed"
            session.progress = 100
            for segment in session.segments:
                segment.polished_text = segment.original_text
                segment.status = "completed"
            self.db.commit()

            blocked = self.client.get(f"/tasks/{task_id}/result", headers=self.headers)
            self.assertEqual(blocked.status_code, 400)
            self.assertEqual(blocked.json()["error"]["code"], "bad_request")

            result = self.client.get(
                f"/tasks/{task_id}/result?acknowledge_academic_integrity=true",
                headers=self.headers,
            )
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.content, original)
            self.assertIn("source_", result.headers["Content-Disposition"])

    def test_batch_status_and_zip_result(self):
        with (
            patch.object(
                optimization_routes,
                "source_document_path",
                side_effect=self.source_path,
            ),
            patch.object(
                optimization_routes,
                "run_batch_optimizations",
                new_callable=AsyncMock,
            ),
        ):
            response = self.client.post(
                "/batches/files",
                headers=self.headers,
                data={"processing_mode": "paper_polish"},
                files=[
                    ("files", ("same.txt", b"First", "text/plain")),
                    ("files", ("same.txt", b"Second", "text/plain")),
                ],
            )
            self.assertEqual(response.status_code, 202, response.text)
            batch_id = response.json()["batch_id"]
            sessions = (
                self.db.query(OptimizationSession).filter_by(batch_id=batch_id).all()
            )
            self.assertEqual(len(sessions), 2)
            for session in sessions:
                session.status = "completed"
                session.progress = 100
                for segment in session.segments:
                    segment.polished_text = segment.original_text
                    segment.status = "completed"
            self.db.commit()

            status = self.client.get(f"/batches/{batch_id}", headers=self.headers)
            self.assertEqual(status.status_code, 200)
            self.assertTrue(status.json()["result_ready"])
            self.assertEqual(status.json()["completed"], 2)

            result = self.client.get(
                f"/batches/{batch_id}/result?acknowledge_academic_integrity=true",
                headers=self.headers,
            )
            self.assertEqual(result.status_code, 200, result.text)
            with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
                self.assertEqual(len(archive.namelist()), 2)
                self.assertNotEqual(archive.namelist()[0], archive.namelist()[1])
                self.assertEqual(
                    sorted(archive.read(name) for name in archive.namelist()),
                    [b"First", b"Second"],
                )

    def test_validation_error_uses_machine_readable_shape(self):
        response = self.client.post(
            "/tasks/text",
            headers={**self.headers, "X-Request-ID": "agent-test-request"},
            json={"text": "", "processing_mode": "unknown"},
        )
        self.assertEqual(response.status_code, 422)
        payload = response.json()["error"]
        self.assertEqual(payload["code"], "validation_error")
        self.assertEqual(payload["request_id"], "agent-test-request")
        self.assertEqual(response.headers["X-Request-ID"], "agent-test-request")


if __name__ == "__main__":
    unittest.main()
