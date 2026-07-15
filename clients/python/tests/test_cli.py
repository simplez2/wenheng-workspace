import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from wenheng_client import cli


class FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def capabilities(self):
        return {"api_version": "v1", "authentication": "bearer"}

    def create_text(self, text, processing_mode):
        return {
            "task_id": "task-1",
            "status": "queued",
            "terminal": False,
            "result_ready": False,
            "received_text": text,
            "processing_mode": processing_mode,
        }


class CliTests(unittest.TestCase):
    def test_capabilities_prints_json(self):
        stdout = io.StringIO()
        with patch.object(cli, "WenhengClient", FakeClient), redirect_stdout(stdout):
            exit_code = cli.main(["--api-key", "TEST", "capabilities"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["api_version"], "v1")

    def test_text_submission_from_argument(self):
        stdout = io.StringIO()
        with patch.object(cli, "WenhengClient", FakeClient), redirect_stdout(stdout):
            exit_code = cli.main(
                [
                    "--api-key",
                    "TEST",
                    "text",
                    "--text",
                    "hello agent",
                    "--mode",
                    "paper_polish",
                ]
            )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["received_text"], "hello agent")
        self.assertEqual(payload["processing_mode"], "paper_polish")

    def test_missing_api_key_is_machine_readable(self):
        stderr = io.StringIO()
        with (
            patch.dict("os.environ", {}, clear=True),
            redirect_stderr(stderr),
        ):
            exit_code = cli.main(["capabilities"])
        self.assertEqual(exit_code, 2)
        self.assertEqual(json.loads(stderr.getvalue())["error"]["code"], "client_error")


if __name__ == "__main__":
    unittest.main()
