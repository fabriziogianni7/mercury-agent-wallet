"""Signer request and result models."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mercury.models.addresses import normalize_evm_address
from mercury.models.transactions import HexData, PreparedEVMTransaction
from mercury.models.wallets import WalletRef


class SignTransactionRequest(BaseModel):
    """Request to sign a fully prepared EVM transaction."""

    model_config = ConfigDict(frozen=True)

    wallet: WalletRef
    chain_id: int = Field(gt=0)
    prepared_transaction: PreparedEVMTransaction

    @model_validator(mode="after")
    def validate_chain_id(self) -> "SignTransactionRequest":
        if self.prepared_transaction.chain_id != self.chain_id:
            raise ValueError("Prepared transaction chain_id must match request chain_id.")
        return self


class SignedTransactionResult(BaseModel):
    """Public result for an in-memory signed transaction."""

    model_config = ConfigDict(frozen=True)

    wallet_id: str = Field(min_length=1)
    chain_id: int = Field(gt=0)
    signer_address: str = Field(min_length=1)
    raw_transaction_hex: HexData
    tx_hash: HexData

    @model_validator(mode="after")
    def validate_signer_address(self) -> "SignedTransactionResult":
        object.__setattr__(self, "signer_address", normalize_evm_address(self.signer_address))
        return self


class SignTypedDataRequest(BaseModel):
    """Request to sign an EIP-712 typed-data payload."""

    model_config = ConfigDict(frozen=True)

    wallet: WalletRef
    chain_id: int = Field(gt=0)
    typed_data: dict[str, Any] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_domain_chain_id(self) -> "SignTypedDataRequest":
        domain = self.typed_data.get("domain")
        if isinstance(domain, dict):
            domain_chain_id = domain.get("chainId")
            if domain_chain_id is not None and domain_chain_id != self.chain_id:
                raise ValueError("Typed-data domain chainId must match request chain_id.")
        return self


class SignedTypedDataResult(BaseModel):
    """Public result for an EIP-712 signature."""

    model_config = ConfigDict(frozen=True)

    wallet_id: str = Field(min_length=1)
    chain_id: int = Field(gt=0)
    signer_address: str = Field(min_length=1)
    signature: HexData
    message_hash: HexData

    @model_validator(mode="after")
    def validate_signer_address(self) -> "SignedTypedDataResult":
        object.__setattr__(self, "signer_address", normalize_evm_address(self.signer_address))
        return self
