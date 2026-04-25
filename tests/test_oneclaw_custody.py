import pytest
from mercury.custody import (
    EmptySecretValueError,
    FakeOneClawClient,
    FakeSecretStore,
    OneClawSecretStore,
    SecretNotFoundError,
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
