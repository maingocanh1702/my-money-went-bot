# Deep Code & Security Review — MyMoneyWent
Date: 2026-05-14
Reviewer: code-reviewer (Staff Engineer, production-readiness pass)
Scope: full repo (~82 Python files, 15K LOC). Complements `plans/reports/security-scan-20260514.md` (which covered secrets, dep CVEs, basic injection). Goes deeper into tenant isolation, webhook semantics, race conditions, supply chain.

## Executive summary

| Severity | Count | Theme |
|----------|------:|-------|
| CRITICAL | 4 | Multi-tenant wiring is dormant; prod traffic still routes through single-tenant legacy. Email webhook trusts unauthenticated `from` claims. |
| HIGH     | 7 | Plan-tier enforcement absent; `assert` used as input gate; legacy global `CHAT_ID` mutates shared sheet state across users; CI pre-commit pin drift on `jinja2`/`black`; over-scoped Drive permission; SePay 10-min replay window is real. |
| MEDIUM   | 9 | Idempotency only covers `ref_code` collisions, not concurrent first-writes; structlog `processors.dict_tracebacks` not enabled (Sentry may leak local vars); analytics `emit_*` swallows all; sheet-cache global is process-global not tenant-scoped; mutable global `_buckets_cache` in `sheets.py`; legacy paths still imported by `main.py`; etc. |
| LOW      | 5 | Mostly style / future-debt: 600+ LOC files, `print(...)` instead of structured log on hot path, etc. |

**The single most important finding**: the new multi-tenant capture pipeline (`markets/vn/capture/sepay_webhook.py`, `webhook_tokens`, `tenant_context`, asyncpg pool, settings_svc) is fully written and tested but **never wired**. `main.py` does not call `db.create_pool`, does not register `request_id_middleware`, does not call `init_sentry`, does not mount the per-user `/webhooks/sepay/{token}` route, and routes BOTH the SePay native webhook AND the Postmark/email-forwarded payload to the legacy `handlers.sepay.handle_sepay_webhook` — which writes to a single Google Sheet keyed by a global `CHAT_ID` from env. If a second user signs up today, their transactions land in user #1's sheet. This is the cross-tenant leak the architecture was built to prevent — the wiring just never happened.

The prior `security-scan` findings (jinja2 CVEs, fail-open webhook secrets, GCP key on disk) remain valid; this review does not re-list them.

---

## Findings

### CRITICAL

#### C1. Multi-tenant pipeline is not wired — prod traffic falls back to single-tenant legacy
**Files:** `main.py:21,49-61,174`, `markets/vn/capture/sepay_webhook.py:144`, `core/db.py`, `core/observability.py:95`
**Risk:** Cross-tenant data leak. Every webhook + every Telegram message currently writes to a single Google Sheet keyed by global `config.CHAT_ID`. Second user onboarding → their bank txns + categorization state collide with user #1's. F01 `/start` creates a fresh row in Postgres `users` and mints a webhook token, but no inbound traffic touches that table.
**Evidence:**
- `main.py:21` imports `from handlers.sepay import handle_sepay_webhook` — the **legacy** module, not `markets.vn.capture.sepay_webhook`.
- `main.py:174` and `main.py:97` dispatch ALL SePay + email payloads to that legacy handler, which uses global `CHAT_ID` via `sheets.py`.
- No route `/webhooks/sepay/{token}` is registered anywhere (`grep "@app.post"` confirms only `/webhook`, `/webhook/email`, `/trigger/*`, `/dashboard`, `/`).
- `main.py` does NOT call `core.db.create_pool(...)` at startup → if anything in the new path *did* run, it would crash with `asyncpg pool not initialised`.
- `main.py` does NOT call `core.observability.init_sentry(...)` or register `request_id_middleware`.
- `core/handlers/start.py` IS wired (`main.py:217`) so users *can* `/start` and get a Postgres row + token, but nothing downstream consumes it.
**Fix (urgent):**
1. Wire the new pipeline at startup:
   ```python
   @app.on_event("startup")
   async def on_startup():
       from core.db import create_pool
       from core.observability import init_sentry
       from core.logging import configure_logging
       configure_logging()
       init_sentry(os.environ.get("SENTRY_DSN"))
       await create_pool(os.environ["DATABASE_URL"])
       ...
   app.middleware("http")(request_id_middleware)
   ```
2. Mount the per-tenant SePay route:
   ```python
   from markets.vn.capture.sepay_webhook import handle_sepay_webhook as handle_sepay_v2
   @app.post("/webhooks/sepay/{token}")
   async def sepay_v2(token: str, request: Request):
       body = await request.json()
       return await handle_sepay_v2(token, body)
   ```
3. Delete or hard-disable the legacy `/webhook` SePay path *before* onboarding user #2. Even one extra tenant on the legacy path corrupts user #1's history.
4. Same for `/webhook/email` — route email payloads to a per-user inbound-token handler that resolves `u<id>@in.mymoneywent.com` to a `user_id` via the same `webhook_tokens` (kind=`email_inbound`) lookup. Currently `handlers/email_parser.py:34` accepts ANY `from_addr` claim and routes by sender domain only.

#### C2. Email webhook trusts forwarded `from` field — no SPF / DKIM / signature verification
**Files:** `main.py:71-82`, `handlers/email_parser.py:34-60`
**Risk:** Anyone who can POST to `/webhook/email` (and knows `EMAIL_SECRET` — see prior scan finding #3 about fail-open) can inject arbitrary "bank notification" emails. The parser routes by `from_addr` substring — claim `from = "automail@techcombank.com.vn"` and the system creates a fake transaction.
**Evidence:** `handlers/email_parser.py:40` — `sender = _extract_email_addr(from_addr).lower()` then `BANK_SENDERS.get(sender)`. No DKIM / SPF / Authentication-Results header check. The payload only has `{ secret, from, subject, body, date }` (per `main.py:69` docstring) — no auth metadata is even passed.
**Risk amplification:** Once C1 is fixed and routing is per-tenant via the `u<id>@in.mymoneywent.com` scheme, this becomes a single-tenant injection (attacker can only forge transactions into their own ledger). But until then, anyone who learns `EMAIL_SECRET` can pollute user #1's data forever.
**Fix:** Require the Postmark inbound webhook (not Google Apps Script) and verify Postmark's HMAC-signed delivery, OR forward the raw email envelope (including DKIM-Signature + Authentication-Results headers) and reject when `Authentication-Results` does not show `dkim=pass` and a domain matching the claimed `from`. Strip `BANK_SENDERS` substring matching → require exact-match registered sender plus DKIM result.

#### C3. Legacy `handlers/sepay.py` fail-open secret check + global single-tenant state
**Files:** `handlers/sepay.py:121-133`, `sheets.py:21-26`
**Risk:** Two issues compound. (a) `SEPAY_SECRET` check is skipped when env var is empty (covered in prior scan as HIGH). (b) When it does run, it writes to a process-global `_buckets_cache` (`sheets.py:21`) shared across all requests, and uses `bootstrap_lock` (`sheets.py:26`) for serializing — but the cache key is `month_key`, not `(user_id, month_key)`. With C1's single-tenant assumption broken (any multi-tenant deploy), one user's bucket list overwrites another's in memory until the process restarts.
**Evidence:** `sheets.py:21` `_buckets_cache: dict = {}` keyed only by `month_key`. `sheets.py:124-142` `get_active_buckets(month_key)` consults the cache without any tenant scoping. `handlers/sepay.py:101-118` `_ensure_buckets` calls it.
**Fix:** Subsumed by C1 — delete `sheets.py` along with the legacy path. If for any reason the legacy path must stay, add a `tenant_id` dimension to the cache and `bootstrap_lock` keying.

#### C4. Idempotency on legacy SePay fallback collides across users
**File:** `handlers/sepay.py:165-175`
**Risk:** When `referenceCode` is missing, the fallback ref_code is `md5(f"{raw_amount}|{description}|{raw_date}")` — global, not tenant-scoped. Two users receiving the same-amount same-description payment at the same second would have the second write silently swallowed by `sh.tx_exists(ref_code)`. The new path in `markets/vn/capture/sepay_webhook.py:81-94` correctly scopes by `user_id` in the hash key — the legacy one doesn't.
**Fix:** Subsumed by C1.

---

### HIGH

#### H1. Plan-tier limits are not enforced anywhere
**Files:** entire codebase (negative finding). Spec mentions Free=45 tx/mo, Pro=3 banks, Biz=5 banks, but no enforcement code exists.
**Risk:** Revenue leakage on launch — every user gets unlimited usage regardless of plan. Also, when limits *are* added later, naive `count(*) FROM transactions WHERE user_id=$1 AND month_key=$2` + insert is a classic TOCTOU: 10 concurrent webhook deliveries when user is at 44/45 all read 44, all insert, user ends at 54.
**Fix:** Enforce at insert time using a row-count atomic check in a single statement, e.g. CTE + conditional INSERT:
```sql
WITH cnt AS (
  SELECT COUNT(*) AS n FROM transactions
  WHERE user_id = $1 AND month_key = $2
)
INSERT INTO transactions (...)
SELECT ...
FROM cnt
WHERE cnt.n < (SELECT tx_cap FROM plans WHERE plan = (SELECT plan FROM users WHERE id = $1));
```
Add a `monthly_tx_count` column with a trigger or compute via partial index. For bank-count caps, enforce via a CHECK constraint on `funding_sources` or a row-level insert trigger.

#### H2. `assert` used for input validation in handler code (`-O` strips it)
**Files:** `handlers/allocation.py:137,173`, `handlers/manage.py:168,381`, `core/services/user_svc.py:195`
**Risk:** `python -O` (Python optimized mode) elides all `assert` statements. Running the bot with `python -O main.py` (which is a reasonable prod toggle) silently disables these guards. `user_svc.py:195` `assert row is not None` is a coverage-only check, but the four `assert amount > 0` / `assert amount >= 0` in allocation/manage are user-input gates — under `-O` an empty-string amount → `int("")` raises `ValueError`, but `int("0".join(...))` from non-digit input could land at 0 or worse.
**Fix:** Replace each `assert <cond>` with `if not <cond>: raise <Specific>Error(...)`. The `try/except Exception` around them in allocation/manage means the failure path already works, but explicit raises read clearer and survive `-O`.

#### H3. Webhook secret comparison non-constant-time + accepts multiple field names
**File:** `handlers/sepay.py:125-131`
```python
incoming_secret = (
    payload.get("apikey")
    or payload.get("token")
    or payload.get("secret")
    or (payload.get("data") or {}).get("apikey")
)
if incoming_secret != SEPAY_SECRET:
```
**Risk:** (a) `!=` is non-constant-time (prior scan called this out — it's still here). (b) Accepting four different field names broadens the attack surface and makes the contract ambiguous — SePay docs specify exactly one. Allowing `data.apikey` ALSO means a malicious caller can put their secret guess in a nested dict, which differs from how `SEPAY_SECRET` was documented to be checked.
**Fix:** Pick one field per SePay docs (`apikey`). Use `hmac.compare_digest`. Reject explicit None/empty before compare.

#### H4. SePay 10-minute "stale tx" replay window is exploitable
**File:** `handlers/sepay.py:189-198`
**Risk:** The current guard rejects txns >10 min old (or >24h for email). An attacker who captures one real webhook payload can replay it within 10 minutes from a different IP — `ref_code` dedupe (`sh.tx_exists`) would catch *exact* duplicates, but if any field differs (e.g. they bump the description by one char), the dedupe miss + idempotency hash regen creates a new row. Also, the time-based check is on `tx_date` (from payload, attacker-controlled), not on a server-stamped receipt time — attacker can just set `transactionDate=<now>`.
**Fix:** Use server receipt time AND `payload.tx_date` together; reject if `|server_now - tx_date| > 10min` for SePay (covers both directions). Move from string-substring dedupe (`find_recent_duplicate`) to (user_id, ref_code) UNIQUE check enforced by DB — which the new path already does.

#### H5. CI pre-commit hook versions disagree with `requirements.txt` and `[dev]` pins
**Files:** `pyproject.toml:25-30`, `.pre-commit-config.yaml` (per snippet seen), `requirements.txt:11-15`
**Risk:** `requirements.txt` still pins `jinja2==3.1.4` (3 HIGH CVEs per prior scan), `black==24.4.2` (LOW CVE), `ruff==0.4.10` (year-old). pre-commit pins `black 24.4.2` so CI never surfaces the bump. The next dependabot SHA refresh will conflict with these pins. No `pip-audit` step in `.github/workflows/ci.yml`.
**Fix:** (a) bump `jinja2 → 3.1.6`, `black → 26.3.1`, `ruff → latest 0.6.x`; align pre-commit `rev:` to match. (b) add `pip-audit` step to `ci.yml`: `pip install pip-audit && pip-audit --strict -r requirements.txt`. (c) add `.github/dependabot.yml` for `pip` and `github-actions` ecosystems (`dashboard.yml` uses unpinned `actions/checkout@v5` / `setup-python@v6` — prior scan didn't catch this because pin-by-SHA is only done in `ci.yml`).

#### H6. GH Action versions inconsistently pinned (supply chain)
**Files:** `.github/workflows/ci.yml:14-18` (good — SHA-pinned), `.github/workflows/dashboard.yml:27,46`, `.github/workflows/sync-tracker.yml:35,40`, `.github/workflows/linear-status-sync.yml:17,18,21`, `.github/workflows/pr-validate.yml` (no actions used)
**Risk:** `ci.yml` is hardened with full-SHA pins. The other four workflows use floating tags (`actions/checkout@v5`, `actions/setup-python@v6`, `actions/checkout@v4`). A compromised tag (cf. tj-actions/changed-files incident, 2025) on any of these workflows would let an attacker exfiltrate `GITHUB_TOKEN` and the `LINEAR_API_KEY` secret in `linear-status-sync.yml:113`.
**Evidence:** `dashboard.yml:27` `uses: actions/checkout@v5` (with `token: ${{ secrets.GITHUB_TOKEN }}` and `permissions: contents: write` — it can push to main). `linear-status-sync.yml:113` exposes `LINEAR_API_KEY` to a `python .github/scripts/linear-sync.py` invocation; if `actions/checkout@v4` were compromised the script execution context already has the secret in env.
**Fix:** SHA-pin all four workflows the same way `ci.yml` does. Add `permissions:` blocks (default to `read-all`, opt-in to `contents:write` only on the step that needs it). Consider OIDC for Linear if Linear supports it.

#### H7. Over-scoped Google API permission
**File:** `sheets.py:14-17`
```python
SCOPES = [
  "https://www.googleapis.com/auth/spreadsheets",
  "https://www.googleapis.com/auth/drive",
]
```
**Risk:** `auth/drive` grants full read+write+delete to ALL Drive files visible to the service account, not just the one sheet. If the service-account key leaks (cf. prior scan finding #1 — key is on disk), the blast radius is everything the SA has been shared into. The bot only needs `auth/spreadsheets` plus optionally `auth/drive.file` (per-file).
**Fix:** Drop `auth/drive`; switch to `auth/spreadsheets` only (gspread's `open_by_key` works with just spreadsheets scope when the SA already has access to the file). Verify by running locally first.

---

### MEDIUM

#### M1. `_persist` in new SePay path has no retry / no transaction wrapper
**File:** `markets/vn/capture/sepay_webhook.py:97-141`
**Risk:** A single `conn.execute(INSERT ... ON CONFLICT DO NOTHING)` with no transaction is fine for the single-statement case, but the surrounding `handle_sepay_webhook` does (resolve_token → parse → persist → log). If `_persist` fails transiently (asyncpg disconnect), the webhook returns 200 OK silently — SePay won't retry, transaction is lost. The "fail silently" docstring at L150 is correct for *attacker probing* but masks real errors too.
**Fix:** Wrap parse+persist in a try/except that re-raises only specific transient errors so SePay retries (or, since we already return 200, log to Sentry with severity=error rather than silently returning).

#### M2. `_content_hash_ref_code` collision risk acknowledged but not mitigated
**File:** `markets/vn/capture/sepay_webhook.py:81-94`
**Risk:** Self-acknowledged in docstring — "two distinct events sharing user+date+amount+direction+bank+last4 in the same second WILL collide." Cake credit card has format-2 emails that emit second-resolution `tx_date`. Two ride-share charges at 12:34:00 of the same amount = one row lost. The probability is low but the failure mode is silent (DO NOTHING).
**Fix:** Include `description[:40]` in the hash key, or fall back to inserting with a synthetic `ref_code = f"nokey-{uuid.uuid4()}"` so the dedupe is "best effort but never silently merge". The current behavior trades data correctness for dedupe — probably wrong for a finance app.

#### M3. `tenant_context.set_tenant` not called by every handler that touches DB
**Files:** `handlers/settings.py` (whole file), `core/handlers/start.py`, `core/services/user_svc.py`
**Risk:** `core/tenant_context.py:18` declares as a hard invariant: "Every query that reads/writes tenant-scoped tables MUST filter by `user_id = get_user_id()`." But in practice the handlers pass `user_id` explicitly down through every service call — `tenant_context` is only used for log/Sentry binding. That's defensible (explicit args > magic ContextVar) but the doc lies: nobody calls `get_user_id()` in business logic, only `set_tenant` in webhooks. The contract should match the implementation: either drop the "hard invariant" wording, or add a runtime assertion in `db.py` that the bound `user_id` equals the `$1` in queries (impractical) — or accept that explicit args are the actual contract and rewrite the docstring.
**Fix:** Update `core/tenant_context.py:16-22` docstring to describe its actual role: "log/Sentry correlation context, not a query-layer enforcement mechanism." This matters because future developers reading the comment will assume `tenant_context` is the safety net and skip per-query review.

#### M4. `core/services/user_svc.create_or_get_user` race window on chat_id self-heal
**File:** `core/services/user_svc.py:165-181`
**Risk:** Concurrent `/start` from two contexts (e.g. user blocks bot, unblocks, hits /start twice fast) — both calls hit the `ON CONFLICT DO NOTHING`, both go into the `inserted is None` branch, both find the existing row with `chat_id IS NULL`, both UPDATE. Last-write-wins, but the analytics event will mis-attribute `created=False` twice when the user perceives it as one onboarding. Low impact, but the race is real.
**Fix:** Add `RETURNING xmin` or move chat_id backfill into the ON CONFLICT branch:
```sql
INSERT INTO users (...)
VALUES (...)
ON CONFLICT (channel_type, channel_user_id) DO UPDATE
  SET chat_id = COALESCE(users.chat_id, EXCLUDED.chat_id),
      updated_at = NOW()
RETURNING id, (xmax = 0) AS inserted;
```

#### M5. `seed_default_categories` runs N inserts in a loop — N+1 pattern
**File:** `core/services/user_svc.py:209-227`
**Risk:** Only 3 categories today, so impact is trivial. But the pattern (`for cat in DEFAULT_CATEGORIES: conn.execute(INSERT)`) is the wrong template — when `DEFAULT_CATEGORIES` grows or this gets reused for monthly category roll-forward, it becomes a per-user-per-month N+1.
**Fix:** Build a `executemany` or single `INSERT ... VALUES ($1,...),($2,...),...` from the list. Cheap and future-proofs the template.

#### M6. `emit_analytics` swallows ALL exceptions — masks real DB issues
**File:** `core/settings_svc.py:290-321`
**Risk:** `except Exception as exc:` and downgrade to `warning` means a hot loop where every `emit_analytics` call fails (e.g. analytics_events table dropped, FK violation, JSON encoding bug) is invisible at the page level. Sentry will surface the warning but Sentry's warning channel is noisy.
**Fix:** Rate-limit the log to once per minute per error type, OR re-raise `asyncpg.PostgresError` while still swallowing JSON encoding errors.

#### M7. Sentry `before_send` adds `user.id` but never scrubs `request.data`
**File:** `core/observability.py:47-56`
**Risk:** `send_default_pii=False` in `init_sentry` (L84) helps, but transaction descriptions, amounts, bank account last4 all flow through structlog at `info` level — those get attached to Sentry breadcrumbs by the structlog→sentry integration if anyone wires `sentry_sdk.integrations.logging.LoggingIntegration` (not currently wired, but will be when someone reads the Sentry docs). The `before_send` hook does not redact event_dict fields.
**Fix:** Add a redaction processor to `core/logging.py` BEFORE the JSON renderer: scrub `account_number`, `last4`, `description` (or hash them), and `amount` (round to nearest 10k). Then the structlog→Sentry pipeline can't leak.

#### M8. `i18n.t` missing-key fallback emits `[MISSING: key]` into user-facing text
**File:** `core/services/user_svc.py:204-207` (docstring), `core/handlers/start.py:165-173` (welcome msg uses `text_key`)
**Risk:** If F-i18n misses a key for the welcome message in EN, the user sees `[MISSING: onboard.welcome_new]` — bad UX, also informs an attacker which keys exist. Not a security finding, but on a fresh deploy where translations lag, it's a leaky default.
**Fix:** Fall back to `vi` for missing keys before showing `[MISSING:]`. Log the miss to structlog.warning. Never render the literal `[MISSING:]` token to end-users.

#### M9. Webhook tokens never expire
**File:** `markets/vn/capture/webhook_tokens.py`, `migrations/versions/0001_initial_schema.py:180-191`
**Risk:** Tokens have `created_at` and `revoked_at` but no `expires_at`. Once minted, valid forever unless user regenerates. SePay's webhook URL is shared with SePay's infra — if leaked from SePay logs (not under our control), the token grants permanent write access to that user's ledger.
**Fix:** Add `expires_at` column; default 1 year; on `mint_token` set new value; `resolve_token` adds `AND (expires_at IS NULL OR expires_at > NOW())` to the WHERE clause. Surface days-left in `/settings`. Schedule auto-rotation reminders.

---

### LOW

#### L1. Files over 200 LOC contrary to local CLAUDE.md rule
- `sheets.py` 661 (deprecated, but still loaded), `core/settings_svc.py` 338, `handlers/manage.py` 425, `handlers/reports.py` 429, `handlers/settings.py` 355, `tools/autopilot/loop.py` 676, `tools/autopilot/claude_codegen.py` 506, `tools/autopilot/codex.py` 386. Acceptable for the autopilot tooling (orchestrator); legacy `sheets.py`/`handlers/*` should die per their own ⚠️ DEPRECATED banners.

#### L2. `print(...)` instead of structured log on hot paths
`handlers/sepay.py:132,138,147,158,174,197,205`, `handlers/email_parser.py:46,81,98,196,213`, `main.py:78,94,99,177,226,235`. structlog is configured but only the new `core/markets` code uses it. Logs to stdout (Railway captures) but lose tenant binding + JSON structure.

#### L3. `httpx.AsyncClient` created at import time without close
`telegram_api.py:9` `_client = httpx.AsyncClient(timeout=10)` — global, never closed. Fine for a long-lived FastAPI process but leaks in test isolation (each pytest run starts a new event loop and inherits this client → "event loop closed" errors).
**Fix:** Use FastAPI lifespan; create in startup, close in shutdown.

#### L4. `_extract_email_addr` regex permits header injection
`handlers/email_parser.py:316-319`. If `from_addr` is `"Name\r\nBcc: attacker@..." <real@bank.com>`, `_extract_email_addr` returns `real@bank.com` correctly (only matches `<...>`) — so this is safe by accident. Worth a test to lock it in. Hypothetical, marked LOW.

#### L5. `tools/autopilot/git_ops.py:100` uses `--no-verify` on auto-commit fallback
Bypasses pre-commit secret detection. Self-documented as acceptable; orchestrator runs only on founder's machine in known repo. Worth flagging if autopilot ever runs in CI.

---

## Cross-cutting observations

1. **The legacy/new split is a transitional hazard.** Every legacy file carries a `⚠️ DEPRECATED — DO NOT add new features here` banner, but `main.py` still imports and dispatches to all of them. The kill-switch (Phase 2 F02 cutover) has not happened, and based on tests passing + dashboard rebuilds, the team thinks they're already multi-tenant. The gap between intent and wiring is the source of C1-C4. **Priority**: complete F02 cutover this week or kill the legacy `/webhook` route entirely.
2. **`docs/`-driven development is great for intent but cannot enforce wiring.** The architecture docs (`docs/tdd-vi.md`, F-feature plans) read like the new pipeline is live. CI passes (because the legacy code paths aren't tested by the new test suite, and the new tests pass against the test pool). Consider an integration smoke test: spin up `main:app` with TestClient, send a `POST /webhooks/sepay/{minted_token}`, assert the row lands in Postgres scoped to the right user. Right now that test cannot exist because the route does not exist.
3. **Idempotency is layered but not principled.** Three different fallback strategies for `ref_code` (new path), an md5 of "amount|desc|date" (legacy path), and a `find_recent_duplicate` fuzzy match (legacy `handlers/sepay.py:204`). Each has different collision behavior. Standardize on a single (user_id, source_id) idempotency key in the schema.
4. **`tenant_context` is only used for logs/Sentry, not query enforcement.** That's a defensible design (explicit `user_id` args are clearer) but the docstring should match. Future devs may rely on the bound context for safety and skip the explicit parameter.
5. **No rate limiting anywhere.** `i18n.error.rate_limit` strings exist but no code emits them. SePay webhook endpoint, Telegram callback handler, `/start` are all unbounded. A single attacker can pin the bot's DB connections by spamming `/start` with random `channel_user_id`s, creating unbounded user rows.
6. **No CI dep-audit step.** Easy to add — `pip-audit` already exists in the security report's recommendations. Adding it to `ci.yml` would have caught the jinja2 CVEs at PR time.

---

## What looks good

- **`markets/vn/capture/webhook_tokens.py` is well-designed.** SHA-256 storage, `hmac.compare_digest` even on the hashed value, `display_suffix` for UX without leaking entropy, `ON CONFLICT (user_id, kind) DO UPDATE` for atomic regen. Token lifecycle is the one part of the new path that's airtight.
- **`core/tenant_context.py` ContextVar implementation is correct** for asyncio (vs. threading.local). `set_tenant` validates `user_id > 0`. `get_user_id` raises rather than defaulting (fail-loud). Pattern is right; just unused in business logic (M3).
- **`migrations/versions/` are reversible** (except 0003 which documents the irreversibility). Constraints are well-chosen: `UNIQUE(user_id, ref_code)` on `transactions`, `UNIQUE(user_id, slug, month_key)` on `categories`, `UNIQUE(user_id, kind, bank, last4)` on `funding_sources`. The DB enforces tenant scoping where it can.
- **`core/db.py` pool lifecycle is correct.** Idempotent `create_pool`, sane defaults (`min_size=2`, `max_size=10`, `command_timeout=30s`), explicit `get_pool` raises rather than auto-creating.
- **`ci.yml` is SHA-pinned** with security-hardening rationale in comments. The pattern just needs propagating to the other three workflows (H6).
- **`request_id_middleware` correctly uses Token-based reset** to avoid ContextVar leakage across requests (`core/observability.py:107-115`).
- **Spec-driven autopilot is impressively rigorous.** `tools/autopilot/codex.py` keyword-regex categorization, circuit breaker, parser-uncertain halt, stale-blob detection — a lot of paranoia baked in. (Risk only if it ever runs outside the founder's machine — see L5.)

---

## Recommended actions (prioritized)

1. **Today.** Wire C1: register `/webhooks/sepay/{token}` route, call `create_pool` + `init_sentry` at startup, install `request_id_middleware`. Smoke-test with a freshly-minted token via TestClient. Keep `/webhook` alive only as a Telegram-update receiver; remove SePay branch (`main.py:174`).
2. **This week.** Address C2: harden email webhook (require DKIM-pass header or switch to Postmark HMAC). Disable email webhook if not yet rewired to per-user inbound tokens.
3. **This week.** Address H1 (plan-tier enforcement) — even a minimal `monthly_tx_count` column + insert-time check is enough to prevent revenue leakage on launch.
4. **Pre-launch.** Fix H2 (assert→raise), H3 (hmac.compare_digest), H5 (jinja2 bump + pip-audit in CI), H6 (SHA-pin workflows), H7 (drop drive scope).
5. **Soon.** Medium findings as part of normal cleanup; consider M9 (token expiry) before paid plan launch.
6. **Eventually.** Kill legacy `handlers/`, `sheets.py`, `telegram_api.py`, `config.CHAT_ID`. The deprecation banners have been there long enough to land Phase 2 F02.

---

## Unresolved questions

- Is there an alternate startup path (e.g. `uvicorn` arg or a `core/__main__.py`) that wires the new pipeline, and `main.py` is dead code? `setup.sh:33` `ExecStart=$BOT_DIR/venv/bin/uvicorn main:app` says no — `main:app` is the entrypoint and `main.py` is what runs. But worth confirming `railway.toml`'s start command before sounding the C1 alarm publicly.
- Postmark webhook integration — the prompt mentions Postmark inbound, but the only email-receive code is `main.py:65 /webhook/email` accepting a Google Apps Script payload with custom `{secret, from, ...}` shape. Has Postmark replaced GAS yet, or is it a future plan? The DKIM/SPF discussion (C2) assumes the GAS bridge is current; if Postmark is live, Postmark's signed delivery solves part of C2.
- Has user #2 ever signed up? If yes, their data is already mixed into user #1's Google Sheet (per C1). Recovery would need a tx-history audit by `bankAccount` ticker.
- Does `tools/autopilot/` ever run in CI / with elevated GitHub permissions, or only on the founder's laptop? L5 / H6 severity hinges on that.

---

**Status:** DONE_WITH_CONCERNS
**Summary:** Deep review complete; report at `plans/reports/code-review-260514-full-codebase-deep.md`. Concerns: 4 CRITICAL findings are blocking — most importantly C1 (multi-tenant pipeline is fully built but not wired into `main.py`; legacy single-tenant code still handles all prod webhook traffic). C2-C4 follow from C1. Recommend fixing wiring + email auth + plan-tier enforcement before adding a second user.
