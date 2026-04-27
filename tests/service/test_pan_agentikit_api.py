from __future__ import annotations

from fastapi.testclient import TestClient
from mercury.graph.state import MercuryState
from mercury.service import create_app

from tests.fixtures.pan_agentikit_envelopes import envelope_fixture


def test_pan_agentikit_api_accepts_user_message_and_task_request_envelopes() -> None:
    runtime = CapturingRuntime(
        {
            "chain_name": "base",
            "response_text": "0x000000000000000000000000000000000000dEaD has 1 ETH.",
            "tool_result": {"balance": "1"},
        }
    )
    client = TestClient(create_app(runtime=runtime))

    user_response = client.post("/v1/agent", json=envelope_fixture("user_message"))
    task_response = client.post("/v1/agent", json=envelope_fixture("task_request"))

    assert user_response.status_code == 200
    assert user_response.json()["payload"]["kind"] == "agent_reply"
    assert task_response.status_code == 200
    assert task_response.json()["payload"]["kind"] == "task_result"
    assert runtime.invocations[0]["request_id"] == "trace-user-1"
    assert runtime.invocations[1]["request_id"] == "trace-task-1"
    assert runtime.invocations[1]["raw_input"]["metadata"]["trace_id"] == "trace-task-1"


def test_pan_agentikit_api_rejects_value_moving_task_without_idempotency() -> None:
    envelope = envelope_fixture("approval_task")
    envelope["payload"].pop("idempotency_key")
    runtime = CapturingRuntime({})
    client = TestClient(create_app(runtime=runtime))

    response = client.post("/v1/agent", json=envelope)

    assert response.status_code == 200
    payload = response.json()
    assert payload["payload"]["kind"] == "agent_error"
    assert payload["payload"]["code"] == "missing_idempotency_key"
    assert runtime.invocations == []


def test_pan_agentikit_api_sanitizes_unsupported_payload_errors() -> None:
    envelope = envelope_fixture("unsupported")
    envelope["metadata"] = {"api_key": "secret-api-key", "debug": "https://rpc.example.invalid"}
    client = TestClient(create_app(runtime=CapturingRuntime({})))

    response = client.post("/v1/agent", json=envelope)

    assert response.status_code == 200
    assert "https://rpc.example.invalid" not in response.text
    assert "secret-api-key" not in response.text
    payload = response.json()
    assert payload["payload"]["kind"] == "agent_error"
    assert payload["payload"]["code"] == "unsupported_payload"


class CapturingRuntime:
    def __init__(self, result: MercuryState) -> None:
        self._result = result
        self.invocations: list[MercuryState] = []

    def invoke(self, state: MercuryState) -> MercuryState:
        self.invocations.append(state)
        return self._result
