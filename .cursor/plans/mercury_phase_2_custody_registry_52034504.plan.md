---
name: Mercury Phase 2 Custody Registry
overview: Phase 2 connects the chain registry to 1Claw-managed secret references for RPC and API configuration, without introducing wallet private-key retrieval or signing.
todos:
  - id: secret-store-protocol
    content: Define SecretStore protocol and typed secret value model.
    status: pending
  - id: oneclaw-wrapper
    content: Implement OneClawSecretStore wrapper with sanitized errors.
    status: pending
  - id: fake-secret-store
    content: Add fake secret store for unit tests.
    status: pending
  - id: rpc-secret-paths
    content: Add Ethereum/Base RPC secret path metadata to chain registry.
    status: pending
  - id: rpc-resolution
    content: Implement RPC URL resolution through SecretStore.
    status: pending
  - id: custody-tests
    content: Test successful, missing, unsupported, and empty secret cases.
    status: pending
isProject: false
---

# Mercury Phase 2: Chain Registry And 1Claw Custody Wrapper

## Goal

Implement the real chain registry and 1Claw custody wrapper needed to resolve non-wallet secrets such as RPC URLs and provider API keys. This phase prepares Mercury to use 1Claw for all secret management while keeping signing out of scope.

## Scope

- Add a 1Claw client abstraction.
- Resolve Ethereum and Base RPC URLs through 1Claw secret references.
- Extend chain registry entries with RPC secret paths.
- Add typed errors for missing secrets and unsupported chains.
- Add config for 1Claw API base URL, vault ID, API key secret source, and optional agent ID.
- Add tests using fake 1Claw clients only.

## Out Of Scope

- No wallet private-key retrieval.
- No transaction signing.
- No blockchain RPC calls.
- No LangGraph routing changes except config imports if needed.

## Files To Build

- [`mercury/custody/oneclaw.py`](mercury/custody/oneclaw.py): 1Claw client protocol, SDK/HTTP adapter, fake test client.
- [`mercury/custody/errors.py`](mercury/custody/errors.py): custody-specific exceptions.
- [`mercury/config.py`](mercury/config.py): 1Claw settings and secret-path conventions.
- [`mercury/chains/registry.py`](mercury/chains/registry.py): chain lookup plus RPC secret reference metadata.
- [`mercury/chains/rpc.py`](mercury/chains/rpc.py): resolve RPC URLs through 1Claw.
- [`tests/test_oneclaw_custody.py`](tests/test_oneclaw_custody.py): fake-client tests.
- [`tests/test_rpc_resolution.py`](tests/test_rpc_resolution.py): chain-to-RPC secret resolution tests.

## 1Claw Secret Paths

- `mercury/rpc/ethereum`
- `mercury/rpc/base`
- `mercury/apis/lifi`
- `mercury/apis/cowswap`
- `mercury/apis/uniswap`

Wallet paths are reserved for later:

- `mercury/wallets/{wallet_id}/private_key`

## Implementation Steps

1. Add a `SecretStore` protocol with `get_secret(path: str) -> SecretValue`.
2. Add a `OneClawSecretStore` implementation behind that protocol.
3. Add a `FakeSecretStore` for tests.
4. Add typed secret response models that keep value access explicit.
5. Extend `ChainConfig` with `rpc_secret_path`.
6. Add `resolve_rpc_url(chain_name, secret_store)`.
7. Ensure errors do not include secret values.
8. Add tests for successful Ethereum/Base RPC resolution.
9. Add tests for missing secret, unsupported chain, and empty secret value.
10. Update README with 1Claw secret path conventions.

## Security Requirements

- Do not log secret values.
- Do not include secret values in exception messages.
- Do not add `.env` with real values.
- Keep the public interface path-based, not value-based.
- Wallet private-key paths must exist only as documented conventions, not as active retrieval logic.

## Acceptance Criteria

- Ethereum and Base resolve RPC URLs through a fake 1Claw store in tests.
- Missing 1Claw secrets produce clear sanitized errors.
- No wallet private-key fetch function exists yet.
- No graph state stores secret values.
- Tests pass without network access.