# Mercury

Mercury is the wallet-agent package for the Agentic Pantheon project.

This foundation creates the Python project scaffold, typed configuration, static
chain registry, initial domain models, a minimal LangGraph skeleton, 1Claw-backed
secret-store abstractions for non-wallet configuration, and read-only EVM/ERC20
tools.

## Phase 2 Boundaries

Mercury does not sign or send transactions in this phase. It also does not retrieve
private keys, call live RPC endpoints, integrate swap providers, expose FastAPI routes,
or integrate with pan-agentikit.

All secret-like values are represented as 1Claw secret paths. Tests use fake 1Claw
clients and secret stores only, so no real secrets or network access are required for
local development.

## Setup

```bash
uv sync
uv run pytest
uv run ruff check .
```

## Local Configuration

Copy `.env.example` to `.env` only when local overrides are needed. The default settings
load without any `.env` file.

The RPC entries are 1Claw secret paths such as `mercury/rpc/ethereum`; they are not RPC
URL values. Runtime callers resolve them through the custody `SecretStore` protocol.

## 1Claw Secret Paths

Mercury reserves these non-wallet paths for Phase 2 secret resolution:

- `mercury/rpc/ethereum`
- `mercury/rpc/base`
- `mercury/apis/lifi`
- `mercury/apis/cowswap`
- `mercury/apis/uniswap`

Wallet private-key paths are documented for later phases only:

- `mercury/wallets/{wallet_id}/private_key`

## Read-Only EVM Tools

Phase 3 adds read-only wallet tools for Ethereum and Base. Runtime callers inject a
`Web3ProviderFactory` backed by a custody `SecretStore`; tests use fake providers and
do not call live RPC endpoints.

```python
from mercury.custody import FakeSecretStore
from mercury.providers import Web3ProviderFactory
from mercury.tools import create_readonly_tools

store = FakeSecretStore({"mercury/rpc/ethereum": "https://eth.example.invalid"})
provider_factory = Web3ProviderFactory(store)

tools = create_readonly_tools(provider_factory)
```

The Phase 3 surface is read-only: native balances, ERC20 metadata, ERC20 balances,
ERC20 allowances, and generic view/pure contract calls. It does not retrieve private
keys, sign, approve, transfer, swap, or send transactions.

## Read-Only Graph Invocation

Phase 4 wires the read-only tools into LangGraph for structured wallet-read intents.
Ethereum is the default chain, and Base can be selected explicitly.

```python
from mercury.graph import build_graph
from mercury.tools import ReadOnlyToolRegistry, create_readonly_tools

registry = ReadOnlyToolRegistry(create_readonly_tools(provider_factory))
graph = build_graph(registry).compile()

result = graph.invoke(
    {
        "raw_input": {
            "kind": "native_balance",
            "wallet_address": "0x000000000000000000000000000000000000dEaD",
        }
    }
)
```

Supported structured `kind` values are `native_balance`, `erc20_balance`,
`erc20_allowance`, `erc20_metadata`, and `contract_read`. Value-moving requests such
as approvals, transfers, swaps, signing, and transaction submission remain out of
scope.
