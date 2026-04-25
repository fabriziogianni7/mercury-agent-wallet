"""LangGraph state definition."""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from mercury.models import ChainReference, PolicyDecision, WalletIntent


class MercuryState(TypedDict, total=False):
    """State shared by the Phase 1 graph skeleton."""

    messages: Annotated[list[BaseMessage], add_messages]
    request_id: str
    chain_reference: ChainReference
    intent: WalletIntent
    read_result: dict[str, Any]
    policy_decision: PolicyDecision
    error: str
