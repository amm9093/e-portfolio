"""
test_patterns.py
================
Unit tests for the design-pattern artefacts (test cases P01-P30).

    python -m unittest test_patterns.py -v

Sections
    TestStrategy        P01-P06   pricing rules and AI decision policies
    TestDecorator       P07-P12   logging and security layers
    TestVisitor         P13-P16   reports over the account hierarchy
    TestAbstractFactory P17-P20   provider families
    TestMLPlatform      P21-P24   feature store and model registry
    TestWithMocks       P25-P30   isolating AI-dependent code with unittest.mock

The last section is the important one for AI-readiness: PaymentService
depends on a remote model that does not exist in this environment. Mocks
stand in for it, so the service's *behaviour* (block, review, fall back)
is tested exhaustively without a network, a GPU or a model file.
"""

import logging
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, Mock, call, patch

from ai_providers import (AIServiceFactory, Explainer, FraudScorer,
                          OfflineClient, ProviderUnavailableError,
                          RemoteModelFactory, RemoteModelScorer,
                          RuleBasedFactory, RuleBasedScorer)
from bank import Bank
from bank_account import (BankAccount, CurrentAccount, InsufficientFundsError,
                          SavingsAccount)
from decorators import (AccountDecorator, Authoriser, LoggingAccount,
                        PermissionDeniedError, SecuredAccount)
from ml_platform import FeatureStore, ModelRegistry, standard_features
from payments import MODEL_NAME, PaymentService, TransactionBlockedError
from strategies import (Action, ConservativePolicy, FlatFee, NoFee,
                        PercentageFee, ReviewEverythingPolicy, ThresholdPolicy,
                        TieredFee)
from visitors import (InterestProjectionVisitor, RiskExposureVisitor,
                      StatementVisitor, apply)


def make_service(bank, factory=None, **kwargs):
    """A PaymentService with `factory` (default rule-based) in production."""
    registry = ModelRegistry()
    version = registry.register(MODEL_NAME, factory or RuleBasedFactory())
    registry.promote(MODEL_NAME, version)
    fees = bank.open_account("fees", 0)
    return PaymentService(bank, registry, standard_features(), fees, **kwargs), fees


# ===========================================================================
class TestStrategy(unittest.TestCase):

    def test_P01_each_fee_strategy_prices_the_same_amount_differently(self):
        amount = Decimal("250.00")
        self.assertEqual(NoFee().calculate(amount), Decimal("0.00"))
        self.assertEqual(FlatFee("1.50").calculate(amount), Decimal("1.50"))
        self.assertEqual(PercentageFee("0.015").calculate(amount), Decimal("3.75"))
        tiered = TieredFee([("100", "0.02"), ("1000", "0.01"), (None, "0.005")])
        self.assertEqual(tiered.calculate(amount), Decimal("2.50"))

    def test_P02_percentage_fee_respects_minimum_and_cap(self):
        fee = PercentageFee("0.01", minimum="1.00", maximum="5.00")
        self.assertEqual(fee.calculate("10"), Decimal("1.00"))     # floor
        self.assertEqual(fee.calculate("300"), Decimal("3.00"))    # 1 %
        self.assertEqual(fee.calculate("9000"), Decimal("5.00"))   # cap

    def test_P03_threshold_policy_maps_score_to_action(self):
        policy = ThresholdPolicy(review="0.40", block="0.80")
        self.assertIs(policy.decide("0.39"), Action.ALLOW)
        self.assertIs(policy.decide("0.40"), Action.REVIEW)
        self.assertIs(policy.decide("0.80"), Action.BLOCK)

    def test_P04_policy_rejects_scores_outside_unit_interval(self):
        with self.assertRaises(ValueError):
            ThresholdPolicy().decide("1.5")
        with self.assertRaises(ValueError):
            ThresholdPolicy().decide("nan")

    def test_P05_same_score_different_policy_different_action(self):
        self.assertIs(ThresholdPolicy().decide("0.70"), Action.REVIEW)
        self.assertIs(ConservativePolicy().decide("0.70"), Action.BLOCK)
        self.assertIs(ReviewEverythingPolicy().decide("0.01"), Action.REVIEW)

    def test_P06_fee_strategy_can_be_swapped_at_runtime(self):
        bank = Bank()
        service, fees = make_service(bank, fee_strategy=NoFee())
        alice = bank.open_account("Alice", 1000)
        bob = bank.open_account("Bob", 1000)
        service.pay(alice, bob, 10)
        self.assertEqual(fees.get_balance(), Decimal("0.00"))
        service.set_fee_strategy(FlatFee("2.00"))
        service.pay(alice, bob, 10)
        self.assertEqual(fees.get_balance(), Decimal("2.00"))
        self.assertEqual(alice.get_balance(), Decimal("978.00"))   # 1000-10-10-2


# ===========================================================================
class TestDecorator(unittest.TestCase):

    def setUp(self):
        self.bank = Bank()
        self.inner = self.bank.open_account("Alice", 100)
        self.auth = Authoriser()

    def test_P07_decorator_forwards_untouched_operations(self):
        wrapped = AccountDecorator(self.inner)
        wrapped.deposit(50)
        self.assertEqual(wrapped.get_balance(), Decimal("150.00"))
        self.assertEqual(wrapped.account_number, self.inner.account_number)
        self.assertIs(wrapped.lock, self.inner.lock)

    def test_P08_logging_decorator_logs_success_and_rejection(self):
        logger = MagicMock()                       # no real log output needed
        acct = LoggingAccount(self.inner, logger)
        acct.deposit(25)
        with self.assertRaises(InsufficientFundsError):
            acct.withdraw(1000)
        logger.info.assert_called_once()
        logger.warning.assert_called_once()
        self.assertIn("REJECTED", logger.warning.call_args.args[0])

    def test_P09_secured_decorator_denies_other_users(self):
        acct = SecuredAccount(self.inner, self.auth)
        self.auth.login("Mallory")
        with self.assertRaises(PermissionDeniedError):
            acct.withdraw(10)
        self.assertEqual(acct.get_balance(), Decimal("100.00"))   # untouched
        self.auth.login("Alice")
        acct.withdraw(10)
        self.assertEqual(acct.get_balance(), Decimal("90.00"))

    def test_P10_secured_decorator_locks_out_after_repeated_failures(self):
        acct = SecuredAccount(self.inner, self.auth, max_failures=2,
                              lockout_seconds=60)
        self.auth.login("Mallory")
        for _ in range(2):
            with self.assertRaises(PermissionDeniedError):
                acct.withdraw(1)
        self.assertTrue(acct.is_locked_out)
        self.auth.login("Alice")                  # even the owner must wait
        with self.assertRaises(PermissionDeniedError):
            acct.withdraw(1)

    def test_P11_decorators_stack_and_bank_transfer_still_works(self):
        logger = MagicMock()
        alice = SecuredAccount(LoggingAccount(self.inner, logger), self.auth)
        bob = self.bank.open_account("Bob", 50)
        self.auth.login("Alice")
        self.bank.transfer(alice, bob, 30)
        self.assertEqual(bob.get_balance(), Decimal("80.00"))
        self.assertEqual(alice.unwrapped, self.inner)
        logger.info.assert_called_once()           # the withdraw was logged

    def test_P12_visitor_sees_through_decorators(self):
        alice = LoggingAccount(SecuredAccount(self.inner, self.auth))
        report = apply(StatementVisitor(), [alice]).result()
        self.assertIn("BankAccount", report)
        self.assertNotIn("LoggingAccount", report)


# ===========================================================================
class TestVisitor(unittest.TestCase):

    def setUp(self):
        self.bank = Bank()
        self.bank.open_account("A", 100)
        self.bank.open_account("B", 1000, SavingsAccount, minimum_balance=100,
                               interest_rate="0.10")
        self.current = self.bank.open_account("C", 50, CurrentAccount,
                                              overdraft_limit=200)
        self.accounts = self.bank.get_all_accounts()

    def test_P13_statement_visitor_dispatches_by_type(self):
        text = apply(StatementVisitor(), self.accounts).result()
        self.assertEqual(len(text.splitlines()), 3)
        self.assertIn("rate 10.00%", text)
        self.assertIn("overdraft limit 200.00", text)

    def test_P14_risk_visitor_finds_overdrawn_accounts(self):
        self.current.withdraw(120)                 # balance -70
        risk = apply(RiskExposureVisitor(), self.accounts).result()
        self.assertEqual(risk["overdraft_capacity"], Decimal("200.00"))
        self.assertEqual(risk["overdrawn_accounts"],
                         [(self.current.account_number, Decimal("-70.00"))])
        self.assertEqual(risk["total_balance"], Decimal("1030.00"))

    def test_P15_interest_projection_only_counts_savings(self):
        proj = apply(InterestProjectionVisitor(periods=2), self.accounts)
        self.assertEqual(len(proj.result()), 1)
        self.assertEqual(proj.total, Decimal("210.00"))   # 1000*1.1^2 - 1000

    def test_P16_new_report_needs_no_change_to_account_classes(self):
        class CountVisitor(StatementVisitor):       # a brand-new analysis
            def __init__(self):
                self.n = 0
            def visit_bank_account(self, a): self.n += 1
            def visit_savings_account(self, a): self.n += 1
            def visit_current_account(self, a): self.n += 1
        self.assertEqual(apply(CountVisitor(), self.accounts).n, 3)


# ===========================================================================
class TestAbstractFactory(unittest.TestCase):

    def test_P17_rule_based_family_is_consistent(self):
        factory = RuleBasedFactory()
        self.assertIsInstance(factory.create_scorer(), FraudScorer)
        self.assertIsInstance(factory.create_explainer(), Explainer)
        features = {"amount_to_balance_ratio": 0.95, "is_round_amount": 1.0}
        score = factory.create_scorer().score(features)
        self.assertEqual(score, Decimal("0.85"))
        self.assertIn("almost the whole balance",
                      factory.create_explainer().explain(features, score))

    def test_P18_score_is_always_clamped_to_unit_interval(self):
        self.assertEqual(RuleBasedScorer().score({}), Decimal("0.00"))
        self.assertEqual(RuleBasedScorer().score({"same_owner": 1.0}),
                         Decimal("0.00"))                      # not negative

    def test_P19_remote_family_without_endpoint_raises_provider_error(self):
        factory = RemoteModelFactory(OfflineClient())
        with self.assertRaises(ProviderUnavailableError):
            factory.create_scorer().score({})

    def test_P20_switching_provider_is_one_line(self):
        bank = Bank()
        service, _ = make_service(bank, factory=RuleBasedFactory())
        alice, bob = bank.open_account("A", 1000), bank.open_account("B", 0)
        self.assertEqual(service.pay(alice, bob, 1).provider, "rules-v1")
        # Promote a different family; the service code is untouched.
        client = Mock()
        client.predict.return_value = {"probability": 0.05}
        client.explain.return_value = {"reason": "typical"}
        v2 = service._registry.register(MODEL_NAME, RemoteModelFactory(client))
        service._registry.promote(MODEL_NAME, v2)
        self.assertEqual(service.pay(alice, bob, 1).provider, "remote:fraud-xgb")


# ===========================================================================
class TestMLPlatform(unittest.TestCase):

    def test_P21_feature_store_computes_named_features(self):
        bank = Bank()
        alice = bank.open_account("Alice", 200)
        bob = bank.open_account("Alice", 10)       # same owner
        alice.withdraw(40)
        f = standard_features().compute(alice, Decimal("80"), bob)
        self.assertEqual(f["amount_to_balance_ratio"], 0.5)
        self.assertEqual(f["withdrawals_so_far"], 1)
        self.assertEqual(f["largest_previous_withdrawal"], 40.0)
        self.assertEqual(f["same_owner"], 1.0)

    def test_P22_feature_store_refuses_silent_redefinition(self):
        store = FeatureStore()
        store.register("x", lambda a, m, c: 1)
        with self.assertRaises(ValueError):
            store.register("x", lambda a, m, c: 2)
        self.assertEqual(store.schema(), {"x": 1})

    def test_P23_registry_versions_promotes_and_rolls_back(self):
        reg = ModelRegistry()
        v1 = reg.register("m", "model-a", who="alice")
        v2 = reg.register("m", "model-b", who="bob")
        self.assertEqual((v1, v2), (1, 2))
        with self.assertRaises(LookupError):
            reg.production("m")                    # nothing promoted yet
        reg.promote("m", v1)
        reg.promote("m", v2)
        self.assertEqual(reg.production("m").model, "model-b")
        self.assertEqual(reg.versions("m")[0].stage, "archived")
        reg.rollback("m", who="on-call")
        self.assertEqual(reg.production("m").model, "model-a")
        self.assertEqual([e[1] for e in reg.audit_trail()],
                         ["register", "register", "promote", "promote", "promote"])

    def test_P24_registry_keeps_metadata_for_reproducibility(self):
        reg = ModelRegistry()
        schema = standard_features().schema()
        v = reg.register("m", object(), metadata={"features": schema, "auc": 0.9})
        self.assertEqual(reg.versions("m")[0].metadata["features"], schema)
        self.assertEqual(reg.versions("m")[v - 1].version, v)


# ===========================================================================
class TestWithMocks(unittest.TestCase):
    """Isolating the AI-dependent PaymentService with unittest.mock."""

    def setUp(self):
        self.bank = Bank()
        self.alice = self.bank.open_account("Alice", 1000)
        self.bob = self.bank.open_account("Bob", 0)

    def _service_with_scorer(self, scorer, explainer=None):
        """Inject a mock scorer through a mock factory (spec'd to the ABC)."""
        factory = Mock(spec=AIServiceFactory)
        factory.provider_name = "mock-provider"
        factory.create_scorer.return_value = scorer
        factory.create_explainer.return_value = explainer or Mock(
            spec=Explainer, **{"explain.return_value": "mock reason"})
        return make_service(self.bank, factory=factory)[0]

    def test_P25_blocks_when_model_returns_high_score_no_live_model(self):
        scorer = Mock(spec=FraudScorer)
        scorer.score.return_value = Decimal("0.95")
        service = self._service_with_scorer(scorer)
        with self.assertRaises(TransactionBlockedError) as ctx:
            service.pay(self.alice, self.bob, 10)
        self.assertIs(ctx.exception.receipt.action, Action.BLOCK)
        self.assertEqual(self.alice.get_balance(), Decimal("1000.00"))  # no money moved
        scorer.score.assert_called_once()

    def test_P26_model_receives_exactly_the_feature_store_output(self):
        scorer = Mock(spec=FraudScorer, **{"score.return_value": Decimal("0")})
        service = self._service_with_scorer(scorer)
        service.pay(self.alice, self.bob, 10)
        features = scorer.score.call_args.args[0]
        self.assertEqual(set(features), set(standard_features().names()))
        self.assertEqual(features["amount_to_balance_ratio"], 0.01)

    def test_P27_review_queues_without_moving_money(self):
        scorer = Mock(spec=FraudScorer, **{"score.return_value": Decimal("0.5")})
        service = self._service_with_scorer(scorer)
        receipt = service.pay(self.alice, self.bob, 10)
        self.assertIs(receipt.action, Action.REVIEW)
        self.assertEqual(service.review_queue(), [receipt])
        self.assertEqual(self.bob.get_balance(), Decimal("0.00"))

    def test_P28_remote_timeout_falls_back_and_marks_receipt_degraded(self):
        client = Mock()
        client.predict.side_effect = TimeoutError("504 gateway timeout")
        service, _ = make_service(self.bank, factory=RemoteModelFactory(client))
        receipt = service.pay(self.alice, self.bob, 10)
        self.assertTrue(receipt.degraded)
        self.assertEqual(receipt.provider, "rules-v1")
        self.assertIn("504", receipt.explanation)
        client.predict.assert_called_once()
        self.assertEqual(self.bob.get_balance(), Decimal("10.00"))

    def test_P29_remote_scorer_translates_payload_and_validates_response(self):
        client = Mock()
        client.predict.return_value = {"probability": "0.42"}
        scorer = RemoteModelScorer(client, "fraud-xgb")
        self.assertEqual(scorer.score({"f": 1}), Decimal("0.42"))
        client.predict.assert_called_once_with(
            {"model": "fraud-xgb", "features": {"f": 1}})
        client.predict.return_value = {"probability": 7}     # corrupt response
        with self.assertRaises(ValueError):
            scorer.score({})

    def test_P30_service_isolated_from_bank_with_patch(self):
        """PaymentService logic tested with the money-moving layer stubbed."""
        scorer = Mock(spec=FraudScorer, **{"score.return_value": Decimal("0")})
        service = self._service_with_scorer(scorer)
        service.set_fee_strategy(FlatFee("1.00"))
        with patch.object(self.alice, "withdraw") as withdraw, \
                patch.object(self.bob, "deposit") as deposit:
            receipt = service.pay(self.alice, self.bob, 10)
        withdraw.assert_called_once_with(Decimal("11.00"))   # amount + fee together
        deposit.assert_called_once_with(Decimal("10.00"))
        self.assertEqual(receipt.fee, Decimal("1.00"))


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    unittest.main(verbosity=2)
