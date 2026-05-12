"""Local verification — runs the same checks pre-commit + CI run.

5 layers: ruff, black, mypy, lint-imports, pytest. ALL must pass for
``VerifyResult.ok`` to be True.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

from .config import Config


@dataclass
class StepResult:
    name: str
    ok: bool
    duration_seconds: float
    stdout_tail: str
    stderr_tail: str


@dataclass
class VerifyResult:
    steps: list[StepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(step.ok for step in self.steps)

    @property
    def failed_steps(self) -> list[StepResult]:
        return [s for s in self.steps if not s.ok]

    def render(self) -> str:
        lines = ["Local verify:"]
        for step in self.steps:
            sym = "PASS" if step.ok else "FAIL"
            lines.append(f"  {sym} {step.name} ({step.duration_seconds:.1f}s)")
            if not step.ok:
                if step.stdout_tail:
                    lines.append("    --- stdout (tail) ---")
                    lines.extend(f"    {line}" for line in step.stdout_tail.splitlines()[-15:])
                if step.stderr_tail:
                    lines.append("    --- stderr (tail) ---")
                    lines.extend(f"    {line}" for line in step.stderr_tail.splitlines()[-15:])
        return "\n".join(lines)


VERIFY_STEPS: list[tuple[str, list[str]]] = [
    ("ruff", ["ruff", "check", "core/", "markets/", "tests/"]),
    ("black", ["black", "--check", "core/", "markets/", "tests/"]),
    ("mypy", ["mypy", "core/", "markets/", "tests/"]),
    ("lint-imports", ["lint-imports"]),
    ("pytest", ["pytest", "tests/", "-q"]),
]


def run_all(cfg: Config, *, fail_fast: bool = False) -> VerifyResult:
    """Run all verify steps. With ``fail_fast``, stop after first failure."""
    import time

    result = VerifyResult()
    for name, cmd in VERIFY_STEPS:
        start = time.time()
        completed = subprocess.run(
            cmd,
            cwd=cfg.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        duration = time.time() - start
        step = StepResult(
            name=name,
            ok=completed.returncode == 0,
            duration_seconds=duration,
            stdout_tail=completed.stdout[-2000:],
            stderr_tail=completed.stderr[-1000:],
        )
        result.steps.append(step)
        if not step.ok and fail_fast:
            break
    return result
