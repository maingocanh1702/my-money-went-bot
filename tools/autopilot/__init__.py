"""Autopilot orchestrator — run a feature spec through code → review → fix → merge.

Public CLI: ``python -m tools.autopilot <command> <args>``.

Modules:
- ``config``: paths + constants + env overrides
- ``spec_lint``: validate FE+BE spec before autopilot consumes
- ``preflight``: env + git + tooling checks
- ``git_ops``: subprocess wrappers for git
- ``codex``: Codex CLI invocation + findings parser
- ``claude_codegen``: Claude CLI invocation for code-gen and targeted fixes
- ``verify``: ruff/black/mypy/lint-imports/pytest runner
- ``circuit_breaker``: 10 halt conditions per Level 3 template
- ``state``: JSON checkpoint per feature for resume
- ``loop``: orchestration of phases A→E
- ``merge``: auto-squash with strict pre-merge gates
- ``tracker``: implementation-tracker.md row updater
"""

__version__ = "0.1.0"
