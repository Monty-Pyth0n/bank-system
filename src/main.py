from src.models import (  # noqa: I001
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

def main():

    print("===============================")
    print("      Bank Account System")
    print("===============================")
    print("\n=== Creating accounts ===")

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
        print(f"Deposit of 250 {active_account.currency} successful.")
        print(active_account)

        active_account.withdraw(100)
        print(f"Withdrawal of 100 {active_account.currency} successful.")
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

    # Day 2: Portfolio management
    print("\n=== Portfolio management ===")

    # Savings account
    savings = SavingsAccount(
        owner="Ivan Petrov",
        balance=1000,
        currency="RUB",
        min_balance=100,
        interest_rate=0.05
    )
    print(savings)
    print(f"Account info: {savings.get_account_info()}\n")

    try:
        savings.withdraw(950)
        print(f"Withdrawal of 950 {savings.currency} successful.")
        print(savings)
    except InsufficientFundsError as error:
        print(f"Withdrawal rejected: {error}")

    try:
        savings.withdraw(100)
    except InsufficientFundsError as error:
        print(f"Withdrawal rejected: {error}")

    # Apply monthly interest
    savings.apply_monthly_interest()
    print("After monthly interest:")
    print(savings)

    # Premium account
    premium = PremiumAccount(
        owner="Anna Smirnova",
        balance=500,
        currency="RUB",
        overdraft_limit=1000,
        fixed_fee=10
    )
    print(premium)
    print(f"Account info: {premium.get_account_info()}\n")

    try:
        premium.withdraw(600)
        print("Withdrawal of 600 RUB successful (with overdraft).")
        print(premium)
    except InsufficientFundsError as error:
        print(f"Withdrawal rejected: {error}")

    try:
        premium.deposit(1200000)
        print("Deposit of 1 200 000 RUB successful.")
        print(premium)
    except InsufficientFundsError as error:
        print(f"Deposit rejected: {error}")

    try:
        premium.withdraw(600000)
        print("Withdrawal of 600 000 RUB successful.")
        print(premium)
    except InsufficientFundsError as error:
        print(f"Withdrawal of 600 000 RUB rejected. {error}")   


    # Investment account
    investment = InvestmentAccount(
        owner="Petr Ivanov",
        balance=0,
        currency="EUR"
    )
    print(investment)
    print(f"Account info: {investment.get_account_info()}\n")

    try:
        investment.allocated("stocks", 1000)
        investment.allocated("bonds", 500)
        investment.allocated("etf", 300)
        print("After portfolio allocation:")
        print(investment)
        print(f"Account info: {investment.get_account_info()}\n")

        # Project yearly growth
        growth = investment.project_yearly_growth(
            {"stocks": 0.10, "bonds": 0.04, "etf": 0.07}
        )
        print(f"Projected yearly growth: {growth:.2f} {investment.currency}")
        
    except InsufficientFundsError as error:
        print(f"Portfolio allocation rejected: {error}")

if __name__ == "__main__":
    main()