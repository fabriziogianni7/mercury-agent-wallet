"""Structured domain errors for Mercury graph and execution results."""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, Field, ValidationError


def _redact_error_message(error: BaseException | str) -> str:
    """Lazy wrapper so `mercury.models` does not import `mercury.service` at import time."""

    from mercury.service.logging import redact_error_message

    return redact_error_message(error)


def _redact_value(value: Any) -> Any:
    from mercury.service.logging import redact_value

    return redact_value(value)


class MercuryErrorInfo(BaseModel):
    """Machine-actionable error payload with sanitized public text."""

    model_config = {"frozen": True}

    code: str
    category: str
    message: str
    retryable: bool = False
    recoverable: bool = True
    user_action: str | None = None
    llm_action: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


def _with_stage(details: dict[str, Any] | None, stage: str | None) -> dict[str, Any]:
    out = dict(details or {})
    if stage is not None:
        out.setdefault("stage", stage)
    return out


def unsupported_intent(
    *,
    message: str | None = None,
    user_action: str | None = "Provide a supported wallet intent in the expected shape.",
    llm_action: str | None = (
        "Ask the user for a supported read-only or structured transaction intent."
    ),
    details: dict[str, Any] | None = None,
    stage: str | None = None,
) -> MercuryErrorInfo:
    text = _redact_error_message(message or "This wallet intent is not supported.")
    return MercuryErrorInfo(
        code="unsupported_intent",
        category="intent",
        message=text,
        retryable=False,
        recoverable=True,
        user_action=user_action,
        llm_action=llm_action,
        details=_with_stage(details, stage),
    )


def validation_failed(
    *,
    message: str,
    user_action: str | None = "Fix the invalid fields and try again.",
    llm_action: str | None = "Inspect validation details, correct the payload, and retry.",
    details: dict[str, Any] | None = None,
    stage: str | None = None,
) -> MercuryErrorInfo:
    return MercuryErrorInfo(
        code="validation_failed",
        category="validation",
        message=_redact_error_message(message),
        retryable=False,
        recoverable=True,
        user_action=user_action,
        llm_action=llm_action,
        details=_with_stage(details, stage),
    )


def missing_chain_config(
    *,
    message: str,
    chain: str | None = None,
    user_action: str | None = "Choose a supported chain name.",
    llm_action: str | None = "Retry with a supported chain; list configured chains if unsure.",
    details: dict[str, Any] | None = None,
    stage: str | None = None,
) -> MercuryErrorInfo:
    d = _with_stage(details, stage)
    if chain is not None:
        d.setdefault("chain", chain)
    return MercuryErrorInfo(
        code="missing_chain_config",
        category="config",
        message=_redact_error_message(message),
        retryable=False,
        recoverable=True,
        user_action=user_action,
        llm_action=llm_action,
        details=d,
    )


def rpc_unavailable(
    *,
    message: str,
    chain: str | None = None,
    user_action: str | None = "Try again later or choose another supported chain.",
    llm_action: str | None = (
        "Retry once with backoff. If it fails again, ask about another supported chain."
    ),
    details: dict[str, Any] | None = None,
    stage: str | None = None,
) -> MercuryErrorInfo:
    d = _with_stage(details, stage)
    if chain is not None:
        d.setdefault("chain", chain)
    return MercuryErrorInfo(
        code="rpc_unavailable",
        category="rpc",
        message=_redact_error_message(message),
        retryable=True,
        recoverable=True,
        user_action=user_action,
        llm_action=llm_action,
        details=d,
    )


def policy_rejected(
    *,
    message: str,
    user_action: str | None = "Adjust the transaction or policy inputs.",
    llm_action: str | None = "Explain the policy outcome and what the user can change.",
    details: dict[str, Any] | None = None,
    stage: str | None = None,
) -> MercuryErrorInfo:
    return MercuryErrorInfo(
        code="policy_rejected",
        category="policy",
        message=_redact_error_message(message),
        retryable=False,
        recoverable=True,
        user_action=user_action,
        llm_action=llm_action,
        details=_with_stage(details, stage),
    )


def idempotency_conflict(
    *,
    message: str = "Duplicate transaction: this idempotency key is already in flight or completed.",
    user_action: str | None = "Use a new idempotency key or wait for the in-flight request.",
    llm_action: str | None = "Do not retry blindly; check idempotency and prior execution state.",
    details: dict[str, Any] | None = None,
    stage: str | None = None,
) -> MercuryErrorInfo:
    return MercuryErrorInfo(
        code="idempotency_conflict",
        category="policy",
        message=_redact_error_message(message),
        retryable=False,
        recoverable=True,
        user_action=user_action,
        llm_action=llm_action,
        details=_with_stage(details, stage),
    )


def approval_required(
    *,
    message: str,
    user_action: str | None = "Approve the transaction in your wallet or approval channel.",
    llm_action: str | None = (
        "Request explicit human approval with clear risk summary before continuing."
    ),
    details: dict[str, Any] | None = None,
    stage: str | None = None,
) -> MercuryErrorInfo:
    return MercuryErrorInfo(
        code="approval_required",
        category="approval",
        message=_redact_error_message(message),
        retryable=True,
        recoverable=True,
        user_action=user_action,
        llm_action=llm_action,
        details=_with_stage(details, stage),
    )


def approval_denied(
    *,
    message: str,
    user_action: str | None = (
        "Approval was not granted; change the request or try again if appropriate."
    ),
    llm_action: str | None = (
        "Report denial and offer to revise amount, recipient, or safety checks."
    ),
    details: dict[str, Any] | None = None,
    stage: str | None = None,
) -> MercuryErrorInfo:
    return MercuryErrorInfo(
        code="approval_denied",
        category="approval",
        message=_redact_error_message(message),
        retryable=False,
        recoverable=True,
        user_action=user_action,
        llm_action=llm_action,
        details=_with_stage(details, stage),
    )


def simulation_failed(
    *,
    message: str,
    user_action: str | None = "Adjust the transaction; simulation indicated it may fail on-chain.",
    llm_action: str | None = "Analyze simulation failure, suggest calldata, gas, or balance fixes.",
    details: dict[str, Any] | None = None,
    stage: str | None = None,
) -> MercuryErrorInfo:
    return MercuryErrorInfo(
        code="simulation_failed",
        category="simulation",
        message=_redact_error_message(message),
        retryable=True,
        recoverable=True,
        user_action=user_action,
        llm_action=llm_action,
        details=_with_stage(details, stage),
    )


def signing_failed(
    *,
    message: str,
    user_action: str | None = "Retry signing with an unlocked key or a valid wallet session.",
    llm_action: str | None = (
        "If signing failed repeatedly, stop and ask the user to verify custody setup."
    ),
    details: dict[str, Any] | None = None,
    stage: str | None = None,
) -> MercuryErrorInfo:
    return MercuryErrorInfo(
        code="signing_failed",
        category="signing",
        message=_redact_error_message(message),
        retryable=True,
        recoverable=True,
        user_action=user_action,
        llm_action=llm_action,
        details=_with_stage(details, stage),
    )


def broadcast_failed(
    *,
    message: str,
    user_action: str | None = "Retry the broadcast; check network and RPC availability.",
    llm_action: str | None = (
        "Retry once; if the error persists, consider gas, nonce, and chain health."
    ),
    details: dict[str, Any] | None = None,
    stage: str | None = None,
) -> MercuryErrorInfo:
    return MercuryErrorInfo(
        code="broadcast_failed",
        category="rpc",
        message=_redact_error_message(message),
        retryable=True,
        recoverable=True,
        user_action=user_action,
        llm_action=llm_action,
        details=_with_stage(details, stage),
    )


def internal_error(
    *,
    message: str,
    user_action: str | None = "Try again; contact support if the problem continues.",
    llm_action: str | None = (
        "Retry once; if it still fails, stop and report an internal error without exposing secrets."
    ),
    details: dict[str, Any] | None = None,
    stage: str | None = None,
    code: str = "internal_error",
) -> MercuryErrorInfo:
    return MercuryErrorInfo(
        code=code,
        category="internal",
        message=_redact_error_message(message),
        retryable=True,
        recoverable=True,
        user_action=user_action,
        llm_action=llm_action,
        details=_with_stage(details, stage),
    )


def validation_failed_from_pydantic(
    exc: ValidationError, *, stage: str | None = None
) -> MercuryErrorInfo:
    """Build a validation error with redacted Pydantic error list in details."""
    err_list = exc.errors()
    first = cast(dict[str, Any], err_list[0] if err_list else {})
    loc = ".".join(str(part) for part in first.get("loc", ()))
    msg = str(first.get("msg", "Validation failed."))
    summary = f"Invalid field '{loc}': {msg}." if loc else _redact_error_message(str(exc))
    return validation_failed(
        message=_redact_error_message(summary),
        details={"errors": _redact_value(exc.errors())},
        stage=stage,
    )


def normalize_exception(
    exc: BaseException | str,
    *,
    stage: str | None = None,
    code: str | None = None,
    default_category: str | None = None,
) -> MercuryErrorInfo:
    """Map an exception or message to MercuryErrorInfo with a redacted message field."""
    if isinstance(exc, MercuryErrorInfo):
        if stage is not None and "stage" not in exc.details:
            return exc.model_copy(update={"details": {**exc.details, "stage": stage}})
        return exc

    if isinstance(exc, ValidationError):
        return validation_failed_from_pydantic(exc, stage=stage)

    if type(exc).__name__ == "UnsupportedIntentError" and type(exc).__module__.endswith(
        "mercury.graph.intents"
    ):
        return unsupported_intent(message=str(exc) or None, stage=stage)

    if type(exc).__name__ == "DuplicateTransactionError" and type(exc).__module__.endswith(
        "mercury.policy.idempotency"
    ):
        return idempotency_conflict(stage=stage)

    if type(exc).__name__ == "UnsupportedChainError" and "mercury.chains" in (
        type(exc).__module__ or ""
    ):
        return missing_chain_config(message=str(exc), stage=stage)

    message = _redact_error_message(exc if isinstance(exc, BaseException) else str(exc))
    if not message:
        message = "Mercury request failed."

    if code == "simulation_failed":
        return simulation_failed(message=message, stage=stage)
    if code == "signing_failed":
        return signing_failed(message=message, stage=stage)
    if code == "broadcast_failed":
        return broadcast_failed(message=message, stage=stage)
    if code == "rpc_unavailable":
        return rpc_unavailable(message=message, stage=stage)
    if code == "policy_rejected":
        return policy_rejected(message=message, stage=stage)
    if code == "internal_error" or default_category == "internal":
        return internal_error(message=message, stage=stage)

    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return rpc_unavailable(message=message, stage=stage)

    if isinstance(exc, ValueError) and "nonce" in str(exc).lower():
        return rpc_unavailable(message=message, stage=stage)
    if isinstance(exc, ValueError) and "chain" in str(exc).lower():
        return missing_chain_config(message=message, stage=stage)

    if code is not None:
        return internal_error(message=message, stage=stage, code=code)

    return internal_error(message=message, stage=stage)


__all__ = [
    "MercuryErrorInfo",
    "approval_denied",
    "approval_required",
    "broadcast_failed",
    "idempotency_conflict",
    "internal_error",
    "missing_chain_config",
    "normalize_exception",
    "policy_rejected",
    "rpc_unavailable",
    "signing_failed",
    "simulation_failed",
    "unsupported_intent",
    "validation_failed",
    "validation_failed_from_pydantic",
]
