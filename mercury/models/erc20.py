"""ERC20 token and transaction intent models."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mercury.models.addresses import normalize_evm_address
from mercury.models.amounts import MAX_DECIMALS, format_units, parse_units, validate_token_decimals

MAX_UINT256 = (2**256) - 1
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


class ERC20Action(StrEnum):
    """ERC20 value-moving actions supported by Mercury."""

    TRANSFER = "erc20_transfer"
    APPROVAL = "erc20_approval"


class ERC20Token(BaseModel):
    """Minimal token metadata needed to prepare ERC20 transactions."""

    model_config = ConfigDict(frozen=True)

    chain: str = Field(min_length=1)
    chain_id: int = Field(gt=0)
    token_address: str = Field(min_length=1)
    decimals: int = Field(ge=0, le=MAX_DECIMALS)
    symbol: str | None = None
    name: str | None = None

    @field_validator("chain")
    @classmethod
    def normalize_chain(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("token_address")
    @classmethod
    def normalize_token_address(cls, value: str) -> str:
        return normalize_evm_address(value)

    @field_validator("decimals")
    @classmethod
    def validate_decimals(cls, value: int) -> int:
        return validate_token_decimals(value)


class ERC20Amount(BaseModel):
    """Human and raw token amount representation."""

    model_config = ConfigDict(frozen=True)

    human_amount: str = Field(min_length=1)
    decimals: int = Field(ge=0, le=MAX_DECIMALS)
    raw_amount: int = Field(ge=0)

    @field_validator("decimals")
    @classmethod
    def validate_decimals(cls, value: int) -> int:
        return validate_token_decimals(value)

    @model_validator(mode="after")
    def validate_amount_pair(self) -> "ERC20Amount":
        parsed = parse_units(self.human_amount, self.decimals)
        if parsed != self.raw_amount:
            raise ValueError("Human amount does not match raw amount.")
        return self

    @classmethod
    def from_human(cls, human_amount: str, decimals: int) -> "ERC20Amount":
        """Create an amount by parsing a decimal string into raw units."""

        raw_amount = parse_units(human_amount, decimals)
        return cls(human_amount=human_amount, decimals=decimals, raw_amount=raw_amount)

    @property
    def formatted(self) -> str:
        """Return the canonical decimal formatting for the raw amount."""

        return format_units(self.raw_amount, self.decimals)


class ERC20TransferIntent(BaseModel):
    """Intent to prepare an ERC20 transfer transaction."""

    model_config = ConfigDict(frozen=True)

    chain: str = Field(min_length=1)
    wallet_id: str = Field(min_length=1)
    token_address: str = Field(min_length=1)
    recipient_address: str = Field(min_length=1)
    amount: str = Field(min_length=1)
    idempotency_key: str | None = Field(default=None, min_length=1)

    @field_validator("chain")
    @classmethod
    def normalize_chain(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("token_address", "recipient_address")
    @classmethod
    def normalize_address(cls, value: str) -> str:
        return normalize_evm_address(value)


class ERC20ApprovalIntent(BaseModel):
    """Intent to prepare an ERC20 approval transaction."""

    model_config = ConfigDict(frozen=True)

    chain: str = Field(min_length=1)
    wallet_id: str = Field(min_length=1)
    token_address: str = Field(min_length=1)
    spender_address: str = Field(min_length=1)
    amount: str = Field(min_length=1)
    idempotency_key: str | None = Field(default=None, min_length=1)
    spender_known: bool = False
    allow_unlimited: bool = False

    @field_validator("chain")
    @classmethod
    def normalize_chain(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("token_address", "spender_address")
    @classmethod
    def normalize_address(cls, value: str) -> str:
        return normalize_evm_address(value)
