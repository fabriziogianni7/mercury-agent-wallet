from __future__ import annotations

import pytest
from mercury.known_addresses import (
    KnownAddressMissingError,
    list_protocol_keys,
    list_token_symbols,
    lookup_address,
    reload_known_addresses_for_tests,
)
from web3 import Web3


@pytest.fixture(autouse=True)
def clear_address_cache() -> None:
    reload_known_addresses_for_tests()
    yield
    reload_known_addresses_for_tests()


def test_lookup_usdc_mainnet() -> None:
    addr = lookup_address("ethereum", "token", "USDC")
    assert addr == Web3.to_checksum_address(addr)
    assert addr == "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


def test_lookup_aave_pool_base() -> None:
    addr = lookup_address("base", "protocol", "AAVE_V3.pool")
    assert addr.startswith("0x")


def test_morpho_placeholder_is_zero_but_valid_checksum() -> None:
    addr = lookup_address("ethereum", "protocol", "MORPHO.morpho_blue")
    assert addr == Web3.to_checksum_address("0x0000000000000000000000000000000000000000")


def test_monad_lists_empty_but_protocol_placeholder_accessible() -> None:
    assert list_token_symbols("monad") == []
    morpho = lookup_address(143, "protocol", "MORPHO.morpho_blue")
    assert morpho == Web3.to_checksum_address("0x0000000000000000000000000000000000000000")


def test_unknown_token_raises() -> None:
    with pytest.raises(KnownAddressMissingError, match="No token"):
        lookup_address("monad", "token", "USDC")


def test_list_protocol_keys_includes_flat_names() -> None:
    keys = list_protocol_keys("optimism")
    assert "AAVE_V3.pool" in keys
    assert "MORPHO.morpho_blue" in keys


def test_lookup_accepts_numeric_chain_strings() -> None:
    addr = lookup_address("42161", "token", "ARB")
    assert addr.startswith("0x")


def test_resolve_chain_via_int_chain_id() -> None:
    same = lookup_address(8453, "token", "USDC")
    named = lookup_address("base", "token", "USDC")
    assert same == named
