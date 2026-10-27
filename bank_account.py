
# 2. Bank account

class BankAccount(AbstractAccount):

    ALLOWED_CURRENCIES = {"RUB", "USD", "EUR", "KZT", "CNY"}

    def __init__(
        self,
        owner,
        balance=0,
        account_number=None,
        currency="RUB",
        status=AccountStatus.ACTIVE
    ):
        super().__init__(owner, balance, account_number)

        if not isinstance(currency, str):
            raise InvalidOperationError("Currency must be a string.")

        currency = currency.upper()

        if currency not in self.ALLOWED_CURRENCIES:
            raise InvalidOperationError(
                f"Unsupported currency: {currency}. "
                f"Allowed currencies: {', '.join(sorted(self.ALLOWED_CURRENCIES))}"
            )

        if not isinstance(status, AccountStatus):
            raise InvalidOperationError("Invalid account status.")

        self.currency = currency
        self._status = status


    @property
    def owner(self):
        return self._owner

    @property
    def account_number(self):
        return self._account_number

    @property
    def balance(self):
        return self._balance

    @property
    def status(self):
        return self._status

    def _check_status(self):
        """Ensure that the account can perform operations."""
        if self._status == AccountStatus.FROZEN:
            raise AccountFrozenError("The account is frozen.")

        if self._status == AccountStatus.CLOSED:
            raise AccountClosedError("The account is closed.")

    def deposit(self, amount):
        self._check_status()
        amount = self._validate_amount(amount)

        if amount == 0:
            raise InvalidOperationError("Deposit amount must be greater than zero.")

        self._balance += amount
        return self._balance

    def withdraw(self, amount):
        self._check_status()
        amount = self._validate_amount(amount)

        if amount == 0:
            raise InvalidOperationError("Withdrawal amount must be greater than zero.")

        if amount > self._balance:
            raise InsufficientFundsError(
                "Insufficient funds to complete the withdrawal."
            )

        self._balance -= amount
        return self._balance

    def freeze(self):
        if self._status == AccountStatus.CLOSED:
            raise AccountClosedError("A closed account cannot be frozen.")

        self._status = AccountStatus.FROZEN

    def activate(self):
        if self._status == AccountStatus.CLOSED:
            raise AccountClosedError("A closed account cannot be activated.")

        self._status = AccountStatus.ACTIVE

    def close(self):
        if self._status == AccountStatus.CLOSED:
            raise AccountClosedError("The account is already closed.")

        self._status = AccountStatus.CLOSED

    def get_account_info(self):
        return {
            "account_type": type(self).__name__,
            "account_number": self._account_number,
            "owner": self._owner,
            "balance": self._balance,
            "currency": self.currency,
            "status": self._status.value,
        }

    def __str__(self):
        last_four = self._account_number[-4:]

        return (
            f"Account type: {type(self).__name__} | "
            f"Customer: {self._owner} | "
            f"Account: ****{last_four} | "
            f"Status: {self._status.value} | "
            f"Balance: {self._balance:.2f} {self.currency}"
        )
