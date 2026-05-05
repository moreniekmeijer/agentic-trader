# Testing

**Analysis Date:** 2026-05-05

## Test Framework

**Runner:** pytest
**Config location:** `pyproject.toml` under `[tool.pytest.ini_options]`

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

**Note:** `pythonpath = ["src"]` is configured but the project uses `agentic_trader/` at the root, not a `src/` layout. This config is vestigial and has no effect.

**Coverage plugin:** `pytest-cov` (installed as dev dependency)

**Dev dependencies:**
```toml
[dependency-groups]
dev = [
    "pytest",
    "pytest-cov",
    "ruff",
    "ty",
]
```

## Test Types & Coverage

**Current state:** The `tests/` directory exists but is empty — zero test files are present.

There are no unit tests, integration tests, or end-to-end tests in the repository. The test infrastructure (pytest, pytest-cov) is installed and configured, but no tests have been written yet.

**Coverage tooling available but unused:**
```bash
make test-cov
# runs: pytest --cov=agentic_trader --cov-report=term --cov-report=xml:coverage.xml --junitxml=report.xml tests/
```

This produces `coverage.xml` and `report.xml` but currently exits with zero tests collected.

**Areas that need test coverage (priority order):**

1. `agentic_trader/agents/agent.py` — `BaseAgent._compute_scores`, `_apply_bias`, `_decide`, `_clamp`, `_build_response`
2. `agentic_trader/agents/fundamental/agent.py` — `FundamentalsAgent._score_relative`, `_score_growth`, `_score_pe`, `_compute_scores`
3. `agentic_trader/agents/technical/agent.py` — `TechnicalAgent._compute_scores` signal logic
4. `agentic_trader/agents/discussion/agent.py` — `DiscussionAgent._aggregate` weighted voting
5. `agentic_trader/risk/engine.py` — `RiskEngine.can_trade`, `get_allowed_qty`, cooldown logic
6. `agentic_trader/scanner/engine.py` — `ScannerEngine._score`, `scan` ranking logic
7. `agentic_trader/services/market_data/indicators/` — RSI, MA, volume computation correctness
8. `agentic_trader/database/mapper.py` — mapper functions (pure functions, easy to unit test)
9. `agentic_trader/decision/engine.py` — `DecisionEngine.execute_decision` orchestration

## Test Organization

**Test root:** `tests/` (project root)

**Intended structure** (based on pytest config and project layout):
```
tests/
├── conftest.py            # shared fixtures (not yet created)
├── agents/
│   ├── test_base_agent.py
│   ├── test_technical_agent.py
│   ├── test_fundamental_agent.py
│   └── test_discussion_agent.py
├── risk/
│   └── test_risk_engine.py
├── scanner/
│   └── test_scanner_engine.py
├── services/
│   └── market_data/
│       └── indicators/
│           └── test_rsi.py
└── database/
    └── test_mapper.py
```

**Naming convention to use:**
- Test files: `test_<module_name>.py`
- Test functions: `test_<behaviour_under_test>`
- Test classes: `Test<ClassName>` (optional; flat functions are acceptable and consistent with the simple codebase)

## Running Tests

```bash
# Run all tests
make test
# equivalent: uv run pytest tests/

# Run with coverage (terminal + XML)
make test-cov
# equivalent: uv run pytest --cov=agentic_trader --cov-report=term --cov-report=xml:coverage.xml --junitxml=report.xml tests/

# Run a specific file
uv run pytest tests/agents/test_base_agent.py

# Run with verbose output
uv run pytest -v tests/

# Run a specific test by name
uv run pytest tests/ -k "test_risk_blocked_on_low_confidence"
```

**Coverage reports:**
- Terminal output: `--cov-report=term`
- XML (for CI): `coverage.xml`
- JUnit XML: `report.xml`

## CI Integration

No CI pipeline is configured. There is no `.github/workflows/`, `.gitlab-ci.yml`, or other pipeline definition file in the repository.

**What exists for local quality gates:**
- `make all` runs `format → lint → typecheck → test` in sequence
- This can serve as a pre-push checklist

**To add CI** (GitHub Actions example):
```yaml
# .github/workflows/ci.yml
- run: uv sync
- run: uv run ruff check .
- run: uv run ty check .
- run: uv run pytest tests/ --cov=agentic_trader --cov-report=xml
```

---

*Testing analysis: 2026-05-05*
