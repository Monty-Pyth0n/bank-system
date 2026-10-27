from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation
from enum import Enum
from uuid import uuid4



# Account status
class AccountStatus(Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


# Exceptions
class AccountFrozenError(Exception):
    """Raised when an operation is attempted on a frozen account."""
    pass


class AccountClosedError(Exception):
    """Raised when an operation is attempted on a closed account."""
    pass


class InvalidOperationError(Exception):
    """Raised when an invalid operation or argument is provided."""
    pass


class InsufficientFundsError(Exception):
    """Raised when the account has insufficient funds."""
    pass


# Abstract account
class AbstractAccount(ABC):

    def __init__(self, owner, balance=0, account_number=None):
        if not isinstance(owner, str) or not owner.strip():
            raise InvalidOperationError("Owner name cannot be empty.")

        self._owner = owner.strip()
        self._balance = self._validate_amount(balance)
        self._account_number = (
            str(account_number).strip()
            if account_number is not None
            else uuid4().hex[:8].upper()
        )

        if not self._account_number:
            raise InvalidOperationError("Account number cannot be empty.")

        self._status = AccountStatus.ACTIVE

    @staticmethod
    def _validate_amount(amount):
        """Convert an amount to Decimal and validate it."""
        if isinstance(amount, bool):
            raise InvalidOperationError("Amount must be a number.")

        try:
            value = Decimal(str(amount))
        except (InvalidOperation, ValueError, TypeError):
            raise InvalidOperationError("Amount must be a valid number.")

        if not value.is_finite():
            raise InvalidOperationError("Amount must be finite.")

        if value < 0:
            raise InvalidOperationError("Amount cannot be negative.")

        return value

    @abstractmethod
    def deposit(self, amount):
        pass

    @abstractmethod
    def withdraw(self, amount):
        pass

    @abstractmethod
    def get_account_info(self):
        pass


# Bank account
class BankAccount(AbstractAccount):

    ALLOWED_CURRENCIES = {"RUB", "USD", "EUR", "KZT", "CNY"}

    def __init__(
        self,
        owner,
        balance=0,
        account_number=None,
        currency="RUB",
        status=AccountStatus.ACTIVE
    ):
        super().__init__(owner, balance, account_number)

        if not isinstance(currency, str):
            raise InvalidOperationError("Currency must be a string.")

        currency = currency.upper()

        if currency not in self.ALLOWED_CURRENCIES:
            raise InvalidOperationError(
                f"Unsupported currency: {currency}. "
                f"Allowed currencies: {', '.join(sorted(self.ALLOWED_CURRENCIES))}"
            )

        if not isinstance(status, AccountStatus):
            raise InvalidOperationError("Invalid account status.")

        self.currency = currency
        self._status = status


    @property
    def owner(self):
        return self._owner

    @property
    def account_number(self):
        return self._account_number

    @property
    def balance(self):
        return self._balance

    @property
    def status(self):
        return self._status

    def _check_status(self):
        """Ensure that the account can perform operations."""
        if self._status == AccountStatus.FROZEN:
            raise AccountFrozenError("The account is frozen.")

        if self._status == AccountStatus.CLOSED:
            raise AccountClosedError("The account is closed.")

    def deposit(self, amount):
        self._check_status()
        amount = self._validate_amount(amount)

        if amount == 0:
            raise InvalidOperationError("Deposit amount must be greater than zero.")

        self._balance += amount
        return self._balance

    def withdraw(self, amount):
        self._check_status()
        amount = self._validate_amount(amount)

        if amount == 0:
            raise InvalidOperationError("Withdrawal amount must be greater than zero.")

        if amount > self._balance:
            raise InsufficientFundsError(
                "Insufficient funds to complete the withdrawal."
            )

        self._balance -= amount
        return self._balance

    def freeze(self):
        if self._status == AccountStatus.CLOSED:
            raise AccountClosedError("A closed account cannot be frozen.")

        self._status = AccountStatus.FROZEN

    def activate(self):
        if self._status == AccountStatus.CLOSED:
            raise AccountClosedError("A closed account cannot be activated.")

        self._status = AccountStatus.ACTIVE

    def close(self):
        if self._status == AccountStatus.CLOSED:
            raise AccountClosedError("The account is already closed.")

        self._status = AccountStatus.CLOSED

    def get_account_info(self):
        return {
            "account_type": type(self).__name__,
            "account_number": self._account_number,
            "owner": self._owner,
            "balance": self._balance,
            "currency": self.currency,
            "status": self._status.value,
        }

    def __str__(self):
        last_four = self._account_number[-4:]

        return (
            f"Account type: {type(self).__name__} | "
            f"Customer: {self._owner} | "
            f"Account: ****{last_four} | "
            f"Status: {self._status.value} | "
            f"Balance: {self._balance:.2f} {self.currency}"
        )
    