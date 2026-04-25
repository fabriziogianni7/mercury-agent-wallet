"""Isolated Mercury signer boundary for 1Claw-managed wallet keys."""

from __future__ import annotations

import re
from typing import Any

from eth_account import Account
from hexbytes import HexBytes

from mercury.custody.errors import (
    EmptySecretValueError,
    SecretNotFoundError,
    SignerError,
    SigningFailedError,
    SigningRequestError,
    WalletPrivateKeyError,
)
from mercury.custody.oneclaw import SecretStore
from mercury.custody.wallets import validate_wallet_id, wallet_private_key_path
from mercury.models.addresses import normalize_evm_address
from mercury.models.signing import (
    SignedTransactionResult,
    SignedTypedDataResult,
    SignTransactionRequest,
    SignTypedDataRequest,
)
from mercury.models.wallets import WalletAddressResult

_PRIVATE_KEY_HEX = re.compile(r"^(?:0x)?[a-fA-F0-9]{64}$")


class MercuryWalletSigner:
    """Signer boundary that keeps raw private keys inside custody code."""

    def __init__(self, secret_store: SecretStore) -> None:
        self._secret_store = secret_store

    def get_wallet_address(self, wallet_id: str) -> WalletAddressResult:
        """Derive the public EVM address for a 1Claw-managed wallet."""

        normalized_wallet_id = validate_wallet_id(wallet_id)
        private_key = self._load_private_key(normalized_wallet_id)
        try:
            address = normalize_evm_address(Account.from_key(private_key).address)
        except Exception:
            raise WalletPrivateKeyError(normalized_wallet_id) from None

        return WalletAddressResult(wallet_id=normalized_wallet_id, address=address)

    def sign_transaction(self, request: SignTransactionRequest) -> SignedTransactionResult:
        """Sign a prepared EVM transaction in memory without broadcasting it."""

        wallet_id = validate_wallet_id(request.wallet.wallet_id)
        private_key = self._load_private_key(wallet_id)
        signer_address = self._derive_address(wallet_id, private_key)
        self._validate_expected_address(request.wallet.expected_address, signer_address)

        try:
            signed = Account.sign_transaction(
                request.prepared_transaction.as_signable_dict(),
                private_key,
            )
            raw_transaction_hex = _hex(signed.raw_transaction)
            tx_hash = _hex(signed.hash)
        except SignerError:
            raise
        except Exception:
            raise SigningFailedError() from None

        return SignedTransactionResult(
            wallet_id=wallet_id,
            chain_id=request.chain_id,
            signer_address=signer_address,
            raw_transaction_hex=raw_transaction_hex,
            tx_hash=tx_hash,
        )

    def sign_typed_data(self, request: SignTypedDataRequest) -> SignedTypedDataResult:
        """Sign an EIP-712 typed-data payload in memory."""

        wallet_id = validate_wallet_id(request.wallet.wallet_id)
        private_key = self._load_private_key(wallet_id)
        signer_address = self._derive_address(wallet_id, private_key)
        self._validate_expected_address(request.wallet.expected_address, signer_address)

        try:
            signed = Account.sign_typed_data(private_key, full_message=dict(request.typed_data))
            signature = _hex(signed.signature)
            message_hash = _hex(signed.message_hash)
        except Exception:
            raise SigningFailedError() from None

        return SignedTypedDataResult(
            wallet_id=wallet_id,
            chain_id=request.chain_id,
            signer_address=signer_address,
            signature=signature,
            message_hash=message_hash,
        )

    def _load_private_key(self, wallet_id: str) -> str:
        path = wallet_private_key_path(wallet_id)
        try:
            secret = self._secret_store.get_secret(path)
            return _normalize_private_key(secret.reveal(), wallet_id=wallet_id)
        except (SecretNotFoundError, EmptySecretValueError, ValueError):
            raise WalletPrivateKeyError(wallet_id) from None

    def _derive_address(self, wallet_id: str, private_key: str) -> str:
        try:
            return normalize_evm_address(Account.from_key(private_key).address)
        except Exception:
            raise WalletPrivateKeyError(wallet_id) from None

    def _validate_expected_address(
        self,
        expected_address: str | None,
        signer_address: str,
    ) -> None:
        if expected_address is None:
            return
        if normalize_evm_address(expected_address) != signer_address:
            raise SigningRequestError("Expected wallet address does not match signing key.")


def _normalize_private_key(private_key: str, *, wallet_id: str) -> str:
    candidate = private_key.strip()
    if not _PRIVATE_KEY_HEX.fullmatch(candidate):
        raise WalletPrivateKeyError(wallet_id)
    if not candidate.startswith("0x"):
        candidate = f"0x{candidate}"
    return candidate


def _hex(value: Any) -> str:
    if isinstance(value, HexBytes):
        text = value.hex()
    elif isinstance(value, bytes):
        text = HexBytes(value).hex()
    else:
        text = str(value)
    if text.startswith("0x"):
        return text
    return f"0x{text}"
