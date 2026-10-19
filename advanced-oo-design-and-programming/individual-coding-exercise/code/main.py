"""
main.py
=======
Demonstration program for the thread-safe banking system.

Run with:   python main.py

Four demonstrations are produced, matching the sections of the report:
    1. Basic account operations and polymorphism
    2. Why locking is needed (a race condition, shown side by side)
    3. Concurrent transactions using TransactionSimulator
    4. Deadlock prevention with transfers in both directions
"""

import threading
import time
from decimal import Decimal

from bank import Bank
from bank_account import (BankAccount, CurrentAccount, InsufficientFundsError,
                          SavingsAccount)
from simulator import TransactionSimulator

LINE = "=" * 66


def title(text):
    """Print a section heading."""
    print("\n" + LINE)
    print(text)
    print(LINE)


# ---------------------------------------------------------------------------
# Demonstration 1: accounts and polymorphism
# ---------------------------------------------------------------------------
def demo_accounts():
    """Show the three account types following the same interface."""
    title("DEMONSTRATION 1: Account types and polymorphism")

    bank = Bank("Northgate Bank")
    accounts = [
        bank.open_account("Alice", 1000),
        bank.open_account("Bob", 1000, account_type=SavingsAccount,
                          minimum_balance=200, interest_rate="0.02"),
        bank.open_account("Carol", 1000, account_type=CurrentAccount,
                          overdraft_limit=300),
    ]

    rules = ["no overdraft allowed",
             "must keep 200.00 in the account",
             "overdraft of up to 300.00 allowed"]

    print("Every account starts with 1000.00 and is asked to withdraw 1100.00")
    print("through the SAME withdraw() call, but each applies its own rule:\n")
    for account, rule in zip(accounts, rules):
        try:
            account.withdraw(1100)
            result = f"ALLOWED, balance now {account.get_balance():>8}"
        except InsufficientFundsError:
            result = "REFUSED                    "
        print(f"  {type(account).__name__:<16} {account.account_number}  "
              f"{result}  ({rule})")

    savings = accounts[1]
    print(f"\nInterest added to savings account: {savings.add_interest()}")
    print(f"Bank total: {bank.total_balance()}")
    return True


# ---------------------------------------------------------------------------
# Demonstration 2: the race condition
# ---------------------------------------------------------------------------
class UnsafeAccount:
    """An account with NO lock. Used only to show what goes wrong.

    This class is deliberately broken and is not part of the banking system.
    """

    def __init__(self, balance=0):
        self.balance = Decimal(balance)

    def deposit(self, amount):
        current = self.balance     # 1. read
        time.sleep(0)              # 2. the thread may be swapped out here
        self.balance = current + amount   # 3. write back a stale value


def demo_race_condition():
    """Run the same workload with and without a lock and compare."""
    title("DEMONSTRATION 2: Why the lock is needed (race condition)")

    threads_count, per_thread = 8, 250
    expected = Decimal(threads_count * per_thread)

    def run(account, deposit_call):
        threads = [threading.Thread(target=deposit_call)
                   for _ in range(threads_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return account

    unsafe = UnsafeAccount(0)
    run(unsafe, lambda: [unsafe.deposit(Decimal("1.00"))
                         for _ in range(per_thread)])

    safe = BankAccount("Alice", 0)
    run(safe, lambda: [safe.deposit(1) for _ in range(per_thread)])

    print(f"{threads_count} threads each deposit 1.00, {per_thread} times.")
    print(f"Expected balance             : {expected}.00")
    print(f"Without a lock (UnsafeAccount): {unsafe.balance}  "
          f"<-- {expected - unsafe.balance} lost")
    print(f"With a lock (BankAccount)     : {safe.get_balance()}  <-- correct")
    print("\nThe GIL does not make this safe: 'balance = balance + amount' is")
    print("three separate steps and a thread can be interrupted between them.")
    return safe.get_balance() == expected


# ---------------------------------------------------------------------------
# Demonstration 3: concurrent transactions
# ---------------------------------------------------------------------------
def demo_simulation():
    """Run several users against the same accounts at the same time."""
    title("DEMONSTRATION 3: Concurrent transactions (TransactionSimulator)")

    bank = Bank("Northgate Bank")
    # Small opening balances so that some withdrawals are correctly declined.
    accounts = [bank.open_account(f"User{i + 1}", 200) for i in range(3)]

    simulator = TransactionSimulator(bank, accounts, num_users=5,
                                     operations_per_user=400)
    results = simulator.run()
    TransactionSimulator.print_results(results)

    print("\nFinal position of each account:")
    for account in accounts:
        print(f"  {account}")
    return results["consistent"]


# ---------------------------------------------------------------------------
# Demonstration 4: deadlock prevention
# ---------------------------------------------------------------------------
def demo_deadlock():
    """Transfer money in both directions at once - the deadlock scenario."""
    title("DEMONSTRATION 4: Deadlock prevention (transfers in both directions)")

    bank = Bank("Northgate Bank")
    alice = bank.open_account("Alice", 5000)
    bob = bank.open_account("Bob", 5000)
    opening = bank.total_balance()

    def transfer_loop(source, target):
        for _ in range(400):
            try:
                bank.transfer(source, target, 10)
            except InsufficientFundsError:
                pass

    threads = []
    for index in range(6):
        if index % 2 == 0:
            args = (alice, bob)          # Alice -> Bob
        else:
            args = (bob, alice)          # Bob -> Alice (opposite direction)
        threads.append(threading.Thread(target=transfer_loop, args=args,
                                        name=f"Transfer-{index + 1}"))

    started = time.time()
    for thread in threads:
        thread.start()

    stuck = []
    for thread in threads:
        thread.join(timeout=30)          # a deadlock would time out here
        if thread.is_alive():
            stuck.append(thread.name)
    duration = time.time() - started

    print(f"6 threads, 400 transfers each, 3 threads in each direction.")
    print(f"Alice                 : {alice.get_balance()}")
    print(f"Bob                   : {bob.get_balance()}")
    print(f"Opening total         : {opening}")
    print(f"Closing total         : {bank.total_balance()}")
    print(f"Threads still running : {len(stuck)}")
    print(f"Time taken            : {duration:.3f} seconds")

    passed = not stuck and bank.total_balance() == opening
    print(f"RESULT                : "
          f"{'PASS - no deadlock, money conserved' if passed else 'FAIL'}")
    return passed


# ---------------------------------------------------------------------------
def main():
    """Run every demonstration and print a summary."""
    print(LINE)
    print("THREAD-SAFE BANKING SYSTEM - DEMONSTRATION")
    print(LINE)

    demonstrations = [
        ("Account types and polymorphism", demo_accounts),
        ("Race condition comparison", demo_race_condition),
        ("Concurrent transactions", demo_simulation),
        ("Deadlock prevention", demo_deadlock),
    ]

    outcomes = [(name, function()) for name, function in demonstrations]

    title("SUMMARY")
    for name, passed in outcomes:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")


if __name__ == "__main__":
    main()
