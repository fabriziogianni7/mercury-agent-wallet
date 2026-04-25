"""Custody and secret-store exports."""

from mercury.custody.errors import (
    CustodyError,
    EmptySecretValueError,
    SecretNotFoundError,
    SecretStoreError,
    SecretStoreUnavailableError,
    SignerError,
    SigningFailedError,
    SigningRequestError,
    WalletIdValidationError,
    WalletPrivateKeyError,
)
from mercury.custody.oneclaw import (
    FakeOneClawClient,
    FakeSecretStore,
    OneClawClient,
    OneClawHttpClient,
    OneClawSecretStore,
    SecretStore,
    SecretValue,
)
from mercury.custody.redaction import REDACTION, redact_secret_text, secret_text_leaked
from mercury.custody.signer import MercuryWalletSigner
from mercury.custody.wallets import (
    WALLET_PRIVATE_KEY_PATH_TEMPLATE,
    validate_wallet_id,
    wallet_private_key_path,
)

__all__ = [
    "CustodyError",
    "EmptySecretValueError",
    "FakeOneClawClient",
    "FakeSecretStore",
    "OneClawClient",
    "OneClawHttpClient",
    "OneClawSecretStore",
    "MercuryWalletSigner",
    "REDACTION",
    "SecretNotFoundError",
    "SecretStore",
    "SecretStoreError",
    "SecretStoreUnavailableError",
    "SecretValue",
    "SignerError",
    "SigningFailedError",
    "SigningRequestError",
    "WALLET_PRIVATE_KEY_PATH_TEMPLATE",
    "WalletIdValidationError",
    "WalletPrivateKeyError",
    "redact_secret_text",
    "secret_text_leaked",
    "validate_wallet_id",
    "wallet_private_key_path",
]
