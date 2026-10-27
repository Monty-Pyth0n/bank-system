import pytest
from decimal import Decimal

from src.models import (
    BankAccount,
    AccountStatus,
    InvalidOperationError,
    InsufficientFundsError,
    AccountFrozenError,
    AccountClosedError,
)


def test_create_account():
    account = BankAccount(
        owner="Ivan Petrov",
        balance=1000,
        currency="RUB"
    )

    assert account.owner == "Ivan Petrov"
    assert account.balance == Decimal("1000")
    assert account.currency == "RUB"
    assert account.status == AccountStatus.ACTIVE
    assert account.account_number


def test_deposit():
    account = BankAccount("Ivan", balance=1000)

    account.deposit(250)

    assert account.balance == Decimal("1250")


def test_withdraw():
    account = BankAccount("Ivan", balance=1000)

    account.withdraw(300)

    assert account.balance == Decimal("700")


def test_frozen_account_cannot_deposit():
    account = BankAccount(
        "Anna",
        balance=500,
        status=AccountStatus.FROZEN
    )

    with pytest.raises(AccountFrozenError):
        account.deposit(100)

    assert account.balance == Decimal("500")


def test_frozen_account_cannot_withdraw():
    account = BankAccount(
        "Anna",
        balance=500,
        status=AccountStatus.FROZEN
    )

    with pytest.raises(AccountFrozenError):
        account.withdraw(100)

    assert account.balance == Decimal("500")


def test_insufficient_funds():
    account = BankAccount("Ivan", balance=100)

    with pytest.raises(InsufficientFundsError):
        account.withdraw(200)

    assert account.balance == Decimal("100")


def test_negative_deposit():
    account = BankAccount("Ivan", balance=100)

    with pytest.raises(InvalidOperationError):
        account.deposit(-50)

    assert account.balance == Decimal("100")


def test_zero_deposit():
    account = BankAccount("Ivan", balance=100)

    with pytest.raises(InvalidOperationError):
        account.deposit(0)

    assert account.balance == Decimal("100")


def test_closed_account_cannot_deposit():
    account = BankAccount("Ivan", balance=100)
    account.close()

    with pytest.raises(AccountClosedError):
        account.deposit(50)

    assert account.balance == Decimal("100")


def test_invalid_currency():
    with pytest.raises(InvalidOperationError):
        BankAccount(
            owner="Ivan",
            balance=100,
            currency="GBP"
        )
