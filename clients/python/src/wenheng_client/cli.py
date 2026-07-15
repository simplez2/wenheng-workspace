from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from . import __version__
from .client import DEFAULT_BASE_URL, DownloadedResult, WenhengAPIError, WenhengClient


PROCESSING_MODES = (
    "paper_polish",
    "paper_enhance",
    "paper_polish_enhance",
    "emotion_polish",
)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _print_json(payload: Any, *, stream=None) -> None:
    stream = stream or sys.stdout
    json.dump(payload, stream, ensure_ascii=False, indent=2, default=str)
    stream.write("\n")


def _add_mode(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mode",
        choices=PROCESSING_MODES,
        default="paper_polish_enhance",
        help="Optimization mode (default: paper_polish_enhance)",
    )


def _add_wait_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--wait", action="store_true", help="Wait for completion")
    parser.add_argument(
        "--wait-timeout",
        type=float,
        default=3600,
        help="Maximum wait time in seconds (default: 3600)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1,
        help="Polling interval in seconds (default: 1)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wenheng",
        description="CLI for the Wenheng Agent API",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("WENHENG_BASE_URL", DEFAULT_BASE_URL),
        help="Service URL (env: WENHENG_BASE_URL)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("WENHENG_API_KEY"),
        help="User card key (env: WENHENG_API_KEY)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("WENHENG_HTTP_TIMEOUT", "60")),
        help="HTTP timeout in seconds (env: WENHENG_HTTP_TIMEOUT)",
    )
    parser.add_argument(
        "--acknowledge-academic-integrity",
        action="store_true",
        default=_env_bool("WENHENG_ACKNOWLEDGE_ACADEMIC_INTEGRITY"),
        help=(
            "Acknowledge responsibility before result downloads "
            "(env: WENHENG_ACKNOWLEDGE_ACADEMIC_INTEGRITY=true)"
        ),
    )

    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("capabilities", help="Show formats, modes, and limits")

    text_parser = commands.add_parser(
        "text", help="Submit text from an argument, file, or stdin"
    )
    source = text_parser.add_mutually_exclusive_group()
    source.add_argument("--text", help="Text to optimize")
    source.add_argument("--file", type=Path, help="Read UTF-8 text from this file")
    _add_mode(text_parser)
    _add_wait_options(text_parser)
    text_parser.add_argument("-o", "--output", help="Download completed result here")
    text_parser.add_argument(
        "--format", choices=("txt", "md", "docx", "pdf"), default="txt"
    )

    submit_parser = commands.add_parser("submit", help="Submit one document")
    submit_parser.add_argument("file", type=Path)
    _add_mode(submit_parser)
    _add_wait_options(submit_parser)
    submit_parser.add_argument("-o", "--output", help="Download completed result here")

    batch_parser = commands.add_parser(
        "batch", help="Submit multiple documents as one batch"
    )
    batch_parser.add_argument("files", nargs="+", type=Path)
    _add_mode(batch_parser)
    _add_wait_options(batch_parser)
    batch_parser.add_argument("-o", "--output", help="Download completed ZIP here")

    tasks_parser = commands.add_parser("tasks", help="List recent tasks")
    tasks_parser.add_argument(
        "--status", choices=("queued", "processing", "completed", "failed", "stopped")
    )
    tasks_parser.add_argument("--batch-id")
    tasks_parser.add_argument("--limit", type=int, default=20)
    tasks_parser.add_argument("--offset", type=int, default=0)

    status_parser = commands.add_parser("status", help="Get one task")
    status_parser.add_argument("task_id")

    wait_parser = commands.add_parser("wait", help="Wait for one task")
    wait_parser.add_argument("task_id")
    wait_parser.add_argument("--wait-timeout", type=float, default=3600)
    wait_parser.add_argument("--poll-interval", type=float, default=1)

    batch_status_parser = commands.add_parser("batch-status", help="Get one batch")
    batch_status_parser.add_argument("batch_id")

    batch_wait_parser = commands.add_parser("batch-wait", help="Wait for one batch")
    batch_wait_parser.add_argument("batch_id")
    batch_wait_parser.add_argument("--wait-timeout", type=float, default=3600)
    batch_wait_parser.add_argument("--poll-interval", type=float, default=1)

    cancel_parser = commands.add_parser(
        "cancel", help="Cancel a queued or running task"
    )
    cancel_parser.add_argument("task_id")

    resume_parser = commands.add_parser(
        "resume", help="Resume a stopped task or retry a failure"
    )
    resume_parser.add_argument("task_id")

    download_parser = commands.add_parser(
        "download", help="Download one completed result"
    )
    download_parser.add_argument("task_id")
    download_parser.add_argument("-o", "--output", default=".")
    download_parser.add_argument("--format", choices=("txt", "md", "docx", "pdf"))

    batch_download_parser = commands.add_parser(
        "batch-download", help="Download a completed batch ZIP"
    )
    batch_download_parser.add_argument("batch_id")
    batch_download_parser.add_argument("-o", "--output", default=".")

    return parser


def _read_text(args: argparse.Namespace) -> str:
    if args.text is not None:
        return args.text
    if args.file is not None:
        return args.file.expanduser().read_text(encoding="utf-8")
    if sys.stdin.isatty():
        raise ValueError("Provide --text, --file, or pipe text through stdin")
    return sys.stdin.read()


def _save_download(result: DownloadedResult, output: str) -> Optional[Path]:
    if output == "-":
        sys.stdout.buffer.write(result.content)
        sys.stdout.buffer.flush()
        return None
    return result.save(output)


def _download_summary(result: DownloadedResult, path: Optional[Path]) -> Dict[str, Any]:
    return {
        "filename": result.filename,
        "content_type": result.content_type,
        "bytes": len(result.content),
        "saved_to": str(path.resolve()) if path else None,
    }


def _require_acknowledgement(args: argparse.Namespace) -> None:
    if not args.acknowledge_academic_integrity:
        raise ValueError(
            "Result download requires --acknowledge-academic-integrity or "
            "WENHENG_ACKNOWLEDGE_ACADEMIC_INTEGRITY=true"
        )


def _wait_task(client: WenhengClient, task_id: str, args: argparse.Namespace):
    return client.wait_task(
        task_id,
        timeout=args.wait_timeout,
        poll_interval=args.poll_interval,
    )


def _wait_batch(client: WenhengClient, batch_id: str, args: argparse.Namespace):
    return client.wait_batch(
        batch_id,
        timeout=args.wait_timeout,
        poll_interval=args.poll_interval,
    )


def run(args: argparse.Namespace) -> int:
    if not args.api_key:
        raise ValueError("Set --api-key or WENHENG_API_KEY")

    with WenhengClient(args.api_key, args.base_url, timeout=args.timeout) as client:
        if args.command == "capabilities":
            _print_json(client.capabilities())
            return 0

        if args.command == "text":
            task = client.create_text(_read_text(args), args.mode)
            if args.wait or args.output:
                task = _wait_task(client, task["task_id"], args)
            if args.output and task.get("result_ready"):
                _require_acknowledgement(args)
                result = client.download_task(
                    task["task_id"],
                    acknowledge_academic_integrity=True,
                    export_format=args.format,
                )
                path = _save_download(result, args.output)
                if path is None:
                    return 0
                task["download"] = _download_summary(result, path)
            _print_json(task)
            return 0 if task.get("status") != "failed" else 1

        if args.command == "submit":
            task = client.create_file(args.file, args.mode)
            if args.wait or args.output:
                task = _wait_task(client, task["task_id"], args)
            if args.output and task.get("result_ready"):
                _require_acknowledgement(args)
                result = client.download_task(
                    task["task_id"],
                    acknowledge_academic_integrity=True,
                )
                path = _save_download(result, args.output)
                if path is None:
                    return 0
                task["download"] = _download_summary(result, path)
            _print_json(task)
            return 0 if task.get("status") != "failed" else 1

        if args.command == "batch":
            batch = client.create_batch(args.files, args.mode)
            if args.wait or args.output:
                batch = _wait_batch(client, batch["batch_id"], args)
            if args.output and batch.get("result_ready"):
                _require_acknowledgement(args)
                result = client.download_batch(
                    batch["batch_id"],
                    acknowledge_academic_integrity=True,
                )
                path = _save_download(result, args.output)
                if path is None:
                    return 0
                batch["download"] = _download_summary(result, path)
            _print_json(batch)
            return 0 if batch.get("status") not in {"failed", "partial_failed"} else 1

        if args.command == "tasks":
            _print_json(
                client.list_tasks(
                    status=args.status,
                    batch_id=args.batch_id,
                    limit=args.limit,
                    offset=args.offset,
                )
            )
            return 0

        if args.command == "status":
            _print_json(client.get_task(args.task_id))
            return 0

        if args.command == "wait":
            task = _wait_task(client, args.task_id, args)
            _print_json(task)
            return 0 if task.get("status") != "failed" else 1

        if args.command == "batch-status":
            _print_json(client.get_batch(args.batch_id))
            return 0

        if args.command == "batch-wait":
            batch = _wait_batch(client, args.batch_id, args)
            _print_json(batch)
            return 0 if batch.get("status") not in {"failed", "partial_failed"} else 1

        if args.command == "cancel":
            _print_json(client.cancel_task(args.task_id))
            return 0

        if args.command == "resume":
            _print_json(client.resume_task(args.task_id))
            return 0

        if args.command == "download":
            _require_acknowledgement(args)
            result = client.download_task(
                args.task_id,
                acknowledge_academic_integrity=True,
                export_format=args.format,
            )
            path = _save_download(result, args.output)
            if path is not None:
                _print_json(_download_summary(result, path))
            return 0

        if args.command == "batch-download":
            _require_acknowledgement(args)
            result = client.download_batch(
                args.batch_id,
                acknowledge_academic_integrity=True,
            )
            path = _save_download(result, args.output)
            if path is not None:
                _print_json(_download_summary(result, path))
            return 0

    raise ValueError(f"Unknown command: {args.command}")


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except WenhengAPIError as exc:
        _print_json(
            {
                "error": {
                    "code": exc.code or "api_error",
                    "message": str(exc),
                    "status_code": exc.status_code,
                    "request_id": exc.request_id,
                    "details": exc.details,
                }
            },
            stream=sys.stderr,
        )
        return 2
    except (OSError, ValueError) as exc:
        _print_json(
            {
                "error": {
                    "code": "client_error",
                    "message": str(exc),
                }
            },
            stream=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        _print_json(
            {"error": {"code": "interrupted", "message": "Interrupted"}},
            stream=sys.stderr,
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
