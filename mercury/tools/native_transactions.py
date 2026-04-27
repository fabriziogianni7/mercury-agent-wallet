"""Prepare unsigned native (gas token) transfer transactions."""

from mercury.chains import get_chain_by_name
from mercury.models.addresses import normalize_evm_address
from mercury.models.amounts import parse_units
from mercury.models.erc20 import ZERO_ADDRESS
from mercury.models.execution import PreparedTransaction
from mercury.tools.erc20_transactions import PublicAddressResolver


def prepare_native_transfer(
    *,
    chain: str,
    wallet_id: str,
    recipient_address: str,
    amount: str,
    address_resolver: PublicAddressResolver,
    idempotency_key: str | None = None,
) -> PreparedTransaction:
    """Build an unsigned native transfer (empty calldata, value in wei)."""

    chain_cfg = get_chain_by_name(chain)
    wallet = address_resolver.get_wallet_address(wallet_id)
    recipient = normalize_evm_address(recipient_address)
    if recipient == normalize_evm_address(ZERO_ADDRESS):
        raise ValueError("Native transfer recipient must not be the zero address.")
    if recipient == normalize_evm_address(wallet.address):
        raise ValueError("Native self-transfer is not allowed.")

    value_wei = parse_units(amount.strip(), 18)
    if value_wei <= 0:
        raise ValueError("Native transfer amount must be greater than zero.")

    return PreparedTransaction(
        wallet_id=wallet_id,
        chain=chain_cfg.name,
        chain_id=chain_cfg.chain_id,
        from_address=wallet.address,
        to=recipient,
        value_wei=value_wei,
        data="0x",
        idempotency_key=idempotency_key,
        metadata={
            "action": "native_transfer",
            "recipient_address": recipient,
            "amount_eth": amount.strip(),
        },
    )
