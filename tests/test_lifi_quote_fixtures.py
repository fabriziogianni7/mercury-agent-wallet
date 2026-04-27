"""Fixture-style tests for LiFi /quote response normalization (documented-style shapes)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from mercury.models.swaps import SwapExecutionType, SwapQuoteRequest, SwapRouteKind
from mercury.swaps.base import SwapProviderError
from mercury.swaps.lifi import LiFiProvider

TOKEN_IN = "0x000000000000000000000000000000000000cafE"
TOKEN_OUT = "0x000000000000000000000000000000000000dEaD"
WALLET = "0x000000000000000000000000000000000000bEEF"
SPENDER = "0x0000000000000000000000000000000000000002"
SWAP_TO = "0x0000000000000000000000000000000000000003"


def test_lifi_fixture_string_amounts_and_top_level_approval() -> None:
    """Amounts as decimal strings; approval only on payload (not inside estimate)."""

    http = FakeHttpClient(
        {
            "id": "fx-1",
            "action": {
                "fromChainId": 8453,
                "toChainId": 8453,
                "fromToken": TOKEN_IN,
                "toToken": TOKEN_OUT,
            },
            "approvalAddress": SPENDER,
            "estimate": {
                "fromAmount": "1500000",
                "toAmount": "1000000",
                "toAmountMin": "990000",
            },
            "transactionRequest": {"to": SWAP_TO, "data": "0xabcd", "value": "0"},
        }
    )
    provider = LiFiProvider(http_client=http)
    quote = provider.get_quote(_request())

    assert quote.expected_amount_out_raw == 1_000_000
    assert quote.min_amount_out_raw == 990_000
    assert quote.route.spender_address == SPENDER


def test_lifi_fixture_expires_at_iso_in_estimate() -> None:
    http = FakeHttpClient(
        _minimal_response(
            expires_at="2028-01-01T12:00:00.000Z",
        )
    )
    quote = LiFiProvider(http_client=http).get_quote(_request())
    assert quote.expires_at is not None
    assert quote.expires_at.year == 2028


def test_lifi_fixture_expires_at_unix_int_in_payload() -> None:
    ts = 1890000000
    http = FakeHttpClient(
        _minimal_response(
            extra_top={"expiresAt": ts},
        )
    )
    quote = LiFiProvider(http_client=http).get_quote(_request())
    assert quote.expires_at == datetime.fromtimestamp(ts, tz=UTC)


def test_lifi_fixture_expires_at_unix_string() -> None:
    ts = 1890000000
    http = FakeHttpClient(
        _minimal_response(
            extra_est={"expiresAt": str(ts)},
        )
    )
    quote = LiFiProvider(http_client=http).get_quote(_request())
    assert quote.expires_at == datetime.fromtimestamp(ts, tz=UTC)


def test_lifi_fixture_optional_to_amount_min() -> None:
    body = _minimal_response()
    del body["estimate"]["toAmountMin"]
    http = FakeHttpClient(body)
    quote = LiFiProvider(http_client=http).get_quote(_request())
    assert quote.min_amount_out_raw is None


def test_lifi_fixture_transaction_value_hex() -> None:
    http = FakeHttpClient(
        {
            "action": {
                "fromChainId": 8453,
                "toChainId": 8453,
                "fromToken": TOKEN_IN,
                "toToken": TOKEN_OUT,
            },
            "estimate": {
                "fromAmount": "1500000",
                "toAmount": "1000000",
            },
            "transactionRequest": {
                "to": SWAP_TO,
                "data": "0x12",
                "value": "0x00",
            },
        }
    )
    provider = LiFiProvider(http_client=http)
    execution = provider.build_execution(provider.get_quote(_request()))
    assert execution.execution_type == SwapExecutionType.EVM_TRANSACTION
    assert execution.transaction is not None
    assert execution.transaction.value_wei == 0


def test_lifi_bridge_request_sends_to_chain_param() -> None:
    body = {
        "id": "bridge-1",
        "action": {
            "fromChainId": 8453,
            "toChainId": 1,
            "fromToken": TOKEN_IN,
            "toToken": TOKEN_OUT,
        },
        "estimate": {
            "fromAmount": "1500000",
            "toAmount": "900000",
            "toAmountMin": "890000",
            "approvalAddress": SPENDER,
        },
        "transactionRequest": {"to": SWAP_TO, "data": "0x1", "value": 0},
    }
    http = FakeHttpClient(body)
    provider = LiFiProvider(http_client=http)
    request = _request(to_chain="ethereum", to_chain_id=1)
    quote = provider.get_quote(request)

    params = cast(dict[str, Any], http.get_requests[0]["params"])
    assert params["fromChain"] == 8453
    assert params["toChain"] == 1
    assert quote.route.route_kind == SwapRouteKind.BRIDGE
    assert quote.route.to_chain_id == 1


def test_lifi_rejects_missing_action() -> None:
    with pytest.raises(SwapProviderError, match="action"):
        LiFiProvider(http_client=FakeHttpClient({})).get_quote(_request())


class FakeHttpClient:
    def __init__(self, response: dict[str, object]) -> None:
        self._response = response
        self.get_requests: list[dict[str, object]] = []

    def get_json(
        self,
        path: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        self.get_requests.append({"path": path, "params": params or {}, "headers": headers or {}})
        return self._response

    def post_json(
        self,
        path: str,
        *,
        payload: dict[str, object],
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        raise AssertionError("not used")


def _request(
    *,
    to_chain: str | None = None,
    to_chain_id: int | None = None,
) -> SwapQuoteRequest:
    return SwapQuoteRequest(
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
        to_chain=to_chain,
        to_chain_id=to_chain_id,
    )


def _minimal_response(
    *,
    expires_at: str | int | None = None,
    extra_top: dict[str, Any] | None = None,
    extra_est: dict[str, Any] | None = None,
) -> dict[str, Any]:
    est: dict[str, Any] = {
        "fromAmount": "1500000",
        "toAmount": "1000000",
        "toAmountMin": "990000",
        "approvalAddress": SPENDER,
    }
    if isinstance(expires_at, str):
        est["expiresAt"] = expires_at
    if extra_est:
        est.update(extra_est)
    out: dict[str, Any] = {
        "id": "lifi-x",
        "action": {
            "fromChainId": 8453,
            "toChainId": 8453,
            "fromToken": TOKEN_IN,
            "toToken": TOKEN_OUT,
        },
        "estimate": est,
        "transactionRequest": {
            "to": SWAP_TO,
            "data": "0x1234",
            "value": "0",
        },
    }
    if isinstance(expires_at, int):
        out["expiresAt"] = expires_at
    if extra_top:
        out.update(extra_top)
    return out
