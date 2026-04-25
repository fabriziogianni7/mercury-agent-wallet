"""LangGraph construction for the Phase 1 Mercury skeleton."""

from langgraph.graph import END, START, StateGraph

from mercury.graph.nodes import parse_intent, resolve_chain, respond
from mercury.graph.state import MercuryState


def build_graph() -> StateGraph[MercuryState]:
    """Build the uncompiled Phase 1 graph."""

    builder = StateGraph(MercuryState)
    builder.add_node("parse_intent", parse_intent)
    builder.add_node("resolve_chain", resolve_chain)
    builder.add_node("respond", respond)

    builder.add_edge(START, "parse_intent")
    builder.add_edge("parse_intent", "resolve_chain")
    builder.add_edge("resolve_chain", "respond")
    builder.add_edge("respond", END)

    return builder


graph = build_graph().compile()
