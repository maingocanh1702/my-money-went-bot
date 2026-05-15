#!/usr/bin/env python3
"""Autopilot agent driver — subprocess wrapper around Claude Code headless mode.

Per memory project_ops_tracker_full_auto_exception (2026-05-13): TRUE zero-touch
for ops-tracker batch. Uses Claude Max subscription via Claude Code's OAuth.

Each autopilot prompt = one `claude -p` invocation with `--output-format json`.
Claude Code provides Bash/Read/Edit tools natively.

Setup (one-time):
  npm i -g @anthropic-ai/claude-code
  claude login                          # OAuth to Claude.ai (Max sub)
  which codex                           # MUST resolve (used inside prompts)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / ".autopilot" / "sdk-sessions"
LOG_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_TIMEOUT_SECONDS = int(os.environ.get("AUTOPILOT_PROMPT_TIMEOUT", "3600"))
ALLOWED_TOOLS = os.environ.get("AUTOPILOT_ALLOWED_TOOLS", "Bash,Read,Edit,Write,Glob,Grep")
MODEL = os.environ.get("AUTOPILOT_MODEL", "claude-opus-4-6")

SENTINEL_READY = re.compile(r"AUTOPILOT[^\n]*READY_FOR_MANUAL_MERGE", re.IGNORECASE)
SENTINEL_COMPLETE = re.compile(r"AUTOPILOT[^\n]*COMPLETE\b", re.IGNORECASE)
SENTINEL_HALT = re.compile(r"HALT\s+—", re.IGNORECASE)


@dataclass
class SessionResult:
    status: str  # "ready" | "completed" | "halted" | "error"
    final_text: str
    iterations: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    error: str | None = None
    log_path: Path | None = None


def _scan_sentinel(text: str) -> str | None:
    if SENTINEL_HALT.search(text):
        return "halted"
    if SENTINEL_COMPLETE.search(text):
        return "completed"
    if SENTINEL_READY.search(text):
        return "ready"
    return None


def _preflight_claude_cli() -> str | None:
    """Returns error message if claude CLI not ready, else None."""
    try:
        proc = subprocess.run(  # noqa: S603,S607
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        return "claude CLI not installed. Install: npm i -g @anthropic-ai/claude-code"
    except subprocess.TimeoutExpired:
        return "claude --version timed out (10s)"
    if proc.returncode != 0:
        return f"claude --version exit {proc.returncode}: {proc.stderr[-500:]}"
    return None


def run_autopilot_session(
    prompt_content: str,
    item_id: str,
    *,
    on_progress=None,
    extra_args: list[str] | None = None,
) -> SessionResult:
    """Run one autopilot prompt as a Claude Code headless session."""
    err = _preflight_claude_cli()
    if err:
        return SessionResult(status="error", final_text="", error=err)

    log_path = LOG_DIR / f"{item_id}-{int(time.time())}.json"
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--allowedTools",
        ALLOWED_TOOLS,
        "--model",
        MODEL,
    ]
    if extra_args:
        cmd += extra_args

    if on_progress:
        on_progress(item_id, 0, f"Spawning `{' '.join(cmd)}` (max {PROMPT_TIMEOUT_SECONDS}s)...")

    start = time.monotonic()
    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            input=prompt_content,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=PROMPT_TIMEOUT_SECONDS,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    except subprocess.TimeoutExpired as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        partial = (
            (e.stdout or b"").decode("utf-8", errors="replace")
            if isinstance(e.stdout, bytes)
            else (e.stdout or "")
        )
        log_path.write_text(
            json.dumps(
                {
                    "item_id": item_id,
                    "status": "timeout",
                    "elapsed_ms": elapsed_ms,
                    "stdout_partial": partial[-4000:],
                },
                indent=2,
            )
        )
        return SessionResult(
            status="error",
            final_text="",
            duration_ms=elapsed_ms,
            error=f"claude -p timed out after {PROMPT_TIMEOUT_SECONDS}s",
            log_path=log_path,
        )

    duration_ms = int((time.monotonic() - start) * 1000)
    raw_stdout = proc.stdout or ""
    raw_stderr = proc.stderr or ""

    log_path.write_text(
        json.dumps(
            {
                "item_id": item_id,
                "cmd": cmd,
                "exit_code": proc.returncode,
                "duration_ms": duration_ms,
                "stdout": raw_stdout,
                "stderr": raw_stderr,
            },
            indent=2,
        )
    )

    if proc.returncode != 0:
        return SessionResult(
            status="error",
            final_text=raw_stdout,
            duration_ms=duration_ms,
            error=f"claude -p exit {proc.returncode}: {raw_stderr[-1500:]}",
            log_path=log_path,
        )

    final_text = ""
    iterations = 0
    input_tokens = 0
    output_tokens = 0
    cost_usd = 0.0
    try:
        parsed = json.loads(raw_stdout)
        final_text = parsed.get("result") or parsed.get("text") or parsed.get("content") or ""
        iterations = parsed.get("num_turns") or 0
        usage = parsed.get("usage") or {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cost_usd = parsed.get("total_cost_usd") or 0.0
    except json.JSONDecodeError:
        final_text = raw_stdout

    if on_progress:
        on_progress(
            item_id, iterations, f"claude -p done in {duration_ms/1000:.1f}s, {iterations} turns"
        )

    sentinel = _scan_sentinel(final_text)
    if sentinel:
        return SessionResult(
            status=sentinel,
            final_text=final_text,
            iterations=iterations,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            log_path=log_path,
        )

    return SessionResult(
        status="error",
        final_text=final_text,
        iterations=iterations,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        error="No sentinel (READY_FOR_MANUAL_MERGE / COMPLETE / HALT) in final assistant text",
        log_path=log_path,
    )


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Run a single autopilot prompt via Claude Code headless mode"
    )
    p.add_argument("prompt_file")
    p.add_argument("--item-id", default="adhoc")
    args = p.parse_args()
    prompt = Path(args.prompt_file).read_text()

    def progress(item, it, text):
        print(f"  [{item} t={it}] {text}", flush=True)

    result = run_autopilot_session(prompt, args.item_id, on_progress=progress)
    print(f"\nStatus: {result.status}")
    print(f"Turns: {result.iterations}, tokens: {result.input_tokens}in/{result.output_tokens}out")
    print(f"Cost: ${result.cost_usd:.4f}, duration: {result.duration_ms/1000:.1f}s")
    print(f"Log: {result.log_path}")
    if result.error:
        print(f"Error: {result.error}")
    print("\n--- Final text (last 4000 chars) ---")
    print(result.final_text[-4000:] if result.final_text else "(empty)")
    return 0 if result.status in ("ready", "completed") else 1


if __name__ == "__main__":
    sys.exit(main())
