from __future__ import annotations

import os
from collections.abc import Iterable

import pytest

LIVE_MARKERS = {"integration", "live_rpc", "requires_oneclaw"}
LIVE_ENV_VARS = ("MERCURY_RUN_LIVE_TESTS", "ONECLAW_API_KEY", "ONECLAW_VAULT_ID")


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: Iterable[pytest.Item],
) -> None:
    live_enabled = os.getenv("MERCURY_RUN_LIVE_TESTS", "").lower() == "true"
    live_configured = live_enabled and all(os.getenv(name) for name in LIVE_ENV_VARS[1:])
    skip_live = pytest.mark.skip(
        reason=(
            "live integration tests require MERCURY_RUN_LIVE_TESTS=true, "
            "ONECLAW_API_KEY, and ONECLAW_VAULT_ID"
        )
    )

    for item in items:
        marker_names = {marker.name for marker in item.iter_markers()}
        if marker_names.intersection(LIVE_MARKERS) and not live_configured:
            item.add_marker(skip_live)
