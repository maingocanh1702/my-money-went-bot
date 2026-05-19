---
title: Walk-through — Foundation Lane example (admin-auth)
status: Reference
version: v1.0.0
date: 2026-05-19
author: Founder + Claude
related:
  - docs/operations/linear-and-dashboard-workflow.md
  - docs/operations/dashboard-plan-state-split.md
  - docs/operations/fast-quality-workflow.md
  - docs/operations/development-workflow.md
  - CLAUDE.md
---

# Walk-through — Foundation Lane example: `admin-auth`

> **Status:** Reference · Active
> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-19
> **Mục đích:** Concrete worked example cho 1 P0/Foundation Lane feature đi qua đầy đủ Linear → tracker → spec → branch → code → PR → cross-model review → merge → deploy. Dùng `admin-auth` làm vehicle. Áp dụng same shape cho mọi P0 feature sau này (admin-commands Phase 6, multi-tenant migration W0.1, security/auth changes).

---

## TL;DR

`admin-auth` là P0/Foundation Lane work item. Walk-through dưới đây show từng artifact concrete ở mỗi step — Linear ticket content, tracker row, spec doc skeleton, branch command, code module, PR body, Codex finding, founder sign-off. So sánh state Linear vs dashboard sau mỗi step.

Mục tiêu: founder mở doc này khi start P0 feature tiếp theo, replace từng artifact theo template, không phải nhớ rules từ trí nhớ.

Đây là **complement** với §7 của [`linear-and-dashboard-workflow.md`](linear-and-dashboard-workflow.md) (dùng `funding-sources` P1/Standard làm vehicle) — same flow shape nhưng khác:

| Aspect | §7 funding-sources (Standard) | This doc admin-auth (Foundation) |
|---|---|---|
| Risk tier | P1 | **P0** |
| Lane | Standard | **Foundation** |
| Cross-model review | Recommended | **Mandatory** |
| Review round cap | 5 | **8** (founder approval after 5) |
| Auto-merge | Opt-in `--auto-merge` | **Never** |
| Founder approval gate | No | **Yes — sign-off in PR body** |
| Tenant isolation test | Recommended | **Mandatory** (security-adjacent) |
| Migration | Optional | **Reversible required** |

---

## 0. Why `admin-auth` chosen as example

3 lý do:

1. **Đã có trong tracker** — không hypothetical, founder có thể follow doc + ship feature thật.
2. **Touches security + multi-tenant** — exercise được CLAUDE.md hard rules #4 + #5 đồng thời.
3. **Migration involved** — show được alembic reversibility, Railway auto-deploy hook, dashboard deploy_state transition.

Feature scope:
- Build `is_admin(user_id) -> bool` + `@admin_required` decorator
- Add `admins` table với migration
- Bootstrap: founder = `user_id=1` (per memory `project_wave0_gap_decisions.md`)
- **Out of scope** (defer Phase 6): admin commands (`/admin_stats`, `/admin_cost`, `/admin_user`, `/admin_resolve`), audit log wiring

---

## 1. Plan source artifacts

### 1.1 Linear ticket — MMW-202

```
ID: MMW-202
Title: Admin auth framework (commands deferred to Phase 6)
Type: feature
Priority: P0
Risk tier: P0 (security/auth + multi-tenant)
Lane: Foundation
Cycle: Phase 2 (2026-05-22 → 2026-06-15)
Assignee: founder
Labels: security, framework, multi-tenant

Description:
Foundation cho /admin_* commands sau này. Phase 2 chỉ ship framework + 
identity check + tenant isolation. Commands defer Phase 6.

Acceptance criteria:
- [ ] Admin identity verified via Telegram user_id (FOUNDER_TELEGRAM_ID env, default 1)
- [ ] @admin_required decorator usable bởi handler functions
- [ ] Non-admin call → silent ignore (no leak about command existence)
- [ ] Anonymous webhook (message.from_user is None) → silent reject
- [ ] Tenant isolation tests pass cho admin path + non-admin path + anonymous
- [ ] Migration 0042_admins reversible (alembic downgrade tested)
- [ ] Audit log wiring deferred to Phase 6 (out of scope, document trong spec)

Dependencies: None
External blockers: None
Decision needed: None
```

Linear column: **Backlog**.

### 1.2 Tracker row

Edit `docs/implementation-tracker.md`, add row:

```markdown
| feature_id | name | linear_id | phase | priority | risk_tier | lane | branches | specs.product | specs.tech | acceptance |
|---|---|---|---|---|---|---|---|---|---|---|
| admin-auth | Admin auth framework | MMW-202 | 2 | P0 | P0 | Foundation | feat/MMW-202-admin-auth | docs/features/feature-admin-auth.md | docs/features/BE/feature-admin-auth-tech.md | FS resolver + tenant isolation tests + reversible migration |
```

Commit tracker change. Build script chạy, dashboard rebuild.

Dashboard state sau commit:
```
admin-auth · Phase 2 · P0 · Foundation
status: not-started · progress: 0%
signals: spec=✗ tech=✗ branch=✗ pr=∅ ci=∅ deploy=∅
```

### 1.3 FE/product spec

File: `docs/features/feature-admin-auth.md`

Skeleton:
```markdown
# Feature: admin-auth

## Goal
Framework cho admin commands (Phase 6). Phase 2 chỉ ship identity check + decorator.

## User experience
- Admin user (founder = user_id=1) gõ /admin_command → bot respond.
- Non-admin user gõ cùng command → **silent ignore** (bot không reply, không log error to user).
- Anonymous webhook (no user_id) → silent reject.

## Why silent?
Leak prevention. Nếu bot reply "you are not admin", attacker biết command exists 
+ probe để guess admin user. Silent = không leak existence.

## Edge cases
- Admin lost access (revoked) → @lru_cache invalidate trong 60s (TTL).
- Founder bootstrap: nếu DB empty hoặc startup glitch, FOUNDER_TELEGRAM_ID=1 luôn admin.

## Out of scope (defer Phase 6)
- Specific commands (/admin_stats, etc.)
- Audit log wiring (column granularity)
- Admin invite/revoke UI

## Acceptance criteria
[mirror Linear ticket AC]

## Test cases (high-level)
- Founder (id=1) → is_admin returns True without DB hit (bootstrap)
- Regular user (id=2) not in admins table → False
- Anonymous (from_user=None) → silent reject path
- Tenant isolation: admin sees all, non-admin sees own
```

### 1.4 BE tech spec

File: `docs/features/BE/feature-admin-auth-tech.md`

Skeleton:
```markdown
# BE tech spec: admin-auth

## Module structure
- `core/auth/__init__.py`
- `core/auth/admin.py` — public API: is_admin(), admin_required decorator
- `core/auth/cache.py` — TTLCache wrapper (60s TTL, maxsize=128)

## Public API
```python
async def is_admin(user_id: int) -> bool: ...

def admin_required(handler: Callable) -> Callable: ...
```

## Data model
```sql
-- migrations/0042_admins.sql
CREATE TABLE admins (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    granted_by BIGINT NOT NULL REFERENCES users(user_id),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_admins_granted_at ON admins(granted_at);

-- Down migration (alembic downgrade): DROP TABLE admins CASCADE;
```

## Bootstrap behavior
- `FOUNDER_TELEGRAM_ID` env var (default `1`).
- Inside is_admin: if `user_id == FOUNDER_TELEGRAM_ID` → return True without DB hit.
- This satisfies Wave 0 decision "founder=id=1 bootstrap-only assumption" 
  (memory `project_wave0_gap_decisions.md`).

## Cache invalidation
- TTLCache 60s — trade-off: admin revoke có ≤60s lag, acceptable per founder.
- Manual cache_clear() exposed cho future admin grant/revoke flow Phase 6.

## Test plan (5 categories per Wave 0 lessons)
1. Bootstrap unit: founder=admin without DB
2. DB lookup unit: non-founder admin/non-admin states
3. Decorator behavior: pass-through + silent ignore + anonymous reject
4. Tenant isolation integration: admin user sees all, non-admin sees own (MANDATORY)
5. Migration reversibility: alembic upgrade + downgrade round-trip

## Failure modes
- DB unavailable during is_admin lookup → log + return False (fail closed, no leak)
- Cache corrupt → cache_clear() + reload
- Migration partial fail → alembic rollback (Postgres DDL transactional)
```

After saving 2 spec files + tracker row commit, dashboard rebuilds:
```
admin-auth · Phase 2 · P0 · Foundation
status: tech-ready · progress: 25%
signals: spec=✓ tech=✓ branch=✗ pr=∅ ci=∅ deploy=∅
events.jsonl: spec_created, tech_created
```

Linear ticket: vẫn "Backlog" (founder chưa move, Linear's GitHub integration không fire vì chưa có branch).

---

## 2. Step-by-step walk-through

### Step 2 — Branch + worktree creation (T+2 day)

```bash
# In main worktree
cd /Users/maingocanh/Projects/MyMoneyWent
source .venv/bin/activate      # per memory feedback_activate_venv_before_commit.md
git fetch origin

# Create new worktree for parallel session (CLAUDE.md hard rule #1)
git worktree add ../MyMoneyWent-admin-auth feat/MMW-202-admin-auth -b
cd ../MyMoneyWent-admin-auth
```

Branch name `feat/MMW-202-admin-auth` matches `pr-validate.yml` regex `^[a-z0-9-]+/MMW-[0-9]+-[a-z0-9-]+$`.

Engine events:
- `branch_created` → state `tech-ready → in-progress`
- signals: `branch=✓ commits=0`

| Linear | Dashboard |
|--------|-----------|
| Backlog → **In Progress** (auto via integration, hoặc manual) | `in-progress` 30% |

### Step 3 — Code + commits (T+2 to T+4)

Implement theo BE tech spec:

```python
# core/auth/__init__.py
from core.auth.admin import is_admin, admin_required

__all__ = ["is_admin", "admin_required"]
```

```python
# core/auth/admin.py
import os
from functools import wraps
from typing import Callable, Optional

from cachetools import TTLCache
from cachetools.keys import hashkey

from core.db import get_session
from core.db.models import Admin

FOUNDER_TELEGRAM_ID = int(os.getenv("FOUNDER_TELEGRAM_ID", "1"))

# TTL 60s — admin revoke lag accepted per spec
_admin_cache: TTLCache[int, bool] = TTLCache(maxsize=128, ttl=60)


async def is_admin(user_id: int) -> bool:
    """Check if user_id is admin.

    Bootstrap: FOUNDER_TELEGRAM_ID always admin (no DB hit).
    Otherwise: DB lookup + TTL cache.
    Fail closed: DB error → False (no leak).
    """
    if user_id == FOUNDER_TELEGRAM_ID:
        return True

    cached = _admin_cache.get(user_id)
    if cached is not None:
        return cached

    try:
        async with get_session() as session:
            admin = await session.get(Admin, user_id)
            result = admin is not None
            _admin_cache[user_id] = result
            return result
    except Exception:
        # Fail closed — log via structlog, return False
        # ... structlog.warn("admin.lookup.failed", user_id=user_id)
        return False


def admin_required(handler: Callable) -> Callable:
    """Decorator: silent ignore for non-admin / anonymous calls."""
    @wraps(handler)
    async def wrapper(message, *args, **kwargs):
        if message.from_user is None:
            return  # silent — anonymous reject
        if not await is_admin(message.from_user.id):
            return  # silent — non-admin reject
        return await handler(message, *args, **kwargs)
    return wrapper


def cache_clear() -> None:
    """For future admin grant/revoke flow Phase 6."""
    _admin_cache.clear()
```

```python
# tests/core/auth/test_admin.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.auth.admin import is_admin, admin_required, cache_clear, FOUNDER_TELEGRAM_ID


@pytest.fixture(autouse=True)
def clear_cache():
    cache_clear()
    yield
    cache_clear()


# Category 1: Bootstrap unit
async def test_founder_is_admin_without_db_hit():
    """Bootstrap: founder always admin, no DB call."""
    assert await is_admin(FOUNDER_TELEGRAM_ID) is True


# Category 2: DB lookup unit
async def test_user_in_admins_table_returns_true(db):
    # ... insert admin row, assert True
    ...

async def test_user_not_in_admins_table_returns_false(db):
    assert await is_admin(99999) is False


# Category 3: Decorator behavior
async def test_admin_required_silent_ignore_non_admin():
    handler = AsyncMock()
    @admin_required
    async def my_handler(msg): return await handler(msg)
    msg = MagicMock(from_user=MagicMock(id=999))
    result = await my_handler(msg)
    assert result is None
    handler.assert_not_called()

async def test_admin_required_silent_reject_anonymous():
    handler = AsyncMock()
    @admin_required
    async def my_handler(msg): return await handler(msg)
    msg = MagicMock(from_user=None)
    result = await my_handler(msg)
    assert result is None
    handler.assert_not_called()

async def test_admin_required_passes_through_admin():
    handler = AsyncMock(return_value="ok")
    @admin_required
    async def my_handler(msg): return await handler(msg)
    msg = MagicMock(from_user=MagicMock(id=FOUNDER_TELEGRAM_ID))
    result = await my_handler(msg)
    assert result == "ok"
    handler.assert_called_once_with(msg)


# Category 4: Tenant isolation integration (MANDATORY per CLAUDE.md hard rule #4)
async def test_tenant_isolation_admin_sees_all_tenants(db, founder, tenant_a, tenant_b):
    # ... admin queries → see both tenant_a + tenant_b data
    ...

async def test_tenant_isolation_non_admin_sees_own_only(db, user_a, tenant_a, tenant_b):
    # ... user_a queries → see only tenant_a data
    ...


# Category 5: Cache + edge cases
async def test_cache_hit_avoids_db_lookup(mocker, db):
    # ... first call hits DB, second hits cache
    ...

async def test_cache_clear_invalidates(db):
    # ... cache_clear() forces re-lookup
    ...
```

Migration:
```sql
-- migrations/versions/0042_admins.sql
-- Up
CREATE TABLE admins (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    granted_by BIGINT NOT NULL REFERENCES users(user_id),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_admins_granted_at ON admins(granted_at);

-- Down
DROP TABLE admins CASCADE;
```

Conventional Commits style (CLAUDE.md):
```
feat(admin-auth): add FOUNDER_TELEGRAM_ID bootstrap + is_admin function
feat(admin-auth): add @admin_required decorator with silent ignore
feat(admin-auth): add admins table migration (0042)
test(admin-auth): tenant isolation tests for admin/non-admin/anonymous paths
test(admin-auth): cache hit/clear + bootstrap edge cases
```

5 commits. Engine events:
```
commit_added × 5
```

State machine: vẫn `in-progress` (chưa PR), progress nhích lên ~50%.

Dashboard:
```
admin-auth · Phase 2 · P0 · Foundation
status: in-progress · progress: 50%
signals: spec=✓ tech=✓ branch=✓ commits=5 pr=∅ ci=∅
```

| Linear | Dashboard |
|--------|-----------|
| In Progress | `in-progress` 50% |

### Step 4 — Push + PR open (T+4)

```bash
git push -u origin feat/MMW-202-admin-auth

gh pr create \
  --base main \
  --title "feat(admin-auth): admin auth framework (Closes MMW-202)" \
  --body-file - <<'EOF'
## What
Admin auth framework — `is_admin()` + `@admin_required` decorator + `admins` table 
migration. **No commands yet** (deferred to Phase 6).

## Why
Foundation cho `/admin_*` commands sau này (Phase 6). Lock identity check + tenant 
isolation **trước** khi viết command, không retrofit security sau.

## How
- `core/auth/admin.py` — is_admin + decorator + TTLCache 60s
- `migrations/0042_admins.sql` — admins table (reversible)
- `FOUNDER_TELEGRAM_ID` env var, default 1 (Wave 0 bootstrap)
- Silent ignore design — no leak about command existence

## Tests
- 11 unit tests (5 categories per Wave 0 lessons)
- 4 integration tests cho tenant isolation (admin path + non-admin + anonymous)
- All required CI: test ✓ pre-commit ✓ import-linter ✓

## Acceptance criteria
- [x] Admin identity via Telegram user_id (env-configurable)
- [x] @admin_required decorator usable
- [x] Non-admin → silent ignore
- [x] Anonymous → silent reject
- [x] Tenant isolation tests pass
- [x] Migration reversible (downgrade tested local)
- [ ] Audit log — deferred Phase 6 per spec scope

## Risk + blast radius
- New module, no breaking change to existing code
- Migration additive (CREATE TABLE), no data loss path
- Cache TTL 60s — admin revoke lag accepted (documented)

Closes MMW-202
EOF
```

PR #87 created.

GitHub events:
- `pull_request opened` → engine: `pr_opened`, state `in-progress → in-review`
- `workflow_run` CI starts → overlay `ci-running`

Required checks run (per CLAUDE.md):
- ruff (lint) ✓
- black (format) ✓
- mypy strict on core/markets/i18n ✓
- pytest ✓ (15 tests pass)
- import-linter ✓ (no boundary violation)
- detect-secrets ✓

CI green sau ~4 phút. Engine: `ci_passed`, overlay `ci-running` cleared.

Linear: integration link PR #87 vào ticket MMW-202. Auto-move sang "In Review".

Dashboard:
```
admin-auth · Phase 2 · P0 · Foundation
status: in-review · progress: 60%
signals: spec=✓ tech=✓ branch=✓ commits=5 pr=open ci=pass review=pending
```

| Linear | Dashboard |
|--------|-----------|
| In Progress → **In Review** | `in-review` 60% |

### Step 5 — Cross-model review (Codex, T+4 to T+5)

> **Hard rule #5: P0/Foundation → Codex review mandatory. NO self-review.**

Tag Codex review trên PR. Codex round 1 — 3 findings:

```
[Codex Review · Round 1]

Finding 1 (BLOCKER):
core/auth/admin.py:18 — FOUNDER_TELEGRAM_ID hardcoded fallback `1` in os.getenv 
default. Acceptable for dev, but prod should fail loudly if env not set 
(security-sensitive). Recommend: raise ConfigError if FOUNDER_TELEGRAM_ID unset 
in production (detect via ENV=production check).

Finding 2 (MAJOR):
core/auth/admin.py:30-40 — except Exception in is_admin() catches everything, 
hides programming bugs (TypeError, AttributeError). Narrow to (asyncpg.PostgresError, 
asyncio.TimeoutError, sqlalchemy.exc.SQLAlchemyError) — explicit DB error categories.

Finding 3 (MINOR):
tests/core/auth/test_admin.py — thiếu test cho TTL expiry. Add freezegun-based 
test: set admin in cache, advance time 61s, assert re-lookup.
```

Engine: `changes_requested`, state `in-review → changes-requested`.

Dashboard:
```
admin-auth · Phase 2 · P0 · Foundation
status: changes-requested · progress: 60%
signals: review_state=changes-requested
overlay: (none, just status change)
```

Founder address 3 findings:

**Finding 1 fix:**
```python
# core/config.py
import os

ENV = os.getenv("ENV", "development")

_founder_id_raw = os.getenv("FOUNDER_TELEGRAM_ID")
if _founder_id_raw is None:
    if ENV == "production":
        raise RuntimeError(
            "FOUNDER_TELEGRAM_ID required in production — refusing to start "
            "with default fallback to id=1 (would grant founder access to wrong user)."
        )
    _founder_id_raw = "1"  # dev fallback

FOUNDER_TELEGRAM_ID = int(_founder_id_raw)
```

**Finding 2 fix:**
```python
import asyncpg
import asyncio
from sqlalchemy.exc import SQLAlchemyError

# In is_admin:
try:
    ...
except (asyncpg.PostgresError, asyncio.TimeoutError, SQLAlchemyError) as e:
    structlog.warn("admin.lookup.failed", user_id=user_id, error_type=type(e).__name__)
    return False  # fail closed
```

**Finding 3 fix:**
```python
# tests/core/auth/test_admin.py
from freezegun import freeze_time
import datetime

async def test_ttl_cache_expires_after_60s(db):
    with freeze_time("2026-05-19 10:00:00") as frozen:
        await is_admin(999)  # populates cache
        frozen.tick(delta=datetime.timedelta(seconds=61))
        # Next call should re-lookup, not hit cache
        # ... assert via mock spy on DB session
```

Push 3 fix commits:
```
fix(admin-auth): raise ConfigError if FOUNDER_TELEGRAM_ID unset in prod
fix(admin-auth): narrow exception catch in is_admin to DB errors only
test(admin-auth): add TTL expiry test with freezegun
```

CI re-run → green sau 3 phút. Re-request Codex review.

Codex round 2: approve. Engine: `approved`, state `changes-requested → approved-pending-merge`.

Round counter check:
- Foundation Lane cap: 8 rounds (founder approval after 5)
- This PR: 2 rounds used → còn 6 buffer

Dashboard:
```
admin-auth · Phase 2 · P0 · Foundation
status: approved-pending-merge · progress: 85%
signals: review_state=approved · 8 commits total
```

| Linear | Dashboard |
|--------|-----------|
| In Review | `approved-pending-merge` 85% |

### Step 6 — Founder approval gate (T+5)

> **Hard rule #6: Foundation Lane never auto-merges. Founder manual squash + sign-off required.**

Founder review trên PR:

| Check | Pass? |
|-------|-------|
| Codex's 3 findings addressed | ✓ all 3 |
| AC checkboxes complete | ✓ (audit defer = scope-correct) |
| Tenant isolation tests | ✓ 4 integration tests pass |
| No legacy file mod | ✓ (CLAUDE.md "don't extend legacy") |
| Migration reversible | ✓ tested alembic downgrade local |
| Blast radius documented | ✓ in PR body |
| No `--auto-merge` | ✓ Foundation Lane never auto-merges |
| Cross-model review done | ✓ Codex round 1+2 |

Sign-off comment trên PR:
```
Foundation Lane founder approval:

AC: met (audit defer per spec scope)
Cross-model review: Codex 2 rounds, all addressed
Blast radius: new module + additive migration, no breaking change
Known tradeoffs: TTLCache 60s admin revoke lag (documented in spec)
Migration verified reversible: alembic downgrade tested local
Test coverage: 5-category plan (Wave 0 standard), tenant isolation MANDATORY met

Ready to squash-merge.
```

Click "Squash and merge" trên GitHub UI.

GitHub: PR #87 closed (merged=true). Engine: `merged`, state `approved-pending-merge → merged`.

Linear's GitHub integration: detect "Closes MMW-202" + merged → auto-move ticket sang "Done".

Dashboard:
```
admin-auth · Phase 2 · P0 · Foundation
status: merged · progress: 95%
signals: pr_state=merged · merge_sha=a4b2c1d
```

| Linear | Dashboard |
|--------|-----------|
| In Review → **Done** (auto) | `merged` 95% |

### Step 7 — Railway deploy (auto, T+5)

Railway webhook fires sau push lên main:

1. Build container (~30s) — copy code + install deps
2. Run alembic migrations:
   ```
   $ alembic upgrade head
   INFO  [alembic.runtime.migration] Running upgrade 0041 -> 0042, add admins table
   ```
3. Deploy new replica (~60s)
4. Health check `GET /healthz` pass
5. Switch traffic to new replica
6. Old replica drained

Total ~90 seconds from merge to live.

Engine events:
- `deploy_started` → state `merged → deploying`
- `deploy_succeeded` → state `deploying → deployed`

Dashboard final:
```
admin-auth · Phase 2 · P0 · Foundation
status: deployed · progress: 100%
signals: ALL ✓ · deploy_commit=a4b2c1d
events.jsonl: 14 events spanning T0 → T+5 (~5 days)
```

| Linear | Dashboard |
|--------|-----------|
| Done | **`deployed` 100%** |

Note Linear không phân biệt được "merged" vs "deployed" — đây là dashboard-only signal.

### Step 8 — Cleanup (T+5)

```bash
cd /Users/maingocanh/Projects/MyMoneyWent
git fetch --prune
git worktree remove ../MyMoneyWent-admin-auth
```

Remote branch auto-deleted sau merge (nếu Railway/GitHub config). Engine PR identity resolution: cached `github_pr=#87` trong `.dashboard/state-cache.json` resolve → state vẫn `deployed`, history preserved.

Final dashboard state stay `deployed` indefinitely (until next change).

---

## 3. Side-by-side state table

Linear column vs dashboard status xuyên suốt walk-through:

| Step | Time | Linear column | Dashboard status | Progress | Drift |
|------|------|---------------|------------------|----------|-------|
| 0 Plan | T+0 | Backlog | — (chưa exist) | — | Linear lead |
| 1 Tracker+Spec | T+1 | Backlog | `tech-ready` | 25% | minor (Linear ko track spec) |
| 2 Branch | T+2 | In Progress (auto) | `in-progress` | 30% | aligned |
| 3 Code | T+2→T+4 | In Progress | `in-progress` | 50% | aligned |
| 4 PR open | T+4 | In Review (auto) | `in-review` | 60% | aligned |
| 5a CR Codex | T+4 | In Review | `changes-requested` | 60% | minor (Linear ko sub-state) |
| 5b Approved | T+5 | In Review | `approved-pending-merge` | 85% | minor |
| 6 Merge | T+5 | Done (auto) | `merged` | 95% | aligned |
| 7 Deploy | T+5+90s | Done | **`deployed`** | 100% | dashboard mạnh hơn |
| 8 Cleanup | T+5 | Done | `deployed` (PR cache) | 100% | history preserved |

---

## 4. MMW rules invoked + which step

| Rule | Source | Applied where |
|------|--------|---------------|
| 1 session per `.git/` | CLAUDE.md hard rule #1 | Step 2 — worktree pattern |
| Never auto-delete `.md` | CLAUDE.md hard rule #2 | Throughout — commit before destructive ops |
| Spec-first | CLAUDE.md hard rule #3 | Step 1 — FE+BE spec trước code |
| Tenant isolation test mandatory | CLAUDE.md hard rule #4 | Step 3 — 4 integration tests |
| Cross-model review P0/P1 | CLAUDE.md hard rule #5 | Step 5 — Codex 2 rounds |
| Auto-merge opt-in | CLAUDE.md hard rule #6 | Step 6 — Foundation never auto-merges |
| Single-phase autopilot scope | CLAUDE.md hard rule #7 | N/A (no autopilot used here) |
| Review cap by lane | CLAUDE.md hard rule #8 | Step 5 — Foundation cap 8, used 2 |
| Manual fallback when blocked | CLAUDE.md hard rule #9 | N/A (no blocker hit) |
| Conventional Commits | CLAUDE.md style | Step 3 + 5 — commit messages |
| Activate venv before commit | memory `feedback_activate_venv_before_commit.md` | Step 2 setup |
| FOUNDER=id=1 bootstrap | memory `project_wave0_gap_decisions.md` | Step 3 code + Finding 1 fix |
| 5-category test plan upfront | memory `feedback_wave0_lessons.md` | Step 1 BE tech spec + Step 3 tests |
| Founder approval = sign-off in PR body | memory `project_autopilot_risk_tier_policy.md` | Step 6 |

---

## 5. Differences vs Standard Lane (`funding-sources`)

Side-by-side với §7 walkthrough trong [`linear-and-dashboard-workflow.md`](linear-and-dashboard-workflow.md):

| Aspect | Standard Lane (funding-sources) | Foundation Lane (admin-auth) |
|--------|-------------------------------|------------------------------|
| Risk tier | P1 | P0 |
| Cross-model review | Recommended (Codex) | **MANDATORY** Codex, no self-review |
| Review round cap | 5 | **8** (founder approval after 5) |
| Auto-merge | Opt-in `--auto-merge` flag | **Never** allowed |
| Founder approval gate | No formal gate | **Yes** — sign-off comment in PR |
| Tenant isolation test | Recommended | **MANDATORY** (security-adjacent) |
| Migration reversibility | If migration involved | **MANDATORY** if migration involved |
| Spec verbosity | Brief OK | Detailed required (security implications) |
| Failure mode documentation | Brief | Explicit (fail-closed, leak prevention) |
| Risk + blast radius in PR body | Optional | **Required** |
| Cache invalidation strategy | Per implementation | **Required documented** (security-relevant) |

---

## 6. Failure modes + recovery

Realistic scenarios mà founder có thể gặp trong Foundation Lane work.

### 6.1 CI fail at round 1 (test broken)

**Trigger**: push lên feat branch, CI red.

**State**: PR open, `ci-failing` overlay, status `in-review`.

**Recovery**:
1. Click "Details" trên failing check → see test output
2. Fix locally trong worktree
3. Push fix commit
4. CI re-run → overlay clears nếu green

**Round count**: không tính round Codex — CI fail/fix iteration không count vào review cap.

### 6.2 Codex round cap exceeded (round 8 reached)

**Trigger**: Foundation Lane, đã 8 round Codex review nhưng vẫn còn issue.

**State**: status `changes-requested`, founder cần decide.

**Recovery options (per memory `feedback_f07_lessons.md`)**:
- **Split PR**: scope quá lớn → split thành 2 PR nhỏ hơn. Cherry-pick safe commits, retreat scope.
- **Manual review**: tạm bỏ Codex, founder + 1 trusted reviewer (nếu có) thay vào.
- **Revisit Foundation classification**: maybe scope thực sự là Standard. Re-classify, restart review với cap 5.

**Đừng làm**: loop round 9, 10... vô hạn. Cap exists vì lý do.

### 6.3 Scope creep discovered mid-PR

**Trigger**: code review reveal feature cần thêm 1 module liên quan ngoài scope ban đầu.

**State**: status `in-review`, founder muốn add scope.

**Recovery**:
- **Resist add scope** to current PR. Open separate Linear ticket + tracker row cho add-on work.
- Current PR ship scope ban đầu. Add-on work là PR #2.
- Lý do: Foundation Lane PR đã có blast radius documented; expand scope = re-do risk review.

### 6.4 Migration fail in production deploy

**Trigger**: PR merged, Railway run alembic upgrade, migration fail.

**State**: dashboard `deploy_state=deploy-failed`, status overlay `deploy-failed`.

**Recovery (DR runbook style)**:
1. Railway auto-rollback to previous container (~10s) — main code chưa apply
2. Alembic state: nếu migration partial → manually rollback via `alembic downgrade -1`
3. Open Linear ticket "Hotfix admin-auth migration" với linear_id new
4. Fix migration locally, test downgrade + upgrade round-trip
5. New PR via `hotfix/*` exempt branch (CLAUDE.md exempt list)
6. Foundation Lane gates still apply — Codex review even for hotfix

### 6.5 Founder approval blocked (tenant isolation test fails post-merge)

**Trigger**: PR merged, deployed, sau đó phát hiện 1 tenant isolation case fail trong production.

**State**: critical incident.

**Recovery**:
- Run `engineering:incident-response` skill
- Triage severity, communicate to stakeholders (Linear ticket update)
- Postmortem trong `docs/postmortems/<date>-admin-auth-leak.md`
- Fix + new PR (Foundation Lane gates apply)
- Update test plan — add regression test cho specific case missed
- Memory update — record lesson for future Foundation work

---

## 7. Re-use template cho P0 feature khác

Substitution table — replace admin-auth specifics với feature mới:

| Field | admin-auth value | Your feature (fill in) |
|-------|------------------|------------------------|
| feature_id | `admin-auth` | `<your-feature-kebab>` |
| linear_id | `MMW-202` | `MMW-<new-id>` |
| Phase | 2 | `<phase>` |
| Branch prefix | `feat/MMW-202-admin-auth` | `feat/MMW-<id>-<slug>` |
| Spec path | `docs/features/feature-admin-auth.md` | `docs/features/feature-<slug>.md` |
| Tech spec | `docs/features/BE/feature-admin-auth-tech.md` | `docs/features/BE/feature-<slug>-tech.md` |
| Module path | `core/auth/admin.py` | `core/<area>/<module>.py` |
| Migration file | `0042_admins.sql` | `<next>_<name>.sql` |
| Test file | `tests/core/auth/test_admin.py` | `tests/core/<area>/test_<module>.py` |
| Bootstrap assumption | founder=id=1 | (your bootstrap if any) |

Other P0 candidates trong tracker:
- `admin-commands` (Phase 6)
- `pricing-tiers` enforcement (Phase 3) — touches money, need careful
- `W6.3 backup-b2` — touches data persistence, P0
- `messenger-channel` if scope includes auth flow
- Future: multi-tenant data migration (post-Wave 1)

---

## 8. Checklist — copy-paste cho P0 PR body

```markdown
## What
[1 sentence — what this PR ships]

## Why
[1-2 sentences — motivation, link to spec]

## How
[bullet list — key implementation choices]

## Tests
- [ ] X unit tests (categories: bootstrap, DB, decorator, edge)
- [ ] Y integration tests (TENANT ISOLATION MANDATORY)
- [ ] All required CI green

## Acceptance criteria
[mirror Linear ticket AC with checkboxes]

## Risk + blast radius
- [ ] New module / existing code touched: ...
- [ ] Migration involved: yes/no, reversible: yes/no
- [ ] Known tradeoffs documented in spec: ...
- [ ] Failure modes considered: ...

## Cross-model review status
- Codex review requested: ...
- Round count: ...

Closes MMW-NNN
```

---

## 9. Checklist — founder sign-off comment

```markdown
Foundation Lane founder approval:

AC: [met / which deferred + why]
Cross-model review: [N rounds, all addressed]
Blast radius: [scope + breaking change check]
Known tradeoffs: [list]
Migration reversibility: [tested / N/A]
Test coverage: [5-category, tenant isolation MANDATORY met]

Ready to squash-merge.
```

---

## 10. References

- **Sister walk-through (Standard Lane)** — [`linear-and-dashboard-workflow.md`](linear-and-dashboard-workflow.md) §7
- **Engine spec** — [`dashboard-plan-state-split.md`](dashboard-plan-state-split.md)
- **3-lane risk-based workflow** — `fast-quality-workflow.md`
- **10-step per-feature workflow** — `development-workflow.md`
- **Hard rules** — `CLAUDE.md` "Hard rules — read every session"
- **Wave 0 lessons** — memory `feedback_wave0_lessons.md`
- **F07 saga lessons** — memory `feedback_f07_lessons.md`
- **Autopilot risk tier policy** — memory `project_autopilot_risk_tier_policy.md`

---

## Changelog

| Version | Date | Author | Notes |
|---------|------|--------|-------|
| v1.0.0 | 2026-05-19 | Founder + Claude | Initial reference walk-through. Uses admin-auth (MMW-202, P0, Foundation Lane) as concrete vehicle. Complements §7 of linear-and-dashboard-workflow.md (which uses funding-sources P1/Standard). |
