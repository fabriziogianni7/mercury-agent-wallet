"""Native (ETH / gas token) transfer intent model."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mercury.models.addresses import normalize_evm_address


class NativeTransferIntent(BaseModel):
    """Intent to send the chain's native currency to a recipient."""

    model_config = ConfigDict(frozen=True)

    chain: str = Field(min_length=1)
    wallet_id: str = Field(min_length=1)
    recipient_address: str = Field(min_length=1)
    amount: str = Field(
        min_length=1,
        description="Human-readable amount in ETH-style decimals (18).",
    )
    idempotency_key: str | None = Field(default=None, min_length=1)

    @field_validator("chain")
    @classmethod
    def normalize_chain(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("recipient_address")
    @classmethod
    def normalize_recipient(cls, value: str) -> str:
        return normalize_evm_address(value)
