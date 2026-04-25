"""Typed application settings for Mercury."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MercurySettings(BaseSettings):
    """Settings that store references to secrets, never secret values."""

    model_config = SettingsConfigDict(env_prefix="MERCURY_", env_file=None, extra="ignore")

    app_name: str = "Mercury Wallet Agent"
    default_chain: str = "ethereum"

    ethereum_rpc_secret_ref: str = Field(
        default="MERCURY_ETHEREUM_RPC_URL",
        description="Environment-variable or secret reference for Ethereum RPC.",
    )
    base_rpc_secret_ref: str = Field(
        default="MERCURY_BASE_RPC_URL",
        description="Environment-variable or secret reference for Base RPC.",
    )

    oneclaw_base_url_secret_ref: str = Field(
        default="MERCURY_ONECLAW_BASE_URL",
        description="Future 1Claw base URL reference; not resolved in Phase 1.",
    )
    oneclaw_api_key_secret_ref: str = Field(
        default="MERCURY_ONECLAW_API_KEY",
        description="Future 1Claw API key reference; not resolved in Phase 1.",
    )


@lru_cache
def get_settings() -> MercurySettings:
    """Return cached application settings."""

    return MercurySettings()
