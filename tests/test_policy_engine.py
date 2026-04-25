from mercury.models import ExecutableTransaction, GasFees
from mercury.models.policy import PolicyDecisionStatus
from mercury.models.simulation import SimulationResult, SimulationStatus
from mercury.policy.risk import TransactionPolicyEngine


def test_value_moving_transaction_requires_approval_by_default() -> None:
    decision = TransactionPolicyEngine().evaluate(
        _transaction(value_wei=1),
        SimulationResult(status=SimulationStatus.PASSED, gas_estimate=21_000),
    )

    assert decision.status == PolicyDecisionStatus.NEEDS_APPROVAL
    assert "Human approval" in decision.reason


def test_chain_id_mismatch_is_rejected() -> None:
    decision = TransactionPolicyEngine().evaluate(
        _transaction(chain_id=8453),
        SimulationResult(status=SimulationStatus.PASSED, gas_estimate=21_000),
    )

    assert decision.status == PolicyDecisionStatus.REJECTED
    assert "chain_id" in decision.reason


def test_simulation_failure_is_rejected() -> None:
    decision = TransactionPolicyEngine().evaluate(
        _transaction(),
        SimulationResult(status=SimulationStatus.FAILED, reason="execution reverted"),
    )

    assert decision.status == PolicyDecisionStatus.REJECTED
    assert decision.reason == "execution reverted"


def test_missing_idempotency_key_for_value_moving_transaction_is_rejected() -> None:
    decision = TransactionPolicyEngine().evaluate(
        _transaction(value_wei=1, idempotency_key=None),
        SimulationResult(status=SimulationStatus.PASSED, gas_estimate=21_000),
    )

    assert decision.status == PolicyDecisionStatus.REJECTED
    assert "Idempotency key" in decision.reason


def test_configured_max_gas_limit_is_enforced() -> None:
    decision = TransactionPolicyEngine(max_gas_limit=20_000).evaluate(
        _transaction(),
        SimulationResult(status=SimulationStatus.PASSED, gas_estimate=21_000),
    )

    assert decision.status == PolicyDecisionStatus.REJECTED
    assert "gas" in decision.reason


def _transaction(
    *,
    chain_id: int = 1,
    value_wei: int = 1,
    idempotency_key: str | None = "phase-6",
) -> ExecutableTransaction:
    return ExecutableTransaction(
        wallet_id="primary",
        chain="ethereum",
        chain_id=chain_id,
        from_address="0x000000000000000000000000000000000000bEEF",
        to="0x000000000000000000000000000000000000dEaD",
        value_wei=value_wei,
        nonce=0,
        gas=GasFees(gas_limit=21_000, gas_price=1_000_000_000),
        idempotency_key=idempotency_key,
    )
