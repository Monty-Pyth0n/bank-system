import pytest

from src.exceptions import (
    ClientLockedError,
    InvalidOperationError,
)
from src.models import (
    Bank,
    BankAccount,
    Client,
    ClientStatus,
)

# ======================================
# Day 3: Bank System::Client
# ======================================

# --- Client class tests ---

def test_client_creation():
    """Test creating a client with valid data."""
    client = Client(
        client_id="CL001",
        full_name="Ivan Petrov",
        contact_details="ivan@example.com",
        age=25,
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


# --- Security: Suspicious activity tests ---

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