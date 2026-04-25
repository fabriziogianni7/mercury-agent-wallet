"""MVP transaction policy engine."""

from mercury.models.execution import ExecutableTransaction
from mercury.models.policy import PolicyDecision, PolicyDecisionStatus
from mercury.models.simulation import SimulationResult
from mercury.policy.rules import (
    erc20_approval_reason,
    erc20_policy_reason,
    excessive_gas_reason,
    invalid_transaction_reason,
    simulation_failure_reason,
    unsupported_chain_reason,
)


class TransactionPolicyEngine:
    """Initial conservative policy engine for generic value-moving transactions."""

    def __init__(
        self,
        *,
        max_gas_limit: int | None = None,
        reject_unlimited_erc20_approvals: bool = True,
        reject_erc20_self_transfers: bool = True,
    ) -> None:
        self._max_gas_limit = max_gas_limit
        self._reject_unlimited_erc20_approvals = reject_unlimited_erc20_approvals
        self._reject_erc20_self_transfers = reject_erc20_self_transfers

    def evaluate(
        self,
        transaction: ExecutableTransaction,
        simulation: SimulationResult | None,
    ) -> PolicyDecision:
        """Evaluate transaction risk before approval and signing."""

        for reason in (
            unsupported_chain_reason(transaction),
            invalid_transaction_reason(transaction),
            simulation_failure_reason(simulation),
            excessive_gas_reason(transaction, max_gas_limit=self._max_gas_limit),
            erc20_policy_reason(
                transaction,
                reject_unlimited_approvals=self._reject_unlimited_erc20_approvals,
                reject_self_transfers=self._reject_erc20_self_transfers,
            ),
        ):
            if reason is not None:
                return PolicyDecision(status=PolicyDecisionStatus.REJECTED, reason=reason)

        erc20_reason = erc20_approval_reason(transaction)
        if erc20_reason is not None:
            return PolicyDecision(status=PolicyDecisionStatus.NEEDS_APPROVAL, reason=erc20_reason)

        if transaction.is_value_moving:
            return PolicyDecision(
                status=PolicyDecisionStatus.NEEDS_APPROVAL,
                reason="Human approval is required for value-moving transactions.",
            )

        return PolicyDecision(
            status=PolicyDecisionStatus.ALLOWED,
            reason="Transaction passed MVP policy checks.",
        )
