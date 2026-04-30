from mercury.config import MercurySettings


def test_default_settings_load_without_secrets() -> None:
    settings = MercurySettings()

    assert settings.app_name == "Mercury Wallet Agent"
    assert settings.ethereum_rpc_secret_path == "mercury/rpc/ethereum"
    assert settings.base_rpc_secret_path == "mercury/rpc/base"
    assert settings.oneclaw_vault_id == "mercury"
    assert settings.oneclaw_api_key_secret_source == "MERCURY_ONECLAW_API_KEY"


def test_default_chain_is_ethereum() -> None:
    settings = MercurySettings()

    assert settings.default_chain == "ethereum"


def test_rpc_values_are_references_not_secret_values() -> None:
    settings = MercurySettings()

    paths = [
        settings.ethereum_rpc_secret_path,
        settings.base_rpc_secret_path,
        settings.arbitrum_rpc_secret_path,
        settings.optimism_rpc_secret_path,
        settings.monad_rpc_secret_path,
    ]
    assert all(path.startswith("mercury/rpc/") for path in paths)
    assert all("://" not in path for path in paths)
