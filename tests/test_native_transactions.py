from mercury.models.wallets import WalletAddressResult
from mercury.tools.native_transactions import prepare_native_transfer

WALLET = "0x000000000000000000000000000000000000bEEF"
RECIPIENT = "0x000000000000000000000000000000000000dEaD"


class FakeResolver:
    def get_wallet_address(self, wallet_id: str) -> WalletAddressResult:
        return WalletAddressResult(wallet_id=wallet_id, address=WALLET)


def test_prepare_native_transfer_targets_recipient_with_value() -> None:
    tx = prepare_native_transfer(
        chain="base",
        wallet_id="primary",
        recipient_address=RECIPIENT,
        amount="0.001",
        address_resolver=FakeResolver(),
        idempotency_key="n1",
    )
    assert tx.chain == "base"
    assert tx.to == RECIPIENT
    assert tx.value_wei == 1_000_000_000_000_000
    assert tx.data == "0x"
    assert tx.metadata["action"] == "native_transfer"


def test_prepare_native_transfer_rejects_self_transfer() -> None:
    try:
        prepare_native_transfer(
            chain="ethereum",
            wallet_id="primary",
            recipient_address=WALLET,
            amount="1",
            address_resolver=FakeResolver(),
        )
    except ValueError as exc:
        assert "self-transfer" in str(exc).lower()
    else:
        raise AssertionError("expected self-transfer error")
