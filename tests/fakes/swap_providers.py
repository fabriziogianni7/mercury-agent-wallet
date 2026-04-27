from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mercury.models.swaps import (
    SwapEVMTransaction,
    SwapExecution,
    SwapExecutionType,
    SwapProviderName,
    SwapQuote,
    SwapQuoteRequest,
    SwapRoute,
)

TEST_TOKEN_IN = "0x000000000000000000000000000000000000cafE"
TEST_TOKEN_OUT = "0x000000000000000000000000000000000000dEaD"
TEST_SPENDER = "0x0000000000000000000000000000000000000002"
TEST_SWAP_TO = "0x0000000000000000000000000000000000000003"


class FakeSwapProvider:
    name = SwapProviderName.LIFI

    def __init__(
        self,
        events: list[str] | None = None,
        *,
        spender_address: str | None = TEST_SPENDER,
        expires_at: datetime | None = None,
        transaction_chain_id: int | None = None,
    ) -> None:
        self.events = events if events is not None else []
        self.spender_address = spender_address
        self.expires_at = expires_at
        self.transaction_chain_id = transaction_chain_id

    def get_quote(self, request: SwapQuoteRequest) -> SwapQuote:
        self.events.append("quote")
        return fake_swap_quote(
            request=request,
            provider=self.name,
            spender_address=self.spender_address,
            expires_at=self.expires_at,
        )

    def build_execution(self, quote: SwapQuote) -> SwapExecution:
        self.events.append("build")
        return SwapExecution(
            provider=self.name,
            execution_type=SwapExecutionType.EVM_TRANSACTION,
            quote=quote,
            transaction=SwapEVMTransaction(
                chain_id=self.transaction_chain_id or quote.request.chain_id,
                to=TEST_SWAP_TO,
                data="0x1234",
            ),
        )


def fake_swap_request(
    *,
    chain: str = "base",
    chain_id: int = 8453,
    wallet_id: str = "primary",
    wallet_address: str = "0x000000000000000000000000000000000000bEEF",
    amount_in_raw: int = 1_500_000,
    max_slippage_bps: int = 50,
    idempotency_key: str = "swap-test-1",
) -> SwapQuoteRequest:
    return SwapQuoteRequest(
        wallet_id=wallet_id,
        wallet_address=wallet_address,
        chain=chain,
        chain_id=chain_id,
        from_token=TEST_TOKEN_IN,
        to_token=TEST_TOKEN_OUT,
        amount_in="1.5",
        amount_in_raw=amount_in_raw,
        max_slippage_bps=max_slippage_bps,
        idempotency_key=idempotency_key,
    )


def fake_swap_quote(
    *,
    request: SwapQuoteRequest | None = None,
    provider: SwapProviderName = SwapProviderName.LIFI,
    spender_address: str | None = TEST_SPENDER,
    slippage_bps: int = 50,
    expires_at: datetime | None = None,
) -> SwapQuote:
    quote_request = request or fake_swap_request(max_slippage_bps=slippage_bps)
    return SwapQuote(
        provider=provider,
        request=quote_request,
        route=SwapRoute(
            provider=provider,
            route_id="route-1",
            from_chain_id=quote_request.chain_id,
            to_chain_id=quote_request.chain_id,
            from_token=quote_request.from_token,
            to_token=quote_request.to_token,
            spender_address=spender_address,
        ),
        amount_in_raw=quote_request.amount_in_raw,
        expected_amount_out_raw=1_000_000,
        min_amount_out_raw=990_000,
        slippage_bps=slippage_bps,
        expires_at=expires_at or datetime.now(tz=UTC) + timedelta(minutes=5),
        recipient_address=quote_request.effective_recipient,
    )
