"""Swap provider adapters and routing utilities."""

from mercury.swaps.base import (
    JsonHttpClient,
    SwapProvider,
    SwapProviderConfig,
    SwapProviderError,
    UnsupportedSwapRoute,
    provider_api_key,
)
from mercury.swaps.cowswap import CowSwapProvider
from mercury.swaps.lifi import LiFiProvider
from mercury.swaps.router import SwapRouter
from mercury.swaps.uniswap import UniswapProvider

__all__ = [
    "CowSwapProvider",
    "JsonHttpClient",
    "LiFiProvider",
    "SwapProvider",
    "SwapProviderConfig",
    "SwapProviderError",
    "SwapRouter",
    "UniswapProvider",
    "UnsupportedSwapRoute",
    "provider_api_key",
]
