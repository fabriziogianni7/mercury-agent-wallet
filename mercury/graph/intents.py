"""Structured read-only intent parsing for the Mercury graph."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, cast

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from mercury.models.addresses import normalize_evm_address


class ReadOnlyIntentKind(StrEnum):
    """Read-only graph intent discriminators."""

    NATIVE_BALANCE = "native_balance"
    ERC20_BALANCE = "erc20_balance"
    ERC20_ALLOWANCE = "erc20_allowance"
    ERC20_METADATA = "erc20_metadata"
    CONTRACT_READ = "contract_read"
    KNOWN_ADDRESS = "known_address"
    UNSUPPORTED = "unsupported"


class UnsupportedIntentError(ValueError):
    """Raised when input cannot be parsed as a supported read-only intent."""


class BaseReadOnlyIntent(BaseModel):
    """Common fields for read-only intents."""

    model_config = ConfigDict(frozen=True)

    kind: ReadOnlyIntentKind
    chain: str | None = None

    @field_validator("chain")
    @classmethod
    def normalize_chain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None


class NativeBalanceIntent(BaseReadOnlyIntent):
    """Read a wallet's native balance."""

    kind: Literal[ReadOnlyIntentKind.NATIVE_BALANCE] = ReadOnlyIntentKind.NATIVE_BALANCE
    wallet_address: str = Field(min_length=1)

    @field_validator("wallet_address")
    @classmethod
    def normalize_wallet_address(cls, value: str) -> str:
        return normalize_evm_address(value)


class ERC20MetadataIntent(BaseReadOnlyIntent):
    """Read ERC20 token metadata."""

    kind: Literal[ReadOnlyIntentKind.ERC20_METADATA] = ReadOnlyIntentKind.ERC20_METADATA
    token_address: str = Field(min_length=1)

    @field_validator("token_address")
    @classmethod
    def normalize_token_address(cls, value: str) -> str:
        return normalize_evm_address(value)


class ERC20BalanceIntent(BaseReadOnlyIntent):
    """Read an ERC20 token balance."""

    kind: Literal[ReadOnlyIntentKind.ERC20_BALANCE] = ReadOnlyIntentKind.ERC20_BALANCE
    token_address: str = Field(min_length=1)
    wallet_address: str = Field(min_length=1)

    @field_validator("token_address")
    @classmethod
    def normalize_token_address(cls, value: str) -> str:
        return normalize_evm_address(value)

    @field_validator("wallet_address")
    @classmethod
    def normalize_wallet_address(cls, value: str) -> str:
        return normalize_evm_address(value)


class ERC20AllowanceIntent(BaseReadOnlyIntent):
    """Read an ERC20 allowance."""

    kind: Literal[ReadOnlyIntentKind.ERC20_ALLOWANCE] = ReadOnlyIntentKind.ERC20_ALLOWANCE
    token_address: str = Field(min_length=1)
    owner_address: str = Field(min_length=1)
    spender_address: str = Field(min_length=1)

    @field_validator("token_address")
    @classmethod
    def normalize_token_address(cls, value: str) -> str:
        return normalize_evm_address(value)

    @field_validator("owner_address", "spender_address")
    @classmethod
    def normalize_allowance_address(cls, value: str) -> str:
        return normalize_evm_address(value)


class ContractReadIntent(BaseReadOnlyIntent):
    """Read a view or pure contract function."""

    kind: Literal[ReadOnlyIntentKind.CONTRACT_READ] = ReadOnlyIntentKind.CONTRACT_READ
    contract_address: str = Field(min_length=1)
    abi_fragment: list[dict[str, Any]] = Field(min_length=1)
    function_name: str = Field(min_length=1)
    args: list[Any] = Field(default_factory=list)

    @field_validator("contract_address")
    @classmethod
    def normalize_contract_address(cls, value: str) -> str:
        return normalize_evm_address(value)


class KnownAddressIntent(BaseReadOnlyIntent):
    """Resolve a ticker or protocol.deployment key via bundled JSON."""

    kind: Literal[ReadOnlyIntentKind.KNOWN_ADDRESS] = ReadOnlyIntentKind.KNOWN_ADDRESS
    category: Literal["token", "protocol"]
    key: str = Field(min_length=1)

    @field_validator("key")
    @classmethod
    def strip_key(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("key must not be empty.")
        return stripped


class UnsupportedIntent(BaseModel):
    """A non-executable intent with a user-safe reason."""

    model_config = ConfigDict(frozen=True)

    kind: Literal[ReadOnlyIntentKind.UNSUPPORTED] = ReadOnlyIntentKind.UNSUPPORTED
    reason: str


type ParsedIntent = (
    NativeBalanceIntent
    | ERC20BalanceIntent
    | ERC20AllowanceIntent
    | ERC20MetadataIntent
    | ContractReadIntent
    | KnownAddressIntent
    | UnsupportedIntent
)

_INTENT_MODELS: dict[ReadOnlyIntentKind, type[BaseReadOnlyIntent]] = {
    ReadOnlyIntentKind.NATIVE_BALANCE: NativeBalanceIntent,
    ReadOnlyIntentKind.ERC20_BALANCE: ERC20BalanceIntent,
    ReadOnlyIntentKind.ERC20_ALLOWANCE: ERC20AllowanceIntent,
    ReadOnlyIntentKind.ERC20_METADATA: ERC20MetadataIntent,
    ReadOnlyIntentKind.CONTRACT_READ: ContractReadIntent,
    ReadOnlyIntentKind.KNOWN_ADDRESS: KnownAddressIntent,
}

_KIND_ALIASES = {
    "get_native_balance": ReadOnlyIntentKind.NATIVE_BALANCE,
    "native_balance": ReadOnlyIntentKind.NATIVE_BALANCE,
    "eth_balance": ReadOnlyIntentKind.NATIVE_BALANCE,
    "get_erc20_balance": ReadOnlyIntentKind.ERC20_BALANCE,
    "erc20_balance": ReadOnlyIntentKind.ERC20_BALANCE,
    "token_balance": ReadOnlyIntentKind.ERC20_BALANCE,
    "get_erc20_allowance": ReadOnlyIntentKind.ERC20_ALLOWANCE,
    "erc20_allowance": ReadOnlyIntentKind.ERC20_ALLOWANCE,
    "allowance": ReadOnlyIntentKind.ERC20_ALLOWANCE,
    "get_erc20_metadata": ReadOnlyIntentKind.ERC20_METADATA,
    "erc20_metadata": ReadOnlyIntentKind.ERC20_METADATA,
    "token_metadata": ReadOnlyIntentKind.ERC20_METADATA,
    "read_contract": ReadOnlyIntentKind.CONTRACT_READ,
    "contract_read": ReadOnlyIntentKind.CONTRACT_READ,
    "known_address": ReadOnlyIntentKind.KNOWN_ADDRESS,
    "address_lookup": ReadOnlyIntentKind.KNOWN_ADDRESS,
    "lookup_known_address": ReadOnlyIntentKind.KNOWN_ADDRESS,
}

_VALUE_MOVING_WORDS = (
    "approve",
    "approval",
    "send",
    "transfer",
    "swap",
    "sign",
    "transaction",
    "tx",
)


def parse_readonly_intent(
    raw_input: Any,
    messages: list[BaseMessage] | None = None,
) -> ParsedIntent:
    """Parse structured or very simple text input into a read-only intent."""

    raw = _coerce_raw_input(raw_input, messages)
    if isinstance(raw, dict):
        return _parse_structured_intent(raw)
    if isinstance(raw, str):
        return _parse_text_intent(raw)
    return UnsupportedIntent(reason="Provide a structured read-only wallet intent.")


def _coerce_raw_input(raw_input: Any, messages: list[BaseMessage] | None) -> Any:
    if raw_input is not None:
        return raw_input
    if not messages:
        return None
    content = messages[-1].content
    return content if isinstance(content, str | dict) else str(content)


def _parse_structured_intent(raw: dict[str, Any]) -> ParsedIntent:
    payload = _unwrap_payload(raw)
    raw_kind = payload.get("kind", payload.get("type", payload.get("intent")))
    if not isinstance(raw_kind, str):
        return UnsupportedIntent(reason="Structured intents must include a kind.")

    kind = _KIND_ALIASES.get(raw_kind.strip().lower())
    if kind is None:
        return UnsupportedIntent(reason=f"Unsupported wallet intent: {raw_kind}.")

    model = _INTENT_MODELS[kind]
    try:
        return cast(ParsedIntent, model.model_validate({**payload, "kind": kind}))
    except ValidationError as exc:
        raise UnsupportedIntentError(_format_validation_error(exc)) from exc


def _unwrap_payload(raw: dict[str, Any]) -> dict[str, Any]:
    intent = raw.get("intent")
    if isinstance(intent, dict):
        return intent
    return raw


def _parse_text_intent(text: str) -> ParsedIntent:
    lowered = text.lower()
    if any(word in lowered for word in _VALUE_MOVING_WORDS):
        return UnsupportedIntent(
            reason="Value-moving wallet actions are not supported in this phase."
        )
    return UnsupportedIntent(reason="Use a structured read-only intent for wallet reads.")


def _format_validation_error(exc: ValidationError) -> str:
    first_error = exc.errors()[0]
    location = ".".join(str(part) for part in first_error["loc"])
    message = str(first_error["msg"])
    return f"Invalid read-only intent field '{location}': {message}."
