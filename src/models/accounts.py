from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from enum import Enum

from ..exceptions import (
    AccountClosedError,
    AccountFrozenError,
    InsufficientFundsError,
    InvalidOperationError,
    TransactionProhibitedError,
)
from ..logging import security_logger
from ..utils import (
    ALLOWED_CURRENCIES,
    _validate_amount,
    build_account_table,
    generate_account_number,
)

# ======================================
# Day 1: Basic Banking Account Model
# ======================================

# Account status
class AccountStatus(Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


# Abstract account
class AbstractAccount(ABC):
    def __init__(self, owner, balance=0, account_number=None):
        if not isinstance(owner, str) or not owner.strip():
            raise InvalidOperationError("Owner name cannot be empty.")

        self._owner = owner.strip()
        self._balance = _validate_amount(balance)
        self._account_number = (
            str(account_number).strip()
            if account_number is not None
            else generate_account_number()
        )

        if not self._account_number:
            raise InvalidOperationError("Account number cannot be empty.")

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
    
    DEFAULT_WITHDRAWAL_LIMIT = Decimal("100000.00")  # Default daily withdrawal limit

    PROHIBITED_HOURS_START = 0  # 00:00
    PROHIBITED_HOURS_END = 5  # 05:00

    def __init__(
        self,
        owner,
        balance=0,
        account_number=None,
        currency="RUB",
        status=AccountStatus.ACTIVE,
        withdrawal_limit=None,
        client=None,  # linking BankAccount and Client objects
    ):
        super().__init__(owner, balance, account_number)

        if not isinstance(currency, str):
            raise InvalidOperationError("Currency must be a string.")

        currency = currency.upper()

        if currency not in ALLOWED_CURRENCIES:
            raise InvalidOperationError(
                f"Unsupported currency: {currency}. "
                f"Allowed currencies: {', '.join(sorted(ALLOWED_CURRENCIES))}"
            )

        if not isinstance(status, AccountStatus):
            raise InvalidOperationError("Invalid account status.")

        self.currency = currency
        self._status = status
        self._client = client
        self.withdrawal_limit = (
            _validate_amount(withdrawal_limit)
            if withdrawal_limit is not None
            else self.DEFAULT_WITHDRAWAL_LIMIT
        )

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

    def _check_prohibited_hours(self):
        """Check if current time is within prohibited hours (00:00-05:00)."""
        current_hour = datetime.now().hour
        if self.PROHIBITED_HOURS_START <= current_hour < self.PROHIBITED_HOURS_END:
            security_logger.warning(
                f"SUSPICIOUS ACTIVITY: Transaction attempted during prohibited hours "
                f"({self.PROHIBITED_HOURS_START}:00-{self.PROHIBITED_HOURS_END}:00) "
                f"on account {self._account_number} by {self._owner}"
            )
            raise TransactionProhibitedError(
                f"Transactions are prohibited between {self.PROHIBITED_HOURS_START}:00 "
                f"and {self.PROHIBITED_HOURS_END}:00"
            )

    def _check_suspicious_activity(self, amount, operation_type):
        """Check for suspicious activity patterns."""
        # Large transactions at unusual hours (even if not in prohibited hours)
        current_hour = datetime.now().hour
        large_amount_threshold = Decimal("100000.00")

        if amount > large_amount_threshold and (current_hour < 6 or current_hour > 22):
            reason = (
                f"Large {operation_type} of {amount} "
                f"at unusual hour ({current_hour}:00) "
                f"on account {self._account_number}"
            )

            security_logger.warning(f"SUSPICIOUS ACTIVITY: {reason}")

            # Notify the suspicious client
            if self._client is not None:
                self._client.flag_suspicious_activity(reason)

    def deposit(self, amount):
        self._check_status()

        amount = _validate_amount(amount)

        if amount == 0:
            raise InvalidOperationError("Deposit amount must be greater than zero.")

        # Security checks
        self._check_prohibited_hours()
        self._check_suspicious_activity(amount, "deposit")

        self._balance += amount
        return self._balance

    def withdraw(self, amount):
        self._check_status()

        amount = _validate_amount(amount)

        if amount == 0:
            raise InvalidOperationError("Withdrawal amount must be greater than zero.")

        if amount > self._balance:
            raise InsufficientFundsError(
                "Insufficient funds to complete the withdrawal."
            )

        if amount > self.withdrawal_limit:
            raise InsufficientFundsError(
                f"Withdrawal amount exceeds daily limit of {self.withdrawal_limit}"
            )

        # Security checks
        self._check_prohibited_hours()
        self._check_suspicious_activity(amount, "withdrawal")

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


# ======================================
# Day 2: Advanced Types of Bank Accounts
# ======================================

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
        client=None,
    ):
        super().__init__(
            owner,
            balance,
            account_number,
            currency,
            status,
            withdrawal_limit,
            client=client,
        )

        self.min_balance = min_balance
        self.interest_rate = interest_rate

    def withdraw(self, amount):
        amount = _validate_amount(amount)

        if self._balance - amount < self.min_balance:
            raise InsufficientFundsError(
                f"Cannot withdraw below minimum balance of {self.min_balance}. "
                f"Available: {self._balance - self.min_balance}"
            )

        return super().withdraw(amount)

    def apply_monthly_interest(self):
        """Apply monthly interest to the account balance."""
        # Security checks
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

    DEFAULT_WITHDRAWAL_LIMIT = Decimal(
        "500000.00"
    )  # Higher daily withdrawal limit for premium

    def __init__(
        self,
        owner,
        balance=0,
        account_number=None,
        currency="RUB",
        status=AccountStatus.ACTIVE,
        overdraft_limit=50000,
        fixed_fee=100,
        withdrawal_limit=DEFAULT_WITHDRAWAL_LIMIT,
        client=None,
    ):
        super().__init__(
            owner,
            balance,
            account_number,
            currency,
            status,
            withdrawal_limit,
            client=client,
        )
        self.overdraft_limit = _validate_amount(overdraft_limit)
        self.fixed_fee = _validate_amount(fixed_fee)

    def withdraw(self, amount):
        self._check_status()
        amount = _validate_amount(amount)

        if amount == 0:
            raise InvalidOperationError("Withdrawal amount must be greater than zero.")

        total_with_fee = amount + self.fixed_fee

        if total_with_fee > self.withdrawal_limit:
            raise InsufficientFundsError(
                f"Withdrawal amount exceeds daily limit of {self.withdrawal_limit}"
            )

        available = self._balance + self.overdraft_limit

        if total_with_fee > available:
            raise InsufficientFundsError(
                f"Insufficient funds. Available with overdraft: {available}"
            )

        # Security checks
        self._check_prohibited_hours()
        self._check_suspicious_activity(amount, "withdrawal")

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


# Investment account
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
        client=None,
    ):
        super().__init__(
            owner,
            balance,
            account_number,
            currency,
            status,
            withdrawal_limit,
            client=client,
        )
        self._portfolio = {asset: Decimal(0) for asset in self.SUPPORTED_ASSET_TYPES}

    @property
    def portfolio(self):
        """Return a copy of the portfolio dictionary."""
        return self._portfolio.copy()

    @property
    def total_balance(self):
        """Total balance = free cash + portfolio value."""
        return self._balance + sum(self._portfolio.values())

    def withdraw(self, amount):
        """Withdraw funds from the investment account."""
        return super().withdraw(amount)

    def allocate(self, asset_type, amount):
        """Allocate funds to a specific asset type in the investment portfolio."""
        self._check_status()

        amount = _validate_amount(amount)

        if asset_type not in self.SUPPORTED_ASSET_TYPES:
            raise InvalidOperationError(
                f"Unsupported asset type: {asset_type}. "
                f"Supported types: {', '.join(sorted(self.SUPPORTED_ASSET_TYPES))}"
            )

        if amount <= 0:
            raise InvalidOperationError("Allocation amount must be greater than zero.")

        if amount > self._balance:
            raise InsufficientFundsError("Insufficient funds to allocation")

        # Security checks
        self._check_prohibited_hours()
        self._check_suspicious_activity(amount, "allocation")

        self._balance -= amount
        self._portfolio[asset_type] += amount
        return self._portfolio[asset_type]

    def project_yearly_growth(self, growth_rates):
        """Calculate expected annual growth based on the growth rates per asset type."""

        for asset_type in growth_rates:
            if asset_type not in self.SUPPORTED_ASSET_TYPES:
                raise InvalidOperationError(
                    f"Unsupported asset type: {asset_type}. "
                    f"Supported types: {', '.join(sorted(self.SUPPORTED_ASSET_TYPES))}"
                )

        total_growth = Decimal(0)
        for asset_type, rate in growth_rates.items():
            total_growth += self._portfolio[asset_type] * Decimal(str(rate))

        return total_growth

    def get_account_info(self):
        info = super().get_account_info()
        portfolio_value = sum(self._portfolio.values())
        info.update(
            {
                "account_type": type(self).__name__,
                "portfolio": {k: str(v) for k, v in self._portfolio.items()},
                "portfolio_value": portfolio_value,
                "total_balance": self.total_balance,
            }
        )
        return info

    def __str__(self):
        last_four = self._account_number[-4:]
        portfolio_str = ", ".join(f"{k}: {v:.2f}" for k, v in self._portfolio.items())

        rows = [
            ("Account type", type(self).__name__),
            ("Customer", self._owner),
            ("Account", f"****{last_four}"),
            ("Status", self._status.value),
            ("Withdrawal limit", f"{self.withdrawal_limit:.2f} {self.currency}"),
            ("Portfolio", portfolio_str),
            ("Total balance", f"{self.total_balance:.2f} {self.currency}"),
        ]

        return build_account_table(rows)
