"""Generic EVM transaction execution tools and fakeable boundaries."""

from __future__ import annotations

import time
from typing import Any, Protocol

from eth_typing import HexStr
from hexbytes import HexBytes

from mercury.graph.responses import sanitize_error
from mercury.models.approval import ApprovalRequest, ApprovalResult, ApprovalStatus
from mercury.models.execution import (
    ExecutableTransaction,
    ExecutionStatus,
    PreparedTransaction,
    TransactionReceipt,
)
from mercury.models.gas import GasFees
from mercury.models.signing import SignedTransactionResult, SignTransactionRequest
from mercury.models.simulation import SimulationResult, SimulationStatus
from mercury.models.wallets import WalletAddressResult, WalletRef
from mercury.providers.web3 import Web3ProviderFactory


class TransactionBackend(Protocol):
    """Provider-backed transaction operations used by the graph."""

    def resolve_chain_id(self, transaction: PreparedTransaction) -> int:
        """Return the canonical chain ID for a prepared transaction."""

    def lookup_nonce(self, transaction: PreparedTransaction, wallet_address: str) -> int:
        """Return the next transaction nonce for a wallet."""

    def populate_gas(self, transaction: PreparedTransaction | ExecutableTransaction) -> GasFees:
        """Estimate gas and populate EIP-1559 or legacy fee fields."""

    def simulate(self, transaction: ExecutableTransaction) -> SimulationResult:
        """Run transaction preflight checks."""

    def broadcast(self, signed_transaction: SignedTransactionResult) -> str:
        """Broadcast a signed raw transaction and return its hash."""

    def wait_for_receipt(
        self,
        *,
        chain: str,
        tx_hash: str,
        timeout_seconds: float,
        confirmations: int,
    ) -> TransactionReceipt:
        """Wait for a transaction receipt."""


class TransactionSigner(Protocol):
    """Phase 5 signer boundary required by the transaction graph."""

    def get_wallet_address(self, wallet_id: str) -> WalletAddressResult:
        """Return the public wallet address."""

    def sign_transaction(self, request: SignTransactionRequest) -> SignedTransactionResult:
        """Sign a fully prepared transaction."""


class TransactionApprover(Protocol):
    """Human approval boundary."""

    def request_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """Request approval for a value-moving transaction."""


class PlaceholderTransactionApprover:
    """Explicit placeholder that prevents unattended value-moving execution."""

    def request_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """Return a required approval result until a human approval runtime is wired."""

        return _default_required_approval(request)


class RequestMetadataTransactionApprover:
    """Approve only when the inbound HTTP request included an explicit approval payload.

    ``ApprovalRequest.metadata`` is populated from the prepared transaction, which
    merges service intent metadata (including ``approval_response`` from
    ``MercuryInvokeRequest``).
    """

    def request_approval(self, request: ApprovalRequest) -> ApprovalResult:
        meta = request.metadata
        if not isinstance(meta, dict):
            return _default_required_approval(request)

        raw = meta.get("approval_response")
        if not isinstance(raw, dict):
            return _default_required_approval(request)

        status = str(raw.get("status", "")).strip().lower()
        if status == ApprovalStatus.DENIED.value:
            return ApprovalResult(
                status=ApprovalStatus.DENIED,
                reason=str(raw.get("reason") or "Approval denied."),
            )
        if status != ApprovalStatus.APPROVED.value:
            return _default_required_approval(request)

        optional_key = raw.get("idempotency_key")
        if optional_key is not None and str(optional_key) != str(request.idempotency_key):
            return ApprovalResult(
                status=ApprovalStatus.DENIED,
                reason="Approval idempotency key does not match transaction.",
            )

        approved_by = raw.get("approved_by")
        reason = str(raw.get("reason") or "Approved via request metadata.")
        return ApprovalResult(
            status=ApprovalStatus.APPROVED,
            reason=reason,
            approved_by=str(approved_by) if approved_by is not None else None,
        )


def _default_required_approval(request: ApprovalRequest) -> ApprovalResult:
    return ApprovalResult(
        status=ApprovalStatus.REQUIRED,
        reason=f"Human approval is required before signing {request.idempotency_key}.",
    )


class Web3TransactionBackend:
    """Web3-backed implementation of generic EVM transaction operations."""

    def __init__(self, provider_factory: Web3ProviderFactory) -> None:
        self._provider_factory = provider_factory

    def resolve_chain_id(self, transaction: PreparedTransaction) -> int:
        provider = self._provider_factory.create(transaction.chain)
        return provider.chain.chain_id

    def lookup_nonce(self, transaction: PreparedTransaction, wallet_address: str) -> int:
        provider = self._provider_factory.create(transaction.chain)
        eth: Any = provider.client.eth
        return int(eth.get_transaction_count(wallet_address, "pending"))

    def populate_gas(self, transaction: PreparedTransaction | ExecutableTransaction) -> GasFees:
        if transaction.gas is not None:
            return transaction.gas

        provider = self._provider_factory.create(transaction.chain)
        tx_fields = _transaction_fields(transaction)
        eth: Any = provider.client.eth
        gas_limit = int(eth.estimate_gas(tx_fields))
        try:
            priority_fee = int(eth.max_priority_fee)
            latest_block = eth.get_block("latest")
            base_fee = int(latest_block["baseFeePerGas"])
            return GasFees(
                gas_limit=gas_limit,
                max_fee_per_gas=(base_fee * 2) + priority_fee,
                max_priority_fee_per_gas=priority_fee,
            )
        except Exception:
            return GasFees(gas_limit=gas_limit, gas_price=int(eth.gas_price))

    def simulate(self, transaction: ExecutableTransaction) -> SimulationResult:
        provider = self._provider_factory.create(transaction.chain)
        try:
            if provider.chain.chain_id != transaction.chain_id:
                return SimulationResult(
                    status=SimulationStatus.FAILED,
                    reason="Prepared transaction chain_id does not match resolved chain.",
                )
            tx_fields = _transaction_fields(transaction)
            eth: Any = provider.client.eth
            eth.call(tx_fields)
            gas_estimate = int(eth.estimate_gas(tx_fields))
            if transaction.from_address is not None:
                balance = int(eth.get_balance(transaction.from_address))
                max_fee_per_gas = transaction.gas.max_fee_per_gas or transaction.gas.gas_price or 0
                required_wei = transaction.value_wei + (transaction.gas.gas_limit * max_fee_per_gas)
                if balance < required_wei:
                    return SimulationResult(
                        status=SimulationStatus.FAILED,
                        gas_estimate=gas_estimate,
                        reason="Wallet balance is insufficient for value plus maximum gas.",
                    )
            return SimulationResult(status=SimulationStatus.PASSED, gas_estimate=gas_estimate)
        except Exception as exc:
            return SimulationResult(status=SimulationStatus.FAILED, reason=sanitize_error(exc))

    def broadcast(self, signed_transaction: SignedTransactionResult) -> str:
        provider = self._provider_factory.create(_chain_name_for_id(signed_transaction.chain_id))
        eth: Any = provider.client.eth
        tx_hash = eth.send_raw_transaction(HexStr(signed_transaction.raw_transaction_hex))
        return _hex(tx_hash)

    def wait_for_receipt(
        self,
        *,
        chain: str,
        tx_hash: str,
        timeout_seconds: float,
        confirmations: int,
    ) -> TransactionReceipt:
        provider = self._provider_factory.create(chain)
        try:
            eth: Any = provider.client.eth
            receipt = eth.wait_for_transaction_receipt(
                HexStr(tx_hash),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            return TransactionReceipt(tx_hash=tx_hash, status=ExecutionStatus.PENDING)

        if confirmations > 0:
            self._wait_for_confirmations(
                provider.client,
                int(receipt["blockNumber"]),
                confirmations,
            )

        return TransactionReceipt(
            tx_hash=_hex(receipt["transactionHash"]),
            status=ExecutionStatus.CONFIRMED
            if int(receipt.get("status", 1)) == 1
            else ExecutionStatus.FAILED,
            block_number=int(receipt["blockNumber"]),
            gas_used=int(receipt["gasUsed"]),
        )

    def _wait_for_confirmations(self, client: Any, block_number: int, confirmations: int) -> None:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            current_block = int(client.eth.block_number)
            if current_block - block_number + 1 >= confirmations:
                return
            time.sleep(1)


def build_approval_request(transaction: ExecutableTransaction) -> ApprovalRequest:
    """Create human-readable approval prompt data."""

    return ApprovalRequest(
        wallet_id=transaction.wallet_id,
        chain=transaction.chain,
        chain_id=transaction.chain_id,
        from_address=transaction.from_address,
        to=transaction.to,
        value_wei=transaction.value_wei,
        data=transaction.data,
        idempotency_key=transaction.idempotency_key or "",
        metadata=transaction.metadata,
    )


def sign_executable_transaction(
    *,
    signer: TransactionSigner,
    transaction: ExecutableTransaction,
) -> SignedTransactionResult:
    """Sign through the Phase 5 signer boundary."""

    return signer.sign_transaction(
        SignTransactionRequest(
            wallet=WalletRef(
                wallet_id=transaction.wallet_id,
                expected_address=transaction.from_address,
            ),
            chain_id=transaction.chain_id,
            prepared_transaction=transaction.to_prepared_evm_transaction(),
        )
    )


def _transaction_fields(transaction: PreparedTransaction | ExecutableTransaction) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "chainId": transaction.chain_id,
        "from": transaction.from_address,
        "to": transaction.to,
        "value": transaction.value_wei,
        "data": transaction.data,
        "nonce": transaction.nonce,
    }
    if transaction.gas is not None:
        fields.update(transaction.gas.to_transaction_fields())
    return {key: value for key, value in fields.items() if value is not None}


def _chain_name_for_id(chain_id: int) -> str:
    from mercury.chains import get_chain_by_id

    return get_chain_by_id(chain_id).name


def _hex(value: Any) -> str:
    """Normalize hashes and binary blobs to a ``0x``-prefixed hex string for API models."""

    if isinstance(value, HexBytes):
        text = value.hex()
    elif isinstance(value, bytes):
        text = HexBytes(value).hex()
    else:
        text = str(value)
    if text.startswith("0x"):
        return text
    return f"0x{text}"
