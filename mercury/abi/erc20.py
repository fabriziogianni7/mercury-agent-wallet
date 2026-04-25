"""Minimal ERC20 ABI fragments for read-only calls."""

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
