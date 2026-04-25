import pytest
from mercury.custody import (
    WalletIdValidationError,
    validate_wallet_id,
    wallet_private_key_path,
)


@pytest.mark.parametrize(
    ("wallet_id", "expected_path"),
    [
        ("primary", "mercury/wallets/primary/private_key"),
        ("agent-1_wallet.main", "mercury/wallets/agent-1_wallet.main/private_key"),
    ],
)
def test_wallet_private_key_path_uses_oneclaw_convention(
    wallet_id: str,
    expected_path: str,
) -> None:
    assert wallet_private_key_path(wallet_id) == expected_path


@pytest.mark.parametrize(
    "wallet_id",
    [
        "",
        "   ",
        "../primary",
        "primary/../../escape",
        "primary/key",
        ".hidden",
        "primary..backup",
        "wallet:primary",
    ],
)
def test_wallet_id_rejects_unsafe_path_values(wallet_id: str) -> None:
    with pytest.raises(WalletIdValidationError):
        validate_wallet_id(wallet_id)
