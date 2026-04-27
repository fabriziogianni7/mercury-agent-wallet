"""RPC URL resolution through Mercury's secret-store interface."""

from mercury.chains.registry import get_chain_by_name
from mercury.custody import SecretStore


def resolve_rpc_url(chain_name: str, secret_store: SecretStore) -> str:
    """Resolve a supported chain's RPC URL from the configured secret path."""

    chain = get_chain_by_name(chain_name)
    return secret_store.get_secret(chain.rpc_secret_path).reveal()
