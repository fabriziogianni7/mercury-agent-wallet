from __future__ import annotations

from mercury.models import SignedTransactionResult
from mercury.models.signing import SignTransactionRequest
from mercury.models.wallets import WalletAddressResult

TEST_WALLET_ADDRESS = "0x000000000000000000000000000000000000bEEF"


class RecordingSigner:
    def __init__(
        self,
        events: list[str] | None = None,
        *,
        wallet_address: str = TEST_WALLET_ADDRESS,
        expected_to: str | None = None,
    ) -> None:
        self.events = events if events is not None else []
        self.wallet_address = wallet_address
        self.expected_to = expected_to
        self.sign_calls = 0

    def get_wallet_address(self, wallet_id: str) -> WalletAddressResult:
        self.events.append("address")
        return WalletAddressResult(wallet_id=wallet_id, address=self.wallet_address)

    def sign_transaction(self, request: SignTransactionRequest) -> SignedTransactionResult:
        self.events.append("sign")
        self.sign_calls += 1
        if self.expected_to is not None:
            assert request.prepared_transaction.transaction["to"] == self.expected_to
        return SignedTransactionResult(
            wallet_id=request.wallet.wallet_id,
            chain_id=request.chain_id,
            signer_address=self.wallet_address,
            raw_transaction_hex="0x02",
            tx_hash="0xabcd",
        )
