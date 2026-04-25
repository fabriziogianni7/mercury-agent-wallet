# Mercury

Mercury is the wallet-agent package for the Agentic Pantheon project.

This Phase 2 foundation creates the Python project scaffold, typed configuration,
static chain registry, initial domain models, a minimal LangGraph skeleton, and
1Claw-backed secret-store abstractions for non-wallet configuration.

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
