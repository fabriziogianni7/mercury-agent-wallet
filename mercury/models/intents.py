"""Initial wallet intent models."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Address = Annotated[str, Field(pattern=r"^0x[a-fA-F0-9]{40}$")]


class IntentKind(StrEnum):
    """Supported Phase 1 intent discriminators."""

    READ_CONTRACT = "read_contract"
    NATIVE_BALANCE = "native_balance"
    ERC20_BALANCE = "erc20_balance"
    PREPARE_TRANSACTION = "prepare_transaction"


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


type WalletIntent = (
    ReadContractIntent | NativeBalanceIntent | ERC20BalanceIntent | PlaceholderTransactionIntent
)
