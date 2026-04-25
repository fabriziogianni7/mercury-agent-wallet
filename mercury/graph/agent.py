"""LangGraph construction for Mercury read-only execution."""

from typing import Any, cast

from langgraph.graph import END, START, StateGraph

from mercury.graph.nodes import (
    format_response,
    make_read_tool_node,
    parse_intent,
    resolve_chain,
    unsupported_response,
)
from mercury.graph.router import (
    ROUTE_CONTRACT_READ,
    ROUTE_ERC20_ALLOWANCE,
    ROUTE_ERC20_BALANCE,
    ROUTE_ERC20_METADATA,
    ROUTE_FORMAT_RESPONSE,
    ROUTE_NATIVE_BALANCE,
    ROUTE_RESOLVE_CHAIN,
    ROUTE_UNSUPPORTED,
    route_after_chain,
    route_after_parse,
)
from mercury.graph.state import MercuryState
from mercury.tools.registry import ReadOnlyToolRegistry


def build_graph(registry: ReadOnlyToolRegistry | None = None) -> StateGraph[MercuryState]:
    """Build the uncompiled read-only graph.

    Callers may inject a registry backed by fake tools or providers. The module-level
    graph intentionally compiles without tools so imports never require live RPC.
    """

    tool_registry = registry or ReadOnlyToolRegistry()

    builder = StateGraph(MercuryState)
    builder.add_node("parse_intent", parse_intent)
    builder.add_node("resolve_chain", resolve_chain)
    builder.add_node("unsupported_response", unsupported_response)
    builder.add_node(
        "get_native_balance",
        cast(Any, make_read_tool_node("get_native_balance", tool_registry)),
    )
    builder.add_node(
        "get_erc20_balance",
        cast(Any, make_read_tool_node("get_erc20_balance", tool_registry)),
    )
    builder.add_node(
        "get_erc20_allowance",
        cast(Any, make_read_tool_node("get_erc20_allowance", tool_registry)),
    )
    builder.add_node(
        "get_erc20_metadata",
        cast(Any, make_read_tool_node("get_erc20_metadata", tool_registry)),
    )
    builder.add_node(
        "read_contract",
        cast(Any, make_read_tool_node("read_contract", tool_registry)),
    )
    builder.add_node("format_response", format_response)

    builder.add_edge(START, "parse_intent")
    builder.add_conditional_edges(
        "parse_intent",
        route_after_parse,
        {
            ROUTE_UNSUPPORTED: "unsupported_response",
            ROUTE_RESOLVE_CHAIN: "resolve_chain",
        },
    )
    builder.add_conditional_edges(
        "resolve_chain",
        route_after_chain,
        {
            ROUTE_NATIVE_BALANCE: "get_native_balance",
            ROUTE_ERC20_BALANCE: "get_erc20_balance",
            ROUTE_ERC20_ALLOWANCE: "get_erc20_allowance",
            ROUTE_ERC20_METADATA: "get_erc20_metadata",
            ROUTE_CONTRACT_READ: "read_contract",
            ROUTE_FORMAT_RESPONSE: "format_response",
        },
    )
    builder.add_edge("get_native_balance", "format_response")
    builder.add_edge("get_erc20_balance", "format_response")
    builder.add_edge("get_erc20_allowance", "format_response")
    builder.add_edge("get_erc20_metadata", "format_response")
    builder.add_edge("read_contract", "format_response")
    builder.add_edge("unsupported_response", END)
    builder.add_edge("format_response", END)

    return builder


graph = build_graph().compile()
