"""Web3 provider factory backed by 1Claw-resolved RPC URLs."""

from __future__ import annotations

from dataclasses import dataclass

from web3 import Web3

from mercury.chains import get_chain_by_name, resolve_rpc_url
from mercury.custody import SecretStore
from mercury.models.chain import ChainConfig


@dataclass(frozen=True)
class Web3Provider:
    """Chain-specific Web3 client and public chain metadata."""

    chain: ChainConfig
    client: Web3


class Web3ProviderFactory:
    """Create read-only Web3 clients from RPC URLs stored in SecretStore."""

    def __init__(self, secret_store: SecretStore) -> None:
        self._secret_store = secret_store

    def create(self, chain_name: str) -> Web3Provider:
        """Resolve the chain RPC URL and return a Web3 client."""

        chain = get_chain_by_name(chain_name)
        rpc_url = resolve_rpc_url(chain.name, self._secret_store)
        return Web3Provider(
            chain=chain,
            client=Web3(Web3.HTTPProvider(rpc_url)),
        )
