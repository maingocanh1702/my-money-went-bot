# Phase 1: Foundation — Remaining PRs

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-12
> **Trạng thái:** Active
> **Owner:** Founder (dev)
> **Mục đích:** Wrap-up Phase 1. Wave 0 (W0.1-W0.6) đã merged 2026-05-11. Còn 3 PR infra để complete foundation trước khi vào Phase 2 business logic.
> **Tham chiếu:**
> - [Implementation Tracker](../implementation-tracker.md)
> - [Roadmap §Phase 1](../mymoneywent-roadmap.md)
> - [Development Workflow §4 Wave 0](../operations/development-workflow.md)

---

## Overview

| PR | Scope | Tests | Est. days |
|----|-------|:-----:|:---------:|
| W1.1 | Docker Compose dev + prod | 2 (smoke) | 0.5 |
| W1.2 | Discord adapter | 8 (contract reuse + Discord-specific) | 1.0 |
| W1.3 | Phase 1 integration smoke E2E | 4 (cross-channel + tenant) | 0.5 |
| **Total** | | **14** | **~2 days** |

---

## W1.1 — Docker Compose dev + prod

### Scope

- `docker-compose.yml` (dev): Postgres 16 + bot service, env from `.env`
- `docker-compose.prod.yml` (override): production tuning (no port expose for Postgres, healthcheck, restart policy)
- `Dockerfile` (multi-stage, slim base, non-root user)
- `.dockerignore` (exclude `.venv`, `.git`, `__pycache__`, tests, docs)
- README update: `docker compose up` quickstart

### Files touched

```
+ Dockerfile
+ docker-compose.yml
+ docker-compose.prod.yml
+ .dockerignore
M README.md  (Quickstart section)
```

### Test plan

1. **Smoke (positive):** `docker compose up -d` → Postgres healthy → bot service `/health` returns 200
2. **Migration on cold start:** Container starts → alembic upgrade head runs idempotent

### Acceptance criteria

- `docker compose up` boots Postgres + bot in <30s on M-series Mac
- `/health/detailed` shows pool stats correctly
- Production override file passes `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` validate
- README quickstart works on clean machine

### Decision lockdown

- [ ] Postgres version: **16** (match Railway target)
- [ ] Python base: `python:3.12-slim` (match `.venv`)
- [ ] Run as non-root user `app` (uid 1000)
- [ ] Volume mount for migrations: read-only

### Risk / open questions

- Apple Silicon vs Linux/amd64 prod parity → use `--platform=linux/amd64` flag in prod build
- Secrets management: dev `.env` mount; prod use Railway env (no docker secrets needed yet)

---

## W1.2 — Discord adapter

### Scope

- `core/messenger/discord.py` — `DiscordSender(BaseSender)` impl
- Reuse `BaseSender` ABC + `SendPayload` TypedDict từ W0.4
- Webhook ingestion stub (Discord bot tokens, slash command registration deferred to F14 phase)
- Contract test suite parametrize: pass cho cả `TelegramSender` + `DiscordSender`

### Files touched

```
+ core/messenger/discord.py
+ tests/contract/test_messenger_discord_contract.py
M core/messenger/__init__.py  (wire DiscordSender)
M tests/contract/test_messenger_contract.py  (parametrize add discord)
```

### Test plan

1. **Contract (positive):** `send_text`, `send_image`, `send_markup` — all return DeliveryReceipt
2. **Contract (edge):** message >2000 chars → split or truncate per Discord limit (2000)
3. **Discord-specific (positive):** embed colored card support
4. **Discord-specific (edge):** rate limit (429) → retry with exponential backoff
5. **i18n (positive):** locale resolution VI/EN matches Telegram
6. **Error (negative):** invalid webhook URL → DeliveryFailed, no exception leak
7. **Tenant (mandatory):** payload `user_id` propagated via `tenant_context`
8. **Mock-only:** no real Discord API call (use `aioresponses` or similar)

### Acceptance criteria

- Contract test suite passes cho cả 2 senders
- Discord-specific limits documented (2000 char, 10 embed/message)
- `feature-discord-channel.md` spec invariants honored (no DM-only assumption)

### Decision lockdown

- [ ] Discord library: `discord.py` v2.x hay raw HTTP via `aiohttp`? — recommend `discord.py` (battle-tested, async)
- [ ] Webhook vs bot? — bot token for now (slash commands needed later in F14 full)
- [ ] Message split strategy on >2000 chars: split at last newline before 1950 chars

### Risk / open questions

- Discord bot registration flow: defer to F14 Phase 6 (this PR only ships adapter, not user-facing onboarding)
- Slash command schema: defer (uses adapter when ready)

---

## W1.3 — Phase 1 integration smoke E2E

### Scope

Integration test verify Phase 1 invariants end-to-end:
- 2 user across 2 channels (TG + Discord) → query verify isolated
- Adapter dispatch correct sender per channel
- Tenant context propagates through full request lifecycle

### Files touched

```
+ tests/integration/test_phase1_smoke.py
```

### Test plan

1. **Cross-channel isolation:** User A on Telegram + User B on Discord → User A `SELECT * FROM transactions` returns 0 (no data yet)
2. **Adapter dispatch:** `messenger.send(user_id=1, payload=...)` routes to TelegramSender; `user_id=2` (discord channel) routes to DiscordSender
3. **Health detailed:** `/health/detailed` returns pool stats + Sentry status + alembic head match expected revision
4. **Context propagation:** Sentry event from background task includes correct `user_id` from contextvar

### Acceptance criteria

- All 4 tests pass on real Postgres (testcontainers)
- Run time <15s
- No flakiness over 10 consecutive runs

### Decision lockdown

- [ ] Use existing `tests/integration/test_tenant_isolation.py` fixture pattern
- [ ] Mock external (Telegram/Discord API) — focus is internal wiring

---

## Phase 1 exit checklist (gate → Phase 2)

- [ ] W1.1, W1.2, W1.3 all merged
- [ ] `docker compose up` works on clean machine
- [ ] Discord adapter passes contract test
- [ ] Smoke E2E green
- [ ] Roadmap Phase 1 → 100%, tracker updated
- [ ] CHANGELOG entries added
- [ ] No new tech debt entries
- [ ] Move to `phase-2-handlers.md`

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-12 | Initial plan. 3 PRs (W1.1 docker, W1.2 discord, W1.3 smoke). ~2 days est. Wraps Wave 0 → Phase 1 complete. |
