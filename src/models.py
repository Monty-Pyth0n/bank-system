from abc import ABC, abstractmethod  # noqa: I001
from decimal import Decimal, InvalidOperation
from enum import Enum

from src.utils import generate_account_number
from src.utils import build_account_table


# Account status
class AccountStatus(Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


# Exceptions
class AccountFrozenError(Exception):
    """Raised when an operation is attempted on a frozen account."""


class AccountClosedError(Exception):
    """Raised when an operation is attempted on a closed account."""


class InvalidOperationError(Exception):
    """Raised when an invalid operation or argument is provided."""


class InsufficientFundsError(Exception):
    """Raised when the account has insufficient funds."""


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
            else generate_account_number()
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

    ALLOWED_CURRENCIES = {"RUB", "USD", "EUR", "KZT", "CNY"}  # noqa: RUF012
    DEFAULT_WITHDRAWAL_LIMIT = Decimal("100000.00")  # Default daily withdrawal limit

    def __init__(
        self,
        owner,
        balance=0,
        account_number=None,
        currency="RUB",
        status=AccountStatus.ACTIVE,
        withdrawal_limit=None
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
        self.withdrawal_limit = self._validate_amount(withdrawal_limit) if withdrawal_limit is not None else self.DEFAULT_WITHDRAWAL_LIMIT


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

        if amount > self.withdrawal_limit:
            raise InsufficientFundsError(
                f"Withdrawal amount exceeds daily limit of {self.withdrawal_limit}"
            )

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
            "withdrawal_limit": self.withdrawal_limit,
        }

    def __str__(self):
        last_four = self._account_number[-4:]

        rows = [
            ("Account type", type(self).__name__),
            ("Customer", self._owner),
            ("Account", f"****{last_four}"),
            ("Status", self._status.value),
            ("Withdrawal limit", f"{self.withdrawal_limit:.2f} {self.currency}"),
            ("Balance", f"{self._balance:.2f} {self.currency}"),
        ]
        
        return build_account_table(rows)


# Savings account
class SavingsAccount(BankAccount):
    """Savings account with minimum balance and monthly interest."""

    def __init__(
        self,
        owner,
        balance=0,
        account_number=None,
        currency="RUB",
        status=AccountStatus.ACTIVE,
        min_balance=0,
        interest_rate=0.01,
        withdrawal_limit=None,
    ):
        super().__init__(owner, balance, account_number, currency, status, withdrawal_limit)
        self.min_balance = self._validate_amount(min_balance)
        self.interest_rate = interest_rate

    def withdraw(self, amount):
        self._check_status()
        amount = self._validate_amount(amount)

        if amount == 0:
            raise InvalidOperationError("Withdrawal amount must be greater than zero.")

        if amount > self.withdrawal_limit:
                    raise InsufficientFundsError(
                        f"Withdrawal amount exceeds daily limit of {self.withdrawal_limit}"
                    )

        if self._balance - amount < self.min_balance:
            raise InsufficientFundsError(
                f"Cannot withdraw below minimum balance of {self.min_balance}. "
                f"Available: {self._balance - self.min_balance}"
            )

        self._balance -= amount
        return self._balance

    def apply_monthly_interest(self):
        """Apply monthly interest to the account balance."""
        self._check_status()
        interest = self._balance * Decimal(str(self.interest_rate))
        self._balance += interest
        return self._balance

    def get_account_info(self):
        info = super().get_account_info()
        info.update(
            {
                "account_type": type(self).__name__,
                "min_balance": self.min_balance,
                "interest_rate": self.interest_rate,
            }
        )
        return info

    def __str__(self):
        last_four = self._account_number[-4:]

        rows = [
            ("Account type", type(self).__name__),
            ("Customer", self._owner),
            ("Account", f"****{last_four}"),
            ("Status", self._status.value),
            ("Min balance", f"{self.min_balance:.2f} {self.currency}"),
            ("Withdrawal limit", f"{self.withdrawal_limit:.2f} {self.currency}"),
            ("Interest rate", f"{self.interest_rate * 100:.2f}%"),
            ("Balance", f"{self._balance:.2f} {self.currency}"),
        ]

        return build_account_table(rows)


# Premium account
class PremiumAccount(BankAccount):
    """Premium account with higher limits, overdraft facility, and fixed fee."""

    DEFAULT_WITHDRAWAL_LIMIT = Decimal("500000.00")  # Higher daily withdrawal limit for premium

    def __init__(
        self,
        owner,
        balance=0,
        account_number=None,
        currency="RUB",
        status=AccountStatus.ACTIVE,
        overdraft_limit=50000,
        fixed_fee=100,
        withdrawal_limit=None
    ):
        super().__init__(owner, balance, account_number, currency, status, withdrawal_limit)
        self.overdraft_limit = self._validate_amount(overdraft_limit)
        self.fixed_fee = self._validate_amount(fixed_fee)

    def withdraw(self, amount):
        self._check_status()
        amount = self._validate_amount(amount)

        if amount == 0:
            raise InvalidOperationError("Withdrawal amount must be greater than zero.")

        if amount > self.withdrawal_limit:
            raise InsufficientFundsError(
                f"Withdrawal amount exceeds daily limit of {self.withdrawal_limit}"
            )

        total_with_fee = amount + self.fixed_fee
        available = self._balance + self.overdraft_limit

        if total_with_fee > available:
            raise InsufficientFundsError(
                f"Insufficient funds. Available with overdraft: {available}"
            )

        self._balance -= total_with_fee
        return self._balance

    def get_account_info(self):
        info = super().get_account_info()
        info.update(
            {
                "account_type": type(self).__name__,
                "overdraft_limit": self.overdraft_limit,
                "fixed_fee": self.fixed_fee,
                "withdrawal_limit": self.withdrawal_limit,
            }
        )
        return info

    def __str__(self):
        last_four = self._account_number[-4:]

        rows = [
            ("Account type", type(self).__name__),
            ("Customer", self._owner),
            ("Account", f"****{last_four}"),
            ("Status", self._status.value),
            ("Withdrawal limit", f"{self.withdrawal_limit:.2f} {self.currency}"),
            ("Overdraft limit", f"{self.overdraft_limit:.2f} {self.currency}"),
            ("Fixed fee", f"{self.fixed_fee:.2f} {self.currency}"),
            ("Balance", f"{self._balance:.2f} {self.currency}"),
        ]

        return build_account_table(rows)

#Investment account
class InvestmentAccount(BankAccount):
    """Investment account with portfolio management across asset types."""

    SUPPORTED_ASSET_TYPES = {"stocks", "bonds", "etf"}  # noqa: RUF012

    def __init__(
        self,
        owner,
        balance=0,
        account_number=None,
        currency="RUB",
        status=AccountStatus.ACTIVE,
        withdrawal_limit=None,
    ):
        super().__init__(owner, balance, account_number, currency, status, withdrawal_limit)
        self.portfolio = {asset: Decimal(0) for asset in self.SUPPORTED_ASSET_TYPES}

    def withdraw(self, amount):
        self._check_status()
        amount = self._validate_amount(amount)

        if amount == 0:
            raise InvalidOperationError("Withdrawal amount must be greater than zero.")

        if amount > self.withdrawal_limit:
            raise InsufficientFundsError(
                f"Withdrawal amount exceeds daily limit of {self.withdrawal_limit}"
            )

        if amount > self._balance:
            raise InsufficientFundsError(
                "Insufficient funds to complete the withdrawal."
            )

        self._balance -= amount
        return self._balance

    def allocated(self, asset_type, amount):
        """Allocate funds to a specific asset type in the investment portfolio."""
        self._check_status()
        amount = self._validate_amount(amount)

        if asset_type not in self.SUPPORTED_ASSET_TYPES:
            raise InvalidOperationError(
                f"Unsupported asset type: {asset_type}. "
                f"Supported types: {', '.join(sorted(self.SUPPORTED_ASSET_TYPES))}"
            )

        if amount <= 0:
            raise InvalidOperationError("Allocation amount must be greater than zero.")

        if amount > self._balance:
            raise InsufficientFundsError(
                "Insufficient funds to allocation"
            )

        self._balance -= amount
        self.portfolio[asset_type] += amount
        return self.portfolio[asset_type]

    def project_yearly_growth(self, growth_rates):
        """Calculate expected annual growth based on the growth rates per asset type."""
        self._check_status()

        for asset_type in growth_rates:
            if asset_type not in self.SUPPORTED_ASSET_TYPES:
                raise InvalidOperationError(
                    f"Unsupported asset type: {asset_type}. "
                    f"Supported types: {', '.join(sorted(self.SUPPORTED_ASSET_TYPES))}"
                )

        total_growth = Decimal(0)
        for asset_type, rate in growth_rates.items():
            total_growth += self.portfolio[asset_type] * Decimal(str(rate))

        return total_growth

    def get_account_info(self):
        info = super().get_account_info()
        portfolio_value = sum(self.portfolio.values())
        total_value = self._balance + portfolio_value
        info.update(
            {
                "account_type": type(self).__name__,
                "portfolio": {k: str(v) for k, v in self.portfolio.items()},
                "portfolio_value": portfolio_value,
                "total_value": total_value,
            }
        )
        return info

    def __str__(self):
        last_four = self._account_number[-4:]

        portfolio_str = ', '.join(f"{k}: {v:.2f}" for k, v in self.portfolio.items())
        total_value = self._balance + sum(self.portfolio.values())
        
        rows = [
            ("Account type", type(self).__name__),
            ("Customer", self._owner),
            ("Account", f"****{last_four}"),
            ("Status", self._status.value),
            ("Withdrawal limit", f"{self.withdrawal_limit:.2f} {self.currency}"),
            ("Portfolio", portfolio_str),
            ("Balance", f"{total_value:.2f} {self.currency}"),
        ]

        return build_account_table(rows)
    