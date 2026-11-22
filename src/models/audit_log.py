import json
import os
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from ..exceptions import InvalidOperationError

# ======================================
# Day 5: Audit Log
# ======================================

class SeverityLevel(Enum):
    """Audit log severity levels.

    Levels, in order of increasing criticality:
    INFORMATION < WARNING < ERROR < CRITICAL

    This allows for not only collecting log entries based on a specific destination,
    but also filtering them by "level X and above."
    """

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        """Numerical rank of the level (a higher value indicates greater criticality).

        Determined by the order of the enumeration definitions:
        INFORMATION=1, WARNING=2, ERROR=3, CRITICAL=4.
        """
        return list(SeverityLevel).index(self) + 1

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, SeverityLevel):
            return NotImplemented
        return self.rank >= other.rank

    def __le__(self, other: object) -> bool:
        if not isinstance(other, SeverityLevel):
            return NotImplemented
        return self.rank <= other.rank

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, SeverityLevel):
            return NotImplemented
        return self.rank > other.rank

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SeverityLevel):
            return NotImplemented
        return self.rank < other.rank


class AuditLogEntry:
    """A single audit log entry."""

    def __init__(
        self,
        severity: SeverityLevel,
        message: str,
        source: str | None = None,
        details: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
        entry_id: str | None = None,
    ) -> None:
        if not isinstance(severity, SeverityLevel):
            raise InvalidOperationError(
                "Severity must be a SeverityLevel enum value."
            )
        if not message or not message.strip():
            raise InvalidOperationError("Log message cannot be empty.")

        self._id = entry_id or str(uuid4())
        self._severity = severity
        self._message = message.strip()
        self._source = source.strip() if source else None
        self._details = dict(details) if details else None
        self._timestamp = timestamp or datetime.now(UTC)

    @property
    def id(self) -> str:
        """Unique record identifier."""
        return self._id

    @property
    def severity(self) -> SeverityLevel:
        """Importance level of the entry."""
        return self._severity

    @property
    def message(self) -> str:
        """Message text."""
        return self._message

    @property
    def source(self) -> str | None:
        """Event source (e.g., ``transaction``, ``account``)."""
        return self._source

    @property
    def details(self) -> dict[str, Any] | None:
        """Additional structured data (copy)."""
        return dict(self._details) if self._details else None

    @property
    def timestamp(self) -> datetime:
        """Time of record creation."""
        return self._timestamp

    def to_dict(self) -> dict[str, Any]:
        """Convert the record into a dictionary for serialization."""
        return {
            "id": self._id,
            "severity": self._severity.value,
            "message": self._message,
            "source": self._source,
            "details": self._details,
            "timestamp": self._timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditLogEntry":
        """Restore an entry from a dictionary (the opposite of :meth:`to_dict`)."""
        severity = SeverityLevel(data["severity"])
        timestamp = datetime.fromisoformat(data["timestamp"])
        return cls(
            severity=severity,
            message=data["message"],
            source=data.get("source"),
            details=data.get("details"),
            timestamp=timestamp,
            entry_id=data.get("id"),
        )

    def __repr__(self) -> str:
        return (
            f"AuditLogEntry(id={self._id[:8]}..., "
            f"severity={self._severity.value}, message={self._message!r})"
        )

    def __str__(self) -> str:
        return (
            f"[{self._timestamp.isoformat()}] "
            f"{self._severity.value.upper()}: {self._message}"
        )


class AuditLog:
    """The audit log is maintained both in memory and in a file.

    Features:
    - Entries are stored in memory (as a list) and simultaneously written to a text file.
    - Each entry is stored in the file as an individual JSON string (JSONL),
    which allows for the safe appending of new events.
    - Filtering is supported based on severity, source,
    time period, and keywords within the source.
    """

    def __init__(
        self,
        log_file: str | None = None,
        max_entries: int = 10_000,
        auto_save: bool = True,
    ) -> None:
        if max_entries <= 0:
            raise InvalidOperationError("max_entries must be positive.")

        self._entries: list[AuditLogEntry] = []
        self._log_file = log_file
        self._max_entries = max_entries
        self._auto_save = auto_save

        self._prepare_log_file()

    def _prepare_log_file(self) -> None:
        """Create the log file and the parent directory, if they do not exist."""
        if self._log_file is None:
            return

        directory = os.path.dirname(os.path.abspath(self._log_file))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        if not os.path.exists(self._log_file):
            with open(self._log_file, "w", encoding="utf-8"):
                pass

    @property
    def entries(self) -> list[AuditLogEntry]:
        """Return a list of all entries in the order they were added."""
        return list(self._entries)

    @property
    def log_file(self) -> str | None:
        """Path to the log file (or ``None`` if no file is used)."""
        return self._log_file

    @property
    def size(self) -> int:
        """Number of records in memory."""
        return len(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    # Writing
    def add_entry(
        self,
        severity: SeverityLevel,
        message: str,
        source: str | None = None,
        details: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> str:
        """Add an entry to the log.

        The entry is added to memory and, if ``auto_save`` is enabled and a
        `log_file` is specified, it is also appended to the file.

        Args:
        severity: The severity level of the entry.
        message: The message text.
        source: The source of the event (e.g., ``"transaction"``).
        details: Additional structured data.
        timestamp: The time of the event. If not specified, the
        current time is used.

        Returns:
        The identifier of the created entry.
        """
        entry = AuditLogEntry(
            severity=severity,
            message=message,
            source=source,
            details=details,
            timestamp=timestamp,
        )
        self._entries.append(entry)
        self._trim_to_max()
        self._append_entry(entry)
        return entry.id

    def log(
        self,
        severity: SeverityLevel,
        message: str,
        source: str | None = None,
        details: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> str:
        """Alias for :meth:`add_entry`."""
        return self.add_entry(
            severity=severity,
            message=message,
            source=source,
            details=details,
            timestamp=timestamp,
        )

    def _trim_to_max(self) -> None:
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]

    def _append_entry(self, entry: AuditLogEntry) -> None:
        if self._auto_save and self._log_file:
            with open(self._log_file, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def save_to_file(self, path: str | None = None) -> None:
        """Save all records to a file (overwrites the file completely).

        Args:
        path: Path to the file. If not specified, the
        ``log_file`` provided in the constructor is used.
        """
        target = path or self._log_file
        if not target:
            raise InvalidOperationError("Путь к файлу журнала не указан.")
        directory = os.path.dirname(os.path.abspath(target))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            for entry in self._entries:
                handle.writelines(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def load_from_file(self, path: str | None = None) -> int:
        """Load entries from a file into memory (appends to the end).

        Corrupted lines are skipped, so the loading process is not interrupted
        by a damaged entry.

        Args:
        path: Path to the file. If not specified, the ``log_file``
        provided to the constructor is used.

        Returns:
        The number of successfully loaded entries.
        """
        target = path or self._log_file
        if not target or not os.path.exists(target):
            return 0

        loaded = 0
        with open(target, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    self._entries.append(AuditLogEntry.from_dict(data))
                    loaded += 1
                except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                    continue

        self._trim_to_max()
        return loaded

    # Filtering
    def filter_entries(
        self,
        severity: SeverityLevel | None = None,
        min_severity: SeverityLevel | None = None,
        source: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        contains: str | None = None,
    ) -> list[AuditLogEntry]:
        """Filter records based on various criteria.

        All provided filters are applied simultaneously (using AND logic).
        Records are returned in the order they were added (oldest first).

        Args:
        severity: Exact match for the severity level.
        min_severity: Include records with a severity level 
                      greater than or equal to the specified value.
        source: Exact match for the event source.
        start: Start of the time period (inclusive).
        end: End of the time period (inclusive).
        contains: A substring to search for within the message and source
        (case-insensitive search).

        Returns:
        The filtered copy of the records.
        """
        result = list(self._entries)

        if severity is not None:
            result = [e for e in result if e.severity == severity]

        if min_severity is not None:
            result = [e for e in result if e.severity >= min_severity]

        if source is not None:
            result = [e for e in result if e.source == source]

        if start is not None:
            result = [e for e in result if e.timestamp >= start]

        if end is not None:
            result = [e for e in result if e.timestamp <= end]

        if contains is not None:
            needle = contains.lower()
            result = [
                e
                for e in result
                if needle in e.message.lower()
                or (e.source is not None and needle in e.source.lower())
            ]

        return result

    def clear(self) -> int:
        """Clear all records from memory.

        Returns:
        The number of deleted records.
        """
        removed = len(self._entries)
        self._entries.clear()
        return removed

    def __repr__(self) -> str:
        return (
            f"AuditLog(entries={len(self._entries)}, "
            f"log_file={self._log_file!r})"
        )


__all__ = ["AuditLog", "AuditLogEntry", "SeverityLevel"]

