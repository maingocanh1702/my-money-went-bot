#!/usr/bin/env python3
"""Automators for the 'manual' items in the ops-tracker batch.

Per project_ops_tracker_full_auto_exception memory: TRUE walk-away requested.

Items automated:
  C-2          Linear projects + labels (idempotent; reuses existing team)
  C-3-execute  Run linear_migrate.py --dry-run then --execute --confirm
  C-4-deploy   Railway CLI deploy
  D-6-protect  GitHub branch protection
  D-5-templates Linear issue templates

Items still founder-only:
  C-3.0   Linear plan UI eyeballing (5 min)
  D-2.1   Visual dashboard render check (5 min)
  C-5.3   Archive tracker.md (memory feedback_never_auto_delete_docs)

Required env:
  LINEAR_API_KEY    — Linear personal API key
  LINEAR_TEAM_NAME  — (optional) exact team name; defaults to "Engineering"
                      or first team if "Engineering" not found
  GITHUB_TOKEN      — for D-6-protect
  GH_REPO           — owner/repo (auto-detected from git remote if absent)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
LINEAR_ENDPOINT = "https://api.linear.app/graphql"

# ─── Linear helpers ───────────────────────────────────────────────────────


def _linear_client() -> httpx.Client:
    key = os.environ.get("LINEAR_API_KEY")
    if not key:
        raise RuntimeError("LINEAR_API_KEY not set")
    return httpx.Client(
        base_url=LINEAR_ENDPOINT,
        headers={"Authorization": key, "Content-Type": "application/json"},
        timeout=30.0,
    )


def _linear_gql(client: httpx.Client, query: str, variables: dict | None = None) -> dict:
    r = client.post("", json={"query": query, "variables": variables or {}})
    if r.status_code >= 400:
        try:
            body_text = r.json()
        except Exception:  # noqa: BLE001
            body_text = r.text[:2000]
        raise RuntimeError(
            f"Linear API HTTP {r.status_code} on query "
            f"'{query.strip().splitlines()[0][:80]}...': {body_text}"
        )
    body = r.json()
    if "errors" in body:
        raise RuntimeError(f"Linear GraphQL error: {body['errors']}")
    return body["data"]


PHASES = [
    ("P0 — Docs & Foundation Specs", "Wave 0 spec + foundation infra"),
    ("P1 — Foundation", "Repo bootstrapping, CI, base architecture"),
    ("P2 — Handlers", "F02-F08 implementation"),
    ("P3 — Pricing & Billing", "Stripe + family plan"),
    ("P4 — SePay Integration", "F01 SePay onboarding"),
    ("P5 — Email Parsers", "TCB + Cake + MB MVP"),
    ("P6 — Deploy & DevOps", "Railway, CI/CD"),
    ("P7 — Beta Testing", "User testing cycle"),
    ("P8 — Public Launch", "Marketing, launch ops"),
    ("PW — Web Dashboard", "Deferred phase"),
]

LABELS = [
    ("feature", "#2196f3"),
    ("infra", "#9c27b0"),
    ("bug", "#f44336"),
    ("docs", "#4caf50"),
    ("chore", "#9e9e9e"),
    ("blocked", "#ff9800"),
    ("ci-failing", "#e53935"),
    ("changes-requested", "#fdd835"),
]


def automate_c2_linear_setup() -> dict:
    """Idempotent: reuses existing team + skips existing projects/labels."""
    try:
        with _linear_client() as c:
            # 1. Pick team
            all_teams = _linear_gql(c, "query { teams { nodes { id name key } } }")["teams"][
                "nodes"
            ]
            if not all_teams:
                return {"status": "halted", "detail": "No teams in Linear workspace"}

            preferred = os.environ.get("LINEAR_TEAM_NAME")
            team = None
            if preferred:
                team = next((t for t in all_teams if t["name"] == preferred), None)
                if not team:
                    return {
                        "status": "halted",
                        "detail": f"LINEAR_TEAM_NAME='{preferred}' not found. Existing: {[t['name'] for t in all_teams]}",
                    }
            else:
                team = next((t for t in all_teams if t["name"] == "Engineering"), all_teams[0])

            team_id = team["id"]
            print(f"  · Using team '{team['name']}' (key={team['key']}, id={team_id})")

            # 2. Projects (idempotent)
            existing_projects = _linear_gql(
                c,
                f"""
                query {{ projects(filter: {{accessibleTeams: {{some: {{id: {{eq: "{team_id}"}}}}}}}}) {{
                    nodes {{ id name }}
                }} }}
            """,
            )
            existing_names = {p["name"] for p in existing_projects["projects"]["nodes"]}
            created = 0
            for name, desc in PHASES:
                if name in existing_names:
                    print(f"  · Project '{name}' exists, skip")
                    continue
                _linear_gql(
                    c,
                    """
                    mutation Create($input: ProjectCreateInput!) {
                        projectCreate(input: $input) { success project { id name } }
                    }
                """,
                    {"input": {"name": name, "description": desc, "teamIds": [team_id]}},
                )
                created += 1
                print(f"  · Created project '{name}'")

            # 3. Labels (handle workspace-wide uniqueness)
            existing_labels = _linear_gql(
                c,
                f"""
                query {{ issueLabels(filter: {{team: {{id: {{eq: "{team_id}"}}}}}}) {{
                    nodes {{ id name }}
                }} }}
            """,
            )
            existing_label_names = {lbl["name"] for lbl in existing_labels["issueLabels"]["nodes"]}
            for label_name, color in LABELS:
                if label_name in existing_label_names:
                    print(f"  · Label '{label_name}' exists, skip")
                    continue
                try:
                    _linear_gql(
                        c,
                        """
                        mutation Create($input: IssueLabelCreateInput!) {
                            issueLabelCreate(input: $input) { success }
                        }
                    """,
                        {"input": {"name": label_name, "color": color, "teamId": team_id}},
                    )
                    print(f"  · Created label '{label_name}'")
                except RuntimeError as e:
                    msg = str(e).lower()
                    if "duplicate" in msg or "already exists" in msg:
                        print(f"  · Label '{label_name}' already in workspace, skip")
                        continue
                    raise

            print(
                "  ⚠ Custom fields: free-tier may not allow; fallback to labels (phase:P1, feature:F02)"
            )
            return {"status": "completed", "detail": f"team={team_id}, projects_created={created}"}
    except Exception as e:  # noqa: BLE001
        return {"status": "halted", "detail": f"Linear setup error: {e}"}


def automate_c3_execute() -> dict:
    """Run linear_migrate.py --dry-run then --execute --confirm."""
    script = REPO_ROOT / "scripts" / "linear_migrate.py"
    if not script.exists():
        return {"status": "halted", "detail": "scripts/linear_migrate.py not found"}
    try:
        print("  · --dry-run...")
        dry = subprocess.run(  # noqa: S603
            [sys.executable, str(script), "--dry-run"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if dry.returncode != 0:
            return {"status": "halted", "detail": f"dry-run failed: {dry.stderr[-2000:]}"}
        print("  · --execute --confirm...")
        ex = subprocess.run(  # noqa: S603
            [sys.executable, str(script), "--execute", "--confirm"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        if ex.returncode != 0:
            return {"status": "halted", "detail": f"execute failed: {ex.stderr[-2000:]}"}
        return {"status": "completed", "detail": "migration done"}
    except subprocess.TimeoutExpired:
        return {"status": "halted", "detail": "script timeout"}
    except Exception as e:  # noqa: BLE001
        return {"status": "halted", "detail": str(e)}


def automate_c4_deploy() -> dict:
    """Deploy ops_api/ to Railway via CLI."""
    try:
        whoami = subprocess.run(  # noqa: S603,S607
            ["railway", "whoami"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if whoami.returncode != 0:
            return {"status": "halted", "detail": "railway CLI not authed. Run `railway login`"}
    except FileNotFoundError:
        return {"status": "halted", "detail": "railway CLI not installed"}

    if not (REPO_ROOT / "ops_api").exists():
        return {"status": "halted", "detail": "ops_api/ not present (C-4 not merged?)"}

    try:
        print("  · railway up...")
        deploy = subprocess.run(  # noqa: S603,S607
            ["railway", "up", "--detach"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if deploy.returncode != 0:
            return {"status": "halted", "detail": f"railway up failed: {deploy.stderr[-2000:]}"}

        domain_proc = subprocess.run(  # noqa: S603,S607
            ["railway", "domain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        domain = domain_proc.stdout.strip()
        if domain:
            print(f"  · smoke test https://{domain}/healthz")
            for _ in range(12):
                try:
                    r = httpx.get(f"https://{domain}/healthz", timeout=10)
                    if r.status_code == 200 and "ok" in r.text:
                        return {"status": "completed", "detail": f"deployed at {domain}"}
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(5)
            return {"status": "halted", "detail": f"healthz never returned 200 at {domain}"}
        return {"status": "completed", "detail": "deployed (no domain)"}
    except Exception as e:  # noqa: BLE001
        return {"status": "halted", "detail": str(e)}


def automate_d6_branch_protection() -> dict:
    """Apply branch protection via gh api."""
    try:
        if os.environ.get("GH_REPO"):
            repo = os.environ["GH_REPO"]
        else:
            r = subprocess.run(  # noqa: S603,S607
                ["git", "config", "--get", "remote.origin.url"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=5,
            )
            m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", r.stdout.strip())
            if not m:
                return {"status": "halted", "detail": f"could not parse repo: {r.stdout}"}
            repo = m.group(1)

        protection = {
            "required_status_checks": {
                "strict": True,
                "contexts": ["ci/pytest", "ci/lint", "pr-validate"],
            },
            "enforce_admins": False,
            "required_pull_request_reviews": {
                "required_approving_review_count": 1,
                "require_code_owner_reviews": True,
                "dismiss_stale_reviews": True,
            },
            "restrictions": None,
            "allow_force_pushes": False,
            "allow_deletions": False,
        }
        proc = subprocess.run(  # noqa: S603,S607
            ["gh", "api", "-X", "PUT", f"repos/{repo}/branches/main/protection", "--input", "-"],
            input=json.dumps(protection),
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            return {"status": "halted", "detail": f"gh api failed: {proc.stderr[-1000:]}"}
        return {"status": "completed", "detail": f"branch protection set on {repo}/main"}
    except FileNotFoundError:
        return {"status": "halted", "detail": "gh CLI not installed"}
    except Exception as e:  # noqa: BLE001
        return {"status": "halted", "detail": str(e)}


def automate_d5_templates() -> dict:
    """Create Linear issue templates from spec doc. Falls back to manual if API unsupported."""
    spec = REPO_ROOT / "docs" / "operations" / "linear-issue-templates.md"
    if not spec.exists():
        return {"status": "halted", "detail": "linear-issue-templates.md not found"}
    try:
        with _linear_client() as c:
            data = _linear_gql(c, "query { teams { nodes { id name } } }")
            team_id = next(
                (
                    t["id"]
                    for t in data["teams"]["nodes"]
                    if t["name"] == os.environ.get("LINEAR_TEAM_NAME", "Engineering")
                ),
                None,
            )
            if not team_id:
                return {"status": "halted", "detail": "team not found"}
            spec_text = spec.read_text()
            templates = re.findall(
                r"##\s+Template\s+\d+:\s+(\w+).*?\*\*Body template:\*\*\s*```\s*\n(.*?)```",
                spec_text,
                re.DOTALL,
            )
            if len(templates) < 4:
                return {"status": "halted", "detail": f"parsed only {len(templates)} templates"}
            created = 0
            for name, body in templates:
                try:
                    _linear_gql(
                        c,
                        """
                        mutation Create($input: IssueTemplateCreateInput!) {
                            issueTemplateCreate(input: $input) { success }
                        }
                    """,
                        {"input": {"name": name, "description": body, "teamId": team_id}},
                    )
                    created += 1
                except Exception as e:  # noqa: BLE001
                    print(f"  ⚠ Template '{name}' failed: {e}")
            if created == 0:
                return {
                    "status": "halted",
                    "detail": "Linear plan doesn't support issueTemplateCreate. "
                    "Founder paste manually from docs/operations/linear-issue-templates.md",
                }
            return {"status": "completed", "detail": f"{created}/4 templates created"}
    except Exception as e:  # noqa: BLE001
        return {"status": "halted", "detail": str(e)}


AUTOMATORS = {
    "C-2": automate_c2_linear_setup,
    "C-3-execute": automate_c3_execute,
    "C-4-deploy": automate_c4_deploy,
    "D-6-protect": automate_d6_branch_protection,
    "D-5-templates": automate_d5_templates,
}

MUST_BE_FOUNDER = {"C-3.0", "D-2.1", "C-5.3"}


def can_automate(item_id: str) -> bool:
    return item_id in AUTOMATORS


def run_automator(item_id: str) -> dict:
    if item_id not in AUTOMATORS:
        return {"status": "halted", "detail": f"no automator for {item_id}"}
    print(f"  Running automator for {item_id}...")
    try:
        return AUTOMATORS[item_id]()
    except Exception as e:  # noqa: BLE001
        return {"status": "halted", "detail": f"automator exception: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: autopilot_manual_automators.py <item-id>")
        sys.exit(2)
    print(json.dumps(run_automator(sys.argv[1]), indent=2))
