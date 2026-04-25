import pytest
from mercury.chains import (
    UnsupportedChainError,
    get_chain_by_id,
    get_chain_by_name,
    get_default_chain,
)


def test_resolves_ethereum_by_name() -> None:
    chain = get_chain_by_name("ethereum")

    assert chain.name == "ethereum"
    assert chain.chain_id == 1
    assert chain.native_symbol == "ETH"
    assert chain.rpc_secret_path == "mercury/rpc/ethereum"


def test_resolves_base_by_name() -> None:
    chain = get_chain_by_name("base")

    assert chain.name == "base"
    assert chain.chain_id == 8453
    assert chain.native_symbol == "ETH"
    assert chain.rpc_secret_path == "mercury/rpc/base"


def test_resolves_ethereum_by_chain_id() -> None:
    assert get_chain_by_id(1).name == "ethereum"


def test_resolves_base_by_chain_id() -> None:
    assert get_chain_by_id(8453).name == "base"


def test_unsupported_chain_raises_clear_error() -> None:
    with pytest.raises(UnsupportedChainError, match="Unsupported chain name 'polygon'"):
        get_chain_by_name("polygon")

    with pytest.raises(UnsupportedChainError, match="Unsupported chain ID '137'"):
        get_chain_by_id(137)


def test_default_chain_is_ethereum() -> None:
    assert get_default_chain().name == "ethereum"
