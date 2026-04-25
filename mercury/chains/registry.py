"""Static chain registry with 1Claw RPC secret metadata."""

from mercury.config import get_settings
from mercury.models.chain import ChainConfig

DEFAULT_CHAIN_NAME = "ethereum"
_settings = get_settings()

ETHEREUM = ChainConfig(
    name="ethereum",
    chain_id=1,
    native_symbol="ETH",
    rpc_secret_path=_settings.ethereum_rpc_secret_path,
    block_explorer_url="https://etherscan.io",
)

BASE = ChainConfig(
    name="base",
    chain_id=8453,
    native_symbol="ETH",
    rpc_secret_path=_settings.base_rpc_secret_path,
    block_explorer_url="https://basescan.org",
)

_CHAINS_BY_NAME = {chain.name: chain for chain in (ETHEREUM, BASE)}
_CHAINS_BY_ID = {chain.chain_id: chain for chain in (ETHEREUM, BASE)}


class UnsupportedChainError(ValueError):
    """Raised when a chain is not supported by Mercury."""


def _supported_chains_text() -> str:
    return ", ".join(sorted(_CHAINS_BY_NAME))


def get_chain_by_name(name: str) -> ChainConfig:
    """Return a supported chain by canonical name."""

    normalized_name = name.strip().lower()
    try:
        return _CHAINS_BY_NAME[normalized_name]
    except KeyError as exc:
        msg = f"Unsupported chain name '{name}'. Supported chains: {_supported_chains_text()}."
        raise UnsupportedChainError(msg) from exc


def get_chain_by_id(chain_id: int) -> ChainConfig:
    """Return a supported chain by EVM chain ID."""

    try:
        return _CHAINS_BY_ID[chain_id]
    except KeyError as exc:
        msg = f"Unsupported chain ID '{chain_id}'. Supported chains: {_supported_chains_text()}."
        raise UnsupportedChainError(msg) from exc


def get_default_chain() -> ChainConfig:
    """Return Mercury's default chain."""

    return get_chain_by_name(DEFAULT_CHAIN_NAME)


def list_chains() -> tuple[ChainConfig, ...]:
    """Return all supported chains."""

    return tuple(_CHAINS_BY_NAME.values())
