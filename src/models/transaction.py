from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from heapq import heapify, heappop, heappush
from typing import Any, ClassVar
from uuid import uuid4

from ..exceptions import (
    AccountFrozenError,
    InsufficientFundsError,
    InvalidOperationError,
    TransactionFailedError,
)
from ..logging import transaction_logger
from ..utils import validate_amount, validate_currency
from .accounts import AccountStatus, BankAccount, PremiumAccount

# ======================================
# Day 4: Transaction System
# ======================================

# Transaction Types
class TransactionType(Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    PAYMENT = "payment"
    REFUND = "refund"
    FEE = "fee"
    INTEREST = "interest"


# Transaction Status
class TransactionStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REVERSED = "reversed"


# Transaction Model
class Transaction:
    """
    Transaction model representing a financial transaction in the banking system.

    Attributes:
        id: Unique transaction identifier (UUID)
        type: Type of transaction (deposit, withdrawal, transfer, etc.)
        amount: Transaction amount
        currency: Currency code (e.g., RUB, USD, EUR)
        fee: Transaction fee
        sender: Sender account number (for transfers/withdrawals)
        recipient: Recipient account number (for transfers/deposits)
        status: Current transaction status
        failure_reason: Reason for failure if status is FAILED
        created_at: Timestamp when transaction was created
        updated_at: Timestamp when transaction was last updated
        completed_at: Timestamp when transaction was completed
    """

    def __init__(
        self,
        type: TransactionType,
        amount: Decimal | int,
        currency: str,
        sender: str | None = None,
        recipient: str | None = None,
        fee: Decimal = Decimal("0.00"),
        transaction_id: str | None = None,
    ):
        # Validate and set ID
        self._id = transaction_id or str(uuid4())

        # Validate and set type
        if not isinstance(type, TransactionType):
            raise InvalidOperationError("Transaction type must be a TransactionType enum.")
        self._type = type
        self._amount = validate_amount(amount)
        self._currency = validate_currency(currency)
        self._fee = validate_amount(fee)
        self._sender = sender.strip() if sender else None
        self._recipient = recipient.strip() if recipient else None

        # Validate sender/recipient based on transaction type
        self._validate_parties()

        self._status = TransactionStatus.PENDING
        self._failure_reason: str | None = None

        # Set timestamps
        self._created_at = datetime.now()
        self._updated_at = self._created_at
        self._completed_at: datetime | None = None
            
    # Properties
    @property
    def id(self) -> str:
        return self._id

    @property
    def type(self) -> TransactionType:
        return self._type

    @property
    def amount(self) -> Decimal:
        return self._amount

    @property
    def currency(self) -> str:
        return self._currency

    @property
    def fee(self) -> Decimal:
        return self._fee

    @property
    def sender(self) -> str | None:
        return self._sender

    @property
    def recipient(self) -> str | None:
        return self._recipient

    @property
    def status(self) -> TransactionStatus:
        return self._status

    @property
    def failure_reason(self) -> str | None:
        return self._failure_reason

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def completed_at(self) -> datetime | None:
        return self._completed_at

    # Validation sender/recipient
    def _validate_parties(self) -> None:
        """Validate sender and recipient based on transaction type."""
        if self._type in (TransactionType.TRANSFER, TransactionType.PAYMENT):
            if not self._sender:
                raise InvalidOperationError(
                    f"Sender is required for {self._type.value} transactions."
                )
            if not self._recipient:
                raise InvalidOperationError(
                    f"Recipient is required for {self._type.value} transactions."
                )
            if self._sender == self._recipient:
                raise InvalidOperationError("Sender and recipient cannot be the same.")
        elif self._type == TransactionType.WITHDRAWAL and not self._sender:
            raise InvalidOperationError(
                "Sender is required for withdrawal transactions."
            )
        elif self._type == TransactionType.DEPOSIT and not self._recipient:
            raise InvalidOperationError(
                "Recipient is required for deposit transactions."
            )

    # Status Management
    def _set_status(self, status: TransactionStatus, failure_reason: str | None = None) -> None:
        """Internal method to set status - used by TransactionProcessor."""
        self._status = status
        self._updated_at = datetime.now()
        if failure_reason:
            self._failure_reason = failure_reason
        if status == TransactionStatus.COMPLETED:
            self._completed_at = self._updated_at
            self._failure_reason = None

    # Utility Methods
    def is_finalized(self) -> bool:
        """Check if transaction is in a final state."""
        return self._status in (
            TransactionStatus.COMPLETED,
            TransactionStatus.FAILED,
            TransactionStatus.CANCELLED,
            TransactionStatus.REVERSED,
        )

    def is_successful(self) -> bool:
        """Check if transaction was successful."""
        return self._status == TransactionStatus.COMPLETED

    def to_dict(self) -> dict:
        """Convert transaction to dictionary representation."""
        return {
            "id": self._id,
            "type": self._type.value,
            "amount": str(self._amount),
            "currency": self._currency,
            "fee": str(self._fee),
            "sender": self._sender,
            "recipient": self._recipient,
            "status": self._status.value,
            "failure_reason": self._failure_reason,
            "created_at": self._created_at.isoformat() + "Z",
            "updated_at": self._updated_at.isoformat() + "Z",
            "completed_at": self._completed_at.isoformat() + "Z" if self._completed_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"Transaction(id={self._id[:8]}..., type={self._type.value}, "
            f"amount={self._amount} {self._currency}, status={self._status.value})"
        )

    def __str__(self) -> str:
        return (
            f"Transaction {self._id[:8]}: {self._type.value} "
            f"{self._amount} {self._currency} ({self._status.value})"
        )


# Transaction Priority
class TransactionPriority(Enum):
    """Priority levels for transaction processing."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


# Transaction Queue
class TransactionQueue:
    """
    Queue for managing transaction processing with priority support.

    Features:
    - Add transactions with priority
    - Schedule deferred operations
    - Cancel transactions
    - Priority-based processing order
    """

    def __init__(self):
        self._queue: list[
            tuple[int, int, Transaction]
        ] = []  # (priority, sequence, transaction)
        self._sequence = 0  # For FIFO ordering within same priority
        self._cancelled_ids: set[str] = set()
        # transaction_id -> (scheduled_time, transaction, priority)
        self._scheduled: dict[
            str, tuple[datetime, Transaction, TransactionPriority]
        ] = {}

    def add(
        self,
        transaction: Transaction,
        priority: TransactionPriority = TransactionPriority.NORMAL,
    ) -> None:
        """
        Add a transaction to the queue with specified priority.

        Args:
            transaction: Transaction to add
            priority: Processing priority (default: NORMAL)
        """
        if transaction.id in self._cancelled_ids:
            self._cancelled_ids.discard(transaction.id)

        # Negative priority for max-heap behavior (higher priority = processed first)
        heappush(self._queue, (-priority.value, self._sequence, transaction))
        self._sequence += 1

    def add_scheduled(
        self,
        transaction: Transaction,
        scheduled_at: datetime,
        priority: TransactionPriority = TransactionPriority.NORMAL,
    ) -> None:
        """
        Schedule a transaction for future processing.

        Args:
            transaction: Transaction to schedule
            scheduled_at: When to process the transaction
            priority: Processing priority (default: NORMAL)
        """
        if scheduled_at <= datetime.now():
            # If scheduled time has passed, add to queue immediately
            self.add(transaction, priority)
        else:
            # Store scheduled transaction with its priority
            self._scheduled[transaction.id] = (scheduled_at, transaction, priority)

    def get_next(self) -> Transaction | None:
        """
        Get the next transaction to process (highest priority, earliest added).

        Returns:
            Next transaction or None if queue is empty
        """
        # Check for scheduled transactions that are now due
        self._process_scheduled()

        while self._queue:
            _, _, transaction = heappop(self._queue)
            if transaction.id not in self._cancelled_ids:
                return transaction
        return None

    def _process_scheduled(self) -> None:
        """Move scheduled transactions that are due to the active queue."""
        now = datetime.now()
        due_ids = [
            tid
            for tid, (scheduled_time, _, _) in self._scheduled.items()
            if scheduled_time <= now
        ]
        for tid in due_ids:
            _, transaction, priority = self._scheduled.pop(tid)
            self.add(transaction, priority)

    def cancel(self, transaction_id: str) -> bool:
        """
        Cancel a transaction in the queue.

        Args:
            transaction_id: ID of transaction to cancel

        Returns:
            True if transaction was found and cancelled, False otherwise
        """
        # Mark as cancelled (will be skipped when popped)
        self._cancelled_ids.add(transaction_id)

        # Also remove from scheduled if present
        if transaction_id in self._scheduled:
            del self._scheduled[transaction_id]
            return True

        # Check if in queue (we can't easily remove from heap, so just mark)
        for _, _, txn in self._queue:
            if txn.id == transaction_id:
                return True
        return False

    def set_priority(self, transaction_id: str, priority: TransactionPriority) -> bool:
        """
        Change priority of a transaction in the queue.

        Note: since a heap doesn't support efficient in-place update, the old
        entry is removed and re-inserted with the new priority (O(n) rebuild).

        Args:
            transaction_id: ID of transaction to update
            priority: New priority level

        Returns:
            True if transaction was found and priority updated, False otherwise
        """

        for i, (_, _, txn) in enumerate(self._queue):
            if txn.id == transaction_id:
                # Drop the stale entry, then restore heap invariant.
                del self._queue[i]
                heapify(self._queue)

                # Re-insert with the new priority
                heappush(self._queue, (-priority.value, self._sequence, txn))
                self._sequence += 1

                return True
        return False

    def get_priority(self, transaction_id: str) -> TransactionPriority | None:
        """Return current queue priority for a transaction, or None if not found."""
        for priority, _, txn in self._queue:
            if txn.id == transaction_id:
                return TransactionPriority(-priority)
        return None

    def peek(self) -> Transaction | None:
        """View the next transaction without removing it."""
        self._process_scheduled()
        for _, _, txn in self._queue:
            if txn.id not in self._cancelled_ids:
                return txn
        return None

    def size(self) -> int:
        """Return number of pending transactions in queue."""
        self._process_scheduled()
        return sum(1 for _, _, txn in self._queue if txn.id not in self._cancelled_ids)

    def is_empty(self) -> bool:
        """Check if queue has no pending transactions.

        Scheduled transactions whose due time has arrived are moved to the
        active queue first, so they are not mistakenly reported as empty
        and left unprocessed by :meth:`TransactionProcessor.process_queue`.
        """
        self._process_scheduled()
        return self.size() == 0

    def get_scheduled_count(self) -> int:
        """Return number of scheduled (future) transactions."""
        return len(self._scheduled)

    def clear_cancelled(self) -> int:
        """Remove cancelled transactions from queue and return count removed."""
        original_size = len(self._queue)
        self._queue = [
            (p, s, txn)
            for p, s, txn in self._queue
            if txn.id not in self._cancelled_ids
        ]
        removed = original_size - len(self._queue)
        self._cancelled_ids.clear()
        return removed


# Transaction Processor
class TransactionProcessor:
    """
    Processor for executing transactions with fee calculation,
    currency conversion, retry logic, and error logging.

    Features:
    - Calculate fees based on transaction type and amount
    - Convert currencies using configurable exchange rates
    - Process transactions with full lifecycle management
    - Retry failed transactions with configurable max attempts
    - Log errors to both in-memory log and system logger
    - Process all pending transactions in a queue
    """

    # Exchange rates relative to USD (base currency)
    _EXCHANGE_RATES: ClassVar[dict[str, Decimal]] = {
        "USD": Decimal("1.0000"),
        "EUR": Decimal("0.9200"),
        "RUB": Decimal("90.5000"),
        "KZT": Decimal("500.0000"),
        "CNY": Decimal("7.2000"),
    }

    # Fee rates by transaction type (as a fraction of amount)
    _FEE_RATES: ClassVar[dict[TransactionType, Decimal]] = {
        TransactionType.TRANSFER: Decimal("0.01"),
        TransactionType.PAYMENT: Decimal("0.005"),
        TransactionType.WITHDRAWAL: Decimal("0.002"),
        TransactionType.DEPOSIT: Decimal("0.00"),
        TransactionType.REFUND: Decimal("0.00"),
        TransactionType.FEE: Decimal("0.00"),
        TransactionType.INTEREST: Decimal("0.00"),
    }

    # Flat fee for transfers to recipients outside the bank (external transfers)
    _EXTERNAL_TRANSFER_FEE: ClassVar[Decimal] = Decimal("25.00")

    def __init__(
        self,
        queue: TransactionQueue | None = None,
        max_retries: int = 3,
        accounts: dict[str, BankAccount] | None = None,
        risk_analyzer: Any = None,
    ):
        self._queue = queue or TransactionQueue()
        # Account registry (account_number -> account) used to enforce
        # bank business rules during processing.
        self._accounts = accounts or {}
        # Optional risk analyzer.
        self._risk_analyzer = risk_analyzer
        self._retry_counts: dict[str, int] = {}
        self._max_retries = max_retries
        self._error_log: list[dict] = []
        self._logger = transaction_logger

    @property
    def queue(self) -> TransactionQueue:
        return self._queue

    @property
    def accounts(self) -> dict[str, BankAccount]:
        """Return the account registry used for business rule validation."""
        return self._accounts

    @property
    def risk_analyzer(self) -> Any:
        """Return the optional risk analyzer used to block high-risk transactions."""
        return self._risk_analyzer

    @property
    def max_retries(self) -> int:
        return self._max_retries

    @max_retries.setter
    def max_retries(self, value: int) -> None:
        if value < 0:
            raise InvalidOperationError("Max retries cannot be negative.")
        self._max_retries = value

    @property
    def error_log(self) -> list[dict]:
        return list(self._error_log)

    # Fee calculation
    def calculate_fee(self, transaction: Transaction) -> Decimal:
        """
        Calculate fee for a transaction based on type and amount.

        Args:
            transaction: Transaction to calculate fee for

        Returns:
            Calculated fee amount quantized to 2 decimal places
        """
        rate = self._FEE_RATES.get(transaction.type, Decimal("0.01"))
        fee = (transaction.amount * rate).quantize(Decimal("0.01"))
        return fee

    def apply_fee(self, transaction: Transaction) -> Decimal:
        """
        Calculate and apply fee to a transaction.

        External transfers (the recipient is not a known account of the
        bank) are charged an additional flat external transfer fee.

        Args:
            transaction: Transaction to apply fee to

        Returns:
            The fee amount that was applied
        """
        fee = self.calculate_fee(transaction)

        # Rule: charge a fee for external transfers
        if (
            transaction.type == TransactionType.TRANSFER
            and transaction.recipient
            and transaction.recipient not in self._accounts
        ):
            fee = fee + self._EXTERNAL_TRANSFER_FEE

        transaction._fee = fee
        return fee

    # Currency conversion
    def convert_currency(
        self, amount: Decimal, from_currency: str, to_currency: str
    ) -> Decimal:
        """
        Convert amount between currencies using exchange rates.

        Conversion is performed via USD as the base currency:
            amount -> USD -> target_currency

        Args:
            amount: Amount to convert
            from_currency: Source currency code (e.g., "RUB")
            to_currency: Target currency code (e.g., "USD")

        Returns:
            Converted amount quantized to 2 decimal places

        Raises:
            InvalidOperationError: If either currency is unsupported
        """
        from_currency = from_currency.upper().strip()
        to_currency = to_currency.upper().strip()

        if from_currency == to_currency:
            return amount

        if from_currency not in self._EXCHANGE_RATES:
            raise InvalidOperationError(
                f"Unsupported source currency: {from_currency}"
            )
        if to_currency not in self._EXCHANGE_RATES:
            raise InvalidOperationError(
                f"Unsupported target currency: {to_currency}"
            )

        usd_amount = amount / self._EXCHANGE_RATES[from_currency]
        converted = usd_amount * self._EXCHANGE_RATES[to_currency]
        return converted.quantize(Decimal("0.01"))

    def set_exchange_rate(self, currency: str, rate: Decimal) -> None:
        """
        Set or update exchange rate for a currency relative to USD.

        Args:
            currency: Currency code (e.g., "EUR")
            rate: Exchange rate relative to USD (must be positive)

        Raises:
            InvalidOperationError: If rate is not positive
        """
        currency = currency.upper().strip()
        if rate <= 0:
            raise InvalidOperationError("Exchange rate must be positive.")
        self._EXCHANGE_RATES[currency] = rate

    def get_exchange_rate(self, currency: str) -> Decimal | None:
        """
        Get the exchange rate for a currency relative to USD.

        Args:
            currency: Currency code

        Returns:
            Exchange rate or None if currency is not registered
        """
        return self._EXCHANGE_RATES.get(currency.upper().strip())

    # Business rules validation
    def _validate_business_rules(self, transaction: Transaction) -> None:
        """
        Validate bank business rules before a transaction is processed.

        Rules enforced:
            1. Transactions on frozen accounts are prohibited.
            2. Transfers (TRANSFER/PAYMENT) from an account with a
               negative balance are prohibited, unless the sender is a
               premium account (overdraft facility).
            3. External transfers (recipient is not a known account of
               the bank) incur an additional flat fee (applied in
               ``apply_fee``).

        Args:
            transaction: Transaction to validate.

        Raises:
            AccountFrozenError: If the sender or recipient account is frozen.
            InvalidOperationError: If a transfer from a negative-balance,
                non-premium account is attempted.
        """
        sender = (
            self._accounts.get(transaction.sender)
            if transaction.sender
            else None
        )
        recipient = (
            self._accounts.get(transaction.recipient)
            if transaction.recipient
            else None
        )

        # Rule: no transactions on frozen accounts.
        for account, role in ((sender, "sender"), (recipient, "recipient")):
            if account is not None and account.status == AccountStatus.FROZEN:
                raise AccountFrozenError(
                    f"Transaction prohibited: {role} account "
                    f"{account.account_number} is frozen."
                )

        # Rule: transfers from a negative balance are prohibited unless
        # the sender is a premium account (overdraft facility).
        if transaction.type in (
            TransactionType.TRANSFER,
            TransactionType.PAYMENT,
        ) and (
            sender is not None
            and sender.balance < 0
            and not isinstance(sender, PremiumAccount)
        ):
            raise InvalidOperationError(
                f"Transfer prohibited: sender account "
                f"{sender.account_number} has a negative balance "
                f"({sender.balance})."
            )

    # Transaction processing
    def process(self, transaction: Transaction) -> bool:
        """
        Process a single transaction through its lifecycle.

        Steps:
        1. Reject if transaction is already in a final state
        2. Validate bank business rules (frozen accounts, negative-balance
           transfers, etc.)
        3. Set status to PROCESSING
        4. Calculate and apply fee
        5. Debit/credit the involved accounts (sufficient funds are checked
           and currency conversion is applied when account and transaction
           currencies differ)
        6. Mark as COMPLETED on success or FAILED on error

        Args:
            transaction: Transaction to process

        Returns:
            True if transaction completed successfully, False otherwise
        """
        if transaction.is_finalized():
            self.log_error(
                transaction,
                InvalidOperationError(
                    f"Transaction {transaction.id} is already "
                    f"{transaction.status.value}"
                ),
            )
            return False

        try:
            self._validate_business_rules(transaction)

            # High-risk transactions are marked FAILED with a reason
            if self._risk_analyzer is not None:
                level = self._risk_analyzer.analyze_transaction(transaction)

                from ..services.risk_analyzer import RiskLevel
                if level == RiskLevel.HIGH:
                    self.log_error(
                        transaction,
                        InvalidOperationError(
                            f"Transaction {transaction.id} blocked: high risk"
                        ),
                    )
                    return False

            transaction._set_status(TransactionStatus.PROCESSING)

            fee = self.apply_fee(transaction)

            self._execute_transaction(transaction, fee)

            transaction._set_status(TransactionStatus.COMPLETED)
            return True

        except (
            InvalidOperationError,
            TransactionFailedError,
            AccountFrozenError,
            InsufficientFundsError,
        ) as e:
            transaction._set_status(TransactionStatus.FAILED, failure_reason=str(e))
            self.log_error(transaction, e)
            return False

    def _execute_transaction(self, transaction: Transaction, fee: Decimal) -> None:
        """
        Move funds between the accounts involved in a transaction.

        The sender is debited the amount plus the transaction fee (for
        withdrawals, transfers and payments); the recipient is credited the
        amount (for deposits, transfers, payments and refunds). Amounts are
        converted to the account currency when it differs from the
        transaction currency. Sufficient funds are verified before any
        balance is changed, so a failure leaves all balances untouched.

        Args:
            transaction: Transaction being executed
            fee: Transaction fee already applied to the transaction

        Raises:
            InvalidOperationError: If a required account is not registered
                with the processor
            InsufficientFundsError: If the sender cannot cover the debit
        """
        sender = (
            self._accounts.get(transaction.sender)
            if transaction.sender
            else None
        )
        recipient = (
            self._accounts.get(transaction.recipient)
            if transaction.recipient
            else None
        )

        debit_amount = Decimal("0.00")
        credit_amount = Decimal("0.00")
        do_debit = False
        do_credit = False
        credit_target = None

        # Determine the sender debit
        if transaction.type in (
            TransactionType.WITHDRAWAL,
            TransactionType.TRANSFER,
            TransactionType.PAYMENT,
        ):
            if sender is None:
                raise InvalidOperationError(
                    f"Sender account {transaction.sender!r} is not registered "
                    "with the transaction processor."
                )
            debit_amount = transaction.amount + fee
            if sender.currency != transaction.currency:
                debit_amount = self.convert_currency(
                    debit_amount, transaction.currency, sender.currency
                )
            do_debit = True

        # Determine the recipient credit
        if transaction.type in (
            TransactionType.DEPOSIT,
            TransactionType.TRANSFER,
            TransactionType.PAYMENT,
            TransactionType.REFUND,
        ):
            credit_target = recipient
            if (
                transaction.type == TransactionType.REFUND
                and credit_target is None
                and sender is not None
            ):
                # A refund without a recipient goes back to the sender.
                credit_target = sender
            if credit_target is None:
                if transaction.type == TransactionType.DEPOSIT:
                    raise InvalidOperationError(
                        f"Recipient account {transaction.recipient!r} is not "
                        "registered with the transaction processor."
                    )
                # External recipient (e.g. external transfer): nothing to credit.
            else:
                credit_amount = transaction.amount
                if credit_target.currency != transaction.currency:
                    credit_amount = self.convert_currency(
                        transaction.amount,
                        transaction.currency,
                        credit_target.currency,
                    )
                do_credit = True

        # Validate sufficient funds before mutating any balance
        if sender is not None and do_debit:
            available = sender.balance
            if isinstance(sender, PremiumAccount):
                available += sender.overdraft_limit
            if available < debit_amount:
                raise InsufficientFundsError(
                    f"Insufficient funds on sender account "
                    f"{sender.account_number}: available {available} "
                    f"{sender.currency}, required {debit_amount} "
                    f"{sender.currency}."
                )

        # Apply the movement 
        if sender is not None and do_debit:
            sender._balance -= debit_amount
        if credit_target is not None and do_credit:
            credit_target._balance += credit_amount

    def process_queue(self) -> dict[str, int]:
        """
        Process all pending transactions in the queue.

        Transactions are dequeued in priority order and processed one by one.
        Already finalized transactions are skipped.

        Returns:
            Dictionary with counts: {"completed": n, "failed": n, "skipped": n}
        """
        stats = {"completed": 0, "failed": 0, "skipped": 0}

        while not self._queue.is_empty():
            transaction = self._queue.get_next()
            if transaction is None:
                break

            if transaction.is_finalized():
                stats["skipped"] += 1
                continue

            if self.process(transaction):
                stats["completed"] += 1
            else:
                stats["failed"] += 1

        return stats

    # Retry logic
    def retry_failed(self, transaction: Transaction) -> bool:
        """
        Retry a failed transaction.

        The transaction is reset to PENDING status, its failure reason is
        cleared, and it is re-added to the queue with HIGH priority.

        Args:
            transaction: Failed transaction to retry

        Returns:
            True if the retry was queued, False if max retries exceeded
            or the transaction is not in FAILED state
        """
        if transaction.status != TransactionStatus.FAILED:
            self.log_error(
                transaction,
                InvalidOperationError(
                    f"Only failed transactions can be retried, "
                    f"current status: {transaction.status.value}"
                ),
            )
            return False

        count = self._retry_counts.get(transaction.id, 0)
        if count >= self._max_retries:
            self.log_error(
                transaction,
                InvalidOperationError(
                    f"Max retries ({self._max_retries}) exceeded for "
                    f"transaction {transaction.id}"
                ),
            )
            return False

        self._retry_counts[transaction.id] = count + 1
        transaction._set_status(TransactionStatus.PENDING)
        transaction._failure_reason = None
        self._queue.add(transaction, TransactionPriority.HIGH)
        return True

    def get_retry_count(self, transaction_id: str) -> int:
        """
        Return the number of retry attempts for a transaction.

        Args:
            transaction_id: ID of the transaction

        Returns:
            Number of retries attempted (0 if never retried)
        """
        return self._retry_counts.get(transaction_id, 0)

    def clear_retry_count(self, transaction_id: str) -> None:
        """
        Clear the retry count for a transaction.

        Args:
            transaction_id: ID of the transaction
        """
        self._retry_counts.pop(transaction_id, None)

    # Error logging
    def log_error(self, transaction: Transaction, error: Exception) -> None:
        """
        Log a transaction processing error.

        The error is recorded in the in-memory error log and also emitted
        via the standard logging module under the "bank.transaction" logger.

        Args:
            transaction: Transaction that encountered the error
            error: Exception that was raised
        """
        error_entry = {
            "transaction_id": transaction.id,
            "error": str(error),
            "error_type": type(error).__name__,
            "timestamp": datetime.now(UTC).isoformat(),
            "transaction_status": transaction.status.value,
        }
        self._error_log.append(error_entry)

        self._logger.error(
            "Transaction %s failed: %s (%s)",
            transaction.id,
            error,
            type(error).__name__,
        )
