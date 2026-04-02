# Testing the Synthetic Invoice Generator

This directory contains the `pytest` suite for validating the engine's core boundaries (AST, DAG resolution, Schema Models, and Mutators).

## 🚀 How to Run Tests

To ensure standard Python module paths (`src/`) are resolved correctly without needing to alter your environment manually, run `pytest` using the `python -m` module syntax:

```bash
# Run all tests using the local virtual environment
./venv/bin/python -m pytest tests/
```

### 🔍 Running Specific Test Suites
You can isolate test runs by targeting specific files:

```bash
# Test the Pydantic Exclusivity rules
./venv/bin/python -m pytest tests/test_config.py

# Test the AST Evaluator & DAG Topological Sorter
./venv/bin/python -m pytest tests/test_engine.py

# Test the dot-notation path resolution and Drop/Replace handlers
./venv/bin/python -m pytest tests/test_mutator.py
```

---

## 🏗️ Architecture of the Suite

The suite utilizes a decoupled architecture structure:
1. **`conftest.py`**: Houses universal pytest `@pytest.fixture` primitives (e.g., standard YAML mock loads). Do not overload this file; keep it clean.
2. **`test_config.py`**: Validates the Pydantic configurations boundaries (prevents the engine from starting if mutually exclusive rules exist).
3. **`test_engine.py`**: Dense mathematics and AST evaluator tests.
4. **`test_mutator.py`**: Validates post-generation graph mutations.

> [!IMPORTANT]
> If you encounter `ModuleNotFoundError: No module named 'src'`, verify that you are running the test runner using `python -m` in the root workspace folder of the project. This natively seeds the system path.

---

## 📈 Adding New Tests Guidelines

- **Native Extensibility**: Do not override existing fixtures for ad-hoc script tests. Inherit existing ones or use clean python parameters.
- **Actionable QA Reproducibility**: If test suites involve randomization elements, hardcode `--seed` arguments in the pytest fixtures to ensure flawless reproduce rate.
