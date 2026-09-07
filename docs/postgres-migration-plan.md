# My Money Went Bot — PostgreSQL plan (revised)

**Repo:** `maingocanh1702/my-money-went-bot` · **Revised:** 2026-09-06
**Supersedes:** the first PostgreSQL migration plan.

The original plan was sound in the abstract but misread the repo in four
places, contained two design decisions that would lose data, and skipped the
decision that actually governs the work. This version fixes those, and splits
out a phase that is worth doing **whether or not the migration ever happens**.

---

## 0. The decision to settle first

The README's headline promise, as of 2026-09-06, is:

> No database. No third-party data store. Single-tenant — one bot per person.
> Your Google Sheet IS the entire backend.

A PostgreSQL Source of Truth breaks that promise for everyone who clones this
repo: another paid service to run, `DATABASE_URL` + TLS cert + `alembic upgrade`
on top of the current 8 environment variables, and the user no longer owns the
whole record in a file they control.

Scale argues the same way. This is a single-tenant bot; SePay's free tier is 50
transactions/month and real usage is roughly 90–100/month, ~900/year. Shadow
writes, an outbox worker, a reconciliation tool and a cutover gate are the
architecture for thousands of transactions per day.

**Decision taken here:** PostgreSQL is an **optional backend**, never a
requirement.

```env
STORAGE_BACKEND=sheets     # the default, permanently, for the public repo
STORAGE_BACKEND=postgres   # opt-in, for an operator who wants it
```

Consequences that bind the rest of this document:

- The Sheets path stays a first-class, fully supported backend forever. It is
  not a legacy path awaiting removal.
- No PR may make PostgreSQL necessary to run the bot, or necessary to pass CI.
- The README keeps its promise unchanged. If PostgreSQL is ever made the
  default, that is a separate, explicit product decision with its own
  positioning rewrite — not a side effect of this migration.

---

## 1. What the repo actually has today

Verified against the working tree, not assumed.

**Already built, and better than the original plan credited:**

- `sheets.tx_exists()` is a **claim-based exact-idempotency protocol**, not a
  naive lookup: a durable `Processed Refs` tab, an in-process cache with a
  5-minute claim TTL, a lock that also guards `append_transaction`, and
  fail-closed behaviour — a claim-store failure raises a retryable error rather
  than acknowledging. It also resolves the ambiguous case where the row commits
  but the marker update times out.
- `handlers/sepay.py:_append_claimed_transaction()` settles the claim
  (`mark_ref_committed` / `mark_ref_failed`) around the write.
- `main.py:138` returns **503** on a retryable claim failure. *"Only ACK after
  durable persistence succeeds"* — §10 of the original plan — is already the
  implemented policy, just against Sheets.
- `storage/postgres_connection.py` — 334 lines, 20 tests, TLS-hardened, and
  imported by no runtime module. Correct to keep and stop polishing.

**Genuinely missing or wrong:**

| Where | What |
|---|---|
| `handlers/sepay.py:175` | `ref_code = referenceCode or md5(amount\|description\|date)[:16]`. SePay's own `id` is never read. |
| `handlers/sepay.py:203` | Stale-age guard `return`s silently — the event leaves no trace. |
| `handlers/sepay.py:210` | Fuzzy cross-source dedup `return`s silently — same problem. |
| `google_apps_script.js:185` | Payload is `{secret, from, subject, body, date}`. `msg.getId()` exists at line 110 but is used only for the script's own dedup and **never sent to the bot**. |
| everywhere | No `Decimal`. Money is float end-to-end; `cashback_engine._vnd()` is `int(round(float(n)))`. |
| `requirements-dev.txt` | SQLAlchemy 2.0.52 + psycopg[binary] 3.3.5, dev-only. No alembic anywhere. No `models.py`, `session.py`, `repositories/`. |

**History worth knowing:** this exact slicing has been attempted and closed
before. `.autopilot/dispositions/postgres-sot-foundation.json` describes
"alembic + storage/models.py + full migration in one slice" → `authorized_close`,
superseded. `postgres-sot-core-r2` → stale halted. `postgres-sot-tls-core-r24` →
MAX_ROUNDS. Only `postgres-sot-direct-creator-r25` (the connection boundary)
reached main. Phase 0 below exists partly so that the next attempt starts from
a smaller, already-correct base.

---

## 2. Phase 0 — fixes that stand alone

**These are the highest-value work in this document.** Each is independently
useful, ships against Sheets, needs no database, and turns the original plan's
PR 4 from a redesign into a mechanical port.

### PR 0a — use SePay's real event id

SePay's webhook carries `id`, its own unique transaction identifier; SePay's
integration guide names that field as the one to deduplicate on. `referenceCode`
is an external bank reference with no uniqueness guarantee, and the current MD5
fallback is worse than it looks:

> Two **different** transactions with the same amount, same description and the
> same timestamp produce the same `ref_code`, so `tx_exists()` swallows the
> second one. This is a live data-loss bug, not a hypothetical.

Change `ref_code` derivation to, in order: `sepay:<id>` → `sepay:ref:<referenceCode>`
→ (only if both are absent) today's hash, logged as a degraded case. Keep the
existing claim protocol untouched; only the identity changes.

Tests: two transactions identical in amount/description/timestamp but with
different `id` must both be written. One `id` delivered ten times must write one
row.

### PR 0b — record dropped events instead of discarding them

Both silent `return`s become a written row plus a flag, so nothing disappears:

- fuzzy cross-source match → write the row with `possible_duplicate = TRUE`,
  and tell the user, rather than deleting a possibly-real transaction;
- past the stale-age window → write the row flagged `delayed`.

Age must stop being replay protection; the claim ledger already is. Keep the
age window only to suppress the first-setup history replay, and make that
explicit — a one-off bootstrap concern, not a correctness mechanism.

Closes audit items F-03 and F-04.

### PR 0c — send the Gmail message id

`google_apps_script.js` adds `messageId: msg.getId()` to the POST body;
`/webhook/email` reads it; the email path derives `email:<messageId>` as its
event id instead of the content hash.

Two things the original plan omitted:

1. **Every existing operator must re-paste the script** into their Apps Script
   project. Ship a short "updating the forwarder" section in the wiki with this
   PR, and make the bot tolerate a missing `messageId` (fall back to today's
   behaviour) so nobody's bot breaks the moment this merges.
2. `google_apps_script.js` is in `EXPECTED_DIVERGENCE` in `scripts/check_parity.sh`
   — change it in both repos in the same pass.

### PR 0d — exact money arithmetic

`Decimal` from parse to write: `sheets._parse_amount`, the cashback engine, and
the report aggregations. Putting `NUMERIC(20,2)` in a database while Python
still computes in float only moves the rounding error. Closes F-06.

**Phase 0 gate:** all four merged, Sheets still the only backend, CI green. At
this point the bot has stable per-event identity, loses nothing silently, and
does exact money arithmetic — most of the correctness value the original plan
promised, at a fraction of the cost.

---

## 3. Phase 1 — optional PostgreSQL backend

Only start this if Phase 0 is done and you still want it.

### PR 1 — foundation

`storage/models.py`, `storage/session.py`, `storage/repositories/`, `alembic.ini`,
`alembic/versions/001_initial_schema.py`. Promote SQLAlchemy, psycopg and add
alembic to runtime **as extras**, not as hard dependencies: the bot must still
start and pass its whole test suite with `STORAGE_BACKEND=sheets` and no
database driver installed.

Acceptance: a Sheets-only deployment is byte-for-byte unaffected; `alembic
upgrade head` builds an empty database; CI runs both the Sheets suite and an
ephemeral-PostgreSQL suite.

### PR 2 — schema

Take the original plan's schema as written — it is good. Two corrections:

- **`transactions`**: `UNIQUE(source, source_event_id)` where `source_event_id`
  is what PR 0a/0c already produce. `possible_duplicate BOOLEAN` and a `delayed`
  status are already meaningful because PR 0b defined them.
- **`cashback_ledger`**: keep `UNIQUE(transaction_id)`, keep `rule_version`.

Money columns `NUMERIC(20,2)`, matching the `Decimal` from PR 0d.

### PR 3 — repository abstraction

`TransactionRepository`, `AccountRepository`, `CategoryRepository`,
`BudgetRepository`, `CashbackRepository`, `KeywordRepository`, each with a
Sheets and a PostgreSQL implementation, chosen once at composition time. No
`if postgres:` inside handlers.

This is the PR that pays for itself even if PostgreSQL is abandoned: it is the
first time `handlers/` stops calling `sheets.*` directly.

### PR 4 — port idempotency to the database

Not a redesign. `UNIQUE(source, source_event_id)` plus
`INSERT ... ON CONFLICT DO NOTHING RETURNING id` expresses in one constraint
what `tx_exists()` currently achieves with a claim ledger. **Reuse the existing
idempotency tests verbatim** — they already encode the semantics, and passing
them against both backends is the proof the port is faithful.

### PR 5 — cashback atomicity, corrected

**Do not put cashback inside the transaction's insert.** The original plan's
sequence — `BEGIN → INSERT transaction → calculate cashback → INSERT
cashback_ledger → COMMIT` — means a *deterministic* bug in the cashback engine
rolls back the transaction row, SePay retries, it rolls back again, and the
financial event is never recorded. Losing a transaction because a secondary
feature failed is strictly worse than the current behaviour, which deliberately
comments: *"Never let a cashback error block the tx write."*

Correct shape:

```
TX 1:  BEGIN  INSERT transaction  INSERT outbox(tx_recorded)  COMMIT
TX 2:  BEGIN  compute cashback  INSERT cashback_ledger  COMMIT   (own retry)
```

Atomicity belongs between `cashback_ledger` and its own state, guarded by
`UNIQUE(transaction_id)` so a repeated callback cannot double-credit. Cashback
is derived data: it can be recomputed from the transaction at any time, which
is exactly why it must not be able to block the transaction.

`pending_mcc` stays a durable state on the transaction, resolved by a later
user selection in its own transaction.

### PR 6 — shadow writes

As the original plan: `STORAGE_BACKEND=sheets` + `POSTGRES_SHADOW_WRITE=true`,
reads still 100% Sheets, shadow failures observable and non-fatal. Metrics as
listed there.

### PR 7 — backfill and reconciliation, with a stable identity

The original plan's `source_event_id = <sheet-id>:<stable-row-id>` is unsafe:
Google Sheet row numbers move when rows are inserted or deleted, and `/recat`
and voiding do edit rows. A second backfill run after any such change would
duplicate or mis-key records — violating the plan's own idempotency requirement.

Use the `ref_code` already stored in the transactions tab as the legacy
identity: `legacy:<ref_code>`. It is unique in practice and stable under row
movement. For pre-PR-0a rows whose `ref_code` is a content hash, that hash is
still the best available identity — record them as `legacy_hash` so the
reconciliation report can show how many rows carry a weaker identity.

Reconciliation comparisons and the cutover gate: as the original plan.

### PR 8 — optional cutover and outbox

For an operator who opts in: `STORAGE_BACKEND=postgres`, the transactional
outbox, a Sheets sync worker with backoff. Never call the Sheets API inside a
database transaction. Sheets becomes that operator's mirror — while remaining
the default backend for everyone else.

---

## 4. Kept from the original plan without change

The core invariant (*1 unique upstream event = exactly 1 transaction*), the
migration principles, the schema shapes, the shadow-write metrics, the
reconciliation comparisons, the cutover gate thresholds, the observability list
and its logging prohibitions, the rollback posture, and the instruction to stop
polishing `storage/postgres_connection.py`. Those were all right.

---

## 5. Definition of done

Phase 0 (the part that matters):

1. Every SePay event is identified by SePay's `id`; every email event by its
   Gmail message id.
2. Two distinct transactions with identical amount, description and timestamp
   are both preserved.
3. No transaction is discarded without a record — duplicates and delayed events
   are flagged, not dropped.
4. Money is `Decimal` from parse to write.

Phase 1, additionally, and only for an operator who opts in:

5. `STORAGE_BACKEND=sheets` remains the default and is fully supported.
6. The bot runs and passes CI with no database driver installed.
7. The same idempotency tests pass against both backends.
8. A cashback failure cannot roll back a transaction.
9. Backfill is idempotent under row movement.
10. Reconciliation shows zero unexplained financial mismatches before any
    cutover, and backup/restore has been tested.

---

## 6. Order

```
PR 0a  SePay event id            ← start here
PR 0b  flag instead of drop
PR 0c  Gmail message id (+ operator migration note)
PR 0d  Decimal money
────────── Phase 0 gate: correctness fixed, still Sheets-only ──────────
PR 1   foundation (optional backend)
PR 2   schema
PR 3   repository abstraction     ← pays for itself regardless
PR 4   port idempotency to the DB
PR 5   cashback atomicity (separate transaction)
PR 6   shadow writes
PR 7   backfill + reconciliation
────────── cutover gate: unexplained mismatch = 0 ──────────
PR 8   opt-in cutover + outbox
```

Phase 0 is not a prerequisite you can skip. It is where the financial
correctness the original plan was reaching for actually gets fixed; Phase 1
only changes where the data lives.
