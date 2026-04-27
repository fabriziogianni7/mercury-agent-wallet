"""Uniswap API adapter behind Mercury's normalized interface."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from mercury.models.execution import PreparedTransaction
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
from mercury.swaps.base import (
    JsonHttpClient,
    SwapProviderConfig,
    SwapProviderError,
    UrllibJsonHttpClient,
    optional_int,
    provider_api_key,
    require_int,
    require_string,
)


class UniswapProvider:
    """Uniswap quote/build adapter with API details isolated behind this class."""

    name = SwapProviderName.UNISWAP

    def __init__(
        self,
        config: SwapProviderConfig | None = None,
        *,
        http_client: JsonHttpClient | None = None,
    ) -> None:
        self._config = config or SwapProviderConfig.default_for(self.name)
        self._http = http_client or UrllibJsonHttpClient(self._config.base_url)

    def get_quote(self, request: SwapQuoteRequest) -> SwapQuote:
        """Fetch and normalize a Uniswap quote."""

        response = self._http.post_json(
            "/v1/quote",
            payload={
                "tokenInChainId": request.chain_id,
                "tokenOutChainId": request.chain_id,
                "tokenIn": request.from_token,
                "tokenOut": request.to_token,
                "amount": str(request.amount_in_raw),
                "swapper": request.wallet_address,
                "recipient": request.effective_recipient,
                "type": "EXACT_INPUT",
            },
            headers=_headers(self._config),
        )
        raw_quote = response.get("quote")
        quote_payload: dict[str, Any] = raw_quote if isinstance(raw_quote, dict) else response
        route = SwapRoute(
            provider=self.name,
            route_id=_route_id(quote_payload),
            route_kind=SwapRouteKind.SWAP,
            from_chain_id=require_int(quote_payload, "tokenInChainId"),
            to_chain_id=require_int(quote_payload, "tokenOutChainId"),
            from_token=require_string(quote_payload, "tokenIn"),
            to_token=require_string(quote_payload, "tokenOut"),
            spender_address=_spender(quote_payload),
            steps=("uniswap",),
        )
        return SwapQuote(
            provider=self.name,
            request=request,
            route=route,
            amount_in_raw=require_int(quote_payload, "amount"),
            expected_amount_out_raw=require_int(quote_payload, "amountOut"),
            min_amount_out_raw=optional_int(quote_payload, "minAmountOut"),
            slippage_bps=request.max_slippage_bps,
            expires_at=_expiry(quote_payload),
            recipient_address=request.effective_recipient,
            raw_quote=response,
        )

    def build_execution(self, quote: SwapQuote) -> SwapExecution:
        """Build a Uniswap EVM execution payload or return explicit unsupported."""

        response = self._http.post_json(
            "/v1/swap",
            payload={"quote": quote.raw_quote.get("quote", quote.raw_quote)},
            headers=_headers(self._config),
        )
        transaction_payload = response.get("transaction")
        if not isinstance(transaction_payload, dict):
            return SwapExecution(
                provider=self.name,
                execution_type=SwapExecutionType.UNSUPPORTED,
                quote=quote,
                unsupported_reason="Uniswap response did not include an executable transaction.",
                raw_execution=response,
            )
        transaction = SwapEVMTransaction(
            chain_id=quote.request.chain_id,
            to=require_string(transaction_payload, "to"),
            data=require_string(transaction_payload, "data"),
            value_wei=optional_int(transaction_payload, "value") or 0,
        )
        return SwapExecution(
            provider=self.name,
            execution_type=SwapExecutionType.EVM_TRANSACTION,
            quote=quote,
            transaction=transaction,
            raw_execution=response,
        )

    def to_prepared_transaction(self, execution: SwapExecution) -> PreparedTransaction:
        """Convert a normalized Uniswap execution into the Phase 6 transaction model."""

        if execution.transaction is None:
            raise SwapProviderError("Uniswap execution has no EVM transaction.")
        quote = execution.quote
        return PreparedTransaction(
            wallet_id=quote.request.wallet_id,
            chain=quote.request.chain,
            chain_id=execution.transaction.chain_id,
            from_address=quote.request.wallet_address,
            to=execution.transaction.to,
            value_wei=execution.transaction.value_wei,
            data=execution.transaction.data,
            idempotency_key=quote.request.idempotency_key,
            metadata={
                "action": "swap",
                "provider": self.name.value,
                "route_id": quote.route.route_id,
                "route_kind": quote.route.route_kind.value,
                "from_token": quote.route.from_token,
                "to_token": quote.route.to_token,
                "spender_address": quote.route.spender_address,
                "amount_in_raw": quote.amount_in_raw,
                "expected_amount_out_raw": quote.expected_amount_out_raw,
                "min_amount_out_raw": quote.min_amount_out_raw,
                "slippage_bps": quote.slippage_bps,
                "recipient_address": quote.recipient_address,
                "quote_expires_at": quote.expires_at.isoformat() if quote.expires_at else None,
            },
        )


def _headers(config: SwapProviderConfig) -> dict[str, str]:
    api_key = provider_api_key(config)
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _route_id(payload: dict[str, Any]) -> str:
    for key in ("requestId", "quoteId", "routeId"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return "uniswap-route"


def _spender(payload: dict[str, Any]) -> str | None:
    for key in ("permit2Address", "allowanceTarget", "spender"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _expiry(payload: dict[str, Any]) -> datetime:
    value = payload.get("expiresAt")
    if isinstance(value, int):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str) and value.strip():
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    return datetime.now(tz=UTC) + timedelta(minutes=5)
