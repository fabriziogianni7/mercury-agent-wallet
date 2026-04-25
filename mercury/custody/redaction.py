"""Helpers for keeping custody secrets out of public strings."""

from __future__ import annotations

import re

REDACTION = "<redacted>"

_HEX_PRIVATE_KEY_PATTERN = re.compile(r"\b(?:0x)?[a-fA-F0-9]{64}\b")
_WALLET_PRIVATE_KEY_PATH_PATTERN = re.compile(
    r"\bmercury/wallets/[A-Za-z0-9_.-]+/private_key\b"
)
_ONECLAW_TOKEN_PATTERN = re.compile(
    r"(?i)\b(?:oneclaw|1claw|api[_-]?key|bearer)\s*[:=]\s*\S+"
)


def redact_secret_text(text: object) -> str:
    """Return text with likely private key material and wallet secret paths removed."""

    redacted = str(text)
    for pattern in (
        _HEX_PRIVATE_KEY_PATTERN,
        _WALLET_PRIVATE_KEY_PATH_PATTERN,
        _ONECLAW_TOKEN_PATTERN,
    ):
        redacted = pattern.sub(REDACTION, redacted)
    return redacted


def secret_text_leaked(text: object, secret_values: list[str] | tuple[str, ...]) -> bool:
    """Check whether any exact secret value appears in a public string."""

    haystack = str(text)
    return any(secret for secret in secret_values if secret and secret in haystack)
