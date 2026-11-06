# bank-system

A multi-level banking system implemented as object-oriented modules in Python. The project provides bank account models with operation validation, a status system, custom exceptions, and three concrete account types.

## Features

- **BankAccount** — base account type with deposit/withdraw operations, status management (active/frozen/closed), and currency support (RUB, USD, EUR, KZT, CNY).
- **SavingsAccount** — adds minimum balance requirement and monthly interest calculation.
- **PremiumAccount** — adds overdraft facility and a fixed withdrawal fee.
- **InvestmentAccount** — manages a portfolio across asset types (stocks, bonds, etf) with yearly growth projection.

All monetary calculations use `Decimal` for exact precision.

## Repository Structure

```
bank-system/
├── README.md            # This file
├── requirements.txt      # Dependencies (pytest)
├── docs/
│   └── algorithm.md     # Detailed algorithm documentation
├── src/
│   ├── __init__.py
│   ├── main.py          # Demo script (CLI scenario)
│   ├── models.py        # Domain models: accounts, statuses, exceptions
│   ├── utils.py         # Helper functions
│   └── run_app.bat     # Launch the application
└── tests/
    ├── run_tests.bat    # Run unit tests
    └── test_main.py     # Unit tests (pytest)
```

## Running the Application

```bat
run_app.bat
```

## Running Tests

```bat
run_tests.bat
```

## Documentation

Detailed algorithm documentation is available in [`docs/algorithm.md`](docs/algorithm.md).

## Planned Extensions

- Transaction system (transfers between accounts, operation history);
- Audit processes and report generation;
- Security mechanisms (authentication, roles);
- Extensibility through the `AbstractAccount` abstraction (new account types: deposit, credit, etc.).
