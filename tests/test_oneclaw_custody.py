import json
from email.message import Message
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import pytest
from mercury.custody import (
    EmptySecretValueError,
    FakeOneClawClient,
    FakeSecretStore,
    OneClawHttpClient,
    OneClawSecretStore,
    SecretNotFoundError,
    SecretStoreUnavailableError,
    SecretValue,
)


def test_secret_value_requires_explicit_reveal() -> None:
    secret = SecretValue(path="mercury/rpc/ethereum", _value="https://example.invalid")

    assert secret.reveal() == "https://example.invalid"
    assert "https://example.invalid" not in repr(secret)
    assert "<redacted>" in repr(secret)


def test_oneclaw_secret_store_resolves_secret_with_agent_scope() -> None:
    client = FakeOneClawClient({"mercury/rpc/ethereum": "https://eth.example.invalid"})
    store = OneClawSecretStore(client=client, vault_id="vault-1", agent_id="agent-1")

    secret = store.get_secret("mercury/rpc/ethereum")

    assert secret.reveal() == "https://eth.example.invalid"
    assert client.requests == [
        {
            "vault_id": "vault-1",
            "path": "mercury/rpc/ethereum",
            "agent_id": "agent-1",
        }
    ]


def test_missing_secret_error_is_sanitized() -> None:
    store = OneClawSecretStore(client=FakeOneClawClient({}), vault_id="vault-1")

    with pytest.raises(SecretNotFoundError) as exc_info:
        store.get_secret("mercury/rpc/ethereum")

    assert "mercury/rpc/ethereum" in str(exc_info.value)
    assert "https://" not in str(exc_info.value)


def test_empty_secret_error_is_sanitized() -> None:
    store = FakeSecretStore({"mercury/rpc/base": "   "})

    with pytest.raises(EmptySecretValueError) as exc_info:
        store.get_secret("mercury/rpc/base")

    assert "mercury/rpc/base" in str(exc_info.value)
    assert "   " not in str(exc_info.value)


def _mock_url_response(payload: dict[str, object]) -> MagicMock:
    body = json.dumps(payload).encode("utf-8")
    inner = MagicMock()
    inner.read.return_value = body
    cm = MagicMock()
    cm.__enter__.return_value = inner
    cm.__exit__.return_value = None
    return cm


def test_oneclaw_http_client_hosted_gets_jwt_then_secret() -> None:
    client = OneClawHttpClient(base_url="https://api.example.invalid", api_key="agent-key")

    with patch("mercury.custody.oneclaw.urlopen") as urlopen_mock:
        urlopen_mock.side_effect = [
            _mock_url_response({"access_token": "jwt-token"}),
            _mock_url_response({"value": "https://rpc.example.invalid"}),
        ]

        value = client.get_secret(
            vault_id="00000000-0000-0000-0000-000000000001",
            path="mercury/rpc/base",
            agent_id="agent-99",
        )

    assert value == "https://rpc.example.invalid"
    assert urlopen_mock.call_count == 2
    auth_req = urlopen_mock.call_args_list[0].args[0]
    assert auth_req.full_url.endswith("/v1/auth/agent-token")
    assert auth_req.method == "POST"
    secret_req = urlopen_mock.call_args_list[1].args[0]
    vault_url = "/v1/vaults/00000000-0000-0000-0000-000000000001/secrets/mercury/rpc/base"
    assert secret_req.full_url.endswith(vault_url)
    assert secret_req.method == "GET"
    assert secret_req.headers["Authorization"] == "Bearer jwt-token"


def test_oneclaw_http_client_legacy_resolve_without_agent() -> None:
    client = OneClawHttpClient(base_url="https://legacy.example.invalid", api_key="raw-bearer")

    with patch("mercury.custody.oneclaw.urlopen") as urlopen_mock:
        urlopen_mock.return_value = _mock_url_response({"value": "secret"})
        value = client.get_secret(
            vault_id="vault-a",
            path="mercury/rpc/ethereum",
            agent_id=None,
        )

    assert value == "secret"
    assert urlopen_mock.call_count == 1
    req = urlopen_mock.call_args.args[0]
    assert req.full_url.endswith("/v1/vaults/vault-a/secrets:resolve")
    assert req.method == "POST"
    assert req.headers["Authorization"] == "Bearer raw-bearer"


def test_oneclaw_http_client_hosted_secret_forbidden() -> None:
    client = OneClawHttpClient(base_url="https://api.example.invalid", api_key="agent-key")

    with patch("mercury.custody.oneclaw.urlopen") as urlopen_mock:
        urlopen_mock.side_effect = [
            _mock_url_response({"access_token": "jwt-token"}),
            HTTPError(
                "https://api.example.invalid/v1/vaults/vid/secrets/mercury/rpc/base",
                403,
                "Forbidden",
                hdrs=Message(),
                fp=BytesIO(),
            ),
        ]

        with pytest.raises(SecretStoreUnavailableError, match="HTTP 403 Forbidden"):
            client.get_secret(
                vault_id="vid",
                path="mercury/rpc/base",
                agent_id="agent-1",
            )


def test_oneclaw_http_client_hosted_auth_failure() -> None:
    client = OneClawHttpClient(base_url="https://api.example.invalid", api_key="bad")

    with patch("mercury.custody.oneclaw.urlopen") as urlopen_mock:
        err = HTTPError(
            "https://api.example.invalid/v1/auth/agent-token",
            401,
            "Unauthorized",
            hdrs=Message(),
            fp=BytesIO(),
        )
        urlopen_mock.side_effect = err

        with pytest.raises(SecretStoreUnavailableError, match="agent authentication"):
            client.get_secret(
                vault_id="00000000-0000-0000-0000-000000000001",
                path="mercury/rpc/base",
                agent_id="agent-1",
            )
