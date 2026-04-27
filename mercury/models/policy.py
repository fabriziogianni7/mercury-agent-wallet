"""Policy decision placeholders."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class PolicyDecisionStatus(StrEnum):
    """Possible policy outcomes."""

    ALLOWED = "allowed"
    NEEDS_APPROVAL = "needs_approval"
    REJECTED = "rejected"


class PolicyDecision(BaseModel):
    """Policy result placeholder for later safety layers."""

    model_config = ConfigDict(frozen=True)

    status: PolicyDecisionStatus
    reason: str = Field(min_length=1)
