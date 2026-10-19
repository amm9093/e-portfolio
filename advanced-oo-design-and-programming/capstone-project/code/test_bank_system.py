"""
test_bank_system.py
===================
Unit tests for the thread-safe banking system.

The test method names carry the test-case numbers (T01, T02 ...) used in the
Testing and Validation table of the report, so each row of that table can be
traced to the test that produced it.

Run with:   python -m unittest test_bank_system.py -v
"""

import threading
import unittest
from decimal import Decimal

from bank import Bank
from bank_account import (BankAccount, CurrentAccount, InsufficientFundsError,
                          InvalidAmountError, SavingsAccount)
from simulator import TransactionSimulator


def run_threads(target, count, timeout=30):
    """Start `count` threads on `target`, release them together, wait for all.

    Returns:
        list: names of any threads that did not finish (a deadlock symptom).
    """
    start_signal = threading.Event()

    def worker():
        start_signal.wait()
        target()

    threads = [threading.Thread(target=worker, name=f"T{i}")
               for i in range(count)]
    for thread in threads:
        thread.start()
    start_signal.set()

    stuck = []
    for thread in threads:
        thread.join(timeout=timeout)
        if thread.is_alive():
            stuck.append(thread.name)
    return stuck


# ---------------------------------------------------------------------------
# Basic account behaviour
# ---------------------------------------------------------------------------
class TestBasicOperations(unittest.TestCase):
    """T01 - T05: single-threaded behaviour of a BankAccount."""

    def setUp(self):
        self.account = BankAccount("Alice", 1000)

    def test_T01_deposit_increases_balance(self):
        self.account.deposit(500)
        self.assertEqual(self.account.get_balance(), Decimal("1500.00"))

    def test_T02_withdraw_decreases_balance(self):
        self.account.withdraw(300)
        self.assertEqual(self.account.get_balance(), Decimal("700.00"))

    def test_T03_withdraw_more_than_balance_is_refused(self):
        with self.assertRaises(InsufficientFundsError):
            self.account.withdraw(1500)
        # The balance must be completely unchanged after a refusal.
        self.assertEqual(self.account.get_balance(), Decimal("1000.00"))

    def test_T04_invalid_amounts_are_refused(self):
        for bad_amount in [0, -100, "abc", None, float("nan")]:
            with self.subTest(amount=bad_amount):
                with self.assertRaises(InvalidAmountError):
                    self.account.deposit(bad_amount)
        self.assertEqual(self.account.get_balance(), Decimal("1000.00"))

    def test_T05_decimal_arithmetic_is_exact(self):
        """0.1 + 0.2 must be exactly 0.30, which float cannot guarantee."""
        account = BankAccount("Bob", 0)
        account.deposit("0.10")
        account.deposit("0.20")
        self.assertEqual(account.get_balance(), Decimal("0.30"))


# ---------------------------------------------------------------------------
# Object-oriented features
# ---------------------------------------------------------------------------
class TestOOPFeatures(unittest.TestCase):
    """T06 - T08: inheritance, polymorphism and encapsulation."""

    def test_T06_savings_account_protects_minimum_balance(self):
        savings = SavingsAccount("Carol", 1000, minimum_balance=100)
        savings.withdraw(900)
        self.assertEqual(savings.get_balance(), Decimal("100.00"))
        with self.assertRaises(InsufficientFundsError):
            savings.withdraw(1)          # would breach the minimum

    def test_T07_current_account_allows_agreed_overdraft(self):
        current = CurrentAccount("Dave", 100, overdraft_limit=200)
        current.withdraw(300)            # allowed: 100 + 200 available
        self.assertEqual(current.get_balance(), Decimal("-200.00"))
        with self.assertRaises(InsufficientFundsError):
            current.withdraw(1)          # would exceed the overdraft

    def test_T08_encapsulation_protects_internal_state(self):
        account = BankAccount("Eve", 500)
        # The balance cannot be overwritten from outside the class.
        with self.assertRaises(AttributeError):
            account.account_number = "HACKED"
        # The history returned is a copy, so it cannot be tampered with.
        history = account.get_transaction_history()
        history.append({"type": "FAKE"})
        self.assertEqual(len(account.get_transaction_history()), 1)

    def test_T08b_polymorphism_same_calls_different_rules(self):
        """One loop, three account types, three different withdrawal rules."""
        accounts = [
            BankAccount("Alice", 500),
            SavingsAccount("Carol", 500, minimum_balance=100),
            CurrentAccount("Dave", 500, overdraft_limit=100),
        ]
        expected = [Decimal("500.00"), Decimal("400.00"), Decimal("600.00")]
        for account, limit in zip(accounts, expected):
            with self.subTest(account=type(account).__name__):
                account.withdraw(limit)   # exactly the maximum allowed
                with self.assertRaises(InsufficientFundsError):
                    account.withdraw(1)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------
class TestThreadSafety(unittest.TestCase):
    """T09 - T11: concurrent access to a single account."""

    def test_T09_concurrent_deposits_are_not_lost(self):
        """10 threads x 100 deposits of 10.00 must total exactly 10,000.00."""
        account = BankAccount("Alice", 0)

        def make_deposits():
            for _ in range(100):
                account.deposit(10)

        stuck = run_threads(make_deposits, 10)
        self.assertEqual(stuck, [])
        self.assertEqual(account.get_balance(), Decimal("10000.00"))

    def test_T10_concurrent_withdrawals_never_overdraw(self):
        """500.00 in the account, 10 x 100 attempts of 10.00: only 50 succeed."""
        account = BankAccount("Alice", 500)
        successes = []
        counter_lock = threading.Lock()

        def make_withdrawals():
            local = 0
            for _ in range(100):
                try:
                    account.withdraw(10)
                    local += 1
                except InsufficientFundsError:
                    pass
            with counter_lock:
                successes.append(local)

        stuck = run_threads(make_withdrawals, 10)
        self.assertEqual(stuck, [])
        self.assertEqual(sum(successes), 50)
        self.assertEqual(account.get_balance(), Decimal("0.00"))
        # The balance must never be driven below zero.
        self.assertGreaterEqual(account.get_balance(), Decimal("0.00"))

    def test_T11_mixed_deposits_and_withdrawals_balance(self):
        """Equal numbers of deposits and withdrawals return to the start."""
        account = BankAccount("Alice", 1000)

        def mixed_operations():
            for _ in range(100):
                account.deposit(20)
                account.withdraw(20)

        stuck = run_threads(mixed_operations, 8)
        self.assertEqual(stuck, [])
        self.assertEqual(account.get_balance(), Decimal("1000.00"))


# ---------------------------------------------------------------------------
# Transfers and deadlock prevention
# ---------------------------------------------------------------------------
class TestTransfersAndDeadlock(unittest.TestCase):
    """T12 - T15: multi-account operations."""

    def setUp(self):
        self.bank = Bank("Test Bank")
        self.alice = self.bank.open_account("Alice", 1000)
        self.bob = self.bank.open_account("Bob", 1000)

    def test_T12_transfer_moves_money_and_conserves_the_total(self):
        opening = self.bank.total_balance()
        self.bank.transfer(self.alice, self.bob, 250)
        self.assertEqual(self.alice.get_balance(), Decimal("750.00"))
        self.assertEqual(self.bob.get_balance(), Decimal("1250.00"))
        self.assertEqual(self.bank.total_balance(), opening)

    def test_T13_failed_transfer_changes_nothing(self):
        with self.assertRaises(InsufficientFundsError):
            self.bank.transfer(self.alice, self.bob, 5000)
        self.assertEqual(self.alice.get_balance(), Decimal("1000.00"))
        self.assertEqual(self.bob.get_balance(), Decimal("1000.00"))

    def test_T13b_transfer_to_same_account_is_refused(self):
        with self.assertRaises(ValueError):
            self.bank.transfer(self.alice, self.alice, 100)

    def test_T14_opposite_transfers_do_not_deadlock(self):
        """The classic deadlock scenario: A->B and B->A at the same time."""
        opening = self.bank.total_balance()
        results = []
        results_lock = threading.Lock()

        def transfer_both_ways(index):
            # Half the threads send money one way, half the other way.
            if index % 2 == 0:
                source, target = self.alice, self.bob
            else:
                source, target = self.bob, self.alice
            done = 0
            for _ in range(200):
                try:
                    self.bank.transfer(source, target, 5)
                    done += 1
                except InsufficientFundsError:
                    pass
            with results_lock:
                results.append(done)

        start_signal = threading.Event()

        def worker(index):
            start_signal.wait()
            transfer_both_ways(index)

        threads = [threading.Thread(target=worker, args=(i,), name=f"X{i}")
                   for i in range(6)]
        for thread in threads:
            thread.start()
        start_signal.set()

        stuck = []
        for thread in threads:
            thread.join(timeout=30)
            if thread.is_alive():
                stuck.append(thread.name)

        # If ordered locking failed, threads would still be alive here.
        self.assertEqual(stuck, [], "Deadlock: threads did not finish")
        self.assertEqual(self.bank.total_balance(), opening)

    def test_T15_many_accounts_random_transfers_conserve_money(self):
        accounts = [self.bank.open_account(f"User{i}", 500) for i in range(5)]
        opening = self.bank.total_balance()

        def random_transfers():
            import random
            rng = random.Random()
            for _ in range(100):
                source, target = rng.sample(accounts, 2)
                try:
                    self.bank.transfer(source, target, 25)
                except InsufficientFundsError:
                    pass

        stuck = run_threads(random_transfers, 6)
        self.assertEqual(stuck, [])
        self.assertEqual(self.bank.total_balance(), opening)


# ---------------------------------------------------------------------------
# End-to-end simulation
# ---------------------------------------------------------------------------
class TestSimulator(unittest.TestCase):
    """T16 - T17: the full concurrent simulation."""

    def test_T16_simulation_leaves_the_books_balanced(self):
        bank = Bank("Test Bank")
        accounts = [bank.open_account(f"User{i}", 1000) for i in range(3)]
        simulator = TransactionSimulator(bank, accounts, num_users=5,
                                         operations_per_user=200)
        results = simulator.run()

        self.assertEqual(results["stuck_threads"], [])
        self.assertEqual(results["difference"], Decimal("0.00"))
        self.assertTrue(results["consistent"])

    def test_T17_simulation_rejects_invalid_settings(self):
        bank = Bank("Test Bank")
        account = bank.open_account("Alice", 100)
        with self.assertRaises(ValueError):
            TransactionSimulator(bank, [])
        with self.assertRaises(ValueError):
            TransactionSimulator(bank, [account], num_users=0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
