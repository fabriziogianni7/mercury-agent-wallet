from __future__ import annotations

import json
from typing import Any

import pytest
from mercury.graph.agent import build_graph

WALLET = "0x000000000000000000000000000000000000dEaD"
OWNER = "0x0000000000000000000000000000000000000001"
SPENDER = "0x0000000000000000000000000000000000000002"
TOKEN = "0x000000000000000000000000000000000000cafE"
CONTRACT = "0x000000000000000000000000000000000000bEEF"


@pytest.mark.parametrize(
    ("raw_input", "tool_name", "response_fragment"),
    [
        (
            {"kind": "native_balance", "wallet_address": WALLET},
            "get_native_balance",
            "1.5 ETH on ethereum",
        ),
        (
            {"kind": "erc20_metadata", "chain": "base", "token_address": TOKEN},
            "get_erc20_metadata",
            "USD Coin (USDC) on base has 6 decimals",
        ),
        (
            {
                "kind": "erc20_balance",
                "chain": "base",
                "token_address": TOKEN,
                "wallet_address": WALLET,
            },
            "get_erc20_balance",
            "42 USDC on base",
        ),
        (
            {
                "kind": "erc20_allowance",
                "chain": "base",
                "token_address": TOKEN,
                "owner_address": OWNER,
                "spender_address": SPENDER,
            },
            "get_erc20_allowance",
            "7 USDC from",
        ),
        (
            {
                "kind": "contract_read",
                "chain": "base",
                "contract_address": CONTRACT,
                "abi_fragment": [{"type": "function", "name": "totalSupply"}],
                "function_name": "totalSupply",
            },
            "read_contract",
            "totalSupply returned 1000 on base",
        ),
    ],
)
def test_readonly_graph_executes_each_full_route(
    raw_input: dict[str, Any],
    tool_name: str,
    response_fragment: str,
) -> None:
    graph = build_graph(_route_registry()).compile()

    result = graph.invoke({"raw_input": raw_input})

    assert result["selected_tool_name"] == tool_name
    assert response_fragment in result["response_text"]
    assert "error" not in result


def test_full_graph_routes_unsupported_intents_without_tool_execution() -> None:
    graph = build_graph(_route_registry()).compile()

    result = graph.invoke({"raw_input": {"kind": "approve", "wallet_address": WALLET}})

    assert "selected_tool_name" not in result
    assert result["parsed_intent"]["kind"] == "unsupported"
    assert "Unsupported operation" in result["response_text"]


def test_full_graph_error_state_is_sanitized_when_serialized() -> None:
    graph = build_graph(_route_registry(raise_error=True)).compile()

    result = graph.invoke({"raw_input": {"kind": "native_balance", "wallet_address": WALLET}})
    serialized = json.dumps(result, default=str, sort_keys=True)

    assert "https://rpc.example.invalid" not in serialized
    assert "mercury/rpc/base" not in serialized
    assert "required chain configuration is unavailable" in result["response_text"]


def _route_registry(*, raise_error: bool = False) -> Any:
    return RouteRegistry(raise_error=raise_error)


class RouteRegistry:
    def __init__(self, *, raise_error: bool = False) -> None:
        self.raise_error = raise_error

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "get_native_balance":
            return self._get_native_balance(tool_input)
        if tool_name == "get_erc20_metadata":
            return self._get_erc20_metadata(tool_input)
        if tool_name == "get_erc20_balance":
            return self._get_erc20_balance(tool_input)
        if tool_name == "get_erc20_allowance":
            return self._get_erc20_allowance(tool_input)
        if tool_name == "read_contract":
            return self._read_contract(tool_input)
        raise ValueError(f"unexpected tool: {tool_name}")

    def _get_native_balance(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        if self.raise_error:
            raise RuntimeError("missing https://rpc.example.invalid mercury/rpc/base")
        chain = str(tool_input["chain"])
        return {
            "chain": chain,
            "chain_id": 1 if chain == "ethereum" else 8453,
            "wallet_address": tool_input["wallet_address"],
            "raw_wei": 1_500_000_000_000_000_000,
            "formatted": "1.5",
            "symbol": "ETH",
        }

    def _get_erc20_metadata(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        return {
            "chain": tool_input["chain"],
            "chain_id": 8453,
            "token_address": tool_input["token_address"],
            "decimals": 6,
            "symbol": "USDC",
            "name": "USD Coin",
        }

    def _get_erc20_balance(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        return {
            "chain": tool_input["chain"],
            "chain_id": 8453,
            "token_address": tool_input["token_address"],
            "wallet_address": tool_input["wallet_address"],
            "raw_amount": 42_000_000,
            "formatted": "42",
            "decimals": 6,
            "symbol": "USDC",
        }

    def _get_erc20_allowance(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        return {
            "chain": tool_input["chain"],
            "chain_id": 8453,
            "token_address": tool_input["token_address"],
            "owner_address": tool_input["owner_address"],
            "spender_address": tool_input["spender_address"],
            "raw_amount": 7_000_000,
            "formatted": "7",
            "decimals": 6,
            "symbol": "USDC",
        }

    def _read_contract(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        return {
            "chain": tool_input["chain"],
            "chain_id": 8453,
            "contract_address": tool_input["contract_address"],
            "function_name": tool_input["function_name"],
            "result": 1_000,
        }
