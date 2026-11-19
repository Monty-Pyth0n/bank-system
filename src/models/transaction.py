from datetime import datetime
from decimal import Decimal
from enum import Enum
from heapq import heappop, heappush
from uuid import uuid4

from ..exceptions import InvalidOperationError
from ..utils import validate_amount, validate_currency

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
        amount: Decimal,
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

        Note: Since heap doesn't support efficient update, we mark old entry
        as cancelled and add a new one with updated priority.

        Args:
            transaction_id: ID of transaction to update
            priority: New priority level

        Returns:
            True if transaction was found and priority updated, False otherwise
        """
        # Find and cancel the old entry
        for i, (_, _, txn) in enumerate(self._queue):
            if txn.id == transaction_id:
                self._cancelled_ids.add(transaction_id)
                # Re-add with new priority
                heappush(self._queue, (-priority.value, self._sequence, txn))
                self._sequence += 1
                return True
        return False

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
        """Check if queue has no pending transactions."""
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
