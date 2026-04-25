"""Human approval models for value-moving transaction execution."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApprovalStatus(StrEnum):
    """Human approval outcomes."""

    APPROVED = "approved"
    DENIED = "denied"
    REQUIRED = "required"


class ApprovalRequest(BaseModel):
    """Human-readable transaction approval prompt data."""

    model_config = ConfigDict(frozen=True)

    wallet_id: str = Field(min_length=1)
    chain: str = Field(min_length=1)
    chain_id: int = Field(gt=0)
    from_address: str | None = None
    to: str = Field(min_length=1)
    value_wei: int = Field(ge=0)
    data: str = Field(min_length=2)
    idempotency_key: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalResult(BaseModel):
    """Result returned by a human approval step or placeholder."""

    model_config = ConfigDict(frozen=True)

    status: ApprovalStatus
    reason: str = Field(min_length=1)
    approved_by: str | None = None

    @property
    def approved(self) -> bool:
        """Return whether execution may proceed."""

        return self.status == ApprovalStatus.APPROVED
