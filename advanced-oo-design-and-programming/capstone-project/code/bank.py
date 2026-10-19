"""
bank.py
=======
The Bank class: holds the accounts and performs transfers between them.

Bank is where DEADLOCK PREVENTION lives, because a transfer is the only
operation that needs to hold two locks at the same time.
"""

import threading
from contextlib import contextmanager
from decimal import Decimal

from bank_account import BankAccount, validate_amount


@contextmanager
def ordered_locks(*accounts):
    """Acquire the locks of several accounts in a fixed global order.

    Every multi-account operation in the system (transfer, total_balance,
    fee-charging payments) goes through this one function, so all of them
    agree on the order and none of them can form a circular wait. The locks
    are re-entrant, so a caller that already holds them may nest safely.
    """
    ordered = sorted(accounts, key=lambda a: a.account_number)
    acquired = []
    try:
        for account in ordered:
            account.lock.acquire()
            acquired.append(account)
        yield
    finally:
        for account in reversed(acquired):
            account.lock.release()


class Bank:
    """A collection of accounts, supporting deadlock-free transfers.

    Bank uses COMPOSITION: it *has* accounts rather than being an account.
    It also acts as a Facade - the outside world calls bank.transfer() and
    does not have to know anything about locks or lock ordering.
    """

    def __init__(self, name="Bank"):
        self._name = name
        self._accounts = {}
        # A separate lock for the accounts dictionary itself. It is never
        # held at the same time as an account lock, so it cannot take part
        # in a deadlock.
        self._registry_lock = threading.Lock()

    @property
    def name(self):
        """Name of the bank (read-only)."""
        return self._name

    def open_account(self, owner, balance=0, account_type=BankAccount, **kwargs):
        """Create an account and add it to the bank.

        Any Account subclass can be passed in, so new account products can be
        added without changing this method.

        Args:
            owner: name of the account holder.
            balance: opening balance.
            account_type: the class to create (BankAccount, SavingsAccount...).
            **kwargs: extra arguments for that class, e.g. overdraft_limit.

        Returns:
            The new account object.
        """
        account = account_type(owner, balance, **kwargs)
        with self._registry_lock:
            self._accounts[account.account_number] = account
        return account

    def get_account(self, account_number):
        """Look up an account by its number, or raise KeyError."""
        with self._registry_lock:
            if account_number not in self._accounts:
                raise KeyError("Account not found.")
            return self._accounts[account_number]

    def get_all_accounts(self):
        """Return a list of all accounts held by the bank."""
        with self._registry_lock:
            return list(self._accounts.values())

    # -----------------------------------------------------------------
    # DEADLOCK PREVENTION
    # -----------------------------------------------------------------
    def transfer(self, source, target, amount):
        """Move money from one account to another atomically.

        THE DEADLOCK PROBLEM
        --------------------
        A transfer must hold both account locks at once, otherwise another
        thread could see money that has left the source but not yet arrived
        at the target. If each thread simply locked its own source first:

            Thread A: transfer(ACC001 -> ACC002)  locks ACC001, waits ACC002
            Thread B: transfer(ACC002 -> ACC001)  locks ACC002, waits ACC001

        neither thread can continue and neither will release what it holds.
        This circular wait is a deadlock.

        THE SOLUTION - ORDERED LOCKING
        ------------------------------
        The two accounts are sorted by account number BEFORE any lock is
        taken, so every thread in the system always locks the lower-numbered
        account first. In the example above both threads now lock ACC001
        first, so one of them simply waits and the circle can never form.

        Args:
            source: account to debit.
            target: account to credit.
            amount: positive value to move.

        Returns:
            bool: True when the transfer has completed.

        Raises:
            ValueError: if source and target are the same account.
            InvalidAmountError: if the amount is invalid.
            InsufficientFundsError: if the source cannot fund the transfer.
        """
        # Validate before locking, so one caller's mistake does not make
        # every other thread wait.
        amount = validate_amount(amount)

        if source.account_number == target.account_number:
            raise ValueError("Cannot transfer to the same account.")

        # ordered_locks() is the deadlock prevention: a fixed, global order.
        with ordered_locks(source, target):
            # withdraw() raises if the funds are not there, which aborts
            # the transfer before the target is touched, so the money is
            # never lost half-way.
            source.withdraw(amount)
            target.deposit(amount)
            return True

    def total_balance(self):
        """Return the total money held by the bank.

        All account locks are acquired first, in account-number order, so
        the total is a consistent snapshot: money in the middle of a transfer
        can never be counted twice or missed. Using the same ordering as
        transfer() means this method cannot deadlock against a transfer.
        """
        accounts = self.get_all_accounts()
        with ordered_locks(*accounts):
            return sum((a.get_balance() for a in accounts), Decimal("0.00"))

    def __len__(self):
        with self._registry_lock:
            return len(self._accounts)

    def __str__(self):
        return f"{self._name} ({len(self)} accounts)"
