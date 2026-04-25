"""1Claw wallet secret path helpers."""

from __future__ import annotations

import re

from mercury.custody.errors import WalletIdValidationError

WALLET_PRIVATE_KEY_PATH_TEMPLATE = "mercury/wallets/{wallet_id}/private_key"

_SAFE_WALLET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def validate_wallet_id(wallet_id: str) -> str:
    """Validate and normalize a wallet ID before embedding it in a secret path."""

    candidate = wallet_id.strip()
    if (
        not candidate
        or not _SAFE_WALLET_ID.fullmatch(candidate)
        or candidate in {".", ".."}
        or ".." in candidate
    ):
        raise WalletIdValidationError(wallet_id)
    return candidate


def wallet_private_key_path(wallet_id: str) -> str:
    """Return the private-key secret path for a validated 1Claw wallet ID."""

    return WALLET_PRIVATE_KEY_PATH_TEMPLATE.format(wallet_id=validate_wallet_id(wallet_id))
