from decimal import Decimal

import pytest

from src.exceptions import (
    AccountFrozenError,
    ClientLockedError,
    InvalidOperationError,
)
from src.models import (
    AccountStatus,
    Bank,
    BankAccount,
    ClientStatus,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
)

# ======================================
# Day 3: Bank System::Bank
# ======================================

# --- Bank class tests ---

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
    account2 = bank.open_account(
        "CL001", "savings", balance=5000, min_balance=100, interest_rate=0.02
    )
    assert isinstance(account2, SavingsAccount)
    assert account2.min_balance == Decimal("100.00")
    assert account2.interest_rate == 0.02

    # Open premium account
    account3 = bank.open_account(
        "CL001", "premium", balance=10000, overdraft_limit=5000, fixed_fee=100
    )
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


# --- Authentication and security tests ---

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


# --- Search accounts tests ---

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


# --- Additional features tests ---

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
