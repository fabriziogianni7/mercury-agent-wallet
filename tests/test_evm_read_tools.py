from dataclasses import dataclass
from typing import Any

import pytest
from mercury.chains import get_chain_by_name
from mercury.models.chain import ChainConfig
from mercury.tools import create_readonly_tools, get_native_balance, read_contract

WALLET = "0x000000000000000000000000000000000000dEaD"
CONTRACT = "0x000000000000000000000000000000000000bEEF"


@dataclass(frozen=True)
class FakeProvider:
    chain: ChainConfig
    client: Any


class FakeProviderFactory:
    def __init__(self, client: Any) -> None:
        self.client = client

    def create(self, chain_name: str) -> FakeProvider:
        return FakeProvider(chain=get_chain_by_name(chain_name), client=self.client)


class FakeCall:
    def __init__(self, result: Any) -> None:
        self._result = result

    def call(self) -> Any:
        return self._result


class FakeFunctions:
    def __init__(self, responses: dict[tuple[str, tuple[Any, ...]], Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def __getattr__(self, name: str) -> Any:
        def factory(*args: Any) -> FakeCall:
            call = (name, args)
            self.calls.append(call)
            return FakeCall(self.responses[call])

        return factory


class FakeContract:
    def __init__(self, responses: dict[tuple[str, tuple[Any, ...]], Any]) -> None:
        self.functions = FakeFunctions(responses)


class FakeEth:
    def __init__(
        self,
        *,
        balance: int = 0,
        contract_responses: dict[tuple[str, tuple[Any, ...]], Any] | None = None,
    ) -> None:
        self.balance = balance
        self.contract_responses = contract_responses or {}
        self.balance_requests: list[str] = []
        self.contract_requests: list[dict[str, Any]] = []
        self.last_contract: FakeContract | None = None

    def get_balance(self, address: str) -> int:
        self.balance_requests.append(address)
        return self.balance

    def contract(self, *, address: str, abi: list[dict[str, Any]]) -> FakeContract:
        self.contract_requests.append({"address": address, "abi": abi})
        self.last_contract = FakeContract(self.contract_responses)
        return self.last_contract


class FakeWeb3:
    def __init__(self, eth: FakeEth) -> None:
        self.eth = eth


def test_get_native_balance_returns_raw_and_formatted_eth() -> None:
    eth = FakeEth(balance=1_500_000_000_000_000_000)
    factory = FakeProviderFactory(FakeWeb3(eth))

    result = get_native_balance(
        chain="ethereum",
        wallet_address=WALLET.lower(),
        provider_factory=factory,
    )

    assert result.raw_wei == 1_500_000_000_000_000_000
    assert result.formatted == "1.5"
    assert result.symbol == "ETH"
    assert result.wallet_address == WALLET
    assert eth.balance_requests == [WALLET]


def test_read_contract_calls_requested_view_function() -> None:
    responses = {("totalSupply", ()): 1_000}
    eth = FakeEth(contract_responses=responses)
    factory = FakeProviderFactory(FakeWeb3(eth))

    result = read_contract(
        chain="base",
        contract_address=CONTRACT.lower(),
        abi_fragment=[
            {
                "type": "function",
                "name": "totalSupply",
                "stateMutability": "view",
                "inputs": [],
                "outputs": [{"type": "uint256"}],
            }
        ],
        function_name="totalSupply",
        provider_factory=factory,
    )

    assert result.chain == "base"
    assert result.chain_id == 8453
    assert result.contract_address == CONTRACT
    assert result.result == 1_000
    assert eth.last_contract is not None
    assert eth.last_contract.functions.calls == [("totalSupply", ())]


def test_read_contract_rejects_mutating_abi_entries() -> None:
    factory = FakeProviderFactory(FakeWeb3(FakeEth()))

    with pytest.raises(ValueError, match="not read-only"):
        read_contract(
            chain="ethereum",
            contract_address=CONTRACT,
            abi_fragment=[
                {
                    "type": "function",
                    "name": "transfer",
                    "stateMutability": "nonpayable",
                    "inputs": [],
                    "outputs": [{"type": "bool"}],
                }
            ],
            function_name="transfer",
            provider_factory=factory,
        )


def test_read_contract_rejects_missing_function() -> None:
    factory = FakeProviderFactory(FakeWeb3(FakeEth()))

    with pytest.raises(ValueError, match="was not found"):
        read_contract(
            chain="ethereum",
            contract_address=CONTRACT,
            abi_fragment=[
                {
                    "type": "function",
                    "name": "balanceOf",
                    "stateMutability": "view",
                    "inputs": [],
                    "outputs": [{"type": "uint256"}],
                }
            ],
            function_name="totalSupply",
            provider_factory=factory,
        )


def test_readonly_langchain_tools_are_created() -> None:
    tools = create_readonly_tools(FakeProviderFactory(FakeWeb3(FakeEth())))

    assert {tool.name for tool in tools} == {
        "get_native_balance",
        "read_contract",
        "get_erc20_metadata",
        "get_erc20_balance",
        "get_erc20_allowance",
        "resolve_known_address",
    }
