from datetime import UTC, datetime, timedelta

from mercury.models.swaps import SwapExecutionType, SwapQuoteRequest
from mercury.swaps.cowswap import CowSwapProvider

TOKEN_IN = "0x000000000000000000000000000000000000cafE"
TOKEN_OUT = "0x000000000000000000000000000000000000dEaD"
WALLET = "0x000000000000000000000000000000000000bEEF"
SPENDER = "0x0000000000000000000000000000000000000002"


def test_cowswap_quote_normalizes_order_route() -> None:
    provider = CowSwapProvider(http_client=FakeHttpClient(_response(include_typed_data=True)))

    quote = provider.get_quote(_request())

    assert quote.route.spender_address == SPENDER
    assert quote.amount_in_raw == 1_500_000
    assert quote.expected_amount_out_raw == 1_000_000


def test_cowswap_build_execution_returns_typed_order_when_available() -> None:
    provider = CowSwapProvider(http_client=FakeHttpClient(_response(include_typed_data=True)))
    quote = provider.get_quote(_request())

    execution = provider.build_execution(quote)

    assert execution.execution_type == SwapExecutionType.EIP712_ORDER
    assert execution.order is not None
    assert execution.order.typed_data["domain"]["chainId"] == 8453


def test_cowswap_build_execution_explicitly_defers_without_typed_data() -> None:
    provider = CowSwapProvider(http_client=FakeHttpClient(_response(include_typed_data=False)))
    quote = provider.get_quote(_request())

    execution = provider.build_execution(quote)

    assert execution.execution_type == SwapExecutionType.UNSUPPORTED
    assert "typed-data" in (execution.unsupported_reason or "")


class FakeHttpClient:
    def __init__(self, response: dict[str, object]) -> None:
        self._response = response

    def get_json(
        self,
        path: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        raise AssertionError("CoW Swap quote test should not GET")

    def post_json(
        self,
        path: str,
        *,
        payload: dict[str, object],
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        return self._response


def _request() -> SwapQuoteRequest:
    return SwapQuoteRequest(
        wallet_id="primary",
        wallet_address=WALLET,
        chain="base",
        chain_id=8453,
        from_token=TOKEN_IN,
        to_token=TOKEN_OUT,
        amount_in="1.5",
        amount_in_raw=1_500_000,
        idempotency_key="swap-1",
    )


def _response(*, include_typed_data: bool) -> dict[str, object]:
    response: dict[str, object] = {
        "id": "cow-quote-1",
        "spender": SPENDER,
        "quote": {
            "sellToken": TOKEN_IN,
            "buyToken": TOKEN_OUT,
            "sellAmount": "1500000",
            "buyAmount": "1000000",
            "validTo": int((datetime.now(tz=UTC) + timedelta(minutes=5)).timestamp()),
        },
    }
    if include_typed_data:
        response["typedData"] = {"domain": {"chainId": 8453}, "message": {"sellToken": TOKEN_IN}}
    return response
