# Exceptions
class AccountFrozenError(Exception):
    """Raised when an operation is attempted on a frozen account."""


class AccountClosedError(Exception):
    """Raised when an operation is attempted on a closed account."""


class InvalidOperationError(Exception):
    """Raised when an invalid operation or argument is provided."""


class InsufficientFundsError(Exception):
    """Raised when the account has insufficient funds."""


class ClientLockedError(Exception):
    """Raised when an account is locked due to too many failed login attempts."""


class TransactionProhibitedError(Exception):
    """Raised when a transaction is attempted during prohibited hours (00:00-05:00)."""

class TransactionFailedError(Exception):
    """Raised when a transaction fails during processing."""
