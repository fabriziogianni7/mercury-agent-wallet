"""User-facing response formatting for read-only graph execution."""

from __future__ import annotations

from typing import Any

from mercury.graph.intents import ReadOnlyIntentKind

_SECRET_MARKERS = ("http://", "https://", "mercury/rpc/", "private_key")


def sanitize_error(error: BaseException | str) -> str:
    """Return a user-safe error string without RPC URLs or secret paths."""

    message = str(error)
    if not message:
        return "The read-only request failed."
    if any(marker in message for marker in _SECRET_MARKERS):
        return "The read-only request failed because required chain configuration is unavailable."
    return message


def format_success_response(
    *,
    intent_kind: str,
    tool_result: dict[str, Any],
) -> str:
    """Format a successful read-only tool result."""

    if intent_kind == ReadOnlyIntentKind.NATIVE_BALANCE.value:
        return (
            f"{tool_result['wallet_address']} has {tool_result['formatted']} "
            f"{tool_result['symbol']} on {tool_result['chain']}."
        )
    if intent_kind == ReadOnlyIntentKind.ERC20_BALANCE.value:
        symbol = _symbol(tool_result)
        return (
            f"{tool_result['wallet_address']} has {tool_result['formatted']} {symbol} "
            f"on {tool_result['chain']}."
        )
    if intent_kind == ReadOnlyIntentKind.ERC20_ALLOWANCE.value:
        symbol = _symbol(tool_result)
        return (
            f"{tool_result['spender_address']} is allowed to spend {tool_result['formatted']} "
            f"{symbol} from {tool_result['owner_address']} on {tool_result['chain']}."
        )
    if intent_kind == ReadOnlyIntentKind.ERC20_METADATA.value:
        name = tool_result.get("name") or "ERC20 token"
        symbol = _symbol(tool_result)
        return (
            f"{name} ({symbol}) on {tool_result['chain']} has "
            f"{tool_result['decimals']} decimals."
        )
    if intent_kind == ReadOnlyIntentKind.CONTRACT_READ.value:
        return (
            f"{tool_result['function_name']} returned {tool_result['result']!r} "
            f"on {tool_result['chain']}."
        )
    return "Read-only request completed."


def format_error_response(error: str) -> str:
    """Format a sanitized error response."""

    return f"I could not complete the read-only request: {sanitize_error(error)}"


def format_unsupported_response(reason: str) -> str:
    """Format unsupported intents without suggesting execution happened."""

    return f"Unsupported operation: {sanitize_error(reason)}"


def _symbol(tool_result: dict[str, Any]) -> str:
    symbol = tool_result.get("symbol")
    if isinstance(symbol, str) and symbol:
        return symbol
    return "tokens"
