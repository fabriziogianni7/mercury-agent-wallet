"""Amount parsing and formatting helpers for native and token balances."""

from decimal import Decimal, InvalidOperation, localcontext

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_DECIMALS = 77


class InvalidTokenDecimalsError(ValueError):
    """Raised when token decimals are outside the supported range."""


def validate_token_decimals(decimals: int) -> int:
    """Validate ERC20 decimals before using them for formatting."""

    if decimals < 0 or decimals > MAX_DECIMALS:
        msg = f"Token decimals must be between 0 and {MAX_DECIMALS}."
        raise InvalidTokenDecimalsError(msg)
    return decimals


def format_units(raw_amount: int, decimals: int) -> str:
    """Format a raw integer amount into a decimal string."""

    validate_token_decimals(decimals)
    if raw_amount < 0:
        raise ValueError("Raw amount must not be negative.")

    if decimals == 0:
        return str(raw_amount)

    with localcontext() as context:
        context.prec = max(len(str(raw_amount)), decimals) + 2
        formatted = Decimal(raw_amount) / (Decimal(10) ** decimals)

    return format(formatted, "f")


def parse_units(amount: str, decimals: int) -> int:
    """Parse a human decimal amount into raw token units."""

    validate_token_decimals(decimals)
    candidate = amount.strip()
    if not candidate:
        raise ValueError("Amount must not be empty.")
    if candidate.startswith("+"):
        candidate = candidate[1:]

    try:
        parsed = Decimal(candidate)
    except InvalidOperation as exc:
        raise ValueError("Amount must be a valid decimal string.") from exc

    if not parsed.is_finite():
        raise ValueError("Amount must be finite.")
    if parsed < 0:
        raise ValueError("Amount must not be negative.")

    normalized = parsed.normalize()
    exponent = normalized.as_tuple().exponent
    fractional_digits = max(-exponent, 0) if isinstance(exponent, int) else 0
    if fractional_digits > decimals:
        raise ValueError("Amount has too many decimal places for token decimals.")

    with localcontext() as context:
        context.prec = max(len(candidate), decimals) + decimals + 4
        raw = parsed * (Decimal(10) ** decimals)

    if raw != raw.to_integral_value():
        raise ValueError("Amount has too many decimal places for token decimals.")
    return int(raw)


class FormattedAmount(BaseModel):
    """Raw and human-readable representation of an EVM amount."""

    model_config = ConfigDict(frozen=True)

    raw: int = Field(ge=0)
    formatted: str = Field(min_length=1)
    decimals: int = Field(ge=0, le=MAX_DECIMALS)

    @field_validator("decimals")
    @classmethod
    def validate_decimals(cls, value: int) -> int:
        return validate_token_decimals(value)
