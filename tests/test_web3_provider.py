from typing import Any, cast

import mercury.providers.web3 as web3_provider
import pytest
from mercury.custody import FakeSecretStore, SecretNotFoundError
from mercury.models.addresses import InvalidEVMAddressError, normalize_evm_address
from mercury.providers import Web3ProviderFactory


class SpyWeb3:
    created_providers: list[object] = []

    @staticmethod
    def HTTPProvider(rpc_url: str) -> dict[str, str]:  # noqa: N802
        return {"rpc_url": rpc_url}

    def __init__(self, provider: object) -> None:
        self.provider = provider
        self.created_providers.append(provider)


def test_provider_factory_resolves_ethereum_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web3_provider, "Web3", SpyWeb3)
    store = FakeSecretStore({"mercury/rpc/ethereum": "https://eth.example.invalid"})

    provider = Web3ProviderFactory(store).create("ethereum")

    assert provider.chain.name == "ethereum"
    client = cast(Any, provider.client)
    assert client.provider == {"rpc_url": "https://eth.example.invalid"}


def test_provider_factory_resolves_base_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web3_provider, "Web3", SpyWeb3)
    store = FakeSecretStore({"mercury/rpc/base": "https://base.example.invalid"})

    provider = Web3ProviderFactory(store).create("base")

    assert provider.chain.name == "base"
    client = cast(Any, provider.client)
    assert client.provider == {"rpc_url": "https://base.example.invalid"}


def test_provider_factory_fails_cleanly_when_rpc_secret_missing() -> None:
    store = FakeSecretStore({})

    with pytest.raises(SecretNotFoundError) as exc_info:
        Web3ProviderFactory(store).create("ethereum")

    assert "mercury/rpc/ethereum" in str(exc_info.value)
    assert "https://" not in str(exc_info.value)


def test_normalize_evm_address_accepts_lowercase_and_checksum() -> None:
    lowercase = "0x000000000000000000000000000000000000dead"
    checksum = normalize_evm_address(lowercase)

    assert checksum == "0x000000000000000000000000000000000000dEaD"
    assert normalize_evm_address(checksum) == checksum


def test_normalize_evm_address_rejects_malformed_values() -> None:
    with pytest.raises(InvalidEVMAddressError, match="must not be empty"):
        normalize_evm_address(" ")

    with pytest.raises(InvalidEVMAddressError, match="Invalid EVM address"):
        normalize_evm_address("not-an-address")
