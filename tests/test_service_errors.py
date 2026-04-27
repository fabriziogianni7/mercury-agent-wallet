from fastapi.testclient import TestClient
from mercury.graph.state import MercuryState
from mercury.service import create_app


def test_invoke_validation_error_rejects_malformed_wallet_id() -> None:
    runtime = RaisingRuntime(RuntimeError("should not be called"))
    client = TestClient(create_app(runtime=runtime), raise_server_exceptions=False)

    response = client.post(
        "/v1/mercury/invoke",
        json={
            "request_id": "req-validation",
            "user_id": "user-1",
            "wallet_id": "../primary",
            "intent": {"kind": "native_balance"},
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["message"] == "Request validation failed."
    assert runtime.called is False


def test_invoke_redacts_secret_like_graph_state_errors() -> None:
    runtime = StaticRuntime(
        {
            "chain_name": "ethereum",
            "error": (
                "failed using https://rpc.example.invalid and mercury/wallets/primary/private_key"
            ),
        }
    )
    client = TestClient(create_app(runtime=runtime))

    response = client.post(
        "/v1/mercury/invoke",
        json={
            "request_id": "req-redact",
            "user_id": "user-1",
            "wallet_id": "primary",
            "intent": {"kind": "native_balance"},
        },
    )

    assert response.status_code == 200
    text = response.text
    assert "https://rpc.example.invalid" not in text
    assert "mercury/wallets/primary/private_key" not in text
    assert "<redacted>" in text


def test_invoke_graph_exception_maps_to_sanitized_error() -> None:
    runtime = RaisingRuntime(RuntimeError("boom https://rpc.example.invalid bearer=secret-token"))
    client = TestClient(create_app(runtime=runtime), raise_server_exceptions=False)

    response = client.post(
        "/v1/mercury/invoke",
        json={
            "request_id": "req-graph-error",
            "user_id": "user-1",
            "wallet_id": "primary",
            "intent": {"kind": "native_balance"},
        },
    )

    assert response.status_code == 500
    text = response.text
    assert "https://rpc.example.invalid" not in text
    assert "secret-token" not in text
    assert "<redacted>" in text


class StaticRuntime:
    def __init__(self, result: MercuryState) -> None:
        self._result = result

    def invoke(self, state: MercuryState) -> MercuryState:
        return self._result


class RaisingRuntime:
    def __init__(self, error: Exception) -> None:
        self._error = error
        self.called = False

    def invoke(self, state: MercuryState) -> MercuryState:
        self.called = True
        raise self._error
