import json
from typing import Any

import pytest
from mercury.custody import (
    FakeSecretStore,
    MercuryWalletSigner,
    SigningFailedError,
    SigningRequestError,
    WalletPrivateKeyError,
)
from mercury.models import (
    PreparedEVMTransaction,
    SignTransactionRequest,
    SignTypedDataRequest,
    WalletRef,
)

PRIVATE_KEY = "0x1111111111111111111111111111111111111111111111111111111111111111"
UNPREFIXED_PRIVATE_KEY = PRIVATE_KEY.removeprefix("0x")
WALLET_ADDRESS = "0x19E7E376E7C213B7E7e7e46cc70A5dD086DAff2A"
WALLET_SECRET_PATH = "mercury/wallets/primary/private_key"


def test_get_wallet_address_derives_public_address_without_exposing_key() -> None:
    signer = MercuryWalletSigner(FakeSecretStore({WALLET_SECRET_PATH: PRIVATE_KEY}))

    result = signer.get_wallet_address("primary")

    assert result.address == WALLET_ADDRESS
    serialized = result.model_dump_json()
    assert PRIVATE_KEY not in serialized
    assert WALLET_SECRET_PATH not in serialized


def test_sign_transaction_accepts_unprefixed_key_and_returns_signed_payload() -> None:
    signer = MercuryWalletSigner(FakeSecretStore({WALLET_SECRET_PATH: UNPREFIXED_PRIVATE_KEY}))

    result = signer.sign_transaction(
        SignTransactionRequest(
            wallet=WalletRef(wallet_id="primary", expected_address=WALLET_ADDRESS.lower()),
            chain_id=1,
            prepared_transaction=PreparedEVMTransaction(
                chain_id=1,
                transaction=_legacy_transaction(),
            ),
        )
    )

    assert result.wallet_id == "primary"
    assert result.chain_id == 1
    assert result.signer_address == WALLET_ADDRESS
    assert result.raw_transaction_hex.startswith("0x")
    assert result.tx_hash.startswith("0x")
    assert PRIVATE_KEY not in result.model_dump_json()
    assert UNPREFIXED_PRIVATE_KEY not in result.model_dump_json()


def test_sign_transaction_rejects_expected_address_mismatch() -> None:
    signer = MercuryWalletSigner(FakeSecretStore({WALLET_SECRET_PATH: PRIVATE_KEY}))

    with pytest.raises(SigningRequestError) as exc_info:
        signer.sign_transaction(
            SignTransactionRequest(
                wallet=WalletRef(
                    wallet_id="primary",
                    expected_address="0x000000000000000000000000000000000000dEaD",
                ),
                chain_id=1,
                prepared_transaction=PreparedEVMTransaction(
                    chain_id=1,
                    transaction=_legacy_transaction(),
                ),
            )
        )

    assert PRIVATE_KEY not in str(exc_info.value)
    assert WALLET_SECRET_PATH not in str(exc_info.value)


def test_prepared_transaction_chain_id_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="chainId must match"):
        PreparedEVMTransaction(
            chain_id=8453,
            transaction=_legacy_transaction(),
        )


def test_malformed_private_key_error_is_sanitized() -> None:
    bad_key = f"{PRIVATE_KEY}bad"
    signer = MercuryWalletSigner(FakeSecretStore({WALLET_SECRET_PATH: bad_key}))

    with pytest.raises(WalletPrivateKeyError) as exc_info:
        signer.get_wallet_address("primary")

    assert bad_key not in str(exc_info.value)
    assert PRIVATE_KEY not in str(exc_info.value)
    assert WALLET_SECRET_PATH not in str(exc_info.value)


def test_sign_typed_data_returns_signature_without_private_key() -> None:
    signer = MercuryWalletSigner(FakeSecretStore({WALLET_SECRET_PATH: PRIVATE_KEY}))

    result = signer.sign_typed_data(
        SignTypedDataRequest(
            wallet=WalletRef(wallet_id="primary"),
            chain_id=1,
            typed_data=_typed_data(),
        )
    )

    assert result.signer_address == WALLET_ADDRESS
    assert result.signature.startswith("0x")
    assert result.message_hash.startswith("0x")
    assert PRIVATE_KEY not in result.model_dump_json()


def test_typed_data_domain_chain_id_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="domain chainId"):
        SignTypedDataRequest(
            wallet=WalletRef(wallet_id="primary"),
            chain_id=8453,
            typed_data=_typed_data(),
        )


def test_signing_failures_do_not_leak_key_material() -> None:
    signer = MercuryWalletSigner(FakeSecretStore({WALLET_SECRET_PATH: PRIVATE_KEY}))
    bad_transaction = _legacy_transaction()
    bad_transaction["from"] = "0x000000000000000000000000000000000000dEaD"

    with pytest.raises(SigningFailedError) as exc_info:
        signer.sign_transaction(
            SignTransactionRequest(
                wallet=WalletRef(wallet_id="primary"),
                chain_id=1,
                prepared_transaction=PreparedEVMTransaction(
                    chain_id=1,
                    transaction=bad_transaction,
                ),
            )
        )

    assert PRIVATE_KEY not in str(exc_info.value)
    assert WALLET_SECRET_PATH not in str(exc_info.value)


def test_private_key_absent_from_graph_state_like_serialization() -> None:
    signer = MercuryWalletSigner(FakeSecretStore({WALLET_SECRET_PATH: PRIVATE_KEY}))
    result = signer.get_wallet_address("primary")
    state_sample: dict[str, Any] = {
        "tool_result": result.model_dump(mode="json"),
        "response_text": f"Wallet primary address is {result.address}",
    }

    serialized = json.dumps(state_sample, sort_keys=True)

    assert PRIVATE_KEY not in serialized
    assert UNPREFIXED_PRIVATE_KEY not in serialized
    assert WALLET_SECRET_PATH not in serialized


def _legacy_transaction() -> dict[str, Any]:
    return {
        "chainId": 1,
        "nonce": 0,
        "gas": 21_000,
        "gasPrice": 1_000_000_000,
        "to": "0x000000000000000000000000000000000000dEaD",
        "value": 1,
        "data": "0x",
    }


def _typed_data() -> dict[str, Any]:
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Mail": [
                {"name": "contents", "type": "string"},
            ],
        },
        "primaryType": "Mail",
        "domain": {
            "name": "Mercury",
            "version": "1",
            "chainId": 1,
            "verifyingContract": "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC",
        },
        "message": {
            "contents": "Sign only inside Mercury custody boundary.",
        },
    }
