"""Placeholder graph nodes for Phase 1."""

from langchain_core.messages import AIMessage

from mercury.chains import get_default_chain
from mercury.graph.state import MercuryState


def parse_intent(state: MercuryState) -> MercuryState:
    """Placeholder intent parser.

    Future phases will parse user requests into typed intents. Phase 1 only marks
    that parsing has not been implemented.
    """

    return {
        "read_result": {
            **state.get("read_result", {}),
            "intent_parser": "placeholder",
        }
    }


def resolve_chain(state: MercuryState) -> MercuryState:
    """Resolve the default chain without making network calls."""

    if "chain_reference" in state:
        return {}

    return {"chain_reference": get_default_chain().to_reference()}


def respond(state: MercuryState) -> MercuryState:
    """Return a placeholder assistant response."""

    chain_reference = state.get("chain_reference")
    chain_name = chain_reference.name if chain_reference is not None else "unknown"
    return {
        "messages": [
            AIMessage(
                content=(
                    "Mercury Phase 1 foundation is ready. "
                    f"Default chain: {chain_name}. "
                    "Wallet actions are placeholders only."
                )
            )
        ]
    }
