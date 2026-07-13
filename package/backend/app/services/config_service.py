"""Validated and atomic runtime configuration persistence."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Dict

from app.config import get_env_file_path, reload_settings, settings
from app.security import validate_ai_base_url


class ConfigUpdateError(ValueError):
    pass


SECRET_KEYS = {
    "POLISH_API_KEY",
    "ENHANCE_API_KEY",
    "EMOTION_API_KEY",
    "COMPRESSION_API_KEY",
}
URL_KEYS = {
    "POLISH_BASE_URL",
    "ENHANCE_BASE_URL",
    "EMOTION_BASE_URL",
    "COMPRESSION_BASE_URL",
}
MODEL_KEYS = {
    "POLISH_MODEL",
    "ENHANCE_MODEL",
    "EMOTION_MODEL",
    "COMPRESSION_MODEL",
}
BOOL_KEYS = {"THINKING_MODE_ENABLED", "USE_STREAMING"}
INT_RANGES = {
    "MAX_CONCURRENT_USERS": (1, 1000),
    "MAX_CONCURRENT_AI_REQUESTS": (1, 1000),
    "HISTORY_COMPRESSION_THRESHOLD": (100, 10_000_000),
    "DEFAULT_USAGE_LIMIT": (0, 10_000_000),
    "DEFAULT_TASK_CONCURRENCY_LIMIT": (1, 100),
    "SEGMENT_SKIP_THRESHOLD": (0, 100_000),
    "MAX_UPLOAD_FILE_SIZE_MB": (1, 500),
    "API_REQUEST_INTERVAL": (0, 3600),
}
ALLOWED_KEYS = SECRET_KEYS | URL_KEYS | MODEL_KEYS | BOOL_KEYS | set(INT_RANGES) | {
    "THINKING_MODE_EFFORT",
}


def public_runtime_config() -> Dict[str, object]:
    def provider(prefix: str) -> Dict[str, object]:
        api_key = getattr(settings, f"{prefix}_API_KEY", None) or ""
        return {
            "model": getattr(settings, f"{prefix}_MODEL", "") or "",
            "api_key": "",
            "api_key_configured": bool(api_key),
            "base_url": getattr(settings, f"{prefix}_BASE_URL", None) or "",
        }

    return {
        "polish": provider("POLISH"),
        "enhance": provider("ENHANCE"),
        "emotion": provider("EMOTION"),
        "compression": provider("COMPRESSION"),
        "thinking": {
            "enabled": settings.THINKING_MODE_ENABLED,
            "effort": settings.THINKING_MODE_EFFORT,
        },
        "system": {
            "max_concurrent_users": settings.MAX_CONCURRENT_USERS,
            "max_concurrent_ai_requests": settings.MAX_CONCURRENT_AI_REQUESTS,
            "history_compression_threshold": settings.HISTORY_COMPRESSION_THRESHOLD,
            "default_usage_limit": settings.DEFAULT_USAGE_LIMIT,
            "default_task_concurrency_limit": settings.DEFAULT_TASK_CONCURRENCY_LIMIT,
            "segment_skip_threshold": settings.SEGMENT_SKIP_THRESHOLD,
            "use_streaming": settings.USE_STREAMING,
            "max_upload_file_size_mb": settings.MAX_UPLOAD_FILE_SIZE_MB,
            "api_request_interval": settings.API_REQUEST_INTERVAL,
        },
    }


def _validated_updates(updates: Dict[str, str]) -> Dict[str, str]:
    unknown = sorted(set(updates) - ALLOWED_KEYS)
    if unknown:
        raise ConfigUpdateError("Unsupported configuration keys: " + ", ".join(unknown))

    clean: Dict[str, str] = {}
    for key, raw_value in updates.items():
        value = str(raw_value).strip()
        if "\n" in value or "\r" in value:
            raise ConfigUpdateError(f"{key} contains a newline")
        if key in SECRET_KEYS and not value:
            continue
        if key in MODEL_KEYS:
            if not value or len(value) > 200:
                raise ConfigUpdateError(f"{key} must contain 1 to 200 characters")
        elif key in URL_KEYS:
            try:
                value = validate_ai_base_url(value)
            except ValueError as exc:
                raise ConfigUpdateError(f"{key}: {exc}") from exc
        elif key in BOOL_KEYS:
            lowered = value.lower()
            if lowered not in {"true", "false", "1", "0", "yes", "no"}:
                raise ConfigUpdateError(f"{key} must be a boolean")
            value = "true" if lowered in {"true", "1", "yes"} else "false"
        elif key in INT_RANGES:
            minimum, maximum = INT_RANGES[key]
            try:
                number = int(value)
            except ValueError as exc:
                raise ConfigUpdateError(f"{key} must be an integer") from exc
            if not minimum <= number <= maximum:
                raise ConfigUpdateError(f"{key} must be between {minimum} and {maximum}")
            value = str(number)
        elif key == "THINKING_MODE_EFFORT" and value not in {"none", "low", "medium", "high", "xhigh"}:
            raise ConfigUpdateError("THINKING_MODE_EFFORT is invalid")
        clean[key] = value
    return clean


def update_runtime_config(updates: Dict[str, str]) -> list[str]:
    clean = _validated_updates(updates)
    if not clean:
        return []

    env_path = Path(get_env_file_path())
    if not env_path.exists():
        raise FileNotFoundError(str(env_path))

    lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    updated = set()
    output = []
    for line in lines:
        stripped = line.rstrip("\r\n")
        if "=" in stripped and not stripped.lstrip().startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in clean:
                output.append(f"{key}={clean[key]}\n")
                updated.add(key)
                continue
        output.append(line)
    for key, value in clean.items():
        if key not in updated:
            output.append(f"{key}={value}\n")

    fd, temporary = tempfile.mkstemp(prefix=".env.", dir=str(env_path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.writelines(output)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, env_path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise

    reload_settings()
    return sorted(clean)
