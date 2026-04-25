"""Minimal ERC20 ABI fragments for read and transaction preparation calls."""

from typing import Any

ERC20_BALANCE_OF_ABI: dict[str, Any] = {
    "type": "function",
    "name": "balanceOf",
    "stateMutability": "view",
    "inputs": [{"name": "account", "type": "address"}],
    "outputs": [{"name": "", "type": "uint256"}],
}

ERC20_ALLOWANCE_ABI: dict[str, Any] = {
    "type": "function",
    "name": "allowance",
    "stateMutability": "view",
    "inputs": [
        {"name": "owner", "type": "address"},
        {"name": "spender", "type": "address"},
    ],
    "outputs": [{"name": "", "type": "uint256"}],
}

ERC20_DECIMALS_ABI: dict[str, Any] = {
    "type": "function",
    "name": "decimals",
    "stateMutability": "view",
    "inputs": [],
    "outputs": [{"name": "", "type": "uint8"}],
}

ERC20_SYMBOL_ABI: dict[str, Any] = {
    "type": "function",
    "name": "symbol",
    "stateMutability": "view",
    "inputs": [],
    "outputs": [{"name": "", "type": "string"}],
}

ERC20_NAME_ABI: dict[str, Any] = {
    "type": "function",
    "name": "name",
    "stateMutability": "view",
    "inputs": [],
    "outputs": [{"name": "", "type": "string"}],
}

ERC20_TRANSFER_ABI: dict[str, Any] = {
    "type": "function",
    "name": "transfer",
    "stateMutability": "nonpayable",
    "inputs": [
        {"name": "to", "type": "address"},
        {"name": "amount", "type": "uint256"},
    ],
    "outputs": [{"name": "", "type": "bool"}],
}

ERC20_APPROVE_ABI: dict[str, Any] = {
    "type": "function",
    "name": "approve",
    "stateMutability": "nonpayable",
    "inputs": [
        {"name": "spender", "type": "address"},
        {"name": "amount", "type": "uint256"},
    ],
    "outputs": [{"name": "", "type": "bool"}],
}

ERC20_METADATA_ABI: list[dict[str, Any]] = [
    ERC20_DECIMALS_ABI,
    ERC20_SYMBOL_ABI,
    ERC20_NAME_ABI,
]

ERC20_READ_ABI: list[dict[str, Any]] = [
    ERC20_BALANCE_OF_ABI,
    ERC20_ALLOWANCE_ABI,
    *ERC20_METADATA_ABI,
]

ERC20_WRITE_ABI: list[dict[str, Any]] = [
    ERC20_TRANSFER_ABI,
    ERC20_APPROVE_ABI,
]

ERC20_TRANSACTION_ABI: list[dict[str, Any]] = [
    *ERC20_READ_ABI,
    *ERC20_WRITE_ABI,
]
