import tempfile
import unittest
from pathlib import Path

import httpx

from wenheng_client import WenhengAPIError, WenhengClient


class WenhengClientTests(unittest.TestCase):
    def test_create_wait_and_download(self):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            self.assertEqual(request.headers["Authorization"], "Bearer TEST-CARD")
            if request.url.path.endswith("/tasks/text"):
                return httpx.Response(
                    202, json={"task_id": "task-1", "status": "queued"}
                )
            if request.url.path.endswith("/tasks/task-1/wait"):
                return httpx.Response(
                    200,
                    json={
                        "task_id": "task-1",
                        "status": "completed",
                        "terminal": True,
                        "result_ready": True,
                    },
                )
            if request.url.path.endswith("/tasks/task-1/result"):
                return httpx.Response(
                    200,
                    content=b"result text",
                    headers={
                        "Content-Type": "text/plain",
                        "Content-Disposition": (
                            "attachment; filename=wenheng-result.txt; "
                            "filename*=UTF-8''paper_%E4%BC%98%E5%8C%96.txt"
                        ),
                    },
                )
            return httpx.Response(404)

        with WenhengClient(
            "TEST-CARD",
            "https://example.test",
            transport=httpx.MockTransport(handler),
        ) as client:
            task = client.create_text("hello", "paper_polish")
            completed = client.wait_task(task["task_id"], timeout=5)
            downloaded = client.download_task(
                task["task_id"],
                acknowledge_academic_integrity=True,
            )

        self.assertEqual(completed["status"], "completed")
        self.assertEqual(downloaded.filename, "paper_优化.txt")
        self.assertEqual(downloaded.content, b"result text")
        self.assertEqual(len(requests), 3)

    def test_file_upload_and_save(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertIn(
                'name="file"', request.content.decode("utf-8", errors="ignore")
            )
            self.assertIn(
                "sample.txt", request.content.decode("utf-8", errors="ignore")
            )
            return httpx.Response(
                202, json={"task_id": "file-task", "status": "queued"}
            )

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.txt"
            source.write_text("source", encoding="utf-8")
            with WenhengClient(
                "TEST-CARD",
                "https://example.test/api/v1/agent",
                transport=httpx.MockTransport(handler),
            ) as client:
                task = client.create_file(source)
            self.assertEqual(task["task_id"], "file-task")

    def test_machine_readable_error_is_exposed(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                429,
                json={
                    "error": {
                        "code": "queue_limit_reached",
                        "message": "Too many queued tasks",
                        "request_id": "request-1",
                        "details": {"limit": 100},
                    }
                },
            )

        with WenhengClient(
            "TEST-CARD",
            "https://example.test",
            transport=httpx.MockTransport(handler),
        ) as client:
            with self.assertRaises(WenhengAPIError) as context:
                client.capabilities()
        error = context.exception
        self.assertEqual(error.status_code, 429)
        self.assertEqual(error.code, "queue_limit_reached")
        self.assertEqual(error.request_id, "request-1")
        self.assertEqual(error.details, {"limit": 100})


if __name__ == "__main__":
    unittest.main()
