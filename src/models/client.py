from datetime import datetime
from enum import Enum

from ..exceptions import ClientLockedError, InvalidOperationError
from ..logging import security_logger

# ======================================
# Day 3: Bank System
# ======================================

# Client Status
class ClientStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


# Client class
class Client:
    """Client class representing a bank client with personal information and accounts."""

    # Security constants
    MAX_FAILED_ATTEMPTS = 3

    def __init__(
        self, client_id, full_name, contact_details, age, status=ClientStatus.ACTIVE
    ):
        self._client_id = client_id.strip()
        self._full_name = full_name.strip()
        self._status = status
        self._contact_details = contact_details
        self._age = self._validate_age(age)
        self._account_numbers = []

        # Security features
        self._failed_login_attempts = 0
        self._last_failed_attempt_time = None
        self._is_locked = False
        self._is_suspicious = False
        self._suspicious_activity = None

    # Encapsulation of attributes with property decorators
    @property
    def client_id(self):
        return self._client_id

    @property
    def full_name(self):
        return self._full_name

    @property
    def status(self):
        return self._status

    @property
    def contact_details(self):
        return self._contact_details

    @property
    def age(self):
        return self._age

    @property
    def account_numbers(self):
        return self._account_numbers.copy()

    # Security properties
    @property
    def is_locked(self):
        """Check if client is locked."""
        return self._is_locked

    @property
    def is_suspicious(self):
        """Check if client is suspicious."""
        return self._is_suspicious

    @property
    def failed_login_attempts(self):
        """Get number of failed login attempts."""
        return self._failed_login_attempts

    @property
    def suspicious_activity(self):
        return self._suspicious_activity

    @staticmethod
    def _validate_age(age):
        """Validate that the client is at least 18 years old."""
        try:
            age_value = int(age)
        except (ValueError, TypeError):
            raise InvalidOperationError("Age must be a valid integer.")

        if age_value < 18:
            raise InvalidOperationError("Client must be at least 18 years old.")

        return age_value

    def add_account(self, account):
        """Add an account to the client's account list."""
        if not hasattr(account, "account_number"):
            raise InvalidOperationError("Invalid account object.")

        self._account_numbers.append(account.account_number)
        return self._account_numbers

    def remove_account(self, account_number):
        """Remove an account from the client's account list."""
        if account_number not in self._account_numbers:
            raise InvalidOperationError("Account number not found.")

        self._account_numbers.remove(account_number)
        return self._account_numbers

    def get_account_info(self):
        """Get comprehensive information about the client and their accounts."""
        return {
            "full_name": self._full_name,
            "client_id": self._client_id,
            "status": self._status,
            "contact_details": self._contact_details,
            "age": self._age,
            "account_numbers": self._account_numbers.copy(),
        }

    def __str__(self):
        return (
            f"ID: {self._client_id}, Client: {self._full_name}, "
            f"Contact details: {self._contact_details}, Age: {self._age}, "
            f"Status: {self._status.value}, "
            f"Accounts: {', '.join(self._account_numbers) if self._account_numbers else 'None'}"
        )

    # Security methods
    def _lock(self):
        """Lock a client."""

        if self._is_locked:
            raise ClientLockedError("Client is already locked.")
        self._is_locked = True

    def _unlock(self):
        """Unlock a client."""

        if not self._is_locked:
            raise ClientLockedError("Client is already unlocked.")

        self._is_locked = False
        security_logger.info(
            f"CLIENT UNLOCKED: Client {self._client_id} - {self._full_name} unlocked"
        )
        self.reset_failed_attempts()

    def flag_suspicious_activity(self, reason: str):
        """Mark client as suspicious."""

        self._is_suspicious = True
        self._suspicious_activity = reason

        security_logger.warning(
            f"Suspicious activity flagged for client "
            f"{self._client_id} - {self._full_name}: {reason}"
        )

    def record_failed_login(self):
        """Record a failed login attempt and lock account if threshold reached."""
        self._failed_login_attempts += 1
        self._last_failed_attempt_time = datetime.now()

        security_logger.warning(
            f"Failed login attempt #{self._failed_login_attempts} "
            f"by client {self._client_id} - {self._full_name}"
        )

        if self._failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
            self._lock()
            self.flag_suspicious_activity(
                f"Client locked after {self.MAX_FAILED_ATTEMPTS} failed login attempts."
                f"Last attempt was at {self._last_failed_attempt_time}. "
            )

    def reset_failed_attempts(self):
        """Reset failed login attempts counter on successful login."""
        if self._failed_login_attempts > 0:
            security_logger.info(
                f"Failed login attempts reset for client {self._client_id} "
                f"after successful authentication by {self._full_name}"
            )
        self._failed_login_attempts = 0
        self._last_failed_attempt_time = None
        self._is_suspicious = False
        self._suspicious_activity = None

    def check_locked(self):
        """Check if client is locked due to failed login attempts."""
        if self._is_locked:
            security_logger.warning(
                f"SUSPICIOUS ACTIVITY: Client {self._client_id} - {self._full_name} "
                f"is locked due to {self.MAX_FAILED_ATTEMPTS} failed login attempts."
            )
            raise ClientLockedError(
                f"Client {self._full_name} is locked "
                f"after {self.MAX_FAILED_ATTEMPTS} failed login attempts. "
                f"Please contact bank support to unlock."
            )
