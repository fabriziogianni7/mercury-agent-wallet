"""Helpers to preserve HTTP intent metadata on prepared transactions."""

from __future__ import annotations

from typing import Any

from mercury.models.execution import PreparedTransaction


def merge_intent_metadata_into_prepared(
    prepared: PreparedTransaction,
    intent_payload: dict[str, Any],
) -> PreparedTransaction:
    """Merge ``intent_payload[\"metadata\"]`` into the prepared transaction metadata.

    Service requests attach ``user_id``, ``approval_response``, etc. under intent
    metadata so downstream nodes (e.g. approval) can read them.
    """

    raw = intent_payload.get("metadata")
    if not isinstance(raw, dict) or not raw:
        return prepared
    merged: dict[str, Any] = {**dict(prepared.metadata), **raw}
    return prepared.model_copy(update={"metadata": merged})
