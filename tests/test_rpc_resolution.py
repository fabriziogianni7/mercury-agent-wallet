import pytest
from mercury.chains import UnsupportedChainError, resolve_rpc_url
from mercury.custody import EmptySecretValueError, FakeSecretStore, SecretNotFoundError


def test_resolves_ethereum_rpc_url_from_secret_store() -> None:
    store = FakeSecretStore({"mercury/rpc/ethereum": "https://eth.example.invalid"})

    assert resolve_rpc_url("ethereum", store) == "https://eth.example.invalid"


def test_resolves_base_rpc_url_from_secret_store() -> None:
    store = FakeSecretStore({"mercury/rpc/base": "https://base.example.invalid"})

    assert resolve_rpc_url("base", store) == "https://base.example.invalid"


def test_missing_rpc_secret_raises_sanitized_error() -> None:
    store = FakeSecretStore({})

    with pytest.raises(SecretNotFoundError) as exc_info:
        resolve_rpc_url("ethereum", store)

    assert "mercury/rpc/ethereum" in str(exc_info.value)
    assert "https://" not in str(exc_info.value)


def test_unsupported_chain_raises_before_secret_lookup() -> None:
    store = FakeSecretStore({"mercury/rpc/ethereum": "https://eth.example.invalid"})

    with pytest.raises(UnsupportedChainError, match="Unsupported chain name 'polygon'"):
        resolve_rpc_url("polygon", store)


def test_empty_rpc_secret_raises_sanitized_error() -> None:
    store = FakeSecretStore({"mercury/rpc/base": ""})

    with pytest.raises(EmptySecretValueError) as exc_info:
        resolve_rpc_url("base", store)

    assert "mercury/rpc/base" in str(exc_info.value)
    assert "https://" not in str(exc_info.value)
