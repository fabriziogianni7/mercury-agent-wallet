"""Sanitized custody-layer exceptions."""


class CustodyError(RuntimeError):
    """Base class for custody and secret-store failures."""


class SecretStoreError(CustodyError):
    """Base class for secret-store failures."""


class SecretNotFoundError(SecretStoreError):
    """Raised when a secret path is not present in the secret store."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Secret not found at path '{path}'.")
        self.path = path


class EmptySecretValueError(SecretStoreError):
    """Raised when a secret exists but has no usable value."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Secret at path '{path}' is empty.")
        self.path = path


class SecretStoreUnavailableError(SecretStoreError):
    """Raised when the backing secret store cannot be reached or queried."""

    def __init__(
        self,
        path: str,
        store_name: str = "secret store",
        *,
        detail: str | None = None,
    ) -> None:
        self.path = path
        self.store_name = store_name
        if detail is not None:
            super().__init__(f"{store_name}: {detail}")
        else:
            super().__init__(f"{store_name} could not resolve secret path '{path}'.")


class WalletIdValidationError(CustodyError):
    """Raised when a wallet ID is unsafe for 1Claw path resolution."""

    def __init__(self, wallet_id: str) -> None:
        super().__init__("Wallet ID is empty or contains unsupported path characters.")
        self.wallet_id = wallet_id


class SignerError(CustodyError):
    """Base class for sanitized signer-boundary failures."""


class WalletPrivateKeyError(SignerError):
    """Raised when a wallet private key cannot be used for signing."""

    def __init__(self, wallet_id: str) -> None:
        super().__init__(f"Wallet private key for wallet '{wallet_id}' is unavailable or invalid.")
        self.wallet_id = wallet_id


class SigningRequestError(SignerError):
    """Raised when a prepared signing request is invalid."""


class SigningFailedError(SignerError):
    """Raised when in-memory signing fails without exposing secret material."""

    def __init__(self) -> None:
        super().__init__("Prepared payload could not be signed.")
