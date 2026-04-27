from fastapi.testclient import TestClient
from mercury.graph.state import MercuryState
from mercury.models import ExecutionResult, ExecutionStatus
from mercury.models.approval import ApprovalResult, ApprovalStatus
from mercury.service import create_app
from tests.fixtures.pan_agentikit_envelopes import envelope_fixture


def test_agent_route_accepts_user_message_envelope() -> None:
    runtime = CapturingRuntime(
        {
            "chain_name": "base",
            "response_text": "0x000000000000000000000000000000000000dEaD has 1 ETH.",
            "tool_result": {"balance": "1"},
        }
    )
    client = TestClient(create_app(runtime=runtime))

    response = client.post("/v1/agent", json=envelope_fixture("user_message"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["trace_id"] == "trace-user-1"
    assert payload["turn_id"] == "turn-1"
    assert payload["parent_step_id"] == "step-user-1"
    assert payload["from_role"] == "mercury"
    assert payload["to_role"] == "coordinator"
    assert payload["payload"]["kind"] == "agent_reply"
    assert payload["payload"]["text"].endswith("has 1 ETH.")
    assert payload["payload"]["content"].endswith("has 1 ETH.")
    assert runtime.invocations[0]["request_id"] == "trace-user-1"
    assert runtime.invocations[0]["raw_input"] == "What is my native balance?"


def test_agent_route_maps_task_result_envelope() -> None:
    runtime = CapturingRuntime(
        {
            "chain_name": "base",
            "response_text": "0x000000000000000000000000000000000000dEaD has 1 ETH.",
            "tool_result": {"balance": "1"},
        }
    )
    client = TestClient(create_app(runtime=runtime))

    response = client.post("/v1/agent", json=envelope_fixture("task_request"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["payload"]["kind"] == "task_result"
    assert payload["payload"]["text"].endswith("has 1 ETH.")
    assert payload["payload"]["task_id"] == "task-read-1"
    assert payload["payload"]["status"] == "succeeded"
    assert payload["payload"]["result"]["chain"] == "base"
    assert runtime.invocations[0]["raw_input"]["metadata"]["trace_id"] == "trace-task-1"


def test_agent_route_maps_approval_required_envelope() -> None:
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
    client = TestClient(create_app(runtime=runtime))

    response = client.post("/v1/agent", json=envelope_fixture("approval_task"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["payload"]["kind"] == "wallet_approval_required"
    assert payload["payload"]["status"] == "approval_required"
    assert payload["payload"]["approval"]["status"] == "required"
    assert payload["payload"]["idempotency_key"] == "idem-transfer-1"


def test_agent_route_returns_error_envelope_for_graph_exception() -> None:
    runtime = RaisingRuntime(RuntimeError("boom https://rpc.example.invalid bearer=secret-token"))
    client = TestClient(create_app(runtime=runtime), raise_server_exceptions=False)

    response = client.post("/v1/agent", json=envelope_fixture("task_request"))

    assert response.status_code == 200
    text = response.text
    assert "https://rpc.example.invalid" not in text
    assert "secret-token" not in text
    payload = response.json()
    assert payload["payload"]["kind"] == "agent_error"
    assert payload["payload"]["code"] == "graph_invocation_failed"
    assert payload["error"]["message"] == "boom <redacted> <redacted>"


class CapturingRuntime:
    def __init__(self, result: MercuryState) -> None:
        self._result = result
        self.invocations: list[MercuryState] = []

    def invoke(self, state: MercuryState) -> MercuryState:
        self.invocations.append(state)
        return self._result


class RaisingRuntime:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def invoke(self, state: MercuryState) -> MercuryState:
        raise self._error
