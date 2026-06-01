# Implementation Plan — Facebook Messenger channel + `/recat` command

**Status:** Revised draft / proposal
**Target repo:** `my-money-went-bot` (public OSS)
**Source of truth:** `/recat` and Zalo-style picker patterns are ported from the private `Bot Finance` codebase; Facebook Messenger itself is net-new work
**Author:** generated 2026-06-01, revised 2026-06-01

---

## 1. Goal (working backwards)

Two independent deliverables, shipped as separate PRs:

1. **`/recat <row>` command** — let the user re-categorize *any* past transaction by row number, not just the one the bot just logged. Small, low-risk.
2. **Facebook Messenger channel** — a genuine third front-end (after Telegram and Zalo) so a user can run the same bot from Messenger. Net-new, larger.

The end state we are working back from:

> A Messenger user can run `/report`, `/today`, `/keywords`, `/manage`, `/allocate`, and `/recat 125` from Messenger. Messenger may also receive transaction prompts **only while the user is inside Meta's allowed messaging window, or if PR 0 proves a policy-compliant tagged send path for this exact use case**. Otherwise transaction prompts continue to fall back to Telegram.

---

## 2. Current state (what already exists — do NOT rebuild)

This was verified against the current `main` of the public repo.

### 2.1 `/recat` is ~80% already here

| Piece | Location | Status |
|---|---|---|
| `handle_recategorize(parts, message_id)` core | `handlers/transaction.py:188` | ✅ present (identical to Bot Finance) |
| "🔄 Sai mục?" inline button on every confirmation | `handlers/transaction.py:259,272,320` | ✅ present |
| Callback dispatch `prefix == "recat"` | `main.py:222` | ✅ wired |
| `_CALLBACK_MIN_PARTS["recat"] = 2` | `main.py:44` | ✅ present |
| Sheet helpers (`get_transaction_row`, `reset_transaction_row`, `row_currency`, `get_active_buckets`, `_parse_amount`, `fmt_amount`, `fmt_month`) | `sheets.py` | ✅ all present |
| `tg.build_bucket_buttons`, `tg.edit_message` | `telegram_api.py` | ✅ present |

**So the button-based recat (fix the *just-logged* tx) already works.** The only gap is the **`/recat <row>` slash command** for fixing an *arbitrary older* row.

### 2.2 Channel architecture (the pattern Messenger must follow)

The public repo deliberately does **not** use the `messenger.py` abstraction layer that Bot Finance has. Instead, each channel is a **parallel dispatcher** that shares only the business logic in `sheets.py` and `handlers/*`.

```
FastAPI (main.py)
├── POST /webhook         → Telegram updates + SePay webhooks  → _process()
│                            ├── _handle_callback()  (inline-button taps)
│                            ├── _handle_message()   (text + state machine)
│                            └── _handle_command()
├── POST /zalo/webhook    → Zalo events → _process_zalo()
│                            ├── _handle_zalo_command()
│                            └── _handle_zalo_text()  (numbered-text state machine)
└── handlers/*            → shared business logic (Telegram-button shaped)
    sheets.py             → shared Google Sheets data layer
```

**Key insight — analogy:** Telegram is a "rich client" (native inline keyboards + editable messages + `callback_query`). Zalo is a "dumb terminal" (plain text only → numbered menus, state stored per `chat_id`). **Messenger sits in between**: it has tappable *quick replies* whose payload comes back as an ordinary message webhook — closer to Zalo's model than Telegram's. So **Messenger should be built by mirroring the Zalo dispatcher**, optionally upgraded with quick-reply buttons.

Important correction: the public repo's Zalo dispatcher currently covers `/today`, `/report`, `/accounts`, `/keywords`, `/manage`, and `/allocate`, but it does **not** yet handle SePay transaction category picking. New outgoing transactions still set Telegram `await_parent` state and send Telegram inline buttons only (`handlers/sepay.py:241-256`). Bot Finance has the missing numbered transaction picker + queue pattern (`Bot Finance/handlers/sepay.py:254-293`), so Messenger transaction picking must port/adapt that pattern rather than assuming it already exists in public Zalo.

Zalo state machine reference (good template for command/menu flows):
- `_process_zalo` → `main.py:330`
- `_handle_zalo_command` → `main.py:439`
- `_handle_zalo_text` (step router) → `main.py:372`
- `zalo_api.py` (send/strip/chunk/webhook helpers) → 194 LOC, the closest template for `messenger_api.py`
- Config gating: `ZALO_ENABLED` / `ZALO_INTERACTIVE` / `ZALO_WEBHOOK_SECRET` / `ZALO_USER_ID` in `config.py:28-58`

Bot Finance reference (template for transaction picker + recat entry points):
- `handlers/sepay.py:254-293` → numbered non-Telegram transaction picker + pending queue.
- `messenger.py:85-132` → Telegram button conversion to numbered options / bucket map.
- `main.py:1508` → `_zalo_cmd_recat`.
- `main.py:2844` → `_tg_cmd_recat`.

---

## 3. Part A — `/recat <row>` command (small)

### 3.1 Domain model

`/recat <row>` = "take an already-finalized transaction row, undo its categorization, and re-run the normal category picker against it." The undo + re-pick machinery already exists (`reset_transaction_row` + `await_parent` state + `build_bucket_buttons`). We are only adding the **entry point** that accepts an explicit row number.

### 3.2 Telegram changes

**File: `main.py`**

Add a command handler mirroring Bot Finance's `_tg_cmd_recat` (Bot Finance `main.py:2844`). Adapted to the public's existing helpers:

```python
async def _cmd_recat(text: str):
    """/recat <row_num> — re-categorize a past transaction via the bucket picker."""
    parts = text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await tg.send_text("Usage: `/recat <row_number>`\nVd: `/recat 125`")
        return
    row_num = int(parts[1])
    row = sh.get_transaction_row(row_num)
    if not row:
        await tg.send_text(f"⚠️ Không tìm thấy transaction row {row_num}.")
        return

    direction = "in" if (row[6] if len(row) > 6 else "") == "Tiền vào" else "out"
    if direction == "in":
        await tg.send_text("ℹ️ Income hiện không cần category. Không recat.")
        return

    amount = sh._parse_amount(row[7]) if len(row) > 7 else 0
    description = row[5] if len(row) > 5 else ""
    currency = sh.row_currency(row)

    # Use the transaction's own month so old rows show the correct bucket set.
    row_month = row[14] if len(row) > 14 else ""
    month_key = row_month or sh.fmt_month(datetime.now(pytz.timezone(TIMEZONE)))
    buckets = sh.get_active_buckets(month_key)
    if not buckets:
        await tg.send_text(f"⚠️ Không có category active cho tháng {month_key}. Dùng /manage trước.")
        return

    sh.reset_transaction_row(row_num)
    sh.set_state(CHAT_ID, {
        "step": "await_parent", "row_num": row_num,
        "amount": amount, "currency": currency, "description": description,
    })
    buttons = tg.build_bucket_buttons(buckets, f"p_{row_num}", include_new=True)
    await tg.send_with_buttons(
        f"↩️ *Re-categorize: -{sh.fmt_amount(amount, currency)}*\n"
        f"`{description}`\n\nKhoản này thuộc mục nào?",
        buttons,
    )
```

Wire it into `_handle_command` (`main.py:302`):

```python
    elif cmd == "/recat":     await _cmd_recat(text)
```

Use local imports inside `_cmd_recat` (`from datetime import datetime`, `import pytz`) or add them at module scope. `main.py` currently imports neither at module scope.

**File: `telegram_api.py` → `set_my_commands()`**
Add `/recat` to the command menu so it shows in Telegram's "/" picker.

**Help text:** add a `/recat <row>` line to the default help blurb in `_handle_message` (`main.py:236`).

**Consistency note (fix while here):** the existing button-path `handle_recategorize` (`handlers/transaction.py:188`) computes its bucket set from the **current** month (`fmt_month(datetime.now(...))`), whereas the new `/recat <row>` command above uses the transaction's **own** month (`row[14]`). Re-categorizing an old row via the button vs. via the command would therefore offer different bucket sets. Update `handle_recategorize` to also read `row[14]` (falling back to current month when empty) so both entry points behave identically. Add a regression test for an old-month row recategorized via the button.

### 3.3 Zalo (optional, only if Zalo interactive is enabled)

Port `_zalo_cmd_recat` (Bot Finance `main.py:1508`) into the public Zalo dispatcher. It uses the Zalo numbered-bucket state (`await_zalo_parent` / `_format_zalo_bucket_options`). **Defer to a follow-up** unless Zalo interactive recat is explicitly wanted — the Telegram command covers the core need.

If Zalo `/recat` is added later, do not copy it blindly. The public repo currently has no `await_zalo_parent` router, `_format_zalo_bucket_options`, or transaction picker queue. Those must be ported first or introduced as a shared channel picker helper.

### 3.4 Tests

Add `tests/unit/test_recat_command.py`:
- `/recat` with no arg / non-numeric → usage message.
- `/recat <missing row>` → not-found message.
- `/recat <income row>` → "income không cần category".
- `/recat <expense row>` → row reset + state set to `await_parent` + bucket buttons sent.
- `/recat <old-month expense row>` → uses `row[14]` month buckets, not current month.
- `/recat <expense row>` with no active buckets for that row month → clear warning and no row reset.

Mirror the fake-worksheet harness in `tests/unit/test_fake_ws_smoke.py` / `conftest.py`.

### 3.5 Effort
~1–2 hours including tests. Pure additive, no schema or migration impact.

---

## 4. Part B — Facebook Messenger channel (net-new)

### 4.1 Domain model

A Messenger conversation maps onto the existing model as:

| Concept | Telegram | Messenger equivalent |
|---|---|---|
| User identity | `chat.id` == `CHAT_ID` | sender **PSID** == `MESSENGER_USER_PSID` |
| Send text | `tg.send_text` | `POST graph.facebook.com/{version}/me/messages` or page-specific messages endpoint, authenticated with Page access token |
| Buttons | inline keyboard + `callback_query` | **quick replies** (payload echoed as a message) |
| Edit message | `tg.edit_message` | ❌ not supported → send a new message |
| Webhook auth | `X-Telegram-Bot-Api-Secret-Token` | `X-Hub-Signature-256` (HMAC-SHA256 of body w/ App Secret) + GET verify token |
| State | `sh.get_state(chat_id)` | `sh.get_state(psid)` with `msgr_*` step prefixes |

Because Messenger cannot edit a message and quick-reply payloads return as plain messages, **the Zalo text-menu dispatcher is the correct structural template for read-only/menu commands**, with quick replies layered on for nicer UX. For SePay transaction category picking, use the Bot Finance numbered-picker queue pattern as the template, because the public Zalo code does not currently implement that flow.

Policy constraint (verified June 2026 — see §5 PR 0): Messenger proactive sends are gated by two separate Meta walls, and both must be validated **before** building the fan-out.

1. **24-hour window + message tags.** Outside the standard 24h window, automated Messenger sends only have narrow non-promotional tag paths such as `ACCOUNT_UPDATE`, `POST_PURCHASE_UPDATE`, and `CONFIRMED_EVENT_UPDATE` — *not* "template messages" (that is WhatsApp Business terminology; Messenger has no pre-approved templates). `HUMAN_AGENT` is a separate manual-support path for human-sent replies and must not be used by this automated bot. The closest automated fit, `ACCOUNT_UPDATE`, is officially defined for a **non-recurring** account change (e.g. password reset). A continuous stream of bank-transaction prompts is recurring, so leaning on `ACCOUNT_UPDATE` for every tx is a policy gray area and risks app rejection/ban. The opt-in **Recurring Notifications** route was replaced by **Marketing Messages** on 2026-01-07 and is *no longer available in most countries* (Vietnam almost certainly unsupported), and it is classed as marketing anyway — so it does not rescue this use case.

2. **App Review + Business Verification.** In **Development Mode**, a Page token can only message Facebook accounts that hold an **Admin / Developer / Tester** role on the app. Messaging any other end-user requires Meta **App Review** of `pages_messaging` plus **Business Verification**. Implication: the bot author messaging *their own* account works fine in dev mode with no review, but a third party who clones this OSS repo to self-host must clear App Review to message themselves unless they add their own account as an app role. This makes Messenger materially harder to set up than Telegram or Zalo for the OSS audience.

**Net:** proactive transaction prompts are **not assumed viable**. They may be viable for a **single-user, dev-mode, owner-as-admin** deployment only if PR 0 proves Meta accepts the exact send path and content. They are **not cleanly distributable** as a general OSS channel. The implementation must treat Messenger as command-first by default and degrade to "reply within 24h or use Telegram for live prompts" UX.

### 4.2 New file: `messenger_api.py`

Mirror `zalo_api.py` (194 LOC). Functions:

```python
GRAPH_BASE = f"https://graph.facebook.com/{MESSENGER_GRAPH_VERSION}"

async def send_text(text: str, psid: str | None = None) -> dict | None: ...
async def send_quick_replies(text: str, options: list[dict], psid=None): ...
    # options: [{"title": "🛒 Daily", "payload": "p_5_daily_spending"}, ...]
    # Messenger limit: max 13 quick replies, title ≤ 20 chars, payload ≤ 1000
async def send_buttons(text: str, buttons: list[dict], psid=None): ...   # button template, max 3
def strip_markdown(text: str) -> str: ...        # reuse zalo_api.strip_markdown logic
def chunk_text(text: str, max_chars: int = 2000) -> list[str]: ...
def verify_signature(app_secret: str, raw_body: bytes, header: str) -> bool: ...
```

Notes:
- Prefer `Authorization: Bearer <MESSENGER_PAGE_TOKEN>` on Graph calls. Use query-string `access_token` only if the chosen endpoint/version requires it, because query strings are more likely to leak in logs.
- Include `messaging_type` in every Send API payload. Use `RESPONSE` for user-initiated replies. For bot-initiated transaction/account notifications, only use `MESSAGE_TAG` + an allowed tag if the message fits Meta policy and the current API version accepts it.
- Keep Graph API version configurable (`MESSENGER_GRAPH_VERSION`, default to the version verified during implementation). Do not hard-code stale versions in code.
- Strip Markdown before sending (Messenger renders none) — reuse the Zalo helper.
- `send_text` chunks long messages like Zalo does.
- A helper to convert the Telegram `build_bucket_buttons` output (`[[{text, callback_data}]]`) into Messenger quick replies — analogous to Bot Finance's `_buttons_to_numbered_text` / `buttons_to_bucket_map` in `messenger.py`. Reuse the `p_{row}_{bucket}` payload convention so the picker math is shared.
- Add a fallback renderer that sends numbered text when there are more than 13 quick replies, titles exceed Messenger limits, or the payload is not suitable for quick replies.

### 4.3 `config.py` additions

Follow the exact pattern of the Zalo block (`config.py:28-58`):

```python
# ── Optional: Facebook Messenger channel ──────────────────────────────
MESSENGER_ENABLED      = os.environ.get("MESSENGER_ENABLED", "false").lower() == "true"
MESSENGER_PAGE_TOKEN   = os.environ.get("MESSENGER_PAGE_TOKEN", "")   # Page access token
MESSENGER_APP_SECRET   = os.environ.get("MESSENGER_APP_SECRET", "")   # for X-Hub-Signature-256
MESSENGER_VERIFY_TOKEN = os.environ.get("MESSENGER_VERIFY_TOKEN", "") # GET webhook handshake
MESSENGER_USER_PSID    = os.environ.get("MESSENGER_USER_PSID", "")    # authorized sender (PSID)
MESSENGER_GRAPH_VERSION = os.environ.get("MESSENGER_GRAPH_VERSION", "v25.0")
MESSENGER_DISCOVERY_MODE = os.environ.get("MESSENGER_DISCOVERY_MODE", "false").lower() == "true"
MESSENGER_PROACTIVE_MODE = os.environ.get("MESSENGER_PROACTIVE_MODE", "off")
# allowed: off | window_only | tagged_experiment
```

Extend the startup validation block:
- When `MESSENGER_ENABLED`, require `MESSENGER_PAGE_TOKEN`, `MESSENGER_APP_SECRET`, and `MESSENGER_VERIFY_TOKEN`.
- Require `MESSENGER_USER_PSID` unless `MESSENGER_DISCOVERY_MODE=true`.
- In discovery mode, accept signed webhook events, log only the sender PSID and safe metadata, and do not process commands or send transaction data until `MESSENGER_USER_PSID` is configured.

Add all Messenger env vars to `.env.example`, with comments that Railway users should keep `MESSENGER_ENABLED=false` until the Page token, app secret, verify token, and PSID are known.

`MESSENGER_PROACTIVE_MODE` gates all bot-initiated Messenger sends:
- `off` (default): Messenger is command-only; no SePay proactive prompt/fan-out.
- `window_only`: send proactive prompts only when `last_messenger_user_interaction_at` is within 24 hours.
- `tagged_experiment`: allow tagged sends outside 24 hours only after PR 0 explicitly green-lights the exact tag/content path. This mode must remain documented as experimental and policy-risky.

### 4.4 `main.py` — webhook endpoints

**GET verify handshake** (Messenger requires this once when you register the webhook):

Add `PlainTextResponse` to the FastAPI response imports and import `json` at module scope.

```python
@app.get("/messenger/webhook")
async def messenger_verify(request: Request):
    params = request.query_params
    if (params.get("hub.mode") == "subscribe"
            and params.get("hub.verify_token") == MESSENGER_VERIFY_TOKEN):
        return PlainTextResponse(params.get("hub.challenge", ""))
    return PlainTextResponse("forbidden", status_code=403)
```

**POST receive** (mirror `/zalo/webhook` gating + signature check):

```python
@app.post("/messenger/webhook")
async def messenger_webhook(request: Request, bg: BackgroundTasks):
    if not MESSENGER_ENABLED:
        return JSONResponse({"ok": True})
    raw = await request.body()
    sig = request.headers.get("x-hub-signature-256", "")
    if not messenger_api.verify_signature(MESSENGER_APP_SECRET, raw, sig):
        print("[messenger] rejected: bad signature")
        return JSONResponse({"ok": True})
    try:
        body = json.loads(raw or b"{}")
    except Exception:
        return JSONResponse({"ok": True})
    if body.get("object") != "page":
        return JSONResponse({"ok": True})
    bg.add_task(_process_messenger, body)
    return JSONResponse({"ok": True})
```

### 4.5 `main.py` — dispatcher (mirror Zalo)

```python
async def _process_messenger(body: dict):
    try:
        for entry in body.get("entry", []):
            for ev in entry.get("messaging", []):
                psid = str(ev.get("sender", {}).get("id", ""))
                if MESSENGER_USER_PSID and psid != MESSENGER_USER_PSID:
                    continue  # reject unauthorized sender
                msg = ev.get("message", {})
                if msg.get("is_echo") or ev.get("delivery") or ev.get("read"):
                    continue

                if MESSENGER_DISCOVERY_MODE and not MESSENGER_USER_PSID:
                    print(f"[messenger-discovery] psid={psid}")
                    continue

                # Any real inbound user event reopens/refreshes the Messenger window.
                sh.set_state(psid, {
                    **(sh.get_state(psid) or {}),
                    "last_messenger_user_interaction_at": datetime.now(timezone.utc).isoformat(),
                })

                # quick-reply tap → treat payload like a Zalo numbered choice / Telegram callback
                qr = msg.get("quick_reply", {}).get("payload")
                postback = ev.get("postback", {}).get("payload")
                text = qr or postback or (msg.get("text") or "").strip()
                if not text:
                    continue
                if text.startswith("/"):
                    await _handle_messenger_command(text, psid)
                else:
                    await _handle_messenger_text(text, psid)
    except Exception:
        ...  # same err-id logging pattern as _process_zalo
```

Then build, mirroring the Zalo functions one-for-one:
- `_handle_messenger_command` ← copy of `_handle_zalo_command` (`/today`, `/report`, `/accounts`, `/keywords`, `/manage`, `/allocate`, `/cancel`, `/recat`).
- `_handle_messenger_text` ← step router like `_handle_zalo_text`, with `msgr_*` step prefixes to avoid colliding with `zalo_*` state.
- The command/menu interactive flows (`keywords`, `manage`, `allocate`) reuse the Zalo numbered-menu logic. **Decision:** render menus as **quick replies** (`messenger_api.send_quick_replies`) where ≤13 options, falling back to numbered text when more.
- The transaction category pick and `/recat` flows should use a new `msgr_await_parent` state, with `row_num`, `amount`, `currency`, `description`, `tx_direction`, `buckets`, and `queue`, adapted from Bot Finance's Zalo transaction picker. This is not present in public Zalo today.
- Quick replies and postbacks both route through the same payload parser. Numbered-text fallback routes through the active `msgr_*` state and selected index.
- Persist `last_messenger_user_interaction_at` on every non-echo inbound event from the authorized PSID. Use it to decide whether the user is still inside the 24h messaging window before any bot-initiated SePay prompt.

### 4.6 Transaction picker and notification fan-out

SePay has two different notification shapes:

1. Text-only notifications (`notifier.py`) for welcome, income, and auto-categorized notices.
2. Interactive transaction category prompts (`handlers/sepay.py:241-256`) that currently go only to Telegram.

Implement Messenger support separately for each shape:
- Add Messenger best-effort text fan-out to `notifier.py`, guarded by `MESSENGER_ENABLED`, `MESSENGER_USER_PSID`, and `MESSENGER_PROACTIVE_MODE`.
- Add a Messenger-specific outgoing transaction picker in `handlers/sepay.py`, next to the Telegram picker, modeled on Bot Finance's Zalo queue logic. Do not route this through `notifier.py`, because it needs buttons/quick replies and per-channel state.
- Before sending any Messenger proactive prompt, evaluate `MESSENGER_PROACTIVE_MODE`:
  - `off`: do not send Messenger proactive messages.
  - `window_only`: send only when `last_messenger_user_interaction_at` is less than 24 hours old.
  - `tagged_experiment`: send outside 24 hours only with the PR-0-approved tag/content path; safely skip on Graph policy errors.
- If Messenger proactive send is not allowed, Telegram remains the reliable prompt channel. Do not block SePay processing.
- When a Messenger category is selected, finalize the same transaction row. To avoid double-finalize races across Telegram/Messenger, re-read the row before finalizing and handle already-confirmed rows idempotently.
- For more than one pending outgoing transaction, queue later Messenger prompts behind the current `msgr_await_parent` row, like Bot Finance does for Zalo.

### 4.7 Security checklist
- Verify `X-Hub-Signature-256` on every POST (constant-time compare).
- GET verify-token handshake gated on `MESSENGER_VERIFY_TOKEN`.
- Reject any sender PSID ≠ `MESSENGER_USER_PSID` (single-user bot, same as Zalo `ZALO_USER_ID`).
- Keep `MESSENGER_DISCOVERY_MODE` narrow: signed webhook + safe PSID logging only; no command execution and no transaction data send.
- Always return HTTP 200 quickly; process in background (Messenger retries on non-200, like Telegram).
- Never log the page token / app secret.
- Do not log raw webhook bodies, message text, bank descriptions, or transaction amounts in discovery/error logs.
- Do not send proactive Messenger notifications unless the message type and tag comply with current Meta policy.
- Never use `HUMAN_AGENT` from automated code.
- Treat Graph API policy/window errors as terminal for that send attempt: log a safe summary and do not retry in a loop.

### 4.8 Tests
`tests/unit/test_messenger_webhook.py`:
- GET verify: correct token → echoes `hub.challenge`; wrong token → 403.
- POST with bad/missing `X-Hub-Signature-256` → ignored.
- POST from unauthorized PSID → ignored.
- Discovery mode with no `MESSENGER_USER_PSID` → logs PSID-safe marker and does not execute commands.
- Quick-reply payload `p_5_daily_spending` routes into the category picker.
- Postback payload routes through the same parser as quick replies.
- Numbered fallback selection routes through `msgr_await_parent`.
- Multiple pending SePay outgoing rows queue instead of overwriting the active Messenger state.
- Inbound user event stores/refreshes `last_messenger_user_interaction_at`.
- `MESSENGER_PROACTIVE_MODE=off` → SePay does not call Graph for Messenger.
- `MESSENGER_PROACTIVE_MODE=window_only` + last interaction <24h → Messenger prompt allowed.
- `MESSENGER_PROACTIVE_MODE=window_only` + last interaction >24h/missing → no Messenger Graph send; Telegram path still runs.
- `MESSENGER_PROACTIVE_MODE=tagged_experiment` disabled/unapproved → never uses `MESSAGE_TAG`.
- Graph policy/window error → safe log, no repeated retries, no SePay failure.
- Text command `/today` → calls the shared today builder.
- Send API payloads include `messaging_type` and use the configured Graph version.

Add a fake Graph client (mirror how Zalo send is faked in existing tests).

### 4.9 Deployment / external setup (document in `docs/wiki/`)
1. Create a Facebook App (type *Business*) + a Facebook Page.
2. Add the Messenger product; generate a **Page Access Token**.
3. Set the webhook callback URL `https://<host>/messenger/webhook`, the verify token, subscribe to `messages`; subscribe to `messaging_postbacks` only if button templates/postbacks are implemented.
4. Subscribe the app to the Page.
5. Bootstrap PSID safely:
   - Set token/secret/verify vars and `MESSENGER_DISCOVERY_MODE=true`.
   - Keep `MESSENGER_ENABLED=true` only for discovery, with no command processing.
   - Send a message to the Page.
   - Read the safe `[messenger-discovery] psid=...` log from Railway.
   - Set `MESSENGER_USER_PSID`, then set `MESSENGER_DISCOVERY_MODE=false`.
6. Set the Messenger Railway env vars; redeploy.
7. New wiki page: `docs/wiki/Messenger-Setup.md` (mirror `Zalo-Setup` / `SePay-Setup`).

### 4.10 Effort
~2–4 days: `messenger_api.py` + webhook + signature + discovery mode (~0.5–1d), read-only dispatcher (~0.5d), transaction picker state/queue + quick replies/fallback (~1d), text fan-out + tests + wiki (~0.5–1d). Risk is split between Meta setup/policy constraints and the cross-channel finalize race.

---

## 5. Suggested sequencing

0. **PR 0 — Meta policy spike (go/no-go, do this FIRST for Part B).** Time-boxed (~0.5–1d), no production code. Create a throwaway FB App + Page, add own account as Admin/Tester, and empirically answer: (a) Can the bot send the owner a message **outside** the 24h window in dev mode using `ACCOUNT_UPDATE`? (b) Does Meta accept that tag for a transaction-style notification without flagging? (c) Confirm Marketing Messages is unavailable for VN. Decide go/no-go on proactive transaction fan-out before any of PR 2–6. If no-go, Part B narrows to **user-initiated commands only** (`/report`, `/today`, `/accounts`, `/manage`, etc.) and the SePay auto-prompt is dropped on Messenger.
1. **PR 1 — `/recat <row>` (Telegram).** Tiny, ships value immediately, zero new infra. Independent of Part B / PR 0. *(Part A — includes the `handle_recategorize` month-consistency fix from §3.2.)*
2. **PR 2 — shared button/picker helpers.** Port/adapt Bot Finance's button-to-option map and transaction picker queue shape into public repo tests, without enabling Messenger yet.
3. **PR 3 — `messenger_api.py` + webhook verify/receive + signature + discovery mode.** Provable in isolation (handshake + signed POST logs PSID safely), no transaction behavior change.
4. **PR 4 — Messenger read-only command dispatcher** (`/today`, `/report`, `/accounts` first).
5. **PR 5a — Messenger inbound `/recat` + user-initiated picker only.** User can type `/recat <row>` on Messenger and complete the picker inside the active conversation. No SePay proactive send yet.
6. **PR 5b — conditional Messenger proactive SePay prompt.** Only if PR 0 green-lights it. Implement `MESSENGER_PROACTIVE_MODE`, 24h-window checks, optional tagged experiment path, safe policy-error handling, queue, and idempotent finalize.
7. **PR 6 — Messenger menu flows** (`/keywords`, `/manage`, `/allocate`) after the core command workflow is stable.
8. **PR 7 — optional Zalo `/recat` / Zalo transaction picker parity.**

Each PR keeps the channel behind its `*_ENABLED` flag, so nothing is exposed until configured — same safety model the repo already uses for Zalo.

---

## 6. Out of scope
- Multi-user / multi-PSID support (bot stays single-user, matching current Telegram/Zalo design).
- Messenger rich templates beyond quick replies / 3-button template.
- Broad proactive Messenger messaging beyond policy-compliant account/transaction updates.
- `/transfer` and `/cc` (separate roadmap items; stubs live in `handlers/experimental.py`).
- Discord channel and multi-currency (roadmap).

## 7. Open questions
1. Which Graph API version should be pinned after implementation verification? Default recommendation: configurable env, verified current stable version.
2. **Resolved by research (June 2026), confirm via PR 0 spike:** Outside-24h sends on Messenger use **message tags**, not WhatsApp-style templates. `ACCOUNT_UPDATE` is the only plausible fit but is defined for *non-recurring* changes → gray area for a recurring tx stream. **Marketing Messages** (the opt-in route, replaced Recurring Notifications on 2026-01-07) is unavailable in most countries incl. VN. Open decision: do we (a) rely on `ACCOUNT_UPDATE` and accept the policy risk, (b) require the user to keep an open 24h window (reactive only), or (c) ship Messenger as commands-only with no proactive tx prompt? Recommendation pending PR 0 result.
3. **App distribution:** Messenger needs App Review + Business Verification to message non-admins. Do we support Messenger only for the bot owner (dev mode, owner-as-admin), or invest in App Review so OSS adopters can use it? Recommendation: owner/dev-mode only in v1; document the App Review path as advanced/optional.
4. Quick replies (nicer, native) vs. pure numbered text (simpler, identical to Zalo) for the category picker — default recommendation: **quick replies with numbered-text fallback**.
5. Should `/recat` also land on Zalo in the first pass, or defer to the optional parity PR? Defer recommended.
6. Is a single shared `CHAT_ID`-style identity per channel acceptable, or do you want one unified user record? Current design = per-channel; keep it.
