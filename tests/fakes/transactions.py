from __future__ import annotations

from mercury.models import ExecutionStatus, GasFees, PreparedTransaction, SignedTransactionResult
from mercury.models.approval import ApprovalRequest, ApprovalResult, ApprovalStatus
from mercury.models.execution import ExecutableTransaction, TransactionReceipt
from mercury.models.simulation import SimulationResult, SimulationStatus


class RecordingApprover:
    def __init__(
        self,
        events: list[str] | None = None,
        *,
        approved: bool = True,
    ) -> None:
        self.events = events if events is not None else []
        self.approved = approved
        self.requests: list[ApprovalRequest] = []

    def request_approval(self, request: ApprovalRequest) -> ApprovalResult:
        self.events.append("approval")
        self.requests.append(request)
        if self.approved:
            return ApprovalResult(
                status=ApprovalStatus.APPROVED,
                reason="approved",
                approved_by="test",
            )
        return ApprovalResult(status=ApprovalStatus.DENIED, reason="denied")


class RecordingTransactionBackend:
    def __init__(
        self,
        events: list[str] | None = None,
        *,
        simulation_passed: bool = True,
        gas_limit: int = 21_000,
        tx_hash: str = "0xbeef",
    ) -> None:
        self.events = events if events is not None else []
        self.simulation_passed = simulation_passed
        self.gas_limit = gas_limit
        self.tx_hash = tx_hash

    def resolve_chain_id(self, transaction: PreparedTransaction) -> int:
        return transaction.chain_id or 1

    def lookup_nonce(self, transaction: PreparedTransaction, wallet_address: str) -> int:
        self.events.append("nonce")
        return 7

    def populate_gas(self, transaction: PreparedTransaction | ExecutableTransaction) -> GasFees:
        self.events.append("gas")
        return GasFees(gas_limit=self.gas_limit, gas_price=1_000_000_000)

    def simulate(self, transaction: ExecutableTransaction) -> SimulationResult:
        self.events.append("simulate")
        if not self.simulation_passed:
            return SimulationResult(status=SimulationStatus.FAILED, reason="execution reverted")
        return SimulationResult(status=SimulationStatus.PASSED, gas_estimate=self.gas_limit)

    def broadcast(self, signed_transaction: SignedTransactionResult) -> str:
        self.events.append("broadcast")
        return self.tx_hash

    def wait_for_receipt(
        self,
        *,
        chain: str,
        tx_hash: str,
        timeout_seconds: float,
        confirmations: int,
    ) -> TransactionReceipt:
        self.events.append("monitor")
        return TransactionReceipt(
            tx_hash=tx_hash,
            status=ExecutionStatus.CONFIRMED,
            block_number=123,
            gas_used=self.gas_limit,
        )
