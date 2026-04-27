from datetime import UTC, datetime, timedelta

from mercury.models.policy import PolicyDecisionStatus
from mercury.models.swaps import (
    SwapProviderName,
    SwapQuote,
    SwapQuoteRequest,
    SwapRoute,
    SwapRouteKind,
)
from mercury.policy.swap_rules import SwapPolicyConfig, evaluate_swap_quote_policy

TOKEN_IN = "0x000000000000000000000000000000000000cafE"
TOKEN_OUT = "0x000000000000000000000000000000000000dEaD"
WALLET = "0x000000000000000000000000000000000000bEEF"
SPENDER = "0x0000000000000000000000000000000000000002"


def test_swap_policy_rejects_excessive_slippage() -> None:
    quote = _quote(slippage_bps=250)

    decision = evaluate_swap_quote_policy(quote, config=SwapPolicyConfig(max_slippage_bps=100))

    assert decision.status == PolicyDecisionStatus.REJECTED
    assert "slippage" in decision.reason


def test_swap_policy_rejects_expired_quote() -> None:
    quote = _quote(expires_at=datetime.now(tz=UTC) - timedelta(seconds=1))

    decision = evaluate_swap_quote_policy(quote)

    assert decision.status == PolicyDecisionStatus.REJECTED
    assert "expired" in decision.reason


def test_swap_policy_rejects_missing_spender() -> None:
    quote = _quote(spender_address=None)

    decision = evaluate_swap_quote_policy(quote)

    assert decision.status == PolicyDecisionStatus.REJECTED
    assert "spender" in decision.reason


def test_swap_policy_allows_safe_quote() -> None:
    decision = evaluate_swap_quote_policy(_quote())

    assert decision.status == PolicyDecisionStatus.ALLOWED


def test_swap_policy_rejects_bridge_when_allow_bridges_false() -> None:
    decision = evaluate_swap_quote_policy(
        _bridge_quote(),
        config=SwapPolicyConfig(allow_bridges=False),
    )
    assert decision.status == PolicyDecisionStatus.REJECTED
    assert "bridge" in decision.reason.lower() or "disabled" in decision.reason.lower()


def test_swap_policy_allows_bridge_when_allow_bridges_true() -> None:
    decision = evaluate_swap_quote_policy(
        _bridge_quote(),
        config=SwapPolicyConfig(allow_bridges=True),
    )
    assert decision.status == PolicyDecisionStatus.ALLOWED


def _quote(
    *,
    slippage_bps: int = 50,
    expires_at: datetime | None = None,
    spender_address: str | None = SPENDER,
) -> SwapQuote:
    request = SwapQuoteRequest(
        wallet_id="primary",
        wallet_address=WALLET,
        chain="base",
        chain_id=8453,
        from_token=TOKEN_IN,
        to_token=TOKEN_OUT,
        amount_in="1.5",
        amount_in_raw=1_500_000,
        max_slippage_bps=slippage_bps,
        idempotency_key="swap-1",
    )
    return SwapQuote(
        provider=SwapProviderName.LIFI,
        request=request,
        route=SwapRoute(
            provider=SwapProviderName.LIFI,
            route_id="route-1",
            from_chain_id=8453,
            to_chain_id=8453,
            from_token=TOKEN_IN,
            to_token=TOKEN_OUT,
            spender_address=spender_address,
        ),
        amount_in_raw=1_500_000,
        expected_amount_out_raw=1_000_000,
        min_amount_out_raw=990_000,
        slippage_bps=slippage_bps,
        expires_at=expires_at or datetime.now(tz=UTC) + timedelta(minutes=5),
        recipient_address=WALLET,
    )


def _bridge_quote() -> SwapQuote:
    request = SwapQuoteRequest(
        wallet_id="primary",
        wallet_address=WALLET,
        chain="base",
        chain_id=8453,
        from_token=TOKEN_IN,
        to_token=TOKEN_OUT,
        amount_in="1.5",
        amount_in_raw=1_500_000,
        max_slippage_bps=50,
        idempotency_key="swap-1",
        to_chain="ethereum",
        to_chain_id=1,
    )
    return SwapQuote(
        provider=SwapProviderName.LIFI,
        request=request,
        route=SwapRoute(
            provider=SwapProviderName.LIFI,
            route_id="route-bridge-1",
            route_kind=SwapRouteKind.BRIDGE,
            from_chain_id=8453,
            to_chain_id=1,
            from_token=TOKEN_IN,
            to_token=TOKEN_OUT,
            spender_address=SPENDER,
        ),
        amount_in_raw=1_500_000,
        expected_amount_out_raw=1_000_000,
        min_amount_out_raw=990_000,
        slippage_bps=50,
        expires_at=datetime.now(tz=UTC) + timedelta(minutes=5),
        recipient_address=WALLET,
    )
