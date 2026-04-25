"""LangGraph nodes for read-only Mercury execution."""

from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage

from mercury.chains import UnsupportedChainError, get_chain_by_name, get_default_chain
from mercury.graph.intents import ReadOnlyIntentKind, UnsupportedIntentError, parse_readonly_intent
from mercury.graph.responses import (
    format_error_response,
    format_success_response,
    format_unsupported_response,
    sanitize_error,
)
from mercury.graph.state import MercuryState
from mercury.tools.registry import ReadOnlyToolRegistry


def parse_intent(state: MercuryState) -> MercuryState:
    """Parse structured read-only input into graph state."""

    try:
        parsed_intent = parse_readonly_intent(state.get("raw_input"), state.get("messages"))
    except UnsupportedIntentError as exc:
        return {"error": sanitize_error(exc)}

    return {
        "parsed_intent": parsed_intent.model_dump(mode="json"),
        "read_result": {"intent_kind": parsed_intent.kind.value},
    }


def resolve_chain(state: MercuryState) -> MercuryState:
    """Resolve the requested chain, defaulting to Ethereum."""

    parsed_intent = state.get("parsed_intent", {})
    chain_name = parsed_intent.get("chain")
    if not isinstance(chain_name, str) or not chain_name:
        chain_name = get_default_chain().name

    try:
        chain_config = get_chain_by_name(chain_name)
    except UnsupportedChainError as exc:
        return {"error": sanitize_error(exc), "chain_name": chain_name}

    return {
        "chain_name": chain_config.name,
        "chain_config": chain_config,
        "chain_reference": chain_config.to_reference(),
    }


def make_read_tool_node(
    tool_name: str,
    registry: ReadOnlyToolRegistry,
) -> Callable[[MercuryState], MercuryState]:
    """Create a graph node that executes one read-only tool."""

    def execute_read_tool(state: MercuryState) -> MercuryState:
        tool_input = _tool_input_for_state(state)
        try:
            tool_result = registry.execute(tool_name, tool_input)
        except Exception as exc:
            return {
                "selected_tool_name": tool_name,
                "tool_input": tool_input,
                "error": sanitize_error(exc),
            }

        return {
            "selected_tool_name": tool_name,
            "tool_input": tool_input,
            "tool_result": tool_result,
            "read_result": tool_result,
        }

    return execute_read_tool


def format_response(state: MercuryState) -> MercuryState:
    """Format successful or failed read-only execution."""

    if state.get("error"):
        response_text = format_error_response(state["error"])
    else:
        parsed_intent = state.get("parsed_intent", {})
        intent_kind = parsed_intent.get("kind", "")
        response_text = format_success_response(
            intent_kind=str(intent_kind),
            tool_result=state.get("tool_result", {}),
        )

    return {"response_text": response_text, "messages": [AIMessage(content=response_text)]}


def unsupported_response(state: MercuryState) -> MercuryState:
    """Return a clear response for unsupported or invalid intents."""

    parsed_intent = state.get("parsed_intent", {})
    reason = state.get("error")
    if reason is None:
        raw_reason = parsed_intent.get("reason")
        reason = raw_reason if isinstance(raw_reason, str) else "Unsupported wallet intent."

    response_text = format_unsupported_response(reason)
    return {"response_text": response_text, "messages": [AIMessage(content=response_text)]}


def respond(state: MercuryState) -> MercuryState:
    """Compatibility alias for older smoke tests."""

    return format_response(state)


def _tool_input_for_state(state: MercuryState) -> dict[str, Any]:
    parsed_intent = state.get("parsed_intent", {})
    chain_name = state.get("chain_name", get_default_chain().name)
    intent_kind = parsed_intent.get("kind")
    base = {"chain": chain_name}

    if intent_kind == ReadOnlyIntentKind.NATIVE_BALANCE.value:
        return {**base, "wallet_address": parsed_intent["wallet_address"]}
    if intent_kind == ReadOnlyIntentKind.ERC20_BALANCE.value:
        return {
            **base,
            "token_address": parsed_intent["token_address"],
            "wallet_address": parsed_intent["wallet_address"],
        }
    if intent_kind == ReadOnlyIntentKind.ERC20_ALLOWANCE.value:
        return {
            **base,
            "token_address": parsed_intent["token_address"],
            "owner_address": parsed_intent["owner_address"],
            "spender_address": parsed_intent["spender_address"],
        }
    if intent_kind == ReadOnlyIntentKind.ERC20_METADATA.value:
        return {**base, "token_address": parsed_intent["token_address"]}
    if intent_kind == ReadOnlyIntentKind.CONTRACT_READ.value:
        return {
            **base,
            "contract_address": parsed_intent["contract_address"],
            "abi_fragment": parsed_intent["abi_fragment"],
            "function_name": parsed_intent["function_name"],
            "args": parsed_intent.get("args", []),
        }

    msg = f"Unsupported read-only intent kind: {intent_kind}."
    raise ValueError(msg)
