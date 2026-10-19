"""
demo_patterns.py
================
Demonstrations 5-9: the design-pattern artefacts, run end to end.

    python demo_patterns.py          # all five
    python demo_patterns.py 7 8      # a selection

Demonstrations 1-4 (thread safety and deadlock prevention) are in main.py.
"""

import logging
import random
import threading
from decimal import Decimal

from ai_providers import OfflineClient, RemoteModelFactory, RuleBasedFactory
from bank import Bank
from bank_account import (BankAccount, CurrentAccount, InsufficientFundsError,
                          SavingsAccount)
from decorators import (Authoriser, LoggingAccount, PermissionDeniedError,
                        SecuredAccount)
from ml_platform import ModelRegistry, standard_features
from payments import MODEL_NAME, PaymentService, TransactionBlockedError
from strategies import (Action, ConservativePolicy, FlatFee, NoFee,
                        PercentageFee, ThresholdPolicy, TieredFee)
from visitors import (InterestProjectionVisitor, RiskExposureVisitor,
                      StatementVisitor, apply)


def banner(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def build_platform(bank):
    """Registry with the rule-based provider live, plus the feature store."""
    registry = ModelRegistry()
    v1 = registry.register(MODEL_NAME, RuleBasedFactory(),
                           metadata={"type": "rules"}, who="demo")
    registry.promote(MODEL_NAME, v1, who="demo")
    fees = bank.open_account("Bank fees", 0)
    return registry, standard_features(), fees


# ---------------------------------------------------------------------------
def demo5_strategy():
    banner("DEMONSTRATION 5 - Strategy: pricing rules and AI decision policy")
    amount = Decimal("250.00")
    for strategy in (NoFee(), FlatFee("1.50"),
                     PercentageFee("0.015", minimum="0.50", maximum="10.00"),
                     TieredFee([("100", "0.02"), ("1000", "0.01"), (None, "0.005")])):
        print(f"  {str(strategy):<16} fee on {amount}: {strategy.calculate(amount)}")

    print("\n  Same score, different policy -> different action:")
    for score in ("0.15", "0.45", "0.70"):
        default = ThresholdPolicy().decide(score)
        strict = ConservativePolicy().decide(score)
        print(f"    score {score}: ThresholdPolicy -> {default.name:<6} "
              f"ConservativePolicy -> {strict.name}")

    bank = Bank("Strategy demo")
    registry, store, fees = build_platform(bank)
    alice = bank.open_account("Alice", 1000)
    bob = bank.open_account("Bob", 100)
    service = PaymentService(bank, registry, store, fees, fee_strategy=NoFee())
    service.pay(alice, bob, 50)
    print(f"\n  Pay 50 under NoFee        -> fee account {fees.get_balance()}")
    service.set_fee_strategy(PercentageFee("0.02"))      # swapped at runtime
    service.pay(alice, bob, 50)
    print(f"  Pay 50 under PercentageFee -> fee account {fees.get_balance()}  "
          f"(strategy swapped while running, no restart)")


# ---------------------------------------------------------------------------
def demo6_decorator():
    banner("DEMONSTRATION 6 - Decorator: logging and security layers")
    logging.basicConfig(level=logging.INFO, format="  [audit] %(message)s")
    logging.getLogger("bank.audit").setLevel(logging.INFO)
    bank = Bank("Decorator demo")
    auth = Authoriser()
    plain = bank.open_account("Alice", 500)
    alice = SecuredAccount(LoggingAccount(plain), auth, max_failures=2,
                           lockout_seconds=30)
    bob = LoggingAccount(bank.open_account("Bob", 100))

    print(f"  Stack: {alice}\n")
    auth.login("Mallory")
    for attempt in (1, 2, 3):
        try:
            alice.withdraw(100)
        except PermissionDeniedError as err:
            print(f"  attempt {attempt} as Mallory: DENIED - {err}")
    auth.login("Alice")
    try:
        alice.withdraw(100)
    except PermissionDeniedError as err:
        print(f"  attempt 4 as Alice:   DENIED - {err}  (lock-out still active)")

    print("\n  Bank.transfer() works unchanged through the decorators:")
    auth.logout()
    bank.transfer(bob, alice, 25)              # deposit needs no permission
    try:
        bob.withdraw(10000)
    except InsufficientFundsError:
        pass                                      # rejected call is still logged
    print(f"  Alice balance after Bob's transfer: {alice.get_balance()}")
    logging.getLogger("bank.audit").setLevel(logging.WARNING)
    logging.getLogger().handlers.clear()


# ---------------------------------------------------------------------------
def demo7_visitor():
    banner("DEMONSTRATION 7 - Visitor: reports without touching account classes")
    bank = Bank("Visitor demo")
    bank.open_account("Alice", 1200)
    bank.open_account("Bob", 5000, SavingsAccount, minimum_balance=500,
                      interest_rate="0.01")
    bank.open_account("Carol", 300, CurrentAccount, overdraft_limit=1000)
    dave = bank.open_account("Dave", 200, CurrentAccount, overdraft_limit=400)
    dave.withdraw(350)                                     # Dave goes overdrawn

    accounts = bank.get_all_accounts()
    print(apply(StatementVisitor(), accounts).result())
    risk = apply(RiskExposureVisitor(), accounts).result()
    print(f"\n  Risk exposure : {risk}")
    proj = apply(InterestProjectionVisitor(periods=12), accounts)
    print(f"  12-period interest projection: {proj.result()}  total {proj.total}")


# ---------------------------------------------------------------------------
def demo8_factory_registry():
    banner("DEMONSTRATION 8 - Abstract Factory + Model Registry + Feature Store")
    bank = Bank("Factory demo")
    registry, store, fees = build_platform(bank)
    alice = bank.open_account("Alice", 1000)
    bob = bank.open_account("Bob", 50)
    service = PaymentService(bank, registry, store, fees)

    print(f"  Feature schema: {store.schema()}")
    print(f"  Features for Alice->Bob 900: "
          f"{store.compute(alice, Decimal('900'), bob)}")

    print(f"\n  Live provider: {registry.production(MODEL_NAME)}")
    r = service.pay(alice, bob, 100)
    print(f"  pay 100 -> {r.action.name} score {r.score} via {r.provider}")
    r = service.pay(alice, bob, 850)
    print(f"  pay 850 -> {r.action.name} score {r.score} (queued for a human, "
          f"Alice still has {alice.get_balance()})")
    try:
        service.pay(alice, bob, 900)
    except TransactionBlockedError as err:
        print(f"  pay 900 -> BLOCKED: {err.receipt.explanation}")

    v2 = registry.register(MODEL_NAME, RemoteModelFactory(OfflineClient()),
                           metadata={"auc": 0.91, "features": store.schema()},
                           who="ml-team")
    registry.promote(MODEL_NAME, v2, who="ml-team")
    print(f"\n  Promoted {registry.production(MODEL_NAME)} - remote model, no endpoint here")
    r = service.pay(alice, bob, 100)
    print(f"  pay 100 -> {r.action.name} via {r.provider} degraded={r.degraded}")
    print(f"           {r.explanation}")

    registry.rollback(MODEL_NAME, who="on-call")
    print(f"\n  Rolled back to {registry.production(MODEL_NAME)}")
    print("  Audit trail:")
    for ts, event, name, version, who in registry.audit_trail():
        print(f"    {ts:%H:%M:%S}  {event:<9} {name} v{version}  by {who}")


# ---------------------------------------------------------------------------
def demo9_end_to_end():
    banner("DEMONSTRATION 9 - Concurrent payments through the whole stack")
    bank = Bank("Capstone")
    registry, store, fees = build_platform(bank)
    auth = Authoriser()
    customers = []
    for name in ("Alice", "Bob", "Carol", "Dave", "Erin", "Frank"):
        acct = bank.open_account(name, 1000, CurrentAccount, overdraft_limit=200)
        customers.append(SecuredAccount(LoggingAccount(acct), auth))
    service = PaymentService(bank, registry, store, fees,
                             fee_strategy=FlatFee("0.25"),
                             risk_policy=ThresholdPolicy())
    opening = bank.total_balance()
    counts = {a: 0 for a in Action}
    counts["funds"] = 0
    counts["denied"] = 0
    counts_lock = threading.Lock()
    start = threading.Barrier(len(customers))

    def session(me):
        rng = random.Random(me.owner)
        auth.login(me.owner)
        start.wait()
        for _ in range(60):
            target = rng.choice([c for c in customers if c is not me])
            amount = rng.choice([5, 20, 50, 100, 300])
            try:
                receipt = service.pay(me, target, amount)
                key = receipt.action
            except TransactionBlockedError:
                key = Action.BLOCK
            except InsufficientFundsError:
                key = "funds"
            except PermissionDeniedError:
                key = "denied"
            with counts_lock:
                counts[key] += 1

    threads = [threading.Thread(target=session, args=(c,), name=c.owner)
               for c in customers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    closing = bank.total_balance()
    print(f"  {len(threads)} threads x 60 payments: "
          f"ALLOW {counts[Action.ALLOW]}  REVIEW {counts[Action.REVIEW]}  "
          f"BLOCK {counts[Action.BLOCK]}  insufficient {counts['funds']}  "
          f"denied {counts['denied']}")
    print(f"  Fees collected: {fees.get_balance()}   review queue: "
          f"{len(service.review_queue())}")
    print(f"  Money in system: opening {opening} -> closing {closing}  "
          f"{'CONSERVED' if opening == closing else 'LOST!'}")
    print(f"  Receipts recorded: {len(service.receipts())} "
          f"(every decision is auditable)")


DEMOS = {"5": demo5_strategy, "6": demo6_decorator, "7": demo7_visitor,
         "8": demo8_factory_registry, "9": demo9_end_to_end}

if __name__ == "__main__":
    import sys
    logging.getLogger("bank.audit").setLevel(logging.WARNING)  # keep demo 9 quiet
    # python demo_patterns.py        -> all demonstrations
    # python demo_patterns.py 6 8    -> only the ones listed
    chosen = sys.argv[1:] or list(DEMOS)
    for number in chosen:
        DEMOS[number]()
