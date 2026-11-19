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


