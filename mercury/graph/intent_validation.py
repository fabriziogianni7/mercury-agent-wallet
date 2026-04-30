"""Upfront validation and normalization for Mercury invoke intents."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from pydantic import ValidationError

from mercury.graph.intents import (
    _KIND_ALIASES,
    UnsupportedIntent,
    UnsupportedIntentError,
    parse_readonly_intent,
)
from mercury.graph.state import MercuryState
from mercury.models.erc20 import ERC20ApprovalIntent, ERC20TransferIntent
from mercury.models.errors import (
    MercuryErrorInfo,
    normalize_exception,
    unsupported_intent,
    validation_failed,
    validation_failed_from_pydantic,
)
from mercury.models.native_tx import NativeTransferIntent
from mercury.models.swaps import SwapIntent

_STAGE = "validate_invoke_intent"

_VALUE_MOVING_KINDS: frozenset[str] = frozenset(
    {"erc20_transfer", "erc20_approval", "native_transfer", "swap"}
)

_VALUE_MOVING_MODEL: dict[str, type[Any]] = {
    "erc20_transfer": ERC20TransferIntent,
    "erc20_approval": ERC20ApprovalIntent,
    "native_transfer": NativeTransferIntent,
    "swap": SwapIntent,
}


def unwrap_intent_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Return nested ``intent`` dict when present; otherwise ``raw``.

    Matches :func:`mercury.graph.intents._unwrap_payload` semantics so routing
    agrees with :func:`mercury.graph.intents.parse_readonly_intent`.
    """

    intent = raw.get("intent")
    if isinstance(intent, dict):
        return intent
    return raw


def merge_canonical_into_raw_input(
    raw_input: dict[str, Any],
    canonical: dict[str, Any],
) -> dict[str, Any]:
    """Merge validated intent fields into ``raw_input``, preserving boundary-only keys."""

    out = dict(raw_input)
    if isinstance(raw_input.get("intent"), dict):
        out["intent"] = dict(canonical)
    else:
        out.update(canonical)
    return out


def merged_invoke_validation_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Nested ``intent`` plus top-level boundary fields (chain, wallet_id, metadata, etc.).

    Aligns with the merged dict shape produced by
    :func:`mercury.service.api._intent_with_boundary_fields` while still accepting
    a nested ``intent`` wrapper from other callers.
    """

    inner = unwrap_intent_payload(raw)
    merged = dict(inner)
    if inner is not raw:
        for key in ("wallet_id", "chain", "idempotency_key"):
            if key in raw:
                merged.setdefault(key, raw[key])
        if "metadata" in raw:
            merged.setdefault("metadata", raw["metadata"])
    return merged


def validate_invoke_intent(
    state: MercuryState | Mapping[str, Any],
) -> tuple[MercuryState | None, MercuryErrorInfo | None]:
    """Validate invoke intent input and normalize ``raw_input``.

    Parameters
    ----------
    state:
        Either a :class:`~mercury.graph.state.MercuryState` mapping (uses
        ``raw_input``) or the merged intent dict itself (same surface as
        :func:`mercury.service.api._intent_with_boundary_fields`).

    Returns
    -------
    tuple
        ``(updated_state, None)`` on success with canonical intent fields merged
        back into ``raw_input``, or ``(None, error)`` with structured
        :class:`~mercury.models.errors.MercuryErrorInfo`.
    """

    raw = _extract_raw_blob(state)

    if isinstance(raw, str):
        return None, unsupported_intent(
            message=(
                "String intents cannot be validated for invoke; "
                "provide a structured JSON object with a ``kind`` field."
            ),
            stage=_STAGE,
            details={"remediation": "Replace text intents with a structured intent payload."},
        )

    if not isinstance(raw, dict):
        return None, validation_failed(
            message="Invoke intent must be a JSON object.",
            stage=_STAGE,
        )

    kind_payload = unwrap_intent_payload(raw)
    raw_kind = kind_payload.get("kind", kind_payload.get("type", kind_payload.get("intent")))
    if not isinstance(raw_kind, str):
        return None, validation_failed(
            message="Structured intents must include a string ``kind`` field.",
            stage=_STAGE,
        )

    kind_lower = raw_kind.strip().lower()
    merged = merged_invoke_validation_payload(raw)

    if kind_lower in _VALUE_MOVING_KINDS:
        model_cls = _VALUE_MOVING_MODEL[kind_lower]
        try:
            validated = model_cls.model_validate(merged)
        except ValidationError as exc:
            return None, _validation_failed_from_pydantic_invoke(exc)

        canonical = validated.model_dump(mode="json")
        new_raw = merge_canonical_into_raw_input(raw, canonical)
        return _success_state(state, new_raw), None

    if kind_lower in _KIND_ALIASES:
        try:
            parsed = parse_readonly_intent(merged, None)
        except UnsupportedIntentError as exc:
            return None, normalize_exception(exc, stage=_STAGE)

        if isinstance(parsed, UnsupportedIntent):
            return None, unsupported_intent(message=parsed.reason, stage=_STAGE)

        canonical = parsed.model_dump(mode="json")
        new_raw = merge_canonical_into_raw_input(raw, canonical)
        return _success_state(state, new_raw), None

    return None, unsupported_intent(
        message=f"Unsupported wallet intent: {raw_kind}.",
        stage=_STAGE,
    )


def _extract_raw_blob(state: MercuryState | Mapping[str, Any]) -> Any:
    if isinstance(state, Mapping) and "raw_input" in state:
        return state["raw_input"]
    return state


def _validation_failed_from_pydantic_invoke(exc: ValidationError) -> MercuryErrorInfo:
    info = validation_failed_from_pydantic(exc, stage=_STAGE)
    remediation = (
        "Compare your payload with the required fields for this intent kind "
        "(addresses, amounts, chain, wallet_id, and idempotency_key where applicable)."
    )
    return info.model_copy(update={"details": {**info.details, "remediation": remediation}})


def _success_state(
    state: MercuryState | Mapping[str, Any],
    merged_raw: dict[str, Any],
) -> MercuryState:
    if isinstance(state, Mapping) and "raw_input" in state:
        out = dict(cast(dict[str, Any], state))
        out["raw_input"] = merged_raw
        return cast(MercuryState, out)
    return cast(MercuryState, {"raw_input": merged_raw})


__all__ = [
    "merge_canonical_into_raw_input",
    "merged_invoke_validation_payload",
    "unwrap_intent_payload",
    "validate_invoke_intent",
]
