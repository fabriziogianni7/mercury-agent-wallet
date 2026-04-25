"""Swap provider selection and quote routing."""

from __future__ import annotations

from collections.abc import Iterable

from mercury.models.swaps import SwapProviderName, SwapQuote, SwapQuoteRequest
from mercury.swaps.base import SwapProvider, SwapProviderError


class SwapRouter:
    """Select providers and fetch normalized swap quotes."""

    def __init__(
        self,
        providers: Iterable[SwapProvider],
        *,
        provider_order: tuple[SwapProviderName, ...] = (
            SwapProviderName.LIFI,
            SwapProviderName.COWSWAP,
            SwapProviderName.UNISWAP,
        ),
    ) -> None:
        self._providers = {provider.name: provider for provider in providers}
        self._provider_order = provider_order

    def get_quote(
        self,
        request: SwapQuoteRequest,
        *,
        provider_preference: SwapProviderName | None = None,
    ) -> SwapQuote:
        """Fetch a quote from the selected provider."""

        provider = self.provider_for(provider_preference)
        return provider.get_quote(request)

    def provider_for(self, preference: SwapProviderName | None = None) -> SwapProvider:
        """Return a provider by preference or configured order."""

        if preference is not None:
            try:
                return self._providers[preference]
            except KeyError as exc:
                raise SwapProviderError(
                    f"Swap provider '{preference.value}' is not configured."
                ) from exc

        for name in self._provider_order:
            provider = self._providers.get(name)
            if provider is not None:
                return provider
        raise SwapProviderError("No swap providers are configured.")
