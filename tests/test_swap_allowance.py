from datetime import UTC, datetime, timedelta

from mercury.models.swaps import (
    SwapEVMTransaction,
    SwapExecution,
    SwapExecutionType,
    SwapIntent,
    SwapProviderName,
    SwapQuote,
    SwapQuoteRequest,
    SwapRoute,
)
from mercury.models.wallets import WalletAddressResult
from mercury.swaps.router import SwapRouter
from mercury.tools.swaps import prepare_swap
from tests.test_evm_read_tools import FakeEth, FakeProviderFactory, FakeWeb3

TOKEN_IN = "0x000000000000000000000000000000000000cafE"
TOKEN_OUT = "0x000000000000000000000000000000000000dEaD"
WALLET = "0x000000000000000000000000000000000000bEEF"
SPENDER = "0x0000000000000000000000000000000000000002"
SWAP_TO = "0x0000000000000000000000000000000000000003"


def test_prepare_swap_creates_approval_when_allowance_is_insufficient() -> None:
    prepared = prepare_swap(
        intent=_intent(),
        router=SwapRouter([FakeSwapProvider()]),
        provider_factory=_factory(allowance=0),
        address_resolver=FakeAddressResolver(),
    )

    assert prepared.approval_transaction is not None
    assert prepared.swap_transaction is None
    assert prepared.approval_transaction.data.startswith("0x095ea7b3")
    assert prepared.approval_transaction.metadata["spender_address"] == SPENDER


def test_prepare_swap_builds_swap_when_allowance_is_sufficient() -> None:
    prepared = prepare_swap(
        intent=_intent(),
        router=SwapRouter([FakeSwapProvider()]),
        provider_factory=_factory(allowance=2_000_000),
        address_resolver=FakeAddressResolver(),
    )

    assert prepared.approval_transaction is None
    assert prepared.swap_transaction is not None
    assert prepared.swap_transaction.to == SWAP_TO
    assert prepared.swap_transaction.metadata["action"] == "swap"


class FakeSwapProvider:
    name = SwapProviderName.LIFI

    def get_quote(self, request: SwapQuoteRequest) -> SwapQuote:
        return SwapQuote(
            provider=self.name,
            request=request,
            route=SwapRoute(
                provider=self.name,
                route_id="route-1",
                from_chain_id=request.chain_id,
                to_chain_id=request.chain_id,
                from_token=request.from_token,
                to_token=request.to_token,
                spender_address=SPENDER,
            ),
            amount_in_raw=request.amount_in_raw,
            expected_amount_out_raw=1_000_000,
            min_amount_out_raw=990_000,
            slippage_bps=request.max_slippage_bps,
            expires_at=datetime.now(tz=UTC) + timedelta(minutes=5),
            recipient_address=request.effective_recipient,
        )

    def build_execution(self, quote: SwapQuote) -> SwapExecution:
        return SwapExecution(
            provider=self.name,
            execution_type=SwapExecutionType.EVM_TRANSACTION,
            quote=quote,
            transaction=SwapEVMTransaction(
                chain_id=quote.request.chain_id,
                to=SWAP_TO,
                data="0x1234",
            ),
        )


class FakeAddressResolver:
    def get_wallet_address(self, wallet_id: str) -> WalletAddressResult:
        return WalletAddressResult(wallet_id=wallet_id, address=WALLET)


def _intent() -> SwapIntent:
    return SwapIntent(
        wallet_id="primary",
        chain="base",
        from_token=TOKEN_IN,
        to_token=TOKEN_OUT,
        amount_in="1.5",
        max_slippage_bps=50,
        provider_preference="lifi",
        idempotency_key="swap-1",
    )


def _factory(*, allowance: int) -> FakeProviderFactory:
    return FakeProviderFactory(
        FakeWeb3(
            FakeEth(
                contract_responses={
                    ("decimals", ()): 6,
                    ("symbol", ()): "USDC",
                    ("allowance", (WALLET, SPENDER)): allowance,
                }
            )
        )
    )
