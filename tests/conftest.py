from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.models import (
    AccountStatus,
    Bank,
    BankAccount,
    PremiumAccount,
)
from src.models.transaction import TransactionProcessor
from src.services import ReportBuilder

# =====================================
# ----------- Fixtures ----------------
# =====================================


@pytest.fixture(autouse=True)
def mock_datetime():
    """Mock datetime.now() to return a time outside prohibited hours (00:00-05:00)."""
    with (
        patch("src.models.accounts.datetime") as mock_acc_dt,
        patch("src.models.client.datetime") as mock_dt,
    ):
        # Set to 12:00 (noon) - outside prohibited hours
        freezed_time = datetime(2024, 1, 1, 12, 0, 0)
        for mock in (mock_dt, mock_acc_dt):
            mock.now.return_value = freezed_time
            # Need to keep the real datetime class for other uses
            mock.side_effect = lambda *args, **kw: datetime(*args, **kw)
        yield mock

# ======================================
# Day 4: Transaction System
# ======================================

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

# ======================================
# Day 7: Report Builder Tests
# ======================================

@pytest.fixture
def report_bank():
    """Create a bank with test clients and accounts for report testing."""
    bank = Bank("Test Bank")
    bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 30)
    bank.add_client("CL002", "Anna Smirnova", "anna@example.com", 25)
    bank.add_client("CL003", "Petr Ivanov", "petr@example.com", 35)

    bank.open_account("CL001", "bank", balance=5000, currency="RUB")
    bank.open_account("CL001", "savings", balance=10000, min_balance=100, interest_rate=0.02)
    bank.open_account("CL002", "premium", balance=25000, overdraft_limit=5000, fixed_fee=100, currency="USD")
    bank.open_account("CL003", "investment", balance=15000, currency="EUR")

    return bank


@pytest.fixture
def report_builder(report_bank):
    """Create a ReportBuilder instance with test data."""
    return ReportBuilder(report_bank)
