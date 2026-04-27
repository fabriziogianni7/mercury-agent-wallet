from mercury.graph.state import MercuryState
from mercury.models import ExecutionResult, ExecutionStatus
from mercury.models.approval import ApprovalResult, ApprovalStatus
from mercury.service.pan_agentikit_handler import (
    handle_agent_envelope,
    mercury_request_from_envelope,
)
from mercury.service.pan_agentikit_models import PanAgentEnvelope

from tests.fixtures.pan_agentikit_envelopes import envelope_fixture


def test_user_message_maps_to_native_mercury_request_with_metadata() -> None:
    envelope = PanAgentEnvelope.model_validate(envelope_fixture("user_message"))

    request = mercury_request_from_envelope(envelope)

    assert request.request_id == "trace-user-1"
    assert request.user_id == "user-1"
    assert request.wallet_id == "primary"
    assert request.intent == "What is my native balance?"
    assert request.chain == "base"
    assert request.idempotency_key == "idem-user-1"
    assert request.metadata["trace_id"] == "trace-user-1"
    assert request.metadata["turn_id"] == "turn-1"
    assert request.metadata["step_id"] == "step-user-1"
    assert request.metadata["from_role"] == "coordinator"
    assert request.metadata["artifacts"] == [{"kind": "note", "uri": "artifact://request"}]


def test_task_request_maps_structured_wallet_task_to_native_request() -> None:
    envelope = PanAgentEnvelope.model_validate(envelope_fixture("task_request"))

    request = mercury_request_from_envelope(envelope)

    assert request.request_id == "trace-task-1"
    assert request.intent == {
        "kind": "native_balance",
        "wallet_address": "0x000000000000000000000000000000000000dEaD",
    }
    assert request.chain == "base"
    assert request.metadata["task_id"] == "task-read-1"
    assert request.metadata["parent_step_id"] == "step-parent-1"


def test_value_moving_task_requires_idempotency_key() -> None:
    data = envelope_fixture("approval_task")
    data["payload"].pop("idempotency_key")
    envelope = PanAgentEnvelope.model_validate(data)

    response = handle_agent_envelope(envelope, graph_runtime=CapturingRuntime({}))

    assert response.payload["kind"] == "agent_error"
    assert response.payload["code"] == "missing_idempotency_key"
    assert response.error is not None
    assert response.trace_id == "trace-approval-1"


def test_unsupported_payload_returns_error_envelope_without_invoking_runtime() -> None:
    runtime = CapturingRuntime({})
    envelope = PanAgentEnvelope.model_validate(envelope_fixture("unsupported"))

    response = handle_agent_envelope(envelope, graph_runtime=runtime)

    assert runtime.invocations == []
    assert response.payload["kind"] == "agent_error"
    assert response.payload["code"] == "unsupported_payload"
    assert response.trace_id == "trace-unsupported-1"
    assert response.parent_step_id == "step-unsupported-1"
    assert response.from_role == "mercury"
    assert response.to_role == "coordinator"


def test_approval_required_result_maps_to_wallet_approval_payload() -> None:
    execution = ExecutionResult(
        chain="base",
        chain_id=8453,
        wallet_id="primary",
        status=ExecutionStatus.APPROVAL_DENIED,
        error="Human approval is required before signing idem-transfer-1.",
    )
    approval = ApprovalResult(
        status=ApprovalStatus.REQUIRED,
        reason="Human approval is required before signing idem-transfer-1.",
    )
    runtime = CapturingRuntime({"execution_result": execution, "approval_result": approval})
    envelope = PanAgentEnvelope.model_validate(envelope_fixture("approval_task"))

    response = handle_agent_envelope(envelope, graph_runtime=runtime)

    assert response.payload["kind"] == "wallet_approval_required"
    assert response.payload["task_id"] == "task-transfer-1"
    assert response.payload["idempotency_key"] == "idem-transfer-1"
    assert response.payload["approval"]["status"] == "required"
    assert response.metadata["idempotency_key"] == "idem-transfer-1"
    assert runtime.invocations[0]["raw_input"]["idempotency_key"] == "idem-transfer-1"
    assert runtime.invocations[0]["raw_input"]["metadata"]["trace_id"] == "trace-approval-1"


def test_graph_state_error_maps_to_sanitized_error_envelope() -> None:
    runtime = CapturingRuntime(
        {
            "chain_name": "base",
            "error": (
                "failed using https://rpc.example.invalid and mercury/wallets/primary/private_key"
            ),
        }
    )
    envelope = PanAgentEnvelope.model_validate(envelope_fixture("task_request"))

    response = handle_agent_envelope(envelope, graph_runtime=runtime)

    assert response.payload["kind"] == "agent_error"
    assert response.error is not None
    assert "https://rpc.example.invalid" not in response.error["message"]
    assert "mercury/wallets/primary/private_key" not in response.error["message"]
    assert "<redacted>" in response.error["message"]


class CapturingRuntime:
    def __init__(self, result: MercuryState) -> None:
        self._result = result
        self.invocations: list[MercuryState] = []

    def invoke(self, state: MercuryState) -> MercuryState:
        self.invocations.append(state)
        return self._result
