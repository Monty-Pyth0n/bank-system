from datetime import datetime
from decimal import Decimal

import pytest

from src.exceptions import (
    AccountFrozenError,
    InvalidOperationError,
)
from src.models import BankAccount
from src.models.transaction import (
    Transaction,
    TransactionPriority,
    TransactionQueue,
    TransactionStatus,
    TransactionType,
)

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
    t1 = Transaction(
        type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A"
    )
    t2 = Transaction(
        type=TransactionType.DEPOSIT, amount=Decimal(20), currency="RUB", recipient="B"
    )
    t3 = Transaction(
        type=TransactionType.DEPOSIT, amount=Decimal(30), currency="RUB", recipient="C"
    )

    queue.add(t1, TransactionPriority.LOW)
    queue.add(t2, TransactionPriority.URGENT)
    queue.add(t3, TransactionPriority.NORMAL)

    assert queue.get_next() is t2
    assert queue.get_next() is t3
    assert queue.get_next() is t1


def test_queue_cancel():
    queue = TransactionQueue()
    t1 = Transaction(
        type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A"
    )
    t2 = Transaction(
        type=TransactionType.DEPOSIT, amount=Decimal(20), currency="RUB", recipient="B"
    )

    queue.add(t1)
    queue.add(t2)

    assert queue.cancel(t1.id) is True
    assert queue.get_next() is t2
    assert queue.get_next() is None


def test_queue_set_priority():
    queue = TransactionQueue()
    t1 = Transaction(
        type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A"
    )
    t2 = Transaction(
        type=TransactionType.DEPOSIT, amount=Decimal(20), currency="RUB", recipient="B"
    )

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
    t1 = Transaction(
        type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A"
    )
    future = datetime.now() + timedelta(hours=1)

    queue.add_scheduled(t1, future)
    assert queue.get_scheduled_count() == 1
    assert queue.is_empty() is True
    assert queue.get_next() is None


def test_queue_scheduled_past():
    from datetime import datetime, timedelta

    queue = TransactionQueue()
    t1 = Transaction(
        type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A"
    )
    past = datetime.now() - timedelta(hours=1)

    queue.add_scheduled(t1, past)
    assert queue.get_scheduled_count() == 0
    assert queue.get_next() is t1


def test_queue_is_empty_considers_due_scheduled():
    """Due scheduled transactions must not make the queue appear empty."""
    from datetime import timedelta

    queue = TransactionQueue()
    t1 = Transaction(
        type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A"
    )
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
    t1 = Transaction(
        type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A"
    )
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
    t1 = Transaction(
        type=TransactionType.DEPOSIT, amount=Decimal(10), currency="RUB", recipient="A"
    )
    t2 = Transaction(
        type=TransactionType.DEPOSIT, amount=Decimal(20), currency="RUB", recipient="B"
    )

    queue.add(t1)
    queue.add(t2)
    queue.cancel(t1.id)

    removed = queue.clear_cancelled()
    assert removed == 1
    assert queue.size() == 1


# --- TransactionProcessor tests ---

def test_processor_calculate_fee_transfer(txn_processor):
    proc, _, _, _ = txn_processor
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("1000.00"),
        currency="RUB",
        sender="A",
        recipient="B",
    )
    fee = proc.calculate_fee(txn)
    assert fee == Decimal("10.00")


def test_processor_calculate_fee_payment(txn_processor):
    proc, _, _, _ = txn_processor
    txn = Transaction(
        type=TransactionType.PAYMENT,
        amount=Decimal("1000.00"),
        currency="RUB",
        sender="A",
        recipient="B",
    )
    fee = proc.calculate_fee(txn)
    assert fee == Decimal("5.00")


def test_processor_calculate_fee_deposit_zero(txn_processor):
    proc, _, _, _ = txn_processor
    txn = Transaction(
        type=TransactionType.DEPOSIT,
        amount=Decimal("1000.00"),
        currency="RUB",
        recipient="B",
    )
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
            recipient=acc_premium.account_number
            if i % 2 == 0
            else acc_active.account_number,
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
    acc_usd = BankAccount(owner="Alex", balance=1000, currency="USD")
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