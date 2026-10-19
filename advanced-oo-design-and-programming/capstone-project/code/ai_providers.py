"""
ai_providers.py
===============
ABSTRACT FACTORY - a *family* of related AI objects that must be used
together, created by one factory so they can never be mismatched.

The payment service needs two products from its AI provider:

    FraudScorer   - score(features) -> probability of fraud in [0, 1]
    Explainer     - explain(features, score) -> human-readable reason

A score from provider A explained by provider B's explainer would be
meaningless, so the pair is created by one AIServiceFactory. Switching the
whole system from the local rule-based provider to a remote model provider
is a one-line change where the factory is chosen; nothing else is touched.

    RuleBasedFactory     - deterministic heuristics, runs offline. Also the
                           fallback when the remote provider is down.
    RemoteModelFactory   - talks to a hosted model through an injected
                           `client`. In this coursework no live API exists,
                           so the client is a Mock in the tests; this is
                           exactly how AI-dependent code is made testable.

Why Abstract Factory rather than a plain factory function?
    * It guarantees a consistent family (scorer + explainer) - a single
      factory method would only guarantee one product.
    * Dependency inversion: PaymentService depends on the abstract factory,
      not on any provider, so providers can be added (or mocked) freely.
"""

from abc import ABC, abstractmethod
from decimal import Decimal


class ProviderUnavailableError(RuntimeError):
    """Raised when a remote AI provider cannot be reached."""


# ---------------------------------------------------------------------------
# Abstract products
# ---------------------------------------------------------------------------
class FraudScorer(ABC):
    @abstractmethod
    def score(self, features):
        """Return Decimal in [0, 1]: estimated probability of fraud."""


class Explainer(ABC):
    @abstractmethod
    def explain(self, features, score):
        """Return a short human-readable justification for `score`."""


# ---------------------------------------------------------------------------
# Abstract factory
# ---------------------------------------------------------------------------
class AIServiceFactory(ABC):
    """Creates a matching scorer/explainer pair."""

    @property
    @abstractmethod
    def provider_name(self):
        """Short name used in audit records."""

    @abstractmethod
    def create_scorer(self):
        """Return a FraudScorer."""

    @abstractmethod
    def create_explainer(self):
        """Return an Explainer that understands this provider's scores."""


# ---------------------------------------------------------------------------
# Concrete family 1: rule-based, runs locally, fully deterministic
# ---------------------------------------------------------------------------
RULES = (
    # (feature, threshold, weight, explanation)
    ("amount_to_balance_ratio", 0.9, Decimal("0.55"), "amount is almost the whole balance"),
    ("amount_to_balance_ratio", 0.5, Decimal("0.20"), "amount is over half the balance"),
    ("is_round_amount", 1.0, Decimal("0.10"), "suspiciously round amount"),
    ("withdrawals_so_far", 25, Decimal("0.15"), "unusually many withdrawals"),
)


class RuleBasedScorer(FraudScorer):
    """Adds a fixed weight for every rule that fires, capped at 1."""

    def score(self, features):
        total = Decimal("0.00")
        for feature, threshold, weight, _ in RULES:
            if features.get(feature, 0) >= threshold:
                total += weight
        if features.get("same_owner", 0.0) >= 1.0:
            total -= Decimal("0.30")          # moving money between own accounts
        return max(Decimal("0.00"), min(Decimal("1.00"), total))


class RuleBasedExplainer(Explainer):
    def explain(self, features, score):
        fired = [text for feature, threshold, _, text in RULES
                 if features.get(feature, 0) >= threshold]
        if features.get("same_owner", 0.0) >= 1.0:
            fired.append("counterparty is the same owner (reduces risk)")
        reason = "; ".join(fired) if fired else "no rule triggered"
        return f"rule-based score {score}: {reason}"


class RuleBasedFactory(AIServiceFactory):
    provider_name = "rules-v1"

    def create_scorer(self):
        return RuleBasedScorer()

    def create_explainer(self):
        return RuleBasedExplainer()


# ---------------------------------------------------------------------------
# Concrete family 2: remote hosted model behind an injected client
# ---------------------------------------------------------------------------
class RemoteModelScorer(FraudScorer):
    """Sends the features to a hosted model via `client.predict(payload)`.

    The client is any object with predict() and explain() methods. Nothing
    here imports a network library: the scorer is pure translation logic,
    which is what makes it unit-testable with a mock client.
    """

    def __init__(self, client, model_name):
        self._client = client
        self._model_name = model_name

    def score(self, features):
        try:
            response = self._client.predict({"model": self._model_name,
                                             "features": features})
        except (ConnectionError, TimeoutError, OSError) as err:
            raise ProviderUnavailableError(str(err)) from err
        score = Decimal(str(response["probability"]))
        if not 0 <= score <= 1:
            raise ValueError(f"provider returned invalid probability {score}")
        return score


class RemoteExplainer(Explainer):
    def __init__(self, client, model_name):
        self._client = client
        self._model_name = model_name

    def explain(self, features, score):
        try:
            response = self._client.explain({"model": self._model_name,
                                             "features": features,
                                             "probability": str(score)})
        except (ConnectionError, TimeoutError, OSError) as err:
            raise ProviderUnavailableError(str(err)) from err
        return f"{self._model_name} score {score}: {response['reason']}"


class RemoteModelFactory(AIServiceFactory):
    def __init__(self, client, model_name="fraud-xgb"):
        self._client = client
        self._model_name = model_name

    @property
    def provider_name(self):
        return f"remote:{self._model_name}"

    def create_scorer(self):
        return RemoteModelScorer(self._client, self._model_name)

    def create_explainer(self):
        return RemoteExplainer(self._client, self._model_name)


class OfflineClient:
    """Default client used when no real endpoint is configured: it refuses
    every call so that the fallback path is exercised rather than a fake
    result being silently trusted."""

    def predict(self, payload):
        raise ConnectionError("no AI endpoint configured in this environment")

    def explain(self, payload):
        raise ConnectionError("no AI endpoint configured in this environment")
