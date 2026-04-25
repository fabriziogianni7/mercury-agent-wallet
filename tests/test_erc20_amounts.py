import pytest
from mercury.models.amounts import format_units, parse_units
from mercury.models.erc20 import ERC20Amount
from pydantic import ValidationError


def test_parse_usdc_decimal_amount_to_raw_units() -> None:
    assert parse_units("1.5", 6) == 1_500_000
    amount = ERC20Amount.from_human("1.5", 6)

    assert amount.raw_amount == 1_500_000
    assert amount.formatted == "1.5"


def test_parse_units_rejects_negative_amount() -> None:
    with pytest.raises(ValueError, match="negative"):
        parse_units("-1", 6)


def test_parse_units_rejects_too_many_decimal_places() -> None:
    with pytest.raises(ValueError, match="too many decimal"):
        parse_units("1.0000001", 6)


def test_erc20_amount_rejects_mismatched_human_and_raw_amounts() -> None:
    with pytest.raises(ValidationError, match="does not match"):
        ERC20Amount(human_amount="1.5", decimals=6, raw_amount=1)


def test_format_units_preserves_existing_decimal_behavior() -> None:
    assert format_units(2_500_000_000_000_000_000, 18) == "2.5"
