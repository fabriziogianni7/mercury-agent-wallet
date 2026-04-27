"""Tests for HTTP-driven transaction approval via intent metadata."""

from mercury.graph.request_metadata import merge_intent_metadata_into_prepared
from mercury.models.approval import ApprovalRequest, ApprovalStatus
from mercury.models.execution import PreparedTransaction
from mercury.tools.transactions import RequestMetadataTransactionApprover


def _request(**metadata: object) -> ApprovalRequest:
    return ApprovalRequest(
        wallet_id="primary",
        chain="base",
        chain_id=8453,
        to="0x0000000000000000000000000000000000000001",
        value_wei=0,
        data="0x",
        idempotency_key="idem-1",
        metadata=dict(metadata),
    )


def test_approver_requires_approval_when_no_metadata() -> None:
    approver = RequestMetadataTransactionApprover()
    request = _request()
    result = approver.request_approval(request)
    assert result.status == ApprovalStatus.REQUIRED
    assert "idem-1" in result.reason


def test_approver_requires_approval_when_no_approval_response() -> None:
    approver = RequestMetadataTransactionApprover()
    request = _request(user_id="u1")
    result = approver.request_approval(request)
    assert result.status == ApprovalStatus.REQUIRED


def test_approver_requires_approval_for_non_approved_status() -> None:
    approver = RequestMetadataTransactionApprover()
    request = _request(approval_response={"status": "pending"})
    result = approver.request_approval(request)
    assert result.status == ApprovalStatus.REQUIRED


def test_approver_denies_explicit_denial() -> None:
    approver = RequestMetadataTransactionApprover()
    request = _request(approval_response={"status": "denied", "reason": "nope"})
    result = approver.request_approval(request)
    assert result.status == ApprovalStatus.DENIED
    assert result.reason == "nope"


def test_approver_approves_explicit_approval() -> None:
    approver = RequestMetadataTransactionApprover()
    request = _request(
        approval_response={
            "status": "approved",
            "approved_by": "tester",
            "reason": "ok",
        },
    )
    result = approver.request_approval(request)
    assert result.status == ApprovalStatus.APPROVED
    assert result.approved_by == "tester"
    assert result.reason == "ok"


def test_approver_denies_when_optional_idempotency_key_mismatches() -> None:
    approver = RequestMetadataTransactionApprover()
    request = _request(
        approval_response={
            "status": "approved",
            "idempotency_key": "other",
        },
    )
    result = approver.request_approval(request)
    assert result.status == ApprovalStatus.DENIED
    assert "idempotency" in result.reason.lower()


def test_approver_approves_when_optional_idempotency_key_matches() -> None:
    approver = RequestMetadataTransactionApprover()
    request = _request(
        approval_response={
            "status": "approved",
            "idempotency_key": "idem-1",
        },
    )
    result = approver.request_approval(request)
    assert result.status == ApprovalStatus.APPROVED


def test_merge_intent_metadata_into_prepared() -> None:
    prepared = PreparedTransaction(
        wallet_id="primary",
        chain="base",
        to="0x0000000000000000000000000000000000000001",
        metadata={"action": "erc20_transfer"},
    )
    merged = merge_intent_metadata_into_prepared(
        prepared,
        {
            "kind": "erc20_transfer",
            "metadata": {
                "user_id": "u1",
                "approval_response": {"status": "approved"},
            },
        },
    )
    assert merged.metadata["action"] == "erc20_transfer"
    assert merged.metadata["user_id"] == "u1"
    assert merged.metadata["approval_response"]["status"] == "approved"
