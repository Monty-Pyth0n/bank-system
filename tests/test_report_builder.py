from datetime import datetime
from decimal import Decimal

import pytest

from src.exceptions import InvalidOperationError
from src.models.transaction import Transaction, TransactionType
from src.services import (
    ChartType,
    ReportType,
    RiskAnalyzer,
)

# ======================================
# Day 7: Report Builder Tests
# ======================================

# --- ReportType and ChartType enum tests ---

def test_report_type_values():
    """Test ReportType enum has correct values."""
    assert ReportType.CLIENT.value == "client"
    assert ReportType.BANK.value == "bank"
    assert ReportType.RISK.value == "risk"


def test_chart_type_values():
    """Test ChartType enum has correct values."""
    assert ChartType.PIE.value == "pie"
    assert ChartType.BAR.value == "bar"
    assert ChartType.BALANCE_HISTORY.value == "balance_history"


# --- Client report tests ---

def test_generate_client_report(report_builder, report_bank):
    """Test generating a client report."""
    report = report_builder.generate_client_report("CL001")

    assert report["report_type"] == "client"
    assert report["client_id"] == "CL001"
    assert report["full_name"] == "Ivan Petrov"
    assert report["contact_details"] == "ivan@example.com"
    assert report["age"] == 30
    assert report["status"] == "active"
    assert report["is_locked"] is False
    assert report["is_suspicious"] is False
    assert report["account_count"] == 2
    assert "generated_at" in report
    assert len(report["accounts"]) == 2


def test_generate_client_report_includes_account_details(report_builder):
    """Test that client report includes detailed account information."""
    report = report_builder.generate_client_report("CL001")

    account_numbers = [acc["account_number"] for acc in report["accounts"]]
    assert len(account_numbers) == 2

    # Check that accounts have expected fields
    for acc in report["accounts"]:
        assert "account_type" in acc
        assert "account_number" in acc
        assert "owner" in acc
        assert "balance" in acc
        assert "currency" in acc
        assert "status" in acc


def test_generate_client_report_total_balance(report_builder):
    """Test that client report calculates total balance correctly."""
    report = report_builder.generate_client_report("CL001")
    # 5000 + 10000 = 15000
    assert report["total_balance"] == "15000.00"


def test_generate_client_report_nonexistent_client(report_builder):
    """Test that generating report for nonexistent client raises error."""
    with pytest.raises(InvalidOperationError):
        report_builder.generate_client_report("NONEXISTENT")


# --- Bank report tests ---

def test_generate_bank_report(report_builder):
    """Test generating a bank-wide report."""
    report = report_builder.generate_bank_report()

    assert report["report_type"] == "bank"
    assert report["bank_name"] == "Test Bank"
    assert report["client_count"] == 3
    assert report["account_count"] == 4
    assert report["total_balance"] == "55000.00"  # 5000+10000+25000+15000
    assert report["locked_clients"] == 0
    assert report["suspicious_clients"] == 0
    assert "generated_at" in report


def test_generate_bank_report_distributions(report_builder):
    """Test that bank report includes all distribution data."""
    report = report_builder.generate_bank_report()

    assert "client_status_distribution" in report
    assert "account_status_distribution" in report
    assert "account_type_distribution" in report
    assert "currency_distribution" in report

    assert report["client_status_distribution"]["active"] == 3
    assert report["account_status_distribution"]["active"] == 4
    assert "BankAccount" in report["account_type_distribution"]
    assert "SavingsAccount" in report["account_type_distribution"]
    assert "PremiumAccount" in report["account_type_distribution"]
    assert "InvestmentAccount" in report["account_type_distribution"]
    assert report["currency_distribution"]["RUB"] == 2
    assert report["currency_distribution"]["USD"] == 1
    assert report["currency_distribution"]["EUR"] == 1


def test_generate_bank_report_top_clients(report_builder):
    """Test that bank report includes top clients ranked by balance."""
    report = report_builder.generate_bank_report()

    assert len(report["top_clients"]) == 3
    top_client = report["top_clients"][0]
    assert "client_id" in top_client
    assert "full_name" in top_client
    assert "total_balance" in top_client


# --- Risk report tests ---

def test_generate_risk_report(report_builder):
    """Test generating a risk report."""
    analyzer = RiskAnalyzer()
    report = report_builder.generate_risk_report(analyzer)

    assert report["report_type"] == "risk"
    assert "error_statistics" in report
    assert "client_risk_profiles" in report
    assert "suspicious_transactions_count" in report
    assert "blocked_transactions_count" in report
    assert "blocked_transaction_ids" in report
    assert "generated_at" in report

    stats = report["error_statistics"]
    assert stats["total_analyzed"] == 0
    assert stats["high_risk"] == 0
    assert stats["medium_risk"] == 0
    assert stats["low_risk"] == 0


def test_generate_risk_report_with_data(report_builder):
    """Test risk report with analyzed transactions."""
    analyzer = RiskAnalyzer()
    analyzer.register_known_recipient("ACC002")

    txn = Transaction(
        type=TransactionType.TRANSFER,
        amount=Decimal("500000.00"),
        currency="RUB",
        sender="ACC001",
        recipient="ACC_NEW",
        transaction_id="TXN_RISK_001",
    )
    txn._created_at = datetime(2024, 1, 1, 3, 0, 0)  # night
    analyzer.analyze_transaction(txn, client_id="CL001")

    report = report_builder.generate_risk_report(analyzer)

    assert report["suspicious_transactions_count"] == 1
    assert report["blocked_transactions_count"] == 1
    assert "TXN_RISK_001" in report["blocked_transaction_ids"]
    assert report["error_statistics"]["high_risk"] == 1


# --- generate_report dispatch tests ---

def test_generate_report_client_dispatch(report_builder):
    """Test generate_report dispatches to client report."""
    report = report_builder.generate_report(ReportType.CLIENT, client_id="CL001")
    assert report["report_type"] == "client"
    assert report["client_id"] == "CL001"


def test_generate_report_bank_dispatch(report_builder):
    """Test generate_report dispatches to bank report."""
    report = report_builder.generate_report(ReportType.BANK)
    assert report["report_type"] == "bank"
    assert report["bank_name"] == "Test Bank"


def test_generate_report_risk_dispatch(report_builder):
    """Test generate_report dispatches to risk report."""
    analyzer = RiskAnalyzer()
    report = report_builder.generate_report(ReportType.RISK, risk_analyzer=analyzer)
    assert report["report_type"] == "risk"


def test_generate_report_client_missing_id(report_builder):
    """Test generate_report raises error when client_id is missing."""
    with pytest.raises(InvalidOperationError) as exc_info:
        report_builder.generate_report(ReportType.CLIENT)
    assert "client_id is required" in str(exc_info.value)


def test_generate_report_risk_missing_analyzer(report_builder):
    """Test generate_report raises error when risk_analyzer is missing."""
    with pytest.raises(InvalidOperationError) as exc_info:
        report_builder.generate_report(ReportType.RISK)
    assert "risk_analyzer is required" in str(exc_info.value)


def test_generate_report_unknown_type(report_builder):
    """Test generate_report raises error for unknown report type."""
    with pytest.raises(InvalidOperationError) as exc_info:
        report_builder.generate_report("unknown_type")
    assert "Unknown report type" in str(exc_info.value)


# --- Text report tests ---

def test_generate_text_report_client(report_builder):
    """Test generating text report for client."""
    report = report_builder.generate_client_report("CL001")
    text = report_builder.generate_text_report(report)

    assert "REPORT TYPE: CLIENT" in text
    assert "Ivan Petrov" in text
    assert "CL001" in text
    assert "ivan@example.com" in text
    assert "active" in text
    assert "15000.00" in text


def test_generate_text_report_bank(report_builder):
    """Test generating text report for bank."""
    report = report_builder.generate_bank_report()
    text = report_builder.generate_text_report(report)

    assert "REPORT TYPE: BANK" in text
    assert "Test Bank" in text
    assert "Client Count: 3" in text
    assert "Account Count: 4" in text
    assert "Top Clients by Balance:" in text


def test_generate_text_report_risk(report_builder):
    """Test generating text report for risk."""
    analyzer = RiskAnalyzer()
    report = report_builder.generate_risk_report(analyzer)
    text = report_builder.generate_text_report(report)

    assert "REPORT TYPE: RISK" in text
    assert "Error Statistics:" in text
    assert "Total Analyzed: 0" in text


# --- Export to JSON tests ---

def test_export_to_json_client_report(report_builder, tmp_path):
    """Test exporting client report to JSON."""
    report = report_builder.generate_client_report("CL001")
    filepath = tmp_path / "client_report.json"

    result = report_builder.export_to_json(report, str(filepath))

    assert result == str(filepath)
    assert filepath.exists()

    import json

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["report_type"] == "client"
    assert data["client_id"] == "CL001"
    assert data["full_name"] == "Ivan Petrov"


def test_export_to_json_bank_report(report_builder, tmp_path):
    """Test exporting bank report to JSON."""
    report = report_builder.generate_bank_report()
    filepath = tmp_path / "bank_report.json"

    report_builder.export_to_json(report, str(filepath))

    assert filepath.exists()

    import json

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["report_type"] == "bank"
    assert data["bank_name"] == "Test Bank"


def test_export_to_json_creates_directory(report_builder, tmp_path):
    """Test that export_to_json creates directories if needed."""
    report = report_builder.generate_bank_report()
    filepath = tmp_path / "subdir" / "report.json"

    result = report_builder.export_to_json(report, str(filepath))

    assert result == str(filepath)
    assert filepath.exists()


# --- Export to CSV tests ---

def test_export_to_csv_client_report(report_builder, tmp_path):
    """Test exporting client report to CSV."""
    report = report_builder.generate_client_report("CL001")
    filepath = tmp_path / "client_report.csv"

    result = report_builder.export_to_csv(report, str(filepath))

    assert result == str(filepath)
    assert filepath.exists()

    import csv

    with open(filepath, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = [r for r in reader if r]  # filter out empty rows

    assert rows[0] == ["Field", "Value"]
    # Find client_id row
    client_id_row = [r for r in rows if r[0] == "client_id"]
    assert len(client_id_row) == 1
    assert client_id_row[0][1] == "CL001"


def test_export_to_csv_bank_report(report_builder, tmp_path):
    """Test exporting bank report to CSV."""
    report = report_builder.generate_bank_report()
    filepath = tmp_path / "bank_report.csv"

    report_builder.export_to_csv(report, str(filepath))

    assert filepath.exists()

    import csv

    with open(filepath, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = [r for r in reader if r]  # filter out empty rows

    assert rows[0] == ["Field", "Value"]
    # Check bank_name row
    bank_name_row = [r for r in rows if r[0] == "bank_name"]
    assert len(bank_name_row) == 1
    assert bank_name_row[0][1] == "Test Bank"


def test_export_to_csv_risk_report(report_builder, tmp_path):
    """Test exporting risk report to CSV."""
    analyzer = RiskAnalyzer()
    report = report_builder.generate_risk_report(analyzer)
    filepath = tmp_path / "risk_report.csv"

    report_builder.export_to_csv(report, str(filepath))

    assert filepath.exists()

    import csv

    with open(filepath, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    assert rows[0] == ["Field", "Value"]


# --- Chart creation tests ---

def test_create_pie_chart(report_builder):
    """Test creating a pie chart."""
    data = {"active": 3, "frozen": 1, "closed": 0}
    fig = report_builder.create_pie_chart(data, title="Account Status")

    assert fig is not None
    assert "Account Status" in report_builder._figures


def test_create_bar_chart(report_builder):
    """Test creating a bar chart."""
    data = {"RUB": 2, "USD": 1, "EUR": 1}
    fig = report_builder.create_bar_chart(data, title="Currency Distribution")

    assert fig is not None
    assert "Currency Distribution" in report_builder._figures


def test_create_balance_history_chart(report_builder):
    """Test creating a balance history chart."""
    balances = [
        Decimal("1000.00"),
        Decimal("1500.00"),
        Decimal("1200.00"),
        Decimal("2000.00"),
    ]
    fig = report_builder.create_balance_history_chart(balances, title="Balance History")

    assert fig is not None
    assert "Balance History" in report_builder._figures


def test_create_balance_history_chart_with_dates(report_builder):
    """Test creating a balance history chart with dates."""
    balances = [Decimal("1000.00"), Decimal("1500.00"), Decimal("2000.00")]
    dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
    fig = report_builder.create_balance_history_chart(
        balances, dates=dates, title="Balance History with Dates"
    )

    assert fig is not None
    assert "Balance History with Dates" in report_builder._figures


# --- Save charts tests ---

def test_save_charts(report_builder, tmp_path):
    """Test saving charts to directory."""
    report_builder.create_pie_chart({"active": 3, "frozen": 1}, title="Account Status")
    report_builder.create_bar_chart({"RUB": 2, "USD": 1}, title="Currency Distribution")

    saved = report_builder.save_charts(str(tmp_path))

    assert len(saved) == 2
    for path in saved:
        assert path.endswith(".png")
        import os

        assert os.path.exists(path)


def test_save_charts_creates_directory(report_builder, tmp_path):
    """Test that save_charts creates the directory if it doesn't exist."""
    report_builder.create_pie_chart({"active": 3}, title="Test Chart")
    subdir = tmp_path / "charts"
    assert not subdir.exists()

    saved = report_builder.save_charts(str(subdir))

    assert subdir.exists()
    assert len(saved) == 1


def test_save_charts_clears_figures(report_builder, tmp_path):
    """Test that save_charts clears internal figures after saving."""
    report_builder.create_pie_chart({"active": 3}, title="Test Chart")
    assert len(report_builder._figures) == 1

    report_builder.save_charts(str(tmp_path))

    assert len(report_builder._figures) == 0


# --- Properties tests ---

def test_reports_property(report_builder):
    """Test reports property."""
    assert report_builder.reports == {}

    report_builder.generate_client_report("CL001")
    report_builder.generate_bank_report()

    assert "client_CL001" in report_builder.reports
    assert "bank" in report_builder.reports


def test_charts_property(report_builder, tmp_path):
    """Test charts property."""
    assert report_builder.charts == {}

    report_builder.create_pie_chart({"active": 3}, title="Test Chart")
    report_builder.save_charts(str(tmp_path))

    assert "Test Chart" in report_builder.charts


def test_repr(report_builder):
    """Test __repr__ method."""
    r = repr(report_builder)
    assert "ReportBuilder" in r
    assert "Test Bank" in r