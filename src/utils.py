from decimal import Decimal
from uuid import uuid4

from src.exceptions import InvalidOperationError

ALLOWED_CURRENCIES = frozenset({"RUB", "USD", "EUR", "KZT", "CNY"})


def _validate_amount(amount) -> Decimal:
    """Convert an amount to Decimal and validate it."""
    if isinstance(amount, bool):
        raise InvalidOperationError("Amount must be a number.")

    try:
        value = Decimal(str(amount))
    except (ValueError, TypeError, ArithmeticError):
        raise InvalidOperationError("Amount must be a valid number.")

    if not value.is_finite():
        raise InvalidOperationError("Amount must be finite.")

    if value < 0:
        raise InvalidOperationError("Amount cannot be negative.")

    return value

def generate_account_number():
    return uuid4().hex[:8].upper()

def build_account_table(rows):
    label_width = 20   
    value_width = 20
    
    sep = "-" * (label_width + value_width + 3)  # +3 на " | "
    
    lines = [sep]
    for label, value in rows[:-1]:
        lines.append(f"{label:<{label_width}} | {value:>{value_width}}")
    lines.append(sep)
    lines.append(f"{rows[-1][0]:<{label_width}} | {rows[-1][1]:>{value_width}}")
    return "\n".join(lines)+"\n"