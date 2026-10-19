"""
bank_account.py
===============
Account classes for the thread-safe banking system.

Contains:
    validate_amount()      - input validation for all monetary values
    Account (abstract)     - shared state, locking and behaviour
    BankAccount            - standard account, cannot be overdrawn
    SavingsAccount         - must keep a minimum balance, earns interest
    CurrentAccount         - may be overdrawn up to an agreed limit

Thread safety
-------------
Each account owns ONE re-entrant lock (threading.RLock). Every method that
reads or changes the balance acquires that lock, so only one thread at a time
can be inside the critical section of a given account.
"""

import threading
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation

# All money is rounded to 2 decimal places (pence / cents).
CENT = Decimal("0.01")


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------
class BankError(Exception):
    """Base class for all errors raised by this banking system."""


class InvalidAmountError(BankError, ValueError):
    """Raised when an amount is not a valid, positive monetary value."""


class InsufficientFundsError(BankError):
    """Raised when an account does not hold enough funds for a withdrawal."""


# ---------------------------------------------------------------------------
# Input validation (secure coding practice)
# ---------------------------------------------------------------------------
def validate_amount(value, allow_zero=False):
    """Validate an amount and return it as a Decimal rounded to 2 places.

    Decimal is used instead of float because float cannot represent decimal
    fractions exactly (0.1 + 0.2 == 0.30000000000000004), which would cause
    balances to drift over thousands of transactions.

    Args:
        value: the amount to validate (int, str or Decimal).
        allow_zero: True only for opening balances; transactions must be > 0.

    Returns:
        Decimal: the validated amount.

    Raises:
        InvalidAmountError: if the value is not a finite, non-negative number.
    """
    try:
        # str() first so that a float such as 0.1 becomes Decimal('0.1')
        # instead of its long binary expansion.
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise InvalidAmountError(f"'{value}' is not a valid amount.")

    if not amount.is_finite():                 # rejects NaN and Infinity
        raise InvalidAmountError("Amount must be a finite number.")
    if amount < 0:
        raise InvalidAmountError("Amount must not be negative.")
    if amount == 0 and not allow_zero:
        raise InvalidAmountError("Amount must be greater than zero.")

    return amount.quantize(CENT)


# ---------------------------------------------------------------------------
# Abstract base class - ABSTRACTION
# ---------------------------------------------------------------------------
class Account(ABC):
    """Abstract, thread-safe bank account.

    This class hides (abstracts) all the locking and validation from the user
    of the class. A caller simply calls deposit() or withdraw() and does not
    need to know that a lock is being acquired.

    Subclasses must implement _available_funds(), which decides how much may
    be withdrawn. This is the Template Method pattern: withdraw() fixes the
    algorithm (validate -> check -> deduct -> record) and the subclass only
    supplies the rule that varies between products.
    """

    # Class-level counter used to give every account a unique number.
    # It is protected by its own lock because two threads could open accounts
    # at the same moment and otherwise receive the same number.
    _counter_lock = threading.Lock()
    _counter = 0

    def __init__(self, owner, balance=0):
        """Create an account.

        Args:
            owner: name of the account holder.
            balance: opening balance (may be zero, must not be negative).
        """
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("Owner name must be a non-empty string.")

        self._owner = owner.strip()
        self._balance = validate_amount(balance, allow_zero=True)
        self._account_number = self._generate_account_number()

        # RLock (re-entrant) rather than Lock: Bank.transfer() holds this lock
        # and then calls withdraw(), which acquires it again in the same
        # thread. A plain Lock would block for ever against itself.
        self._lock = threading.RLock()

        self._history = []
        self._record("OPEN", self._balance)

    @classmethod
    def _generate_account_number(cls):
        """Return a unique account number such as 'ACC001'."""
        with Account._counter_lock:
            Account._counter += 1
            return f"ACC{Account._counter:03d}"

    # -- Properties: ENCAPSULATION -----------------------------------------
    # The balance is stored in the private attribute _balance and is only
    # reachable through these read-only properties, so no outside code can
    # write account.balance = 1000000 and bypass the locking and validation.

    @property
    def account_number(self):
        """Unique identifier for this account (read-only)."""
        return self._account_number

    @property
    def owner(self):
        """Name of the account holder (read-only)."""
        return self._owner

    @property
    def lock(self):
        """The account's lock, needed by Bank.transfer() (read-only)."""
        return self._lock

    # -- Core operations ---------------------------------------------------
    def deposit(self, amount):
        """Add an amount to the balance (thread-safe).

        Args:
            amount: a positive monetary value.

        Returns:
            Decimal: the new balance.

        Raises:
            InvalidAmountError: if the amount is invalid.
        """
        amount = validate_amount(amount)
        with self._lock:                       # critical section starts
            self._balance += amount
            self._record("DEPOSIT", amount)
            return self._balance               # critical section ends

    def withdraw(self, amount):
        """Deduct an amount from the balance if funds allow (thread-safe).

        The availability check and the deduction are inside the SAME lock.
        If they were in two separate locked blocks, two threads could both
        see a sufficient balance and both withdraw ("check-then-act" race).

        Args:
            amount: a positive monetary value.

        Returns:
            Decimal: the new balance.

        Raises:
            InvalidAmountError: if the amount is invalid.
            InsufficientFundsError: if the funds are not available.
        """
        amount = validate_amount(amount)
        with self._lock:
            available = self._available_funds()      # polymorphic rule
            if amount > available:
                raise InsufficientFundsError(
                    f"{self._account_number}: requested {amount}, "
                    f"only {available} available."
                )
            self._balance -= amount
            self._record("WITHDRAW", amount)
            return self._balance

    def get_balance(self):
        """Return the current balance (thread-safe).

        The read is locked so that a caller never sees a half-finished
        transfer, where money has left one account but not yet arrived
        in the other.
        """
        with self._lock:
            return self._balance

    def get_transaction_history(self):
        """Return a COPY of the transaction history.

        A copy is returned so that outside code cannot alter this account's
        records - another example of encapsulation.
        """
        with self._lock:
            return list(self._history)

    def _record(self, kind, amount):
        """Add an entry to the history. Called with the lock already held."""
        self._history.append({
            "type": kind,
            "amount": amount,
            "balance": self._balance,
            "thread": threading.current_thread().name,
        })

    # -- The one method subclasses must supply - POLYMORPHISM --------------
    @abstractmethod
    def _available_funds(self):
        """Return how much may be withdrawn from this account right now."""

    def __str__(self):
        return (f"{type(self).__name__}({self._account_number}, "
                f"{self._owner}, balance={self.get_balance()})")


# ---------------------------------------------------------------------------
# Concrete classes - INHERITANCE and POLYMORPHISM
# ---------------------------------------------------------------------------
class BankAccount(Account):
    """A standard account that cannot be overdrawn."""

    def _available_funds(self):
        """Everything in the account may be withdrawn, but no more."""
        return self._balance


class SavingsAccount(BankAccount):
    """A savings account that must keep a minimum balance and earns interest."""

    def __init__(self, owner, balance=0, minimum_balance=0, interest_rate=0):
        super().__init__(owner, balance)
        self._minimum_balance = validate_amount(minimum_balance, allow_zero=True)
        self._interest_rate = Decimal(str(interest_rate))
        if self._interest_rate < 0 or self._interest_rate > 1:
            raise InvalidAmountError("Interest rate must be between 0 and 1.")

    @property
    def minimum_balance(self):
        """Balance that must always remain in the account (read-only)."""
        return self._minimum_balance

    def _available_funds(self):
        """Only the money above the protected minimum may be withdrawn."""
        spendable = self._balance - self._minimum_balance
        return spendable if spendable > 0 else Decimal("0.00")

    def add_interest(self):
        """Credit one period of interest (thread-safe)."""
        with self._lock:
            interest = (self._balance * self._interest_rate).quantize(CENT)
            if interest > 0:
                self._balance += interest
                self._record("INTEREST", interest)
            return self._balance


class CurrentAccount(BankAccount):
    """A current account with an agreed overdraft limit."""

    def __init__(self, owner, balance=0, overdraft_limit=0):
        super().__init__(owner, balance)
        self._overdraft_limit = validate_amount(overdraft_limit, allow_zero=True)

    @property
    def overdraft_limit(self):
        """The agreed overdraft limit (read-only)."""
        return self._overdraft_limit

    def _available_funds(self):
        """The balance plus the agreed overdraft may be withdrawn."""
        return self._balance + self._overdraft_limit
