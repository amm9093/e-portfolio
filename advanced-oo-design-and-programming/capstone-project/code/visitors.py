"""
visitors.py
===========
VISITOR PATTERN - keep reporting/analytics algorithms out of the account
classes.

Every concrete account implements accept(visitor) and calls back the visit
method for its own type (double dispatch). The *visitor* then holds the
whole algorithm for all account types in one place.

    report = StatementVisitor()
    for account in bank.get_all_accounts():
        account.accept(report)
    print(report.result())

Why Visitor rather than a statement() method on each account?
    * Separation of concerns: the account classes stay about money and
      locking. A regulator asking for a new report should not mean editing
      (and re-testing) the concurrency-critical classes.
    * New analyses are new classes: StatementVisitor, RiskExposureVisitor,
      InterestProjectionVisitor ... each tested on its own.
    * The trade-off is the classic one: adding a NEW ACCOUNT TYPE means
      adding a method to every visitor. The account hierarchy here is
      stable (three products) while the set of reports keeps growing, which
      is exactly the situation Visitor suits.
"""

from abc import ABC, abstractmethod
from decimal import Decimal

from bank_account import CENT


class AccountVisitor(ABC):
    """One visit method per concrete account type."""

    @abstractmethod
    def visit_bank_account(self, account):
        """Visit a plain BankAccount."""

    @abstractmethod
    def visit_savings_account(self, account):
        """Visit a SavingsAccount."""

    @abstractmethod
    def visit_current_account(self, account):
        """Visit a CurrentAccount."""


def apply(visitor, accounts):
    """Run `visitor` over every account and return the visitor."""
    for account in accounts:
        account.accept(visitor)
    return visitor


class StatementVisitor(AccountVisitor):
    """Builds a human-readable statement, one line per account, with the
    product-specific detail that each type carries."""

    def __init__(self):
        self._lines = []

    def _line(self, account, detail):
        self._lines.append(
            f"{account.account_number}  {account.owner:<8} "
            f"{type(account).__name__:<15} {account.get_balance():>10}  {detail}")

    def visit_bank_account(self, account):
        self._line(account, "")

    def visit_savings_account(self, account):
        self._line(account, f"min {account.minimum_balance}, "
                            f"rate {account.interest_rate:.2%}")

    def visit_current_account(self, account):
        self._line(account, f"overdraft limit {account.overdraft_limit}")

    def result(self):
        return "\n".join(self._lines)


class RiskExposureVisitor(AccountVisitor):
    """Analytics: how much money the bank could lose to overdrafts, and
    which accounts are currently overdrawn."""

    def __init__(self):
        self.total_balance = Decimal("0.00")
        self.overdraft_capacity = Decimal("0.00")   # total agreed overdrafts
        self.overdrawn = []                           # (number, balance)

    def _count(self, account):
        self.total_balance += account.get_balance()

    def visit_bank_account(self, account):
        self._count(account)

    def visit_savings_account(self, account):
        self._count(account)

    def visit_current_account(self, account):
        balance = account.get_balance()
        self.total_balance += balance
        self.overdraft_capacity += account.overdraft_limit
        if balance < 0:
            self.overdrawn.append((account.account_number, balance))

    def result(self):
        return {
            "total_balance": self.total_balance,
            "overdraft_capacity": self.overdraft_capacity,
            "overdrawn_accounts": list(self.overdrawn),
        }


class InterestProjectionVisitor(AccountVisitor):
    """Projects the interest the bank will pay over `periods` periods.

    Only savings accounts earn interest; the other visit methods are
    deliberately empty, which is itself a design statement: the visitor,
    not the account, knows that the product is not interest-bearing.
    """

    def __init__(self, periods=12):
        self._periods = periods
        self.projected = {}

    def visit_bank_account(self, account):
        pass

    def visit_current_account(self, account):
        pass

    def visit_savings_account(self, account):
        balance = account.get_balance()
        rate = account.interest_rate
        future = balance
        for _ in range(self._periods):
            future = (future + future * rate).quantize(CENT)
        self.projected[account.account_number] = (future - balance).quantize(CENT)

    def result(self):
        return dict(self.projected)

    @property
    def total(self):
        return sum(self.projected.values(), Decimal("0.00"))
