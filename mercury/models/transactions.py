"""Transaction models for prepared EVM signing payloads."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

Address = Annotated[str, Field(pattern=r"^0x[a-fA-F0-9]{40}$")]
HexData = Annotated[str, Field(pattern=r"^0x[a-fA-F0-9]*$")]


class UnsignedTransaction(BaseModel):
    """Unsigned transaction envelope; Phase 1 never signs or broadcasts it."""

    model_config = ConfigDict(frozen=True)

    chain_id: int = Field(gt=0)
    to: Address
    value_wei: int = Field(default=0, ge=0)
    data: HexData = "0x"


class TransactionReference(BaseModel):
    """Reference to a transaction hash produced outside Phase 1."""

    model_config = ConfigDict(frozen=True)

    chain_id: int = Field(gt=0)
    tx_hash: HexData


class PreparedEVMTransaction(BaseModel):
    """Fully prepared EVM transaction payload accepted by the signer only."""

    model_config = ConfigDict(frozen=True)

    chain_id: int = Field(gt=0)
    transaction: dict[str, Any] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_chain_id(self) -> "PreparedEVMTransaction":
        tx_chain_id = self.transaction.get("chainId")
        if tx_chain_id is None:
            raise ValueError("Prepared transaction must include chainId.")
        if not isinstance(tx_chain_id, int):
            raise ValueError("Prepared transaction chainId must be an integer.")
        if tx_chain_id != self.chain_id:
            raise ValueError("Prepared transaction chainId must match request chain_id.")
        return self

    def as_signable_dict(self) -> dict[str, Any]:
        """Return a mutable copy suitable for eth_account signing."""

        return dict(self.transaction)
