# CI lint contract

Owner: claude
Branch: claude/ci-lint-contract
Date: 2026-10-08

## What changed

- `pyproject.toml`: declares `[tool.ruff.lint] select = ["E4", "E7", "E9", "F"]`.
- `tests/test_repository_contract.py`: `test_lint_rule_set_is_declared`,
  `test_ci_provisions_the_declared_build_backend`.
- `.github/workflows/ci.yml`: installs the `build-system` requirements read
  from `pyproject.toml`; Python 3.12 has no setuptools, and the wheel test
  builds with `--no-isolation`.
- `tests/test_device_executor.py`: the wheel test reports build stderr.
- `CHANGELOG.md`, `STATE.md`: record the cause and the evidence.

## Why

The only CI run on main (2026-08-13, run 31709407523) failed at the Lint step
with 13 findings. CI installs Ruff unpinned; Ruff 0.16 widened the rules it
enables when none are declared, and with Ruff 0.15 the same tree is clean. The
rejected alternative was adopting the wider default set, which would need
suppressions for intentional code (`exec` in a test loader, a deliberate
`BaseException` catch in the closed-loop script).

## Verified

- Both new tests fail on the old files and pass on the new ones. The 3.12
  build failure (`Backend 'setuptools.build_meta' is not available`) was
  reproduced locally before the fix.
- Python 3.11 and 3.12, Ruff 0.16.10: compileall, `ruff check src tests scripts`,
  176 tests, `python -m build`, `twine check` on both artefacts: all passed.
- `flyto-index verify . --full-scan --strict --json`: 20 pass, 0 warn, 0 fail.

## Not verified

- MCP `task(action='validate')`: the MCP server is pinned to another repository
  in this session.
- `.flyto/coding.yaml` still points at `/Users/chester/flytohub/flyto-ai/.venv`,
  a path that does not exist on the current workstation layout. Unchanged.

## Follow-ups

- Widening the Ruff rule set is open work.
- Re-point or generalise the interpreter in `.flyto/coding.yaml`.
