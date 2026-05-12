"""CLI entry point: ``python -m tools.autopilot <command> [args]``.

Commands:
- ``lint <feature_id>`` — validate spec only.
- ``preflight`` — run env + git checks.
- ``run <feature_id>`` — full pipeline (preflight + lint + A→E).
- ``resume <feature_id>`` — continue from saved state.
- ``status <feature_id>`` — print current state JSON.
- ``abort <feature_id>`` — mark state HALTED + reset branch (manual cleanup).

Exit codes: 0 = success, 1 = lint/verify fail, 2 = preflight fail,
3 = circuit broken, 4 = bad args.
"""

from __future__ import annotations

import argparse
import sys

from . import loop, preflight, spec_lint, state
from .config import Config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="autopilot", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_lint = sub.add_parser("lint", help="validate a spec")
    p_lint.add_argument("feature_id")

    sub.add_parser("preflight", help="run pre-flight env checks")

    p_run = sub.add_parser("run", help="full pipeline for a feature")
    p_run.add_argument("feature_id")

    p_resume = sub.add_parser("resume", help="resume from saved state")
    p_resume.add_argument("feature_id")

    p_status = sub.add_parser("status", help="show current state for a feature")
    p_status.add_argument("feature_id")

    p_abort = sub.add_parser("abort", help="mark state HALTED")
    p_abort.add_argument("feature_id")

    args = parser.parse_args(argv)
    cfg = Config.load()

    if args.cmd == "lint":
        report = spec_lint.lint(cfg, args.feature_id)
        print(report.render())
        return 0 if report.ok else 1

    if args.cmd == "preflight":
        report = preflight.run(cfg)
        print(report.render())
        return 0 if report.ok else 2

    if args.cmd == "run":
        pre = preflight.run(cfg)
        print(pre.render())
        if not pre.ok:
            return 2
        outcome = loop.run(cfg, args.feature_id, resume=False)
        print("\n" + outcome.summary)
        if outcome.halted:
            return 3
        return 0 if outcome.final_phase == "MERGED" else 1

    if args.cmd == "resume":
        outcome = loop.run(cfg, args.feature_id, resume=True)
        print("\n" + outcome.summary)
        if outcome.halted:
            return 3
        return 0 if outcome.final_phase == "MERGED" else 1

    if args.cmd == "status":
        s = state.load(cfg, args.feature_id)
        if s is None:
            print(f"No state for {args.feature_id}")
            return 1
        print(s.to_json())
        return 0

    if args.cmd == "abort":
        s = state.load(cfg, args.feature_id)
        if s is None:
            print(f"No state for {args.feature_id} — nothing to abort.")
            return 1
        state.transition(s, "HALTED")
        s.halt_reason = "manually aborted via CLI"
        state.save(cfg, s)
        print(f"Aborted {args.feature_id}. Inspect branch {s.branch} manually.")
        return 0

    parser.print_help()
    return 4


if __name__ == "__main__":
    sys.exit(main())
