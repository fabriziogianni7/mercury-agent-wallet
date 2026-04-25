from __future__ import annotations

from copy import deepcopy
from typing import Any

USER_MESSAGE_ENVELOPE: dict[str, Any] = {
    "schema_version": "1",
    "id": "env-user-1",
    "trace_id": "trace-user-1",
    "turn_id": "turn-1",
    "step_id": "step-user-1",
    "from_role": "coordinator",
    "to_role": "mercury",
    "metadata": {
        "user_id": "user-1",
        "wallet_id": "primary",
        "chain": "base",
        "idempotency_key": "idem-user-1",
    },
    "artifacts": [{"kind": "note", "uri": "artifact://request"}],
    "payload": {
        "kind": "user_message",
        "version": 1,
        "text": "What is my native balance?",
    },
}

TASK_REQUEST_ENVELOPE: dict[str, Any] = {
    "schema_version": "1",
    "id": "env-task-1",
    "trace_id": "trace-task-1",
    "turn_id": "turn-2",
    "step_id": "step-task-1",
    "parent_step_id": "step-parent-1",
    "from_role": "coordinator",
    "to_role": "mercury",
    "payload": {
        "kind": "task_request",
        "version": 1,
        "task_id": "task-read-1",
        "user_id": "user-1",
        "wallet_id": "primary",
        "chain": "base",
        "input": {
            "kind": "native_balance",
            "wallet_address": "0x000000000000000000000000000000000000dEaD",
        },
    },
}

APPROVAL_TASK_ENVELOPE: dict[str, Any] = {
    "schema_version": "1",
    "id": "env-approval-1",
    "trace_id": "trace-approval-1",
    "turn_id": "turn-3",
    "step_id": "step-approval-1",
    "from_role": "coordinator",
    "to_role": "mercury",
    "payload": {
        "kind": "task_request",
        "version": 1,
        "task_id": "task-transfer-1",
        "user_id": "user-1",
        "wallet_id": "primary",
        "idempotency_key": "idem-transfer-1",
        "input": {
            "kind": "erc20_transfer",
            "chain": "base",
            "token_address": "0x000000000000000000000000000000000000cafE",
            "recipient_address": "0x000000000000000000000000000000000000bEEF",
            "amount": "1",
        },
    },
}

UNSUPPORTED_ENVELOPE: dict[str, Any] = {
    "schema_version": "1",
    "id": "env-unsupported-1",
    "trace_id": "trace-unsupported-1",
    "step_id": "step-unsupported-1",
    "from_role": "coordinator",
    "to_role": "mercury",
    "payload": {"kind": "UnknownPayloadV1"},
}


def envelope_fixture(name: str) -> dict[str, Any]:
    fixtures = {
        "user_message": USER_MESSAGE_ENVELOPE,
        "task_request": TASK_REQUEST_ENVELOPE,
        "approval_task": APPROVAL_TASK_ENVELOPE,
        "unsupported": UNSUPPORTED_ENVELOPE,
    }
    return deepcopy(fixtures[name])
