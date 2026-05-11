# Phase 5: Email Parsing — 9 PRs (1 infra + 1 onboarding + 6 parsers + 1 dedup)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-12
> **Trạng thái:** Active
> **Owner:** Founder (dev)
> **Mục đích:** Postmark inbound + Path C onboarding + 6 bank parsers (3 MVP, 3 defer-able) + cross-source dedup.
> **Tham chiếu:**
> - [Implementation Tracker](../implementation-tracker.md)
> - [Feature Spec F02](../features/feature-transaction-capture.md)
> - [BE Tech F02](../features/BE/feature-transaction-capture-tech.md)
> - [Roadmap §Phase 5](../mymoneywent-roadmap.md)

---

## Overview

| PR | Scope | Tests | Est. days | MVP? |
|----|-------|:-----:|:---------:|:----:|
| W5.1 | Postmark inbound `/inbound/{token}` route | 12 | 1.5 | ✅ |
| F01d | Path C onboarding (Gmail + Outlook guides) | 10 | 1.5 | ✅ |
| P-TCB | Parser: Techcombank full extraction | 8 | 1.5 | ✅ |
| P-Cake | Parser: Cake (VPBank) | 8 | 1.5 | ✅ |
| P-MB | Parser: MB Bank | 8 | 1.5 | ✅ |
| P-ACB | Parser: ACB | 8 | 1.5 | ⚠️ defer-able |
| P-STB | Parser: Sacombank | 8 | 1.5 | ⚠️ defer-able |
| P-BIDV | Parser: BIDV | 8 | 1.5 | ⚠️ defer-able |
| F02-dedup | Cross-source dedup (SePay + Email) | 10 | 1.5 | ✅ |
| **MVP scope** | **6 PRs** | **56** | **~9 days** | |
| **Full scope** | **9 PRs** | **80** | **~13.5 days** | |

**Parser plugin framework + 6 shells already shipped W0.6.** This phase = full HTML extraction logic + golden fixtures.

**MVP scope LOCKED 2026-05-12:** Ship TCB + Cake + MB only. ACB/STB/BIDV → Phase 5b post-soft-launch, prioritized by beta-user demand signal (request count + active user with that bank as primary).

**Rationale:** Covers ~70% target beta persona (Minh/Linh banking habits). Plugin framework allows incremental add zero-cost. Avoid premature 6-bank investment when usage data unknown.

---

## W5.1 — Postmark inbound

### Scope

- HTTP route `POST /inbound/{user_token}` — Postmark webhook payload
- Token resolution: lookup `webhook_tokens` by SHA256(token), verify user exists
- Parser dispatch: extract bank from sender domain, route to parser plugin
- Unparsed fallback: notify user via messenger "Email đến nhưng không parse được, forward [admin] để add support"
- Idempotency: dedupe by `Message-ID` header

### Files touched

```
+ markets/vn/capture/postmark_webhook.py
+ markets/vn/capture/parser_router.py
+ tests/integration/test_postmark_inbound.py
M main.py  (wire /inbound/{token} route)
```

### Test plan (12)

1. Positive: TCB email → parser route → tx inserted
2. Positive: Unknown sender domain → unparsed fallback message sent
3. Token resolution: valid token → correct user
4. Token resolution: invalid → 200 silent (no leak, per Gap 3 invariant)
5. Idempotency: same Message-ID twice → 1 tx insert only
6. Parser plugin: TCB sender pattern matches `noreply@techcombank.com.vn`
7. Parser plugin: Cake sender pattern matches
8. Multipart email: HTML+plain text → prefer HTML
9. Attachment: ignore (no PDF parsing MVP)
10. Charset: UTF-8 + ISO-8859-1 + windows-1258 (VN encoding) all handled
11. Tenant isolation: user A token → tx ONLY for user A
12. Rate limit: 100 emails/min/token → 429 after that (anti-abuse)

### Acceptance criteria

- Endpoint live, Postmark webhook config docs in README
- Unknown bank → user gets graceful fallback (not silent drop)
- Idempotent across replay
- Rate limit configurable via env

### Decision lockdown

- [ ] **Idempotency key:** `Message-ID` header. Store in new table `email_seen_ids` (24h TTL via cron sweep). Or use `transactions` external_id field?
  → **Decision:** Add `email_seen_ids(user_id, message_id, seen_at)` with 24h cleanup. Decouple from `transactions` for unparsed cases.
- [ ] **Rate limit:** 100/min/token. Store counter in `bot_state` JSONB.
- [ ] **Sender → bank mapping:** Defined in each parser's `bank_pattern` regex, central registry via `@register_parser`.
- [ ] **Unparsed notification:** 1 message per unknown sender per day per user (anti-spam).

### Risk

- **Postmark cost:** 10k inbound emails/mo = $10. Monitor via F11 admin cost command (Phase 6).
- **Charset edge:** windows-1258 (VN Windows legacy) — test golden fixtures include sample.

---

## F01d — Path C onboarding (email forwarding)

### Scope

- Extend onboarding picker (F01b) with Path C option
- User picks C → bot shows guide screens:
  - Gmail: filter setup → forward to `{user_token}@inbound.tienvenoidau.com`
  - Outlook: rule setup → forward to same
- Validation: send test email instructions, detect first inbound → trigger F01c celebration
- Per-bank tip: "If you bank with X, also enable email notifications in their app"

### Files touched

```
M core/handlers/onboarding.py  (add Path C branch)
+ core/services/inbound_address.py  (generate per-user inbound email address)
+ tests/integration/test_path_c_onboarding.py
```

### Test plan (10)

1. Path C button → guide screen 1 (Gmail) shown
2. Inline button "Outlook" → screen 2 (Outlook) shown
3. Inline button "Skip help" → just shows address + done
4. Inbound address format: `{user_token}@inbound.tienvenoidau.com` (lowercase, alphanumeric)
5. Two users get different addresses (no collision)
6. Test email instruction: "Send any email from your bank account to test"
7. First inbound → F01c celebration triggers (cross-feature integration)
8. Edge: user copies address to wrong place → silent (no detection unless email arrives)
9. Isolation: User A address never resolves to User B
10. i18n: VI/EN both render

### Acceptance criteria

- Path C completable in <3 min following the guide
- Inbound address visible at any time via `/setup → show inbound`
- Cross-references F01c celebration

### Decision lockdown

- [ ] **Inbound address format:** Per-user token (same scheme as webhook). DNS: setup `inbound.tienvenoidau.com` MX → Postmark.
- [ ] **Per-user address:** Yes (vs single shared inbox with parsing for user identifier). Cleaner isolation, easier debugging.
- [ ] **Test email flow:** No active validation — first real bank email = success signal.

---

## P-TCB — Techcombank parser

### Scope

- Implement `markets/vn/email_parsers/tcb.py:parse()` (shell from W0.6 has the skeleton)
- HTML extraction: amount, currency, type (debit/credit), tx_external_id, balance, merchant
- Output: `CanonicalTransaction` per `core/canonical_tx.py`
- Golden fixtures: 10 sample emails (cover debit/credit/refund/ATM/transfer)

### Files touched

```
M markets/vn/email_parsers/tcb.py
+ tests/integration/fixtures/email_samples/tcb/*.html  (10 samples)
+ tests/integration/test_parser_tcb.py
```

### Test plan (8)

1. Positive: standard debit → correct amount + merchant
2. Positive: standard credit → correct sign
3. Positive: ATM withdrawal → type='atm_withdrawal'
4. Edge: transaction with VND notation "1.234.567" → 1234567 int
5. Edge: timezone in email → convert to user TZ stored as UTC
6. Edge: HTML encoded chars (é, đ) → unicode preserved
7. Pure: parser doesn't touch DB or messenger (import-linter contract)
8. Idempotency: same email parsed twice → identical CanonicalTransaction (deterministic)

### Acceptance criteria

- ≥85% accuracy on 10 golden fixtures
- All canonical fields populated
- Parser pure (4th import-linter contract pass)

### Decision lockdown

- [ ] **Golden fixtures source:** Founder's own TCB emails, redact personal info (account number → XXXX, name → "Test User")
- [ ] **Currency:** Always VND for VN parsers. No FX.
- [ ] **Merchant extraction:** Best-effort regex. Unparseable merchant → `null`, don't fail whole parse.

---

## P-Cake, P-MB, P-ACB, P-STB, P-BIDV

**Same pattern as P-TCB.** Each PR:
- Parser impl in `markets/vn/email_parsers/<bank>.py`
- 10 golden fixtures
- 8 tests (same plan)
- Parser-pure contract enforced

**Specific notes per bank:**

- **P-Cake (VPBank):** Email is sender `noreply@cake.vn` (NOT vpbank.com.vn). Parser logic similar to TCB.
- **P-MB:** MB Bank emails often plain-text, not HTML. Parser must handle both.
- **P-ACB:** ACB uses Vietnamese formatting heavily, double-check accent handling.
- **P-STB:** Sacombank sends summary emails (multi-tx per email!) — parser must yield multiple CanonicalTransactions. Special case.
- **P-BIDV:** BIDV emails large, marketing fluff. Strict regex needed.

### MVP defer rule (LOCKED 2026-05-12)

**MVP ships:** P-TCB + P-Cake + P-MB only.

**Phase 5b (post-soft-launch):** P-ACB, P-STB, P-BIDV ship based on:
- Beta user request count per bank (≥3 distinct users asking for same bank)
- OR signup with that bank as primary (≥5 new signups in 1 week)

Plugin framework allows zero-cost incremental add — no core changes needed.

---

## F02-dedup — Cross-source dedup

### Scope

- Service: `core/services/tx_dedup.py`
- Algorithm: fuzzy match on (user_id, amount, type, ±3 min window, optional bank)
- Sources: SePay webhook + Email parser may both fire for same real-world tx
- Resolution: first-seen wins, mark duplicate with `is_duplicate=TRUE` (preserve audit trail, don't delete)

### Files touched

```
+ core/services/tx_dedup.py
M migrations/versions/0003_tx_dedup_flag.py  (add transactions.is_duplicate boolean default false)
M core/handlers/transaction.py  (call dedup before insert; if duplicate, mark, don't trigger celebration/categorize)
+ tests/unit/test_dedup_algorithm.py
+ tests/integration/test_cross_source_dedup.py
```

### Test plan (10)

1. Positive: SePay + Email arrive within 3 min → dedup detected, 1 active tx + 1 marked duplicate
2. Positive: Same amount, different type (debit vs credit) → NOT duplicate
3. Edge: 3-min boundary (180 sec exact) → IS duplicate (inclusive)
4. Edge: 3 min + 1 sec → NOT duplicate
5. Edge: Same source twice (2 SePay) → idempotent dedup via Postmark Message-ID layer (W5.1), not this service
6. Edge: User has 2 banks, SePay for both → bank field disambiguates
7. Negative: similar amount but different user → NOT cross-tenant
8. Isolation: dedup query bounded to single user_id
9. Algorithm: O(log n) with index on (user_id, amount, type, occurred_at)
10. Audit: duplicate row preserves source_label ('sepay'/'email'/'manual')

### Acceptance criteria

- Cross-source dedup prevents double-counting in reports
- Audit trail preserved (duplicates queryable, not deleted)
- No false positives (different real txs not merged)

### Decision lockdown

- [ ] **Window:** ±3 min. Locked per BRD spec.
- [ ] **Duplicate handling:** Soft (`is_duplicate=TRUE`), not hard delete. Reports filter `WHERE is_duplicate=FALSE`.
- [ ] **First-seen wins:** SePay typically arrives faster (real-time webhook) than email (batched delivery). Preserve source_label for debug.
- [ ] **Manual entry conflict:** Manual `/add` tx + auto-detected → dedup applies same rule.

---

## Phase 5 exit checklist (gate → Phase 6)

### MVP scope (3 banks):
- [ ] W5.1 Postmark inbound merged + DNS configured
- [ ] F01d Path C onboarding merged
- [ ] P-TCB, P-Cake, P-MB merged with ≥85% accuracy each
- [ ] F02-dedup merged, integration test confirms no double-count
- [ ] Founder's own bank emails (TCB) parsing in production for 1 week (canary)
- [ ] Roadmap Phase 5 → 100% (MVP); P-ACB/STB/BIDV moved to "Phase 5b" (post-launch)

### Defer-able PRs:
- P-ACB, P-STB, P-BIDV — ship post-soft-launch based on beta feedback

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-12 | Initial plan. 9 PRs total (6 MVP + 3 defer). ~9 days MVP, ~13.5 days full. Parser shells already W0.6, this phase = HTML extraction + fixtures + dedup. P-STB special-case multi-tx per email noted. |
