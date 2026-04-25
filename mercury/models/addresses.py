"""EVM address validation helpers."""

from pydantic import BaseModel, ConfigDict, Field, field_validator
from web3 import Web3


class InvalidEVMAddressError(ValueError):
    """Raised when a value is not a valid EVM address."""


def normalize_evm_address(address: str) -> str:
    """Validate and return an EIP-55 checksum EVM address."""

    candidate = address.strip()
    if not candidate:
        raise InvalidEVMAddressError("EVM address must not be empty.")
    if not Web3.is_address(candidate):
        raise InvalidEVMAddressError("Invalid EVM address.")

    return Web3.to_checksum_address(candidate)


class EVMAddress(BaseModel):
    """Pydantic wrapper that stores EVM addresses in checksum form."""

    model_config = ConfigDict(frozen=True)

    value: str = Field(min_length=1)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        return normalize_evm_address(value)
