"""Generic EVM transaction execution request and result models."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mercury.models.addresses import normalize_evm_address
from mercury.models.gas import GasFees
from mercury.models.policy import PolicyDecision
from mercury.models.transactions import HexData, PreparedEVMTransaction


class ExecutionStatus(StrEnum):
    """Normalized transaction execution statuses."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REJECTED = "rejected"
    APPROVAL_DENIED = "approval_denied"


class PreparedTransaction(BaseModel):
    """Action-agnostic unsigned EVM transaction accepted by the Phase 6 pipeline."""

    model_config = ConfigDict(frozen=True)

    wallet_id: str = Field(min_length=1)
    chain: str = Field(min_length=1)
    chain_id: int | None = Field(default=None, gt=0)
    from_address: str | None = None
    to: str = Field(min_length=1)
    value_wei: int = Field(default=0, ge=0)
    data: HexData = "0x"
    nonce: int | None = Field(default=None, ge=0)
    gas: GasFees | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("to", "from_address")
    @classmethod
    def validate_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_evm_address(value)

    @property
    def is_value_moving(self) -> bool:
        """Return whether the transaction can mutate value or chain state."""

        return self.value_wei > 0 or self.data != "0x"


class ExecutableTransaction(BaseModel):
    """Prepared transaction with chain ID, nonce, and gas populated for signing."""

    model_config = ConfigDict(frozen=True)

    wallet_id: str = Field(min_length=1)
    chain: str = Field(min_length=1)
    chain_id: int = Field(gt=0)
    from_address: str | None = None
    to: str = Field(min_length=1)
    value_wei: int = Field(ge=0)
    data: HexData = "0x"
    nonce: int = Field(ge=0)
    gas: GasFees
    idempotency_key: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("to", "from_address")
    @classmethod
    def validate_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_evm_address(value)

    @property
    def is_value_moving(self) -> bool:
        """Return whether the transaction can mutate value or chain state."""

        return self.value_wei > 0 or self.data != "0x"

    def to_prepared_evm_transaction(self) -> PreparedEVMTransaction:
        """Convert to the Phase 5 signer payload."""

        transaction: dict[str, Any] = {
            "chainId": self.chain_id,
            "nonce": self.nonce,
            "to": self.to,
            "value": self.value_wei,
            "data": self.data,
            **self.gas.to_transaction_fields(),
        }
        if self.from_address is not None:
            transaction["from"] = self.from_address
        return PreparedEVMTransaction(chain_id=self.chain_id, transaction=transaction)


class TransactionReceipt(BaseModel):
    """Normalized EVM receipt data used by execution results."""

    model_config = ConfigDict(frozen=True)

    tx_hash: HexData
    status: ExecutionStatus = ExecutionStatus.CONFIRMED
    block_number: int | None = Field(default=None, ge=0)
    gas_used: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_receipt_status(self) -> "TransactionReceipt":
        valid_statuses = {
            ExecutionStatus.CONFIRMED,
            ExecutionStatus.FAILED,
            ExecutionStatus.PENDING,
        }
        if self.status not in valid_statuses:
            raise ValueError("Receipt status must be confirmed, failed, or pending.")
        return self


class ExecutionResult(BaseModel):
    """Sanitized transaction execution response."""

    model_config = ConfigDict(frozen=True)

    chain: str = Field(min_length=1)
    chain_id: int = Field(gt=0)
    wallet_id: str = Field(min_length=1)
    wallet_address: str | None = None
    tx_hash: HexData | None = None
    status: ExecutionStatus
    block_number: int | None = Field(default=None, ge=0)
    gas_used: int | None = Field(default=None, ge=0)
    policy_decision: PolicyDecision | None = None
    error: str | None = None

    @field_validator("wallet_address")
    @classmethod
    def validate_wallet_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_evm_address(value)
