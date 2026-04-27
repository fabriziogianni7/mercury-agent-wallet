from typing import Any

from mercury.graph.agent import build_erc20_transaction_graph
from mercury.graph.nodes_erc20 import ERC20GraphDependencies, route_erc20_intent
from mercury.graph.nodes_transaction import TransactionGraphDependencies
from mercury.models import ExecutionStatus, GasFees, PreparedTransaction, SignedTransactionResult
from mercury.models.approval import ApprovalRequest, ApprovalResult, ApprovalStatus
from mercury.models.execution import ExecutableTransaction, TransactionReceipt
from mercury.models.signing import SignTransactionRequest
from mercury.models.simulation import SimulationResult, SimulationStatus
from mercury.models.wallets import WalletAddressResult
from mercury.policy.idempotency import InMemoryIdempotencyStore
from mercury.policy.risk import TransactionPolicyEngine
from tests.test_evm_read_tools import FakeEth, FakeProviderFactory, FakeWeb3

TOKEN = "0x000000000000000000000000000000000000cafE"
WALLET = "0x000000000000000000000000000000000000bEEF"
RECIPIENT = "0x000000000000000000000000000000000000dEaD"
SPENDER = "0x0000000000000000000000000000000000000002"


def test_erc20_transfer_intent_routes_to_builder_then_pipeline() -> None:
    events: list[str] = []
    signer = FakeSigner(events)
    graph = _graph(
        events,
        signer,
        {
            ("decimals", ()): 6,
            ("symbol", ()): "USDC",
            ("balanceOf", (WALLET,)): 2_000_000,
        },
    )

    result = graph.invoke(
        {
            "raw_input": {
                "kind": "erc20_transfer",
                "chain": "base",
                "wallet_id": "primary",
                "token_address": TOKEN,
                "recipient_address": RECIPIENT,
                "amount": "1.5",
                "idempotency_key": "erc20-transfer-route",
            }
        }
    )

    assert result["execution_result"].status == ExecutionStatus.CONFIRMED
    assert result["prepared_transaction"].metadata["action"] == "erc20_transfer"
    assert result["prepared_transaction"].to == TOKEN
    assert result["prepared_transaction"].data.startswith("0xa9059cbb")
    assert events == [
        "address",
        "address",
        "nonce",
        "gas",
        "simulate",
        "approval",
        "sign",
        "broadcast",
        "monitor",
    ]


def test_erc20_approval_intent_routes_to_builder_then_pipeline() -> None:
    events: list[str] = []
    signer = FakeSigner(events)
    graph = _graph(
        events,
        signer,
        {
            ("decimals", ()): 18,
            ("symbol", ()): "TOK",
            ("allowance", (WALLET, SPENDER)): 0,
        },
    )

    result = graph.invoke(
        {
            "raw_input": {
                "kind": "erc20_approval",
                "chain": "ethereum",
                "wallet_id": "primary",
                "token_address": TOKEN,
                "spender_address": SPENDER,
                "amount": "2.5",
                "idempotency_key": "erc20-approval-route",
                "spender_known": True,
            }
        }
    )

    assert result["execution_result"].status == ExecutionStatus.CONFIRMED
    assert result["prepared_transaction"].metadata["action"] == "erc20_approval"
    assert result["prepared_transaction"].metadata["spender_address"] == SPENDER
    assert result["prepared_transaction"].data.startswith("0x095ea7b3")
    assert "sign" in events
    assert "broadcast" in events


def test_route_erc20_intent_rejects_non_erc20_payload() -> None:
    assert route_erc20_intent({"raw_input": {"kind": "native_balance"}}) == "unsupported_response"


class FakeSigner:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def get_wallet_address(self, wallet_id: str) -> WalletAddressResult:
        self._events.append("address")
        return WalletAddressResult(wallet_id=wallet_id, address=WALLET)

    def sign_transaction(self, request: SignTransactionRequest) -> SignedTransactionResult:
        self._events.append("sign")
        assert request.prepared_transaction.transaction["to"] == TOKEN
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
        assert request.to == TOKEN
        assert request.metadata["action"] in {"erc20_transfer", "erc20_approval"}
        return ApprovalResult(
            status=ApprovalStatus.APPROVED,
            reason="approved",
            approved_by="test",
        )


class FakeBackend:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def resolve_chain_id(self, transaction: PreparedTransaction) -> int:
        return transaction.chain_id or 1

    def lookup_nonce(self, transaction: PreparedTransaction, wallet_address: str) -> int:
        self._events.append("nonce")
        assert wallet_address == WALLET
        return 9

    def populate_gas(self, transaction: PreparedTransaction | ExecutableTransaction) -> GasFees:
        self._events.append("gas")
        return GasFees(gas_limit=50_000, gas_price=1_000_000_000)

    def simulate(self, transaction: ExecutableTransaction) -> SimulationResult:
        self._events.append("simulate")
        return SimulationResult(status=SimulationStatus.PASSED, gas_estimate=50_000)

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


def _graph(
    events: list[str],
    signer: FakeSigner,
    contract_responses: dict[tuple[str, tuple[Any, ...]], Any],
) -> Any:
    factory = FakeProviderFactory(FakeWeb3(FakeEth(contract_responses=contract_responses)))
    return build_erc20_transaction_graph(
        ERC20GraphDependencies(provider_factory=factory, address_resolver=signer),
        TransactionGraphDependencies(
            backend=FakeBackend(events),
            signer=signer,
            policy_engine=TransactionPolicyEngine(),
            approver=FakeApprover(events),
            idempotency_store=InMemoryIdempotencyStore(),
        ),
    ).compile()
