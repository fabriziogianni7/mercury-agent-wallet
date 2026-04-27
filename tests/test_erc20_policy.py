from typing import Any

from mercury.models import ExecutableTransaction, GasFees
from mercury.models.erc20 import MAX_UINT256, ERC20Action
from mercury.models.policy import PolicyDecisionStatus
from mercury.models.simulation import SimulationResult, SimulationStatus
from mercury.policy.risk import TransactionPolicyEngine

TOKEN = "0x000000000000000000000000000000000000cafE"
WALLET = "0x000000000000000000000000000000000000bEEF"
RECIPIENT = "0x000000000000000000000000000000000000dEaD"
SPENDER = "0x0000000000000000000000000000000000000002"


def test_erc20_transfer_requires_approval() -> None:
    decision = TransactionPolicyEngine().evaluate(
        _erc20_transaction(
            metadata={
                "action": ERC20Action.TRANSFER.value,
                "token_address": TOKEN,
                "recipient_address": RECIPIENT,
                "amount_raw": 1,
            }
        ),
        _passed_simulation(),
    )

    assert decision.status == PolicyDecisionStatus.NEEDS_APPROVAL
    assert "ERC20 transfers" in decision.reason


def test_erc20_approval_requires_approval() -> None:
    decision = TransactionPolicyEngine().evaluate(
        _erc20_transaction(
            metadata={
                "action": ERC20Action.APPROVAL.value,
                "token_address": TOKEN,
                "spender_address": SPENDER,
                "amount_raw": 1,
                "spender_known": True,
            }
        ),
        _passed_simulation(),
    )

    assert decision.status == PolicyDecisionStatus.NEEDS_APPROVAL
    assert "ERC20 approvals" in decision.reason


def test_erc20_unlimited_approval_is_rejected_by_default() -> None:
    decision = TransactionPolicyEngine().evaluate(
        _erc20_transaction(
            metadata={
                "action": ERC20Action.APPROVAL.value,
                "token_address": TOKEN,
                "spender_address": SPENDER,
                "amount_raw": MAX_UINT256,
                "unlimited_approval": True,
                "spender_known": True,
            }
        ),
        _passed_simulation(),
    )

    assert decision.status == PolicyDecisionStatus.REJECTED
    assert "Unlimited ERC20 approvals" in decision.reason


def test_erc20_unknown_spender_is_flagged_for_approval() -> None:
    decision = TransactionPolicyEngine().evaluate(
        _erc20_transaction(
            metadata={
                "action": ERC20Action.APPROVAL.value,
                "token_address": TOKEN,
                "spender_address": SPENDER,
                "amount_raw": 1,
                "spender_known": False,
            }
        ),
        _passed_simulation(),
    )

    assert decision.status == PolicyDecisionStatus.NEEDS_APPROVAL
    assert "unknown" in decision.reason


def test_erc20_zero_spender_is_rejected() -> None:
    decision = TransactionPolicyEngine().evaluate(
        _erc20_transaction(
            metadata={
                "action": ERC20Action.APPROVAL.value,
                "token_address": TOKEN,
                "spender_address": "0x0000000000000000000000000000000000000000",
                "amount_raw": 1,
            }
        ),
        _passed_simulation(),
    )

    assert decision.status == PolicyDecisionStatus.REJECTED
    assert "zero address" in decision.reason


def _erc20_transaction(*, metadata: dict[str, Any]) -> ExecutableTransaction:
    return ExecutableTransaction(
        wallet_id="primary",
        chain="ethereum",
        chain_id=1,
        from_address=WALLET,
        to=TOKEN,
        value_wei=0,
        data="0x095ea7b3",
        nonce=0,
        gas=GasFees(gas_limit=50_000, gas_price=1_000_000_000),
        idempotency_key="erc20-policy",
        metadata=metadata,
    )


def _passed_simulation() -> SimulationResult:
    return SimulationResult(status=SimulationStatus.PASSED, gas_estimate=50_000)
