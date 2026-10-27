# 1. Abstract account
class AbstractAccount(ABC):

    def __init__(self, owner, balance=0, account_number=None):
        if not isinstance(owner, str) or not owner.strip():
            raise InvalidOperationError("Owner name cannot be empty.")

        self._owner = owner.strip()
        self._balance = self._validate_amount(balance)
        self._account_number = (
            str(account_number).strip()
            if account_number is not None
            else uuid4().hex[:8].upper()
        )

        if not self._account_number:
            raise InvalidOperationError("Account number cannot be empty.")

        self._status = AccountStatus.ACTIVE

    @staticmethod
    def _validate_amount(amount):
        """Convert an amount to Decimal and validate it."""
        if isinstance(amount, bool):
            raise InvalidOperationError("Amount must be a number.")

        try:
            value = Decimal(str(amount))
        except (InvalidOperation, ValueError, TypeError):
            raise InvalidOperationError("Amount must be a valid number.")

        if not value.is_finite():
            raise InvalidOperationError("Amount must be finite.")

        if value < 0:
            raise InvalidOperationError("Amount cannot be negative.")

        return value

    @abstractmethod
    def deposit(self, amount):
        pass

    @abstractmethod
    def withdraw(self, amount):
        pass

    @abstractmethod
    def get_account_info(self):
        pass