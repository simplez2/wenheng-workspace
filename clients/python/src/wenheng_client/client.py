from __future__ import annotations

import mimetypes
import re
import time
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.parse import unquote

import httpx


DEFAULT_BASE_URL = "https://aipass.hxai.de"
API_PATH = "/api/v1/agent"
TERMINAL_STATUSES = {"completed", "failed", "stopped"}
CONTENT_DISPOSITION_UTF8 = re.compile(r"filename\*=UTF-8''([^;]+)", re.IGNORECASE)
CONTENT_DISPOSITION_PLAIN = re.compile(r'filename="?([^";]+)"?', re.IGNORECASE)


class WenhengAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: Optional[str] = None,
        request_id: Optional[str] = None,
        details: Any = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        self.details = details


@dataclass(frozen=True)
class DownloadedResult:
    content: bytes
    filename: str
    content_type: str

    def save(self, output: str | Path) -> Path:
        destination = Path(output).expanduser()
        if destination.exists() and destination.is_dir():
            destination = destination / self.filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.content)
        return destination


class WenhengClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 60.0,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        api_key = (api_key or "").strip()
        if not api_key:
            raise ValueError("api_key is required")
        root = base_url.rstrip("/")
        self.api_root = root if root.endswith(API_PATH) else root + API_PATH
        self.timeout = timeout
        self._client = httpx.Client(
            base_url=self.api_root,
            timeout=timeout,
            follow_redirects=True,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "wenheng-agent-client/1.0.0",
            },
            transport=transport,
        )

    def __enter__(self) -> "WenhengClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        response = self._client.request(method, path, **kwargs)
        if response.is_success:
            return response
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            message = error.get("message") or response.reason_phrase
            code = error.get("code")
            request_id = error.get("request_id")
            details = error.get("details")
        else:
            detail = payload.get("detail") if isinstance(payload, dict) else None
            message = detail if isinstance(detail, str) else response.reason_phrase
            code = None
            request_id = response.headers.get("X-Request-ID")
            details = detail if not isinstance(detail, str) else None
        raise WenhengAPIError(
            message,
            status_code=response.status_code,
            code=code,
            request_id=request_id,
            details=details,
        )

    def _json(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        response = self._request(method, path, **kwargs)
        payload = response.json()
        request_id = response.headers.get("X-Request-ID")
        if isinstance(payload, dict) and request_id:
            metadata = payload.setdefault("_meta", {})
            if isinstance(metadata, dict):
                metadata.setdefault("request_id", request_id)
        return payload

    @staticmethod
    def _filename(response: httpx.Response, fallback: str) -> str:
        disposition = response.headers.get("Content-Disposition", "")
        utf8_match = CONTENT_DISPOSITION_UTF8.search(disposition)
        if utf8_match:
            return Path(unquote(utf8_match.group(1))).name
        plain_match = CONTENT_DISPOSITION_PLAIN.search(disposition)
        if plain_match:
            return Path(plain_match.group(1)).name
        return fallback

    @classmethod
    def _downloaded(cls, response: httpx.Response, fallback: str) -> DownloadedResult:
        return DownloadedResult(
            content=response.content,
            filename=cls._filename(response, fallback),
            content_type=response.headers.get(
                "Content-Type", "application/octet-stream"
            ),
        )

    def capabilities(self) -> Dict[str, Any]:
        return self._json("GET", "/capabilities")

    def create_text(
        self,
        text: str,
        processing_mode: str = "paper_polish_enhance",
    ) -> Dict[str, Any]:
        return self._json(
            "POST",
            "/tasks/text",
            json={"text": text, "processing_mode": processing_mode},
        )

    def create_file(
        self,
        path: str | Path,
        processing_mode: str = "paper_polish_enhance",
    ) -> Dict[str, Any]:
        source = Path(path).expanduser().resolve()
        mime_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        with source.open("rb") as handle:
            return self._json(
                "POST",
                "/tasks/file",
                data={"processing_mode": processing_mode},
                files={"file": (source.name, handle, mime_type)},
                timeout=max(self.timeout, 120),
            )

    def create_batch(
        self,
        paths: Iterable[str | Path],
        processing_mode: str = "paper_polish_enhance",
    ) -> Dict[str, Any]:
        sources = [Path(path).expanduser().resolve() for path in paths]
        with ExitStack() as stack:
            files = []
            for source in sources:
                handle = stack.enter_context(source.open("rb"))
                mime_type = (
                    mimetypes.guess_type(source.name)[0] or "application/octet-stream"
                )
                files.append(("files", (source.name, handle, mime_type)))
            return self._json(
                "POST",
                "/batches/files",
                data={"processing_mode": processing_mode},
                files=files,
                timeout=max(self.timeout, 180),
            )

    def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        batch_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if batch_id:
            params["batch_id"] = batch_id
        return self._json("GET", "/tasks", params=params)

    def get_task(self, task_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/tasks/{task_id}")

    def get_batch(self, batch_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/batches/{batch_id}")

    def wait_task(
        self,
        task_id: str,
        *,
        timeout: float = 3600,
        poll_interval: float = 1,
    ) -> Dict[str, Any]:
        deadline = time.monotonic() + max(timeout, 0)
        while True:
            remaining = max(deadline - time.monotonic(), 0)
            wait_chunk = min(30.0, remaining)
            result = self._json(
                "GET",
                f"/tasks/{task_id}/wait",
                params={
                    "timeout_seconds": wait_chunk,
                    "poll_interval": poll_interval,
                },
                timeout=max(self.timeout, wait_chunk + 15),
            )
            if result.get("terminal") or remaining <= 0:
                return result

    def wait_batch(
        self,
        batch_id: str,
        *,
        timeout: float = 3600,
        poll_interval: float = 1,
    ) -> Dict[str, Any]:
        deadline = time.monotonic() + max(timeout, 0)
        while True:
            remaining = max(deadline - time.monotonic(), 0)
            wait_chunk = min(30.0, remaining)
            result = self._json(
                "GET",
                f"/batches/{batch_id}/wait",
                params={
                    "timeout_seconds": wait_chunk,
                    "poll_interval": poll_interval,
                },
                timeout=max(self.timeout, wait_chunk + 15),
            )
            if result.get("terminal") or remaining <= 0:
                return result

    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        return self._json("POST", f"/tasks/{task_id}/cancel")

    def resume_task(self, task_id: str) -> Dict[str, Any]:
        return self._json("POST", f"/tasks/{task_id}/resume")

    def download_task(
        self,
        task_id: str,
        *,
        acknowledge_academic_integrity: bool,
        export_format: Optional[str] = None,
    ) -> DownloadedResult:
        params: Dict[str, Any] = {
            "acknowledge_academic_integrity": str(
                acknowledge_academic_integrity
            ).lower()
        }
        if export_format:
            params["format"] = export_format
        response = self._request(
            "GET",
            f"/tasks/{task_id}/result",
            params=params,
            headers={"Accept": "*/*"},
            timeout=max(self.timeout, 180),
        )
        return self._downloaded(response, f"wenheng-result-{task_id[:8]}")

    def download_batch(
        self,
        batch_id: str,
        *,
        acknowledge_academic_integrity: bool,
    ) -> DownloadedResult:
        response = self._request(
            "GET",
            f"/batches/{batch_id}/result",
            params={
                "acknowledge_academic_integrity": str(
                    acknowledge_academic_integrity
                ).lower()
            },
            headers={"Accept": "application/zip"},
            timeout=max(self.timeout, 300),
        )
        return self._downloaded(response, f"wenheng-batch-{batch_id[:8]}.zip")
