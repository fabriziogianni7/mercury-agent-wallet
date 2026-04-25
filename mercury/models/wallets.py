"""Wallet identity models."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mercury.models.addresses import normalize_evm_address


class WalletRef(BaseModel):
    """Reference to a 1Claw-managed Mercury wallet."""

    model_config = ConfigDict(frozen=True)

    wallet_id: str = Field(min_length=1)
    expected_address: str | None = None

    @field_validator("expected_address")
    @classmethod
    def validate_expected_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_evm_address(value)


class WalletAddressResult(BaseModel):
    """Public wallet address derived inside the custody signer boundary."""

    model_config = ConfigDict(frozen=True)

    wallet_id: str = Field(min_length=1)
    address: str = Field(min_length=1)

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        return normalize_evm_address(value)
