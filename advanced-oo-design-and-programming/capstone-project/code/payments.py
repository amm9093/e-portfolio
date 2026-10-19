"""
payments.py
===========
PaymentService - the Capstone "context" that composes every pattern:

    Bank (Facade, ordered locking)      - moves the money
    FeeStrategy / RiskPolicy (Strategy) - pricing rule and AI decision rule
    AIServiceFactory (Abstract Factory) - scorer + explainer family
    ModelRegistry                       - which provider family is live
    FeatureStore                        - what the model is fed
    Decorators                          - applied by the caller to accounts

A payment is: compute features -> score with the production provider ->
apply the risk policy -> ALLOW (move money and charge fee atomically),
REVIEW (queue for a human) or BLOCK (refuse).

Every outcome is recorded as a Receipt, which carries the provider name,
the score and the explanation. That is the auditability requirement:
a regulator can ask "why was this payment blocked on 3 October?" and the
answer is in the receipt, not lost inside a model.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from ai_providers import ProviderUnavailableError, RuleBasedFactory
from bank import ordered_locks
from bank_account import BankError, validate_amount
from strategies import Action, NoFee, ThresholdPolicy

MODEL_NAME = "fraud-screening"


class TransactionBlockedError(BankError):
    """Raised when the risk policy blocks a payment."""

    def __init__(self, receipt):
        super().__init__(f"payment blocked: {receipt.explanation}")
        self.receipt = receipt


@dataclass(frozen=True)
class Receipt:
    """Immutable record of one screening decision."""
    source: str
    target: str
    amount: Decimal
    fee: Decimal
    score: Decimal
    action: Action
    provider: str
    explanation: str
    degraded: bool = False          # True when the fallback provider was used
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PaymentService:
    """Screens and executes payments. Strategies can be swapped at runtime."""

    def __init__(self, bank, registry, feature_store, fee_account,
                 fee_strategy=None, risk_policy=None, fallback_factory=None):
        self._bank = bank
        self._registry = registry
        self._features = feature_store
        self._fee_account = fee_account
        self._fee_strategy = fee_strategy or NoFee()
        self._risk_policy = risk_policy or ThresholdPolicy()
        self._fallback = fallback_factory or RuleBasedFactory()
        self._review_queue = []
        self._receipts = []
        self._lock = threading.Lock()        # protects the two lists + strategies

    # -- Strategy pattern: swap the algorithms while running ----------------
    def set_fee_strategy(self, strategy):
        with self._lock:
            self._fee_strategy = strategy

    def set_risk_policy(self, policy):
        with self._lock:
            self._risk_policy = policy

    @property
    def fee_strategy(self):
        with self._lock:
            return self._fee_strategy

    @property
    def risk_policy(self):
        with self._lock:
            return self._risk_policy

    # -- Screening -----------------------------------------------------------
    def _score(self, features):
        """Return (score, explanation, provider_name, degraded)."""
        factory = self._registry.production(MODEL_NAME).model
        try:
            score = factory.create_scorer().score(features)
            explanation = factory.create_explainer().explain(features, score)
            return score, explanation, factory.provider_name, False
        except ProviderUnavailableError as err:
            # Fail SAFE, not open: fall back to the deterministic provider
            # and mark the receipt so the degraded decision is visible later.
            fallback = self._fallback
            score = fallback.create_scorer().score(features)
            explanation = (f"{fallback.create_explainer().explain(features, score)} "
                           f"[fallback: {factory.provider_name} unavailable - {err}]")
            return score, explanation, fallback.provider_name, True

    def pay(self, source, target, amount):
        """Screen, then move `amount` from source to target plus the fee.

        Returns a Receipt. Raises TransactionBlockedError when blocked,
        and the usual Bank errors when the funds are not there.
        """
        amount = validate_amount(amount)
        features = self._features.compute(source, amount, target)
        score, explanation, provider, degraded = self._score(features)

        with self._lock:
            policy, pricing = self._risk_policy, self._fee_strategy
        action = policy.decide(score)
        fee = pricing.calculate(amount) if action is Action.ALLOW else Decimal("0.00")

        receipt = Receipt(source.account_number, target.account_number, amount,
                          fee, score, action, provider, explanation, degraded)

        if action is Action.BLOCK:
            self._remember(receipt)
            raise TransactionBlockedError(receipt)

        if action is Action.REVIEW:
            with self._lock:
                self._review_queue.append(receipt)
            self._remember(receipt)
            return receipt

        # ALLOW: amount and fee leave the source together or not at all.
        # ordered_locks() holds all three accounts in the global order, and
        # Bank.transfer() re-enters the same (re-entrant) locks safely.
        with ordered_locks(source, target, self._fee_account):
            source.withdraw(amount + fee)        # one atomic check-and-debit
            target.deposit(amount)
            if fee > 0:
                self._fee_account.deposit(fee)
        self._remember(receipt)
        return receipt

    # -- Audit ---------------------------------------------------------------
    def _remember(self, receipt):
        with self._lock:
            self._receipts.append(receipt)

    def receipts(self):
        with self._lock:
            return list(self._receipts)

    def review_queue(self):
        with self._lock:
            return list(self._review_queue)
