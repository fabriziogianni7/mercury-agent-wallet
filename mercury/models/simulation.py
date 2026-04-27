"""Transaction simulation and preflight result models."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SimulationStatus(StrEnum):
    """Possible preflight outcomes."""

    PASSED = "passed"
    FAILED = "failed"


class SimulationResult(BaseModel):
    """Sanitized result of transaction preflight checks."""

    model_config = ConfigDict(frozen=True)

    status: SimulationStatus
    gas_estimate: int | None = Field(default=None, gt=0)
    reason: str | None = None

    @property
    def passed(self) -> bool:
        """Return whether simulation passed."""

        return self.status == SimulationStatus.PASSED
