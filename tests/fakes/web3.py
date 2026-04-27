from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mercury.chains import get_chain_by_name
from mercury.models.chain import ChainConfig


@dataclass(frozen=True)
class FakeProvider:
    chain: ChainConfig
    client: FakeWeb3


class FakeProviderFactory:
    def __init__(self, client: FakeWeb3) -> None:
        self.client = client
        self.created_chains: list[str] = []

    def create(self, chain_name: str) -> FakeProvider:
        self.created_chains.append(chain_name)
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
