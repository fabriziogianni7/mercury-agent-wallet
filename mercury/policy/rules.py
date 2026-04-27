"""Reusable policy validation rules for transaction execution."""

from mercury.chains import UnsupportedChainError, get_chain_by_name
from mercury.models.addresses import normalize_evm_address
from mercury.models.erc20 import MAX_UINT256, ZERO_ADDRESS, ERC20Action
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


def erc20_policy_reason(
    transaction: ExecutableTransaction,
    *,
    reject_unlimited_approvals: bool = True,
    reject_self_transfers: bool = True,
) -> str | None:
    """Return a rejection reason for ERC20-specific transaction policy."""

    action = transaction.metadata.get("action")
    if action == ERC20Action.TRANSFER.value:
        recipient = _metadata_address(transaction, "recipient_address")
        if recipient == normalize_evm_address(ZERO_ADDRESS):
            return "ERC20 transfer recipient must not be the zero address."
        if reject_self_transfers and transaction.from_address is not None:
            if recipient == normalize_evm_address(transaction.from_address):
                return "ERC20 self-transfer is not allowed."
        return None

    if action == ERC20Action.APPROVAL.value:
        spender = _metadata_address(transaction, "spender_address")
        if spender == normalize_evm_address(ZERO_ADDRESS):
            return "ERC20 approval spender must not be the zero address."
        amount_raw = transaction.metadata.get("amount_raw")
        unlimited = (
            transaction.metadata.get("unlimited_approval") is True or amount_raw == MAX_UINT256
        )
        if reject_unlimited_approvals and unlimited:
            return "Unlimited ERC20 approvals are rejected by default."
        return None

    return None


def erc20_approval_reason(transaction: ExecutableTransaction) -> str | None:
    """Return an ERC20-specific approval reason when a transaction needs approval."""

    action = transaction.metadata.get("action")
    if action == ERC20Action.TRANSFER.value:
        return "Human approval is required for ERC20 transfers."
    if action == ERC20Action.APPROVAL.value:
        if transaction.metadata.get("spender_known") is False:
            return "Human approval is required for ERC20 approvals; spender is unknown."
        return "Human approval is required for ERC20 approvals."
    return None


def _metadata_address(transaction: ExecutableTransaction, key: str) -> str:
    value = transaction.metadata.get(key)
    if not isinstance(value, str):
        raise ValueError(f"ERC20 transaction metadata missing {key}.")
    return normalize_evm_address(value)
