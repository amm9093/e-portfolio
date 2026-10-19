"""
ml_platform.py
==============
AI-ORIENTED OO PATTERNS - two small, honest implementations of
architectural patterns used in machine-learning systems.

    FeatureStore   - one place where the *features* fed to a model are
                     defined, named, versioned and computed. The fraud
                     scorer never reaches into an account itself; it receives
                     a plain dict of features. Training and serving therefore
                     use the same code, which is the whole point of a
                     feature store (training/serving skew is a leading cause
                     of silent ML failures - Sculley et al., 2015).

    ModelRegistry  - manages the lifecycle of models: register a version,
                     promote it through stages (staging -> production),
                     roll back, and always know which version is live and
                     who approved it. The payment service asks the registry
                     for "the production fraud model" and never hard-codes a
                     version.

Both are deliberately in-memory. The *interfaces* are what matter for the
design; a real deployment would back them with a database or MLflow.
"""

import threading
from datetime import datetime, timezone
from decimal import Decimal


# ---------------------------------------------------------------------------
# Feature Store
# ---------------------------------------------------------------------------
class FeatureStore:
    """Registry of named feature functions, computed on demand.

    A feature function takes (account, amount, counterparty) and returns a
    number. Registering a feature twice with the same name is an error, so
    a feature's meaning cannot silently change underneath a trained model.
    """

    def __init__(self):
        self._features = {}          # name -> (version, function)
        self._lock = threading.Lock()

    def register(self, name, func, version=1):
        with self._lock:
            if name in self._features:
                raise ValueError(f"feature {name!r} already registered; "
                                 f"register a new name or bump the version")
            self._features[name] = (version, func)

    def names(self):
        with self._lock:
            return sorted(self._features)

    def schema(self):
        """name -> version, so a model can record exactly what it was fed."""
        with self._lock:
            return {n: v for n, (v, _) in self._features.items()}

    def compute(self, account, amount, counterparty=None):
        """Return {feature_name: value} for one transaction."""
        with self._lock:
            items = list(self._features.items())
        return {name: func(account, amount, counterparty)
                for name, (_, func) in items}


def standard_features():
    """The feature set used by the fraud scorers in this project."""
    store = FeatureStore()

    def amount_to_balance_ratio(account, amount, _):
        balance = account.get_balance()
        if balance <= 0:
            return 1.0
        return float(Decimal(str(amount)) / balance)

    def withdrawals_so_far(account, amount, _):
        history = account.get_transaction_history()
        return sum(1 for h in history if h["type"] == "WITHDRAW")

    def largest_previous_withdrawal(account, amount, _):
        history = account.get_transaction_history()
        amounts = [h["amount"] for h in history if h["type"] == "WITHDRAW"]
        return float(max(amounts)) if amounts else 0.0

    def is_round_amount(account, amount, _):
        return 1.0 if Decimal(str(amount)) % 100 == 0 else 0.0

    def same_owner(account, amount, counterparty):
        if counterparty is None:
            return 0.0
        return 1.0 if counterparty.owner == account.owner else 0.0

    store.register("amount_to_balance_ratio", amount_to_balance_ratio)
    store.register("withdrawals_so_far", withdrawals_so_far)
    store.register("largest_previous_withdrawal", largest_previous_withdrawal)
    store.register("is_round_amount", is_round_amount)
    store.register("same_owner", same_owner)
    return store


# ---------------------------------------------------------------------------
# Model Registry
# ---------------------------------------------------------------------------
class ModelVersion:
    """An immutable record of one registered model version."""

    __slots__ = ("name", "version", "model", "metadata", "registered_at", "stage")

    def __init__(self, name, version, model, metadata):
        self.name = name
        self.version = version
        self.model = model                 # any object with .score(features)
        self.metadata = dict(metadata)     # e.g. {"auc": 0.91, "features": {...}}
        self.registered_at = datetime.now(timezone.utc)
        self.stage = "staging"

    def __repr__(self):
        return f"{self.name}:v{self.version} [{self.stage}]"


class ModelRegistry:
    """Versioned storage for models with a single live version per name."""

    STAGES = ("staging", "production", "archived")

    def __init__(self):
        self._models = {}            # name -> {version: ModelVersion}
        self._production = {}        # name -> version number
        self._audit = []             # (timestamp, event, name, version, who)
        self._lock = threading.RLock()

    def _log(self, event, name, version, who):
        self._audit.append((datetime.now(timezone.utc), event, name, version, who))

    def register(self, name, model, metadata=None, who="system"):
        """Add a new version of `name`; versions are never overwritten."""
        with self._lock:
            versions = self._models.setdefault(name, {})
            version = max(versions, default=0) + 1
            versions[version] = ModelVersion(name, version, model, metadata or {})
            self._log("register", name, version, who)
            return version

    def promote(self, name, version, who="system"):
        """Make `version` the production model, archiving the previous one."""
        with self._lock:
            record = self._models[name][version]      # KeyError if unknown
            previous = self._production.get(name)
            if previous is not None and previous != version:
                self._models[name][previous].stage = "archived"
            record.stage = "production"
            self._production[name] = version
            self._log("promote", name, version, who)

    def rollback(self, name, who="system"):
        """Return to the most recent archived version."""
        with self._lock:
            archived = [v for v, r in self._models[name].items()
                        if r.stage == "archived"]
            if not archived:
                raise LookupError(f"no archived version of {name!r} to roll back to")
            self.promote(name, max(archived), who=who)

    def production(self, name):
        """The live ModelVersion for `name`, or LookupError if none."""
        with self._lock:
            if name not in self._production:
                raise LookupError(f"no production model for {name!r}")
            return self._models[name][self._production[name]]

    def versions(self, name):
        with self._lock:
            return [self._models[name][v] for v in sorted(self._models.get(name, {}))]

    def audit_trail(self):
        with self._lock:
            return list(self._audit)
