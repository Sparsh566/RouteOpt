# Contributing to RouteOpt

Thank you for contributing to RouteOpt! RouteOpt is a research-grade fleet routing and CVRPTW optimization engine. To maintain mathematical correctness, honesty of claims, and reproducibility, all contributions follow a structured Git & GitHub workflow.

---

## 1. Core Principles

1. **Correctness First**: Never claim a bug is fixed or a constraint is supported without an automated test proving it.
2. **No Theater**: No hardcoded numbers, mock delays, or synthetic metrics masquerading as solver output.
3. **Reproducibility**: Benchmark results must be reproducible using the CLI benchmark harness.
4. **Clean Git History**: Work on dedicated feature branches, write clear commit messages, and submit pull requests referencing tracking issues.

---

## 2. Contribution Flow

Every code contribution follows this 5-step lifecycle:

```
Issue (#ID)  -->  Branch (feature/<ID>-short-name)  -->  Commits + Tests  -->  Pull Request (Fixes #ID)  -->  Review & Merge
```

### Step 1: Identify or Open an Issue
- Check existing [GitHub Issues](https://github.com/Sparsh566/RouteOpt/issues).
- If your work addresses a new bug or feature, open an issue using the appropriate template (`bug_report.md` or `feature_request.md`).

### Step 2: Create a Feature Branch
Always branch off the latest `main` branch:
```bash
git checkout main
git pull origin main
git checkout -b feature/<issue-no>-<short-name>
# e.g.: git checkout -b feature/1-dynamic-baseline
```
Use appropriate prefixes:
- `feature/<id>-...` for new features or algorithmic capabilities
- `fix/<id>-...` for bug fixes
- `bench/<id>-...` for benchmarking suites
- `docs/<id>-...` for documentation updates
- `ci/<id>-...` for workflow or tooling changes

### Step 3: Write Tests First & Make Focused Commits
- For bug fixes: Write a **failing regression test** first to reproduce the issue, then implement the fix until the test passes.
- For new constraints: Add tests in `backend/tests/` asserting mathematical feasibility with `RouteValidator`.
- Keep commits small, self-contained, and logically grouped. Use conventional commit messages:
  ```bash
  git commit -m "feat(solver): add vehicle breakdown handling"
  git commit -m "test(solver): add failing test for midday breakdown"
  ```

### Step 4: Run the Test Suite Locally
Ensure all tests pass before opening a PR:
```bash
pytest -v
```

### Step 5: Open a Pull Request
Push your branch to GitHub and open a PR:
```bash
git push -u origin feature/<issue-no>-<short-name>
gh pr create --fill
```
- In the PR body, link the tracking issue using `Fixes #<issue-no>`.
- Fill out the testing notes and the PR checklist.
- Once CI passes and the PR is approved, squash-and-merge or rebase-and-merge into `main`.

---

## 3. Development Setup

```bash
# Clone the repository
git clone https://github.com/Sparsh566/RouteOpt.git
cd RouteOpt

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run test suite
pytest -v
```

---

## 4. Code Style & Standards
- Python code targets Python 3.11+.
- Formatting & linting via `ruff` and type-checking via `mypy`.
- Do not check in virtual environments, credentials, or large local datasets.
