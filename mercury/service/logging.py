"""Structured logging helpers with service-boundary redaction."""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Mapping, Sequence
from typing import Any

REDACTION = "<redacted>"

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "credential",
    "private_key",
    "raw_transaction",
    "rpc_url",
    "secret",
    "signature",
    "token",
)
_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")
_SECRET_PATH_PATTERN = re.compile(r"\bmercury/(?:rpc|apis|wallets)/[A-Za-z0-9_./-]+\b")
_ONECLAW_TOKEN_PATTERN = re.compile(r"(?i)\b(?:oneclaw|1claw|api[_-]?key|bearer)\s*[:=]\s*\S+")
_LONG_HEX_PATTERN = re.compile(r"\b0x[a-fA-F0-9]{96,}\b")


def get_service_logger() -> logging.Logger:
    """Return Mercury's service logger."""

    return logging.getLogger("mercury.service")


def configure_service_logging(*, level: int = logging.INFO) -> None:
    """Ensure application loggers emit when the host only configures its own loggers.

    Uvicorn's default ``LOGGING_CONFIG`` attaches handlers only to ``uvicorn.*`` loggers.
    The root logger is left without handlers at WARNING, so INFO records from
    ``mercury.service`` (and anything else that propagates to root) are discarded.
    """

    root = logging.getLogger()
    if root.handlers:
        if root.level > level:
            root.setLevel(level)
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)


def redact_value(value: Any) -> Any:
    """Recursively redact values that should not cross HTTP or log boundaries."""

    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                redacted[key_text] = REDACTION
            else:
                redacted[key_text] = redact_value(item)
        return redacted
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [redact_value(item) for item in value]
    return value


def redact_error_message(error: BaseException | str) -> str:
    """Return a sanitized error message for public responses."""

    message = str(error) or "Mercury request failed."
    return str(redact_value(message))


def log_service_event(
    event: str,
    *,
    level: int = logging.INFO,
    logger: logging.Logger | None = None,
    **fields: Any,
) -> None:
    """Emit a single structured log line with sensitive fields redacted."""

    target = logger or get_service_logger()
    payload = {"event": event, **redact_value(fields)}
    target.log(level, json.dumps(payload, sort_keys=True, default=str))


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _redact_text(text: str) -> str:
    redacted = text
    for pattern in (_URL_PATTERN, _SECRET_PATH_PATTERN, _ONECLAW_TOKEN_PATTERN, _LONG_HEX_PATTERN):
        redacted = pattern.sub(REDACTION, redacted)
    return redacted
