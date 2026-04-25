"""Read-only EVM tools."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, cast

from langchain_core.tools import BaseTool, StructuredTool

from mercury.models.addresses import normalize_evm_address
from mercury.models.amounts import format_units
from mercury.models.chain import ChainConfig
from mercury.tools.schemas import (
    ContractReadInput,
    ContractReadOutput,
    NativeBalanceInput,
    NativeBalanceOutput,
)

READ_ONLY_MUTABILITY = {"view", "pure"}


class ProviderLike(Protocol):
    """Provider shape used by read-only tools."""

    @property
    def chain(self) -> ChainConfig:
        """Public chain metadata."""

    @property
    def client(self) -> Any:
        """Web3-compatible client."""


class ProviderFactoryLike(Protocol):
    """Factory shape used by read-only tools."""

    def create(self, chain_name: str) -> ProviderLike:
        """Return a chain-specific provider."""


def get_native_balance(
    *,
    chain: str,
    wallet_address: str,
    provider_factory: ProviderFactoryLike,
) -> NativeBalanceOutput:
    """Read a wallet's native balance."""

    normalized_wallet = normalize_evm_address(wallet_address)
    provider = provider_factory.create(chain)
    raw_wei = int(provider.client.eth.get_balance(normalized_wallet))

    return NativeBalanceOutput(
        chain=provider.chain.name,
        chain_id=provider.chain.chain_id,
        wallet_address=normalized_wallet,
        raw_wei=raw_wei,
        formatted=format_units(raw_wei, 18),
        symbol=provider.chain.native_symbol,
    )


def read_contract(
    *,
    chain: str,
    contract_address: str,
    abi_fragment: Sequence[Mapping[str, Any]] | Mapping[str, Any],
    function_name: str,
    args: Sequence[Any] | None = None,
    provider_factory: ProviderFactoryLike,
) -> ContractReadOutput:
    """Call a read-only contract function."""

    normalized_contract = normalize_evm_address(contract_address)
    normalized_abi = _normalize_abi_fragment(abi_fragment)
    _validate_read_only_function(normalized_abi, function_name)

    provider = provider_factory.create(chain)
    contract = provider.client.eth.contract(address=normalized_contract, abi=normalized_abi)
    result = _call_contract_function(contract, function_name, list(args or []))

    return ContractReadOutput(
        chain=provider.chain.name,
        chain_id=provider.chain.chain_id,
        contract_address=normalized_contract,
        function_name=function_name,
        result=result,
    )


def create_evm_tools(provider_factory: ProviderFactoryLike) -> list[BaseTool]:
    """Create LangChain-compatible EVM read tools bound to a provider factory."""

    def native_balance_tool(chain: str, wallet_address: str) -> dict[str, Any]:
        return get_native_balance(
            chain=chain,
            wallet_address=wallet_address,
            provider_factory=provider_factory,
        ).model_dump()

    def contract_read_tool(
        chain: str,
        contract_address: str,
        abi_fragment: list[dict[str, Any]],
        function_name: str,
        args: list[Any] | None = None,
    ) -> dict[str, Any]:
        return read_contract(
            chain=chain,
            contract_address=contract_address,
            abi_fragment=abi_fragment,
            function_name=function_name,
            args=args,
            provider_factory=provider_factory,
        ).model_dump()

    return [
        StructuredTool.from_function(
            func=native_balance_tool,
            name="get_native_balance",
            description="Read the native token balance for an EVM wallet address.",
            args_schema=NativeBalanceInput,
        ),
        StructuredTool.from_function(
            func=contract_read_tool,
            name="read_contract",
            description="Call a read-only EVM contract function from an ABI fragment.",
            args_schema=ContractReadInput,
        ),
    ]


def _normalize_abi_fragment(
    abi_fragment: Sequence[Mapping[str, Any]] | Mapping[str, Any],
) -> list[dict[str, Any]]:
    if isinstance(abi_fragment, Mapping):
        return [dict(abi_fragment)]
    return [dict(entry) for entry in abi_fragment]


def _validate_read_only_function(abi: Sequence[Mapping[str, Any]], function_name: str) -> None:
    matching_entries = [
        entry
        for entry in abi
        if entry.get("type", "function") == "function" and entry.get("name") == function_name
    ]
    if not matching_entries:
        msg = f"Function '{function_name}' was not found in the ABI fragment."
        raise ValueError(msg)

    entry = matching_entries[0]
    state_mutability = entry.get("stateMutability")
    if isinstance(state_mutability, str) and state_mutability not in READ_ONLY_MUTABILITY:
        msg = f"Function '{function_name}' is not read-only."
        raise ValueError(msg)

    constant = entry.get("constant")
    if constant is False:
        msg = f"Function '{function_name}' is not read-only."
        raise ValueError(msg)


def _call_contract_function(contract: Any, function_name: str, args: list[Any]) -> Any:
    function_collection = contract.functions
    function_factory = getattr(function_collection, function_name)
    return cast(Any, function_factory(*args).call())
