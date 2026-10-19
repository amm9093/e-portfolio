"""
simulator.py
============
TransactionSimulator: simulates several users performing transactions on the
same accounts at the same time, using threads.

After the run it checks the accounting rule

    closing total = opening total + all deposits - all withdrawals

Transfers do not appear in that rule because they move money *inside* the
bank. If a transfer were ever interrupted half-way, the rule would break -
which is what makes it a useful test of thread safety.
"""

import random
import threading
import time
from decimal import Decimal

from bank_account import InsufficientFundsError


class TransactionSimulator:
    """Runs several 'users' (threads) against a set of accounts."""

    def __init__(self, bank, accounts, num_users=5, operations_per_user=100,
                 seed=42):
        """Set up a simulation.

        Args:
            bank: the Bank object (needed for transfers).
            accounts: list of accounts the users will operate on.
            num_users: how many threads to run.
            operations_per_user: how many operations each thread performs.
            seed: random seed, so a run can be repeated exactly.
        """
        if not accounts:
            raise ValueError("At least one account is required.")
        if num_users < 1 or operations_per_user < 1:
            raise ValueError("num_users and operations_per_user must be >= 1.")

        self.bank = bank
        self.accounts = accounts
        self.num_users = num_users
        self.operations_per_user = operations_per_user
        self.seed = seed

        # Shared totals, protected by their own lock. Without this lock the
        # simulator itself would suffer the race condition it is testing for.
        self._stats_lock = threading.Lock()
        self._stats = {
            "deposits": 0,
            "withdrawals": 0,
            "failed_withdrawals": 0,
            "transfers": 0,
            "failed_transfers": 0,
            "total_deposited": Decimal("0.00"),
            "total_withdrawn": Decimal("0.00"),
        }

    def _update(self, key, amount=None):
        """Safely update the shared statistics."""
        with self._stats_lock:
            self._stats[key] += 1
            if amount is not None:
                if key == "deposits":
                    self._stats["total_deposited"] += amount
                elif key == "withdrawals":
                    self._stats["total_withdrawn"] += amount

    def _user_session(self, user_id, start_signal):
        """The work done by one simulated user. Runs in its own thread."""
        # Each thread gets its own random generator so the threads do not
        # share hidden state, and so the run is reproducible.
        rng = random.Random(self.seed + user_id)

        # Wait until every thread is ready, then all start together. This
        # forces the threads to compete, which is the point of the test.
        start_signal.wait()

        for _ in range(self.operations_per_user):
            action = rng.choice(["deposit", "withdraw", "transfer", "balance"])
            account = rng.choice(self.accounts)
            amount = Decimal(rng.randrange(100, 5001)) / 100  # 1.00 - 50.00

            if action == "deposit":
                account.deposit(amount)
                self._update("deposits", amount)

            elif action == "withdraw":
                try:
                    account.withdraw(amount)
                    self._update("withdrawals", amount)
                except InsufficientFundsError:
                    # A declined withdrawal is a correct result, not an error.
                    self._update("failed_withdrawals")

            elif action == "transfer" and len(self.accounts) > 1:
                target = rng.choice([a for a in self.accounts
                                     if a is not account])
                try:
                    self.bank.transfer(account, target, amount)
                    self._update("transfers")
                except InsufficientFundsError:
                    self._update("failed_transfers")

            else:
                account.get_balance()

    def run(self):
        """Run the simulation and return a results dictionary."""
        opening_total = self.bank.total_balance()

        # An Event is used as a starting gun for all threads.
        start_signal = threading.Event()
        threads = [
            threading.Thread(target=self._user_session,
                             args=(user_id, start_signal),
                             name=f"User-{user_id + 1}")
            for user_id in range(self.num_users)
        ]

        for thread in threads:
            thread.start()

        started = time.time()
        start_signal.set()                 # release every thread at once

        stuck = []
        for thread in threads:
            # join() with a timeout: if a thread were deadlocked it would
            # still be alive afterwards and would be reported, instead of
            # freezing the program for ever.
            thread.join(timeout=60)
            if thread.is_alive():
                stuck.append(thread.name)
        duration = time.time() - started

        closing_total = self.bank.total_balance()
        expected_total = (opening_total
                          + self._stats["total_deposited"]
                          - self._stats["total_withdrawn"])

        results = dict(self._stats)
        results.update({
            "users": self.num_users,
            "operations_per_user": self.operations_per_user,
            "opening_total": opening_total,
            "closing_total": closing_total,
            "expected_total": expected_total,
            "difference": closing_total - expected_total,
            "duration": duration,
            "stuck_threads": stuck,
            "consistent": closing_total == expected_total and not stuck,
        })
        return results

    @staticmethod
    def print_results(results):
        """Print a results dictionary in a readable form."""
        print(f"Users (threads)        : {results['users']}")
        print(f"Operations per user    : {results['operations_per_user']}")
        print(f"Deposits               : {results['deposits']}")
        print(f"Withdrawals            : {results['withdrawals']} "
              f"({results['failed_withdrawals']} declined)")
        print(f"Transfers              : {results['transfers']} "
              f"({results['failed_transfers']} declined)")
        print(f"Total deposited        : {results['total_deposited']}")
        print(f"Total withdrawn        : {results['total_withdrawn']}")
        print(f"Opening total          : {results['opening_total']}")
        print(f"Expected closing total : {results['expected_total']}")
        print(f"Actual closing total   : {results['closing_total']}")
        print(f"Difference             : {results['difference']}")
        print(f"Threads still running  : {len(results['stuck_threads'])}")
        print(f"Time taken             : {results['duration']:.3f} seconds")
        print(f"RESULT                 : "
              f"{'PASS - balances agree' if results['consistent'] else 'FAIL'}")
