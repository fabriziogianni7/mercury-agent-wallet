"""FastAPI application factory and Mercury-native routes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, cast

from fastapi import Depends, FastAPI, Header, Request

from mercury.chains import list_chains
from mercury.config import MercurySettings
from mercury.graph.runtime import GraphRuntime
from mercury.graph.state import MercuryState
from mercury.models.approval import ApprovalStatus
from mercury.models.chain import ChainConfig
from mercury.models.errors import MercuryErrorInfo
from mercury.models.execution import ExecutionResult
from mercury.service.dependencies import get_graph_runtime
from mercury.service.errors import GraphInvocationError, install_exception_handlers
from mercury.service.logging import log_service_event, redact_error_message, redact_value
from mercury.service.models import (
    HealthResponse,
    MercuryError,
    MercuryInvokeRequest,
    MercuryInvokeResponse,
    ReadinessResponse,
)
from mercury.service.pan_agentikit_handler import handle_agent_envelope
from mercury.service.pan_agentikit_models import PanAgentEnvelope


def _mercury_error_from_info(info: MercuryErrorInfo) -> MercuryError:
    """Map domain error info to API `MercuryError` with redacted text and details."""

    dumped = info.model_dump(mode="json")
    safe = redact_value(dumped)
    if not isinstance(safe, dict):
        safe = {}
    message = redact_error_message(str(safe.get("message", "")))
    raw_details = safe.get("details")
    if isinstance(raw_details, dict):
        details = cast(dict[str, Any], redact_value(raw_details))
    else:
        details = {}
    ua = safe.get("user_action")
    la = safe.get("llm_action")
    return MercuryError(
        code=str(safe.get("code", "internal_error")),
        category=str(safe.get("category", "internal")),
        message=message,
        retryable=bool(safe.get("retryable", False)),
        recoverable=bool(safe.get("recoverable", True)),
        user_action=redact_error_message(ua) if isinstance(ua, str) else None,
        llm_action=redact_error_message(la) if isinstance(la, str) else None,
        details=details,
    )


def create_app(
    *,
    settings: MercurySettings | None = None,
    runtime: GraphRuntime | None = None,
) -> FastAPI:
    """Create the Mercury FastAPI app without touching external services."""

    effective_settings = settings or MercurySettings()
    app = FastAPI(title=effective_settings.app_name)
    app.state.settings = effective_settings
    if runtime is not None:
        app.state.graph_runtime = runtime

    install_exception_handlers(app)

    @app.get("/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return HealthResponse(status="ok", service=effective_settings.app_name)

    @app.get("/readyz", response_model=ReadinessResponse)
    def readyz() -> ReadinessResponse:
        chains = list_chains()
        supported = [chain.name for chain in chains]
        return ReadinessResponse(
            status="ready",
            service=effective_settings.app_name,
            default_chain=effective_settings.default_chain,
            supported_chains=supported,
        )

    @app.post("/v1/mercury/invoke", response_model=MercuryInvokeResponse)
    def invoke_mercury(
        request: Request,
        payload: MercuryInvokeRequest,
        graph_runtime: Annotated[GraphRuntime, Depends(get_graph_runtime)],
        x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> MercuryInvokeResponse:
        request_id = payload.effective_request_id(x_request_id)
        effective_idempotency_key = payload.effective_idempotency_key(idempotency_key)
        request.state.request_id = request_id
        state = _state_from_request(
            payload,
            request_id=request_id,
            idempotency_key=effective_idempotency_key,
        )
        log_service_event(
            "invoke_request",
            request_id=request_id,
            user_id=payload.user_id,
            wallet_id=payload.wallet_id,
            chain=payload.chain,
            idempotency_key=effective_idempotency_key,
        )
        try:
            result = graph_runtime.invoke(state)
        except Exception as exc:
            raise GraphInvocationError(redact_error_message(exc)) from exc

        response = _response_from_state(
            result,
            request_id=request_id,
            fallback_chain=payload.chain,
        )
        log_service_event(
            "invoke_response",
            request_id=request_id,
            status=response.status,
            chain=response.chain,
            tx_hash=response.tx_hash,
            approval_required=response.approval_required,
        )
        return response

    @app.post("/v1/agent", response_model=PanAgentEnvelope)
    def invoke_agent(
        request: Request,
        envelope: PanAgentEnvelope,
        graph_runtime: Annotated[GraphRuntime, Depends(get_graph_runtime)],
        x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> PanAgentEnvelope:
        request_id = envelope.trace_id or x_request_id or envelope.id
        request.state.request_id = request_id
        log_service_event(
            "agent_envelope_request",
            request_id=request_id,
            trace_id=envelope.trace_id,
            turn_id=envelope.turn_id,
            from_role=envelope.from_role,
            to_role=envelope.to_role,
            payload_kind=envelope.payload_kind,
            idempotency_key=idempotency_key or envelope.metadata.get("idempotency_key"),
        )
        response = handle_agent_envelope(
            envelope,
            graph_runtime=graph_runtime,
            request_id=x_request_id,
            idempotency_key=idempotency_key,
        )
        log_service_event(
            "agent_envelope_response",
            request_id=request_id,
            payload_kind=response.payload_kind,
            error=response.error,
        )
        return response

    return app


def _state_from_request(
    payload: MercuryInvokeRequest,
    *,
    request_id: str,
    idempotency_key: str | None,
) -> MercuryState:
    raw_input = _intent_with_boundary_fields(payload, idempotency_key=idempotency_key)
    state: MercuryState = {
        "request_id": request_id,
        "raw_input": raw_input,
    }
    return state


def _intent_with_boundary_fields(
    payload: MercuryInvokeRequest,
    *,
    idempotency_key: str | None,
) -> dict[str, Any] | str:
    if not isinstance(payload.intent, dict):
        return payload.intent

    intent = dict(payload.intent)
    if payload.chain is not None:
        intent.setdefault("chain", payload.chain)
    intent.setdefault("wallet_id", payload.wallet_id)
    if idempotency_key is not None:
        intent.setdefault("idempotency_key", idempotency_key)

    metadata = dict(payload.metadata)
    metadata["user_id"] = payload.user_id
    if payload.approval_response is not None:
        metadata["approval_response"] = payload.approval_response
    if metadata:
        intent.setdefault("metadata", metadata)
    return intent


def _response_from_state(
    state: MercuryState,
    *,
    request_id: str,
    fallback_chain: str | None,
) -> MercuryInvokeResponse:
    safe_state = redact_value(_jsonable(state))
    if not isinstance(safe_state, dict):
        safe_state = {}

    execution = _execution_result(state)
    approval = _mapping(state.get("approval_result"))
    error = _state_error(state)
    chain = _chain_name(state, fallback_chain)

    if execution is not None:
        execution_payload = redact_value(execution.model_dump(mode="json"))
        status = str(execution.status.value)
        approval_required = _approval_required(approval)
        if approval_required:
            status = "approval_required"
        if execution.error is not None:
            message = redact_error_message(execution.error.message)
        else:
            message = _message_for_status(status)
        return MercuryInvokeResponse(
            request_id=request_id,
            status=status,
            chain=execution.chain,
            message=message,
            data={"execution_result": execution_payload},
            tx_hash=execution.tx_hash,
            receipt=_receipt_payload(execution),
            approval_required=approval_required,
            approval_payload=redact_value(approval) if approval_required else None,
            error=_mercury_error_from_info(execution.error) if execution.error else None,
        )

    if error is not None:
        mercury_err = _mercury_error_from_info(error)
        message = mercury_err.message
        return MercuryInvokeResponse(
            request_id=request_id,
            status="failed",
            chain=chain,
            message=message,
            data=safe_state,
            error=mercury_err,
        )

    message = _response_message(state)
    return MercuryInvokeResponse(
        request_id=request_id,
        status="succeeded",
        chain=chain,
        message=message,
        data=safe_state,
        tx_hash=_string_or_none(state.get("tx_hash")),
        approval_required=_approval_required(approval),
        approval_payload=redact_value(approval) if _approval_required(approval) else None,
    )


def _execution_result(state: MercuryState) -> ExecutionResult | None:
    execution = state.get("execution_result")
    if isinstance(execution, ExecutionResult):
        return execution
    if isinstance(execution, Mapping):
        return ExecutionResult.model_validate(execution)
    return None


def _receipt_payload(execution: ExecutionResult) -> dict[str, Any] | None:
    if execution.tx_hash is None:
        return None
    payload: dict[str, Any] = {
        "tx_hash": execution.tx_hash,
        "status": execution.status.value,
    }
    if execution.block_number is not None:
        payload["block_number"] = execution.block_number
    if execution.gas_used is not None:
        payload["gas_used"] = execution.gas_used
    return payload


def _approval_required(approval: dict[str, Any] | None) -> bool:
    if approval is None:
        return False
    status = approval.get("status")
    if isinstance(status, ApprovalStatus):
        return status == ApprovalStatus.REQUIRED
    return str(status) == ApprovalStatus.REQUIRED.value


def _state_error(state: MercuryState) -> MercuryErrorInfo | None:
    err = state.get("error")
    return err if isinstance(err, MercuryErrorInfo) else None


def _response_message(state: MercuryState) -> str:
    response_text = state.get("response_text")
    if isinstance(response_text, str) and response_text:
        return str(redact_value(response_text))
    return "Mercury request completed."


def _message_for_status(status: str) -> str:
    if status == "approval_required":
        return "Human approval is required before execution."
    return f"Mercury request {status}."


def _chain_name(state: MercuryState, fallback_chain: str | None) -> str | None:
    chain_name = state.get("chain_name")
    if isinstance(chain_name, str):
        return chain_name
    chain_config = state.get("chain_config")
    if isinstance(chain_config, ChainConfig):
        name = chain_config.name
        return name if isinstance(name, str) else fallback_chain
    return fallback_chain


def _mapping(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else None
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _jsonable(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    return value


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


app = create_app()
