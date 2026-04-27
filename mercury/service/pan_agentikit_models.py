"""Local pan-agentikit-compatible envelope and payload models.

The pan-agentikit package is not published in this repo's dependency set yet.  These
models intentionally keep the wire shape simple and permissive while preserving the
typed payload names Mercury needs to interoperate with future coordinators.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class PanAgentEnvelope(BaseModel):
    """Transport envelope compatible with pan-agentikit-style message passing."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "1"
    id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str | None = None
    turn_id: str | None = None
    step_id: str | None = None
    parent_step_id: str | None = None
    from_role: str | None = None
    to_role: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None

    @property
    def payload_kind(self) -> str | None:
        """Return the typed payload discriminator used by pan-agentikit payloads."""

        for key in ("kind", "type", "payload_kind"):
            value = self.payload.get(key)
            if isinstance(value, str) and value:
                return value
        return None


class UserMessageV1(BaseModel):
    """Inbound natural-language user message payload."""

    model_config = ConfigDict(extra="allow")

    kind: str = "user_message"
    version: int = 1
    content: str | None = None
    text: str | None = None
    message: str | None = None
    user_id: str | None = None
    wallet_id: str | None = None
    chain: str | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def effective_content(self) -> str:
        """Return the first non-empty text field."""

        for value in (self.content, self.text, self.message):
            if isinstance(value, str) and value.strip():
                return value
        return ""


class TaskRequestV1(BaseModel):
    """Inbound structured task payload."""

    model_config = ConfigDict(extra="allow")

    kind: str = "task_request"
    version: int = 1
    task_id: str | None = None
    task_type: str | None = None
    name: str | None = None
    text: str | None = None
    intent: dict[str, Any] | str | None = None
    input: dict[str, Any] | str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    user_id: str | None = None
    wallet_id: str | None = None
    chain: str | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


class AgentReplyV1(BaseModel):
    """Outbound conversational reply payload."""

    kind: Literal["agent_reply"] = "agent_reply"
    version: Literal[1] = 1
    text: str
    content: str
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskResultV1(BaseModel):
    """Outbound structured task result payload."""

    kind: Literal["task_result"] = "task_result"
    version: Literal[1] = 1
    task_id: str | None = None
    status: str
    text: str
    message: str
    result: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WalletApprovalRequiredV1(BaseModel):
    """Outbound approval payload for value-moving wallet tasks."""

    kind: Literal["wallet_approval_required"] = "wallet_approval_required"
    version: Literal[1] = 1
    task_id: str | None = None
    status: Literal["approval_required"] = "approval_required"
    message: str
    approval: dict[str, Any]
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentErrorV1(BaseModel):
    """Outbound sanitized error payload."""

    kind: Literal["agent_error"] = "agent_error"
    version: Literal[1] = 1
    code: str
    message: str
    details: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
