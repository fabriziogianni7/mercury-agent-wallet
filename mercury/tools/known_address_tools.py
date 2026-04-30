"""Read-only lookup for bundled token / protocol addresses."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.tools import BaseTool, StructuredTool

from mercury.known_addresses.book import (
    KnownCategory,
    lookup_address,
    resolve_chain_catalog_ref,
)

CategoryInput = Literal["token", "protocol"]


def resolve_known_address(chain: str, category: CategoryInput, key: str) -> dict[str, Any]:
    """Return structured lookup result including checksum contract address."""

    cat: KnownCategory = category
    canonical_name, cid_str = resolve_chain_catalog_ref(chain)
    address = lookup_address(chain, cat, key)
    return {
        "chain": canonical_name,
        "chain_id": int(cid_str),
        "category": category,
        "key": key.strip(),
        "address": address,
    }


def create_known_address_tools() -> list[BaseTool]:
    """Tools that require no RPC provider."""

    def tool(chain: str, category: CategoryInput, key: str) -> dict[str, Any]:
        return resolve_known_address(chain, category, key)

    return [
        StructuredTool.from_function(
            name="resolve_known_address",
            description=(
                "Resolve a ticker (category=token) or protocol.field (category=protocol) "
                "to an EIP-55 address using mercury/data/known_addresses.json."
            ),
            func=tool,
        )
    ]
