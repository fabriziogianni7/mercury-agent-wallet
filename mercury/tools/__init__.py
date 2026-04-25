"""Read-only tool exports."""

from langchain_core.tools import BaseTool

from mercury.tools.erc20 import (
    create_erc20_tools,
    get_erc20_allowance,
    get_erc20_balance,
    get_erc20_metadata,
)
from mercury.tools.erc20_transactions import (
    ERC20ApprovalPreconditions,
    ERC20TransferPreconditions,
    check_erc20_approval_preconditions,
    check_erc20_transfer_preconditions,
    encode_erc20_approval_data,
    encode_erc20_transfer_data,
    prepare_erc20_approval,
    prepare_erc20_transfer,
)
from mercury.tools.evm import (
    ProviderFactoryLike,
    create_evm_tools,
    get_native_balance,
    read_contract,
)
from mercury.tools.registry import ReadOnlyToolRegistry
from mercury.tools.schemas import (
    ContractReadInput,
    ContractReadOutput,
    ERC20AllowanceInput,
    ERC20AllowanceOutput,
    ERC20BalanceInput,
    ERC20BalanceOutput,
    ERC20MetadataInput,
    ERC20MetadataOutput,
    NativeBalanceInput,
    NativeBalanceOutput,
)


def create_readonly_tools(provider_factory: ProviderFactoryLike) -> list[BaseTool]:
    """Create all LangChain-compatible read-only Mercury tools."""

    return [
        *create_evm_tools(provider_factory),
        *create_erc20_tools(provider_factory),
    ]


__all__ = [
    "ContractReadInput",
    "ContractReadOutput",
    "ERC20AllowanceInput",
    "ERC20AllowanceOutput",
    "ERC20ApprovalPreconditions",
    "ERC20BalanceInput",
    "ERC20BalanceOutput",
    "ERC20MetadataInput",
    "ERC20MetadataOutput",
    "ERC20TransferPreconditions",
    "NativeBalanceInput",
    "NativeBalanceOutput",
    "ProviderFactoryLike",
    "ReadOnlyToolRegistry",
    "create_erc20_tools",
    "create_evm_tools",
    "create_readonly_tools",
    "check_erc20_approval_preconditions",
    "check_erc20_transfer_preconditions",
    "encode_erc20_approval_data",
    "encode_erc20_transfer_data",
    "get_erc20_allowance",
    "get_erc20_balance",
    "get_erc20_metadata",
    "get_native_balance",
    "prepare_erc20_approval",
    "prepare_erc20_transfer",
    "read_contract",
]
