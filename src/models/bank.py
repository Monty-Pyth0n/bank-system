from decimal import Decimal

from ..exceptions import (
    InvalidOperationError,
)
from .accounts import (
    AccountStatus,
    BankAccount,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
)
from .client import Client, ClientStatus

# ======================================
# Day 3: Bank System
# ======================================

class Bank:
    """Bank class managing clients and accounts."""

    def __init__(self, name):
        self._name = name.strip() if name else "Unnamed Bank"
        self._clients = {}  # client_id -> Client
        self._accounts = {}  # account_number -> Account

    @property
    def name(self):
        return self._name

    @property
    def clients(self):
        return list(self._clients.values())

    @property
    def accounts(self):
        return list(self._accounts.values())

    def get_client(self, client_id):
        """Get a client by ID."""
        client_id = client_id.strip()
        if client_id not in self._clients:
            raise InvalidOperationError(f"Client with ID '{client_id}' not found.")

        return self._clients[client_id]

    def get_account(self, account_number):
        """Get an account by number."""
        account_number = account_number.strip()

        if account_number not in self._accounts:
            raise InvalidOperationError(f"Account '{account_number}' not found.")

        return self._accounts[account_number]

    def add_client(self, client_id, full_name, contact_details, age):
        """
        Add a new client to the bank.

        Args:
            client_id: Unique client identifier
            full_name: Client's full name
            contact_details: Client's contact information
            age: Client's age (must be >= 18)

        Returns:
            The created Client object

        Raises:
            InvalidOperationError: If client_id already exists or validation fails
        """
        client_id = client_id.strip()

        if client_id in self._clients:
            raise InvalidOperationError(f"Client with ID '{client_id}' already exists.")

        client = Client(client_id, full_name, contact_details, age)
        self._clients[client_id] = client

        return client

    def open_account(self, client_id, account_type="bank", **kwargs):
        """
        Open a new account for a client.

        Args:
            client_id: The client's ID
            account_type: Type of account ('bank', 'savings', 'premium', 'investment')
            **kwargs: Additional arguments for account creation (balance, currency, etc.)

        Returns:
            The created account object

        Raises:
            InvalidOperationError: If client_id does not exist or account_type is invalid
        """

        client = self.get_client(client_id)

        # Map account types to class
        account_classes = {
            "bank": BankAccount,
            "savings": SavingsAccount,
            "premium": PremiumAccount,
            "investment": InvestmentAccount,
        }

        account_type_lower = account_type.lower()
        if account_type_lower not in account_classes:
            raise InvalidOperationError(
                f"Invalid account type '{account_type}'. "
                f"Valid types are: {', '.join(account_classes.keys())}"
            )

        AccountClass = account_classes[account_type_lower]

        # Create the account
        account = AccountClass(owner=client.full_name, client=client, **kwargs)

        self._accounts[account.account_number] = account
        client.add_account(account)

        return account

    def close_account(self, account_number):
        """
        Close an account

        Args:
            account_number: The account number to close

        Returns:
            The closed account object

        Raises:
            InvalidOperationError: If account not found
            AccountClosedError: If the account is already closed
        """
        account = self.get_account(account_number)
        account.close()
        del self._accounts[account_number]

        # Remove from client's account list
        # Find the client who owns this account
        for client in self._clients.values():
            if account_number in client.account_numbers:
                client.remove_account(account_number)

                # If the last account is closed
                if not client.account_numbers:
                    client._status = ClientStatus.INACTIVE

                break

        return account

    def freeze_account(self, account_number):
        """
        Freeze an account.

        Args:
            account_number: The account number to freeze

        Raises:
            InvalidOperationError: If account not found
            AccountFrozenError: If the account is already frozen
        """
        account = self.get_account(account_number)
        account.freeze()

        return account

    def unfreeze_account(self, account_number):
        """
        Unfreeze (activate) an account.

        Args:
            account_number: The account number to unfreeze

        Returns:
            The activated account object

        Raises:
            InvalidOperationError: If account not found
            AccountClosedError: If the account is already closed
        """

        account = self.get_account(account_number)
        account.activate()

        return account

    def authenticate_client(self, client_id, contact_details):
        """
        Authenticate a client.

        Args:
            client_id: The client's ID
            contact_details: Optional contact details for verification

        Returns:
            The authenticated Client object

        Raises:
            InvalidOperationError: If client not found or authentication fails
        """

        client = self.get_client(client_id)
        client.check_locked()

        if contact_details is None or client.contact_details != contact_details:
            client.record_failed_login()

            raise InvalidOperationError(
                "Authentication failed: contact details do not match."
            )

        client.reset_failed_attempts()

        return client

    def search_accounts(self, **criteria):
        """
        Search for accounts matching the given criteria.

        Args:
            **criteria: Search criteria (owner, currency, status, account_type, min_balance, max_balance)

        Returns:
            List of matching Account objects
        """

        results = []

        for account in self._accounts.values():
            match = True

            # Check owner
            if ("owner" in criteria) and (
                criteria["owner"].lower() not in account.owner.lower()
            ):
                match = False

            # Check currency
            if (
                ("currency" in criteria)
                and match
                and (criteria["currency"].upper() != account.currency)
            ):
                match = False

            # Check status
            if ("status" in criteria) and match:
                if isinstance(criteria["status"], AccountStatus):
                    status_value = criteria["status"].value
                else:
                    status_value = str(criteria["status"]).lower()
                if account.status.value != status_value:
                    match = False

            # Check account type
            if (
                ("account_type" in criteria)
                and match
                and (criteria["account_type"].lower() != type(account).__name__.lower())
            ):
                match = False

            # Check minimum balance
            if (
                ("min_balance" in criteria)
                and match
                and (account.balance < Decimal(str(criteria["min_balance"])))
            ):
                match = False

            # Check maximum balance
            if (
                ("max_balance" in criteria)
                and match
                and (account.balance > Decimal(str(criteria["max_balance"])))
            ):
                match = False

            if match:
                results.append(account)

        return results

    def __str__(self):
        return f"Bank: {self._name}, Clients: {len(self._clients)}, Accounts: {len(self._accounts)}"

    # Security methods
    def lock_client(self, client_id):
        """Lock a client (admin operation)."""

        client = self.get_client(client_id)
        client._lock()

        return client

    def unlock_client(self, client_id):
        """Unlock a client (admin operation)."""

        client = self.get_client(client_id)
        client._unlock()

        return client

    def get_client_security_status(self, client_id):
        """Return a snapshot of the client's security state.
        Args:
            client_id: Unique client identifier.

        Returns:
            client_id (str): Client ID.
            full_name (str): Full name.
            status (str): Client status ('active' / 'inactive').
            is_locked (bool): Whether the client is locked.
            failed_login_attempts (int): Current number of failed attempts.
            max_failed_attempts (int): Threshold after which locking occurs.
            is_suspicious (bool): Whether the client is flagged as suspicious.
            suspicious_activity (str): Recent suspicious activity.
        """

        client = self.get_client(client_id)

        return {
            "client_id": client._client_id,
            "full_name": client._full_name,
            "status": client._status.value,
            "is_locked": client._is_locked,
            "failed_login_attempts": client._failed_login_attempts,
            "max_failed_attempts": client.MAX_FAILED_ATTEMPTS,
            "is_suspicious": client._is_suspicious,
            "suspicious_activity": client._suspicious_activity,
        }

    def get_total_balance(self):
        """Calculate the total balance across all accounts in the bank and the portfolio"""
        total = Decimal("0.00")
        for account in self._accounts.values():
            # InvestmentAccount has _total_balance, other — just balance
            if hasattr(account, "total_balance"):
                total += account.total_balance
            else:
                total += account.balance
        return total

    def get_clients_ranking(self):
        """Rank clients by their total account balance (descending)."""
        client_balances = []
        for client in self._clients.values():
            total_balance = Decimal("0.00")
            for account_number in client.account_numbers:
                account = self._accounts.get(account_number)
                if account:
                    if hasattr(account, "total_balance"):
                        total_balance += account.total_balance
                    else:
                        total_balance += account.balance
            client_balances.append((client, total_balance))

        # Sort by balance descending
        client_balances.sort(key=lambda x: x[1], reverse=True)
        return client_balances
