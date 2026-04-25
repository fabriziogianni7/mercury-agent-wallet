# Mercury

Mercury is the wallet-agent package for the Agentic Pantheon project.

This foundation creates the Python project scaffold, typed configuration, static
chain registry, initial domain models, a minimal LangGraph skeleton, 1Claw-backed
secret-store abstractions for non-wallet configuration, and read-only EVM/ERC20
tools.

## Safety Boundaries

Mercury keeps private-key retrieval inside the signer boundary and keeps live RPC/API
values behind 1Claw secret paths. Local tests use fake stores, fake providers, and fake
signers by default; they must not require real secrets, live RPC access, or transaction
broadcasts.

All secret-like values are represented as 1Claw secret paths. Tests use fake 1Claw
clients and secret stores only, so no real secrets or network access are required for
local development.

## Setup

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy mercury
```

Optional live read-only tests are skipped unless explicitly enabled and configured:

```bash
MERCURY_RUN_LIVE_TESTS=true \
ONECLAW_API_KEY=... \
ONECLAW_VAULT_ID=... \
uv run pytest -m "integration and live_rpc"
```

Live tests are read-only and must not fetch wallet private keys or broadcast
transactions. `ONECLAW_BASE_URL`, `ONECLAW_AGENT_ID`, and
`MERCURY_LIVE_READONLY_CHAIN` may be set for local integration checks.

## Local FastAPI Service

Phase 9 exposes the native Mercury HTTP boundary. Run it locally with:

```bash
uv run uvicorn mercury.service.api:app --reload
```

The service provides `GET /healthz`, `GET /readyz`, and native
`POST /v1/mercury/invoke`. Readiness validates local configuration and the static
chain registry only; it does not fetch wallet private keys.

## pan-agentikit Agent Boundary

Phase 10 adds `POST /v1/agent` for pan-agentikit-compatible envelopes while keeping
the native `/v1/mercury/invoke` contract unchanged. Mercury accepts `UserMessageV1`
and `TaskRequestV1` payloads, maps them into the same graph, policy, approval,
signing, and broadcast pipeline as native requests, and returns `AgentReplyV1`,
`TaskResultV1`, `WalletApprovalRequiredV1`, or sanitized `AgentErrorV1` envelopes.

Envelope metadata such as `trace_id`, `turn_id`, roles, parent step IDs, artifacts,
and idempotency keys is preserved across the adapter boundary. Value-moving task
requests must include an idempotency key before Mercury will invoke the graph.

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

Supported structured read-only `kind` values are `native_balance`, `erc20_balance`,
`erc20_allowance`, `erc20_metadata`, and `contract_read`.

## Swap Preparation

Phase 8 adds normalized swap providers for LiFi, CoW Swap, and Uniswap. Provider API
keys are optional, but when configured they are resolved only through 1Claw paths:
`mercury/apis/lifi`, `mercury/apis/cowswap`, and `mercury/apis/uniswap`.

Swap graph execution prepares the next safe transaction only. If allowance is
insufficient, Mercury prepares an ERC20 approval transaction first. If allowance is
sufficient, the provider-built swap transaction is policy-checked and then fed into
the same transaction pipeline used for ERC20 transfers: nonce, gas, simulation,
policy, human approval, idempotency, signer boundary, broadcast, and receipt
monitoring.

```python
result = graph.invoke(
    {
        "raw_input": {
            "kind": "swap",
            "chain": "base",
            "wallet_id": "primary",
            "from_token": "0x000000000000000000000000000000000000cafE",
            "to_token": "0x000000000000000000000000000000000000dEaD",
            "amount_in": "10",
            "max_slippage_bps": 50,
            "provider_preference": "lifi",
            "idempotency_key": "swap-base-usdc-1",
        }
    }
)
```
