# Documentation for the "Bank System" Project

## 1. Overview

The project is a multi-level banking system implemented as a set of object-oriented modules in Python. The current version contains bank account models with operation validation, a status system, custom exceptions, a client–bank layer with authentication and security controls, and prohibited-hours/suspicious-activity monitoring.

### Repository Structure

```
bank-system/
├── README.md            # General project description
├── requirements.txt     # Dependencies (pytest)
├── docs/
│   └── algorithm.md     # This document
├── src/
│   ├── __init__.py
│   ├── main.py          # Demo script (CLI scenario)
│   ├── models.py       # Domain models: accounts, clients, bank, statuses, exceptions
│   ├── utils.py         # Helper functions
│   └── run_app.bat     # Launch the application
└── tests/
    ├── run_tests.bat    # Run unit tests
    └── test_main.py     # Unit tests (pytest)
```

### Dependencies

| Package   | Version | Purpose                          |
|-----------|---------|-----------------------------------|
| pytest    | 9.1.1   | Run unit tests                   |

Standard library used: `abc`, `datetime`, `decimal`, `enum`, `logging`, `uuid` — no third-party runtime dependencies.

---

## 2. Architecture

### 2.1 Class Diagram (Simplified)

```
             <<abstract>>                 <<enum>>          <<enum>>
          AbstractAccount --------------> AccountStatus     ClientStatus
         (ABC)                            ACTIVE / FROZEN / CLOSED   ACTIVE / INACTIVE
               |
               | inheritance
               v
          BankAccount
      (currency, status, withdrawal_limit,
       deposit/withdraw, freeze/activate/close,
       prohibited-hours & suspicious-activity checks)
               |  |  |  inheritance
               v  v  v
      SavingsAccount  PremiumAccount  InvestmentAccount
   (min_balance,   (overdraft_limit,   (portfolio,
    interest_rate) fixed_fee)          allocate/growth)

Client (client_id, full_name, age,
       failed-login tracking, lock/unlock,
       suspicious-activity flagging)

Bank (name, clients, accounts)
  add_client / open_account / close_account /
  freeze_account / unfreeze_account /
  authenticate_client / search_accounts /
  lock_client / unlock_client / get_client_security_status /
  get_total_balance / get_clients_ranking

Exceptions (subclasses of Exception):
├── InvalidOperationError     — invalid argument/operation
├── InsufficientFundsError   — insufficient funds
├── AccountFrozenError       — operation on frozen account
├── AccountClosedError       — operation on closed account
├── ClientLockedError        — client locked after too many failed logins
└── TransactionProhibitedError — transaction attempted during 00:00–05:00
```

### 2.2 Module [`src/utils.py`](src/utils.py)

Function [`generate_account_number()`](src/utils.py:3) generates an account number:

1. Calls `uuid4()` — a random UUIDv4.
2. Takes the first 8 characters of the `hex` field (no dashes).
3. Converts the result to uppercase.

Example: `3F9A21C7`.

Function [`build_account_table(rows)`](src/utils.py:7) renders a formatted two-column table:

- `label_width = 20`, `value_width = 20`
- Separator line: `-` repeated `label_width + value_width + 3` times (the `+3` accounts for the ` | ` spacing).
- Output layout: separator line, then each row except the last, then another separator line, then the final row.
- Each row: `f"{label:<{label_width}} | {value:>{value_width}}"`.
- Returns a string joined by newlines, ending with a trailing newline.

### 2.3 Module [`src/models.py`](src/models.py)

#### Enumeration [`AccountStatus`](src/models.py:20)

| Value     | Code      | Behavior                                  |
|-----------|-----------|-------------------------------------------|
| `ACTIVE`  | `active`  | All operations allowed                     |
| `FROZEN`  | `frozen`  | `deposit`/`withdraw` forbidden             |
| `CLOSED`  | `closed`  | All operations forbidden, irreversible     |

#### Enumeration [`ClientStatus`](src/models.py:566)

| Value      | Code       | Behavior                       |
|------------|------------|--------------------------------|
| `ACTIVE`   | `active`   | Client is active                |
| `INACTIVE` | `inactive` | Client has no open accounts     |

#### Exceptions

| Exception                   | Raised when                                                        |
|-----------------------------|--------------------------------------------------------------------|
| `InvalidOperationError`     | invalid argument or operation (empty owner, bad amount, bad currency, unsupported asset type, etc.) |
| `InsufficientFundsError`    | withdrawal/allocation exceeds available funds or limits            |
| `AccountFrozenError`        | operation attempted on a frozen account                            |
| `AccountClosedError`        | operation attempted on a closed account, or changing status of a closed account |
| `ClientLockedError`         | client is locked (after 3 failed login attempts) or admin lock/unlock misuse |
| `TransactionProhibitedError`| transaction attempted during prohibited hours (00:00–05:00)         |

#### Security logging

The module configures `logging.basicConfig(level=logging.WARNING)` and uses `security_logger = logging.getLogger("bank.security")` to log suspicious activity (prohibited-hours transactions, large unusual-hours transactions, failed logins, client lock/unlock events).

#### Abstract Class [`AbstractAccount`](src/models.py:52)

Encapsulates common logic for any account type.

**Constructor `__init__(owner, balance=0, account_number=None)`** executes the following algorithm:

```
1. Validate owner:
   - owner must be a string and non-empty after strip
   - otherwise -> InvalidOperationError("Owner name cannot be empty.")
2. Validate balance via _validate_amount(balance) -> Decimal
3. Account number:
   - if account_number provided -> convert to str and strip
   - otherwise -> generate via generate_account_number()
   - if empty -> InvalidOperationError("Account number cannot be empty.")
4. Set self._owner, self._balance, self._account_number (protected fields)
```

**Validation [`_validate_amount(amount)`](src/models.py:69)** — a static method shared by `deposit` and `withdraw`:

```
1. isinstance(amount, bool) -> InvalidOperationError (not a number)
2. Convert Decimal(str(amount))
   - on InvalidOperation/ValueError/TypeError -> InvalidOperationError
3. value.is_finite() == False (NaN, Infinity) -> InvalidOperationError
4. value < 0 -> InvalidOperationError
5. otherwise -> return Decimal
```

Using `Decimal` instead of `float` guarantees exact monetary calculations (decimal arithmetic without binary representation rounding errors).

**Abstract methods** (must be implemented by subclasses):

- [`deposit(amount)`](src/models.py:89)
- [`withdraw(amount)`](src/models.py:93)
- [`get_account_info()`](src/models.py:97)

#### Class [`BankAccount`](src/models.py:102)

Concrete implementation of a bank account.

**Class attributes:**

- `ALLOWED_CURRENCIES = {"RUB", "USD", "EUR", "KZT", "CNY"}`
- `DEFAULT_WITHDRAWAL_LIMIT = Decimal("100000.00")` — default daily withdrawal limit
- `PROHIBITED_HOURS_START = 0` (00:00), `PROHIBITED_HOURS_END = 5` (05:00)

**Constructor algorithm:**

```
1. Call AbstractAccount.__init__(owner, balance, account_number)
2. currency must be a string -> otherwise InvalidOperationError
3. currency converted to uppercase
4. currency ∈ ALLOWED_CURRENCIES -> otherwise InvalidOperationError
5. status must be an AccountStatus instance -> otherwise InvalidOperationError
6. withdrawal_limit: if provided -> validate via _validate_amount; else DEFAULT_WITHDRAWAL_LIMIT
7. client: optional Client instance linked to the account
8. Set self.currency, self._status, self._client, self.withdrawal_limit
```

**Properties (read-only, accessed via `@property`):**

| Property         | Description                          |
|------------------|-------------------------------------|
| `owner`          | Owner name                           |
| `account_number` | Account number                       |
| `balance`        | Current balance (`Decimal`)          |
| `status`         | Current status (`AccountStatus`)     |
| `currency`       | Account currency                     |
| `withdrawal_limit` | Daily withdrawal limit (`Decimal`) |
| `client`         | Linked `Client` (or None)            |

Fields `_owner`, `_balance`, `_account_number`, `_status` are encapsulated (protected) — direct external writes are not supported.

**Status check [`_check_status()`](src/models.py:160):**

```
status == FROZEN -> AccountFrozenError("The account is frozen.")
status == CLOSED -> AccountClosedError("The account is closed.")
otherwise        -> continue execution
```

Called as the first line inside `deposit()` and `withdraw()`.

**Prohibited-hours check [`_check_prohibited_hours()`](src/models.py:168):**

```
current_hour = datetime.now().hour
0 <= current_hour < 5 -> TransactionProhibitedError(
    "Transactions are prohibited between 0:00 and 5:00"
)
```

Also logs a suspicious-activity warning via `security_logger`.

**Suspicious-activity check [`_check_suspicious_activity(amount, operation_type)`](src/models.py:182):**

```
large_amount_threshold = Decimal("100000.00")
if amount > 100000 and (current_hour < 6 or current_hour > 22):
    log warning via security_logger
    if self._client is not None:
        self._client.flag_suspicious_activity(reason)
```

**Algorithm `deposit(amount)`:**

```
1. _check_status()                     — check account status
2. amount = _validate_amount(amount)  — validate amount (Decimal, >= 0)
3. amount == 0 -> InvalidOperationError("Deposit amount must be greater than zero.")
4. _check_prohibited_hours()          — security: prohibited hours
5. _check_suspicious_activity(amount, "deposit")
6. _balance += amount
7. return new balance
```

**Algorithm `withdraw(amount)`:**

```
1. _check_status()                     — check account status
2. amount = _validate_amount(amount)  — validate amount (Decimal, >= 0)
3. amount == 0 -> InvalidOperationError("Withdrawal amount must be greater than zero.")
4. amount > _balance -> InsufficientFundsError
5. amount > self.withdrawal_limit -> InsufficientFundsError (daily limit exceeded)
6. _check_prohibited_hours()          — security: prohibited hours
7. _check_suspicious_activity(amount, "withdrawal")
8. _balance -= amount
9. return new balance
```

**Status management:**

| Method                    | Precondition                          | Action                              |
|---------------------------|---------------------------------------|-------------------------------------|
| [`freeze()`](src/models.py:246)     | status ≠ `CLOSED`               | status := `FROZEN`                   |
| [`activate()`](src/models.py:252)   | status ≠ `CLOSED`               | status := `ACTIVE`                   |
| [`close()`](src/models.py:258)      | status ≠ `CLOSED` (already closed)| status := `CLOSED`                   |

Closing an account is irreversible: any attempt to change the status of a closed account raises `AccountClosedError`.

**[`get_account_info()`](src/models.py:264)** returns a `dict`:

```python
{
    "account_type": str,      # class name, e.g. "BankAccount"
    "account_number": str,
    "owner": str,
    "balance": Decimal,
    "currency": str,
    "status": str,            # status code: "active" / "frozen" / "closed"
    "withdrawal_limit": Decimal,
}
```

**[`__str__()`](src/models.py:275)** formats output via `build_account_table` with rows:
`Account type`, `Customer`, `Account` (masked `****XXXX`, only last 4 digits shown), `Status`, `Withdrawal limit`, `Balance`.

#### Class [`SavingsAccount`](src/models.py:295)

A savings account with a minimum balance requirement and monthly interest.

**Constructor parameters:** `min_balance=0`, `interest_rate=0.01` (plus all `BankAccount` parameters: `currency`, `status`, `withdrawal_limit`, `client`).

**Additional fields:** `self.min_balance`, `self.interest_rate`.

**Algorithm `withdraw(amount)`** (extends `BankAccount`):

```
1. amount = _validate_amount(amount)  — validate amount (Decimal, >= 0)
2. if self._balance - amount < self.min_balance -> InsufficientFundsError(
       f"Cannot withdraw below minimum balance of {self.min_balance}. "
       f"Available: {self._balance - self.min_balance}"
   )
3. delegate to super().withdraw(amount) — status check, balance/limit checks,
   security checks, balance update
```

Note: status and security checks are performed by `BankAccount.withdraw`.

**Method [`apply_monthly_interest()`](src/models.py:334)** applies monthly interest to the balance:

```
1. _check_status()                     — check account status
2. interest = self._balance * Decimal(str(self.interest_rate))
3. self._balance += interest
4. return new balance
```

**[`get_account_info()`](src/models.py:343)** extends the base info with:

```python
{
    "account_type": str,
    "min_balance": Decimal,
    "interest_rate": float,
    "withdrawal_limit": Decimal,
}
```

**[`__str__()`](src/models.py:354)** adds rows for `Min balance`, `Withdrawal limit`, `Interest rate`.

#### Class [`PremiumAccount`](src/models.py:372)

A premium account with higher withdrawal limits, overdraft facility, and a fixed fee.

**Constructor parameters:** `overdraft_limit=50000`, `fixed_fee=100`, `withdrawal_limit=DEFAULT_WITHDRAWAL_LIMIT` (500,000) (plus base parameters).

**Class attribute:** `DEFAULT_WITHDRAWAL_LIMIT = Decimal("500000.00")`.

**Additional fields:** `self.overdraft_limit` (Decimal), `self.fixed_fee` (Decimal).

**Algorithm `withdraw(amount)`** (extends `BankAccount`):

```
1. _check_status()                     — check account status
2. amount = _validate_amount(amount)  — validate amount (Decimal, >= 0)
3. amount == 0 -> InvalidOperationError("Withdrawal amount must be greater than zero.")
4. total_with_fee = amount + self.fixed_fee
5. if total_with_fee > self.withdrawal_limit -> InsufficientFundsError(
       f"Withdrawal amount exceeds daily limit of {self.withdrawal_limit}"
   )
6. available = self._balance + self.overdraft_limit
7. if total_with_fee > available -> InsufficientFundsError(
       f"Insufficient funds. Available with overdraft: {available}"
   )
8. _check_prohibited_hours()          — security: prohibited hours
9. _check_suspicious_activity(amount, "withdrawal")
10. _balance -= total_with_fee
11. return new balance
```

**[`get_account_info()`](src/models.py:429)** extends the base info with:

```python
{
    "account_type": str,
    "overdraft_limit": Decimal,
    "fixed_fee": Decimal,
    "withdrawal_limit": Decimal,
}
```

**[`__str__()`](src/models.py:441)** adds rows for `Withdrawal limit`, `Overdraft limit`, `Fixed fee`.

#### Class [`InvestmentAccount`](src/models.py:458)

An investment account with portfolio management across asset types.

**Constructor parameters:** none additional beyond base (`currency`, `status`, `withdrawal_limit`, `client`).

**Supported asset types** — `SUPPORTED_ASSET_TYPES = {"stocks", "bonds", "etf"}`.

**Additional field:** `self.portfolio` — a dict mapping asset types to `Decimal` amounts, initialized to 0 for each supported type.

**Method [`allocate(asset_type, amount)`](src/models.py:484)** allocates funds to a specific asset type:

```
1. _check_status()                     — check account status
2. amount = _validate_amount(amount)  — validate amount (Decimal, >= 0)
3. if asset_type not in SUPPORTED_ASSET_TYPES -> InvalidOperationError(
       f"Unsupported asset type: {asset_type}. "
       f"Supported types: {', '.join(sorted(SUPPORTED_ASSET_TYPES))}"
   )
4. if amount <= 0 -> InvalidOperationError("Allocation amount must be greater than zero.")
5. if amount > self._balance -> InsufficientFundsError("Insufficient funds to allocation")
6. _check_prohibited_hours()          — security: prohibited hours
7. _check_suspicious_activity(amount, "allocation")
8. _balance -= amount
9. self.portfolio[asset_type] += amount
10. return self.portfolio[asset_type]
```

**Method [`project_yearly_growth(growth_rates)`](src/models.py:512)** calculates expected annual growth based on per-asset-type growth rates:

```
1. for each asset_type in growth_rates:
   - if asset_type not in SUPPORTED_ASSET_TYPES -> InvalidOperationError(
      f"Unsupported asset type: {asset_type}. "
      f"Supported types: {', '.join(sorted(SUPPORTED_ASSET_TYPES))}"
    )
2. total_growth = Decimal(0)
3. for each (asset_type, rate) in growth_rates:
   - total_growth += self.portfolio[asset_type] * Decimal(str(rate))
4. return total_growth
```

**[`get_account_info()`](src/models.py:528)** extends the base info with:

```python
{
    "account_type": str,
    "portfolio": {k: str(v) for k, v in self.portfolio.items()},
    "portfolio_value": sum(self.portfolio.values()),
    "total_value": self._balance + sum(self.portfolio.values()),
    "withdrawal_limit": Decimal,
}
```

**[`__str__()`](src/models.py:542)** adds a `Portfolio` row showing each asset type and its value, plus a `Balance` row showing the total value (`_balance + portfolio_value`).

#### Class [`Client`](src/models.py:572)

Represents a bank client with personal information, accounts, and security state.

**Class attribute:** `MAX_FAILED_ATTEMPTS = 3`.

**Constructor `__init__(client_id, full_name, contact_details, age, status=ClientStatus.ACTIVE)`:**

```
1. client_id = strip
2. full_name = strip
3. status = ClientStatus
4. contact_details, age stored (age validated via _validate_age)
5. self._account_numbers = []
6. Security state: _failed_login_attempts = 0, _last_failed_attempt_time = None,
   _is_locked = False, _is_suspicious = False, _suspicious_activity = None
```

**Properties (read-only):**

| Property               | Description                          |
|------------------------|-------------------------------------|
| `client_id`            | Client ID                            |
| `full_name`            | Full name                            |
| `status`               | Client status (`ClientStatus`)       |
| `contact_details`      | Contact information                  |
| `age`                  | Client age (>= 18)                   |
| `account_numbers`      | Copy of the account number list      |
| `is_locked`            | Whether the client is locked         |
| `is_suspicious`        | Whether the client is flagged        |
| `failed_login_attempts`| Current failed login count           |
| `suspicious_activity`  | Recent suspicious activity reason    |

**Method [`_validate_age(age)`](src/models.py:639):**

```
1. int(age) -> on ValueError/TypeError -> InvalidOperationError("Age must be a valid integer.")
2. age_value < 18 -> InvalidOperationError("Client must be at least 18 years old.")
3. return age_value
```

**Method `add_account(account)`:** appends `account.account_number` to the client's list (raises `InvalidOperationError` if the object has no `account_number`).

**Method `remove_account(account_number)`:** removes the account number (raises `InvalidOperationError` if not found).

**Method `get_account_info()`** returns a `dict` with `full_name`, `client_id`, `status`, `contact_details`, `age`, `account_numbers`.

**Security methods:**

- [`_lock()`](src/models.py:687) — locks the client; raises `ClientLockedError` if already locked.
- [`_unlock()`](src/models.py:696) — unlocks the client, resets failed attempts and suspicious flags, logs the event; raises `ClientLockedError` if not locked.
- [`flag_suspicious_activity(reason)`](src/models.py:708) — sets `_is_suspicious = True`, stores reason, logs warning.
- [`record_failed_login()`](src/models.py:719) — increments failed-attempt counter, logs warning; if threshold (`MAX_FAILED_ATTEMPTS`) reached, locks the client and flags suspicious activity.
- [`reset_failed_attempts()`](src/models.py:736) — resets counter, time, and suspicious flags; logs info.
- [`check_locked()`](src/models.py:749) — raises `ClientLockedError` if the client is locked.

#### Class [`Bank`](src/models.py:762)

Manages clients and accounts at the bank level.

**Constructor `__init__(name)`:** `self._name`, `self._clients = {}` (client_id -> Client), `self._accounts = {}` (account_number -> Account).

**Properties:** `name`, `clients` (list), `accounts` (list).

**Client management:**

| Method                              | Behavior                                                          |
|-------------------------------------|-------------------------------------------------------------------|
| [`get_client(client_id)`](src/models.py:782) | Returns client by ID; `InvalidOperationError` if not found       |
| [`add_client(client_id, full_name, contact_details, age)`](src/models.py:799) | Creates and registers a client; `InvalidOperationError` if ID exists |
| [`lock_client(client_id)`](src/models.py:1033) | Admin operation: calls `client._lock()`                          |
| [`unlock_client(client_id)`](src/models.py:1041) | Admin operation: calls `client._unlock()`                        |
| [`get_client_security_status(client_id)`](src/models.py:1049) | Returns a security snapshot dict (see below)                     |

**Account management:**

| Method                              | Behavior                                                          |
|-------------------------------------|-------------------------------------------------------------------|
| [`get_account(account_number)`](src/models.py:790) | Returns account by number; `InvalidOperationError` if not found  |
| [`open_account(client_id, account_type="bank", **kwargs)`](src/models.py:825) | Creates account (`bank`/`savings`/`premium`/`investment`), links client, stores account |
| [`close_account(account_number)`](src/models.py:872) | Closes account, removes from bank and client; if client has no accounts left, sets client status to `INACTIVE` |
| [`freeze_account(account_number)`](src/models.py:904) | Calls `account.freeze()`                                         |
| [`unfreeze_account(account_number)`](src/models.py:920) | Calls `account.activate()`                                       |
| [`search_accounts(**criteria)`](src/models.py:969) | Filters accounts by `owner`, `currency`, `status`, `account_type`, `min_balance`, `max_balance` |
| [`get_total_balance()`](src/models.py:1078) | Sum of balances across all accounts                              |
| [`get_clients_ranking()`](src/models.py:1085) | List of `(client, total_balance)` sorted descending by balance   |

**Authentication:**

| Method                              | Behavior                                                          |
|-------------------------------------|-------------------------------------------------------------------|
| [`authenticate_client(client_id, contact_details)`](src/models.py:940) | Gets client, `check_locked()`, verifies contact details; on mismatch records failed login and raises `InvalidOperationError`; on success resets failed attempts and returns client |

**`get_client_security_status(client_id)`** returns:

```python
{
    "client_id": str,
    "full_name": str,
    "status": str,            # "active" / "inactive"
    "is_locked": bool,
    "failed_login_attempts": int,
    "max_failed_attempts": int,
    "is_suspicious": bool,
    "suspicious_activity": str or None,
}
```

**[`__str__()`](src/models.py:1029)** returns `f"Bank: {self._name}, Clients: {len(self._clients)}, Accounts: {len(self._accounts)}"`.

### 2.4 Module [`src/main.py`](src/main.py)

Demo script [`main()`](src/main.py:19), launched via:

```bat
run_app.bat
```

Sequence of actions:

**Day 1 — Basic account operations:**

1. Mock `datetime.now()` to 12:00 (outside prohibited hours 00:00–05:00).
2. Create two accounts: active (`RUB`, balance 1000) and frozen (`USD`, balance 500, status `FROZEN`).
3. Operations on the active account: `deposit(250)`, `withdraw(100)` (in a `try/except` block).
4. Demonstration of rejected operations on the frozen account (`AccountFrozenError`).
5. Validation checks: withdrawal exceeding balance (`InsufficientFundsError`) and negative deposit (`InvalidOperationError`).
6. Output of [`get_account_info()`](src/main.py:97).

**Day 2 — Portfolio management:**

- Savings account creation with `min_balance=100`, `interest_rate=0.05`; withdrawal below minimum balance rejected; monthly interest applied.
- Premium account creation with `overdraft_limit=1000`, `fixed_fee=10`; withdrawal within overdraft succeeds.
- Investment account creation (`EUR`); portfolio allocation across stocks, bonds, etf; yearly growth projection.

**Day 3 — Bank system (client & security layer):**

1. Create a `Bank`, add clients (Ivan Petrov, Anna Smirnova).
2. Open accounts for clients via `bank.open_account(...)`.
3. Authentication: correct contact details succeed; wrong contact details record a failed login.
4. After 3 failed attempts, the client is locked; `check_locked()` raises `ClientLockedError`.
5. Admin lock/unlock of a client via `bank.lock_client()` / `bank.unlock_client()`.
6. Output of `bank.get_client_security_status(...)`.
7. Perform transactions (deposit/withdraw) subject to security checks (`TransactionProhibitedError`, suspicious activity).
8. Freeze and unfreeze an account via `bank.freeze_account()` / `bank.unfreeze_account()`.
9. Search accounts by owner (`bank.search_accounts(owner="Ivan")`).
10. Get total balance across all accounts (`bank.get_total_balance()`).
11. Get client ranking by total balance (`bank.get_clients_ranking()`).
12. Close an account; closing the last account sets the client status to `INACTIVE`.

---

## 3. Error Matrix

| Operation              | Condition                                   | Exception               |
|------------------------|----------------------------------------------|-------------------------|
| constructor (`AbstractAccount`) | empty `owner`                               | `InvalidOperationError` |
| constructor            | `amount` is bool/non-numeric/NaN/Inf/< 0     | `InvalidOperationError` |
| constructor            | empty `account_number`                       | `InvalidOperationError` |
| constructor (`BankAccount`) | unsupported currency                        | `InvalidOperationError` |
| constructor            | `status` not `AccountStatus`                 | `InvalidOperationError` |
| constructor (`Client`) | age < 18 or non-integer                      | `InvalidOperationError` |
| `Bank.add_client`      | duplicate `client_id`                        | `InvalidOperationError` |
| `Bank.open_account`    | invalid `account_type`                       | `InvalidOperationError` |
| `deposit` / `withdraw` | account `FROZEN`                            | `AccountFrozenError`   |
| `deposit` / `withdraw` | account `CLOSED`                            | `AccountClosedError`    |
| `deposit` / `withdraw` | amount = 0                                  | `InvalidOperationError` |
| `deposit` / `withdraw` | 00:00 <= hour < 05:00                        | `TransactionProhibitedError` |
| `withdraw`             | amount > balance                             | `InsufficientFundsError` |
| `withdraw`             | amount > withdrawal_limit                    | `InsufficientFundsError` |
| `freeze` / `activate`   | account `CLOSED`                            | `AccountClosedError`   |
| `close`                | account already `CLOSED`                     | `AccountClosedError`   |
| `Client._lock` / `_unlock` | wrong lock state                          | `ClientLockedError`    |
| `Client.check_locked`  | client is locked                             | `ClientLockedError`    |
| `Bank.authenticate_client` | wrong contact details / locked client     | `InvalidOperationError` / `ClientLockedError` |
| `SavingsAccount.withdraw` | balance - amount < min_balance           | `InsufficientFundsError` |
| `PremiumAccount.withdraw` | amount + fixed_fee > withdrawal_limit     | `InsufficientFundsError` |
| `PremiumAccount.withdraw` | amount + fixed_fee > balance + overdraft_limit | `InsufficientFundsError` |
| `InvestmentAccount.allocate` | unsupported asset type                  | `InvalidOperationError` |
| `InvestmentAccount.allocate` | amount <= 0                             | `InvalidOperationError` |
| `InvestmentAccount.allocate` | amount > balance                        | `InsufficientFundsError` |
| `InvestmentAccount.project_yearly_growth` | unsupported asset type in growth_rates | `InvalidOperationError` |

---

## 4. Testing

Tests are located in [`tests/test_main.py`](tests/test_main.py), framework — `pytest`.

Run via [`run_tests.bat`](tests/run_tests.bat):

```bat
run_tests.bat
```

This creates a `test_logs.txt` file in the project root directory containing the full verbose test output.

An autouse fixture mocks `datetime.now()` to return 12:00 (noon) — outside prohibited hours (00:00–05:00) — for all tests.

Test scenarios:

| Test                                       | Verified behavior                                      |
|--------------------------------------------|--------------------------------------------------------|
| `test_create_account`                      | Correct account creation, Decimal balance             |
| `test_deposit`                             | Deposit increases balance                             |
| `test_withdraw`                            | Withdrawal decreases balance                          |
| `test_bank_account_withdrawal_limit`       | Withdrawal limit enforced (default and custom)        |
| `test_bank_account_custom_withdrawal_limit`| Custom withdrawal limit respected                     |
| `test_frozen_account_cannot_deposit`     | Rejected deposit on frozen account                    |
| `test_frozen_account_cannot_withdraw`     | Rejected withdrawal on frozen account                 |
| `test_insufficient_funds`                  | Rejected withdrawal exceeding balance                 |
| `test_negative_deposit`                   | Rejected negative deposit                              |
| `test_zero_deposit`                       | Rejected zero deposit                                 |
| `test_closed_account_cannot_deposit`     | Rejected operation on closed account                  |
| `test_invalid_currency`                   | Rejected account creation with unsupported currency   |
| `test_savings_account_creation`           | Correct savings account creation, defaults             |
| `test_savings_account_minimum_balance`    | Rejected withdrawal below minimum balance             |
| `test_savings_account_apply_interest`    | Monthly interest applied correctly                     |
| `test_savings_account_get_account_info`  | Info includes min_balance and interest_rate          |
| `test_premium_account_creation`          | Correct premium account creation, defaults             |
| `test_premium_account_overdraft`         | Withdrawal within overdraft succeeds                  |
| `test_premium_account_without_overdraft`  | Rejected withdrawal exceeding overdraft               |
| `test_premium_account_get_account_info`  | Info includes overdraft_limit and fixed_fee          |
| `test_investment_account_creation`        | Correct investment account creation                    |
| `test_investment_account_allocation`       | Portfolio allocation works correctly                  |
| `test_investment_account_insufficient_funds` | Rejected allocation exceeding balance              |
| `test_investment_account_project_yearly_growth` | Yearly growth calculation correct                |
| `test_check_prohibited_hours_*`            | Transactions rejected during 00:00–05:00 (bank/savings/premium/investment) |
| `test_check_prohibited_hours_boundary_*`   | Boundary behavior at 00:00 and 05:00                  |
| `test_client_locked_error_raised`          | `ClientLockedError` after 3 failed login attempts     |
| `test_close_last_account_makes_client_inactive` | Client status becomes `INACTIVE` after last account closed |
| `test_bank_lock_unlock_client_admin`       | Admin lock/unlock resets failed attempts              |

In all negative tests, the account balance is additionally verified to remain unchanged.

---

## 5. Planned Extensions (per README)

- Transaction system (transfers between accounts, operation history);
- Audit processes and report generation;
- Security mechanisms (authentication, roles);
- Extensibility through the `AbstractAccount` abstraction (new account types: deposit, credit, etc.).