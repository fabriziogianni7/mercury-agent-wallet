"""CoW Swap adapter behind Mercury's normalized interface."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from mercury.models.swaps import (
    SwapExecution,
    SwapExecutionType,
    SwapProviderName,
    SwapQuote,
    SwapQuoteRequest,
    SwapRoute,
    SwapRouteKind,
    SwapTypedOrder,
)
from mercury.swaps.base import (
    JsonHttpClient,
    SwapProviderConfig,
    SwapProviderError,
    UrllibJsonHttpClient,
    provider_api_key,
    require_int,
    require_string,
)


class CowSwapProvider:
    """CoW Swap quote/order adapter.

    MVP support normalizes quotes and typed order payloads. Order submission remains
    outside the EVM transaction pipeline and must use the typed-data signer boundary.
    """

    name = SwapProviderName.COWSWAP

    def __init__(
        self,
        config: SwapProviderConfig | None = None,
        *,
        http_client: JsonHttpClient | None = None,
    ) -> None:
        self._config = config or SwapProviderConfig.default_for(self.name)
        self._http = http_client or UrllibJsonHttpClient(self._config.base_url)

    def get_quote(self, request: SwapQuoteRequest) -> SwapQuote:
        """Fetch and normalize a CoW Swap quote."""

        response = self._http.post_json(
            f"/{request.chain_id}/api/v1/quote",
            payload={
                "sellToken": request.from_token,
                "buyToken": request.to_token,
                "receiver": request.effective_recipient,
                "from": request.wallet_address,
                "sellAmountBeforeFee": str(request.amount_in_raw),
                "kind": "sell",
            },
            headers=_headers(self._config),
        )
        quote_payload = response.get("quote")
        if not isinstance(quote_payload, dict):
            raise SwapProviderError("CoW Swap response missing quote payload.")

        route_id = (
            require_string(response, "id")
            if isinstance(response.get("id"), str)
            else "cowswap-quote"
        )
        route = SwapRoute(
            provider=self.name,
            route_id=route_id,
            route_kind=SwapRouteKind.SWAP,
            from_chain_id=request.chain_id,
            to_chain_id=request.chain_id,
            from_token=require_string(quote_payload, "sellToken"),
            to_token=require_string(quote_payload, "buyToken"),
            spender_address=_spender(response),
            steps=("cow-protocol-order",),
        )
        return SwapQuote(
            provider=self.name,
            request=request,
            route=route,
            amount_in_raw=require_int(quote_payload, "sellAmount"),
            expected_amount_out_raw=require_int(quote_payload, "buyAmount"),
            min_amount_out_raw=None,
            slippage_bps=request.max_slippage_bps,
            expires_at=_expiry(quote_payload),
            recipient_address=request.effective_recipient,
            raw_quote=response,
        )

    def build_execution(self, quote: SwapQuote) -> SwapExecution:
        """Build a typed order payload or return an explicit unsupported result."""

        order_payload = quote.raw_quote.get("order") or quote.raw_quote.get("quote")
        if not isinstance(order_payload, dict):
            return SwapExecution(
                provider=self.name,
                execution_type=SwapExecutionType.UNSUPPORTED,
                quote=quote,
                unsupported_reason="CoW Swap quote did not include an order payload.",
            )
        typed_data = quote.raw_quote.get("typedData")
        if not isinstance(typed_data, dict):
            return SwapExecution(
                provider=self.name,
                execution_type=SwapExecutionType.UNSUPPORTED,
                quote=quote,
                unsupported_reason="CoW Swap typed-data signing is not available for this quote.",
                raw_execution=order_payload,
            )

        return SwapExecution(
            provider=self.name,
            execution_type=SwapExecutionType.EIP712_ORDER,
            quote=quote,
            order=SwapTypedOrder(
                chain_id=quote.request.chain_id,
                typed_data=typed_data,
                submit_url=f"{self._config.base_url.rstrip('/')}/{quote.request.chain_id}/api/v1/orders",
            ),
            raw_execution=order_payload,
        )


def _headers(config: SwapProviderConfig) -> dict[str, str]:
    api_key = provider_api_key(config)
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _spender(payload: dict[str, Any]) -> str | None:
    for key in ("spender", "allowanceTarget", "vaultRelayer"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _expiry(quote_payload: dict[str, Any]) -> datetime:
    value = quote_payload.get("validTo")
    if isinstance(value, int):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        if value.isdecimal():
            return datetime.fromtimestamp(int(value), tz=UTC)
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    return datetime.now(tz=UTC) + timedelta(minutes=5)
