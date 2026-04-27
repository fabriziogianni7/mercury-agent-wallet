from mercury.custody import redact_secret_text, secret_text_leaked

PRIVATE_KEY = "0x1111111111111111111111111111111111111111111111111111111111111111"


def test_redacts_private_keys_and_wallet_secret_paths() -> None:
    text = (
        f"failed with {PRIVATE_KEY} at mercury/wallets/primary/private_key "
        "using bearer:super-secret-token"
    )

    redacted = redact_secret_text(text)

    assert PRIVATE_KEY not in redacted
    assert "mercury/wallets/primary/private_key" not in redacted
    assert "super-secret-token" not in redacted
    assert "<redacted>" in redacted


def test_secret_text_leaked_detects_exact_secret_values() -> None:
    assert secret_text_leaked(f"bad output {PRIVATE_KEY}", [PRIVATE_KEY])
    assert not secret_text_leaked("safe output <redacted>", [PRIVATE_KEY])
