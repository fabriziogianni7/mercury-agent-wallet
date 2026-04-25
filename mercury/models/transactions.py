"""Transaction reference models for future phases."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

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
