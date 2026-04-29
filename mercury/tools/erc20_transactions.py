"""ERC20 transaction builders that stop at unsigned preparation."""

from __future__ import annotations

from typing import Protocol

from eth_abi.abi import encode
from pydantic import BaseModel, ConfigDict, Field
from web3 import Web3

from mercury.models.addresses import normalize_evm_address
from mercury.models.amounts import format_units, parse_integer_raw_amount
from mercury.models.erc20 import MAX_UINT256, ZERO_ADDRESS, ERC20Action, ERC20Amount
from mercury.models.execution import PreparedTransaction
from mercury.models.wallets import WalletAddressResult
from mercury.tools.erc20 import get_erc20_allowance, get_erc20_balance, get_erc20_metadata
from mercury.tools.evm import ProviderFactoryLike


class PublicAddressResolver(Protocol):
    """Signer boundary subset allowed for ERC20 transaction preparation."""

    def get_wallet_address(self, wallet_id: str) -> WalletAddressResult:
        """Return the public address for a wallet ID without exposing secret material."""


class ERC20TransferPreconditions(BaseModel):
    """Validated ERC20 transfer precondition data."""

    model_config = ConfigDict(frozen=True)

    chain: str
    chain_id: int = Field(gt=0)
    token_address: str
    owner_address: str
    recipient_address: str
    amount: ERC20Amount
    balance_raw: int = Field(ge=0)
    symbol: str | None = None
    name: str | None = None


def _erc20_amount_for_precondition(
    amount: str,
    decimals: int,
    *,
    amount_in_smallest_units: bool,
) -> ERC20Amount:
    """Build an amount from either a human decimal string or a raw integer string."""

    if amount_in_smallest_units:
        raw = parse_integer_raw_amount(amount)
        if raw > MAX_UINT256:
            raise ValueError("ERC20 raw amount must fit uint256.")
        return ERC20Amount(
            human_amount=format_units(raw, decimals),
            decimals=decimals,
            raw_amount=raw,
        )
    return ERC20Amount.from_human(amount, decimals)


class ERC20ApprovalPreconditions(BaseModel):
    """Validated ERC20 approval precondition data."""

    model_config = ConfigDict(frozen=True)

    chain: str
    chain_id: int = Field(gt=0)
    token_address: str
    owner_address: str
    spender_address: str
    amount: ERC20Amount
    current_allowance_raw: int = Field(ge=0)
    allowance_sufficient: bool
    unlimited_approval: bool = False
    spender_known: bool = False
    symbol: str | None = None
    name: str | None = None


def check_erc20_transfer_preconditions(
    *,
    chain: str,
    token_address: str,
    owner_address: str,
    recipient_address: str,
    amount: str,
    provider_factory: ProviderFactoryLike,
    amount_in_smallest_units: bool = False,
) -> ERC20TransferPreconditions:
    """Validate an ERC20 transfer and ensure the owner has enough token balance."""

    normalized_owner = normalize_evm_address(owner_address)
    normalized_recipient = normalize_evm_address(recipient_address)
    normalized_token = normalize_evm_address(token_address)
    _reject_zero_address(normalized_recipient, "Recipient")
    if normalized_owner == normalized_recipient:
        raise ValueError("ERC20 self-transfer is not allowed.")

    metadata = get_erc20_metadata(
        chain=chain,
        token_address=normalized_token,
        provider_factory=provider_factory,
    )
    token_amount = _erc20_amount_for_precondition(
        amount,
        metadata.decimals,
        amount_in_smallest_units=amount_in_smallest_units,
    )
    if token_amount.raw_amount <= 0:
        raise ValueError("Transfer amount must be greater than zero.")

    balance = get_erc20_balance(
        chain=metadata.chain,
        token_address=metadata.token_address,
        wallet_address=normalized_owner,
        provider_factory=provider_factory,
    )
    if balance.raw_amount < token_amount.raw_amount:
        raise ValueError("ERC20 token balance is insufficient for transfer.")

    return ERC20TransferPreconditions(
        chain=metadata.chain,
        chain_id=metadata.chain_id,
        token_address=metadata.token_address,
        owner_address=normalized_owner,
        recipient_address=normalized_recipient,
        amount=token_amount,
        balance_raw=balance.raw_amount,
        symbol=metadata.symbol,
        name=metadata.name,
    )


def check_erc20_approval_preconditions(
    *,
    chain: str,
    token_address: str,
    owner_address: str,
    spender_address: str,
    amount: str,
    provider_factory: ProviderFactoryLike,
    spender_known: bool = False,
    allow_unlimited: bool = False,
    amount_in_smallest_units: bool = False,
) -> ERC20ApprovalPreconditions:
    """Validate an ERC20 approval and inspect the existing allowance."""

    normalized_owner = normalize_evm_address(owner_address)
    normalized_spender = normalize_evm_address(spender_address)
    normalized_token = normalize_evm_address(token_address)
    _reject_zero_address(normalized_spender, "Spender")

    metadata = get_erc20_metadata(
        chain=chain,
        token_address=normalized_token,
        provider_factory=provider_factory,
    )
    token_amount = _approval_amount(
        amount,
        metadata.decimals,
        allow_unlimited=allow_unlimited,
        amount_in_smallest_units=amount_in_smallest_units,
    )
    unlimited_approval = token_amount.raw_amount == MAX_UINT256
    if unlimited_approval and not allow_unlimited:
        raise ValueError("Unlimited ERC20 approvals are rejected by default.")

    allowance = get_erc20_allowance(
        chain=metadata.chain,
        token_address=metadata.token_address,
        owner_address=normalized_owner,
        spender_address=normalized_spender,
        provider_factory=provider_factory,
    )

    return ERC20ApprovalPreconditions(
        chain=metadata.chain,
        chain_id=metadata.chain_id,
        token_address=metadata.token_address,
        owner_address=normalized_owner,
        spender_address=normalized_spender,
        amount=token_amount,
        current_allowance_raw=allowance.raw_amount,
        allowance_sufficient=allowance.raw_amount >= token_amount.raw_amount,
        unlimited_approval=unlimited_approval,
        spender_known=spender_known,
        symbol=metadata.symbol,
        name=metadata.name,
    )


def prepare_erc20_transfer(
    *,
    chain: str,
    wallet_id: str,
    token_address: str,
    recipient_address: str,
    amount: str,
    provider_factory: ProviderFactoryLike,
    address_resolver: PublicAddressResolver,
    idempotency_key: str | None = None,
    amount_in_smallest_units: bool = False,
) -> PreparedTransaction:
    """Prepare an unsigned ERC20 transfer transaction."""

    wallet = address_resolver.get_wallet_address(wallet_id)
    preconditions = check_erc20_transfer_preconditions(
        chain=chain,
        token_address=token_address,
        owner_address=wallet.address,
        recipient_address=recipient_address,
        amount=amount,
        provider_factory=provider_factory,
        amount_in_smallest_units=amount_in_smallest_units,
    )
    return _prepared_erc20_transaction(
        wallet_id=wallet_id,
        chain=preconditions.chain,
        chain_id=preconditions.chain_id,
        from_address=preconditions.owner_address,
        to=preconditions.token_address,
        data=encode_erc20_transfer_data(
            preconditions.recipient_address,
            preconditions.amount.raw_amount,
        ),
        idempotency_key=idempotency_key,
        metadata={
            "action": ERC20Action.TRANSFER.value,
            "token_address": preconditions.token_address,
            "recipient_address": preconditions.recipient_address,
            "amount": preconditions.amount.human_amount,
            "amount_raw": preconditions.amount.raw_amount,
            "decimals": preconditions.amount.decimals,
            "symbol": preconditions.symbol,
            "name": preconditions.name,
            "balance_raw": preconditions.balance_raw,
        },
    )


def prepare_erc20_approval(
    *,
    chain: str,
    wallet_id: str,
    token_address: str,
    spender_address: str,
    amount: str,
    provider_factory: ProviderFactoryLike,
    address_resolver: PublicAddressResolver,
    idempotency_key: str | None = None,
    spender_known: bool = False,
    allow_unlimited: bool = False,
    amount_in_smallest_units: bool = False,
) -> PreparedTransaction:
    """Prepare an unsigned ERC20 approve transaction."""

    wallet = address_resolver.get_wallet_address(wallet_id)
    preconditions = check_erc20_approval_preconditions(
        chain=chain,
        token_address=token_address,
        owner_address=wallet.address,
        spender_address=spender_address,
        amount=amount,
        provider_factory=provider_factory,
        spender_known=spender_known,
        allow_unlimited=allow_unlimited,
        amount_in_smallest_units=amount_in_smallest_units,
    )
    if preconditions.allowance_sufficient and preconditions.amount.raw_amount > 0:
        raise ValueError("Current allowance already satisfies requested ERC20 approval amount.")

    return _prepared_erc20_transaction(
        wallet_id=wallet_id,
        chain=preconditions.chain,
        chain_id=preconditions.chain_id,
        from_address=preconditions.owner_address,
        to=preconditions.token_address,
        data=encode_erc20_approval_data(
            preconditions.spender_address,
            preconditions.amount.raw_amount,
        ),
        idempotency_key=idempotency_key,
        metadata={
            "action": ERC20Action.APPROVAL.value,
            "token_address": preconditions.token_address,
            "spender_address": preconditions.spender_address,
            "amount": preconditions.amount.human_amount,
            "amount_raw": preconditions.amount.raw_amount,
            "decimals": preconditions.amount.decimals,
            "symbol": preconditions.symbol,
            "name": preconditions.name,
            "current_allowance_raw": preconditions.current_allowance_raw,
            "allowance_sufficient": preconditions.allowance_sufficient,
            "unlimited_approval": preconditions.unlimited_approval,
            "spender_known": preconditions.spender_known,
        },
    )


def encode_erc20_transfer_data(recipient_address: str, raw_amount: int) -> str:
    """Encode transfer(address,uint256) call data."""

    recipient = normalize_evm_address(recipient_address)
    _validate_uint256(raw_amount)
    return _encode_call(
        "transfer(address,uint256)",
        ["address", "uint256"],
        [recipient, raw_amount],
    )


def encode_erc20_approval_data(spender_address: str, raw_amount: int) -> str:
    """Encode approve(address,uint256) call data."""

    spender = normalize_evm_address(spender_address)
    _validate_uint256(raw_amount)
    return _encode_call("approve(address,uint256)", ["address", "uint256"], [spender, raw_amount])


def _approval_amount(
    amount: str,
    decimals: int,
    *,
    allow_unlimited: bool,
    amount_in_smallest_units: bool = False,
) -> ERC20Amount:
    normalized = amount.strip().lower()
    if amount_in_smallest_units and normalized not in {"max", "unlimited"}:
        raw = parse_integer_raw_amount(amount)
        if raw > MAX_UINT256:
            raise ValueError("ERC20 raw amount must fit uint256.")
        return ERC20Amount(
            human_amount=format_units(raw, decimals),
            decimals=decimals,
            raw_amount=raw,
        )
    if normalized in {"max", "unlimited"}:
        if not allow_unlimited:
            raise ValueError("Unlimited ERC20 approvals are rejected by default.")
        return ERC20Amount(
            human_amount=str(MAX_UINT256),
            decimals=0,
            raw_amount=MAX_UINT256,
        )

    token_amount = ERC20Amount.from_human(amount, decimals)
    if token_amount.raw_amount < 0:
        raise ValueError("Approval amount must not be negative.")
    return token_amount


def _prepared_erc20_transaction(
    *,
    wallet_id: str,
    chain: str,
    chain_id: int,
    from_address: str,
    to: str,
    data: str,
    idempotency_key: str | None,
    metadata: dict[str, object],
) -> PreparedTransaction:
    return PreparedTransaction(
        wallet_id=wallet_id,
        chain=chain,
        chain_id=chain_id,
        from_address=from_address,
        to=to,
        value_wei=0,
        data=data,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def _encode_call(signature: str, types: list[str], values: list[object]) -> str:
    selector = Web3.keccak(text=signature)[:4]
    return "0x" + (selector + encode(types, values)).hex()


def _validate_uint256(value: int) -> None:
    if value < 0 or value > MAX_UINT256:
        raise ValueError("ERC20 amount must fit uint256.")


def _reject_zero_address(address: str, label: str) -> None:
    if normalize_evm_address(address) == Web3.to_checksum_address(ZERO_ADDRESS):
        raise ValueError(f"{label} address must not be the zero address.")
