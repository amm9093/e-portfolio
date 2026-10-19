"""
strategies.py
=============
STRATEGY PATTERN - interchangeable algorithms chosen at runtime.

Two families of strategy are used by the payment service:

    FeeStrategy    - pricing rules: how much a transfer costs.
    RiskPolicy     - AI decision logic: what to do with a fraud score.

The context (PaymentService in payments.py) holds a reference to one
strategy of each family and can swap it while the system is running, e.g.
switch to a promotional "no fee" weekend without redeploying, or tighten the
risk policy during a fraud wave.

Why Strategy rather than if/elif inside PaymentService?
    * Open/Closed: a new pricing rule is a new class, not an edit to the
      service - the service's tests never need to change.
    * Each rule is tiny and can be unit tested on its own.
    * The rule in force becomes an explicit, inspectable object instead of
      a buried branch, which also helps auditability.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum

from bank_account import CENT, validate_amount


# ---------------------------------------------------------------------------
# Family 1: pricing rules
# ---------------------------------------------------------------------------
class FeeStrategy(ABC):
    """Interface every pricing rule must satisfy."""

    @abstractmethod
    def calculate(self, amount):
        """Return the fee (Decimal, 2 d.p.) charged on a transfer of `amount`."""

    def __str__(self):
        return type(self).__name__


class NoFee(FeeStrategy):
    """Free transfers (e.g. internal transfers or a promotion)."""

    def calculate(self, amount):
        return Decimal("0.00")


class FlatFee(FeeStrategy):
    """A fixed charge regardless of the amount."""

    def __init__(self, fee):
        self._fee = validate_amount(fee, allow_zero=True)

    def calculate(self, amount):
        return self._fee


class PercentageFee(FeeStrategy):
    """A percentage of the amount, bounded by a minimum and a maximum.

    Args:
        rate: fraction of the amount, e.g. Decimal("0.015") for 1.5 %.
        minimum: fee is never below this.
        maximum: fee is never above this (None = no cap).
    """

    def __init__(self, rate, minimum="0.00", maximum=None):
        self._rate = Decimal(str(rate))
        if self._rate < 0 or self._rate > 1:
            raise ValueError("rate must be between 0 and 1")
        self._minimum = validate_amount(minimum, allow_zero=True)
        self._maximum = None if maximum is None else validate_amount(maximum)

    def calculate(self, amount):
        amount = validate_amount(amount)
        fee = (amount * self._rate).quantize(CENT)
        fee = max(fee, self._minimum)
        if self._maximum is not None:
            fee = min(fee, self._maximum)
        return fee


class TieredFee(FeeStrategy):
    """Cheaper per-pound pricing for larger transfers.

    `tiers` is a list of (upper_limit, rate) pairs in ascending order; the
    rate that applies is the first tier whose limit the amount does not
    exceed. The final tier should use None as its limit (no upper bound).
    """

    def __init__(self, tiers):
        if not tiers or tiers[-1][0] is not None:
            raise ValueError("last tier must have limit None")
        self._tiers = [(None if lim is None else validate_amount(lim),
                        Decimal(str(rate))) for lim, rate in tiers]

    def calculate(self, amount):
        amount = validate_amount(amount)
        for limit, rate in self._tiers:
            if limit is None or amount <= limit:
                return (amount * rate).quantize(CENT)
        return Decimal("0.00")  # unreachable, kept for safety


# ---------------------------------------------------------------------------
# Family 2: AI decision logic
# ---------------------------------------------------------------------------
class Action(Enum):
    """What the payment service does with a screened transaction."""
    ALLOW = "allow"
    REVIEW = "review"      # queue for a human; money is not moved
    BLOCK = "block"


class RiskPolicy(ABC):
    """Turns a fraud score in [0, 1] into an Action.

    The *model* produces a probability; the *policy* decides what the
    business does with it. Keeping the two apart means the thresholds can be
    changed (or audited) without touching the model, and the model can be
    swapped without touching the thresholds.
    """

    @abstractmethod
    def decide(self, score):
        """Map a score (Decimal or float in [0, 1]) to an Action."""

    @staticmethod
    def _check(score):
        score = Decimal(str(score))
        if not score.is_finite() or score < 0 or score > 1:
            raise ValueError(f"score must be in [0, 1], got {score}")
        return score

    def __str__(self):
        return type(self).__name__


class ThresholdPolicy(RiskPolicy):
    """Two thresholds: below `review` allow, below `block` review, else block."""

    def __init__(self, review="0.40", block="0.80"):
        self._review = Decimal(str(review))
        self._block = Decimal(str(block))
        if not 0 <= self._review <= self._block <= 1:
            raise ValueError("need 0 <= review <= block <= 1")

    def decide(self, score):
        score = self._check(score)
        if score >= self._block:
            return Action.BLOCK
        if score >= self._review:
            return Action.REVIEW
        return Action.ALLOW


class ConservativePolicy(ThresholdPolicy):
    """Used during a fraud wave: review early, block early."""

    def __init__(self):
        super().__init__(review="0.20", block="0.60")


class ReviewEverythingPolicy(RiskPolicy):
    """Fail-safe policy for when the model cannot be trusted: a human looks
    at every transaction. Nothing is auto-allowed and nothing is auto-blocked."""

    def decide(self, score):
        self._check(score)
        return Action.REVIEW
