from fastapi.testclient import TestClient
from mercury.graph.state import MercuryState
from mercury.models import ExecutionResult, ExecutionStatus
from mercury.models.approval import ApprovalResult, ApprovalStatus
from mercury.models.errors import approval_required
from mercury.service import create_app


def test_invoke_propagates_request_id_and_idempotency_key_to_runtime() -> None:
    runtime = CapturingRuntime(
        {
            "chain_name": "base",
            "response_text": "0x000000000000000000000000000000000000dEaD has 1 ETH.",
            "tool_result": {"balance": "1"},
        }
    )
    client = TestClient(create_app(runtime=runtime))

    response = client.post(
        "/v1/mercury/invoke",
        headers={"X-Request-ID": "req-header", "Idempotency-Key": "idem-header"},
        json={
            "user_id": "user-1",
            "wallet_id": "primary",
            "intent": {
                "kind": "native_balance",
                "wallet_address": "0x000000000000000000000000000000000000dEaD",
            },
            "chain": "base",
        },
    )

    assert response.status_code == 200
    assert runtime.invocations == [
        {
            "request_id": "req-header",
            "raw_input": {
                "kind": "native_balance",
                "wallet_address": "0x000000000000000000000000000000000000dEaD",
                "chain": "base",
                "wallet_id": "primary",
                "idempotency_key": "idem-header",
                "metadata": {"user_id": "user-1"},
            },
        }
    ]
    payload = response.json()
    assert payload["request_id"] == "req-header"
    assert payload["status"] == "succeeded"
    assert payload["chain"] == "base"


def test_invoke_maps_approval_required_graph_result() -> None:
    execution = ExecutionResult(
        chain="base",
        chain_id=8453,
        wallet_id="primary",
        status=ExecutionStatus.APPROVAL_DENIED,
        error=approval_required(
            message="Human approval is required before signing idem-1.",
        ),
    )
    approval = ApprovalResult(
        status=ApprovalStatus.REQUIRED,
        reason="Human approval is required before signing idem-1.",
    )
    runtime = CapturingRuntime({"execution_result": execution, "approval_result": approval})
    client = TestClient(create_app(runtime=runtime))

    response = client.post(
        "/v1/mercury/invoke",
        json={
            "request_id": "req-approval",
            "user_id": "user-1",
            "wallet_id": "primary",
            "idempotency_key": "idem-1",
            "intent": {"kind": "erc20_transfer", "chain": "base"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "approval_required"
    assert payload["approval_required"] is True
    assert payload["approval_payload"]["status"] == "required"
    err = payload["error"]
    assert err["message"] == "Human approval is required before signing idem-1."
    assert err["code"] == "approval_required"
    assert err["category"] == "approval"
    assert err["retryable"] is True
    assert err["recoverable"] is True
    assert err["user_action"]
    assert err["llm_action"]


def test_invoke_maps_transaction_success_result() -> None:
    execution = ExecutionResult(
        chain="base",
        chain_id=8453,
        wallet_id="primary",
        wallet_address="0x000000000000000000000000000000000000bEEF",
        tx_hash="0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        status=ExecutionStatus.CONFIRMED,
        block_number=123,
        gas_used=21_000,
    )
    runtime = CapturingRuntime({"execution_result": execution})
    client = TestClient(create_app(runtime=runtime))

    response = client.post(
        "/v1/mercury/invoke",
        json={
            "request_id": "req-tx",
            "user_id": "user-1",
            "wallet_id": "primary",
            "intent": {"kind": "erc20_transfer", "chain": "base"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "confirmed"
    assert payload["tx_hash"] == execution.tx_hash
    assert payload["receipt"] == {
        "tx_hash": execution.tx_hash,
        "status": "confirmed",
        "block_number": 123,
        "gas_used": 21000,
    }


class CapturingRuntime:
    def __init__(self, result: MercuryState) -> None:
        self._result = result
        self.invocations: list[MercuryState] = []

    def invoke(self, state: MercuryState) -> MercuryState:
        self.invocations.append(state)
        return self._result
