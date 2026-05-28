# Autopilot Runbook — Zalo Channel Core

Generated 2026-05-28 from `docs/autopilot/autopilot-prompt-template.md` and
`docs/implementation-plan-zalo-channel-core.md` v0.3.0.

Use these prompts in order. Each prompt is intentionally one PR-sized phase.
Founder override is enabled for this prompt set: after local verification and
2× clean Codex review, each phase auto squash-merges into local `main`.

Do **not** push after each phase. Push only after all 4 phases are merged locally
and the final release gate passes.

## Prompt Order

1. `zalo-channel-core-z01-db-user-autopilot.md`
   - Adds DB support for `channel_type='zalo'` and `channel_chat_id`.
   - Updates `create_or_get_user()` and `/start` plumbing.

2. `zalo-channel-core-z02-sender-autopilot.md`
   - Adds `core.messenger.zalo.ZaloSender`.
   - Covers plain text rendering, numbered markup rendering, chunking, and token refresh behavior.

3. `zalo-channel-core-z03-webhook-autopilot.md`
   - Adds `/zalo/webhook` parser and route.
   - Requires a sanitized real Zalo webhook fixture before production signature behavior is enabled.

4. `zalo-channel-core-z04-category-flow-autopilot.md`
   - Adds DB-backed numbered parent-category selection flow.
   - Wires new SePay rows to category picker and reply resolution.

## Release Rule

Do not release Zalo interactive mode until all 4 phases are squash-merged into
local `main` and final full-suite verification passes:

```bash
ruff check .
black --check .
mypy core/ markets/
lint-imports
pytest tests/ -v
```

Keep `ZALO_ENABLED=false` and `ZALO_INTERACTIVE=false` in production until a real webhook fixture and one successful send probe verify:

- Webhook signature header/formula.
- Text webhook payload shape.
- `sender.id` can be used as outbound `recipient.user_id`.
- Text limit for the selected send API.

After final verification, push manually:

```bash
git status --short       # MUST be clean
git branch --show-current # MUST be main
git push origin main
```
