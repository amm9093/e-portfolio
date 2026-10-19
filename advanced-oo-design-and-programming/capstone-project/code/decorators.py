"""
decorators.py
=============
DECORATOR PATTERN - add behaviour to an account at runtime without touching
the account classes and without an explosion of subclasses.

    account = SecuredAccount(LoggingAccount(bank.open_account("Alice", 100)),
                             authoriser)

The outer object still looks like an account to the rest of the system
(Bank.transfer() only needs account_number, lock, withdraw and deposit), so
decorated and undecorated accounts can be mixed freely.

Two decorators are provided:

    LoggingAccount   - cross-cutting concern: an audit trail of every call,
                       including rejected ones, with the thread that made it.
    SecuredAccount   - security layer: withdrawals need an authorised
                       session; a short lock-out follows repeated failures.

Why Decorator rather than putting logging/security inside Account?
    * Separation of concerns: Account knows about money and locks, nothing
      else. Logging and authorisation are independent policies.
    * Combinatorial freedom: logged, secured, both, neither - with
      inheritance that is four classes per account type (twelve in total).
    * Testability: each decorator is tested with a stub account and the
      account classes are tested with no decorators at all.
"""

import logging
import threading
import time

from bank_account import BankError


class PermissionDeniedError(BankError):
    """Raised when a caller is not allowed to perform an operation."""


class AccountDecorator:
    """Base decorator: forwards everything to the wrapped account.

    Explicit forwarding methods are used for the operations we care about;
    __getattr__ covers the read-only properties (owner, account_number, lock)
    so that Bank.transfer() keeps working on a decorated account.
    """

    def __init__(self, wrapped):
        self._wrapped = wrapped

    # Anything not overridden is delegated untouched.
    def __getattr__(self, name):
        return getattr(self._wrapped, name)

    def deposit(self, amount):
        return self._wrapped.deposit(amount)

    def withdraw(self, amount):
        return self._wrapped.withdraw(amount)

    def get_balance(self):
        return self._wrapped.get_balance()

    def accept(self, visitor):
        # Visitors see the real account, not the wrapper.
        return self._wrapped.accept(visitor)

    @property
    def unwrapped(self):
        """The innermost real account (useful for tests and audits)."""
        inner = self._wrapped
        while isinstance(inner, AccountDecorator):
            inner = inner._wrapped
        return inner

    def __str__(self):
        return f"{type(self).__name__}({self._wrapped})"


class LoggingAccount(AccountDecorator):
    """Writes an audit line for every deposit/withdrawal, success or failure."""

    def __init__(self, wrapped, logger=None):
        super().__init__(wrapped)
        self._log = logger or logging.getLogger("bank.audit")

    def _run(self, op, amount, func):
        thread = threading.current_thread().name
        try:
            result = func(amount)
        except BankError as err:
            self._log.warning("%s %s %s by %s REJECTED: %s",
                              self.account_number, op, amount, thread, err)
            raise
        self._log.info("%s %s %s by %s OK -> balance %s",
                       self.account_number, op, amount, thread, result)
        return result

    def deposit(self, amount):
        return self._run("DEPOSIT", amount, self._wrapped.deposit)

    def withdraw(self, amount):
        return self._run("WITHDRAW", amount, self._wrapped.withdraw)


class Authoriser:
    """Minimal session registry: who is currently logged in as whom.

    In production this would be a token service; here it is just enough to
    show the decorator working. It is thread-safe because several simulated
    users log in concurrently.
    """

    def __init__(self):
        self._sessions = {}             # thread name -> owner name
        self._lock = threading.Lock()

    def login(self, owner):
        with self._lock:
            self._sessions[threading.current_thread().name] = owner

    def logout(self):
        with self._lock:
            self._sessions.pop(threading.current_thread().name, None)

    def current_user(self):
        with self._lock:
            return self._sessions.get(threading.current_thread().name)


class SecuredAccount(AccountDecorator):
    """Only the account owner may withdraw; repeated failures lock the account.

    Deposits are not restricted (anyone may pay money in). After
    `max_failures` denied withdrawals the account refuses all withdrawals
    for `lockout_seconds`, which limits brute-force attempts.
    """

    def __init__(self, wrapped, authoriser, max_failures=3, lockout_seconds=60):
        super().__init__(wrapped)
        self._auth = authoriser
        self._max_failures = max_failures
        self._lockout = lockout_seconds
        self._failures = 0
        self._locked_until = 0.0
        self._guard = threading.Lock()   # protects the two counters above

    def _check_permission(self):
        with self._guard:
            now = time.monotonic()
            if now < self._locked_until:
                raise PermissionDeniedError(
                    f"{self.account_number} is locked out after repeated "
                    f"failed attempts.")
            user = self._auth.current_user()
            if user != self.owner:
                self._failures += 1
                if self._failures >= self._max_failures:
                    self._locked_until = now + self._lockout
                    self._failures = 0
                raise PermissionDeniedError(
                    f"{user!r} is not allowed to withdraw from "
                    f"{self.account_number} (owner {self.owner!r}).")
            self._failures = 0

    def withdraw(self, amount):
        self._check_permission()
        return self._wrapped.withdraw(amount)

    @property
    def is_locked_out(self):
        with self._guard:
            return time.monotonic() < self._locked_until
