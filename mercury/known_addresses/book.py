"""Load curated token and protocol addresses shipped with Mercury."""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from importlib.resources import files
from typing import Any, Literal, cast

from mercury.models.addresses import normalize_evm_address

KnownCategory = Literal["token", "protocol"]


class KnownAddressMissingError(KeyError):
    """Raised when a symbol or protocol key has no mapping for the requested chain."""


def load_known_addresses() -> Mapping[str, Any]:
    """Return the parsed JSON document (immutable usage recommended)."""

    return cast(Mapping[str, Any], dict(_cached_document()))


@lru_cache(maxsize=1)
def _cached_document() -> dict[str, Any]:
    raw: Any = json.loads(
        files("mercury.data").joinpath("known_addresses.json").read_text(encoding="utf-8")
    )
    doc = cast(dict[str, Any], raw)
    _validate_and_normalize(doc)
    return doc


def _validate_and_normalize(doc: dict[str, Any]) -> None:
    chains = doc.get("chains")
    if not isinstance(chains, dict):
        msg = "known_addresses.json: missing chains object."
        raise ValueError(msg)

    for cid, block in chains.items():
        if not isinstance(block, dict):
            continue
        toks = block.get("tokens")
        if isinstance(toks, dict):
            rebuilt: dict[str, str] = {}
            for symbol, addr in toks.items():
                if not isinstance(addr, str):
                    raise ValueError(f"Chain {cid} token {symbol}: address must be a string.")
                rebuilt[str(symbol).upper()] = normalize_evm_address(addr)
            block["tokens"] = rebuilt
        protos = block.get("protocols")
        if isinstance(protos, dict):
            for _group, mapping in protos.items():
                if not isinstance(mapping, dict):
                    continue
                for pk, addr in list(mapping.items()):
                    if isinstance(addr, str) and addr.startswith("0x") and len(addr) >= 42:
                        mapping[pk] = normalize_evm_address(addr)


def _chain_id_string(chain: str | int, chain_name_to_id: Mapping[str, Any]) -> str:
    if isinstance(chain, int):
        return str(chain)
    normalized = chain.strip().lower()
    mapped = chain_name_to_id.get(normalized)
    if mapped is None:
        try:
            as_int = int(normalized)
        except ValueError:
            supported = ", ".join(sorted(chain_name_to_id))
            raise KnownAddressMissingError(
                f"Unknown chain {chain!r}. Known chains from known_addresses.json: {supported}. "
                "Use known_address after selecting a supported chain, or Mercury's chain registry."
            ) from None
        return str(as_int)
    return str(int(mapped))


def resolve_chain_catalog_ref(
    chain: str | int,
    doc: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """Return (*canonical_chain_name*, *chain_id_string*) using the bundled catalog."""

    payload = doc if doc is not None else _cached_document()
    name_map = cast(Mapping[str, Any], payload["chain_name_to_id"])
    cid_str = _chain_id_string(chain, name_map)
    for name, value in sorted(name_map.items()):
        if str(int(value)) == cid_str:
            return name, cid_str
    return cid_str, cid_str


def lookup_address(
    chain: str | int,
    category: KnownCategory,
    key: str,
) -> str:
    """Return a checksummed address for *key* on *chain* (*name*, id, or numeric string)."""

    doc = _cached_document()
    chains = cast(dict[str, Any], doc["chains"])
    name_map = cast(Mapping[str, Any], doc["chain_name_to_id"])
    cid = _chain_id_string(chain, name_map)

    block = chains.get(cid)
    if block is None:
        raise KnownAddressMissingError(
            f"No known_addresses bundle for chain_id={cid}. "
            f"Available chain ids: {', '.join(sorted(chains.keys()))}."
        )

    if category == "token":
        symbols = cast(dict[str, str], block.get("tokens") or {})
        symbol = key.strip().upper()
        addr = symbols.get(symbol)
        if addr is None:
            available = ", ".join(sorted(symbols)) or "(none)"
            raise KnownAddressMissingError(
                f"No token '{symbol}' on chain_id={cid}. Known tokens: {available}."
            )
        return addr

    protos = cast(dict[str, Any], block.get("protocols") or {})
    group, _, field = key.strip().partition(".")
    group = group.strip()
    field = field.strip()
    if not group or not field:
        raise KnownAddressMissingError(
            f"Protocol keys must look like PROTO.field (got {key!r}); "
            "e.g. AAVE_V3.pool or MORPHO.morpho_blue."
        )

    subtree = protos.get(group)
    if not isinstance(subtree, dict):
        raise KnownAddressMissingError(
            f"No protocol group {group!r} on chain_id={cid}. "
            f"Groups: {', '.join(sorted(str(k) for k in protos.keys())) or '(none)' }."
        )
    addr_any = subtree.get(field)
    if not isinstance(addr_any, str) or not addr_any.startswith("0x"):
        raise KnownAddressMissingError(
            f"No field {field!r} under {group!r} on chain_id={cid}."
        )
    return normalize_evm_address(addr_any)


def list_token_symbols(chain: str | int) -> list[str]:
    """Sorted token ticker list for this chain."""

    doc = _cached_document()
    cid = _chain_id_string(chain, cast(Mapping[str, Any], doc["chain_name_to_id"]))
    block = cast(dict[str, Any] | None, doc["chains"].get(cid))
    if block is None:
        return []
    toks = block.get("tokens")
    if not isinstance(toks, dict):
        return []
    return sorted(str(k) for k in toks)


def list_protocol_keys(chain: str | int) -> list[str]:
    """Flat PROTO.field keys."""

    doc = _cached_document()
    cid = _chain_id_string(chain, cast(Mapping[str, Any], doc["chain_name_to_id"]))
    block = cast(dict[str, Any] | None, doc["chains"].get(cid))
    if block is None:
        return []

    protos = block.get("protocols")
    if not isinstance(protos, dict):
        return []
    out: list[str] = []
    for group, mapping in protos.items():
        if not isinstance(mapping, dict):
            continue
        g = str(group)
        for field in mapping:
            out.append(f"{g}.{field}")
    return sorted(out)


def reload_known_addresses_for_tests() -> None:
    """Clear loader cache (tests only)."""

    _cached_document.cache_clear()
