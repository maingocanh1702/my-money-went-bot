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

AUTO_MERGE_WARN = (
    "WARNING: --auto-merge enabled. Per implementation-plan §6.5, only P2\n"
    "features qualify for auto-merge. Continue? (y/N) "
)


def _gate_auto_merge(cfg: Config, feature_id: str, stdin=sys.stdin) -> int | None:
    """Return None if auto-merge approved; otherwise an exit code to abort.

    Codex v0.2.0 r4 P1: gate uses an explicit allow-list (P2 only) rather than
    a P0/P1 deny-list. Anything else — None (missing meta), malformed values
    (``p2-lite``, ``HIGH``, custom labels), or future tiers — fails closed.
    Plan §6.5 specifies P2-only for auto-merge, and silent acceptance of
    unrecognized tiers would let misclassified specs bypass policy.
    """
    fe_path, _ = spec_lint.resolve_spec_paths(cfg, feature_id)
    tier = spec_lint.parse_risk_tier(fe_path)
    if tier != "P2":
        effective = tier or "missing"
        print(
            f"ERROR: --auto-merge refused for {feature_id} "
            f"(risk_tier={effective}). Plan §6.5 allows auto-merge ONLY for "
            "risk_tier=P2; P0/P1/missing/malformed all fail closed. Re-run "
            "without --auto-merge and squash manually.",
            file=sys.stderr,
        )
        return 4
    print(AUTO_MERGE_WARN, end="")
    answer = stdin.readline().strip().lower()
    if answer not in ("y", "yes"):
        # Codex v0.2.0 r3 P1: must return non-zero so scripted/non-interactive
        # invocations can distinguish a declined confirmation from a successful
        # run. Exit code 5 = "user declined --auto-merge confirmation"
        # (distinct from 4 = P0/P1 mechanical refusal).
        print(
            "Aborted by user — re-run without --auto-merge for safe default.",
            file=sys.stderr,
        )
        return 5
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="autopilot", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_lint = sub.add_parser("lint", help="validate a spec")
    p_lint.add_argument("feature_id")

    sub.add_parser("preflight", help="run pre-flight env checks")

    p_run = sub.add_parser("run", help="full pipeline for a feature")
    p_run.add_argument("feature_id")
    p_run.add_argument(
        "--auto-merge",
        action="store_true",
        default=False,
        help="Opt in to Phase E auto-merge (safe default: OFF). Allowed only "
        "for P2 features per plan v0.1.6 §6.5; refused for P0/P1.",
    )

    p_resume = sub.add_parser("resume", help="resume from saved state")
    p_resume.add_argument("feature_id")
    p_resume.add_argument(
        "--auto-merge",
        action="store_true",
        default=False,
        help="Opt in to Phase E auto-merge on resume (same rules as run).",
    )

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
        if args.auto_merge:
            bail = _gate_auto_merge(cfg, args.feature_id)
            if bail is not None:
                return bail
        outcome = loop.run(cfg, args.feature_id, resume=False, auto_merge=args.auto_merge)
        print("\n" + outcome.summary)
        if outcome.halted:
            return 3
        if outcome.final_phase in ("MERGED", "READY"):
            return 0
        return 1

    if args.cmd == "resume":
        if args.auto_merge:
            bail = _gate_auto_merge(cfg, args.feature_id)
            if bail is not None:
                return bail
        outcome = loop.run(cfg, args.feature_id, resume=True, auto_merge=args.auto_merge)
        print("\n" + outcome.summary)
        if outcome.halted:
            return 3
        if outcome.final_phase in ("MERGED", "READY"):
            return 0
        return 1

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
