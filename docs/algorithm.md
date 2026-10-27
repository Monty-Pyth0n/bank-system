# Документация по проекту «Bank System»

## 1. Обзор проекта

Проект — многоуровневая банковская система, реализованная как набор объектно-ориентированных модулей на Python. Текущая версия содержит модель банковского счёта с валидацией операций, системой статусов и кастомными исключениями.

### Структура репозитория

```
bank-system/
├── README.md            # общее описание проекта
├── requirements.txt     # зависимости (pytest)
├── docs/
│   └── algorithm.md     # настоящая документация
├── src/
│   ├── __init__.py
│   ├── main.py          # демонстрационный запуск (CLI-сценарий)
│   ├── models.py        # доменные модели: счета, статусы, исключения
│   └── utils.py         # вспомогательные функции
└── tests/
    └── test_main.py     # модульные тесты (pytest)
```

### Зависимости

| Пакет  | Версия | Назначение                          |
|--------|--------|-------------------------------------|
| pytest | 9.1.1  | запуск модульных тестов             |

Стандартная библиотека: `abc`, `decimal`, `enum`, `uuid` — сторонних runtime-зависимостей нет.

---

## 2. Архитектура

### 2.1 Диаграмма классов (упрощённая)

```
            <<abstract>>                 <<enum>>
         AbstractAccount --------------> AccountStatus
        (ABC)                            ACTIVE / FROZEN / CLOSED
              |
              | наследование
              v
         BankAccount
      (currency, status,
       deposit/withdraw,
       freeze/activate/close)

  Исключения (наследники Exception):
  ├── InvalidOperationError    — некорректный аргумент/операция
  ├── InsufficientFundsError   — недостаточно средств
  ├── AccountFrozenError       — операция на замороженном счёте
  └── AccountClosedError       — операция на закрытом счёте
```

### 2.2 Модуль [`src/utils.py`](src/utils.py)

Функция [`generate_account_number()`](src/utils.py:3) генерирует номер счёта:

1. Вызывается `uuid4()` — случайный UUIDv4.
2. Берутся первые 8 символов поля `hex` (без дефисов).
3. Результат приводится к верхнему регистру.

Пример: `3F9A21C7`.

### 2.3 Модуль [`src/models.py`](src/models.py)

#### Перечисление [`AccountStatus`](src/models.py:11)

| Значение | Код      | Поведение                                   |
|----------|----------|---------------------------------------------|
| `ACTIVE` | `active` | все операции разрешены                      |
| `FROZEN` | `frozen` | `deposit`/`withdraw` запрещены              |
| `CLOSED` | `closed` | все операции запрещены, необратимый статус  |

#### Абстрактный класс [`AbstractAccount`](src/models.py:39)

Инкапсулирует общую логику для любых типов счетов.

**Конструктор `__init__(owner, balance=0, account_number=None)`** выполняет алгоритм:

```
1. Проверка владельца:
   - owner должен быть непустой строкой (после strip)
   - иначе -> InvalidOperationError
2. Валидация суммы _validate_amount(balance) -> Decimal
3. Номер счёта:
   - если account_number передан -> привести к строке и strip
   - иначе -> сгенерировать через generate_account_number()
   - если пустой -> InvalidOperationError
4. Статус по умолчанию -> AccountStatus.ACTIVE
```

**Валидация суммы [`_validate_amount(amount)`](src/models.py:58)** — статический метод, общий для `deposit` и `withdraw`:

```
1. bool (True/False)            -> InvalidOperationError (не число)
2. Преобразование Decimal(str(amount))
   при InvalidOperation/ValueError/TypeError -> InvalidOperationError
3. value.is_finite() == False (NaN, Infinity) -> InvalidOperationError
4. value < 0                   -> InvalidOperationError
5. иначе                       -> возврат Decimal
```

Использование `Decimal` вместо `float` гарантирует точность денежных расчётов (десятичная арифметика без ошибок округления двоичного представления).

**Абстрактные методы** (обязательны к реализации в потомках):

- [`deposit(amount)`](src/models.py:78)
- [`withdraw(amount)`](src/models.py:82)
- [`get_account_info()`](src/models.py:86)

#### Класс [`BankAccount`](src/models.py:91)

Конкретная реализация банковского счёта.

**Допустимые валюты** — `ALLOWED_CURRENCIES = {"RUB", "USD", "EUR", "KZT", "CNY"}`.

**Алгоритм конструктора `__init__`:**

```
1. Вызов AbstractAccount.__init__ (владелец, баланс, номер счёта)
2. currency должен быть строкой -> иначе InvalidOperationError
3. currency приводится к верхнему регистру
4. currency ∈ ALLOWED_CURRENCIES -> иначе InvalidOperationError
5. status должен быть экземпляром AccountStatus -> иначе InvalidOperationError
6. Установка self.currency и self._status
```

**Свойства (read-only, только через `@property`):**

| Свойство         | Описание                          |
|------------------|-----------------------------------|
| `owner`          | имя владельца                     |
| `account_number` | номер счёта                       |
| `balance`        | текущий баланс (`Decimal`)        |
| `status`         | текущий статус (`AccountStatus`)  |

Поля `_owner`, `_balance`, `_account_number`, `_status` инкапсулированы (protected) — прямая запись извне не предусмотрена.

**Проверка статуса [`_check_status()`](src/models.py:139):**

```
status == FROZEN -> AccountFrozenError("The account is frozen.")
status == CLOSED -> AccountClosedError("The account is closed.")
иначе            -> продолжить выполнение
```

Вызывается первой строкой в `deposit()` и `withdraw()`.

**Алгоритм `deposit(amount)`:**

```
1. _check_status()                     — проверка статуса счёта
2. amount = _validate_amount(amount)   — валидация суммы (Decimal, >= 0)
3. amount == 0 -> InvalidOperationError("Deposit amount must be greater than zero.")
4. _balance += amount
5. возврат нового баланса
```

**Алгоритм `withdraw(amount)`:**

```
1. _check_status()                     — проверка статуса счёта
2. amount = _validate_amount(amount)   — валидация суммы (Decimal, >= 0)
3. amount == 0 -> InvalidOperationError("Withdrawal amount must be greater than zero.")
4. amount > _balance -> InsufficientFundsError
5. _balance -= amount
6. возврат нового баланса
```

**Управление статусом:**

| Метод                    | Предусловие                          | Действие                          |
|--------------------------|--------------------------------------|-----------------------------------|
| [`freeze()`](src/models.py:172)     | статус ≠ `CLOSED`               | статус := `FROZEN`                |
| [`activate()`](src/models.py:178)   | статус ≠ `CLOSED`               | статус := `ACTIVE`                |
| [`close()`](src/models.py:184)      | статус ≠ `CLOSED` (уже закрыт)  | статус := `CLOSED`                |

Закрытие счёта необратимо: любая попытка изменить статус закрытого счёта выбрасывает `AccountClosedError`.

**[`get_account_info()`](src/models.py:190)** возвращает `dict`:

```python
{
    "account_type": str,      # имя класса, например "BankAccount"
    "account_number": str,
    "owner": str,
    "balance": Decimal,
    "currency": str,
    "status": str,            # код статуса: "active" / "frozen" / "closed"
}
```

**[`__str__()`](src/models.py:200)** форматирует маскированный вывод: показываются только последние 4 цифры номера счёта (`****XXXX`), баланс — с двумя знаками после запятой.

### 2.4 Модуль [`src/main.py`](src/main.py)

Демонстрационный сценарий [`main()`](src/main.py:10), запускаемый командой:

```bash
python -m src.main
```

Последовательность действий:

1. Создание двух счетов: активного (`RUB`, баланс 1000) и замороженного (`USD`, баланс 500, статус `FROZEN`).
2. Операции над активным счётом: `deposit(250)`, `withdraw(100)` (в блоке `try/except`).
3. Демонстрация отказа операций на замороженном счёте (`AccountFrozenError`).
4. Проверки валидации: снятие больше баланса (`InsufficientFundsError`) и отрицательный депозит (`InvalidOperationError`).
5. Вывод [`get_account_info()`](src/main.py:83).

---

## 3. Матрица ошибок

| Операция | Условие                                   | Исключение               |
|----------|-------------------------------------------|--------------------------|
| конструктор | пустой `owner`                          | `InvalidOperationError`  |
| конструктор | `amount` — bool/не число/NaN/Inf/`< 0` | `InvalidOperationError`  |
| конструктор | пустой `account_number`                 | `InvalidOperationError`  |
| конструктор | валюта не из списка разрешённых         | `InvalidOperationError`  |
| конструктор | `status` не `AccountStatus`             | `InvalidOperationError`  |
| `deposit` / `withdraw` | счёт `FROZEN`               | `AccountFrozenError`     |
| `deposit` / `withdraw` | счёт `CLOSED`               | `AccountClosedError`     |
| `deposit` / `withdraw` | сумма = 0                   | `InvalidOperationError`  |
| `withdraw` | сумма > баланса                          | `InsufficientFundsError` |
| `freeze` / `activate` | счёт `CLOSED`               | `AccountClosedError`     |
| `close`   | счёт уже `CLOSED`                        | `AccountClosedError`     |

---

## 4. Тестирование

Тесты расположены в [`tests/test_main.py`](tests/test_main.py), фреймворк — `pytest`.

Запуск:

```bash
pytest
```

Покрытие сценариев:

| Тест                                     | Проверяемое поведение                        |
|------------------------------------------|----------------------------------------------|
| `test_create_account`                    | корректное создание счёта, Decimal-баланс    |
| `test_deposit`                           | пополнение увеличивает баланс                |
| `test_withdraw`                          | снятие уменьшает баланс                      |
| `test_frozen_account_cannot_deposit`     | отказ пополнения замороженного счёта         |
| `test_frozen_account_cannot_withdraw`    | отказ снятия с замороженного счёта           |
| `test_insufficient_funds`                | отказ снятия сверх баланса                   |
| `test_negative_deposit`                  | отказ пополнения отрицательной суммой        |
| `test_zero_deposit`                      | отказ пополнения нулём                       |
| `test_closed_account_cannot_deposit`     | отказ операции с закрытым счётом             |
| `test_invalid_currency`                  | отказ создания счёта в неподдерживаемой валюте |

Во всех негативных тестах дополнительно проверяется, что баланс счёта не изменился.

---

## 5. Планы расширения (согласно README)

- система транзакций (переводы между счетами, история операций);
- процессы аудита и формирование отчётов;
- механизмы безопасности (аутентификация, роли);
- расширяемость за счёт абстракции `AbstractAccount` (новые типы счетов: депозитный, кредитный и т. п.).