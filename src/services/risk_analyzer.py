from decimal import Decimal
from enum import Enum
from typing import Any

from ..exceptions import InvalidOperationError
from ..logging import security_logger
from ..models.transaction import Transaction, TransactionStatus, TransactionType
from .audit_log import AuditLog, SeverityLevel

# ======================================
# Day 5: Risk Analyzer
# ======================================

class RiskLevel(Enum):
    """Risk levels for transaction analysis.

    Levels, in order of increasing criticality:
    LOW < MEDIUM < HIGH
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        """Numerical rank of the level (a higher value indicates greater risk)."""
        return list(RiskLevel).index(self) + 1

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self.rank >= other.rank

    def __le__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self.rank <= other.rank

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self.rank > other.rank

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, RiskLevel):
            return NotImplemented
        return self.rank < other.rank


class _HistoryEntry:
    """Lightweight stand-in exposing ``sender``/``recipient``/``created_at``
    for risk analysis. Wraps entries stored in :attr:`_transaction_history`
    so frequency and new-recipient checks work without an explicit
    ``historical_transactions`` argument.
    """

    __slots__ = ("created_at", "recipient", "sender")

    def __init__(self, sender, recipient, created_at) -> None:
        self.sender = sender
        self.recipient = recipient
        self.created_at = created_at


class RiskAnalyzer:
    """Analyzes transactions for suspicious activity and assigns risk levels.

    Detection criteria:
    - Large amounts (>= 100,000)
    - Frequent transactions (many transactions from the same sender
      within a configurable time window)
    - Transfers to new/unknown accounts
    - Transactions made at night (22:00 - 06:00)

    Risk levels: *low, medium, high*.
    The bank blocks high-risk transactions.

    The analyzer integrates with :class:`AuditLog` for persistent
    logging of every analysis event.
    """

    # Thresholds
    LARGE_AMOUNT_THRESHOLD: Decimal = Decimal("100000.00")
    """Amount above which a transaction is considered large."""

    NIGHT_HOURS_START: int = 22  # 22:00
    """Start of the night interval (inclusive)."""

    NIGHT_HOURS_END: int = 6  # 06:00
    """End of the night interval (exclusive)."""

    FREQUENT_TRANSACTION_COUNT: int = 5
    """Number of transactions within the window that triggers the
    "frequent transactions" flag."""

    FREQUENT_TRANSACTION_WINDOW_MINUTES: int = 60
    """Time window (in minutes) for frequency analysis."""

    def __init__(self, audit_log: AuditLog | None = None) -> None:
        """Initialize the risk analyzer.

        Args:
            audit_log: Optional :class:`AuditLog` instance. If not provided,
                a new in-memory :class:`AuditLog` is created.
        """
        self._audit_log = audit_log if audit_log is not None else AuditLog()
        self._risk_profiles: dict[str, dict[str, Any]] = {}
        self._transaction_history: list[dict[str, Any]] = []
        self._blocked_transactions: list[Transaction] = []
        self._known_recipients: set[str] = set()

    # properties 
    @property
    def audit_log(self) -> AuditLog:
        """The audit log used for recording analysis events."""
        return self._audit_log

    @property
    def blocked_transactions(self) -> list[Transaction]:
        """Return a copy of the list of blocked (high-risk) transactions."""
        return list(self._blocked_transactions)

    @property
    def risk_profiles(self) -> dict[str, dict[str, Any]]:
        """Return a copy of all client risk profiles."""
        return dict(self._risk_profiles)

    # public API
    def register_known_recipient(self, account_number: str) -> None:
        """Register an account number as a known recipient.

        Transfers to registered recipients are not flagged as
        "transfer to new account".
        """
        self._known_recipients.add(account_number.strip())

    def analyze_transaction(
        self,
        transaction: Transaction,
        client_id: str | None = None,
        historical_transactions: list[Transaction] | None = None,
    ) -> RiskLevel:
        """Analyze a single transaction and determine its risk level.

        The analysis checks four criteria:
        1. Large amount
        2. Night-time transaction
        3. Transfer to a new/unknown account
        4. Frequent transactions from the same sender

        Args:
            transaction: The transaction to analyze.
            client_id: Optional client identifier for risk profiling.
            historical_transactions: Optional list of previously analyzed
                transactions used for frequency and new-account detection.

        Returns:
            The assigned :class:`RiskLevel`.

        Raises:
            InvalidOperationError: If ``transaction`` is ``None``.
        """
        if transaction is None:
            raise InvalidOperationError("Transaction cannot be None.")

        risk_score = 0
        reasons: list[str] = []

        # Use explicitly passed history when given; otherwise fall back to
        # the analyzer's own recorded history so repeated operations from the
        # same sender are detected even without an explicit argument.
        if historical_transactions is not None:
            history = list(historical_transactions)
        else:
            history = [
                _HistoryEntry(
                    sender=e["sender"],
                    recipient=e["recipient"],
                    created_at=e["timestamp"],
                )
                for e in self._transaction_history
            ]

        # 1. Large amount
        if transaction.amount >= self.LARGE_AMOUNT_THRESHOLD:
            risk_score += 3
            reasons.append(
                f"Large amount: {transaction.amount} {transaction.currency}"
            )

        # 2. Night transaction
        hour = transaction.created_at.hour
        if hour >= self.NIGHT_HOURS_START or hour < self.NIGHT_HOURS_END:
            risk_score += 2
            reasons.append(f"Night transaction at {hour}:00")

        # 3. Transfer to new account
        if transaction.type in (
            TransactionType.TRANSFER,
            TransactionType.PAYMENT,
        ) and transaction.recipient:
            is_new_recipient = (
                transaction.recipient not in self._known_recipients
                and transaction.recipient
                not in {t.recipient for t in history if t.recipient}
            )
            if is_new_recipient:
                risk_score += 2
                reasons.append(
                    f"Transfer to new account: {transaction.recipient}"
                )

        # 4. Frequent transactions
        if history:
            window_seconds = (
                self.FREQUENT_TRANSACTION_WINDOW_MINUTES * 60
            )
            recent_count = sum(
                1
                for t in history
                if t.sender == transaction.sender
                and abs(
                    (transaction.created_at - t.created_at).total_seconds()
                )
                <= window_seconds
            )
            if recent_count >= self.FREQUENT_TRANSACTION_COUNT:
                risk_score += 2
                reasons.append(
                    f"Frequent transactions: {recent_count} in "
                    f"{self.FREQUENT_TRANSACTION_WINDOW_MINUTES} minutes"
                )

        # Determine risk level
        if risk_score >= 5:
            level = RiskLevel.HIGH
        elif risk_score >= 3:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        # Log to audit log
        self._audit_log.add_entry(
            severity=(
                SeverityLevel.CRITICAL
                if level == RiskLevel.HIGH
                else SeverityLevel.WARNING
                if level == RiskLevel.MEDIUM
                else SeverityLevel.INFO
            ),
            message=(
                f"Risk analysis for transaction {transaction.id}: {level.value}"
            ),
            source="risk_analyzer",
            details={
                "transaction_id": transaction.id,
                "risk_level": level.value,
                "risk_score": risk_score,
                "reasons": list(reasons),
                "client_id": client_id,
                "amount": str(transaction.amount),
                "currency": transaction.currency,
                "sender": transaction.sender,
                "recipient": transaction.recipient,
            },
            timestamp=transaction.created_at,
        )

        # Store in history
        self._transaction_history.append(
            {
                "transaction_id": transaction.id,
                "risk_level": level,
                "risk_score": risk_score,
                "reasons": list(reasons),
                "timestamp": transaction.created_at,
                "client_id": client_id,
                "sender": transaction.sender,
                "recipient": transaction.recipient,
                "amount": str(transaction.amount),
                "currency": transaction.currency,
                "type": transaction.type.value,
            }
        )

        # Update client risk profile
        if client_id:
            self._update_risk_profile(client_id, level, risk_score, reasons)

        # Block high-risk transactions. A transaction that is already
        # finalized (executed earlier) must not be touched: its status and
        # the moved funds are immutable, and it must not be reported as
        # blocked after the fact.
        if level == RiskLevel.HIGH and not transaction.is_finalized():
            self._blocked_transactions.append(transaction)
            transaction._set_status(
                TransactionStatus.FAILED,
                failure_reason=(
                    f"High risk transaction blocked: {', '.join(reasons)}"
                    if reasons
                    else "High risk transaction blocked"
                ),
            )
            security_logger.warning(
                f"HIGH RISK: Transaction {transaction.id} blocked. "
                f"Reasons: {', '.join(reasons)}"
            )

        return level

    def is_blocked(self, transaction_id: str) -> bool:
        """Return ``True`` if a transaction with the given ID is blocked."""
        return any(t.id == transaction_id for t in self._blocked_transactions)

    def get_blocked_transactions(self) -> list[Transaction]:
        """Return a copy of the blocked transactions list."""
        return list(self._blocked_transactions)

    def get_risk_profile(self, client_id: str) -> dict[str, Any] | None:
        """Return the risk profile for a client, or ``None`` if not found."""
        return self._risk_profiles.get(client_id)

    def get_all_risk_profiles(self) -> dict[str, dict[str, Any]]:
        """Return all client risk profiles."""
        return dict(self._risk_profiles)

    def get_suspicious_transactions(
        self, min_level: RiskLevel = RiskLevel.MEDIUM
    ) -> list[dict[str, Any]]:
        """Return transactions flagged as suspicious (risk >= *min_level*).

        Args:
            min_level: Minimum risk level to include (default: MEDIUM).

        Returns:
            List of transaction analysis records.
        """
        return [
            entry
            for entry in self._transaction_history
            if entry["risk_level"].rank >= min_level.rank
        ]

    def get_error_statistics(self) -> dict[str, Any]:
        """Return statistics about all analyzed transactions.

        Returns:
            Dictionary with counts per risk level, blocked count and
            percentages.
        """
        total = len(self._transaction_history)
        if total == 0:
            return {
                "total_analyzed": 0,
                "high_risk": 0,
                "medium_risk": 0,
                "low_risk": 0,
                "blocked_count": len(self._blocked_transactions),
            }

        high = sum(
            1
            for e in self._transaction_history
            if e["risk_level"] == RiskLevel.HIGH
        )
        medium = sum(
            1
            for e in self._transaction_history
            if e["risk_level"] == RiskLevel.MEDIUM
        )
        low = sum(
            1
            for e in self._transaction_history
            if e["risk_level"] == RiskLevel.LOW
        )

        return {
            "total_analyzed": total,
            "high_risk": high,
            "medium_risk": medium,
            "low_risk": low,
            "blocked_count": len(self._blocked_transactions),
            "high_risk_percentage": round((high / total) * 100, 2),
            "medium_risk_percentage": round((medium / total) * 100, 2),
        }

    def generate_report(self) -> dict[str, Any]:
        """Generate a comprehensive audit report.

        The report contains:
        - Suspicious transactions (medium and high risk)
        - Client risk profiles
        - Error statistics
        - Blocked transaction IDs

        Returns:
            Dictionary with report sections.
        """
        return {
            "suspicious_transactions": self.get_suspicious_transactions(),
            "client_risk_profiles": self.get_all_risk_profiles(),
            "error_statistics": self.get_error_statistics(),
            "blocked_transaction_ids": [t.id for t in self._blocked_transactions],
        }

    # internal helpers
    def _update_risk_profile(
        self,
        client_id: str,
        level: RiskLevel,
        score: int,
        reasons: list[str],
    ) -> None:
        """Update the risk profile for a client based on a new analysis."""
        if client_id not in self._risk_profiles:
            self._risk_profiles[client_id] = {
                "client_id": client_id,
                "overall_risk_level": RiskLevel.LOW,
                "total_transactions": 0,
                "high_risk_count": 0,
                "medium_risk_count": 0,
                "low_risk_count": 0,
                "total_risk_score": 0,
                "average_risk_score": 0.0,
                "reasons": [],
            }

        profile = self._risk_profiles[client_id]
        profile["total_transactions"] += 1
        profile["total_risk_score"] += score
        profile["average_risk_score"] = round(
            profile["total_risk_score"] / profile["total_transactions"], 2
        )

        if level == RiskLevel.HIGH:
            profile["high_risk_count"] += 1
        elif level == RiskLevel.MEDIUM:
            profile["medium_risk_count"] += 1
        else:
            profile["low_risk_count"] += 1

        # Escalate overall risk level (never decrease)
        level_rank = {RiskLevel.LOW: 1, RiskLevel.MEDIUM: 2, RiskLevel.HIGH: 3}
        current_rank = level_rank[profile["overall_risk_level"]]
        new_rank = level_rank[level]
        if new_rank > current_rank:
            profile["overall_risk_level"] = level

        # Accumulate unique reasons
        for reason in reasons:
            if reason not in profile["reasons"]:
                profile["reasons"].append(reason)

    # dunder methods
    def __repr__(self) -> str:
        return (
            f"RiskAnalyzer(analyzed={len(self._transaction_history)}, "
            f"blocked={len(self._blocked_transactions)}, "
            f"profiles={len(self._risk_profiles)})"
        )

    def __str__(self) -> str:
        stats = self.get_error_statistics()
        return (
            f"RiskAnalyzer: {stats['total_analyzed']} transactions analyzed, "
            f"{stats['high_risk']} high-risk, {stats['medium_risk']} medium-risk, "
            f"{stats['low_risk']} low-risk, {stats['blocked_count']} blocked"
        )


__all__ = ["RiskAnalyzer", "RiskLevel"]