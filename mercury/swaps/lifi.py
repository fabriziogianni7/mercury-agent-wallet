"""LiFi swap provider adapter."""

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


class LiFiProvider:
    """LiFi quote/build adapter behind Mercury's normalized interface."""

    name = SwapProviderName.LIFI

    def __init__(
        self,
        config: SwapProviderConfig | None = None,
        *,
        http_client: JsonHttpClient | None = None,
    ) -> None:
        self._config = config or SwapProviderConfig.default_for(self.name)
        self._http = http_client or UrllibJsonHttpClient(self._config.base_url)

    def get_quote(self, request: SwapQuoteRequest) -> SwapQuote:
        """Fetch and normalize a LiFi quote response."""

        response = self._http.get_json(
            "/quote",
            params={
                "fromChain": request.chain_id,
                "toChain": request.chain_id,
                "fromToken": request.from_token,
                "toToken": request.to_token,
                "fromAmount": str(request.amount_in_raw),
                "fromAddress": request.wallet_address,
                "toAddress": request.effective_recipient,
                "slippage": _slippage_float(request.max_slippage_bps),
            },
            headers=_headers(self._config),
        )
        return self._normalize_quote(request, response)

    def build_execution(self, quote: SwapQuote) -> SwapExecution:
        """Build an EVM execution payload from LiFi's transaction request."""

        transaction_payload = quote.raw_quote.get("transactionRequest")
        if not isinstance(transaction_payload, dict):
            return SwapExecution(
                provider=self.name,
                execution_type=SwapExecutionType.UNSUPPORTED,
                quote=quote,
                unsupported_reason="LiFi quote did not include an executable transaction.",
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
            raw_execution=transaction_payload,
        )

    def to_prepared_transaction(self, execution: SwapExecution) -> PreparedTransaction:
        """Convert a normalized LiFi EVM execution into the Phase 6 transaction model."""

        if execution.transaction is None:
            raise SwapProviderError("LiFi execution has no EVM transaction.")
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

    def _normalize_quote(self, request: SwapQuoteRequest, payload: dict[str, Any]) -> SwapQuote:
        estimate = payload.get("estimate")
        action = payload.get("action")
        if not isinstance(estimate, dict) or not isinstance(action, dict):
            raise SwapProviderError("LiFi quote response missing estimate or action.")

        route_id = _route_id(payload)
        from_chain_id = require_int(action, "fromChainId")
        to_chain_id = require_int(action, "toChainId")
        spender = _spender(payload, estimate)
        expected_out = require_int(estimate, "toAmount")
        min_out = optional_int(estimate, "toAmountMin")
        expires_at = _expiry(payload, estimate)
        route_kind = SwapRouteKind.BRIDGE if from_chain_id != to_chain_id else SwapRouteKind.SWAP

        route = SwapRoute(
            provider=self.name,
            route_id=route_id,
            route_kind=route_kind,
            from_chain_id=from_chain_id,
            to_chain_id=to_chain_id,
            from_token=require_string(action, "fromToken"),
            to_token=require_string(action, "toToken"),
            spender_address=spender,
            steps=_steps(payload),
        )
        return SwapQuote(
            provider=self.name,
            request=request,
            route=route,
            amount_in_raw=require_int(estimate, "fromAmount"),
            expected_amount_out_raw=expected_out,
            min_amount_out_raw=min_out,
            slippage_bps=request.max_slippage_bps,
            expires_at=expires_at,
            recipient_address=request.effective_recipient,
            raw_quote=payload,
        )


def _headers(config: SwapProviderConfig) -> dict[str, str]:
    api_key = provider_api_key(config)
    return {"x-lifi-api-key": api_key} if api_key else {}


def _slippage_float(slippage_bps: int | None) -> float | None:
    if slippage_bps is None:
        return None
    return slippage_bps / 10_000


def _route_id(payload: dict[str, Any]) -> str:
    for key in ("id", "tool"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return "lifi-route"


def _spender(payload: dict[str, Any], estimate: dict[str, Any]) -> str | None:
    for source in (payload, estimate):
        for key in ("approvalAddress", "spenderAddress", "spender"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def _expiry(payload: dict[str, Any], estimate: dict[str, Any]) -> datetime:
    for source in (payload, estimate):
        value = source.get("expiresAt")
        if isinstance(value, str) and value.strip():
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        if isinstance(value, int):
            return datetime.fromtimestamp(value, tz=UTC)
    return datetime.now(tz=UTC) + timedelta(minutes=5)


def _steps(payload: dict[str, Any]) -> tuple[str, ...]:
    included_steps = payload.get("includedSteps")
    if not isinstance(included_steps, list):
        return ()
    names: list[str] = []
    for step in included_steps:
        if isinstance(step, dict):
            tool = step.get("tool")
            if isinstance(tool, str) and tool.strip():
                names.append(tool)
    return tuple(names)
