from datetime import datetime, timedelta
from decimal import Decimal
from time import sleep
from unittest.mock import patch

from src.exceptions import (
    AccountClosedError,
    AccountFrozenError,
    ClientLockedError,
    InsufficientFundsError,
    InvalidOperationError,
    TransactionProhibitedError,
)
from src.models.accounts import (
    AccountStatus,
    BankAccount,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
)
from src.models.bank import Bank
from src.models.transaction import (
    Transaction,
    TransactionPriority,
    TransactionProcessor,
    TransactionType,
)
from src.services import AuditLog, RiskAnalyzer, RiskLevel


def main():
    with patch("src.models.accounts.datetime") as mock_acc_dt, \
        patch("src.models.client.datetime") as mock_dt:
        # Set to 12:00 (noon) - outside prohibited hours
        freezed_time = datetime(2024, 1, 1, 12, 0, 0)
        for mock in (mock_dt, mock_acc_dt):
            mock.now.return_value = freezed_time
            # Need to keep the real datetime class for other uses
            mock.side_effect = lambda *args, **kw: datetime(*args, **kw)

        print("===============================")
        print("      Bank Account System")
        print("===============================")
        print("\n=== Creating accounts ===")

        try:
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
                status=AccountStatus.FROZEN,
            )
            print(active_account)
            print(frozen_account)

        except InvalidOperationError as error:
            print(f"The invalid argument is provided: {error}")
            return

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
            investment.allocate("stocks", 1000)
            investment.allocate("bonds", 500)
            investment.allocate("etf", 300)
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

        # Day 3: Bank System
        print("\n=== Bank System ===")
        print("===============================")
        print(f"      Time: {mock_dt.now.return_value.strftime('%H:%M')}")
        print("===============================")

        print("\n--- Creating a bank ---")
        bank = Bank("Bo-Bank")
        print(bank)
        
        # Add clients
        print("\n--- Add the clients ---")
        bank.add_client("CL001", "Ivan Petrov", "ivan@example.com", 25)
        bank.add_client("CL002", "Anna Smirnova", "anna@example.com", 30)
        bank.add_client("CL003", "Alex Smith", "alex@example.com", 40)
        print(*bank.clients, sep="\n")

        # Open accounts
        print("\n--- Opening the accounts ---")
        ivan_bank = bank.open_account("CL001", "bank", balance=10000)
        print(ivan_bank)
        ivan_savings = bank.open_account(
            "CL001", "savings", balance=50000, min_balance=1000, interest_rate=0.03
        )
        print(ivan_savings)

        anna_premium = bank.open_account(
            "CL002", "premium", balance=20000, overdraft_limit=10000, fixed_fee=200
        )
        print(anna_premium)

        alex_invest = bank.open_account(
            "CL003", "investment", balance=1000000,
        )
        print(alex_invest)

        try:
            alex_invest.allocate("stocks", 50000)
            alex_invest.allocate("bonds", 200000)
            alex_invest.allocate("etf", 500000)
            print("After portfolio allocation:")
            print(alex_invest)
            print(f"Account info: {alex_invest.get_account_info()}\n")

            # Project yearly growth
            growth = alex_invest.project_yearly_growth(
                {"stocks": 0.10, "bonds": 0.04, "etf": 0.07}
            )
            print(f"Projected yearly growth: {growth:.2f} {alex_invest.currency}")

        except InsufficientFundsError as error:
            print(f"Portfolio allocation rejected: {error}")

        try:
            alex_invest.withdraw(50000)
            print("\nAfter withdrawal of 50000 RUB:")
            print(alex_invest)
            print(f"Account info: {alex_invest.get_account_info()}\n")
        except InsufficientFundsError as error:
            print(f"Withdrawal is rejected. {error}")

        try:
            alex_invest.deposit(150000)
            print("\nAfter deposit of 150000 RUB:")
            print(alex_invest)
            print(f"Account info: {alex_invest.get_account_info()}\n")
        except InsufficientFundsError as error:
            print(f"Deposit is rejected. {error}")
            

        # Authenticate clients
        print("\n--- Authentication of clients ---")
        bank.authenticate_client("CL001", "ivan@example.com")
        bank.authenticate_client("CL002", "anna@example.com")
        bank.authenticate_client("CL003", "alex@example.com")
        print(bank.get_client("CL001"))
        print(bank.get_client("CL002"))
        print(bank.get_client("CL003"))

        # Authentication with wrong credentials
        print("\n--- Authentication with wrong credentials ---")
        try:
            bank.authenticate_client("CL001", "wrong@example.com")
        except InvalidOperationError as error:
            print(f"Authentication rejected: {error}")

        try:
            bank.authenticate_client("CL001", "wrong@example.com")
        except InvalidOperationError as error:
            print(f"Authentication rejected: {error}")

        try:
            bank.authenticate_client("CL001", "wrong@example.com")
        except (InvalidOperationError, ClientLockedError) as error:
            print(f"Authentication rejected: {error}")
    

        # Check client security status
        print("\n--- Checking client security status ---")
        for key, value in bank.get_client_security_status("CL001").items():
            print(f"{key}: {value}")

        # Unlock client by admin
        print("\n--- Unlocking client by admin ---")
        bank.unlock_client("CL001")
        for key, value in bank.get_client_security_status("CL001").items():
                    print(f"{key}: {value}")

        
        # Perform transactions
        print("\n--- Performing transactions ---")
        try:
            ivan_bank.deposit(5000)
            print(f"Ivan deposited 5000 RUB, balance: {ivan_bank.balance} {ivan_bank.currency}")
            print(ivan_bank)
        except (InvalidOperationError, InsufficientFundsError, AccountFrozenError, AccountClosedError, TransactionProhibitedError) as error:
            print(f"Deposit rejected: {error}")

        try:
            ivan_savings.withdraw(2000)
            print(f"Ivan withdrew 2000 RUB from savings, balance: {ivan_savings.balance} {ivan_savings.currency}")
            print(ivan_savings)
        except (InvalidOperationError, InsufficientFundsError, AccountFrozenError, AccountClosedError, TransactionProhibitedError) as error:
            print(f"Withdrawal rejected: {error}")

        try:
            anna_premium.withdraw(5000)  # Includes 200 fee
            print(f"Anna withdrew 5000 RUB (with fee), balance: {anna_premium.balance} {anna_premium.currency}")
            print(anna_premium)
        except (InvalidOperationError, InsufficientFundsError, AccountFrozenError, AccountClosedError, TransactionProhibitedError) as error:
            print(f"Withdrawal rejected: {error}")
        
        # Freeze and unfreeze account
        print("\n--- Freezing and unfreezing account ---")
        try:
            bank.freeze_account(ivan_bank.account_number)
            print(f"Ivan's account is now frozen: {ivan_bank.status}")
            print(bank.get_account(ivan_bank.account_number))
        except (InvalidOperationError, AccountFrozenError, AccountClosedError) as error:
            print(f"Freeze rejected: {error}")

        try:
            bank.unfreeze_account(ivan_bank.account_number)
            print(f"Ivan's account is now unfrozen: {ivan_bank.status}")
            print(bank.get_account(ivan_bank.account_number))
        except (InvalidOperationError, AccountClosedError) as error:
            print(f"Unfreeze rejected: {error}")

        # Search accounts
        print("\n--- Searching accounts ---")
        ivan_accounts = bank.search_accounts(owner="Ivan")
        print(f"Found {len(ivan_accounts)} accounts for Ivan")
        print(*ivan_accounts, "\n")

        # Get total balance
        print("--- Getting total balance ---")
        total = bank.get_total_balance()
        print(f"Total balance across all accounts: {total} RUB")

        # Get ranking
        print("\n--- Getting client ranking ---")
        ranking = bank.get_clients_ranking()
        print(f"Ranking: {len(ranking)} clients")
        for i, (client, balance) in enumerate(ranking, 1):
            print(f"  {i}. {client.full_name}: {balance} {client.contact_details}")

        # Close account
        print("\n--- Closing account ---")
        try:
            bank.close_account(anna_premium.account_number)
            anna = bank.get_client("CL002")
            print(f"Anna's status after closing account: {anna.status}")
            print(anna)
        except (InvalidOperationError, AccountClosedError) as error:
            print(f"Close account rejected: {error}")

        # Day 4: Transaction System
        print("\n===============================")
        print("=== Transaction System ===")
        print("===============================")

        # Build account registry for the processor
        accounts = {
            ivan_bank.account_number: ivan_bank,
            ivan_savings.account_number: ivan_savings,
            anna_premium.account_number: anna_premium,
            alex_invest.account_number: alex_invest,
        }

        # Create audit log and risk analyzer and register internal accounts
        # as known recipients.
        audit_log = AuditLog()
        analyzer = RiskAnalyzer(audit_log=audit_log)
        for acc_num in accounts:
            analyzer.register_known_recipient(acc_num)

        # Create a transaction processor wired to the risk analyzer so that
        # high-risk transactions are blocked before any funds are moved.
        processor = TransactionProcessor(accounts=accounts, risk_analyzer=analyzer)
        # Create a queue for the processor
        queue = processor.queue

        print("\n=== Transaction model methods ===")

        print("\n---Creating of 10 transactions---")
        # Create 10 transactions with mixed types and priorities
        txns = [
            Transaction(
                type=TransactionType.TRANSFER,
                amount=Decimal("1000.00"),
                currency="RUB",
                sender=ivan_bank.account_number,
                recipient=anna_premium.account_number,
            ),
            Transaction(
                type=TransactionType.DEPOSIT,
                amount=Decimal("500.00"),
                currency="RUB",
                recipient=ivan_savings.account_number,
            ),
            Transaction(
                type=TransactionType.PAYMENT,
                amount=Decimal("250.00"),
                currency="RUB",
                sender=ivan_bank.account_number,
                recipient=alex_invest.account_number,
            ),
            Transaction(
                type=TransactionType.TRANSFER,
                amount=Decimal("3000.00"),
                currency="RUB",
                sender=alex_invest.account_number,
                recipient=ivan_bank.account_number,
            ),
            Transaction(
                type=TransactionType.WITHDRAWAL,
                amount=Decimal("200.00"),
                currency="RUB",
                sender=anna_premium.account_number,
            ),
            Transaction(
                type=TransactionType.DEPOSIT,
                amount=Decimal("750.00"),
                currency="RUB",
                recipient=alex_invest.account_number,
            ),
            Transaction(
                type=TransactionType.TRANSFER,
                amount=Decimal("1500.00"),
                currency="RUB",
                sender=ivan_bank.account_number,
                recipient="EXTERNAL_ACCOUNT",
            ),
            Transaction(
                type=TransactionType.PAYMENT,
                amount=Decimal("400.00"),
                currency="RUB",
                sender=anna_premium.account_number,
                recipient=ivan_savings.account_number,
            ),
            Transaction(
                type=TransactionType.TRANSFER,
                amount=Decimal("800.00"),
                currency="RUB",
                sender=alex_invest.account_number,
                recipient=anna_premium.account_number,
            ),
            Transaction(
                type=TransactionType.WITHDRAWAL,
                amount=Decimal("100.00"),
                currency="RUB",
                sender=ivan_savings.account_number,
            ),
        ]

        print(f"Transactions created (the 1st one):\n{txns[0]}")
        print(f"  is_finalized(): {txns[0].is_finalized()}")
        print(f"  is_successful(): {txns[0].is_successful()}")
        print(f"  to_dict(): {txns[0].to_dict()}")

        print("\n=== TransactionQueue methods ===\n")
        # Add transactions to queue with varying priorities
        print("---Add varying priorities to transactions.---")
        for i, txn in enumerate(txns):
            priority = (
                TransactionPriority.URGENT
                if i % 3 == 0
                else TransactionPriority.HIGH
                if i % 3 == 1
                else TransactionPriority.NORMAL
            )
            queue.add(txn, priority)
            print(f"Queued: {txn.type.value} {txn.amount} {txn.currency} (priority={priority.name})")
        
        print(f"\nTotal transactions in queue: {queue.size()}")
        print(f"  queue.is_empty(): {queue.is_empty()}")
        print(f"  queue.get_scheduled_count(): {queue.get_scheduled_count()}")
        next_txn = queue.peek()
        print(f"  next transaction in queue: {next_txn}")

        # Schedule a future transaction
        future_txn = Transaction(
            type=TransactionType.DEPOSIT,
            amount=Decimal("999.00"),
            currency="RUB",
            recipient=ivan_savings.account_number,
        )
        future_time = datetime.now() + timedelta(seconds=2)
        queue.add_scheduled(future_txn, future_time)
        print("\nAfter add_scheduled transaction ():")
        print(f"  scheduled transaction time: after {future_time.second} seconds")
        print(f"  queue.get_scheduled_count(): {queue.get_scheduled_count()}")
        print(f"  scheduled transactions: {queue._scheduled}")
        

        # Cancel a transaction from the queue
        txn_to_cancel = queue.peek()
        if txn_to_cancel:
            cancelled = queue.cancel(txn_to_cancel.id)
            print(f"\nAfter cancel({txn_to_cancel.id[:8]}...): cancelled={cancelled}")
            print(f"  queue.size(): {queue.size()}")

        # Change priority of a transaction
        txn_changed_priority = queue.peek()
        if txn_changed_priority:
            print("\nBefore set_priority")
            print(f"  {txn_changed_priority}")
            priority = queue.get_priority(txn_changed_priority.id)
            print(f"  priority: {priority.name if priority else 'not in queue'}") #URGENT

            new_priority = TransactionPriority.HIGH
            changed = queue.set_priority(txn_changed_priority.id, new_priority)
            print(
                f"\nAfter set_priority({txn_changed_priority.id[:8]}..., ",
                f"{new_priority.name}): changed={changed}"
            )
            print(f"  queue.size(): {queue.size()}")

        # Clear cancelled entries
        removed = queue.clear_cancelled()
        print(f"\nAfter clear_cancelled(): removed={removed}")
        print(f"  queue.size(): {queue.size()}")

        print("\n=== TransactionProcessor currency & exchange rate methods ===")

        rate = processor.convert_currency(Decimal("100.00"), "USD", "EUR")
        print(f"  convert_currency(100 USD -> EUR): {rate} EUR")
        rate = processor.convert_currency(Decimal("100.00"), "EUR", "USD")
        print(f"  convert_currency(100 EUR -> USD): {rate} USD")
        rate = processor.convert_currency(Decimal("100.00"), "RUB", "RUB")
        print(f"  convert_currency(100 RUB -> RUB): {rate} RUB")

        processor.set_exchange_rate("GBP", Decimal("0.80"))
        print("  set_exchange_rate(GBP, 0.80): done")
        gbp_rate = processor.get_exchange_rate("GBP")
        print(f"  get_exchange_rate(GBP): {gbp_rate}")
        unknown_rate = processor.get_exchange_rate("XYZ")
        print(f"  get_exchange_rate(XYZ): {unknown_rate}")

        print("\n=== TransactionProcessor retry & error logging ===")

        # Freeze the sender account
        bank.freeze_account(ivan_savings.account_number)

        # Create a transaction that will fail (frozen sender)
        frozen_txn = Transaction(
            type=TransactionType.TRANSFER,
            amount=Decimal("100.00"),
            currency="RUB",
            sender=ivan_savings.account_number,
            recipient=anna_premium.account_number,
        )
        result = processor.process(frozen_txn)
        print(f"  Process frozen sender transfer: result={result}, status={frozen_txn.status.value}")
        print(f"  failure_reason: {frozen_txn.failure_reason}")
        print(f"  retry count before retry: {processor.get_retry_count(frozen_txn.id)}")

        # Retry the failed transaction (back to queue)
        retried = processor.retry_failed(frozen_txn)
        print(f"  retry_failed(): {retried}, new status: {frozen_txn.status.value}")
        print(f"  retry count after retry: {processor.get_retry_count(frozen_txn.id)}")
        print(f"  queue.size(): {queue.size()}")

        # Show full error log
        print(f"\n  Error log entries: {len(processor.error_log)}")
        for entry in processor.error_log:
            print(f"    [{entry['transaction_id'][:8]}...] {entry['error_type']}: {entry['error']}")

        # Clear retry count
        processor.clear_retry_count(frozen_txn.id)
        print(f"\n  After clear_retry_count(): count={processor.get_retry_count(frozen_txn.id)}")

        print("\n=== TransactionProcessor process queue ===")
        s=2
        print(f"  queue.size(): {queue.size()}")
        print(f"--- Wait {s} seconds to allow the scheduled transactions time to enter the queue")
        sleep(s)    # waiting
        print(f"  queue.size(): {queue.size()}")
        # Process all transactions
        stats = processor.process_queue()
        print("\n--- Processing results ---")
        print(f"Completed: {stats['completed']}")
        print(f"Failed: {stats['failed']}")
        print(f"Skipped: {stats['skipped']}")

        # Show error log if any failures occurred
        if stats["failed"] > 0:
            print("\n--- Error log ---")
            for entry in processor.error_log:
                print(
                    f"  [{entry['transaction_id'][:8]}...] {entry['error_type']}: {entry['error']}"
                )
        print(f"  queue.size(): {queue.size()}")

        print("\n===============================")
        print("=== Audit and Risk Analysis ===")
        print("===============================")

        # Create a set of normal and suspicious transactions
        risk_txns = [
            # Normal: small daytime transfer to known account
            Transaction(
                type=TransactionType.TRANSFER,
                amount=Decimal("5000.00"),
                currency="RUB",
                sender=ivan_bank.account_number,
                recipient=anna_premium.account_number,
                transaction_id="RISK_TXN_001",
            ),
            # Normal: small deposit
            Transaction(
                type=TransactionType.DEPOSIT,
                amount=Decimal("3000.00"),
                currency="RUB",
                recipient=ivan_savings.account_number,
                transaction_id="RISK_TXN_002",
            ),
            # Suspicious: large amount (>= 100,000)
            Transaction(
                type=TransactionType.TRANSFER,
                amount=Decimal("150000.00"),
                currency="RUB",
                sender=ivan_bank.account_number,
                recipient=alex_invest.account_number,
                transaction_id="RISK_TXN_003",
            ),
            # Suspicious: night transaction
            Transaction(
                type=TransactionType.TRANSFER,
                amount=Decimal("40000.00"),
                currency="RUB",
                sender=ivan_bank.account_number,
                recipient=anna_premium.account_number,
                transaction_id="RISK_TXN_004",
            ),
            # Suspicious: transfer to new/unknown account
            Transaction(
                type=TransactionType.TRANSFER,
                amount=Decimal("25000.00"),
                currency="RUB",
                sender=ivan_bank.account_number,
                recipient="UNKNOWN_ACC_999",
                transaction_id="RISK_TXN_005",
            ),
            # Highly suspicious: large amount + night + new account
            Transaction(
                type=TransactionType.TRANSFER,
                amount=Decimal("500000.00"),
                currency="RUB",
                sender=ivan_bank.account_number,
                recipient="FOREIGN_ACC_888",
                transaction_id="RISK_TXN_006",
            ),
        ]

        # Set explicit timestamps for night transactions
        risk_txns[3]._created_at = datetime(2024, 1, 1, 23, 0, 0)  # 23:00 night
        risk_txns[5]._created_at = datetime(2024, 1, 1, 3, 0, 0)   # 03:00 night

        # Analyze all transactions
        print("\n--- Analyzing transactions for risk ---")
        analysis_results = []
        for txn in risk_txns:
            level = analyzer.analyze_transaction(txn, client_id="CL001")
            analysis_results.append((txn, level))
            blocked = " [BLOCKED]" if level == RiskLevel.HIGH else ""
            reason = f" - {txn.failure_reason}" if txn.failure_reason else ""
            print(
                f"  {txn.id}: {txn.amount} {txn.currency} -> {level.value}{blocked}"
                f" [status={txn.status.value}{reason}]"
            )

        # Show blocked transactions
        blocked_txns = analyzer.get_blocked_transactions()
        print(f"\n--- Blocked transactions ({len(blocked_txns)}) ---")
        for txn in blocked_txns:
            print(f"  {txn.id}: {txn.amount} {txn.currency} - BLOCKED")

        # Show risk profile
        profile = analyzer.get_risk_profile("CL001")
        print("\n--- Client risk profile (CL001) ---")
        if profile:
            print(f"  Overall risk level: {profile['overall_risk_level'].value}")
            print(f"  Total transactions: {profile['total_transactions']}")
            print(f"  High risk: {profile['high_risk_count']}")
            print(f"  Medium risk: {profile['medium_risk_count']}")
            print(f"  Low risk: {profile['low_risk_count']}")
            print(f"  Average risk score: {profile['average_risk_score']}")

        # Show statistics
        stats = analyzer.get_error_statistics()
        print("\n--- Error statistics ---")
        print(f"  Total analyzed: {stats['total_analyzed']}")
        print(f"  High risk: {stats['high_risk']} ({stats['high_risk_percentage']}%)")
        print(f"  Medium risk: {stats['medium_risk']} ({stats['medium_risk_percentage']}%)")
        print(f"  Low risk: {stats['low_risk']}")
        print(f"  Blocked count: {stats['blocked_count']}")

        # Show suspicious transactions
        suspicious = analyzer.get_suspicious_transactions()
        print(f"\n--- Suspicious transactions ({len(suspicious)}) ---")
        for entry in suspicious:
            print(
                f"  {entry['transaction_id']}: {entry['risk_level'].value} "
                f"(score={entry['risk_score']})"
            )

        # Show full audit report
        report = analyzer.generate_report()
        print("\n--- Full audit report ---")
        print(f"  Sections: {list(report.keys())}")
        print(f"  Blocked IDs: {report['blocked_transaction_ids']}")

        # Show audit log entries
        print(f"\n--- Audit log entries ({audit_log.size}) ---")
        for entry in audit_log.entries:
            print(
                f"  {entry.timestamp} [{entry.severity.value.upper()}] {entry.message}"
            )

        print("\n--- End of Audit and Risk Analysis ---")


if __name__ == "__main__":
    main()