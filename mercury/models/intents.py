"""Initial wallet intent models."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mercury.models.addresses import normalize_evm_address

Address = Annotated[str, Field(pattern=r"^0x[a-fA-F0-9]{40}$")]


class IntentKind(StrEnum):
    """Supported Phase 1 intent discriminators."""

    READ_CONTRACT = "read_contract"
    NATIVE_BALANCE = "native_balance"
    ERC20_BALANCE = "erc20_balance"
    PREPARE_TRANSACTION = "prepare_transaction"
    ERC20_TRANSFER = "erc20_transfer"
    ERC20_APPROVAL = "erc20_approval"


class BaseWalletIntent(BaseModel):
    """Base class for non-executing wallet intents."""

    model_config = ConfigDict(frozen=True)

    kind: IntentKind


class ReadContractIntent(BaseWalletIntent):
    """Intent to read data from a contract in a future phase."""

    kind: Literal[IntentKind.READ_CONTRACT] = IntentKind.READ_CONTRACT
    contract_address: Address
    function_name: str = Field(min_length=1)
    args: tuple[str, ...] = ()


class NativeBalanceIntent(BaseWalletIntent):
    """Intent to read a native token balance in a future phase."""

    kind: Literal[IntentKind.NATIVE_BALANCE] = IntentKind.NATIVE_BALANCE
    wallet_address: Address


class ERC20BalanceIntent(BaseWalletIntent):
    """Intent to read an ERC20 token balance in a future phase."""

    kind: Literal[IntentKind.ERC20_BALANCE] = IntentKind.ERC20_BALANCE
    wallet_address: Address
    token_address: Address


class PlaceholderTransactionIntent(BaseWalletIntent):
    """Placeholder for future transaction-building phases; never signs or sends."""

    kind: Literal[IntentKind.PREPARE_TRANSACTION] = IntentKind.PREPARE_TRANSACTION
    summary: str = Field(min_length=1)


class ERC20TransferIntent(BaseWalletIntent):
    """Intent to prepare an ERC20 transfer through the transaction pipeline."""

    kind: Literal[IntentKind.ERC20_TRANSFER] = IntentKind.ERC20_TRANSFER
    chain: str = Field(min_length=1)
    wallet_id: str = Field(min_length=1)
    token_address: Address
    recipient_address: Address
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


class ERC20ApprovalIntent(BaseWalletIntent):
    """Intent to prepare an ERC20 approval through the transaction pipeline."""

    kind: Literal[IntentKind.ERC20_APPROVAL] = IntentKind.ERC20_APPROVAL
    chain: str = Field(min_length=1)
    wallet_id: str = Field(min_length=1)
    token_address: Address
    spender_address: Address
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


type WalletIntent = (
    ReadContractIntent
    | NativeBalanceIntent
    | ERC20BalanceIntent
    | PlaceholderTransactionIntent
    | ERC20TransferIntent
    | ERC20ApprovalIntent
)
