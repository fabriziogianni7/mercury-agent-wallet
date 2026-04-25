"""Routing helpers for the read-only graph."""

from mercury.graph.intents import ReadOnlyIntentKind
from mercury.graph.state import MercuryState

ROUTE_UNSUPPORTED = "unsupported_response"
ROUTE_RESOLVE_CHAIN = "resolve_chain"
ROUTE_NATIVE_BALANCE = "get_native_balance"
ROUTE_ERC20_BALANCE = "get_erc20_balance"
ROUTE_ERC20_ALLOWANCE = "get_erc20_allowance"
ROUTE_ERC20_METADATA = "get_erc20_metadata"
ROUTE_CONTRACT_READ = "read_contract"
ROUTE_FORMAT_RESPONSE = "format_response"

_READ_ROUTES = {
    ReadOnlyIntentKind.NATIVE_BALANCE.value: ROUTE_NATIVE_BALANCE,
    ReadOnlyIntentKind.ERC20_BALANCE.value: ROUTE_ERC20_BALANCE,
    ReadOnlyIntentKind.ERC20_ALLOWANCE.value: ROUTE_ERC20_ALLOWANCE,
    ReadOnlyIntentKind.ERC20_METADATA.value: ROUTE_ERC20_METADATA,
    ReadOnlyIntentKind.CONTRACT_READ.value: ROUTE_CONTRACT_READ,
}


def route_after_parse(state: MercuryState) -> str:
    """Route unsupported or invalid input away from tool execution."""

    parsed_intent = state.get("parsed_intent", {})
    if state.get("error") or parsed_intent.get("kind") == ReadOnlyIntentKind.UNSUPPORTED.value:
        return ROUTE_UNSUPPORTED
    return ROUTE_RESOLVE_CHAIN


def route_after_chain(state: MercuryState) -> str:
    """Route chain resolution errors to response formatting."""

    if state.get("error"):
        return ROUTE_FORMAT_RESPONSE
    return route_read_tool(state)


def route_read_tool(state: MercuryState) -> str:
    """Return the read-only tool node for the parsed intent."""

    parsed_intent = state.get("parsed_intent", {})
    kind = parsed_intent.get("kind")
    if isinstance(kind, str):
        return _READ_ROUTES.get(kind, ROUTE_FORMAT_RESPONSE)
    return ROUTE_FORMAT_RESPONSE
