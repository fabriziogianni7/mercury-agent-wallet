import pytest
from mercury.models.erc20 import MAX_UINT256, ERC20Action
from mercury.models.wallets import WalletAddressResult
from mercury.tools.erc20_transactions import (
    check_erc20_approval_preconditions,
    prepare_erc20_approval,
    prepare_erc20_transfer,
)

from tests.test_evm_read_tools import FakeEth, FakeProviderFactory, FakeWeb3

TOKEN = "0x000000000000000000000000000000000000cafE"
WALLET = "0x000000000000000000000000000000000000bEEF"
RECIPIENT = "0x000000000000000000000000000000000000dEaD"
SPENDER = "0x0000000000000000000000000000000000000002"


def test_prepare_erc20_transfer_builds_token_contract_call() -> None:
    factory = _factory(
        {
            ("decimals", ()): 6,
            ("symbol", ()): "USDC",
            ("name", ()): "USD Coin",
            ("balanceOf", (WALLET,)): 2_000_000,
        }
    )

    tx = prepare_erc20_transfer(
        chain="base",
        wallet_id="primary",
        token_address=TOKEN.lower(),
        recipient_address=RECIPIENT.lower(),
        amount="1.5",
        provider_factory=factory,
        address_resolver=FakeAddressResolver(),
        idempotency_key="erc20-transfer-1",
    )

    assert tx.chain == "base"
    assert tx.chain_id == 8453
    assert tx.from_address == WALLET
    assert tx.to == TOKEN
    assert tx.value_wei == 0
    assert tx.data.startswith("0xa9059cbb")
    assert tx.metadata["action"] == ERC20Action.TRANSFER.value
    assert tx.metadata["recipient_address"] == RECIPIENT
    assert tx.metadata["amount_raw"] == 1_500_000


def test_prepare_erc20_transfer_rejects_insufficient_balance() -> None:
    factory = _factory(
        {
            ("decimals", ()): 6,
            ("balanceOf", (WALLET,)): 1,
        }
    )

    with pytest.raises(ValueError, match="insufficient"):
        prepare_erc20_transfer(
            chain="base",
            wallet_id="primary",
            token_address=TOKEN,
            recipient_address=RECIPIENT,
            amount="1.5",
            provider_factory=factory,
            address_resolver=FakeAddressResolver(),
        )


def test_prepare_erc20_transfer_rejects_zero_recipient() -> None:
    factory = _factory({("decimals", ()): 6})

    with pytest.raises(ValueError, match="zero address"):
        prepare_erc20_transfer(
            chain="base",
            wallet_id="primary",
            token_address=TOKEN,
            recipient_address="0x0000000000000000000000000000000000000000",
            amount="1",
            provider_factory=factory,
            address_resolver=FakeAddressResolver(),
        )


def test_prepare_erc20_approval_builds_approval_call() -> None:
    factory = _factory(
        {
            ("decimals", ()): 18,
            ("symbol", ()): "TOK",
            ("name", ()): "Token",
            ("allowance", (WALLET, SPENDER)): 0,
        }
    )

    tx = prepare_erc20_approval(
        chain="ethereum",
        wallet_id="primary",
        token_address=TOKEN,
        spender_address=SPENDER,
        amount="2.5",
        provider_factory=factory,
        address_resolver=FakeAddressResolver(),
        idempotency_key="erc20-approval-1",
        spender_known=True,
    )

    assert tx.chain == "ethereum"
    assert tx.chain_id == 1
    assert tx.to == TOKEN
    assert tx.value_wei == 0
    assert tx.data.startswith("0x095ea7b3")
    assert tx.metadata["action"] == ERC20Action.APPROVAL.value
    assert tx.metadata["spender_address"] == SPENDER
    assert tx.metadata["amount_raw"] == 2_500_000_000_000_000_000
    assert tx.metadata["spender_known"] is True


def test_prepare_erc20_approval_rejects_zero_spender() -> None:
    factory = _factory({("decimals", ()): 18})

    with pytest.raises(ValueError, match="zero address"):
        prepare_erc20_approval(
            chain="ethereum",
            wallet_id="primary",
            token_address=TOKEN,
            spender_address="0x0000000000000000000000000000000000000000",
            amount="1",
            provider_factory=factory,
            address_resolver=FakeAddressResolver(),
        )


def test_prepare_erc20_approval_rejects_unlimited_by_default() -> None:
    factory = _factory({("decimals", ()): 18})

    with pytest.raises(ValueError, match="Unlimited"):
        prepare_erc20_approval(
            chain="ethereum",
            wallet_id="primary",
            token_address=TOKEN,
            spender_address=SPENDER,
            amount="unlimited",
            provider_factory=factory,
            address_resolver=FakeAddressResolver(),
        )


def test_approval_preconditions_report_sufficient_allowance() -> None:
    factory = _factory(
        {
            ("decimals", ()): 6,
            ("allowance", (WALLET, SPENDER)): 10_000_000,
        }
    )

    result = check_erc20_approval_preconditions(
        chain="base",
        token_address=TOKEN,
        owner_address=WALLET,
        spender_address=SPENDER,
        amount="1.5",
        provider_factory=factory,
    )

    assert result.allowance_sufficient is True
    assert result.current_allowance_raw == 10_000_000


def test_approval_preconditions_allow_explicit_unlimited_override() -> None:
    factory = _factory(
        {
            ("decimals", ()): 18,
            ("allowance", (WALLET, SPENDER)): 0,
        }
    )

    result = check_erc20_approval_preconditions(
        chain="ethereum",
        token_address=TOKEN,
        owner_address=WALLET,
        spender_address=SPENDER,
        amount="max",
        provider_factory=factory,
        allow_unlimited=True,
    )

    assert result.unlimited_approval is True
    assert result.amount.raw_amount == MAX_UINT256


class FakeAddressResolver:
    def get_wallet_address(self, wallet_id: str) -> WalletAddressResult:
        return WalletAddressResult(wallet_id=wallet_id, address=WALLET)


def _factory(responses: dict[tuple[str, tuple[object, ...]], object]) -> FakeProviderFactory:
    return FakeProviderFactory(FakeWeb3(FakeEth(contract_responses=responses)))
