# Individual coding exercise — thread-safe banking system

A banking system in Python in which several users deposit, withdraw, transfer and check balances concurrently without corrupting account data. Per-account re-entrant locks prevent lost updates; ordered locking prevents transfer deadlock; `deadlock_experiment.py` reproduces both faults on purpose.

- [Report](Individual%20Coding%20Exercise%20-%20Report.docx)
- [Code](code/) — `python main.py` for the four demonstrations, `python -m unittest test_bank_system.py -v` for the 19 tests

This system is the base that the [Capstone Project](../capstone-project/) extends with Strategy, Decorator, Visitor and Abstract Factory, a model registry, a feature store and mock-based tests.
