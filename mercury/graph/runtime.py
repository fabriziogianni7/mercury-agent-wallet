"""Fakeable runtime boundary for invoking Mercury graphs from services."""

from __future__ import annotations

from typing import Any, Protocol, cast, runtime_checkable

from mercury.graph.agent import (
    build_erc20_transaction_graph,
    build_graph,
    build_swap_transaction_graph,
)
from mercury.graph.nodes_erc20 import ERC20GraphDependencies
from mercury.graph.nodes_swaps import SwapGraphDependencies
from mercury.graph.nodes_transaction import TransactionGraphDependencies
from mercury.graph.state import MercuryState
from mercury.tools.registry import ReadOnlyToolRegistry


@runtime_checkable
class InvokableGraph(Protocol):
    """Compiled LangGraph-like object used behind the service runtime."""

    def invoke(self, input: Any, *args: Any, **kwargs: Any) -> Any:
        """Invoke the graph and return its final state."""


@runtime_checkable
class GraphRuntime(Protocol):
    """Service-facing runtime interface that tests can replace."""

    def invoke(self, state: MercuryState) -> MercuryState:
        """Invoke Mercury for an already-normalized graph state."""


class MercuryGraphRuntime:
    """Route service requests to the appropriate Mercury graph."""

    def __init__(
        self,
        *,
        read_graph: InvokableGraph,
        erc20_graph: InvokableGraph,
        swap_graph: InvokableGraph,
    ) -> None:
        self._read_graph = read_graph
        self._erc20_graph = erc20_graph
        self._swap_graph = swap_graph

    def invoke(self, state: MercuryState) -> MercuryState:
        """Invoke the graph that matches the request intent kind."""

        graph = self._graph_for_state(state)
        return cast(MercuryState, graph.invoke(state))

    def _graph_for_state(self, state: MercuryState) -> InvokableGraph:
        raw_input = state.get("raw_input")
        if isinstance(raw_input, dict):
            payload = raw_input.get("intent")
            if not isinstance(payload, dict):
                payload = raw_input
            kind = str(payload.get("kind", "")).strip().lower()
            if kind in {"erc20_transfer", "erc20_approval"}:
                return self._erc20_graph
            if kind == "swap":
                return self._swap_graph
        return self._read_graph


def build_default_runtime(
    *,
    registry: ReadOnlyToolRegistry,
    erc20_deps: ERC20GraphDependencies,
    swap_deps: SwapGraphDependencies,
    transaction_deps: TransactionGraphDependencies,
) -> MercuryGraphRuntime:
    """Build Mercury's default compiled graphs from injectable dependencies."""

    return MercuryGraphRuntime(
        read_graph=build_graph(registry).compile(),
        erc20_graph=build_erc20_transaction_graph(erc20_deps, transaction_deps).compile(),
        swap_graph=build_swap_transaction_graph(swap_deps, transaction_deps).compile(),
    )
