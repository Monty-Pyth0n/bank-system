from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.exceptions import (
    AccountClosedError,
    AccountFrozenError,
    ClientLockedError,
    InsufficientFundsError,
    InvalidOperationError,
    TransactionProhibitedError,
)
from src.models import (
    AccountStatus,
    Bank,
    BankAccount,
    Client,
    ClientStatus,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
)
from src.models.transaction import (
    Transaction,
    TransactionPriority,
    TransactionProcessor,
    TransactionQueue,
    TransactionStatus,
    TransactionType,
)


@pytest.fixture(autouse=True)
def mock_datetime():
    """Mock datetime.now() to return a time outside prohibited hours (00:00-05:00)."""
    with patch("src.models.accounts.datetime") as mock_acc_dt, \
            patch("src.models.client.datetime") as mock_dt:
            # Set to 12:00 (noon) - outside prohibited hours
            freezed_time = datetime(2024, 1, 1, 12, 0, 0)
            for mock in (mock_dt, mock_acc_dt):
                mock.now.return_value = freezed_time
                # Need to keep the real datetime class for other uses
                mock.side_effect = lambda *args, **kw: datetime(*args, **kw)
            yield mock

########################
# Day 1: Basic Bank Account Operations
#########################

def test_create_account():
    account = BankAccount(
        owner="Ivan Petrov",
        balance=1000,
        currency="RUB"
    )

    assert account.owner == "Ivan Petrov"
    assert account.balance == Decimal("1000.00")
    assert account.currency == "RUB"
    assert account.status == AccountStatus.ACTIVE
    assert account.account_number


def test_deposit():
    account = BankAccount("Ivan", balance=1000)

    account.deposit(250)

    assert account.balance == Decimal("1250.00")


def test_withdraw():
    account = BankAccount("Ivan", balance=1000)

    account.withdraw(300)

    assert account.balance == Decimal("700.00")


def test_bank_account_withdrawal_limit():
    """Test that BankAccount respects withdrawal limit."""
    # Create account with default limit and sufficient balance
    account = BankAccount(owner="Ivan Petrov", balance=1000000)
    assert account.withdrawal_limit == Decimal("100000.00")

    # Withdrawal within limit should work
    account.withdraw(50000)
    assert account.balance == Decimal("950000.00")

    # Withdrawal exceeding limit should fail
    with pytest.raises(InsufficientFundsError) as exc_info:
        account.withdraw(100001)
    assert "exceeds daily limit" in str(exc_info.value)


def test_bank_account_custom_withdrawal_limit():
    """Test that BankAccount respects custom withdrawal limit."""
    # Create account with custom limit and sufficient balance
    account = BankAccount(owner="Ivan Petrov", balance=1000000, withdrawal_limit=50000)
    assert account.withdrawal_limit == Decimal("50000.00")

    # Withdrawal within limit should work
    account.withdraw(25000)
    assert account.balance == Decimal("975000.00")

    # Withdrawal exceeding limit should fail
    with pytest.raises(InsufficientFundsError) as exc_info:
        account.withdraw(50001)
    assert "exceeds daily limit" in str(exc_info.value)


def test_frozen_account_cannot_deposit():
    account = BankAccount(
        "Anna",
        balance=500,
        status=AccountStatus.FROZEN
    )

    with pytest.raises(AccountFrozenError):
        account.deposit(100)

    assert account.balance == Decimal("500.00")


def test_frozen_account_cannot_withdraw():
    account = BankAccount(
        "Anna",
        balance=500,
        status=AccountStatus.FROZEN
    )

    with pytest.raises(AccountFrozenError):
        account.withdraw(100)

    assert account.balance == Decimal("500.00")


def test_insufficient_funds():
    account = BankAccount("Ivan", balance=100)

    with pytest.raises(InsufficientFundsError):
        account.withdraw(200)

    assert account.balance == Decimal("100.00")


def test_negative_deposit():
    account = BankAccount("Ivan", balance=100)

    with pytest.raises(InvalidOperationError):
        account.deposit(-50)

    assert account.balance == Decimal("100.00")


def test_zero_deposit():
    account = BankAccount("Ivan", balance=100)

    with pytest.raises(InvalidOperationError):
        account.deposit(0)

    assert account.balance == Decimal("100.00")


def test_closed_account_cannot_deposit():
    account = BankAccount("Ivan", balance=100)
    account.close()

    with pytest.raises(AccountClosedError):
        account.deposit(50)

    assert account.balance == Decimal("100.00")


def test_invalid_currency():
    with pytest.raises(InvalidOperationError):
        BankAccount(
            owner="Ivan",
            balance=100,
            currency="GBP"
        )

#######################
# Day 2: Advanced Types of Bank Accounts
#######################

# Savings account tests
def test_savings_account_creation():
    account = SavingsAccount(owner="Ivan Petrov", balance=1000, currency="RUB")
    assert account.owner == "Ivan Petrov"
    assert account.balance == Decimal("1000.00")
    assert account.currency == "RUB"
    assert account.status == AccountStatus.ACTIVE
    assert account.min_balance == Decimal("0.00")
    assert account.interest_rate == 0.01
    assert account.account_number


def test_savings_account_minimum_balance():
    account = SavingsAccount(owner="Ivan Petrov", balance=1000, min_balance=100)
    # Should be able to withdraw down to min_balance
    account.withdraw(900)
    assert account.balance == Decimal("100.00")

    # Should not allow withdrawal below min_balance
    with pytest.raises(InsufficientFundsError):
        account.withdraw(50)


def test_savings_account_withdrawal_limit():
    """Test that SavingsAccount respects withdrawal limit."""
    # Create savings account with sufficient balance above min_balance
    account = SavingsAccount(
        owner="Ivan Petrov",
        balance=1000000,
        min_balance=100,
        withdrawal_limit=50000
    )
    assert account.withdrawal_limit == Decimal("50000.00")

    # Withdrawal within limit and above min_balance should work
    account.withdraw(40000)
    assert account.balance == Decimal("960000.00")

    # Withdrawal exceeding limit should fail
    with pytest.raises(InsufficientFundsError) as exc_info:
        account.withdraw(60000)
    assert "exceeds daily limit" in str(exc_info.value)


def test_savings_account_apply_interest():
    account = SavingsAccount(owner="Ivan Petrov", balance=1000, interest_rate=0.05)
    interest_before = account.apply_monthly_interest()
    assert interest_before > Decimal("1000.00")


def test_savings_account_get_account_info():
    account = SavingsAccount(owner="Ivan Petrov", balance=1000, min_balance=100, interest_rate=0.02)
    info = account.get_account_info()
    assert info["min_balance"] == Decimal("100.00")
    assert info["interest_rate"] == 0.02


# Premium account tests
def test_premium_account_creation():
    account = PremiumAccount(owner="Anna Smirnova", balance=5000, currency="USD")
    assert account.owner == "Anna Smirnova"
    assert account.balance == Decimal("5000.00")
    assert account.currency == "USD"
    assert account.status == AccountStatus.ACTIVE
    assert account.overdraft_limit == Decimal("50000.00")
    assert account.fixed_fee == Decimal("100.00")
    assert account.account_number


def test_premium_account_overdraft():
    account = PremiumAccount(owner="Anna Smirnova", balance=500, overdraft_limit=1000, fixed_fee=10)
    # Withdrawal with fee should work within overdraft
    account.withdraw(600)
    assert account.balance == Decimal("-110.00")  # 500 - (600 + 10)


def test_premium_account_without_overdraft():
    account = PremiumAccount(owner="Anna Smirnova", balance=100, overdraft_limit=0, fixed_fee=50)
    with pytest.raises(InsufficientFundsError):
        account.withdraw(200)


def test_premium_account_withdrawal_limit():
    """Test that PremiumAccount respects its higher withdrawal limit."""
    # Create premium account with default limit and sufficient balance
    account = PremiumAccount(owner="Anna Smirnova", balance=1000000)
    assert account.withdrawal_limit == Decimal("500000.00")

    # Withdrawal within limit should work (includes fixed fee)
    account.withdraw(200000)
    assert account.balance == Decimal("799900.00")  # 1000000 - (200000 + 100)

    # Withdrawal exceeding limit should fail
    with pytest.raises(InsufficientFundsError) as exc_info:
        account.withdraw(600000)
    assert "exceeds daily limit" in str(exc_info.value)


def test_premium_account_withdrawal_limit_vs_overdraft():
    """Test that PremiumAccount withdrawal limit is checked before overdraft."""
    # Create premium account with overdraft
    account = PremiumAccount(
        owner="Anna Smirnova",
        balance=1000000,
        overdraft_limit=50000,
    )

    # Withdrawal within both limits should work
    account.withdraw(150000)
    assert account.balance == Decimal("849900.00")  # 1000000 - (150000 + 100)

    # Withdrawal within overdraft but exceeding withdrawal limit should fail
    # Daily limit is 500000, so try to withdraw more than that (including fee)
    with pytest.raises(InsufficientFundsError) as exc_info:
        account.withdraw(499901)  # 499901 + 100 fee = 500001 > 500000 limit
    assert "exceeds daily limit" in str(exc_info.value)


def test_premium_account_get_account_info():
    account = PremiumAccount(owner="Anna Smirnova", balance=5000, overdraft_limit=10000, fixed_fee=100)
    info = account.get_account_info()
    assert info["overdraft_limit"] == Decimal("10000.00")
    assert info["fixed_fee"] == Decimal("100.00")


# Investment account tests
def test_investment_account_creation():
    account = InvestmentAccount(owner="Petr Ivanov", balance=10000, currency="EUR")
    assert account.owner == "Petr Ivanov"
    assert account.balance == Decimal("10000.00")
    assert account.currency == "EUR"
    assert account.status == AccountStatus.ACTIVE
    assert len(account.portfolio) == 3  # stocks, bonds, etf
    assert account.account_number


def test_investment_account_allocate():
    account = InvestmentAccount(owner="Petr Ivanov", balance=10000, currency="EUR")
    account.allocate("stocks", 1000)
    account.allocate("bonds", 500)
    account.allocate("etf", 300)
    assert account.balance == Decimal("8200.00")
    assert account.portfolio["stocks"] == Decimal("1000.00")
    assert account.portfolio["bonds"] == Decimal("500.00")
    assert account.portfolio["etf"] == Decimal("300.00")


def test_investment_account_allocate_unsupported_asset():
    account = InvestmentAccount(owner="Petr Ivanov", balance=10000, currency="EUR")
    with pytest.raises(InvalidOperationError):
        account.allocate("real_estate", 100)


def test_investment_account_allocate_insufficient_funds():
    account = InvestmentAccount(owner="Petr Ivanov", balance=0, currency="EUR")
    with pytest.raises(InsufficientFundsError):
        account.allocate("stocks", 500)


def test_investment_account_project_yearly_growth():
    account = InvestmentAccount(owner="Petr Ivanov", balance=1800, currency="EUR")
    account.allocate("stocks", 1000)
    account.allocate("bonds", 500)
    account.allocate("etf", 300)
    growth = account.project_yearly_growth({"stocks": 0.10, "bonds": 0.04, "etf": 0.07})
    expected_growth = Decimal("141.00")  # 1000*0.10 + 500*0.04 + 300*0.07
    assert growth == expected_growth


def test_investment_account_project_yearly_growth_unsupported():
    account = InvestmentAccount(owner="Petr Ivanov", balance=10000, currency="EUR")
    with pytest.raises(InvalidOperationError):
        account.project_yearly_growth({"stocks": 0.10, "unknown": 0.05})


def test_investment_account_withdraw():
    account = InvestmentAccount(owner="Petr Ivanov", balance=5000, currency="EUR")
    account.withdraw(1000)
    assert account.balance == Decimal("4000.00")


def test_investment_account_withdrawal_limit():
    """Test that InvestmentAccount respects withdrawal limit."""
    # Create investment account with sufficient balance
    account = InvestmentAccount(
        owner="Petr Ivanov",
        balance=1000000,
        withdrawal_limit=50000
    )
    assert account.withdrawal_limit == Decimal("50000.00")

    # Withdrawal within limit should work
    account.withdraw(20000)
    assert account.balance == Decimal("980000.00")

    # Withdrawal exceeding limit should fail
    with pytest.raises(InsufficientFundsError) as exc_info:
        account.withdraw(60001)
    assert "exceeds daily limit" in str(exc_info.value)


def test_investment_account_get_account_info():
    account = InvestmentAccount(owner="Petr Ivanov", balance=5000, currency="EUR")
    account.allocate("stocks", 1000)
    info = account.get_account_info()
    assert info["portfolio_value"] == Decimal("1000.00")
    assert info["total_balance"] == Decimal("5000.00")


def test_investment_account_str():
    account = InvestmentAccount(owner="Petr Ivanov", balance=5000, currency="EUR")
    account.allocate("stocks", 1000)
    str_repr = str(account)
    assert "InvestmentAccount" in str_repr
    assert "5000.00" in str_repr
    assert "EUR" in str_repr
    assert "stocks: 1000.00" in str_repr


# Polymorphism tests
def test_polymorphic_withdraw():
    """Test that withdraw works differently for each account type."""
    savings = SavingsAccount(owner="Ivan", balance=1000, min_balance=100)
    premium = PremiumAccount(owner="Anna", balance=500, overdraft_limit=1000, fixed_fee=10)
    investment = InvestmentAccount(owner="Petr", balance=1000, currency="EUR")

    # All should have withdraw method
    savings.withdraw(500)
    premium.withdraw(200)
    investment.withdraw(100)


def test_polymorphic_get_account_info():
    """Test that get_account_info includes type-specific fields."""
    savings = SavingsAccount(owner="Ivan", balance=1000, min_balance=100, interest_rate=0.02)
    premium = PremiumAccount(owner="Anna", balance=5000, overdraft_limit=10000, fixed_fee=100)
    investment = InvestmentAccount(owner="Petr", balance=1000, currency="EUR")

    savings_info = savings.get_account_info()
    premium_info = premium.get_account_info()
    investment_info = investment.get_account_info()

    assert "min_balance" in savings_info
    assert "interest_rate" in savings_info
    assert "overdraft_limit" in premium_info
    assert "fixed_fee" in premium_info
    assert "portfolio" in investment_info


def test_polymorphic_str():
    """Test that __str__ includes type-specific information."""
    savings = SavingsAccount(owner="Ivan", balance=1000, min_balance=100, interest_rate=0.02)
    premium = PremiumAccount(owner="Anna", balance=5000, overdraft_limit=10000, fixed_fee=100)
    investment = InvestmentAccount(owner="Petr", balance=1000, currency="EUR")

    assert "SavingsAccount" in str(savings)
    assert "Min balance" in str(savings)
    assert "PremiumAccount" in str(premium)
    assert "Overdraft limit" in str(premium)
    assert "InvestmentAccount" in str(investment)
    assert "Portfolio" in str(investment)

# ======================================
# Day 3: Bank System
# ======================================

# Client class tests
def test_client_creation():
    """Test creating a client with valid data."""
    client = Client(
        client_id="CL001",
        full_name="Ivan Petrov",
        contact_details="ivan@example.com",
        age=25
    )
    
    assert client.client_id == "CL001"
    assert client.full_name == "Ivan Petrov"
    assert client.contact_details == "ivan@example.com"
    assert client.age == 25
    assert client.status == ClientStatus.ACTIVE
    assert client.account_numbers == []
    assert client.is_locked is False
    assert client.is_suspicious is False


def test_client_age_validation():
    """Test that client must be at least 18 years old."""
    with pytest.raises(InvalidOperationError) as exc_info:
        Client("CL001", "Ivan Petrov", "ivan@example.com", 17)
    assert "at least 18 years old" in str(exc_info.value)


def test_client_invalid_age():
    """Test that invalid age raises error."""
    with pytest.raises(InvalidOperationError) as exc_info:
        Client("CL001", "Ivan Petrov", "ivan@example.com", "invalid")
    assert "Age must be a valid integer" in str(exc_info.value)


def test_client_add_account():
    """Test adding an account to client."""
    client = Client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    account = BankAccount(owner="Ivan Petrov", balance=1000)
    
    client.add_account(account)
    
    assert account.account_number in client.account_numbers
    assert len(client.account_numbers) == 1


def test_client_remove_account():
    """Test removing an account from client."""
    client = Client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    account = BankAccount(owner="Ivan Petrov", balance=1000)
    client.add_account(account)
    
    client.remove_account(account.account_number)
    
    assert account.account_number not in client.account_numbers
    assert len(client.account_numbers) == 0


def test_client_remove_nonexistent_account():
    """Test removing non-existent account raises error."""
    client = Client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    with pytest.raises(InvalidOperationError) as exc_info:
        client.remove_account("NONEXISTENT")
    assert "Account number not found" in str(exc_info.value)


def test_client_get_account_info():
    """Test getting client info."""
    client = Client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    account = BankAccount(owner="Ivan Petrov", balance=1000)
    client.add_account(account)
    
    info = client.get_account_info()
    
    assert info["full_name"] == "Ivan Petrov"
    assert info["client_id"] == "CL001"
    assert info["contact_details"] == "ivan@example.com"
    assert info["age"] == 25
    assert info["status"] == ClientStatus.ACTIVE
    assert account.account_number in info["account_numbers"]


# Bank class tests
def test_bank_creation():
    """Test creating a bank."""
    bank = Bank("Test Bank")
    
    assert bank.name == "Test Bank"
    assert len(bank.clients) == 0
    assert len(bank.accounts) == 0


def test_bank_add_client():
    """Test adding a client to the bank."""
    bank = Bank("Test Bank")
    
    client = bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    assert client.client_id == "CL001"
    assert client.full_name == "Ivan Petrov"
    assert len(bank.clients) == 1
    assert bank.get_client("CL001") == client


def test_bank_add_duplicate_client():
    """Test adding duplicate client raises error."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    with pytest.raises(InvalidOperationError) as exc_info:
        bank.add_client("CL001", "Another Name", "another@example.com", 30)
    assert "already exists" in str(exc_info.value)


def test_bank_open_account():
    """Test opening different types of accounts."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    # Open basic bank account
    account1 = bank.open_account("CL001", "bank", balance=1000, currency="RUB")
    assert isinstance(account1, BankAccount)
    assert account1.balance == Decimal("1000.00")
    assert account1.currency == "RUB"
    
    # Open savings account
    account2 = bank.open_account("CL001", "savings", balance=5000, min_balance=100, interest_rate=0.02)
    assert isinstance(account2, SavingsAccount)
    assert account2.min_balance == Decimal("100.00")
    assert account2.interest_rate == 0.02
    
    # Open premium account
    account3 = bank.open_account("CL001", "premium", balance=10000, overdraft_limit=5000, fixed_fee=100)
    assert isinstance(account3, PremiumAccount)
    assert account3.overdraft_limit == Decimal("5000.00")
    assert account3.fixed_fee == Decimal("100.00")
    
    # Open investment account
    account4 = bank.open_account("CL001", "investment", balance=20000, currency="EUR")
    assert isinstance(account4, InvestmentAccount)
    assert account4.currency == "EUR"
    
    # Check client has all accounts
    client = bank.get_client("CL001")
    assert len(client.account_numbers) == 4


def test_bank_open_account_invalid_type():
    """Test opening account with invalid type raises error."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    with pytest.raises(InvalidOperationError) as exc_info:
        bank.open_account("CL001", "invalid_type", balance=1000)
    assert "Invalid account type" in str(exc_info.value)


def test_bank_open_account_nonexistent_client():
    """Test opening account for non-existent client raises error."""
    bank = Bank("Test Bank")
    
    with pytest.raises(InvalidOperationError) as exc_info:
        bank.open_account("NONEXISTENT", "bank", balance=1000)
    assert "not found" in str(exc_info.value)


def test_bank_close_account():
    """Test closing an account."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    account = bank.open_account("CL001", "bank", balance=1000)
    
    closed_account = bank.close_account(account.account_number)
    
    assert closed_account.status == AccountStatus.CLOSED
    assert account.account_number not in bank._accounts
    client = bank.get_client("CL001")
    assert account.account_number not in client.account_numbers


def test_bank_close_account_nonexistent():
    """Test closing non-existent account raises error."""
    bank = Bank("Test Bank")
    
    with pytest.raises(InvalidOperationError) as exc_info:
        bank.close_account("NONEXISTENT")
    assert "not found" in str(exc_info.value)


def test_bank_freeze_account():
    """Test freezing an account."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    account = bank.open_account("CL001", "bank", balance=1000)
    
    frozen_account = bank.freeze_account(account.account_number)
    
    assert frozen_account.status == AccountStatus.FROZEN
    
    # Try to deposit to frozen account
    with pytest.raises(AccountFrozenError):
        frozen_account.deposit(100)


def test_bank_unfreeze_account():
    """Test unfreezing an account."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    account = bank.open_account("CL001", "bank", balance=1000)
    bank.freeze_account(account.account_number)
    
    unfrozen_account = bank.unfreeze_account(account.account_number)
    
    assert unfrozen_account.status == AccountStatus.ACTIVE
    # Should be able to deposit now
    unfrozen_account.deposit(100)
    assert unfrozen_account.balance == Decimal("1100.00")


def test_bank_unfreeze_closed_account():
    """Test unfreezing a closed account raises error."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    account = bank.open_account("CL001", "bank", balance=1000)
    bank.close_account(account.account_number)
    
    # Account is removed from bank's accounts when closed, so unfreeze raises InvalidOperationError
    with pytest.raises(InvalidOperationError) as exc_info:
        bank.unfreeze_account(account.account_number)
    assert "not found" in str(exc_info.value)


# Authentication and security tests
def test_bank_authenticate_client_success():
    """Test successful client authentication."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    client = bank.authenticate_client("CL001", "ivan@example.com")
    
    assert client.client_id == "CL001"
    assert client.failed_login_attempts == 0


def test_bank_authenticate_client_wrong_contact():
    """Test authentication fails with wrong contact details."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    with pytest.raises(InvalidOperationError) as exc_info:
        bank.authenticate_client("CL001", "wrong@example.com")
    assert "contact details do not match" in str(exc_info.value)
    
    client = bank.get_client("CL001")
    assert client.failed_login_attempts == 1


def test_bank_authenticate_client_lockout_after_three_failures():
    """Test client gets locked after 3 failed login attempts."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    # First failed attempt
    with pytest.raises(InvalidOperationError):
        bank.authenticate_client("CL001", "wrong1@example.com")
    
    # Second failed attempt
    with pytest.raises(InvalidOperationError):
        bank.authenticate_client("CL001", "wrong2@example.com")
    
    # Third failed attempt - should lock the client
    with pytest.raises(InvalidOperationError):
        bank.authenticate_client("CL001", "wrong3@example.com")
    
    client = bank.get_client("CL001")
    assert client.is_locked is True
    assert client.failed_login_attempts == 3
    assert client.is_suspicious is True


def test_bank_authenticate_locked_client():
    """Test that locked client cannot authenticate even with correct details."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    # Lock the client with 3 failed attempts
    for _ in range(3):
        with pytest.raises(InvalidOperationError):
            bank.authenticate_client("CL001", "wrong@example.com")
    
    # Now try with correct details - should fail because client is locked
    with pytest.raises(ClientLockedError) as exc_info:
        bank.authenticate_client("CL001", "ivan@example.com")
    assert "locked" in str(exc_info.value).lower()


def test_bank_unlock_client():
    """Test unlocking a client."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    # Lock the client
    for _ in range(3):
        with pytest.raises(InvalidOperationError):
            bank.authenticate_client("CL001", "wrong@example.com")
    
    # Unlock the client
    bank.unlock_client("CL001")
    
    client = bank.get_client("CL001")
    assert client.is_locked is False
    assert client.failed_login_attempts == 0
    assert client.is_suspicious is False
    
    # Should be able to authenticate now
    client = bank.authenticate_client("CL001", "ivan@example.com")
    assert client.client_id == "CL001"


def test_bank_get_client_security_status():
    """Test getting client security status."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    status = bank.get_client_security_status("CL001")
    
    assert status["client_id"] == "CL001"
    assert status["full_name"] == "Ivan Petrov"
    assert status["status"] == "active"
    assert status["is_locked"] is False
    assert status["failed_login_attempts"] == 0
    assert status["max_failed_attempts"] == 3
    assert status["is_suspicious"] is False
    assert status["suspicious_activity"] is None


# Search accounts tests
def test_bank_search_accounts_by_owner():
    """Test searching accounts by owner name."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    bank.add_client("CL002", "Anna Smirnova", "anna@example.com", 30)
    
    bank.open_account("CL001", "bank", balance=1000)
    bank.open_account("CL001", "savings", balance=5000)
    bank.open_account("CL002", "bank", balance=2000)
    
    results = bank.search_accounts(owner="Ivan")
    
    assert len(results) == 2
    for account in results:
        assert "Ivan" in account.owner


def test_bank_search_accounts_by_currency():
    """Test searching accounts by currency."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    bank.open_account("CL001", "bank", balance=1000, currency="RUB")
    bank.open_account("CL001", "bank", balance=2000, currency="USD")
    bank.open_account("CL001", "bank", balance=3000, currency="EUR")
    
    results = bank.search_accounts(currency="USD")
    
    assert len(results) == 1
    assert results[0].currency == "USD"


def test_bank_search_accounts_by_status():
    """Test searching accounts by status."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    account1 = bank.open_account("CL001", "bank", balance=1000)
    account2 = bank.open_account("CL001", "bank", balance=2000)
    bank.freeze_account(account2.account_number)
    
    active_accounts = bank.search_accounts(status=AccountStatus.ACTIVE)
    frozen_accounts = bank.search_accounts(status=AccountStatus.FROZEN)
    
    assert len(active_accounts) == 1
    assert active_accounts[0].account_number == account1.account_number
    assert len(frozen_accounts) == 1
    assert frozen_accounts[0].account_number == account2.account_number


def test_bank_search_accounts_by_type():
    """Test searching accounts by type."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    bank.open_account("CL001", "bank", balance=1000)
    bank.open_account("CL001", "savings", balance=5000)
    bank.open_account("CL001", "premium", balance=10000)
    
    results = bank.search_accounts(account_type="savingsaccount")
    
    assert len(results) == 1
    assert isinstance(results[0], SavingsAccount)


def test_bank_search_accounts_by_balance_range():
    """Test searching accounts by balance range."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    bank.open_account("CL001", "bank", balance=1000)
    bank.open_account("CL001", "bank", balance=5000)
    bank.open_account("CL001", "bank", balance=10000)
    
    results = bank.search_accounts(min_balance=3000, max_balance=8000)
    
    assert len(results) == 1
    assert results[0].balance == Decimal("5000.00")


# Additional features tests
def test_bank_get_total_balance():
    """Test getting total balance across all accounts."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    bank.add_client("CL002", "Anna Smirnova", "anna@example.com", 30)
    
    bank.open_account("CL001", "bank", balance=1000)
    bank.open_account("CL001", "savings", balance=5000)
    bank.open_account("CL002", "bank", balance=2000)
    
    total = bank.get_total_balance()
    
    assert total == Decimal("8000.00")


def test_bank_get_clients_ranking():
    """Test ranking clients by total balance."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    bank.add_client("CL002", "Anna Smirnova", "anna@example.com", 30)
    bank.add_client("CL003", "Petr Ivanov", "petr@example.com", 35)
    
    # Ivan has 6000 total
    bank.open_account("CL001", "bank", balance=1000)
    bank.open_account("CL001", "savings", balance=5000)
    
    # Anna has 2000 total
    bank.open_account("CL002", "bank", balance=2000)
    
    # Petr has 15000 total
    bank.open_account("CL003", "premium", balance=10000)
    bank.open_account("CL003", "investment", balance=5000)
    
    ranking = bank.get_clients_ranking()
    
    assert len(ranking) == 3
    # First should be Petr with 15000
    assert ranking[0][0].client_id == "CL003"
    assert ranking[0][1] == Decimal("15000.00")
    # Second should be Ivan with 6000
    assert ranking[1][0].client_id == "CL001"
    assert ranking[1][1] == Decimal("6000.00")
    # Third should be Anna with 2000
    assert ranking[2][0].client_id == "CL002"
    assert ranking[2][1] == Decimal("2000.00")


def test_bank_get_clients_ranking_with_no_accounts():
    """Test ranking includes clients with no accounts (zero balance)."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    bank.add_client("CL002", "Anna Smirnova", "anna@example.com", 30)
    
    bank.open_account("CL001", "bank", balance=1000)
    
    ranking = bank.get_clients_ranking()
    
    assert len(ranking) == 2
    assert ranking[0][0].client_id == "CL001"
    assert ranking[0][1] == Decimal("1000.00")
    assert ranking[1][0].client_id == "CL002"
    assert ranking[1][1] == Decimal("0.00")


# Security: Suspicious activity tests
def test_suspicious_activity_flagged_on_large_transaction_at_night():
    """Test that large transactions at unusual hours flag suspicious activity."""
    # This test may be time-dependent, so we test the flagging mechanism directly
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    bank.open_account("CL001", "bank", balance=200000)
    
    # Manually flag suspicious activity
    client = bank.get_client("CL001")
    client.flag_suspicious_activity("Large deposit at unusual hour")
    
    assert client.is_suspicious is True
    assert "Large deposit at unusual hour" in client.suspicious_activity


def test_check_prohibited_hours_deposit(mock_datetime):
    """Test that deposit during prohibited hours (00:00-05:00) raises TransactionProhibitedError."""
    from datetime import datetime
    mock_datetime.now.return_value = datetime(2024, 1, 1, 3, 0, 0)  # 03:00 AM
    
    account = BankAccount(owner="Ivan Petrov", balance=1000)
    
    with pytest.raises(TransactionProhibitedError) as exc_info:
        account.deposit(100)
    assert "prohibited" in str(exc_info.value).lower()


def test_check_prohibited_hours_withdraw(mock_datetime):
    """Test that withdrawal during prohibited hours (00:00-05:00) raises TransactionProhibitedError."""
    from datetime import datetime
    mock_datetime.now.return_value = datetime(2024, 1, 1, 2, 30, 0)  # 02:30 AM
    
    account = BankAccount(owner="Ivan Petrov", balance=1000)
    
    with pytest.raises(TransactionProhibitedError) as exc_info:
        account.withdraw(100)
    assert "prohibited" in str(exc_info.value).lower()


def test_check_prohibited_hours_boundary_start(mock_datetime):
    """Test that transaction at exactly 00:00 raises TransactionProhibitedError."""
    from datetime import datetime
    mock_datetime.now.return_value = datetime(2024, 1, 1, 0, 0, 0)  # 00:00 AM
    
    account = BankAccount(owner="Ivan Petrov", balance=1000)
    
    with pytest.raises(TransactionProhibitedError):
        account.deposit(100)


def test_check_prohibited_hours_boundary_end(mock_datetime):
    """Test that transaction at exactly 05:00 does NOT raise error (prohibited hours end at 05:00)."""
    from datetime import datetime
    mock_datetime.now.return_value = datetime(2024, 1, 1, 5, 0, 0)  # 05:00 AM
    
    account = BankAccount(owner="Ivan Petrov", balance=1000)
    
    # Should NOT raise error at 05:00 (prohibited hours are 00:00-05:00 exclusive)
    account.deposit(100)
    assert account.balance == Decimal("1100.00")


def test_check_prohibited_hours_savings_account(mock_datetime):
    """Test that savings account withdrawal during prohibited hours raises TransactionProhibitedError."""
    from datetime import datetime
    mock_datetime.now.return_value = datetime(2024, 1, 1, 4, 0, 0)  # 04:00 AM
    
    account = SavingsAccount(owner="Ivan Petrov", balance=1000, min_balance=100)
    
    with pytest.raises(TransactionProhibitedError):
        account.withdraw(100)


def test_check_prohibited_hours_premium_account(mock_datetime):
    """Test that premium account withdrawal during prohibited hours raises TransactionProhibitedError."""
    from datetime import datetime
    mock_datetime.now.return_value = datetime(2024, 1, 1, 1, 0, 0)  # 01:00 AM
    
    account = PremiumAccount(owner="Ivan Petrov", balance=1000, overdraft_limit=500, fixed_fee=10)
    
    with pytest.raises(TransactionProhibitedError):
        account.withdraw(100)


def test_check_prohibited_hours_investment_account(mock_datetime):
    """Test that investment account allocation during prohibited hours raises TransactionProhibitedError."""
    from datetime import datetime
    mock_datetime.now.return_value = datetime(2024, 1, 1, 3, 30, 0)  # 03:30 AM
    
    account = InvestmentAccount(owner="Ivan Petrov", balance=1000, currency="EUR")
    
    with pytest.raises(TransactionProhibitedError):
        account.allocate("stocks", 100)


def test_client_locked_error_raised():
    """Test ClientLockedError is raised when client is locked."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    # Lock the client
    for _ in range(3):
        with pytest.raises(InvalidOperationError):
            bank.authenticate_client("CL001", "wrong@example.com")
    
    # Try to check locked status directly
    client = bank.get_client("CL001")
    with pytest.raises(ClientLockedError):
        client.check_locked()


def test_close_last_account_makes_client_inactive():
    """Test that closing the last account makes client inactive."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    account = bank.open_account("CL001", "bank", balance=1000)
    
    bank.close_account(account.account_number)
    
    client = bank.get_client("CL001")
    assert client.status == ClientStatus.INACTIVE


def test_bank_lock_unlock_client_admin():
    """Test admin lock/unlock client operations."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
    
    # Admin lock
    bank.lock_client("CL001")
    client = bank.get_client("CL001")
    assert client.is_locked is True
    
    # Admin unlock
    bank.unlock_client("CL001")
    client = bank.get_client("CL001")
    assert client.is_locked is False
    assert client.failed_login_attempts == 0

# ======================================
# Day 4: Transaction System
# ======================================


# --- Transaction model tests ---

def test_transaction_creation_basic():
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("1000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC002",
        fee=Decimal("10.00"),
    )
    assert txn.id
    assert txn.type == TransactionType.TRANSFER
    assert txn.amount == Decimal("1000.00")
    assert txn.currency == "RUB"
    assert txn.fee == Decimal("10.00")
    assert txn.sender == "ACC001"
    assert txn.recipient == "ACC002"
    assert txn.status == TransactionStatus.PENDING
    assert txn.failure_reason is None
    assert txn.created_at is not None
    assert txn.updated_at is not None
    assert txn.completed_at is None


def test_transaction_default_fee():
    txn = Transaction(
        type=TransactionType.DEPOSIT,
        amount=Decimal("500.00"),
        currency="USD",
        recipient="ACC002",
    )
    assert txn.fee == Decimal("0.00")


def test_transaction_validation_requires_sender_for_transfer():
    with pytest.raises(InvalidOperationError):
        Transaction(
            type=TransactionType.TRANSFER,
            amount=Decimal("100.00"),
            currency="RUB",
            recipient="ACC002",
        )


def test_transaction_validation_requires_recipient_for_transfer():
    with pytest.raises(InvalidOperationError):
        Transaction(
            type=TransactionType.TRANSFER,
            amount=Decimal("100.00"),
            currency="RUB",
            sender="ACC001",
        )


def test_transaction_validation_sender_equals_recipient():
    with pytest.raises(InvalidOperationError):
        Transaction(
            type=TransactionType.TRANSFER,
            amount=Decimal("100.00"),
            currency="RUB",
            sender="ACC001",
            recipient="ACC001",
        )


def test_transaction_withdrawal_requires_sender():
    with pytest.raises(InvalidOperationError):
        Transaction(
            type=TransactionType.WITHDRAWAL,
            amount=Decimal("100.00"),
            currency="RUB",
        )


def test_transaction_deposit_requires_recipient():
    with pytest.raises(InvalidOperationError):
        Transaction(
            type=TransactionType.DEPOSIT,
            amount=Decimal("100.00"),
            currency="RUB",
        )


def test_transaction_status_transitions():
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("100.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC002",
    )
    assert txn.is_successful() is False
    assert txn.is_finalized() is False

    txn._set_status(TransactionStatus.COMPLETED)
    assert txn.status == TransactionStatus.COMPLETED
    assert txn.is_successful() is True
    assert txn.is_finalized() is True
    assert txn.completed_at is not None

    txn._set_status(TransactionStatus.FAILED, failure_reason="Insufficient funds")
    assert txn.status == TransactionStatus.FAILED
    assert txn.failure_reason == "Insufficient funds"
    assert txn.is_finalized() is True


def test_transaction_to_dict():
    txn = Transaction(
        type=TransactionType.PAYMENT,
        amount=Decimal("250.50"),
        currency="EUR",
        sender="ACC001",
        recipient="ACC002",
        fee=Decimal("1.25"),
    )
    d = txn.to_dict()
    assert d["id"] == txn.id
    assert d["type"] == "payment"
    assert d["amount"] == "250.50"
    assert d["currency"] == "EUR"
    assert d["fee"] == "1.25"
    assert d["sender"] == "ACC001"
    assert d["recipient"] == "ACC002"
    assert d["status"] == "pending"
    assert d["failure_reason"] is None
    assert "created_at" in d
    assert "updated_at" in d


def test_transaction_str_and_repr():
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("100.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC002",
    )
    s = str(txn)
    assert "Transaction" in s
    assert "transfer" in s
    assert "100.00" in s
    assert "RUB" in s
    r = repr(txn)
    assert "Transaction(id=" in r
    assert "type=transfer" in r


# --- TransactionQueue tests ---

def test_queue_add_and_priority_order():
    queue = TransactionQueue()
    t1 = Transaction(type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A")
    t2 = Transaction(type=TransactionType.DEPOSIT, amount=Decimal(20), currency="RUB", recipient="B")
    t3 = Transaction(type=TransactionType.DEPOSIT, amount=Decimal(30), currency="RUB", recipient="C")

    queue.add(t1, TransactionPriority.LOW)
    queue.add(t2, TransactionPriority.URGENT)
    queue.add(t3, TransactionPriority.NORMAL)

    assert queue.get_next() is t2
    assert queue.get_next() is t3
    assert queue.get_next() is t1


def test_queue_cancel():
    queue = TransactionQueue()
    t1 = Transaction(type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A")
    t2 = Transaction(type=TransactionType.DEPOSIT, amount=Decimal(20), currency="RUB", recipient="B")

    queue.add(t1)
    queue.add(t2)

    assert queue.cancel(t1.id) is True
    assert queue.get_next() is t2
    assert queue.get_next() is None


def test_queue_set_priority():
    queue = TransactionQueue()
    t1 = Transaction(type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A")
    t2 = Transaction(type=TransactionType.DEPOSIT, amount=Decimal(20), currency="RUB", recipient="B")

    queue.add(t1, TransactionPriority.LOW)
    queue.add(t2, TransactionPriority.NORMAL)

    assert queue.set_priority(t1.id, TransactionPriority.URGENT) is True
    assert queue.get_next() is t1


def test_queue_set_priority_not_found():
    queue = TransactionQueue()
    assert queue.set_priority("nonexistent", TransactionPriority.HIGH) is False


def test_queue_scheduled_future():
    from datetime import datetime, timedelta
    queue = TransactionQueue()
    t1 = Transaction(type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A")
    future = datetime.now() + timedelta(hours=1)

    queue.add_scheduled(t1, future)
    assert queue.get_scheduled_count() == 1
    assert queue.is_empty() is True
    assert queue.get_next() is None


def test_queue_scheduled_past():
    from datetime import datetime, timedelta
    queue = TransactionQueue()
    t1 = Transaction(type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A")
    past = datetime.now() - timedelta(hours=1)

    queue.add_scheduled(t1, past)
    assert queue.get_scheduled_count() == 0
    assert queue.get_next() is t1


def test_queue_is_empty_considers_due_scheduled():
    """Due scheduled transactions must not make the queue appear empty."""
    from datetime import timedelta
    queue = TransactionQueue()
    t1 = Transaction(type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A")
    past = datetime.now() - timedelta(hours=1)

    # Simulate a transaction scheduled earlier that has since matured while
    # still sitting in _scheduled (add_scheduled with a past time would put it
    # straight into _queue, so we insert directly to reproduce the stuck case).
    queue._scheduled[t1.id] = (past, t1, TransactionPriority.NORMAL)

    assert queue.get_scheduled_count() == 1
    assert queue.is_empty() is False
    assert queue.get_next() is t1
    assert queue.get_scheduled_count() == 0
    assert queue.is_empty() is True


def test_queue_future_scheduled_still_empty():
    """A not-yet-due scheduled transaction must keep the queue empty."""
    from datetime import timedelta
    queue = TransactionQueue()
    t1 = Transaction(type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A")
    future = datetime.now() + timedelta(hours=1)

    queue._scheduled[t1.id] = (future, t1, TransactionPriority.NORMAL)

    assert queue.get_scheduled_count() == 1
    assert queue.is_empty() is True
    assert queue.get_next() is None


def test_processor_process_queue_processes_due_scheduled(txn_processor):
    """process_queue() must process scheduled transactions that have matured."""
    from datetime import timedelta

    proc, acc_active, _, _ = txn_processor
    t1 = Transaction(
        type=TransactionType.DEPOSIT,
        amount=Decimal("100.00"),
        currency="RUB",
        recipient=acc_active.account_number,
    )
    past = datetime.now() - timedelta(hours=1)
    proc.queue._scheduled[t1.id] = (past, t1, TransactionPriority.NORMAL)

    assert proc.queue.get_scheduled_count() == 1
    assert proc.queue.is_empty() is False

    stats = proc.process_queue()
    assert stats["completed"] == 1
    assert stats["failed"] == 0
    assert stats["skipped"] == 0
    assert t1.is_successful() is True
    assert proc.queue.is_empty() is True
    assert proc.queue.get_scheduled_count() == 0


def test_queue_clear_cancelled():
    queue = TransactionQueue()
    t1 = Transaction(type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A")
    t2 = Transaction(type=TransactionType.DEPOSIT, amount=Decimal(20), currency="RUB", recipient="B")

    queue.add(t1)
    queue.add(t2)
    queue.cancel(t1.id)

    removed = queue.clear_cancelled()
    assert removed == 1
    assert queue.size() == 1


# --- TransactionProcessor tests ---

@pytest.fixture
def txn_processor():
    acc_active = BankAccount(owner="Ivan", balance=1000, currency="RUB")
    acc_frozen = BankAccount(owner="Anna", balance=500, currency="RUB", status=AccountStatus.FROZEN)
    acc_premium = PremiumAccount(
        owner="Petr",
        balance=100,
        currency="RUB",
        overdraft_limit=500,
        fixed_fee=10,
    )
    # Set negative balance to simulate overdraft usage
    acc_premium._balance = Decimal("-100.00")
    accounts = {
        acc_active.account_number: acc_active,
        acc_frozen.account_number: acc_frozen,
        acc_premium.account_number: acc_premium,
    }
    return TransactionProcessor(accounts=accounts), acc_active, acc_frozen, acc_premium


def test_processor_calculate_fee_transfer(txn_processor):
    proc, _, _, _ = txn_processor
    txn = Transaction(type=TransactionType.TRANSFER, amount=Decimal("1000.00"), currency="RUB", sender="A", recipient="B")
    fee = proc.calculate_fee(txn)
    assert fee == Decimal("10.00")


def test_processor_calculate_fee_payment(txn_processor):
    proc, _, _, _ = txn_processor
    txn = Transaction(type=TransactionType.PAYMENT, amount=Decimal("1000.00"), currency="RUB", sender="A", recipient="B")
    fee = proc.calculate_fee(txn)
    assert fee == Decimal("5.00")


def test_processor_calculate_fee_deposit_zero(txn_processor):
    proc, _, _, _ = txn_processor
    txn = Transaction(type=TransactionType.DEPOSIT, amount=Decimal("1000.00"), currency="RUB", recipient="B")
    fee = proc.calculate_fee(txn)
    assert fee == Decimal("0.00")


def test_processor_apply_fee_internal_transfer(txn_processor):
    proc, acc_active, _, acc_premium = txn_processor
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("1000.00"),
        currency="RUB",
        sender=acc_active.account_number,
        recipient=acc_premium.account_number,
    )
    fee = proc.apply_fee(txn)
    assert fee == Decimal("10.00")


def test_processor_apply_fee_external_transfer(txn_processor):
    proc, acc_active, _, _ = txn_processor
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("1000.00"),
        currency="RUB",
        sender=acc_active.account_number,
        recipient="EXTERNAL_ACC",
    )
    fee = proc.apply_fee(txn)
    assert fee == Decimal("35.00")


def test_processor_convert_currency_usd_to_eur(txn_processor):
    proc, _, _, _ = txn_processor
    result = proc.convert_currency(Decimal("100.00"), "USD", "EUR")
    assert result == Decimal("92.00")


def test_processor_convert_currency_eur_to_usd(txn_processor):
    proc, _, _, _ = txn_processor
    result = proc.convert_currency(Decimal("100.00"), "EUR", "USD")
    assert result == Decimal("108.70")


def test_processor_convert_currency_same(txn_processor):
    proc, _, _, _ = txn_processor
    result = proc.convert_currency(Decimal("100.00"), "RUB", "RUB")
    assert result == Decimal("100.00")


def test_processor_convert_currency_unsupported(txn_processor):
    proc, _, _, _ = txn_processor
    with pytest.raises(InvalidOperationError):
        proc.convert_currency(Decimal("100.00"), "GBP", "USD")


def test_processor_set_get_exchange_rate(txn_processor):
    proc, _, _, _ = txn_processor
    proc.set_exchange_rate("GBP", Decimal("0.80"))
    assert proc.get_exchange_rate("GBP") == Decimal("0.80")
    assert proc.get_exchange_rate("nonexistent") is None


def test_processor_rule_frozen_sender(txn_processor):
    proc, _, acc_frozen, _ = txn_processor
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("100.00"),
        currency="RUB",
        sender=acc_frozen.account_number,
        recipient="ACC_OTHER",
    )
    with pytest.raises(AccountFrozenError):
        proc._validate_business_rules(txn)


def test_processor_rule_frozen_recipient(txn_processor):
    proc, _, acc_frozen, _ = txn_processor
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("100.00"),
        currency="RUB",
        sender="ACC_OTHER",
        recipient=acc_frozen.account_number,
    )
    with pytest.raises(AccountFrozenError):
        proc._validate_business_rules(txn)


def test_processor_rule_negative_balance_non_premium(txn_processor):
    proc, acc_active, _, _ = txn_processor
    acc_active._balance = Decimal("-50.00")
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("100.00"),
        currency="RUB",
        sender=acc_active.account_number,
        recipient="ACC_OTHER",
    )
    with pytest.raises(InvalidOperationError) as exc_info:
        proc._validate_business_rules(txn)
    assert "negative balance" in str(exc_info.value).lower()


def test_processor_rule_negative_balance_premium_allowed(txn_processor):
    proc, _, _, acc_premium = txn_processor
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("100.00"),
        currency="RUB",
        sender=acc_premium.account_number,
        recipient="ACC_OTHER",
    )
    proc._validate_business_rules(txn)  # should not raise


def test_processor_process_success(txn_processor):
    proc, acc_active, _, _ = txn_processor
    txn = Transaction(
        type=TransactionType.DEPOSIT,
        amount=Decimal("100.00"),
        currency="RUB",
        recipient=acc_active.account_number,
    )
    result = proc.process(txn)
    assert result is True
    assert txn.status == TransactionStatus.COMPLETED
    assert txn.fee == Decimal("0.00")


def test_processor_process_frozen_fails(txn_processor):
    proc, _, acc_frozen, _ = txn_processor
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("100.00"),
        currency="RUB",
        sender=acc_frozen.account_number,
        recipient="ACC_OTHER",
    )
    result = proc.process(txn)
    assert result is False
    assert txn.status == TransactionStatus.FAILED
    assert txn.failure_reason is not None
    assert "frozen" in txn.failure_reason.lower()


def test_processor_process_negative_balance_fails(txn_processor):
    proc, acc_active, _, _ = txn_processor
    acc_active._balance = Decimal("-50.00")
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("100.00"),
        currency="RUB",
        sender=acc_active.account_number,
        recipient="ACC_OTHER",
    )
    result = proc.process(txn)
    assert result is False
    assert txn.status == TransactionStatus.FAILED


def test_processor_process_already_finalized(txn_processor):
    proc, acc_active, _, _ = txn_processor
    txn = Transaction(
        type=TransactionType.DEPOSIT,
        amount=Decimal("100.00"),
        currency="RUB",
        recipient=acc_active.account_number,
    )
    proc.process(txn)
    assert txn.is_finalized() is True
    result = proc.process(txn)
    assert result is False


def test_processor_process_queue_ten_transactions(txn_processor):
    """Requirement 5: Create 10 transactions, add to queue, process them."""
    proc, acc_active, _, acc_premium = txn_processor
    queue = proc.queue

    for i in range(10):
        txn = Transaction(
            type=TransactionType.TRANSFER if i % 2 == 0 else TransactionType.DEPOSIT,
            amount=Decimal(f"{100 + i * 10}.00"),
            currency="RUB",
            sender=acc_active.account_number if i % 2 == 0 else None,
            recipient=acc_premium.account_number if i % 2 == 0 else acc_active.account_number,
        )
        queue.add(txn, TransactionPriority.NORMAL)

    assert queue.size() == 10
    stats = proc.process_queue()
    assert stats["completed"] + stats["failed"] + stats["skipped"] == 10
    assert stats["completed"] > 0


def test_processor_retry_failed(txn_processor):
    proc, _, acc_frozen, _ = txn_processor
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("100.00"),
        currency="RUB",
        sender=acc_frozen.account_number,
        recipient="ACC_OTHER",
    )
    proc.process(txn)
    assert txn.status == TransactionStatus.FAILED

    retried = proc.retry_failed(txn)
    assert retried is True
    assert txn.status == TransactionStatus.PENDING
    assert txn.failure_reason is None
    assert proc.get_retry_count(txn.id) == 1


def test_processor_retry_max_exceeded(txn_processor):
    proc, _, acc_frozen, _ = txn_processor
    proc._max_retries = 0
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("100.00"),
        currency="RUB",
        sender=acc_frozen.account_number,
        recipient="ACC_OTHER",
    )
    proc.process(txn)
    assert txn.status == TransactionStatus.FAILED
    assert proc.retry_failed(txn) is False


def test_processor_error_log(txn_processor):
    proc, _, acc_frozen, _ = txn_processor
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("100.00"),
        currency="RUB",
        sender=acc_frozen.account_number,
        recipient="ACC_OTHER",
    )
    proc.process(txn)
    assert len(proc.error_log) == 1
    assert proc.error_log[0]["transaction_id"] == txn.id
    assert proc.error_log[0]["error_type"] == "AccountFrozenError"


def test_processor_transfer_debits_sender_and_credits_recipient(txn_processor):
    proc, acc_active, _, acc_premium = txn_processor
    acc_active._balance = Decimal("1000.00")
    acc_premium._balance = Decimal("0.00")
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("100.00"),
        currency="RUB",
        sender=acc_active.account_number,
        recipient=acc_premium.account_number,
    )
    result = proc.process(txn)
    assert result is True
    assert txn.status == TransactionStatus.COMPLETED
    assert txn.fee == Decimal("1.00")
    # Sender debited amount + fee, recipient credited the amount.
    assert acc_active.balance == Decimal("899.00")
    assert acc_premium.balance == Decimal("100.00")


def test_processor_transfer_insufficient_funds_fails(txn_processor):
    proc, acc_active, _, acc_premium = txn_processor
    acc_active._balance = Decimal("100.00")
    acc_premium._balance = Decimal("0.00")
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("1000.00"),
        currency="RUB",
        sender=acc_active.account_number,
        recipient=acc_premium.account_number,
    )
    result = proc.process(txn)
    assert result is False
    assert txn.status == TransactionStatus.FAILED
    assert txn.failure_reason is not None
    # Balances must remain untouched on failure.
    assert acc_active.balance == Decimal("100.00")
    assert acc_premium.balance == Decimal("0.00")


def test_processor_deposit_credits_recipient(txn_processor):
    proc, acc_active, _, _ = txn_processor
    acc_active._balance = Decimal("1000.00")
    txn = Transaction(
        type=TransactionType.DEPOSIT,
        amount=Decimal("250.00"),
        currency="RUB",
        recipient=acc_active.account_number,
    )
    result = proc.process(txn)
    assert result is True
    assert txn.status == TransactionStatus.COMPLETED
    assert txn.fee == Decimal("0.00")
    assert acc_active.balance == Decimal("1250.00")


def test_processor_withdrawal_debits_sender(txn_processor):
    proc, acc_active, _, _ = txn_processor
    acc_active._balance = Decimal("1000.00")
    txn = Transaction(
        type=TransactionType.WITHDRAWAL,
        amount=Decimal("100.00"),
        currency="RUB",
        sender=acc_active.account_number,
    )
    result = proc.process(txn)
    assert result is True
    assert txn.status == TransactionStatus.COMPLETED
    # Fee is 0.2% of 100 = 0.20; sender debited amount + fee.
    assert txn.fee == Decimal("0.20")
    assert acc_active.balance == Decimal("899.80")


def test_processor_transfer_cross_currency_conversion(txn_processor):
    proc, acc_active, _, _ = txn_processor
    acc_usd = BankAccount(owner="Alex", balance=Decimal("1000.00"), currency="USD")
    proc.accounts[acc_usd.account_number] = acc_usd
    acc_active._balance = Decimal("10000.00")  # RUB
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("100.00"),
        currency="RUB",
        sender=acc_active.account_number,
        recipient=acc_usd.account_number,
    )
    result = proc.process(txn)
    assert result is True
    assert txn.status == TransactionStatus.COMPLETED
    # Sender debited 100 RUB + 1 RUB fee (no conversion, same currency).
    assert acc_active.balance == Decimal("9899.00")
    # Recipient credited 100 RUB converted to USD: 100 / 90.5 * 1 = 1.10 USD.
    assert acc_usd.balance == Decimal("1001.10")
