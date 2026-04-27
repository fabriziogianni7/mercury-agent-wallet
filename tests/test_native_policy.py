from mercury.models import ExecutableTransaction, GasFees
from mercury.models.policy import PolicyDecisionStatus
from mercury.models.simulation import SimulationResult, SimulationStatus
from mercury.policy.risk import TransactionPolicyEngine

WALLET = "0x000000000000000000000000000000000000bEEF"
RECIPIENT = "0x000000000000000000000000000000000000dEaD"


def _native_executable(
    *,
    to: str = RECIPIENT,
    value_wei: int = 1,
    data: str = "0x",
) -> ExecutableTransaction:
    return ExecutableTransaction(
        wallet_id="primary",
        chain="base",
        chain_id=8453,
        from_address=WALLET,
        to=to,
        value_wei=value_wei,
        data=data,
        nonce=0,
        gas=GasFees(gas_limit=21_000, gas_price=1_000_000_000),
        idempotency_key="native-pol",
        metadata={
            "action": "native_transfer",
            "recipient_address": RECIPIENT,
        },
    )


def test_native_transfer_requires_approval() -> None:
    decision = TransactionPolicyEngine().evaluate(
        _native_executable(),
        SimulationResult(status=SimulationStatus.PASSED, gas_estimate=21_000),
    )
    assert decision.status == PolicyDecisionStatus.NEEDS_APPROVAL
    assert "native" in decision.reason.lower()


def test_native_transfer_rejects_wrong_to() -> None:
    decision = TransactionPolicyEngine().evaluate(
        _native_executable(to=WALLET),
        SimulationResult(status=SimulationStatus.PASSED, gas_estimate=21_000),
    )
    assert decision.status == PolicyDecisionStatus.REJECTED
    assert "recipient" in decision.reason.lower()
