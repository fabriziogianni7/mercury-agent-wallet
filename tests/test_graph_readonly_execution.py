from typing import Any

from langchain_core.tools import StructuredTool
from mercury.graph.agent import build_graph
from mercury.tools.registry import ReadOnlyToolRegistry

WALLET = "0x000000000000000000000000000000000000dEaD"
TOKEN = "0x000000000000000000000000000000000000cafE"


def test_fake_native_balance_tool_result_is_formatted() -> None:
    graph = build_graph(_fake_registry()).compile()

    result = graph.invoke({"raw_input": {"kind": "native_balance", "wallet_address": WALLET}})

    assert result["chain_reference"].name == "ethereum"
    assert result["selected_tool_name"] == "get_native_balance"
    assert result["tool_input"] == {"chain": "ethereum", "wallet_address": WALLET}
    assert result["tool_result"]["formatted"] == "1.5"
    assert "1.5 ETH on ethereum" in result["response_text"]


def test_fake_erc20_balance_tool_result_is_formatted_on_base() -> None:
    graph = build_graph(_fake_registry()).compile()

    result = graph.invoke(
        {
            "raw_input": {
                "kind": "erc20_balance",
                "chain": "base",
                "token_address": TOKEN.lower(),
                "wallet_address": WALLET.lower(),
            }
        }
    )

    assert result["chain_reference"].name == "base"
    assert result["selected_tool_name"] == "get_erc20_balance"
    assert result["tool_input"] == {
        "chain": "base",
        "token_address": TOKEN,
        "wallet_address": WALLET,
    }
    assert "42 USDC on base" in result["response_text"]


def test_fake_tool_error_becomes_sanitized_response() -> None:
    graph = build_graph(_fake_registry(raise_error=True)).compile()

    result = graph.invoke({"raw_input": {"kind": "native_balance", "wallet_address": WALLET}})

    assert "https://" not in result["response_text"]
    assert "mercury/rpc/" not in result["response_text"]
    assert "required chain configuration is unavailable" in result["response_text"]


def test_value_moving_text_is_rejected_without_tool_execution() -> None:
    graph = build_graph(_fake_registry()).compile()

    result = graph.invoke({"raw_input": "approve USDC for this spender"})

    assert "selected_tool_name" not in result
    assert result["parsed_intent"]["kind"] == "unsupported"
    assert "Value-moving wallet actions are not supported" in result["response_text"]


def _fake_registry(*, raise_error: bool = False) -> ReadOnlyToolRegistry:
    def get_native_balance(chain: str, wallet_address: str) -> dict[str, Any]:
        """Read a fake native balance."""

        if raise_error:
            raise RuntimeError("missing https://rpc.example.invalid mercury/rpc/ethereum")
        return {
            "chain": chain,
            "chain_id": 1,
            "wallet_address": wallet_address,
            "raw_wei": 1_500_000_000_000_000_000,
            "formatted": "1.5",
            "symbol": "ETH",
        }

    def get_erc20_balance(
        chain: str,
        token_address: str,
        wallet_address: str,
    ) -> dict[str, Any]:
        """Read a fake ERC20 balance."""

        return {
            "chain": chain,
            "chain_id": 8453,
            "token_address": token_address,
            "wallet_address": wallet_address,
            "raw_amount": 42_000_000,
            "formatted": "42",
            "decimals": 6,
            "symbol": "USDC",
            "name": "USD Coin",
        }

    return ReadOnlyToolRegistry(
        [
            StructuredTool.from_function(get_native_balance),
            StructuredTool.from_function(get_erc20_balance),
        ]
    )
