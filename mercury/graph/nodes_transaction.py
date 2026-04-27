"""LangGraph nodes for the generic transaction execution pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from mercury.graph.responses import sanitize_error
from mercury.graph.state import MercuryState
from mercury.models.approval import ApprovalStatus
from mercury.models.execution import (
    ExecutableTransaction,
    ExecutionResult,
    ExecutionStatus,
    PreparedTransaction,
    TransactionReceipt,
)
from mercury.models.policy import PolicyDecision, PolicyDecisionStatus
from mercury.models.simulation import SimulationResult, SimulationStatus
from mercury.policy.idempotency import (
    DuplicateTransactionError,
    InMemoryIdempotencyStore,
)
from mercury.policy.risk import TransactionPolicyEngine
from mercury.tools.transactions import (
    PlaceholderTransactionApprover,
    TransactionApprover,
    TransactionBackend,
    TransactionSigner,
    build_approval_request,
    sign_executable_transaction,
)


@dataclass
class TransactionGraphDependencies:
    """Injectable transaction graph dependencies."""

    backend: TransactionBackend
    signer: TransactionSigner
    policy_engine: TransactionPolicyEngine = field(default_factory=TransactionPolicyEngine)
    approver: TransactionApprover = field(default_factory=PlaceholderTransactionApprover)
    idempotency_store: InMemoryIdempotencyStore = field(default_factory=InMemoryIdempotencyStore)
    receipt_timeout_seconds: float = 120
    receipt_confirmations: int = 0


def make_resolve_nonce_node(
    deps: TransactionGraphDependencies,
) -> Callable[[MercuryState], MercuryState]:
    """Create a node that resolves wallet address, chain ID, and nonce."""

    def resolve_nonce(state: MercuryState) -> MercuryState:
        try:
            transaction = _prepared_from_state(state)
            wallet = deps.signer.get_wallet_address(transaction.wallet_id)
            chain_id = transaction.chain_id or deps.backend.resolve_chain_id(transaction)
            prepared = transaction.model_copy(
                update={
                    "chain_id": chain_id,
                    "from_address": transaction.from_address or wallet.address,
                    "nonce": transaction.nonce
                    if transaction.nonce is not None
                    else deps.backend.lookup_nonce(transaction, wallet.address),
                }
            )
            return {
                "prepared_transaction": prepared,
                "wallet_address": wallet.address,
                "chain_name": prepared.chain,
            }
        except Exception as exc:
            return {"error": sanitize_error(exc)}

    return resolve_nonce


def make_populate_gas_node(
    deps: TransactionGraphDependencies,
) -> Callable[[MercuryState], MercuryState]:
    """Create a node that estimates gas and builds an executable transaction."""

    def populate_gas(state: MercuryState) -> MercuryState:
        if state.get("error"):
            return {}
        try:
            prepared = _prepared_from_state(state)
            if prepared.chain_id is None or prepared.nonce is None:
                raise ValueError("Transaction nonce and chain_id must be resolved before gas.")
            gas = deps.backend.populate_gas(prepared)
            executable = ExecutableTransaction(
                wallet_id=prepared.wallet_id,
                chain=prepared.chain,
                chain_id=prepared.chain_id,
                from_address=prepared.from_address,
                to=prepared.to,
                value_wei=prepared.value_wei,
                data=prepared.data,
                nonce=prepared.nonce,
                gas=gas,
                idempotency_key=prepared.idempotency_key,
                metadata=prepared.metadata,
            )
            return {"executable_transaction": executable}
        except Exception as exc:
            return {"error": sanitize_error(exc)}

    return populate_gas


def make_simulate_transaction_node(
    deps: TransactionGraphDependencies,
) -> Callable[[MercuryState], MercuryState]:
    """Create a node that runs transaction preflight simulation."""

    def simulate_transaction(state: MercuryState) -> MercuryState:
        if state.get("error"):
            return {}
        try:
            executable = _executable_from_state(state)
            simulation = deps.backend.simulate(executable)
            return {"simulation_result": simulation}
        except Exception as exc:
            return {
                "simulation_result": SimulationResult(
                    status=SimulationStatus.FAILED,
                    reason=sanitize_error(exc),
                )
            }

    return simulate_transaction


def make_policy_node(deps: TransactionGraphDependencies) -> Callable[[MercuryState], MercuryState]:
    """Create a node that evaluates transaction policy."""

    def evaluate_policy(state: MercuryState) -> MercuryState:
        if state.get("error"):
            return {"policy_decision": _reject_decision(state["error"])}
        try:
            decision = deps.policy_engine.evaluate(
                _executable_from_state(state),
                state.get("simulation_result"),
            )
            return {"policy_decision": decision}
        except Exception as exc:
            return {"policy_decision": _reject_decision(sanitize_error(exc))}

    return evaluate_policy


def make_approval_node(
    deps: TransactionGraphDependencies,
) -> Callable[[MercuryState], MercuryState]:
    """Create a node that requests human approval before signing."""

    def request_approval(state: MercuryState) -> MercuryState:
        try:
            approval = deps.approver.request_approval(
                build_approval_request(_executable_from_state(state))
            )
            if approval.status != ApprovalStatus.APPROVED:
                return {
                    "approval_result": approval,
                    "execution_result": _result_from_state(
                        state,
                        status=ExecutionStatus.APPROVAL_DENIED,
                        error=approval.reason,
                    ),
                }
            return {"approval_result": approval}
        except Exception as exc:
            error = sanitize_error(exc)
            return {
                "execution_result": _result_from_state(
                    state,
                    status=ExecutionStatus.APPROVAL_DENIED,
                    error=error,
                )
            }

    return request_approval


def make_idempotency_node(
    deps: TransactionGraphDependencies,
) -> Callable[[MercuryState], MercuryState]:
    """Create a node that reserves an idempotency key before signing."""

    def check_idempotency(state: MercuryState) -> MercuryState:
        try:
            transaction = _executable_from_state(state)
            if transaction.idempotency_key is None:
                raise ValueError("Idempotency key is required before signing.")
            deps.idempotency_store.reserve(transaction.idempotency_key)
            return {}
        except DuplicateTransactionError as exc:
            if exc.record.result is not None:
                return {"execution_result": exc.record.result}
            return {
                "execution_result": _result_from_state(
                    state,
                    status=ExecutionStatus.REJECTED,
                    error="Duplicate transaction is already in flight.",
                )
            }
        except Exception as exc:
            return {
                "execution_result": _result_from_state(
                    state,
                    status=ExecutionStatus.REJECTED,
                    error=sanitize_error(exc),
                )
            }

    return check_idempotency


def make_sign_transaction_node(
    deps: TransactionGraphDependencies,
) -> Callable[[MercuryState], MercuryState]:
    """Create a node that signs only after policy, approval, and idempotency."""

    def sign_transaction(state: MercuryState) -> MercuryState:
        try:
            signed = sign_executable_transaction(
                signer=deps.signer,
                transaction=_executable_from_state(state),
            )
            return {"signed_transaction": signed}
        except Exception as exc:
            return {
                "execution_result": _result_from_state(
                    state,
                    status=ExecutionStatus.FAILED,
                    error=sanitize_error(exc),
                )
            }

    return sign_transaction


def make_broadcast_transaction_node(
    deps: TransactionGraphDependencies,
) -> Callable[[MercuryState], MercuryState]:
    """Create a node that broadcasts a signed transaction."""

    def broadcast_transaction(state: MercuryState) -> MercuryState:
        if state.get("execution_result") is not None:
            return {}
        try:
            tx_hash = deps.backend.broadcast(state["signed_transaction"])
            return {"tx_hash": tx_hash}
        except Exception as exc:
            return {
                "execution_result": _result_from_state(
                    state,
                    status=ExecutionStatus.FAILED,
                    error=sanitize_error(exc),
                )
            }

    return broadcast_transaction


def make_monitor_receipt_node(
    deps: TransactionGraphDependencies,
) -> Callable[[MercuryState], MercuryState]:
    """Create a node that monitors a broadcast transaction receipt."""

    def monitor_receipt(state: MercuryState) -> MercuryState:
        if state.get("execution_result") is not None:
            return {}
        try:
            transaction = _executable_from_state(state)
            tx_hash = state["tx_hash"]
            receipt = deps.backend.wait_for_receipt(
                chain=transaction.chain,
                tx_hash=tx_hash,
                timeout_seconds=deps.receipt_timeout_seconds,
                confirmations=deps.receipt_confirmations,
            )
            result = _result_from_receipt(state, receipt)
            if transaction.idempotency_key is not None:
                deps.idempotency_store.complete(transaction.idempotency_key, result)
            return {"execution_result": result}
        except Exception as exc:
            result = _result_from_state(
                state,
                status=ExecutionStatus.FAILED,
                tx_hash=state.get("tx_hash"),
                error=sanitize_error(exc),
            )
            return {"execution_result": result}

    return monitor_receipt


def reject_transaction(state: MercuryState) -> MercuryState:
    """Create a normalized rejected execution result."""

    if state.get("execution_result") is not None:
        return {}
    decision = state.get("policy_decision")
    reason = (
        decision.reason if decision is not None else state.get("error", "Transaction rejected.")
    )
    return {
        "execution_result": _result_from_state(
            state,
            status=ExecutionStatus.REJECTED,
            error=reason,
        )
    }


def _prepared_from_state(state: MercuryState) -> PreparedTransaction:
    raw = state.get("prepared_transaction", state.get("raw_input"))
    if isinstance(raw, PreparedTransaction):
        return raw
    if isinstance(raw, dict):
        return PreparedTransaction.model_validate(raw)
    raise ValueError("Transaction graph requires a prepared transaction.")


def _executable_from_state(state: MercuryState) -> ExecutableTransaction:
    executable = state.get("executable_transaction")
    if not isinstance(executable, ExecutableTransaction):
        raise ValueError("Transaction graph requires an executable transaction.")
    return executable


def _reject_decision(reason: str) -> PolicyDecision:
    return PolicyDecision(status=PolicyDecisionStatus.REJECTED, reason=reason)


def _result_from_receipt(state: MercuryState, receipt: TransactionReceipt) -> ExecutionResult:
    return _result_from_state(
        state,
        status=receipt.status,
        tx_hash=receipt.tx_hash,
        block_number=receipt.block_number,
        gas_used=receipt.gas_used,
    )


def _result_from_state(
    state: MercuryState,
    *,
    status: ExecutionStatus,
    tx_hash: str | None = None,
    block_number: int | None = None,
    gas_used: int | None = None,
    error: str | None = None,
) -> ExecutionResult:
    transaction = state.get("executable_transaction")
    prepared = state.get("prepared_transaction")
    chain = transaction.chain if isinstance(transaction, ExecutableTransaction) else "unknown"
    chain_id = transaction.chain_id if isinstance(transaction, ExecutableTransaction) else 1
    wallet_id = (
        transaction.wallet_id if isinstance(transaction, ExecutableTransaction) else "unknown"
    )
    if isinstance(prepared, PreparedTransaction):
        chain = prepared.chain
        wallet_id = prepared.wallet_id
        chain_id = prepared.chain_id or chain_id

    return ExecutionResult(
        chain=chain,
        chain_id=chain_id,
        wallet_id=wallet_id,
        wallet_address=state.get("wallet_address"),
        tx_hash=tx_hash,
        status=status,
        block_number=block_number,
        gas_used=gas_used,
        policy_decision=state.get("policy_decision"),
        error=sanitize_error(error) if error is not None else None,
    )
