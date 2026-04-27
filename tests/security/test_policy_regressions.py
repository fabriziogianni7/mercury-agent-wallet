from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from mercury.graph.agent import build_transaction_graph
from mercury.graph.nodes_transaction import TransactionGraphDependencies
from mercury.models import ExecutionStatus, GasFees
from mercury.models.erc20 import MAX_UINT256, ERC20Action
from mercury.models.execution import ExecutableTransaction
from mercury.models.policy import PolicyDecisionStatus
from mercury.models.simulation import SimulationResult, SimulationStatus
from mercury.models.swaps import SwapProviderName
from mercury.policy.risk import TransactionPolicyEngine
from mercury.policy.swap_rules import SwapPolicyConfig, evaluate_swap_quote_policy
from mercury.swaps.base import SwapProviderError
from mercury.swaps.router import SwapRouter

from tests.fakes.signer import RecordingSigner
from tests.fakes.swap_providers import fake_swap_quote
from tests.fakes.transactions import RecordingApprover, RecordingTransactionBackend

WALLET = "0x000000000000000000000000000000000000bEEF"
RECIPIENT = "0x000000000000000000000000000000000000dEaD"
TOKEN = "0x000000000000000000000000000000000000cafE"
SPENDER = "0x0000000000000000000000000000000000000002"


def test_value_moving_transaction_cannot_sign_before_approval_and_idempotency() -> None:
    events: list[str] = []
    signer = RecordingSigner(events, wallet_address=WALLET, expected_to=RECIPIENT)
    graph = build_transaction_graph(
        TransactionGraphDependencies(
            backend=RecordingTransactionBackend(events),
            signer=signer,
            policy_engine=TransactionPolicyEngine(),
            approver=RecordingApprover(events, approved=True),
        )
    ).compile()

    result = graph.invoke({"raw_input": _prepared_transaction()})

    assert result["execution_result"].status == ExecutionStatus.CONFIRMED
    assert events.index("approval") < events.index("sign")
    assert events.index("simulate") < events.index("approval")
    assert signer.sign_calls == 1


def test_missing_idempotency_key_rejects_before_signing_even_after_approval() -> None:
    events: list[str] = []
    signer = RecordingSigner(events, wallet_address=WALLET)
    graph = build_transaction_graph(
        TransactionGraphDependencies(
            backend=RecordingTransactionBackend(events),
            signer=signer,
            policy_engine=TransactionPolicyEngine(),
            approver=RecordingApprover(events, approved=True),
        )
    ).compile()

    result = graph.invoke({"raw_input": _prepared_transaction(idempotency_key=None)})

    assert result["execution_result"].status == ExecutionStatus.REJECTED
    assert "Idempotency key" in result["execution_result"].error
    assert signer.sign_calls == 0
    assert "sign" not in events
    assert "broadcast" not in events


def test_chain_mismatch_and_unlimited_approval_are_rejected_by_policy() -> None:
    chain_mismatch = TransactionPolicyEngine().evaluate(
        _executable(chain_id=8453),
        _passed_simulation(),
    )
    unlimited_approval = TransactionPolicyEngine().evaluate(
        _executable(
            value_wei=0,
            data=("0x095ea7b3" + f"{int(SPENDER, 16):064x}" + f"{MAX_UINT256:064x}"),
            metadata={
                "action": ERC20Action.APPROVAL.value,
                "token_address": TOKEN,
                "spender_address": SPENDER,
                "amount_raw": MAX_UINT256,
                "unlimited_approval": True,
                "spender_known": True,
            },
        ),
        _passed_simulation(),
    )

    assert chain_mismatch.status == PolicyDecisionStatus.REJECTED
    assert "chain_id" in chain_mismatch.reason
    assert unlimited_approval.status == PolicyDecisionStatus.REJECTED
    assert "Unlimited ERC20 approvals" in unlimited_approval.reason


def test_swap_quote_rejects_unsupported_provider_config_and_expiry() -> None:
    quote = fake_swap_quote(expires_at=datetime.now(tz=UTC) - timedelta(seconds=1))
    expired = evaluate_swap_quote_policy(quote)
    unsupported_provider = evaluate_swap_quote_policy(
        fake_swap_quote(provider=SwapProviderName.LIFI),
        config=SwapPolicyConfig(allowed_providers=frozenset({SwapProviderName.UNISWAP})),
    )

    assert expired.status == PolicyDecisionStatus.REJECTED
    assert "expired" in expired.reason
    assert unsupported_provider.status == PolicyDecisionStatus.REJECTED
    assert "allowlist" in unsupported_provider.reason


def test_swap_router_rejects_unknown_provider_preference() -> None:
    router = SwapRouter([])

    try:
        router.provider_for(SwapProviderName.LIFI)
    except SwapProviderError as exc:
        assert "not configured" in str(exc)
    else:
        raise AssertionError("unknown provider preference should be rejected")


def _prepared_transaction(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "wallet_id": "primary",
        "chain": "ethereum",
        "chain_id": 1,
        "to": RECIPIENT,
        "value_wei": 1,
        "data": "0x",
        "idempotency_key": "policy-regression-1",
    }
    payload.update(overrides)
    return payload


def _executable(
    *,
    chain_id: int = 1,
    value_wei: int = 1,
    data: str = "0x",
    metadata: dict[str, Any] | None = None,
) -> ExecutableTransaction:
    return ExecutableTransaction(
        wallet_id="primary",
        chain="ethereum",
        chain_id=chain_id,
        from_address=WALLET,
        to=TOKEN if metadata else RECIPIENT,
        value_wei=value_wei,
        data=data,
        nonce=0,
        gas=GasFees(gas_limit=50_000, gas_price=1_000_000_000),
        idempotency_key="policy-regression-1",
        metadata=metadata or {},
    )


def _passed_simulation() -> SimulationResult:
    return SimulationResult(status=SimulationStatus.PASSED, gas_estimate=50_000)
