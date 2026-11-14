from abc import ABC, abstractmethod  # noqa: I001
from decimal import Decimal, InvalidOperation
from datetime import datetime
from enum import Enum
import logging

from src.utils import generate_account_number
from src.utils import build_account_table

# Configure logging for suspicious activity
logging.basicConfig(level=logging.WARNING)
security_logger = logging.getLogger("bank.security")


# ======================================
# Day 1: Basic Banking Account Model
# ======================================

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


class ClientLockedError(Exception):
    """Raised when an account is locked due to too many failed login attempts."""


class TransactionProhibitedError(Exception):
    """Raised when a transaction is attempted during prohibited hours (00:00-05:00)."""


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

        if currency not in self.ALLOWED_CURRENCIES:
            raise InvalidOperationError(
                f"Unsupported currency: {currency}. "
                f"Allowed currencies: {', '.join(sorted(self.ALLOWED_CURRENCIES))}"
            )

        if not isinstance(status, AccountStatus):
            raise InvalidOperationError("Invalid account status.")

        self.currency = currency
        self._status = status
        self._client = client
        self.withdrawal_limit = self._validate_amount(
            withdrawal_limit
            ) if withdrawal_limit is not None else self.DEFAULT_WITHDRAWAL_LIMIT


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
        
        if amount > large_amount_threshold and (
            current_hour < 6 or current_hour > 22
            ):

            reason = (
                f"Large {operation_type} of {amount} "
                f"at unusual hour ({current_hour}:00) "
                f"on account {self._account_number}"
            )

            security_logger.warning(
                f"SUSPICIOUS ACTIVITY: {reason}"
                )

            # Notify the suspicious client
            if self._client is not None:
                self._client.flag_suspicious_activity(reason)

    def deposit(self, amount):
        self._check_status()

        amount = self._validate_amount(amount)

        if amount == 0:
            raise InvalidOperationError("Deposit amount must be greater than zero.")

        # Security checks
        self._check_prohibited_hours()
        self._check_suspicious_activity(amount, "deposit")

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
        amount = self._validate_amount(amount)

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
        withdrawal_limit=DEFAULT_WITHDRAWAL_LIMIT,
        client = None,
    ):
        super().__init__(
            owner, 
            balance, 
            account_number, 
            currency, 
            status, 
            withdrawal_limit,
            client=client
            )
        self.overdraft_limit = self._validate_amount(overdraft_limit)
        self.fixed_fee = self._validate_amount(fixed_fee)

    def withdraw(self, amount):
        self._check_status()
        amount = self._validate_amount(amount)

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
        client=None,
    ):
        super().__init__(
            owner, 
            balance, 
            account_number, 
            currency, 
            status, 
            withdrawal_limit,
            client=client
            )
        self.portfolio = {asset: Decimal(0) for asset in self.SUPPORTED_ASSET_TYPES}

    def allocate(self, asset_type, amount):
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

        # Security checks
        self._check_prohibited_hours()
        self._check_suspicious_activity(amount, "allocation")

        self._balance -= amount
        self.portfolio[asset_type] += amount
        return self.portfolio[asset_type]

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

    def __init__(self, client_id, full_name, contact_details, age, status=ClientStatus.ACTIVE):
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

    def _validate_age(self, age):
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
            raise ClientLockedError(
                "Client is already locked."
                )
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

class Bank:
    """Bank class managing clients and accounts."""

    def __init__(self, name):
        self._name = name.strip() if name else "Unnamed Bank"
        self._clients = {}  # client_id -> Client
        self._accounts = {}  # account_number -> Account 

    @property
    def name(self):
        return self._name

    @property
    def clients(self):
        return list(self._clients.values())

    @property
    def accounts(self):
        return list(self._accounts.values())

    def get_client(self, client_id):
        """Get a client by ID."""
        client_id = client_id.strip()
        if client_id not in self._clients:
            raise InvalidOperationError(f"Client with ID '{client_id}' not found.")

        return self._clients[client_id]

    def get_account(self, account_number):
        """Get an account by number."""
        account_number = account_number.strip()

        if account_number not in self._accounts:
            raise InvalidOperationError(f"Account '{account_number}' not found.")

        return self._accounts[account_number]

    def add_client(self, client_id, full_name, contact_details, age):
        """
        Add a new client to the bank.

        Args:
            client_id: Unique client identifier
            full_name: Client's full name
            contact_details: Client's contact information
            age: Client's age (must be >= 18)

        Returns:
            The created Client object

        Raises:
            InvalidOperationError: If client_id already exists or validation fails
        """
        client_id = client_id.strip()

        if client_id in self._clients:
            raise InvalidOperationError(f"Client with ID '{client_id}' already exists.")

        client = Client(client_id, full_name, contact_details, age)
        self._clients[client_id] = client

        return client

    def open_account(self, client_id, account_type="bank", **kwargs):
        """
        Open a new account for a client.

        Args:
            client_id: The client's ID
            account_type: Type of account ('bank', 'savings', 'premium', 'investment')
            **kwargs: Additional arguments for account creation (balance, currency, etc.)
        
        Returns:
            The created account object

        Raises:
            InvalidOperationError: If client_id does not exist or account_type is invalid
        """

        client = self.get_client(client_id)

        #Map account types to class
        account_classes = {
            "bank": BankAccount,
            "savings": SavingsAccount,
            "premium": PremiumAccount,
            "investment": InvestmentAccount
        }

        account_type_lower = account_type.lower()
        if account_type_lower not in account_classes:
            raise InvalidOperationError(
                f"Invalid account type '{account_type}'. "
                f"Valid types are: {', '.join(account_classes.keys())}"
            )

        AccountClass = account_classes[account_type_lower]

        # Create the account
        account = AccountClass(
            owner=client.full_name, 
            client=client,
            **kwargs
            )

        self._accounts[account.account_number] = account
        client.add_account(account)

        return account

    def close_account(self, account_number):
        """
        Close an account

        Args:
            account_number: The account number to close
        
        Returns:
            The closed account object

        Raises:
            InvalidOperationError: If account not found
            AccountClosedError: If the account is already closed
        """
        account = self.get_account(account_number)
        account.close()
        del self._accounts[account_number]

        # Remove from client's account list
        # Find the client who owns this account
        for client in self._clients.values():
            if account_number in client.account_numbers:
                client.remove_account(account_number)
                
                # If the last account is closed
                if not client.account_numbers:
                    client._status = ClientStatus.INACTIVE
                    
                break

        return account
    
    def freeze_account(self, account_number):
        """
        Freeze an account.

        Args:
            account_number: The account number to freeze

        Raises:
            InvalidOperationError: If account not found
            AccountFrozenError: If the account is already frozen
        """
        account = self.get_account(account_number)
        account.freeze()

        return account

    def unfreeze_account(self, account_number):
        """
        Unfreeze (activate) an account.

        Args:
            account_number: The account number to unfreeze
        
        Returns:
            The activated account object

        Raises:
            InvalidOperationError: If account not found
            AccountClosedError: If the account is already closed
        """

        account = self.get_account(account_number)
        account.activate()

        return account

    def authenticate_client(self, client_id, contact_details):
        """
        Authenticate a client.

        Args:
            client_id: The client's ID
            contact_details: Optional contact details for verification

        Returns:
            The authenticated Client object

        Raises:
            InvalidOperationError: If client not found or authentication fails
        """

        client = self.get_client(client_id)
        client.check_locked()

        if contact_details is None or client.contact_details != contact_details:
            client.record_failed_login()

            raise InvalidOperationError(
            "Authentication failed: contact details do not match."
            )
    
        client.reset_failed_attempts()

        return client

    def search_accounts(self, **criteria):
        """
        Search for accounts matching the given criteria.

        Args:
            **criteria: Search criteria (owner, currency, status, account_type, min_balance, max_balance)

        Returns:
            List of matching Account objects
        """

        results = []

        for account in self._accounts.values():
            match = True

            # Check owner
            if ("owner" in criteria) and (
                criteria["owner"].lower() not in account.owner.lower()
            ):
                match = False

            # Check currency
            if ("currency" in criteria) and match and (
                criteria["currency"].upper() != account.currency
            ):
                match = False

            # Check status
            if ("status" in criteria) and match:
                if isinstance(criteria["status"], AccountStatus):
                    status_value = criteria["status"].value
                else:
                    status_value = str(criteria["status"]).lower()
                if account.status.value != status_value:
                    match = False

            # Check account type
            if ("account_type" in criteria) and match and (
                criteria["account_type"].lower() != type(account).__name__.lower()
            ):
                match = False

            # Check minimum balance
            if ("min_balance" in criteria) and match and (
                account.balance < Decimal(str(criteria["min_balance"]))                        
            ):
                match = False

            # Check maximum balance
            if ("max_balance" in criteria) and match and (
                account.balance > Decimal(str(criteria["max_balance"]))
            ):
                match = False

            if match:
                results.append(account)

        return results

    def __str__(self):
        return f"Bank: {self._name}, Clients: {len(self._clients)}, Accounts: {len(self._accounts)}"

    # Security methods
    def lock_client(self, client_id):
        """Lock a client (admin operation)."""

        client = self.get_client(client_id)
        client._lock()

        return client

    def unlock_client(self, client_id):
        """Unlock a client (admin operation)."""
    
        client = self.get_client(client_id)
        client._unlock()

        return client

    def get_client_security_status(self, client_id):
        """Return a snapshot of the client's security state.
        Args:
            client_id: Unique client identifier.

        Returns:
            client_id (str): Client ID.
            full_name (str): Full name.
            status (str): Client status ('active' / 'inactive').
            is_locked (bool): Whether the client is locked.
            failed_login_attempts (int): Current number of failed attempts.
            max_failed_attempts (int): Threshold after which locking occurs.
            is_suspicious (bool): Whether the client is flagged as suspicious.
            suspicious_activity (str): Recent suspicious activity.
        """

        client = self.get_client(client_id)

        return {
            "client_id": client._client_id,
            "full_name": client._full_name,
            "status": client._status.value,
            "is_locked": client._is_locked,
            "failed_login_attempts": client._failed_login_attempts,
            "max_failed_attempts": client.MAX_FAILED_ATTEMPTS,
            "is_suspicious": client._is_suspicious,
            "suspicious_activity": client._suspicious_activity,
        }

    def get_total_balance(self):
        """Calculate the total balance across all accounts in the bank."""
        total = Decimal("0.00")
        for account in self._accounts.values():
            total += account.balance
        return total

    def get_clients_ranking(self):
        """Rank clients by their total account balance (descending)."""
        client_balances = []
        for client in self._clients.values():
            total_balance = Decimal("0.00")
            for account_number in client.account_numbers:
                account = self._accounts.get(account_number)
                if account:
                    total_balance += account.balance
            client_balances.append((client, total_balance))
        
        # Sort by balance descending
        client_balances.sort(key=lambda x: x[1], reverse=True)
        return client_balances

