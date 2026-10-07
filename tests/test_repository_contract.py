"""Repository-level contracts that keep the declared gates meaning one thing."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_lint_rule_set_is_declared():
    """The lint gate names its rules instead of inheriting Ruff's defaults.

    CI installs Ruff unpinned, and Ruff's default selection changes between
    releases. An undeclared rule set lets a tool upgrade fail main with no code
    change, and makes "lint passed" mean different things on different days.
    """
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lint = pyproject.get("tool", {}).get("ruff", {}).get("lint", {})

    assert lint.get("select"), "pyproject.toml must declare [tool.ruff.lint] select"


def test_ci_provisions_the_declared_build_backend():
    """CI installs the build-system requirements the no-isolation wheel test needs.

    `test_built_wheel_exposes_loadable_entry_point_without_src` builds with
    `--no-isolation`, so the backend must already be in the interpreter. Python
    3.12 ships without setuptools, so a check-tool list that omits it fails
    only on that matrix leg.
    """
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "['build-system']['requires']" in workflow
