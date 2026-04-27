from typing import Any

from mercury.graph.agent import build_native_transaction_graph
from mercury.graph.nodes_native import NativeGraphDependencies, route_native_intent
from mercury.graph.nodes_transaction import TransactionGraphDependencies
from mercury.models import ExecutionStatus, GasFees, SignedTransactionResult
from mercury.models.approval import ApprovalRequest, ApprovalResult, ApprovalStatus
from mercury.models.execution import ExecutableTransaction, PreparedTransaction, TransactionReceipt
from mercury.models.signing import SignTransactionRequest
from mercury.models.simulation import SimulationResult, SimulationStatus
from mercury.models.wallets import WalletAddressResult
from mercury.policy.idempotency import InMemoryIdempotencyStore
from mercury.policy.risk import TransactionPolicyEngine

WALLET = "0x000000000000000000000000000000000000bEEF"
RECIPIENT = "0x000000000000000000000000000000000000dEaD"


def test_native_transfer_intent_runs_pipeline() -> None:
    events: list[str] = []
    signer = FakeSigner(events)
    graph = _graph(events, signer)

    result = graph.invoke(
        {
            "raw_input": {
                "kind": "native_transfer",
                "chain": "base",
                "wallet_id": "primary",
                "recipient_address": RECIPIENT,
                "amount": "0.000000001",
                "idempotency_key": "native-route-1",
            }
        }
    )

    assert result["execution_result"].status == ExecutionStatus.CONFIRMED
    assert result["prepared_transaction"].metadata["action"] == "native_transfer"
    assert result["prepared_transaction"].to == RECIPIENT
    assert result["prepared_transaction"].value_wei > 0
    assert "sign" in events


def test_route_native_intent_rejects_other_kinds() -> None:
    assert route_native_intent({"raw_input": {"kind": "erc20_transfer"}}) == "unsupported_response"


class FakeSigner:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def get_wallet_address(self, wallet_id: str) -> WalletAddressResult:
        self._events.append("address")
        return WalletAddressResult(wallet_id=wallet_id, address=WALLET)

    def sign_transaction(self, request: SignTransactionRequest) -> SignedTransactionResult:
        self._events.append("sign")
        assert request.prepared_transaction.transaction["to"] == RECIPIENT
        return SignedTransactionResult(
            wallet_id=request.wallet.wallet_id,
            chain_id=request.chain_id,
            signer_address=WALLET,
            raw_transaction_hex="0x02",
            tx_hash="0xabcd",
        )


class FakeApprover:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def request_approval(self, request: ApprovalRequest) -> ApprovalResult:
        self._events.append("approval")
        assert request.to == RECIPIENT
        assert request.metadata["action"] == "native_transfer"
        return ApprovalResult(
            status=ApprovalStatus.APPROVED,
            reason="approved",
            approved_by="test",
        )


class FakeBackend:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def resolve_chain_id(self, transaction: PreparedTransaction) -> int:
        return transaction.chain_id or 8453

    def lookup_nonce(self, transaction: PreparedTransaction, wallet_address: str) -> int:
        self._events.append("nonce")
        return 1

    def populate_gas(self, transaction: PreparedTransaction | ExecutableTransaction) -> GasFees:
        self._events.append("gas")
        return GasFees(gas_limit=21_000, gas_price=1_000_000_000)

    def simulate(self, transaction: ExecutableTransaction) -> SimulationResult:
        self._events.append("simulate")
        return SimulationResult(status=SimulationStatus.PASSED, gas_estimate=21_000)

    def broadcast(self, signed_transaction: SignedTransactionResult) -> str:
        self._events.append("broadcast")
        return "0xbeef"

    def wait_for_receipt(
        self,
        *,
        chain: str,
        tx_hash: str,
        timeout_seconds: float,
        confirmations: int,
    ) -> TransactionReceipt:
        self._events.append("monitor")
        return TransactionReceipt(tx_hash=tx_hash, status=ExecutionStatus.CONFIRMED)


def _graph(events: list[str], signer: FakeSigner) -> Any:
    return build_native_transaction_graph(
        NativeGraphDependencies(address_resolver=signer),
        TransactionGraphDependencies(
            backend=FakeBackend(events),
            signer=signer,
            policy_engine=TransactionPolicyEngine(),
            approver=FakeApprover(events),
            idempotency_store=InMemoryIdempotencyStore(),
        ),
    ).compile()
