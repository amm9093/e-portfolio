# Advanced Object-Oriented Design and Programming

My e-Portfolio for the module. The Capstone Project page is the one referenced from the cover of my end-of-module submission.

- [**Capstone Project**](capstone-project/) — Tasks 1–4: learning outcomes, artefacts with critical commentary (Strategy, Decorator, Visitor, Abstract Factory, Model Registry, Feature Store, mock-based testing), skill reflection and professional development plan; source code, diagrams and the submitted report (PDF)
- [Reflective piece](reflective-piece.md) — my learning journey, structured with Gibbs' reflective cycle, Kolb, the Johari Window and Bloom's taxonomy
- [Individual coding exercise](individual-coding-exercise/) — the thread-safe banking system the Capstone builds on
- [Discussion forum contributions](discussions/)

Artefacts at a glance:

| Artefact | Pattern / technique | Where |
|---|---|---|
| Thread-safe banking system | Abstraction, encapsulation, inheritance, polymorphism; Template Method; Facade; re-entrant and ordered locking | `capstone-project/code/bank_account.py`, `bank.py` |
| Pricing rules and AI decision policy | Strategy | `strategies.py` |
| Logging and security layers | Decorator | `decorators.py` |
| Statements and analytics | Visitor | `visitors.py` |
| Switchable AI providers | Abstract Factory | `ai_providers.py` |
| Model Registry and Feature Store | AI-oriented architectural patterns | `ml_platform.py` |
| Screened payment service | Composition of the above | `payments.py` |
| 49 unit tests, incl. mock-based tests of the AI path | `unittest`, `unittest.mock` | `test_bank_system.py`, `test_patterns.py` |
