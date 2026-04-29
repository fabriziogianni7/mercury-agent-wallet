#!/usr/bin/env python3
"""Print or write Mermaid diagrams for Mercury LangGraph StateGraphs.

Graph structure (nodes + edges) lives in ``mercury/graph/agent.py``:

* ``build_graph`` — read-only flow (balance, metadata, contract read, …).
* ``build_erc20_transaction_graph`` / ``build_native_transaction_graph`` /
  ``build_swap_transaction_graph`` — value-moving prep + shared pipeline.
* ``_add_transaction_pipeline`` — nonce → gas → simulate → policy → approval →
  idempotency → sign → broadcast → monitor (shared by ERC-20, native, swap).

Service-side routing (which compiled graph runs for a given intent) is in
``mercury/graph/runtime.py`` (``MercuryGraphRuntime._graph_for_state``).

This script only **compiles** graphs with stub dependencies so LangGraph can export
structure; it does not invoke RPC or signers.

Examples::

  uv run python scripts/export_mercury_graph_mermaid.py --graph read
  uv run python scripts/export_mercury_graph_mermaid.py --graph all --out-dir ./docs/graphs

"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `uv run python scripts/export_mercury_graph_mermaid.py` without PYTHONPATH=
_REPO_ROOT = Path(__file__).resolve().parents[1]
_repo = str(_REPO_ROOT)
if _repo not in sys.path:
    sys.path.insert(0, _repo)

from typing import Literal

from mercury.graph.agent import (
    build_erc20_transaction_graph,
    build_graph,
    build_native_transaction_graph,
    build_swap_transaction_graph,
)
from mercury.graph.nodes_erc20 import ERC20GraphDependencies
from mercury.graph.nodes_native import NativeGraphDependencies
from mercury.graph.nodes_swaps import SwapGraphDependencies
from mercury.graph.nodes_transaction import TransactionGraphDependencies
from mercury.models.execution import (
    ExecutionStatus,
    PreparedTransaction,
    TransactionReceipt,
)
from mercury.models.gas import GasFees
from mercury.models.signing import SignedTransactionResult, SignTransactionRequest
from mercury.models.simulation import SimulationResult, SimulationStatus
from mercury.models.wallets import WalletAddressResult
from mercury.policy.idempotency import InMemoryIdempotencyStore
from mercury.policy.risk import TransactionPolicyEngine
from mercury.swaps.router import SwapRouter
from mercury.tools.registry import ReadOnlyToolRegistry
from mercury.tools.transactions import PlaceholderTransactionApprover

ZERO = "0x" + "00" * 20


class StubProviderFactory:
    """Compile-time placeholder; real runs use an RPC-backed factory."""

    def create(self, chain: str):  # pragma: no cover - only for graph export
        raise RuntimeError("StubProviderFactory is for Mermaid export only.")


class StubAddressResolver:
    def get_wallet_address(self, wallet_id: str) -> WalletAddressResult:
        return WalletAddressResult(wallet_id=wallet_id, address=ZERO)


class StubTransactionBackend:
    def resolve_chain_id(self, transaction: PreparedTransaction) -> int:
        return transaction.chain_id or 1

    def lookup_nonce(self, transaction: PreparedTransaction, wallet_address: str) -> int:
        return 0

    def populate_gas(
        self,
        transaction: PreparedTransaction,
    ) -> GasFees:
        return GasFees(gas_limit=21000, gas_price=1)

    def simulate(self, transaction: object) -> SimulationResult:
        return SimulationResult(status=SimulationStatus.PASSED, gas_estimate=21000)

    def broadcast(self, signed_transaction: SignedTransactionResult) -> str:
        return "0xdeadbeef"

    def wait_for_receipt(
        self,
        *,
        chain: str,
        tx_hash: str,
        timeout_seconds: float,
        confirmations: int,
    ) -> TransactionReceipt:
        return TransactionReceipt(tx_hash=tx_hash, status=ExecutionStatus.CONFIRMED)


class StubTransactionSigner:
    def get_wallet_address(self, wallet_id: str) -> WalletAddressResult:
        return WalletAddressResult(wallet_id=wallet_id, address=ZERO)

    def sign_transaction(self, request: SignTransactionRequest) -> SignedTransactionResult:
        return SignedTransactionResult(
            wallet_id=request.wallet.wallet_id,
            chain_id=request.chain_id,
            signer_address=ZERO,
            raw_transaction_hex="0x02",
            tx_hash="0xabcd",
        )


def _transaction_dependencies() -> TransactionGraphDependencies:
    return TransactionGraphDependencies(
        backend=StubTransactionBackend(),
        signer=StubTransactionSigner(),
        policy_engine=TransactionPolicyEngine(),
        approver=PlaceholderTransactionApprover(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


def _compile(name: Literal["read", "erc20", "native", "swap"]) -> object:
    tx = _transaction_dependencies()
    resolver = StubAddressResolver()
    stub_factory = StubProviderFactory()
    match name:
        case "read":
            return build_graph(ReadOnlyToolRegistry()).compile()
        case "erc20":
            return build_erc20_transaction_graph(
                ERC20GraphDependencies(
                    provider_factory=stub_factory,
                    address_resolver=resolver,
                ),
                tx,
            ).compile()
        case "native":
            return build_native_transaction_graph(
                NativeGraphDependencies(address_resolver=resolver),
                tx,
            ).compile()
        case "swap":
            return build_swap_transaction_graph(
                SwapGraphDependencies(
                    router=SwapRouter([]),
                    provider_factory=stub_factory,
                    address_resolver=resolver,
                ),
                tx,
            ).compile()


def _draw_mermaid(compiled: object) -> str:
    return compiled.get_graph().draw_mermaid(with_styles=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Mermaid diagrams for Mercury LangGraph compiled graphs."
    )
    parser.add_argument(
        "--graph",
        action="append",
        choices=("read", "erc20", "native", "swap", "all"),
        help="Graph to export (repeatable). Default: read. Use 'all' for every graph.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Write a single graph to this file instead of stdout (--graph must be one graph).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Write mercury_<name>.mmd files here (use with --graph all or multiple --graph).",
    )
    args = parser.parse_args()
    names: list[str]
    if args.graph is None:
        names = ["read"]
    elif "all" in args.graph:
        if len(args.graph) > 1:
            parser.error("'all' cannot be combined with other graph names.")
        names = ["read", "erc20", "native", "swap"]
    else:
        names = list(dict.fromkeys(args.graph))

    if args.out and len(names) > 1:
        parser.error("--out requires exactly one --graph.")

    if args.out and args.out_dir:
        parser.error("Use either --out or --out-dir, not both.")

    if args.out_dir is not None and not args.out_dir.exists():
        args.out_dir.mkdir(parents=True)

    if args.out is not None:
        name = names[0]
        mermaid = _draw_mermaid(_compile(name))  # type: ignore[arg-type]
        args.out.parent.mkdir(parents=True, exist_ok=True)
        text = mermaid + ("" if mermaid.endswith("\n") else "\n")
        args.out.write_text(text)
        print(f"Wrote {args.out}")
        return

    for name in names:
        mermaid = _draw_mermaid(_compile(name))  # type: ignore[arg-type]
        if args.out_dir is not None:
            path = args.out_dir / f"mercury_{name}.mmd"
            text = mermaid + ("" if mermaid.endswith("\n") else "\n")
            path.write_text(text)
            print(f"Wrote {path}")
        else:
            print(f"%% mercury graph: {name}\n{mermaid}\n")


if __name__ == "__main__":
    main()
