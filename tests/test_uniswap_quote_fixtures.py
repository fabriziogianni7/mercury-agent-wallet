"""Fixture-shaped Uniswap Trading API responses and policy integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mercury.models.policy import PolicyDecisionStatus
from mercury.models.swaps import (
    SwapEVMTransaction,
    SwapExecution,
    SwapExecutionType,
    SwapProviderName,
    SwapQuote,
    SwapQuoteRequest,
    SwapRoute,
    SwapRouteKind,
)
from mercury.policy.swap_rules import (
    SwapPolicyConfig,
    evaluate_swap_quote_policy,
    swap_transaction_policy_reason,
)
from mercury.swaps.uniswap import UniswapProvider

TOKEN_IN = "0x000000000000000000000000000000000000cafE"
TOKEN_OUT = "0x000000000000000000000000000000000000dEaD"
WALLET = "0x000000000000000000000000000000000000bEEF"
SPENDER = "0x0000000000000000000000000000000000000002"
SWAP_TO = "0x0000000000000000000000000000000000000003"


def _base_request(**kwargs: object) -> SwapQuoteRequest:
    return SwapQuoteRequest(
        wallet_id="primary",
        wallet_address=WALLET,
        chain="base",
        chain_id=8453,
        from_token=TOKEN_IN,
        to_token=TOKEN_OUT,
        amount_in="1.5",
        amount_in_raw=1_500_000,
        idempotency_key="swap-uni-fixtures",
        **kwargs,
    )


def test_uniswap_quote_top_level_shape_without_nested_quote() -> None:
    """API returns quote fields at the top level (no ``quote`` wrapper)."""

    provider = UniswapProvider(http_client=_RecordingClient(top_level_quote_response()))
    quote = provider.get_quote(_base_request())

    assert quote.route.spender_address == SPENDER
    assert quote.amount_in_raw == 1_500_000
    assert quote.expected_amount_out_raw == 1_000_000
    assert quote.min_amount_out_raw == 990_000
    assert quote.slippage_bps == 50
    assert quote.expires_at is not None
    execution = provider.build_execution(quote)
    assert execution.transaction is not None
    assert execution.transaction.value_wei == 42


def test_uniswap_quote_merges_outer_fields_with_inner_quote() -> None:
    """Outer siblings (e.g. chainId) are merged with nested ``quote``."""

    provider = UniswapProvider(http_client=_RecordingClient(merged_quote_response()))
    quote = provider.get_quote(_base_request())

    assert quote.route.from_chain_id == 8453
    assert quote.route.to_chain_id == 8453
    assert quote.expected_amount_out_raw == 1_000_000


def test_uniswap_swap_posts_inner_quote_when_response_was_wrapped() -> None:
    provider = UniswapProvider(http_client=_RecordingClient(wrapped_quote_response()))
    quote = provider.get_quote(_base_request())
    provider.build_execution(quote)

    last = provider._http.last_swap_payload  # type: ignore[attr-defined]
    assert last is not None
    assert last["quote"]["requestId"] == "inner-only"
    assert "outerMeta" not in last["quote"]


def test_uniswap_swap_posts_full_body_when_quote_was_flat() -> None:
    provider = UniswapProvider(http_client=_RecordingClient(top_level_quote_response()))
    quote = provider.get_quote(_base_request())
    provider.build_execution(quote)

    last = provider._http.last_swap_payload  # type: ignore[attr-defined]
    assert last["quote"]["requestId"] == "top-1"
    assert last["quote"]["tokenIn"] == TOKEN_IN


def test_uniswap_build_execution_parses_hex_transaction_value() -> None:
    provider = UniswapProvider(
        http_client=_RecordingClient(
            wrapped_quote_response(),
            swap_tx={"to": SWAP_TO, "data": "0xabcd", "value": "0x2a"},
        )
    )
    quote = provider.get_quote(_base_request())
    execution = provider.build_execution(quote)
    assert execution.transaction is not None
    assert execution.transaction.value_wei == 42


def test_policy_rejects_uniswap_quote_missing_spender() -> None:
    quote = _manual_uniswap_quote(spender_address=None)
    decision = evaluate_swap_quote_policy(quote)
    assert decision.status == PolicyDecisionStatus.REJECTED
    assert "spender" in decision.reason.lower()


def test_swap_transaction_policy_rejects_missing_spender_metadata() -> None:
    quote = _manual_uniswap_quote()
    execution = SwapExecution(
        provider=SwapProviderName.UNISWAP,
        execution_type=SwapExecutionType.EVM_TRANSACTION,
        quote=quote,
        transaction=SwapEVMTransaction(chain_id=8453, to=SWAP_TO, data="0x", value_wei=0),
    )
    prepared = UniswapProvider().to_prepared_transaction(execution)
    broken = prepared.model_copy(
        update={"metadata": {**prepared.metadata, "spender_address": None}},
    )
    reason = swap_transaction_policy_reason(broken)
    assert reason is not None
    assert "spender" in reason.lower()


def test_swap_transaction_policy_rejects_slippage_over_max_in_metadata() -> None:
    quote = _manual_uniswap_quote()
    execution = SwapExecution(
        provider=SwapProviderName.UNISWAP,
        execution_type=SwapExecutionType.EVM_TRANSACTION,
        quote=quote,
        transaction=SwapEVMTransaction(chain_id=8453, to=SWAP_TO, data="0x", value_wei=0),
    )
    prepared = UniswapProvider().to_prepared_transaction(execution)
    over = prepared.model_copy(
        update={"metadata": {**prepared.metadata, "slippage_bps": 500}},
    )
    reason = swap_transaction_policy_reason(over, config=SwapPolicyConfig(max_slippage_bps=100))
    assert reason is not None
    assert "slippage" in reason.lower()


def _manual_uniswap_quote(*, spender_address: str | None = SPENDER) -> SwapQuote:
    req = _base_request(max_slippage_bps=50)
    route = SwapRoute(
        provider=SwapProviderName.UNISWAP,
        route_id="manual",
        route_kind=SwapRouteKind.SWAP,
        from_chain_id=8453,
        to_chain_id=8453,
        from_token=TOKEN_IN,
        to_token=TOKEN_OUT,
        spender_address=spender_address,
    )
    return SwapQuote(
        provider=SwapProviderName.UNISWAP,
        request=req,
        route=route,
        amount_in_raw=1_500_000,
        expected_amount_out_raw=1_000_000,
        min_amount_out_raw=990_000,
        slippage_bps=50,
        expires_at=datetime.now(tz=UTC) + timedelta(minutes=5),
        recipient_address=req.effective_recipient,
        raw_quote={},
    )


def top_level_quote_response() -> dict[str, object]:
    return {
        "requestId": "top-1",
        "tokenInChainId": 8453,
        "tokenOutChainId": 8453,
        "tokenIn": TOKEN_IN,
        "tokenOut": TOKEN_OUT,
        "amount": 1_500_000,
        "amountOut": "1000000",
        "minAmountOut": "990000",
        "allowanceTarget": SPENDER,
        "slippageBps": 50,
        "expiresAt": int((datetime.now(tz=UTC) + timedelta(minutes=10)).timestamp()),
    }


def wrapped_quote_response() -> dict[str, object]:
    return {
        "quote": {
            "requestId": "inner-only",
            "tokenInChainId": 8453,
            "tokenOutChainId": 8453,
            "tokenIn": TOKEN_IN,
            "tokenOut": TOKEN_OUT,
            "amount": "1500000",
            "quoteAmountOut": "1000000",
            "minAmountOut": "990000",
            "permit2Address": SPENDER,
        }
    }


def merged_quote_response() -> dict[str, object]:
    return {
        "chainId": 8453,
        "quote": {
            "requestId": "merged-1",
            "tokenIn": TOKEN_IN,
            "tokenOut": TOKEN_OUT,
            "amount": "1500000",
            "amountOut": 1_000_000,
            "minAmountOut": 990_000,
            "permit2Address": SPENDER,
        },
    }


class _RecordingClient:
    def __init__(
        self,
        quote_body: dict[str, object],
        *,
        swap_tx: dict[str, object] | None = None,
    ) -> None:
        self._quote = quote_body
        self._swap_tx = swap_tx or {"to": SWAP_TO, "data": "0x1234", "value": "42"}
        self.last_swap_payload: dict[str, object] | None = None

    def post_json(
        self,
        path: str,
        *,
        payload: dict[str, object],
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        if path == "/v1/quote":
            return self._quote
        if path == "/v1/swap":
            self.last_swap_payload = payload
            return {"transaction": self._swap_tx}
        raise AssertionError(f"unexpected path {path}")

    def get_json(
        self,
        path: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        raise AssertionError("Uniswap fixture client should not GET")
