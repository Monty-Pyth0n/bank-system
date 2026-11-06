# Documentation for the "Bank System" Project

## 1. Overview

The project is a multi-level banking system implemented as a set of object-oriented modules in Python. The current version contains bank account models with operation validation, a status system, and custom exceptions.

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
│   ├── models.py       # Domain models: accounts, statuses, exceptions
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

Standard library used: `abc`, `decimal`, `enum`, `uuid` — no third-party runtime dependencies.

---

## 2. Architecture

### 2.1 Class Diagram (Simplified)

```
             <<abstract>>                 <<enum>>
          AbstractAccount --------------> AccountStatus
         (ABC)                            ACTIVE / FROZEN / CLOSED
               |
               | inheritance
               v
          BankAccount
      (currency, status,
       deposit/withdraw,
       freeze/activate/close)

Exceptions (subclasses of Exception):
├── InvalidOperationError    — invalid argument/operation
├── InsufficientFundsError  — insufficient funds
├── AccountFrozenError      — operation on frozen account
└── AccountClosedError      — operation on closed account
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
- Each row: `f"{label:<{label_width}} | {value:>{value_width}}"`.
- Final row uses the same format.
- Returns a string joined by newlines, ending with a trailing newline.

### 2.3 Module [`src/models.py`](src/models.py)

#### Enumeration [`AccountStatus`](src/models.py:11)

| Value     | Code      | Behavior                                  |
|-----------|-----------|-------------------------------------------|
| `ACTIVE`  | `active`  | All operations allowed                     |
| `FROZEN`  | `frozen`  | `deposit`/`withdraw` forbidden             |
| `CLOSED`  | `closed`  | All operations forbidden, irreversible     |

#### Abstract Class [`AbstractAccount`](src/models.py:34)

Encapsulates common logic for any account type.

**Constructor `__init__(owner, balance=0, account_number=None)`** executes the following algorithm:

```
1. Validate owner:
   - owner must be a non-empty string (after strip)
   - otherwise -> InvalidOperationError
2. Validate balance via _validate_amount(balance) -> Decimal
3. Account number:
   - if account_number provided -> convert to str and strip
   - otherwise -> generate via generate_account_number()
   - if empty -> InvalidOperationError
4. Default status -> AccountStatus.ACTIVE
```

**Validation [`_validate_amount(amount)`](src/models.py:54)** — a static method shared by `deposit` and `withdraw`:

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

- [`deposit(amount)`](src/models.py:73)
- [`withdraw(amount)`](src/models.py:77)
- [`get_account_info()`](src/models.py:81)

#### Class [`BankAccount`](src/models.py:86)

Concrete implementation of a bank account.

**Allowed currencies** — `ALLOWED_CURRENCIES = {"RUB", "USD", "EUR", "KZT", "CNY"}`.

**Constructor algorithm:**

```
1. Call AbstractAccount.__init__ (owner, balance, account number)
2. currency must be a string -> otherwise InvalidOperationError
3. currency converted to uppercase
4. currency ∈ ALLOWED_CURRENCIES -> otherwise InvalidOperationError
5. status must be an AccountStatus instance -> otherwise InvalidOperationError
6. Set self.currency and self._status
```

**Properties (read-only, accessed via `@property`):**

| Property         | Description                          |
|------------------|-------------------------------------|
| `owner`          | Owner name                           |
| `account_number` | Account number                       |
| `balance`        | Current balance (`Decimal`)          |
| `status`         | Current status (`AccountStatus`)     |

Fields `_owner`, `_balance`, `_account_number`, `_status` are encapsulated (protected) — direct external writes are not supported.

**Status check [`_check_status()`](src/models.py:134):**

```
status == FROZEN -> AccountFrozenError("The account is frozen.")
status == CLOSED -> AccountClosedError("The account is closed.")
otherwise        -> continue execution
```

Called as the first line inside `deposit()` and `withdraw()`.

**Algorithm `deposit(amount)`:**

```
1. _check_status()                     — check account status
2. amount = _validate_amount(amount)  — validate amount (Decimal, >= 0)
3. amount == 0 -> InvalidOperationError("Deposit amount must be greater than zero.")
4. _balance += amount
5. return new balance
```

**Algorithm `withdraw(amount)`:**

```
1. _check_status()                     — check account status
2. amount = _validate_amount(amount)  — validate amount (Decimal, >= 0)
3. amount == 0 -> InvalidOperationError("Withdrawal amount must be greater than zero.")
4. amount > _balance -> InsufficientFundsError
5. _balance -= amount
6. return new balance
```

**Status management:**

| Method                    | Precondition                          | Action                              |
|---------------------------|---------------------------------------|-------------------------------------|
| [`freeze()`](src/models.py:167)     | status ≠ `CLOSED`               | status := `FROZEN`                   |
| [`activate()`](src/models.py:173)   | status ≠ `CLOSED`               | status := `ACTIVE`                   |
| [`close()`](src/models.py:179)      | status ≠ `CLOSED` (already closed)| status := `CLOSED`                   |

Closing an account is irreversible: any attempt to change the status of a closed account raises `AccountClosedError`.

**[`get_account_info()`](src/models.py:185)** returns a `dict`:

```python
{
    "account_type": str,      # class name, e.g. "BankAccount"
    "account_number": str,
    "owner": str,
    "balance": Decimal,
    "currency": str,
    "status": str,            # status code: "active" / "frozen" / "closed"
}
```

**[`__str__()`](src/models.py:195)** formats masked output: only the last 4 digits of the account number are shown (`****XXXX`), balance displayed with 2 decimal places.

#### Class [`SavingsAccount`](src/models.py:218)

A savings account with a minimum balance requirement and monthly interest.

**Constructor parameters:** `min_balance=0`, `interest_rate=0.01`.

**Additional fields:** `self.min_balance` (Decimal), `self.interest_rate` (float).

**Algorithm `withdraw(amount)`** (extends BankAccount):

```
1. _check_status()                     — check account status
2. amount = _validate_amount(amount)  — validate amount (Decimal, >= 0)
3. amount == 0 -> InvalidOperationError("Withdrawal amount must be greater than zero.")
4. if self._balance - amount < self.min_balance -> InsufficientFundsError(
       f"Cannot withdraw below minimum balance of {self.min_balance}. "
       f"Available: {self._balance - self.min_balance}"
   )
5. _balance -= amount
6. return new balance
```

**Method [`apply_monthly_interest()`](src/models.py:251)** applies monthly interest to the balance:

```
1. _check_status()                     — check account status
2. interest = self._balance * Decimal(str(self.interest_rate))
3. self._balance += interest
4. return new balance
```

**[`get_account_info()`](src/models.py:258)** extends the base info with:

```python
{
    "account_type": str,
    "min_balance": Decimal,
    "interest_rate": float,
}
```

**[`__str__()`](src/models.py:269)** adds rows for `Min balance` and `Interest rate`.

#### Class [`PremiumAccount`](src/models.py:286)

A premium account with higher withdrawal limits, overdraft facility, and a fixed fee.

**Constructor parameters:** `overdraft_limit=50000`, `fixed_fee=100`.

**Additional fields:** `self.overdraft_limit` (Decimal), `self.fixed_fee` (Decimal).

**Algorithm `withdraw(amount)`** (extends BankAccount):

```
1. _check_status()                     — check account status
2. amount = _validate_amount(amount)  — validate amount (Decimal, >= 0)
3. amount == 0 -> InvalidOperationError("Withdrawal amount must be greater than zero.")
4. total_with_fee = amount + self.fixed_fee
5. available = self._balance + self.overdraft_limit
6. if total_with_fee > available -> InsufficientFundsError(
       f"Insufficient funds. Available with overdraft: {available}"
   )
7. _balance -= total_with_fee
8. return new balance
```

**[`get_account_info()`](src/models.py:321)** extends the base info with:

```python
{
    "account_type": str,
    "overdraft_limit": Decimal,
    "fixed_fee": Decimal,
}
```

**[`__str__()`](src/models.py:332)** adds rows for `Overdraft limit` and `Fixed fee`.

#### Class [`InvestmentAccount`](src/models.py:348)

An investment account with portfolio management across asset types.

**Constructor parameters:** none additional beyond base.

**Additional field:** `self.portfolio` — a dict mapping asset types (`"stocks"`, `"bonds"`, `"etf"`) to `Decimal` amounts, initialized to 0.

**Supported asset types** — `SUPPORTED_ASSET_TYPES = {"stocks", "bonds", "etf"}`.

**Method [`allocated(asset_type, amount)`](src/models.py:379)** allocates funds to a specific asset type:

```
1. _check_status()                     — check account status
2. amount = _validate_amount(amount)  — validate amount (Decimal, >= 0)
3. if asset_type not in SUPPORTED_ASSET_TYPES -> InvalidOperationError(
       f"Unsupported asset type: {asset_type}. "
       f"Supported types: {', '.join(sorted(SUPPORTED_ASSET_TYPES))}"
   )
4. if amount <= 0 -> InvalidOperationError("Allocation amount must be greater than zero.")
5. if self._balance > 0 and amount > self._balance -> InsufficientFundsError(
       "Insufficient funds to allocation"
   )
6. _balance -= amount
7. self.portfolio[asset_type] += amount
8. return self.portfolio[asset_type]
```

**Method [`project_yearly_growth(growth_rates)`](src/models.py:404)** calculates expected annual growth based on per-asset-type growth rates:

```
1. _check_status()                     — check account status
2. for each asset_type in growth_rates:
   - if asset_type not in SUPPORTED_ASSET_TYPES -> InvalidOperationError(
       f"Unsupported asset type: {asset_type}. "
       f"Supported types: {', '.join(sorted(SUPPORTED_ASSET_TYPES))}"
     )
3. total_growth = Decimal(0)
4. for each (asset_type, rate) in growth_rates:
   - total_growth += self.portfolio[asset_type] * Decimal(str(rate))
5. return total_growth
```

**[`get_account_info()`](src/models.py:421)** extends the base info with:

```python
{
    "account_type": str,
    "portfolio": {k: str(v) for k, v in self.portfolio.items()},
    "portfolio_value": sum(self.portfolio.values()),
    "total_value": self._balance + sum(self.portfolio.values()),
}
```

**[`__str__()`](src/models.py:435)** adds a `Portfolio` row showing each asset type and its value, plus a `Balance` row showing the total value (`_balance + portfolio_value`).

### 2.4 Module [`src/main.py`](src/main.py)

Demo script [`main()`](src/main.py:13), launched via:

```bat
run_app.bat
```

Sequence of actions:

1. Create two accounts: active (`RUB`, balance 1000) and frozen (`USD`, balance 500, status `FROZEN`).
2. Operations on the active account: `deposit(250)`, `withdraw(100)` (in a `try/except` block).
3. Demonstration of rejected operations on the frozen account (`AccountFrozenError`).
4. Validation checks: withdrawal exceeding balance (`InsufficientFundsError`) and negative deposit (`InvalidOperationError`).
5. Output of [`get_account_info()`](src/main.py:86).
6. Day 2 — Portfolio management:
   - Savings account creation with `min_balance=100`, `interest_rate=0.05`; withdrawal below minimum balance rejected; monthly interest applied.
   - Premium account creation with `overdraft_limit=1000`, `fixed_fee=10`; withdrawal within overdraft succeeds.
   - Investment account creation (`EUR`); portfolio allocation across stocks, bonds, etf; yearly growth projection.

---

## 3. Error Matrix

| Operation              | Condition                                   | Exception               |
|------------------------|----------------------------------------------|-------------------------|
| constructor            | empty `owner`                               | `InvalidOperationError` |
| constructor            | `amount` is bool/non-numeric/NaN/Inf/< 0     | `InvalidOperationError` |
| constructor            | empty `account_number`                       | `InvalidOperationError` |
| constructor            | unsupported currency                        | `InvalidOperationError` |
| constructor            | `status` not `AccountStatus`                 | `InvalidOperationError` |
| `deposit` / `withdraw` | account `FROZEN`                            | `AccountFrozenError`   |
| `deposit` / `withdraw` | account `CLOSED`                            | `AccountClosedError`    |
| `deposit` / `withdraw` | amount = 0                                  | `InvalidOperationError` |
| `withdraw`             | amount > balance                             | `InsufficientFundsError` |
| `freeze` / `activate`   | account `CLOSED`                            | `AccountClosedError`   |
| `close`                | account already `CLOSED`                     | `AccountClosedError`   |
| `SavingsAccount.withdraw` | balance - amount < min_balance         | `InsufficientFundsError` |
| `PremiumAccount.withdraw` | amount + fixed_fee > balance + overdraft_limit | `InsufficientFundsError` |
| `InvestmentAccount.allocated` | unsupported asset type              | `InvalidOperationError` |
| `InvestmentAccount.allocated` | amount > balance (when balance > 0)    | `InsufficientFundsError` |
| `InvestmentAccount.project_yearly_growth` | unsupported asset type in growth_rates | `InvalidOperationError` |

---

## 4. Testing

Tests are located in [`tests/test_main.py`](tests/test_main.py), framework — `pytest`.

Run via [`run_tests.bat`](tests/run_tests.bat):

```bat
run_tests.bat
```

This creates a `test_logs.txt` file in the project root directory containing the full verbose test output.

Test scenarios:

| Test                                       | Verified behavior                                      |
|--------------------------------------------|--------------------------------------------------------|
| `test_create_account`                      | Correct account creation, Decimal balance             |
| `test_deposit`                             | Deposit increases balance                             |
| `test_withdraw`                            | Withdrawal decreases balance                          |
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

In all negative tests, the account balance is additionally verified to remain unchanged.

---

## 5. Planned Extensions (per README)

- Transaction system (transfers between accounts, operation history);
- Audit processes and report generation;
- Security mechanisms (authentication, roles);
- Extensibility through the `AbstractAccount` abstraction (new account types: deposit, credit, etc.).
