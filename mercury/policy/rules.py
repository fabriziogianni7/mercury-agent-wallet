"""Reusable policy validation rules for transaction execution."""

from mercury.chains import UnsupportedChainError, get_chain_by_name
from mercury.models.addresses import normalize_evm_address
from mercury.models.execution import ExecutableTransaction
from mercury.models.simulation import SimulationResult


def unsupported_chain_reason(transaction: ExecutableTransaction) -> str | None:
    """Return a rejection reason when the chain is not supported or mismatched."""

    try:
        chain = get_chain_by_name(transaction.chain)
    except UnsupportedChainError as exc:
        return str(exc)
    if chain.chain_id != transaction.chain_id:
        return "Prepared transaction chain_id does not match resolved chain."
    return None


def invalid_transaction_reason(transaction: ExecutableTransaction) -> str | None:
    """Return a rejection reason for missing identity or invalid recipient fields."""

    if not transaction.wallet_id:
        return "Wallet ID is required."
    try:
        normalize_evm_address(transaction.to)
    except ValueError:
        return "Recipient address is invalid."
    if transaction.is_value_moving and not transaction.idempotency_key:
        return "Idempotency key is required for value-moving transactions."
    return None


def simulation_failure_reason(simulation: SimulationResult | None) -> str | None:
    """Return a rejection reason when simulation did not pass."""

    if simulation is None:
        return "Simulation result is required."
    if not simulation.passed:
        return simulation.reason or "Transaction simulation failed."
    return None


def excessive_gas_reason(
    transaction: ExecutableTransaction,
    *,
    max_gas_limit: int | None,
) -> str | None:
    """Return a rejection reason when gas exceeds a configured maximum."""

    if max_gas_limit is not None and transaction.gas.gas_limit > max_gas_limit:
        return "Estimated gas exceeds configured maximum."
    return None
