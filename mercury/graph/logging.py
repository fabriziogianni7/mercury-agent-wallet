"""Structured logging for Mercury LangGraph execution (pairs with mercury.service.logging)."""

from __future__ import annotations

import json
import logging
from typing import Any


def get_graph_logger() -> logging.Logger:
    """Logger for LangGraph orchestration (`mercury.graph`)."""

    return logging.getLogger("mercury.graph")


def log_graph_event(
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """Emit a single structured JSON line from the graph logger (redacted)."""

    from mercury.service.logging import redact_value

    payload = {"event": event, **redact_value(fields)}
    get_graph_logger().log(level, json.dumps(payload, sort_keys=True, default=str))
