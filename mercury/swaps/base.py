"""Base interfaces for normalized swap providers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mercury.config import get_settings
from mercury.custody.oneclaw import SecretStore
from mercury.models.swaps import SwapExecution, SwapProviderName, SwapQuote, SwapQuoteRequest


class SwapProviderError(ValueError):
    """Raised when an untrusted provider response cannot be normalized safely."""


class UnsupportedSwapRoute(ValueError):
    """Raised when a provider cannot build a requested route."""


@runtime_checkable
class SwapProvider(Protocol):
    """Normalized swap provider interface."""

    name: SwapProviderName

    def get_quote(self, request: SwapQuoteRequest) -> SwapQuote:
        """Fetch and normalize a quote."""

    def build_execution(self, quote: SwapQuote) -> SwapExecution:
        """Build a normalized execution payload from a quote."""


@runtime_checkable
class JsonHttpClient(Protocol):
    """Small injectable JSON HTTP client surface used by provider adapters."""

    def get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Return a JSON object for a GET request."""

    def post_json(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Return a JSON object for a POST request."""


@dataclass(frozen=True)
class SwapProviderConfig:
    """Configuration for provider adapters; API keys stay behind 1Claw paths."""

    provider: SwapProviderName
    base_url: str
    api_secret_path: str | None = None
    secret_store: SecretStore | None = None

    @classmethod
    def default_for(
        cls,
        provider: SwapProviderName,
        *,
        secret_store: SecretStore | None = None,
    ) -> SwapProviderConfig:
        """Create provider config with Mercury's reserved 1Claw secret path."""

        settings = get_settings()
        paths = {
            SwapProviderName.LIFI: settings.lifi_api_secret_path,
            SwapProviderName.COWSWAP: settings.cowswap_api_secret_path,
            SwapProviderName.UNISWAP: settings.uniswap_api_secret_path,
        }
        base_urls = {
            SwapProviderName.LIFI: "https://li.quest/v1",
            SwapProviderName.COWSWAP: "https://api.cow.fi",
            SwapProviderName.UNISWAP: "https://api.uniswap.org",
        }
        return cls(
            provider=provider,
            base_url=base_urls[provider],
            api_secret_path=paths[provider],
            secret_store=secret_store,
        )


# Cloudflare and similar WAFs often return HTTP 403 / error 1010 for the default
# ``Python-urllib/x.y`` user agent (browser-integrity / bot heuristics). Realistic
# headers are required for public provider APIs in production.
_DEFAULT_HTTP_HEADERS: dict[str, str] = {
    "User-Agent": "Mercury/0.1 (EVM agent; https://github.com/fabriziogianni7/mercury-agent-wallet)",
    "Accept": "application/json",
}


def _merge_provider_headers(headers: dict[str, str] | None) -> dict[str, str]:
    return {**_DEFAULT_HTTP_HEADERS, **(headers or {})}


class UrllibJsonHttpClient:
    """Stdlib JSON client for live provider integrations."""

    def __init__(self, base_url: str) -> None:
        if not base_url.strip():
            raise ValueError("Provider base URL must not be empty.")
        self._base_url = base_url.rstrip("/")

    def get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        query = f"?{urlencode(params)}" if params else ""
        request = Request(
            f"{self._base_url}/{path.lstrip('/')}{query}",
            headers=_merge_provider_headers(headers),
            method="GET",
        )
        return self._send(request)

    def post_json(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        merged = _merge_provider_headers(headers)
        merged["Content-Type"] = "application/json"
        request = Request(
            f"{self._base_url}/{path.lstrip('/')}",
            data=json.dumps(payload).encode("utf-8"),
            headers=merged,
            method="POST",
        )
        return self._send(request)

    def _send(self, request: Request) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = _swap_http_error_detail(exc)
            raise SwapProviderError(f"Swap provider request failed ({detail}).") from exc
        except (URLError, OSError) as exc:
            raise SwapProviderError(
                f"Swap provider request failed ({type(exc).__name__}: {exc})."
            ) from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SwapProviderError(
                "Swap provider response was not valid JSON (non-JSON body or HTML error page)."
            ) from exc
        if not isinstance(payload, dict):
            raise SwapProviderError("Swap provider response must be a JSON object.")
        return payload


def _swap_http_error_detail(exc: HTTPError) -> str:
    """Short, log-safe detail for provider HTTP errors (status + optional body snippet)."""

    parts: list[str] = [f"HTTP {exc.code}"]
    if exc.reason:
        parts.append(str(exc.reason).strip())
    try:
        body = exc.read().decode("utf-8", errors="replace").strip()
        if body:
            snippet = body[:400].replace("\n", " ")
            if len(body) > 400:
                snippet += "…"
            parts.append(snippet)
    except Exception:
        pass
    return "; ".join(parts)


def provider_api_key(config: SwapProviderConfig) -> str | None:
    """Resolve an optional provider API key through 1Claw only."""

    if config.api_secret_path is None or config.secret_store is None:
        return None
    return config.secret_store.get_secret(config.api_secret_path).reveal()


def require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SwapProviderError(f"Swap provider response missing string field '{key}'.")
    return value


def require_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool):
        raise SwapProviderError(f"Swap provider response field '{key}' must be an integer.")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    raise SwapProviderError(f"Swap provider response missing integer field '{key}'.")


def optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        raise SwapProviderError(f"Swap provider response field '{key}' must be an integer.")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    raise SwapProviderError(f"Swap provider response field '{key}' must be an integer.")
