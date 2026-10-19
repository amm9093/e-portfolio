# Source code

| File | Responsibility |
|---|---|
| `bank_account.py` | Validation, abstract `Account`, three products, `accept()` for visitors |
| `bank.py` | `Bank` facade, `ordered_locks()` context manager, transfers, totals |
| `simulator.py` | Multi-threaded transaction simulator (coding exercise) |
| `strategies.py` | Strategy: `FeeStrategy` family and `RiskPolicy` family |
| `decorators.py` | Decorator: `LoggingAccount`, `SecuredAccount`, `Authoriser` |
| `visitors.py` | Visitor: statement, risk exposure and interest projection reports |
| `ai_providers.py` | Abstract Factory: rule-based and remote provider families |
| `ml_platform.py` | `FeatureStore` and `ModelRegistry` |
| `payments.py` | `PaymentService` and `Receipt` (Capstone context) |
| `main.py`, `demo_patterns.py`, `deadlock_experiment.py` | Demonstrations and experiments |
| `test_bank_system.py`, `test_patterns.py` | 49 unit tests |

```text
python main.py                       # Demonstrations 1-4
python deadlock_experiment.py        # the two locking faults
python demo_patterns.py              # Demonstrations 5-9 (or: demo_patterns.py 6 8)
python -m unittest test_bank_system.py test_patterns.py -v   # 49 tests
```
Python 3.10 or later; no third-party packages.
