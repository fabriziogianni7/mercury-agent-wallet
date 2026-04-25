from __future__ import annotations

from mercury.custody import FakeOneClawClient, OneClawSecretStore

TEST_PRIVATE_KEY = "0x1111111111111111111111111111111111111111111111111111111111111111"
TEST_RPC_URL = "https://rpc.example.invalid/secret-rpc-token"
TEST_ONECLAW_API_KEY = "oneclaw-api-key-test-only"
TEST_VAULT_ID = "vault-test-only"


def fake_oneclaw_secret_store(
    secrets: dict[str, str] | None = None,
) -> OneClawSecretStore:
    defaults = {
        "mercury/rpc/ethereum": TEST_RPC_URL,
        "mercury/rpc/base": "https://base.example.invalid/base-secret-token",
        "mercury/apis/lifi": "lifi-api-key-test-only",
        "mercury/apis/cowswap": "cowswap-api-key-test-only",
        "mercury/apis/uniswap": "uniswap-api-key-test-only",
        "mercury/wallets/primary/private_key": TEST_PRIVATE_KEY,
    }
    if secrets is not None:
        defaults.update(secrets)
    return OneClawSecretStore(
        client=FakeOneClawClient(defaults),
        vault_id=TEST_VAULT_ID,
        agent_id="agent-test-only",
    )
