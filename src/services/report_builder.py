import csv
import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ..exceptions import InvalidOperationError
from ..models.bank import Bank
from ..services.risk_analyzer import RiskAnalyzer, RiskLevel

# ======================================
# Day 7: Reporting and Data Visualization System
# ======================================

class ReportType(Enum):
    """Types of reports that can be generated."""

    CLIENT = "client"
    BANK = "bank"
    RISK = "risk"


class ChartType(Enum):
    """Types of charts that can be created."""

    PIE = "pie"
    BAR = "bar"
    BALANCE_HISTORY = "balance_history"


class ReportBuilder:
    """Builds text, JSON, and CSV reports and creates charts for the banking system.

    Supports three report types:
        - Client reports: personal info, accounts, balances, security status
        - Bank reports: aggregate statistics, distributions, client rankings
        - Risk reports: risk analysis, suspicious transactions, blocked transactions

    Supports three chart types:
        - Pie charts: distribution visualisations (account status, currency, etc.)
        - Bar charts: comparative visualisations (top clients, risk distribution)
        - Balance history charts: time-series balance evolution
    """

    def __init__(self, bank: Bank) -> None:
        """Initialize the report builder with a bank instance.

        Args:
            bank: The Bank instance to generate reports from.
        """
        self._bank = bank
        self._reports: dict[str, dict[str, Any]] = {}
        self._figures: dict[str, Any] = {}  # chart title -> matplotlib Figure
        self._chart_paths: dict[str, str] = {}  # chart title -> saved file path

    # ==================== Report Generation ====================

    def generate_client_report(self, client_id: str) -> dict[str, Any]:
        """Generate a comprehensive report for a specific client.

        Args:
            client_id: Unique client identifier.

        Returns:
            A dictionary containing the client report data.

        Raises:
            InvalidOperationError: If the client is not found.
        """
        client = self._bank.get_client(client_id)

        accounts_info: list[dict[str, Any]] = []
        total_balance = Decimal("0.00")

        for account_number in client.account_numbers:
            account = self._bank.get_account(account_number)
            info = account.get_account_info()
            accounts_info.append(info)
            if hasattr(account, "total_balance"):
                total_balance += account.total_balance
            else:
                total_balance += account.balance

        report: dict[str, Any] = {
            "report_type": ReportType.CLIENT.value,
            "client_id": client.client_id,
            "full_name": client.full_name,
            "contact_details": client.contact_details,
            "age": client.age,
            "status": client.status.value,
            "is_locked": client.is_locked,
            "is_suspicious": client.is_suspicious,
            "failed_login_attempts": client.failed_login_attempts,
            "suspicious_activity": client.suspicious_activity,
            "account_count": len(accounts_info),
            "accounts": accounts_info,
            "total_balance": str(total_balance),
            "generated_at": datetime.now(UTC).isoformat(),
        }

        self._reports[f"client_{client_id}"] = report
        return report

    def generate_bank_report(self) -> dict[str, Any]:
        """Generate a comprehensive bank-wide report.

        Returns:
            A dictionary containing the bank report data.
        """
        clients = self._bank.clients
        accounts = self._bank.accounts

        total_balance = self._bank.get_total_balance()
        client_ranking = self._bank.get_clients_ranking()

        status_distribution: dict[str, int] = {}
        for account in accounts:
            status = account.status.value
            status_distribution[status] = status_distribution.get(status, 0) + 1

        type_distribution: dict[str, int] = {}
        for account in accounts:
            acc_type = type(account).__name__
            type_distribution[acc_type] = type_distribution.get(acc_type, 0) + 1

        currency_distribution: dict[str, int] = {}
        for account in accounts:
            currency = account.currency
            currency_distribution[currency] = currency_distribution.get(currency, 0) + 1

        client_status_dist: dict[str, int] = {}
        for client in clients:
            status = client.status.value
            client_status_dist[status] = client_status_dist.get(status, 0) + 1

        locked_clients = sum(1 for c in clients if c.is_locked)
        suspicious_clients = sum(1 for c in clients if c.is_suspicious)

        report: dict[str, Any] = {
            "report_type": ReportType.BANK.value,
            "bank_name": self._bank.name,
            "client_count": len(clients),
            "account_count": len(accounts),
            "total_balance": str(total_balance),
            "client_status_distribution": client_status_dist,
            "account_status_distribution": status_distribution,
            "account_type_distribution": type_distribution,
            "currency_distribution": currency_distribution,
            "locked_clients": locked_clients,
            "suspicious_clients": suspicious_clients,
            "top_clients": [
                {
                    "client_id": client.client_id,
                    "full_name": client.full_name,
                    "total_balance": str(balance),
                }
                for client, balance in client_ranking[:10]
            ],
            "generated_at": datetime.now(UTC).isoformat(),
        }

        self._reports["bank"] = report
        return report

    def generate_risk_report(self, risk_analyzer: RiskAnalyzer) -> dict[str, Any]:
        """Generate a comprehensive risk analysis report.

        Args:
            risk_analyzer: The RiskAnalyzer instance to source risk data from.

        Returns:
            A dictionary containing the risk report data.
        """
        stats = risk_analyzer.get_error_statistics()
        profiles = risk_analyzer.get_all_risk_profiles()
        suspicious = risk_analyzer.get_suspicious_transactions()
        blocked = risk_analyzer.get_blocked_transactions()

        report: dict[str, Any] = {
            "report_type": ReportType.RISK.value,
            "error_statistics": stats,
            "client_risk_profiles": {
                client_id: {
                    **profile,
                    "overall_risk_level": profile["overall_risk_level"].value,
                }
                for client_id, profile in profiles.items()
            },
            "suspicious_transactions_count": len(suspicious),
            "blocked_transactions_count": len(blocked),
            "blocked_transaction_ids": [t.id for t in blocked],
            "generated_at": datetime.now(UTC).isoformat(),
        }

        self._reports["risk"] = report
        return report

    def generate_report(self, report_type: ReportType, **kwargs) -> dict[str, Any]:
        """Generate a report of the specified type.

        Args:
            report_type: Type of report to generate.
            **kwargs: Additional arguments depending on report type:
                - For CLIENT: client_id (str)
                - For RISK: risk_analyzer (RiskAnalyzer)

        Returns:
            The generated report as a dictionary.

        Raises:
            InvalidOperationError: If required arguments are missing or type is unknown.
        """
        if report_type == ReportType.CLIENT:
            client_id = kwargs.get("client_id")
            if not client_id:
                raise InvalidOperationError("client_id is required for client reports.")
            return self.generate_client_report(client_id)
        elif report_type == ReportType.BANK:
            return self.generate_bank_report()
        elif report_type == ReportType.RISK:
            risk_analyzer = kwargs.get("risk_analyzer")
            if risk_analyzer is None:
                raise InvalidOperationError(
                    "risk_analyzer is required for risk reports."
                )
            return self.generate_risk_report(risk_analyzer)
        else:
            raise InvalidOperationError(f"Unknown report type: {report_type}")

    # ==================== Text Report ====================

    def generate_text_report(self, report_data: dict[str, Any]) -> str:
        """Generate a human-readable text representation of a report.

        Args:
            report_data: The report data dictionary (as returned by generate_* methods).

        Returns:
            A formatted text string representing the report.
        """
        lines: list[str] = []
        report_type = report_data.get("report_type", "unknown")

        lines.append("=" * 60)
        lines.append(f"REPORT TYPE: {report_type.upper()}")
        lines.append(f"Generated at: {report_data.get('generated_at', 'N/A')}")
        lines.append("=" * 60)
        lines.append("")

        if report_type == ReportType.CLIENT.value:
            lines.append(f"Client ID: {report_data.get('client_id')}")
            lines.append(f"Full Name: {report_data.get('full_name')}")
            lines.append(f"Contact: {report_data.get('contact_details')}")
            lines.append(f"Age: {report_data.get('age')}")
            lines.append(f"Status: {report_data.get('status')}")
            lines.append(f"Is Locked: {report_data.get('is_locked')}")
            lines.append(f"Is Suspicious: {report_data.get('is_suspicious')}")
            lines.append(
                f"Failed Login Attempts: {report_data.get('failed_login_attempts')}"
            )
            lines.append(f"Suspicious Activity: {report_data.get('suspicious_activity')}")
            lines.append(f"Account Count: {report_data.get('account_count')}")
            lines.append(f"Total Balance: {report_data.get('total_balance')}")
            lines.append("")
            lines.append("Accounts:")
            for acc in report_data.get("accounts", []):
                lines.append(
                    f"  - {acc.get('account_type')} ({acc.get('account_number')}): "
                    f"{acc.get('balance')} {acc.get('currency')} [{acc.get('status')}]"
                )

        elif report_type == ReportType.BANK.value:
            lines.append(f"Bank Name: {report_data.get('bank_name')}")
            lines.append(f"Client Count: {report_data.get('client_count')}")
            lines.append(f"Account Count: {report_data.get('account_count')}")
            lines.append(f"Total Balance: {report_data.get('total_balance')}")
            lines.append("")
            lines.append("Client Status Distribution:")
            for status, count in report_data.get(
                "client_status_distribution", {}
            ).items():
                lines.append(f"  {status}: {count}")
            lines.append("")
            lines.append("Account Status Distribution:")
            for status, count in report_data.get(
                "account_status_distribution", {}
            ).items():
                lines.append(f"  {status}: {count}")
            lines.append("")
            lines.append("Account Type Distribution:")
            for acc_type, count in report_data.get(
                "account_type_distribution", {}
            ).items():
                lines.append(f"  {acc_type}: {count}")
            lines.append("")
            lines.append("Currency Distribution:")
            for currency, count in report_data.get(
                "currency_distribution", {}
            ).items():
                lines.append(f"  {currency}: {count}")
            lines.append("")
            lines.append(f"Locked Clients: {report_data.get('locked_clients')}")
            lines.append(f"Suspicious Clients: {report_data.get('suspicious_clients')}")
            lines.append("")
            lines.append("Top Clients by Balance:")
            for i, client in enumerate(report_data.get("top_clients", []), 1):
                lines.append(
                    f"  {i}. {client.get('full_name')} ({client.get('client_id')}): "
                    f"{client.get('total_balance')}"
                )

        elif report_type == ReportType.RISK.value:
            stats = report_data.get("error_statistics", {})
            lines.append("Error Statistics:")
            lines.append(f"  Total Analyzed: {stats.get('total_analyzed', 0)}")
            lines.append(f"  High Risk: {stats.get('high_risk', 0)}")
            lines.append(f"  Medium Risk: {stats.get('medium_risk', 0)}")
            lines.append(f"  Low Risk: {stats.get('low_risk', 0)}")
            lines.append(f"  Blocked Count: {stats.get('blocked_count', 0)}")
            lines.append("")
            lines.append(
                f"Suspicious Transactions: {report_data.get('suspicious_transactions_count')}"
            )
            lines.append(
                f"Blocked Transactions: {report_data.get('blocked_transactions_count')}"
            )
            lines.append("")
            lines.append("Client Risk Profiles:")
            for client_id, profile in report_data.get(
                "client_risk_profiles", {}
            ).items():
                lines.append(
                    f"  {client_id}: {profile.get('overall_risk_level')} "
                    f"({profile.get('total_transactions')} transactions, "
                    f"avg score: {profile.get('average_risk_score')})"
                )

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

# ==================== Export Methods ====================

    def export_to_json(self, report_data: dict[str, Any], filepath: str) -> str:
        """Export a report to a JSON file.

        Args:
            report_data: The report data dictionary.
            filepath: Path to the output JSON file.

        Returns:
            The filepath of the saved file.
        """
        directory = os.path.dirname(os.path.abspath(filepath))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)

        return filepath

    def export_to_csv(self, report_data: dict[str, Any], filepath: str) -> str:
        """Export a report to a CSV file.

        Args:
            report_data: The report data dictionary.
            filepath: Path to the output CSV file.

        Returns:
            The filepath of the saved file.
        """
        directory = os.path.dirname(os.path.abspath(filepath))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            report_type = report_data.get("report_type", "unknown")

            if report_type == ReportType.CLIENT.value:
                writer.writerow(["Field", "Value"])
                writer.writerow(["client_id", report_data.get("client_id", "")])
                writer.writerow(["full_name", report_data.get("full_name", "")])
                writer.writerow(
                    ["contact_details", report_data.get("contact_details", "")]
                )
                writer.writerow(["age", report_data.get("age", "")])
                writer.writerow(["status", report_data.get("status", "")])
                writer.writerow(["is_locked", report_data.get("is_locked", "")])
                writer.writerow(["is_suspicious", report_data.get("is_suspicious", "")])
                writer.writerow(
                    [
                        "failed_login_attempts",
                        report_data.get("failed_login_attempts", ""),
                    ]
                )
                writer.writerow(
                    ["account_count", report_data.get("account_count", "")]
                )
                writer.writerow(["total_balance", report_data.get("total_balance", "")])
                writer.writerow([])
                writer.writerow(
                    [
                        "Account Type",
                        "Account Number",
                        "Owner",
                        "Balance",
                        "Currency",
                        "Status",
                    ]
                )
                for acc in report_data.get("accounts", []):
                    writer.writerow(
                        [
                            acc.get("account_type", ""),
                            acc.get("account_number", ""),
                            acc.get("owner", ""),
                            acc.get("balance", ""),
                            acc.get("currency", ""),
                            acc.get("status", ""),
                        ]
                    )

            elif report_type == ReportType.BANK.value:
                writer.writerow(["Field", "Value"])
                writer.writerow(["bank_name", report_data.get("bank_name", "")])
                writer.writerow(["client_count", report_data.get("client_count", "")])
                writer.writerow(
                    ["account_count", report_data.get("account_count", "")]
                )
                writer.writerow(["total_balance", report_data.get("total_balance", "")])
                writer.writerow(["locked_clients", report_data.get("locked_clients", "")])
                writer.writerow(
                    ["suspicious_clients", report_data.get("suspicious_clients", "")]
                )
                writer.writerow([])
                writer.writerow(["Distribution Type", "Category", "Count"])
                for dist_name, dist_data in [
                    ("client_status", report_data.get("client_status_distribution", {})),
                    ("account_status", report_data.get("account_status_distribution", {})),
                    ("account_type", report_data.get("account_type_distribution", {})),
                    ("currency", report_data.get("currency_distribution", {})),
                ]:
                    for category, count in dist_data.items():
                        writer.writerow([dist_name, category, count])
                writer.writerow([])
                writer.writerow(["Rank", "Client ID", "Full Name", "Total Balance"])
                for i, client in enumerate(report_data.get("top_clients", []), 1):
                    writer.writerow(
                        [
                            i,
                            client.get("client_id", ""),
                            client.get("full_name", ""),
                            client.get("total_balance", ""),
                        ]
                    )

            elif report_type == ReportType.RISK.value:
                stats = report_data.get("error_statistics", {})
                writer.writerow(["Field", "Value"])
                writer.writerow(["total_analyzed", stats.get("total_analyzed", 0)])
                writer.writerow(["high_risk", stats.get("high_risk", 0)])
                writer.writerow(["medium_risk", stats.get("medium_risk", 0)])
                writer.writerow(["low_risk", stats.get("low_risk", 0)])
                writer.writerow(["blocked_count", stats.get("blocked_count", 0)])
                writer.writerow(
                    [
                        "suspicious_transactions_count",
                        report_data.get("suspicious_transactions_count", 0),
                    ]
                )
                writer.writerow(
                    [
                        "blocked_transactions_count",
                        report_data.get("blocked_transactions_count", 0),
                    ]
                )
                writer.writerow([])
                writer.writerow(
                    [
                        "Client ID",
                        "Overall Risk Level",
                        "Total Transactions",
                        "High Risk",
                        "Medium Risk",
                        "Low Risk",
                        "Avg Score",
                    ]
                )
                for client_id, profile in report_data.get(
                    "client_risk_profiles", {}
                ).items():
                    writer.writerow(
                        [
                            client_id,
                            profile.get("overall_risk_level", ""),
                            profile.get("total_transactions", 0),
                            profile.get("high_risk_count", 0),
                            profile.get("medium_risk_count", 0),
                            profile.get("low_risk_count", 0),
                            profile.get("average_risk_score", 0),
                        ]
                    )

        return filepath

    # ==================== Chart Creation ====================

    def create_pie_chart(
        self,
        data: dict[str, int | float],
        title: str = "Pie Chart",
    ) -> Any:
        """Create a pie chart and store it internally.

        Args:
            data: Dictionary of label -> value.
            title: Chart title (used as the internal key).

        Returns:
            The matplotlib Figure object.
        """
        labels = list(data.keys())
        values = list(data.values())

        fig, ax = plt.subplots()
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
        ax.set_title(title)
        ax.axis("equal")

        self._figures[title] = fig
        return fig

    def create_bar_chart(
        self,
        data: dict[str, int | float],
        title: str = "Bar Chart",
    ) -> Any:
        """Create a bar chart and store it internally.

        Args:
            data: Dictionary of label -> value.
            title: Chart title (used as the internal key).

        Returns:
            The matplotlib Figure object.
        """
        labels = list(data.keys())
        values = list(data.values())

        fig, ax = plt.subplots()
        ax.bar(labels, values)
        ax.set_title(title)
        ax.set_ylabel("Value")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        self._figures[title] = fig
        return fig

    def create_balance_history_chart(
        self,
        balances: list[Decimal | int | float],
        dates: list[str] | None = None,
        title: str = "Balance History",
    ) -> Any:
        """Create a balance history line chart and store it internally.

        Args:
            balances: List of balance values over time.
            dates: Optional list of date strings corresponding to balances.
            title: Chart title (used as the internal key).

        Returns:
            The matplotlib Figure object.
        """
        fig, ax = plt.subplots()

        x = dates if dates else list(range(len(balances)))
        ax.plot(x, [float(b) for b in balances], marker="o", linestyle="-", linewidth=2)
        ax.set_title(title)
        ax.set_ylabel("Balance")
        ax.grid(True, alpha=0.3)

        if dates:
            plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        self._figures[title] = fig
        return fig

    # ==================== Save Charts ====================

    def save_charts(self, directory: str = "charts") -> list[str]:
        """Save all generated charts to files in the specified directory.

        Args:
            directory: Directory to save chart images in.

        Returns:
            List of saved file paths.
        """
        if not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)

        saved_paths: list[str] = []
        for title, fig in self._figures.items():
            safe_title = "".join(
                c if c.isalnum() or c in (" ", "-", "_") else "_" for c in title
            )
            safe_title = safe_title.strip().replace(" ", "_")
            filepath = os.path.join(directory, f"{safe_title}.png")

            fig.savefig(filepath, dpi=150, bbox_inches="tight")
            plt.close(fig)
            self._chart_paths[title] = filepath
            saved_paths.append(filepath)

        self._figures.clear()
        return saved_paths

    # ==================== Properties ====================

    @property
    def reports(self) -> dict[str, dict[str, Any]]:
        """Return all generated reports."""
        return dict(self._reports)

    @property
    def charts(self) -> dict[str, str]:
        """Return all saved chart file paths."""
        return dict(self._chart_paths)

    def __repr__(self) -> str:
        return (
            f"ReportBuilder(bank={self._bank.name!r}, "
            f"reports={len(self._reports)}, charts={len(self._chart_paths)})"
        )
 