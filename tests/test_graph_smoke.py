from langchain_core.messages import AIMessage, HumanMessage
from mercury.graph.agent import build_graph, graph


def test_graph_imports_successfully() -> None:
    assert graph is not None


def test_graph_compiles_successfully() -> None:
    compiled_graph = build_graph().compile()

    assert compiled_graph is not None


def test_basic_invocation_returns_placeholder_response() -> None:
    result = graph.invoke({"messages": [HumanMessage(content="Can you check my ETH balance?")]})

    assert isinstance(result["messages"][-1], AIMessage)
    assert result["parsed_intent"]["kind"] == "unsupported"
    assert "structured read-only intent" in result["messages"][-1].content
