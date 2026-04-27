from __future__ import annotations

import os

import pytest
from mercury.custody import OneClawHttpClient, OneClawSecretStore
from mercury.providers import Web3ProviderFactory


@pytest.mark.integration
@pytest.mark.live_rpc
@pytest.mark.requires_oneclaw
def test_optional_live_readonly_provider_factory_is_explicitly_gated() -> None:
    base_url = os.getenv("ONECLAW_BASE_URL", "https://oneclaw.example.invalid")
    api_key = os.environ["ONECLAW_API_KEY"]
    vault_id = os.environ["ONECLAW_VAULT_ID"]

    store = OneClawSecretStore(
        client=OneClawHttpClient(base_url=base_url, api_key=api_key),
        vault_id=vault_id,
        agent_id=os.getenv("ONECLAW_AGENT_ID"),
    )
    factory = Web3ProviderFactory(store)

    provider = factory.create(os.getenv("MERCURY_LIVE_READONLY_CHAIN", "ethereum"))

    assert provider.chain.name in {"ethereum", "base"}
    assert provider.client.is_connected(show_traceback=False) in {True, False}
