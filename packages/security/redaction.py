from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

_CONTENT_KEY_MARKERS = (
    "content",
    "document",
    "excerpt",
    "instruction",
    "model_output",
    "ocr",
    "payload",
    "prompt",
    "provider_response",
    "text",
)
_SECRET_KEY_MARKERS = (
    "authorization",
    "cookie",
    "credential",
    "key",
    "password",
    "secret",
    "token",
)
_SAFE_KEY_MARKERS = (
    "_id",
    "_hash",
    "_version",
    "attempt",
    "count",
    "duration_ms",
    "error_code",
    "latency_ms",
    "model",
    "node_name",
    "outcome",
    "policy_version",
    "provider",
    "request_id",
    "schema_version",
    "status",
    "tenant_id",
)


def safe_log_event(event: str, fields: Mapping[str, Any]) -> dict[str, Any]:
    """Build a bounded structured event without copying untrusted content."""

    result: dict[str, Any] = {"event": event[:120]}
    for key, value in fields.items():
        normalized = key.casefold()
        if any(marker in normalized for marker in _SECRET_KEY_MARKERS):
            result[key] = "[REDACTED_SECRET]"
        elif any(marker in normalized for marker in _CONTENT_KEY_MARKERS):
            result[key] = _content_marker(value)
        elif normalized in _SAFE_KEY_MARKERS or any(
            normalized.endswith(marker) for marker in _SAFE_KEY_MARKERS
        ):
            result[key] = _safe_scalar(value)
        else:
            result[key] = "[REDACTED_FIELD]"
    return result


def safe_error(code: str, exception: BaseException | None = None) -> dict[str, str]:
    """Return an error code only; provider exception text may contain document data."""

    del exception
    return {"error_code": code[:80]}


def redact_untrusted_text(value: str) -> str:
    return _content_marker(value)


def _content_marker(value: Any) -> str:
    encoded = repr(value).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _safe_scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value if not isinstance(value, str) else value[:200]
    return "[REDACTED_COMPLEX_VALUE]"
