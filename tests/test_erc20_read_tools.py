import pytest
from mercury.models.amounts import InvalidTokenDecimalsError
from mercury.tools import get_erc20_allowance, get_erc20_balance, get_erc20_metadata

from tests.test_evm_read_tools import FakeEth, FakeProviderFactory, FakeWeb3

TOKEN = "0x000000000000000000000000000000000000cafE"
WALLET = "0x000000000000000000000000000000000000dEaD"
OWNER = "0x0000000000000000000000000000000000000001"
SPENDER = "0x0000000000000000000000000000000000000002"


def test_get_erc20_metadata_returns_decimals_symbol_and_name() -> None:
    eth = FakeEth(
        contract_responses={
            ("decimals", ()): 6,
            ("symbol", ()): "USDC",
            ("name", ()): "USD Coin",
        }
    )
    factory = FakeProviderFactory(FakeWeb3(eth))

    result = get_erc20_metadata(chain="base", token_address=TOKEN.lower(), provider_factory=factory)

    assert result.chain == "base"
    assert result.chain_id == 8453
    assert result.token_address == TOKEN
    assert result.decimals == 6
    assert result.symbol == "USDC"
    assert result.name == "USD Coin"


def test_get_erc20_metadata_handles_missing_optional_symbol_and_name() -> None:
    eth = FakeEth(contract_responses={("decimals", ()): 18})
    factory = FakeProviderFactory(FakeWeb3(eth))

    result = get_erc20_metadata(chain="ethereum", token_address=TOKEN, provider_factory=factory)

    assert result.decimals == 18
    assert result.symbol is None
    assert result.name is None


def test_get_erc20_balance_calls_balance_of_and_formats_with_decimals() -> None:
    eth = FakeEth(
        contract_responses={
            ("decimals", ()): 6,
            ("symbol", ()): "USDC",
            ("name", ()): "USD Coin",
            ("balanceOf", (WALLET,)): 123_456_789,
        }
    )
    factory = FakeProviderFactory(FakeWeb3(eth))

    result = get_erc20_balance(
        chain="base",
        token_address=TOKEN,
        wallet_address=WALLET.lower(),
        provider_factory=factory,
    )

    assert result.raw_amount == 123_456_789
    assert result.formatted == "123.456789"
    assert result.decimals == 6
    assert result.symbol == "USDC"
    assert result.name == "USD Coin"
    assert result.wallet_address == WALLET
    assert eth.last_contract is not None
    assert ("balanceOf", (WALLET,)) in eth.last_contract.functions.calls


def test_get_erc20_allowance_calls_allowance_and_formats_with_decimals() -> None:
    eth = FakeEth(
        contract_responses={
            ("decimals", ()): 18,
            ("symbol", ()): "TOK",
            ("name", ()): "Token",
            ("allowance", (OWNER, SPENDER)): 2_500_000_000_000_000_000,
        }
    )
    factory = FakeProviderFactory(FakeWeb3(eth))

    result = get_erc20_allowance(
        chain="ethereum",
        token_address=TOKEN,
        owner_address=OWNER,
        spender_address=SPENDER,
        provider_factory=factory,
    )

    assert result.raw_amount == 2_500_000_000_000_000_000
    assert result.formatted == "2.5"
    assert result.decimals == 18
    assert result.owner_address == OWNER
    assert result.spender_address == SPENDER
    assert eth.last_contract is not None
    assert ("allowance", (OWNER, SPENDER)) in eth.last_contract.functions.calls


def test_get_erc20_metadata_rejects_unreasonable_decimals() -> None:
    eth = FakeEth(contract_responses={("decimals", ()): 78})
    factory = FakeProviderFactory(FakeWeb3(eth))

    with pytest.raises(InvalidTokenDecimalsError):
        get_erc20_metadata(chain="ethereum", token_address=TOKEN, provider_factory=factory)
