from datetime import datetime
from decimal import Decimal

from src.models.transaction import (
    Transaction,
    TransactionType,
)
from src.services import (
    AuditLog,
    RiskAnalyzer,
    RiskLevel,
    SeverityLevel,
)

# ======================================
# Day 5: Risk Analyzer
# ======================================

# --- RiskLevel enum tests ---

def test_risk_level_values():
    """Test RiskLevel enum has correct values."""
    assert RiskLevel.LOW.value == "low"
    assert RiskLevel.MEDIUM.value == "medium"
    assert RiskLevel.HIGH.value == "high"


def test_risk_level_ranking():
    """Test RiskLevel comparison operators."""
    assert RiskLevel.LOW < RiskLevel.MEDIUM < RiskLevel.HIGH
    assert RiskLevel.HIGH > RiskLevel.MEDIUM > RiskLevel.LOW
    assert RiskLevel.LOW <= RiskLevel.LOW
    assert RiskLevel.HIGH >= RiskLevel.HIGH
    assert RiskLevel.LOW.rank == 1
    assert RiskLevel.MEDIUM.rank == 2
    assert RiskLevel.HIGH.rank == 3


# --- RiskAnalyzer creation tests ---

def test_risk_analyzer_creation():
    """Test RiskAnalyzer can be created with default audit log."""
    analyzer = RiskAnalyzer()
    assert analyzer is not None
    assert analyzer.audit_log is not None
    assert len(analyzer.blocked_transactions) == 0
    assert len(analyzer.risk_profiles) == 0


def test_risk_analyzer_with_custom_audit_log():
    """Test RiskAnalyzer can be created with a custom AuditLog."""
    custom_log = AuditLog()
    analyzer = RiskAnalyzer(audit_log=custom_log)
    assert analyzer.audit_log is custom_log


def test_risk_analyzer_register_known_recipient():
    """Test registering known recipients."""
    analyzer = RiskAnalyzer()
    analyzer.register_known_recipient("ACC_KNOWN")
    assert "ACC_KNOWN" in analyzer._known_recipients

    # Registering again should not duplicate
    analyzer.register_known_recipient("ACC_KNOWN")
    assert len(analyzer._known_recipients) == 1


# --- analyze_transaction: Low risk tests ---

def test_analyze_low_risk_small_amount_daytime():
    """Test that small daytime transfers are low risk."""
    analyzer = RiskAnalyzer()
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("5000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC002",
        transaction_id="TXN_LOW_001",
    )
    txn._created_at = datetime(2024, 1, 1, 10, 0, 0)

    level = analyzer.analyze_transaction(txn, client_id="CL001")
    assert level == RiskLevel.LOW


def test_analyze_low_risk_deposit():
    """Test that deposits to known accounts are low risk."""
    analyzer = RiskAnalyzer()
    analyzer.register_known_recipient("ACC002")
    txn = Transaction(
        type=TransactionType.DEPOSIT,
        amount=Decimal("5000.00"),
        currency="RUB",
        recipient="ACC002",
        transaction_id="TXN_LOW_002",
    )
    txn._created_at = datetime(2024, 1, 1, 10, 0, 0)

    level = analyzer.analyze_transaction(txn, client_id="CL001")
    assert level == RiskLevel.LOW


# --- analyze_transaction: Medium risk tests ---

def test_analyze_medium_risk_large_amount():
    """Test that large amounts are medium risk."""
    analyzer = RiskAnalyzer()
    analyzer.register_known_recipient("ACC002")
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("150000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC002",
        transaction_id="TXN_MED_001",
    )
    txn._created_at = datetime(2024, 1, 1, 10, 0, 0)

    level = analyzer.analyze_transaction(txn, client_id="CL001")
    assert level == RiskLevel.MEDIUM


def test_analyze_medium_risk_night_transaction():
    """Test that night transactions add risk."""
    analyzer = RiskAnalyzer()
    analyzer.register_known_recipient("ACC002")
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("30000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC002",
        transaction_id="TXN_MED_002",
    )
    txn._created_at = datetime(2024, 1, 1, 23, 0, 0)  # 23:00 = night

    level = analyzer.analyze_transaction(txn, client_id="CL001")
    # Night alone gives +2, total score 2 -> LOW
    assert level == RiskLevel.LOW


def test_analyze_medium_risk_transfer_to_new_account():
    """Test that transfers to new/unknown accounts add risk."""
    analyzer = RiskAnalyzer()
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("30000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC_NEW",
        transaction_id="TXN_MED_003",
    )
    txn._created_at = datetime(2024, 1, 1, 10, 0, 0)

    level = analyzer.analyze_transaction(txn, client_id="CL001")
    # New recipient gives +2, total score 2 -> LOW
    assert level == RiskLevel.LOW


# --- analyze_transaction: High risk tests ---

def test_analyze_high_risk_large_amount_night_new_account():
    """Test that large amount + night + new account = high risk (blocked)."""
    analyzer = RiskAnalyzer()
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("200000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC_NEW",
        transaction_id="TXN_HIGH_001",
    )
    txn._created_at = datetime(2024, 1, 1, 2, 0, 0)  # 02:00 = night

    level = analyzer.analyze_transaction(txn, client_id="CL001")
    assert level == RiskLevel.HIGH
    # High-risk transactions should be blocked
    assert analyzer.is_blocked("TXN_HIGH_001")
    assert len(analyzer.blocked_transactions) == 1
    assert analyzer.blocked_transactions[0].id == "TXN_HIGH_001"


def test_analyze_high_risk_large_amount_night():
    """Test that large amount + night = high risk."""
    analyzer = RiskAnalyzer()
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("200000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC002",
        transaction_id="TXN_HIGH_002",
    )
    txn._created_at = datetime(2024, 1, 1, 2, 0, 0)  # night

    level = analyzer.analyze_transaction(txn, client_id="CL001")
    assert level == RiskLevel.HIGH


# --- Blocking tests ---

def test_high_risk_transactions_are_blocked():
    """Test that the bank blocks high-risk transactions."""
    analyzer = RiskAnalyzer()

    # Create a clearly high-risk transaction
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("500000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC_NEW",
        transaction_id="TXN_BLOCK_001",
    )
    txn._created_at = datetime(2024, 1, 1, 3, 0, 0)  # night

    level = analyzer.analyze_transaction(txn, client_id="CL001")
    assert level == RiskLevel.HIGH
    assert analyzer.is_blocked("TXN_BLOCK_001") is True
    assert analyzer.is_blocked("NONEXISTENT") is False


def test_low_risk_transactions_not_blocked():
    """Test that low-risk transactions are not blocked."""
    analyzer = RiskAnalyzer()
    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("5000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC002",
        transaction_id="TXN_NOT_BLOCKED",
    )
    txn._created_at = datetime(2024, 1, 1, 10, 0, 0)

    level = analyzer.analyze_transaction(txn, client_id="CL001")
    assert level == RiskLevel.LOW
    assert analyzer.is_blocked("TXN_NOT_BLOCKED") is False


# --- Risk profile tests ---

def test_risk_profile_tracking():
    """Test that client risk profiles are tracked."""
    analyzer = RiskAnalyzer()

    txn1 = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("5000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC002",
        transaction_id="TXN_PROF_1",
    )
    txn1._created_at = datetime(2024, 1, 1, 10, 0, 0)
    analyzer.analyze_transaction(txn1, client_id="CL001")

    txn2 = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("200000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC_NEW",
        transaction_id="TXN_PROF_2",
    )
    txn2._created_at = datetime(2024, 1, 1, 3, 0, 0)  # night
    analyzer.analyze_transaction(txn2, client_id="CL001")

    profile = analyzer.get_risk_profile("CL001")
    assert profile is not None
    assert profile["client_id"] == "CL001"
    assert profile["total_transactions"] == 2
    assert profile["overall_risk_level"] == RiskLevel.HIGH  # escalated


def test_get_all_risk_profiles():
    """Test getting all client risk profiles."""
    analyzer = RiskAnalyzer()

    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("5000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC002",
        transaction_id="TXN_ALL_1",
    )
    txn._created_at = datetime(2024, 1, 1, 10, 0, 0)
    analyzer.analyze_transaction(txn, client_id="CL001")

    txn2 = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("5000.00"),
        currency="RUB",
        sender="ACC003",
        recipient="ACC004",
        transaction_id="TXN_ALL_2",
    )
    txn2._created_at = datetime(2024, 1, 1, 10, 0, 0)
    analyzer.analyze_transaction(txn2, client_id="CL002")

    profiles = analyzer.get_all_risk_profiles()
    assert "CL001" in profiles
    assert "CL002" in profiles
    assert len(profiles) == 2


def test_get_risk_profile_nonexistent_client():
    """Test getting risk profile for nonexistent client returns None."""
    analyzer = RiskAnalyzer()
    assert analyzer.get_risk_profile("NONEXISTENT") is None


# --- Suspicious transactions tests ---

def test_get_suspicious_transactions_default():
    """Test getting suspicious transactions with default min_level=MEDIUM."""
    analyzer = RiskAnalyzer()

    # Low risk transaction
    txn1 = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("5000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC002",
        transaction_id="TXN_SUSP_1",
    )
    txn1._created_at = datetime(2024, 1, 1, 10, 0, 0)
    analyzer.analyze_transaction(txn1, client_id="CL001")

    # Medium risk transaction (large amount)
    txn2 = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("150000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC002",
        transaction_id="TXN_SUSP_2",
    )
    txn2._created_at = datetime(2024, 1, 1, 10, 0, 0)
    analyzer.analyze_transaction(txn2, client_id="CL001")

    # High risk transaction
    txn3 = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("500000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC_NEW",
        transaction_id="TXN_SUSP_3",
    )
    txn3._created_at = datetime(2024, 1, 1, 3, 0, 0)  # night
    analyzer.analyze_transaction(txn3, client_id="CL001")

    suspicious = analyzer.get_suspicious_transactions()
    suspicious_ids = [s["transaction_id"] for s in suspicious]
    assert "TXN_SUSP_1" not in suspicious_ids  # low risk, excluded
    assert "TXN_SUSP_2" in suspicious_ids  # medium risk, included
    assert "TXN_SUSP_3" in suspicious_ids  # high risk, included


def test_get_suspicious_transactions_min_level_high():
    """Test getting suspicious transactions with min_level=HIGH."""
    analyzer = RiskAnalyzer()

    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("500000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC_NEW",
        transaction_id="TXN_SUSP_HIGH",
    )
    txn._created_at = datetime(2024, 1, 1, 3, 0, 0)  # night
    analyzer.analyze_transaction(txn, client_id="CL001")

    suspicious = analyzer.get_suspicious_transactions(min_level=RiskLevel.HIGH)
    assert len(suspicious) == 1
    assert suspicious[0]["transaction_id"] == "TXN_SUSP_HIGH"


# --- Error statistics tests ---

def test_error_statistics_empty():
    """Test error statistics with no analyzed transactions."""
    analyzer = RiskAnalyzer()
    stats = analyzer.get_error_statistics()
    assert stats["total_analyzed"] == 0
    assert stats["high_risk"] == 0
    assert stats["medium_risk"] == 0
    assert stats["low_risk"] == 0
    assert stats["blocked_count"] == 0


def test_error_statistics_with_transactions():
    """Test error statistics with analyzed transactions."""
    analyzer = RiskAnalyzer()
    analyzer.register_known_recipient("ACC002")

    txn1 = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("5000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC002",
        transaction_id="TXN_STATS_1",
    )
    txn1._created_at = datetime(2024, 1, 1, 10, 0, 0)
    analyzer.analyze_transaction(txn1, client_id="CL001")

    txn2 = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("150000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC002",
        transaction_id="TXN_STATS_2",
    )
    txn2._created_at = datetime(2024, 1, 1, 10, 0, 0)
    analyzer.analyze_transaction(txn2, client_id="CL001")

    txn3 = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("500000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC_NEW",
        transaction_id="TXN_STATS_3",
    )
    txn3._created_at = datetime(2024, 1, 1, 3, 0, 0)  # night
    analyzer.analyze_transaction(txn3, client_id="CL001")

    stats = analyzer.get_error_statistics()
    assert stats["total_analyzed"] == 3
    assert stats["low_risk"] == 1
    assert stats["medium_risk"] == 1
    assert stats["high_risk"] == 1
    assert stats["blocked_count"] == 1
    assert stats["high_risk_percentage"] == 33.33
    assert stats["medium_risk_percentage"] == 33.33


# --- Generate report tests ---

def test_generate_report():
    """Test generating a comprehensive audit report."""
    analyzer = RiskAnalyzer()

    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("500000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC_NEW",
        transaction_id="TXN_REPORT_1",
    )
    txn._created_at = datetime(2024, 1, 1, 3, 0, 0)  # night
    analyzer.analyze_transaction(txn, client_id="CL001")

    report = analyzer.generate_report()

    assert "suspicious_transactions" in report
    assert "client_risk_profiles" in report
    assert "error_statistics" in report
    assert "blocked_transaction_ids" in report

    assert "TXN_REPORT_1" in report["blocked_transaction_ids"]
    assert "CL001" in report["client_risk_profiles"]
    assert report["error_statistics"]["high_risk"] == 1


# --- Audit log integration tests ---

def test_analyze_logs_to_audit_log():
    """Test that analyze_transaction logs to the audit log."""
    audit_log = AuditLog()
    analyzer = RiskAnalyzer(audit_log=audit_log)

    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("5000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC002",
        transaction_id="TXN_LOG_1",
    )
    txn._created_at = datetime(2024, 1, 1, 10, 0, 0)
    analyzer.analyze_transaction(txn, client_id="CL001")

    assert audit_log.size == 1
    entry = audit_log.entries[0]
    assert entry.source == "risk_analyzer"
    assert entry.severity == SeverityLevel.INFO  # low risk = INFO
    assert "TXN_LOG_1" in entry.message


def test_analyze_logs_high_risk_as_critical():
    """Test that high-risk transactions are logged as CRITICAL."""
    audit_log = AuditLog()
    analyzer = RiskAnalyzer(audit_log=audit_log)

    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("500000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC_NEW",
        transaction_id="TXN_LOG_HIGH",
    )
    txn._created_at = datetime(2024, 1, 1, 3, 0, 0)  # night
    analyzer.analyze_transaction(txn, client_id="CL001")

    critical_entries = audit_log.filter_entries(min_severity=SeverityLevel.CRITICAL)
    assert len(critical_entries) == 1
    assert "TXN_LOG_HIGH" in critical_entries[0].message


# --- Requirement 4: 10 transactions test ---

def test_risk_analyzer_process_ten_transactions():
    """Requirement 4: Create 10 transactions, analyze them with RiskAnalyzer."""
    analyzer = RiskAnalyzer()
    # base_time = datetime(2024, 1, 1, 10, 0, 0)

    transactions = []
    for i in range(10):
        txn = Transaction(
            type=TransactionType.TRANSFER if i % 2 == 0 else TransactionType.DEPOSIT,
            amount=Decimal(f"{100 + i * 1000}.00"),
            currency="RUB",
            sender=f"ACC_SENDER_{i % 3}" if i % 2 == 0 else None,
            recipient=f"ACC_REC_{i}" if i % 2 == 0 else f"ACC_SENDER_{i % 3}",
            transaction_id=f"TXN_TEN_{i:03d}",
        )
        # Make some transactions at night
        hour = 10 if i < 7 else 23  # last 3 at night
        txn._created_at = datetime(2024, 1, 1, hour, 0, 0)
        transactions.append(txn)

    # Register some known recipients
    analyzer.register_known_recipient("ACC_SENDER_0")
    analyzer.register_known_recipient("ACC_SENDER_1")

    # Analyze all 10 transactions
    results = []
    for i, txn in enumerate(transactions):
        level = analyzer.analyze_transaction(txn, client_id=f"CL_{i % 3}")
        results.append((txn.id, level))

    assert len(results) == 10

    # Verify statistics
    stats = analyzer.get_error_statistics()
    assert stats["total_analyzed"] == 10

    # Verify report generation
    report = analyzer.generate_report()
    assert "suspicious_transactions" in report
    assert "client_risk_profiles" in report
    assert "error_statistics" in report
    assert "blocked_transaction_ids" in report

    # Print results for visibility
    print(f"\n  Analyzed {len(results)} transactions:")
    for txn_id, level in results:
        print(f"    {txn_id}: {level.value}")
    print(f"  Statistics: {stats}")
    print(f"  Blocked: {report['blocked_transaction_ids']}")