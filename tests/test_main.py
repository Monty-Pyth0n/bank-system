from decimal import Decimal  # noqa: I001

import pytest

from src.models import (
    BankAccount,
    SavingsAccount,
    PremiumAccount,
    InvestmentAccount,
    AccountStatus,
    InvalidOperationError,
    InsufficientFundsError,
    AccountFrozenError,
    AccountClosedError,
)

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
    account.allocated("stocks", 1000)
    account.allocated("bonds", 500)
    account.allocated("etf", 300)
    assert account.balance == Decimal("8200.00")
    assert account.portfolio["stocks"] == Decimal("1000.00")
    assert account.portfolio["bonds"] == Decimal("500.00")
    assert account.portfolio["etf"] == Decimal("300.00")


def test_investment_account_allocate_unsupported_asset():
    account = InvestmentAccount(owner="Petr Ivanov", balance=10000, currency="EUR")
    with pytest.raises(InvalidOperationError):
        account.allocated("real_estate", 100)


def test_investment_account_allocate_insufficient_funds():
    account = InvestmentAccount(owner="Petr Ivanov", balance=0, currency="EUR")
    with pytest.raises(InsufficientFundsError):
        account.allocated("stocks", 500)


def test_investment_account_project_yearly_growth():
    account = InvestmentAccount(owner="Petr Ivanov", balance=1800, currency="EUR")
    account.allocated("stocks", 1000)
    account.allocated("bonds", 500)
    account.allocated("etf", 300)
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


def test_investment_account_get_account_info():
    account = InvestmentAccount(owner="Petr Ivanov", balance=5000, currency="EUR")
    account.allocated("stocks", 1000)
    info = account.get_account_info()
    assert info["portfolio_value"] == Decimal("1000.00")
    assert info["total_value"] == Decimal("5000.00")


def test_investment_account_str():
    account = InvestmentAccount(owner="Petr Ivanov", balance=5000, currency="EUR")
    account.allocated("stocks", 1000)
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

    
