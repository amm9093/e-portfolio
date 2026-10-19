"""
deadlock_experiment.py
======================
Evidence for the two locking decisions made in this project.

This file is NOT part of the banking system. It contains deliberately faulty
versions of the code so that the two problems described in the report can be
observed rather than merely claimed.

Run with:   python deadlock_experiment.py

Experiment A: a plain Lock instead of an RLock makes transfer() block against
              itself, because transfer() holds the lock and then calls
              withdraw(), which tries to take the same lock again.

Experiment B: locking the source account first and the target second causes a
              deadlock as soon as two transfers run in opposite directions.
              Sorting the accounts before locking removes the problem.
"""

import threading
import time

LINE = "=" * 66


# ---------------------------------------------------------------------------
# Experiment A: plain Lock vs RLock
# ---------------------------------------------------------------------------
class PlainLockAccount:
    """An account using threading.Lock (NOT re-entrant)."""

    def __init__(self, number, balance):
        self.number = number
        self.balance = balance
        self.lock = threading.Lock()

    def withdraw(self, amount):
        # acquire(timeout=2) is used instead of a plain 'with' so that the
        # experiment reports the problem instead of hanging for ever.
        if not self.lock.acquire(timeout=2):
            raise TimeoutError("withdraw() could not acquire the lock")
        try:
            self.balance -= amount
        finally:
            self.lock.release()


def experiment_a():
    """Show that a non-re-entrant lock blocks transfer() against itself."""
    print(LINE)
    print("EXPERIMENT A: threading.Lock vs threading.RLock")
    print(LINE)

    account = PlainLockAccount("ACC001", 1000)

    # This is what Bank.transfer() does: hold the account lock, then call
    # withdraw(), which needs the same lock again.
    with account.lock:
        try:
            account.withdraw(100)
            print("Plain Lock  : withdraw() succeeded (unexpected)")
            result_a = False
        except TimeoutError as error:
            print(f"Plain Lock  : FAILED - {error}")
            print("              The thread is waiting for a lock it already")
            print("              holds. This is self-deadlock.")
            result_a = True

    # The same situation with a re-entrant lock.
    rlock = threading.RLock()
    with rlock:
        acquired_again = rlock.acquire(timeout=2)
        if acquired_again:
            rlock.release()
    print(f"RLock       : re-acquired by the same thread = {acquired_again}")
    print("DECISION    : RLock is used in Account, so transfer() can hold the")
    print("              lock and still call withdraw() and deposit().\n")
    return result_a and acquired_again


# ---------------------------------------------------------------------------
# Experiment B: unordered locking vs ordered locking
# ---------------------------------------------------------------------------
class SimpleAccount:
    """A minimal account used by both transfer versions below."""

    def __init__(self, number, balance):
        self.number = number
        self.balance = balance
        self.lock = threading.RLock()


def unsafe_transfer(source, target, amount):
    """FAULTY: locks the source first, then the target.

    Two threads transferring in opposite directions each hold one lock and
    wait for the other, which is a circular wait - a deadlock.
    """
    if not source.lock.acquire(timeout=3):
        raise TimeoutError(f"could not lock {source.number}")
    try:
        time.sleep(0.01)          # widen the window so the race is reliable
        if not target.lock.acquire(timeout=3):
            raise TimeoutError(f"DEADLOCK: holding {source.number}, "
                               f"cannot get {target.number}")
        try:
            source.balance -= amount
            target.balance += amount
        finally:
            target.lock.release()
    finally:
        source.lock.release()


def safe_transfer(source, target, amount):
    """CORRECT: sorts the accounts, so every thread locks in the same order."""
    first, second = sorted([source, target], key=lambda a: a.number)
    if not first.lock.acquire(timeout=3):
        raise TimeoutError(f"could not lock {first.number}")
    try:
        time.sleep(0.01)          # the same delay as above, for a fair test
        if not second.lock.acquire(timeout=3):
            raise TimeoutError(f"could not lock {second.number}")
        try:
            source.balance -= amount
            target.balance += amount
        finally:
            second.lock.release()
    finally:
        first.lock.release()


def run_opposite_transfers(transfer_function):
    """Run two transfers in opposite directions and report any failure."""
    alice = SimpleAccount("ACC001", 1000)
    bob = SimpleAccount("ACC002", 1000)
    problems = []
    problems_lock = threading.Lock()

    def worker(source, target):
        try:
            transfer_function(source, target, 100)
        except TimeoutError as error:
            with problems_lock:
                problems.append(str(error))

    threads = [
        threading.Thread(target=worker, args=(alice, bob)),   # A -> B
        threading.Thread(target=worker, args=(bob, alice)),   # B -> A
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    total = alice.balance + bob.balance
    return problems, total


def experiment_b():
    """Compare unordered and ordered locking under opposite transfers."""
    print(LINE)
    print("EXPERIMENT B: unordered locking vs ordered locking")
    print(LINE)

    problems, total = run_opposite_transfers(unsafe_transfer)
    print(f"Unordered locking : {len(problems)} thread(s) blocked")
    for problem in problems:
        print(f"                    {problem}")
    print(f"                    total in the two accounts: {total}")
    unsafe_deadlocked = len(problems) > 0

    problems, total = run_opposite_transfers(safe_transfer)
    print(f"Ordered locking   : {len(problems)} thread(s) blocked")
    print(f"                    total in the two accounts: {total}")
    safe_completed = len(problems) == 0 and total == 2000

    print("DECISION          : Bank.transfer() sorts the two accounts by")
    print("                    account number before locking.\n")
    return unsafe_deadlocked and safe_completed


if __name__ == "__main__":
    print("\nEvidence for the locking decisions in Bank.transfer()\n")
    a_passed = experiment_a()
    b_passed = experiment_b()
    print(LINE)
    print("SUMMARY")
    print(LINE)
    print(f"  Experiment A (RLock required)        : "
          f"{'demonstrated' if a_passed else 'not reproduced'}")
    print(f"  Experiment B (ordered locking needed): "
          f"{'demonstrated' if b_passed else 'not reproduced'}")
