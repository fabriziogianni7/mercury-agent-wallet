"""Gas and fee models for executable EVM transactions."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GasFees(BaseModel):
    """EVM gas limit and fee fields."""

    model_config = ConfigDict(frozen=True)

    gas_limit: int = Field(gt=0)
    max_fee_per_gas: int | None = Field(default=None, gt=0)
    max_priority_fee_per_gas: int | None = Field(default=None, gt=0)
    gas_price: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_fee_mode(self) -> "GasFees":
        has_eip1559 = self.max_fee_per_gas is not None or self.max_priority_fee_per_gas is not None
        if has_eip1559 and self.gas_price is not None:
            raise ValueError("Gas fees cannot mix EIP-1559 and legacy gas price fields.")
        if has_eip1559 and (self.max_fee_per_gas is None or self.max_priority_fee_per_gas is None):
            raise ValueError("EIP-1559 fees require max fee and priority fee.")
        if not has_eip1559 and self.gas_price is None:
            raise ValueError("Gas fees require either EIP-1559 fees or legacy gas price.")
        return self

    def to_transaction_fields(self) -> dict[str, int]:
        """Return Web3-compatible transaction fee fields."""

        fields = {"gas": self.gas_limit}
        if self.gas_price is not None:
            fields["gasPrice"] = self.gas_price
        else:
            fields["maxFeePerGas"] = self.max_fee_per_gas or 0
            fields["maxPriorityFeePerGas"] = self.max_priority_fee_per_gas or 0
        return fields
