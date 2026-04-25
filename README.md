# Mercury

Mercury is the wallet-agent package for the Agentic Pantheon project.

This Phase 1 foundation creates only the Python project scaffold, typed configuration,
static chain registry, initial domain models, and a minimal LangGraph skeleton.

## Phase 1 Boundaries

Mercury does not sign or send transactions in this phase. It also does not retrieve
private keys, call live RPC endpoints, integrate swap providers, expose FastAPI routes,
or integrate with pan-agentikit.

All secret-like values are represented as environment-variable names or future secret
references. No real secrets are required for local development.

## Setup

```bash
uv sync
uv run pytest
uv run ruff check .
```

## Local Configuration

Copy `.env.example` to `.env` only when local overrides are needed. The default settings
load without any `.env` file.

The RPC entries are reference names such as `MERCURY_ETHEREUM_RPC_URL`; they are not RPC
URL values. Future phases can resolve these references through the custody and secrets
layers.
