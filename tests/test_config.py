from mercury.config import MercurySettings


def test_default_settings_load_without_secrets() -> None:
    settings = MercurySettings()

    assert settings.app_name == "Mercury Wallet Agent"
    assert settings.ethereum_rpc_secret_ref == "MERCURY_ETHEREUM_RPC_URL"
    assert settings.base_rpc_secret_ref == "MERCURY_BASE_RPC_URL"


def test_default_chain_is_ethereum() -> None:
    settings = MercurySettings()

    assert settings.default_chain == "ethereum"


def test_rpc_values_are_references_not_secret_values() -> None:
    settings = MercurySettings()

    refs = [settings.ethereum_rpc_secret_ref, settings.base_rpc_secret_ref]
    assert all(ref.startswith("MERCURY_") for ref in refs)
    assert all("://" not in ref for ref in refs)
