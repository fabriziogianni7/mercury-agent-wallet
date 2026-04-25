"""LangGraph state definition."""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from mercury.models import ChainConfig, ChainReference, PolicyDecision, WalletIntent
from mercury.models.approval import ApprovalResult
from mercury.models.execution import ExecutableTransaction, ExecutionResult, PreparedTransaction
from mercury.models.signing import SignedTransactionResult
from mercury.models.simulation import SimulationResult
from mercury.tools.swaps import PreparedSwap


class MercuryState(TypedDict, total=False):
    """State shared by Mercury's read-only LangGraph runtime."""

    messages: Annotated[list[BaseMessage], add_messages]
    request_id: str
    raw_input: Any
    parsed_intent: dict[str, Any]
    chain_name: str
    chain_config: ChainConfig
    chain_reference: ChainReference
    selected_tool_name: str
    tool_input: dict[str, Any]
    tool_result: dict[str, Any]
    response_text: str
    intent: WalletIntent
    read_result: dict[str, Any]
    policy_decision: PolicyDecision
    prepared_transaction: PreparedTransaction | dict[str, Any]
    prepared_swap: PreparedSwap
    executable_transaction: ExecutableTransaction
    simulation_result: SimulationResult
    approval_result: ApprovalResult
    signed_transaction: SignedTransactionResult
    tx_hash: str
    execution_result: ExecutionResult
    wallet_address: str
    error: str
