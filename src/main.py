from src.models import (
    BankAccount,
    AccountStatus,
    InvalidOperationError,
    InsufficientFundsError,
    AccountFrozenError,
    AccountClosedError,
)

def main():
    print("Bank Account System")
    
    print("=== Creating accounts ===")

    # Active account
    active_account = BankAccount(
        owner="Ivan Petrov",
        balance=1000,
        currency="RUB"
    )

    # Frozen account
    frozen_account = BankAccount(
        owner="Anna Smirnova",
        balance=500,
        currency="USD",
        status=AccountStatus.FROZEN
    )

    print(active_account)
    print(frozen_account)

    # Operations on the active account
    print("\n=== Operations on the active account ===")

    try:
        active_account.deposit(250)
        print("Deposit of 250 RUB successful.")
        print(active_account)

        active_account.withdraw(100)
        print("Withdrawal of 100 RUB successful.")
        print(active_account)

    except (
        InvalidOperationError,
        InsufficientFundsError,
        AccountFrozenError,
        AccountClosedError
    ) as error:
        print(f"Error: {error}")

    # Operations on the frozen account
    print("\n=== Operations on the frozen account ===")

    try:
        frozen_account.deposit(100)
    except AccountFrozenError as error:
        print(f"Deposit rejected: {error}")

    try:
        frozen_account.withdraw(50)
    except AccountFrozenError as error:
        print(f"Withdrawal rejected: {error}")

    # Additional validation
    print("\n=== Additional validation ===")

    try:
        active_account.withdraw(100000)
    except InsufficientFundsError as error:
        print(f"Withdrawal rejected: {error}")

    try:
        active_account.deposit(-50)
    except InvalidOperationError as error:
        print(f"Deposit rejected: {error}")

    # Account information
    print("\n=== Account information ===")
    print(active_account.get_account_info())

if __name__ == "__main__":
    main()