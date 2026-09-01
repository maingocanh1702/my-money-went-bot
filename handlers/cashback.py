"""
handlers/cashback.py — /cashback command (credit-card cashback management).

Telegram inline + Zalo numbered-text, mirroring handlers/keywords.py.

Subcommands:
  /cashback                      → pick a credit card → rules + config + MCC count
  /cashback seed <template> [cc_id] → seed a card template (e.g. cake_freedom)
  /cashback templates            → list available templates
  /cashback recompute <cc_id> [cycle]
  (card menu buttons)            → Add rule · MCC map · Config · Recompute · Seed

The channel-agnostic core (seed_from_template / list_cashback_cards / recompute_cycle
/ card_overview_text) is unit-tested; the TG/Zalo glue is thin around it.
"""
from datetime import datetime
import pytz

from config import CHAT_ID, TIMEZONE
from config import ZALO_ENABLED, ZALO_CHAT_ID
import sheets as sh
import telegram_api as tg
import messenger
from i18n.core import t
from card_templates import list_templates, load_template


# ════════════════════════════════════════════════════════════════
# Channel-agnostic core
# ════════════════════════════════════════════════════════════════


def list_cashback_cards() -> list[dict]:
    """Active accounts eligible for cashback — credit cards only."""
    return [a for a in sh.get_active_accounts() if a.get("type") == "credit"]


def seed_from_template(account_id: str, template_name: str) -> dict:
    """Seed a card's cashback config from a YAML template (idempotent).

    Creates the card config, per-tx tiers, MCC rules, and the seed MCC-map
    patterns from the named template. Returns {"ok", "rules", "patterns",
    "tiers", "template"}. Safe to re-run — every write is idempotent
    (add_* dedupe; upsert merges; tiers seeded only when absent).
    """
    acc = sh.find_account_by_id(account_id)
    if not acc or acc.get("type") != "credit":
        return {"ok": False, "rules": 0, "patterns": 0, "tiers": 0, "template": template_name}

    try:
        tpl = load_template(template_name)
    except (FileNotFoundError, ValueError) as e:
        return {"ok": False, "rules": 0, "patterns": 0, "tiers": 0,
                "template": template_name, "error": str(e)}

    # Card-level config
    sh.upsert_card_config(
        account_id,
        cashback_rate=tpl.config.cashback_rate,
        min_eligible_spend=tpl.config.min_eligible_spend,
        cap_period=tpl.config.cap_period,
        alert_pct=tpl.config.alert_pct,
        active=True,
    )

    # Tiers (per tier_set, shared across cards) — seed once, batched.
    tier_count = 0
    if tpl.tier_set and tpl.tiers:
        if not sh.get_cashback_tiers(tpl.tier_set):
            ws = sh._ensure_cashback_tiers_tab()
            start = len(ws.get_all_values()) + 1
            rows = [
                [tpl.tier_set, t.tx_min, t.tx_max if t.tx_max is not None else "", t.per_tx_cap]
                for t in tpl.tiers
            ]
            ws.update(f"A{start}:D{start + len(rows) - 1}", rows)
            sh.invalidate_cashback_caches()
        tier_count = len(tpl.tiers)

    # Rules — rate from template rule (None → "" = inherit card-level rate)
    rules = sh.add_cashback_rules_bulk([
        {
            "account_id": account_id,
            "rule_name": r.name,
            "match_type": "mcc",
            "match_value": r.mcc,
            "rate": r.rate if r.rate is not None else "",
            "monthly_cap": r.monthly_cap,
            "per_tx_cap_tier": tpl.tier_set,
            "max_eligible_tx_per_day": r.daily_limit,
            "min_tx_amount": r.min_tx_amount,
            "stackable": r.stackable,
            "priority": r.priority,
            "notes": f"template:{template_name} emoji:{r.emoji}",
        }
        for r in tpl.rules
    ])

    # MCC Map patterns (global, shared across cards)
    pattern_specs = []
    for mcc, pats in tpl.patterns.items():
        rule = tpl.rule_by_mcc(mcc)
        label = rule.name if rule else f"MCC {mcc}"
        for p in pats:
            pattern_specs.append({"pattern": p, "mcc_code": mcc, "mcc_label": label})
    patterns = sh.add_mcc_maps_bulk(pattern_specs)

    return {"ok": True, "rules": rules, "patterns": patterns,
            "tiers": tier_count, "template": template_name}


# Legacy alias for backward compatibility
def seed_cake_card(account_id: str) -> dict:
    """Seed Cake Freedom template (legacy alias for seed_from_template)."""
    return seed_from_template(account_id, "cake_freedom")


def current_cycle(account_id: str) -> str:
    acc = sh.find_account_by_id(account_id)
    sd = acc.get("statement_day") if acc else None
    return sh.cycle_id(account_id, datetime.now(pytz.timezone(TIMEZONE)), sd)


def recompute_cycle(account_id: str, cycle: str | None = None) -> int:
    """Recompute cashback for every tx in a statement cycle. Returns rows touched.

    Finds the account's expense tx, groups by cycle, and rebuilds the target
    cycle via recompute_cashback_for_tx (which rebuilds the whole cycle from one
    representative row). Defaults to the current cycle.
    """
    cycle = cycle or current_cycle(account_id)
    # Accept the short month label users see (2026-06) as well as the internal
    # account-prefixed id (cake_cc_2026-06).
    if cycle and not cycle.startswith(f"{account_id}_"):
        cycle = f"{account_id}_{cycle}"
    acc = sh.find_account_by_id(account_id)
    sd = acc.get("statement_day") if acc else None
    try:
        ws = sh._sheet(sh.S.TRANSACTIONS)
    except Exception:
        return 0
    rows = ws.get_all_values()[1:]
    touched = 0
    rep_row = None
    for i, r in enumerate(rows):
        if (r[16] if len(r) > 16 else "").strip() != account_id:
            continue
        if ((r[17] if len(r) > 17 else "").strip() or "expense") != "expense":
            continue
        if sh.cycle_id(account_id, r[1] if len(r) > 1 else "", sd) != cycle:
            continue
        rep_row = i + 2
        touched += 1
    if rep_row is not None:
        sh.recompute_cashback_for_tx(rep_row)  # rebuilds the whole cycle
    return touched


def mcc_pattern_overview_text(account_id: str | None = None) -> str:
    """List MCC Map keyword patterns grouped by MCC code.

    The MCC Map is global (shared across cards), so every active pattern is
    listed. Labels prefer the card's own rule_name when `account_id` is given
    (falls back to the map's mcc_label, then `MCC <code>`). Patterns are stored
    normalized (lowercased, diacritics stripped) — uppercased here for display,
    matching the merchant-token style used when seeding. Emoji prefix mirrors
    the /report cashback section for visual consistency.
    """
    mcc_map = sh.get_mcc_map()
    if not mcc_map:
        return "🏷️ *MCC Map*\n\n_Chưa có pattern nào._ Seed template hoặc thêm thủ công."

    # Build emoji map from rules of the given card (dynamic, not hardcoded)
    emoji_by_mcc = _get_emoji_map(account_id) if account_id else {}

    by_mcc: dict[str, list[str]] = {}
    label_by_mcc: dict[str, str] = {}
    for m in mcc_map:
        code = str(m["mcc_code"]).strip()
        if not code:
            continue
        by_mcc.setdefault(code, []).append(str(m["pattern"]).upper())
        if m.get("mcc_label") and code not in label_by_mcc:
            label_by_mcc[code] = m["mcc_label"]
    if account_id:
        for r in sh.get_cashback_rules(account_id):
            label_by_mcc[r["match_value"]] = r["rule_name"]

    total = sum(len(v) for v in by_mcc.values())
    lines = [f"🏷️ *MCC Map* — {total} pattern · {len(by_mcc)} MCC"]
    for code in sorted(by_mcc):
        emoji = emoji_by_mcc.get(code, "🏷️")
        label = label_by_mcc.get(code, f"MCC {code}")
        pats = ", ".join(by_mcc[code])
        lines.append(f"{emoji} *{label}* ({code}): {pats}")
    return "\n".join(lines)


def card_overview_text(account_id: str) -> str:
    """Human-readable summary of a card's rules + config + current cycle snapshot."""
    acc = sh.find_account_by_id(account_id)
    name = acc.get("name") if acc else account_id
    cfg = sh.get_card_config(account_id)
    rules = sh.get_cashback_rules(account_id)
    mcc_codes = {r["match_value"] for r in rules}
    mcc_map = sh.get_mcc_map()
    pat_by_mcc: dict[str, int] = {}
    for m in mcc_map:
        pat_by_mcc[m["mcc_code"]] = pat_by_mcc.get(m["mcc_code"], 0) + 1

    lines = [t("cb.title", name=name)]
    if cfg:
        gate = sh.fmt_amount(cfg["min_eligible_spend"])
        status = t("cb.config_on") if cfg.get("active") else t("cb.config_off")
        lines.append(t("cb.config", rate=f"{cfg['cashback_rate']*100:.0f}",
                        gate=gate, status=status))
    else:
        lines.append(t("cb.no_config"))
    # Billing cycle: statement_day drives how tx are grouped into cycles.
    sd = acc.get("statement_day") if acc else None
    dd = acc.get("due_day") if acc else None
    if sd:
        due = t("cb.cycle_due", dd=dd) if dd else ""
        lines.append(t("cb.cycle_sd", sd=sd, due=due))
    else:
        lines.append(t("cb.cycle_none"))

    # Current cycle — unified breakdown: per-MCC cashback + totals + gate
    if cfg and cfg.get("active"):
        try:
            from handlers.report import _cashback_category_label
            cycle = current_cycle(account_id)
            ledger = [l for l in sh.get_cashback_ledger(account_id, cycle)
                      if l["status"] != "void"]
            cycle_label = cycle.split("_")[-1] if "_" in cycle else cycle

            # Per-MCC aggregates
            cb_by_mcc: dict[str, dict] = {}
            for l in ledger:
                mcc = l.get("mcc_code", "")
                if not mcc:
                    continue
                if mcc not in cb_by_mcc:
                    cb_by_mcc[mcc] = {"total": 0, "eligible": 0, "tx_count": 0}
                cb_by_mcc[mcc]["total"] += l["cashback_amount"]
                if l["status"] == "eligible":
                    cb_by_mcc[mcc]["eligible"] += l["cashback_amount"]
                cb_by_mcc[mcc]["tx_count"] += 1

            # ── Per-category breakdown (emoji labels + progress bars) ──
            if rules:
                lines.append(f"\n{t('cb.period_title', cycle=cycle_label)}")
                for r in rules:
                    mcc = r["match_value"]
                    label = _cashback_category_label(r["rule_name"], mcc)
                    mcc_data = cb_by_mcc.get(mcc)
                    earned = mcc_data["total"] if mcc_data else 0
                    tx_n = mcc_data["tx_count"] if mcc_data else 0
                    cap = r.get("monthly_cap") or 0
                    npat = pat_by_mcc.get(mcc, 0)
                    limit_tag = " · 1tx/d" if r["max_eligible_tx_per_day"] else ""
                    if cap > 0:
                        pct = min(100, round(earned / cap * 100))
                        lines.append(
                            f"{label}: {sh.fmt_amount(earned)}/{sh.fmt_amount(cap)} "
                            f"{sh.make_bar(pct, 8)} {pct}%"
                            f"{limit_tag}"
                        )
                    elif earned > 0:
                        lines.append(f"{label}: {sh.fmt_amount(earned)}{limit_tag}")
                    else:
                        lines.append(f"{label}: 0đ{limit_tag}")
                    if npat == 0:
                        lines.append(t("cb.pat_warn"))

            # ── Totals ──
            eligible_cb = sum(l["cashback_amount"] for l in ledger
                              if l["status"] == "eligible")
            pending_cb = sum(l["cashback_amount"] for l in ledger
                             if l["status"] == "pending")
            total_cb = eligible_cb + pending_cb
            lines.append(t("cb.separator"))
            lines.append(t("cb.sum_total", amount=sh.fmt_amount(total_cb))
                         + (t("cb.sum_eligible", amount=sh.fmt_amount(eligible_cb))
                            if eligible_cb > 0 and eligible_cb != total_cb else
                            " ✅" if eligible_cb == total_cb and total_cb > 0 else ""))

            # ── Gate progress ──
            min_spend = float(cfg.get("min_eligible_spend") or 0)
            if min_spend > 0:
                spent = sh.eligible_spend_in_cycle(account_id, cycle)
                pct = min(100, round(spent / min_spend * 100))
                lines.append(t("cb.gate_progress",
                               spent=sh.fmt_amount(spent),
                               gate=sh.fmt_amount(min_spend),
                               bar=sh.make_bar(pct, 8), pct=pct))
                if spent < min_spend:
                    lines.append(t("cb.gate_need_more", amount=sh.fmt_amount(min_spend - spent)))
                else:
                    lines.append(t("cb.gate_done"))
        except Exception:
            pass  # graceful fallback if ledger tab doesn't exist yet
    elif rules:
        # Cashback inactive — just list rules without cycle data
        lines.append("\n*Rules:*")
        for r in rules:
            mcc = r["match_value"]
            npat = pat_by_mcc.get(mcc, 0)
            warn = f" {t('cb.pat_warn').strip()}" if npat == 0 else f" · {npat} pattern"
            lines.append(f"• {r['rule_name']} (MCC {mcc}){warn}")

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
# Telegram flow
# ════════════════════════════════════════════════════════════════

async def start_cashback(text: str = ""):
    """Entry point: /cashback [seed|templates|setup|export|savetemplate|recompute] ..."""
    args = (text or "").split()[1:]  # drop "/cashback"
    if args and args[0] == "seed":
        await _tg_seed(args)
        return
    if args and args[0] == "templates":
        await _tg_list_templates()
        return
    if args and args[0] == "setup":
        await _tg_setup_start(args)
        return
    if args and args[0] == "export":
        await _tg_export(args)
        return
    if args and args[0] == "savetemplate":
        await _tg_savetemplate(args)
        return
    if args and args[0] == "recompute":
        await _tg_recompute(args)
        return
    await _tg_card_menu()


async def _tg_card_menu():
    cards = list_cashback_cards()
    if not cards:
        await tg.send_text(t("cb.no_cards"))
        return
    sh.set_state(CHAT_ID, {"step": "cashback"})
    buttons = [[{"text": f"💳 {c['name']}", "callback_data": f"cb_card_{c['id']}"}]
               for c in cards]
    await tg.send_with_buttons(t("cb.pick_card"), buttons)


async def _tg_card_view(account_id: str, message_id: int | None = None):
    msg = card_overview_text(account_id)
    buttons = [
        [{"text": "🌱 Seed Template", "callback_data": f"cb_tpl_{account_id}"},
         {"text": "🔄 Tính lại", "callback_data": f"cb_rcmp_{account_id}"}],
        [{"text": "📋 Quy tắc", "callback_data": f"cb_rules_{account_id}"},
         {"text": "🏷️ MCC", "callback_data": f"cb_mcc_{account_id}"},
         {"text": "⚙️ Cài đặt", "callback_data": f"cb_cfg_{account_id}"}],
        [{"text": "📅 Kỳ TT", "callback_data": f"cb_cyc_{account_id}"}],
        [{"text": "← Quay lại", "callback_data": "cb_back"}],
    ]
    if message_id:
        await tg.edit_message(message_id, msg)
        await tg.send_with_buttons(t("cb.choose"), buttons)
    else:
        await tg.send_with_buttons(msg, buttons)


async def _tg_list_templates():
    """List available card templates."""
    names = list_templates()
    if not names:
        await tg.send_text("Chưa có template nào.")
        return
    lines = ["📋 *Card Templates* — dùng `/cashback seed <template> [cc_id]`\n"]
    for name in names:
        try:
            tpl = load_template(name)
            lines.append(f"• `{name}` — {tpl.card_name} ({tpl.bank})")
            lines.append(f"  {tpl.description}")
        except Exception:
            lines.append(f"• `{name}` — ⚠️ lỗi load")
    await tg.send_text("\n".join(lines))


async def _tg_seed(args: list):
    # args: ["seed", template_name, maybe account_id]
    template_name = args[1] if len(args) > 1 else "cake_freedom"
    account_id = args[2] if len(args) > 2 else None
    if not account_id:
        cards = list_cashback_cards()
        if len(cards) == 1:
            account_id = cards[0]["id"]
        else:
            await tg.send_text(t("cb.seed_usage"))
            return
    res = seed_from_template(account_id, template_name)
    if not res["ok"]:
        err = res.get("error", "")
        if err:
            await tg.send_text(f"❌ Template `{template_name}`: {err}")
        else:
            await tg.send_text(t("cb.seed_not_credit", id=account_id))
        return
    await tg.send_text(t("cb.seeded", rules=res['rules'], patterns=res['patterns'],
                          tiers=res['tiers'], overview=card_overview_text(account_id)))


async def _tg_recompute(args: list):
    if len(args) < 2:
        await tg.send_text(t("cb.recompute_usage"))
        return
    account_id = args[1]
    cycle = args[2] if len(args) > 2 else None
    n = recompute_cycle(account_id, cycle)
    await tg.send_text(t("cb.recomputed", id=account_id, cycle=cycle or t("cb.recomputed_current"), n=n))


async def handle_cashback_callback(parts: list, message_id: int):
    """Route cb_* callbacks. account_id is rejoined from parts[2:] because the
    router splits callback_data on '_' and account ids contain '_' (cake_cc)."""
    if len(parts) < 2:
        return
    action = parts[1]

    # Interactive learning callbacks (cb_learn_yes/mcc/no) — route before
    # the generic account_id join since these use positional parts, not an id.
    if action == "learn":
        await handle_cashback_learn_callback(parts, message_id)
        return

    account_id = "_".join(parts[2:]) if len(parts) > 2 else ""
    if action == "back":
        await _tg_card_menu()
    elif action == "card":
        await _tg_card_view(account_id, message_id)
    elif action == "tpl":
        # Show template picker as inline buttons
        names = list_templates()
        buttons = [
            [{"text": f"🌱 {n}", "callback_data": f"cb_seedtpl_{account_id}_{n}"}]
            for n in names
        ]
        buttons.append([{"text": "← Quay lại", "callback_data": f"cb_card_{account_id}"}])
        await tg.edit_message(message_id, "Chọn template để seed:")
        await tg.send_with_buttons("Chọn template:", buttons)
    elif action == "seedtpl":
        # cb_seedtpl_{account_id}_{template_name} — rejoin rest after account_id
        # account_id and template_name are both in parts[2:]; template is the last part
        all_parts = "_".join(parts[2:])
        # Template name is always the last known template
        tpl_name = None
        for n in list_templates():
            if all_parts.endswith(f"_{n}"):
                tpl_name = n
                account_id = all_parts[:-(len(n) + 1)]
                break
        if not tpl_name:
            await tg.edit_message(message_id, "Template không hợp lệ.")
            return
        res = seed_from_template(account_id, tpl_name)
        if res["ok"]:
            await tg.edit_message(message_id,
                                 f"✅ Seeded `{tpl_name}`: {res['rules']} rule, {res['patterns']} pattern.")
        else:
            await tg.edit_message(message_id, f"❌ Seed thất bại: {res.get('error', 'unknown')}")
        await _tg_card_view(account_id)
    elif action == "seed":
        # Legacy: cb_seed_{account_id} → seed cake_freedom
        res = seed_from_template(account_id, "cake_freedom")
        await tg.edit_message(message_id, t("cb.seed_done", rules=res['rules'], patterns=res['patterns']))
        await _tg_card_view(account_id)
    elif action == "rcmp":
        n = recompute_cycle(account_id)
        await tg.edit_message(message_id, t("cb.recompute_btn", n=n))
        await _tg_card_view(account_id)
    elif action == "cfg":
        await _tg_config_prompt(account_id)
    elif action == "mcc":
        await _tg_mcc_prompt(account_id)
    elif action == "addr":
        await _tg_add_prompt(account_id)
    elif action == "cyc":
        await _tg_cycle_prompt(account_id)
    elif action == "sum":
        await _tg_cashback_summary(account_id)
    # Rule edit/delete. `account_id` here is the rejoined tail = rule_id for the
    # per-rule actions (rule ids contain '_', same as account ids).
    elif action == "rules":
        await _tg_rules_list(account_id)
    elif action == "rule":
        await _tg_rule_detail(account_id)
    elif action in ("rfn", "rfc", "rfm", "rfr"):
        field = {"rfn": "name", "rfc": "cap", "rfm": "max", "rfr": "rate"}[action]
        await _tg_rule_field_prompt(account_id, field)
    elif action == "rdel":
        await _tg_rule_delete_confirm(account_id)
    elif action == "rdok":
        await _tg_rule_delete_do(account_id)
    elif action == "setup":
        # cb_setup_pick_{account_id} → parts = ["cb", "setup", "pick", ...id_parts]
        sub_action = parts[2] if len(parts) > 2 else ""
        if sub_action == "pick":
            setup_account_id = "_".join(parts[3:])
            await _setup_begin(setup_account_id)
    elif action == "savetpl":
        # cb_savetpl_{account_id}
        tpl = _build_template_from_card(account_id)
        if tpl:
            saved = _save_template_to_disk(tpl)
            if saved:
                from card_templates import invalidate_cache
                invalidate_cache()
                await tg.send_text(
                    f"💾 *Đã lưu template* `{saved}`\n\n"
                    f"Dùng lại: `/cashback seed {saved}`"
                )
            else:
                await tg.send_text("❌ Validation failed.")
        else:
            await tg.send_text("❌ Thẻ chưa có cashback config.")


# ── Config wizard (rate / min_eligible_spend / alert_pct) ─────────
async def _tg_config_prompt(account_id: str):
    cfg = sh.get_card_config(account_id) or {}
    sh.set_state(CHAT_ID, {"step": "cb_cfg", "account_id": account_id})
    await tg.send_text(t("cb.cfg_prompt", id=account_id,
                         rate=f"{cfg.get('cashback_rate', 0)*100:.0f}",
                         gate=sh.fmt_amount(cfg.get('min_eligible_spend', 0)),
                         alert=f"{cfg.get('alert_pct', 0)*100:.0f}"))


async def handle_cashback_config_input(text: str, state: dict):
    parts = (text or "").split()
    if len(parts) < 3:
        await tg.send_text(t("cb.cfg_need_3"))
        return
    try:
        rate, min_spend, alert = float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        await tg.send_text(t("cb.cfg_invalid"))
        return
    if not (0 < rate <= 1):
        await tg.send_text(t("cb.cfg_rate_range"))
        return
    account_id = state.get("account_id")
    sh.upsert_card_config(account_id, cashback_rate=rate, min_eligible_spend=min_spend,
                          alert_pct=alert, active=True)
    sh.set_state(CHAT_ID, {"step": "cashback"})
    await tg.send_text(t("cb.cfg_updated", id=account_id))
    await _tg_card_view(account_id)


# ── Current-cycle cashback snapshot (💰 Đã hoàn) ──────────────────
async def _tg_cashback_summary(account_id: str):
    """On-demand version of the per-tx cashback notice: total + every
    category's accrued/cap + activation-gate progress, for the current cycle."""
    from handlers.report import render_cashback_tx_detail
    msg = render_cashback_tx_detail(account_id, current_cycle(account_id), "")
    await tg.send_text(msg or t("cb.no_cashback"))


# ── Billing cycle (statement / due day) ───────────────────────────
async def _tg_cycle_prompt(account_id: str):
    acc = sh.find_account_by_id(account_id) or {}
    sh.set_state(CHAT_ID, {"step": "cb_cycle", "account_id": account_id})
    sd, dd = acc.get("statement_day"), acc.get("due_day")
    cur = (f"statement day {sd}" + (t("cb.cycle_due", dd=dd) if dd else "")) if sd \
        else "calendar month"
    await tg.send_text(t("cb.cyc_title", id=account_id, current=cur))


async def handle_cashback_cycle_input(text: str, state: dict):
    parts = (text or "").split()
    if not parts:
        await tg.send_text(t("cb.cyc_need_input"))
        return
    try:
        sd = int(parts[0])
        dd = int(parts[1]) if len(parts) > 1 else None
    except ValueError:
        await tg.send_text(t("cb.cyc_not_number"))
        return
    if not 1 <= sd <= 28 or (dd is not None and not 1 <= dd <= 28):
        await tg.send_text(t("cb.cyc_range"))
        return
    account_id = state.get("account_id")
    if not sh.set_billing_cycle(account_id, sd, dd):
        await tg.send_text(t("cb.cyc_fail", id=account_id))
        return
    # Boundary moved → re-label cycles for this card so the ledger matches.
    n = recompute_cycle(account_id)
    sh.set_state(CHAT_ID, {"step": "cashback"})
    due = t("cb.cycle_due", dd=dd) if dd else ""
    await tg.send_text(t("cb.cyc_done", id=account_id, sd=sd, due=due, n=n))
    await _tg_card_view(account_id)


# ── MCC map (add pattern) ─────────────────────────────────────────
async def _tg_mcc_prompt(account_id: str):
    sh.set_state(CHAT_ID, {"step": "cb_mcc", "account_id": account_id})
    await tg.send_text(
        mcc_pattern_overview_text(account_id) + "\n\n"
        "➕ Thêm pattern: `<pattern> <mcc> [label]` (vd `WINMART 5411 Siêu thị`).\n"
        "Pattern là substring khớp mô tả giao dịch (không phân biệt hoa/thường)."
    )


async def handle_cashback_mcc_input(text: str, state: dict):
    parts = (text or "").split()
    if len(parts) < 2:
        await tg.send_text(t("cb.mcc_need_input"))
        return
    pattern, mcc = parts[0], parts[1]
    label = " ".join(parts[2:]) if len(parts) > 2 else ""
    ok = sh.add_mcc_map(pattern, mcc, label)
    sh.set_state(CHAT_ID, {"step": "cashback"})
    msg = (t("cb.mcc_added", pattern=pattern, mcc=mcc) if ok
           else t("cb.mcc_exists", pattern=pattern, mcc=mcc))
    await tg.send_text(msg)
    await _tg_card_view(state.get("account_id"))


# ── Rule edit/delete — channel-agnostic core ──────────────────────
# Shared by the Telegram inline-button flow and the Zalo numbered-text flow.
# The data mutations (sh.update_cashback_rule / sh.soft_delete_cashback_rule)
# and per-field validation live here so both channels behave identically.

_RULE_FIELD_PROMPT = {
    "name": "cb.rf_name",
    "cap":  "cb.rf_cap",
    "max":  "cb.rf_max",
    "rate": "cb.rf_rate",
}


def _find_rule(rule_id: str) -> dict | None:
    return next((r for r in sh.get_cashback_rules() if r["rule_id"] == rule_id), None)


def rule_detail_text(rule_id: str) -> str:
    """Plain-text summary of one rule (renders on both channels)."""
    r = _find_rule(rule_id)
    if not r:
        return ""
    rate = r["rate"]
    rate_txt = t("cb.rule_rate_inherit") if rate in (None, "") else f"{float(rate)*100:.0f}%"
    maxd = r["max_eligible_tx_per_day"]
    maxd_txt = t("cb.rule_maxd", n=maxd) if maxd else t("cb.rule_maxd_unlimited")
    return t("cb.rule_detail", name=r['rule_name'], mcc=r['match_value'],
             cap=sh.fmt_amount(r['monthly_cap'] or 0), maxd=maxd_txt, rate=rate_txt)


def apply_rule_field(rule_id: str, field: str, raw: str) -> tuple[bool, str]:
    """Validate + persist one edited field. Returns (ok, message). Pure logic
    around sh.update_cashback_rule so TG/Zalo glue only collects text."""
    r = _find_rule(rule_id)
    if not r:
        return False, t("cb.rv_not_found")
    raw = (raw or "").strip()
    if field == "name":
        if not 1 <= len(raw) <= 40:
            return False, t("cb.rv_name_len")
        sh.update_cashback_rule(rule_id, rule_name=raw)
        return True, t("cb.rv_name_ok", name=raw)
    if field == "cap":
        from utils import parse_budget_amount
        cap = parse_budget_amount(raw)
        if cap is None:
            return False, t("cb.rv_cap_nan")
        sh.update_cashback_rule(rule_id, monthly_cap=cap)
        return True, t("cb.rv_cap_ok", amount=sh.fmt_amount(cap))
    if field == "max":
        if not raw.isdigit():
            return False, t("cb.rv_max_nan")
        n = int(raw)
        sh.update_cashback_rule(rule_id, max_eligible_tx_per_day=n)
        return True, t("cb.rv_max_ok", value=n if n else t("cb.rule_maxd_unlimited"))
    if field == "rate":
        if raw in ("", "-", "kế thừa", "ke thua", "inherit"):
            sh.update_cashback_rule(rule_id, rate="")
            return True, t("cb.rv_rate_inherit_ok")
        try:
            rate = float(raw)
        except ValueError:
            return False, t("cb.rv_rate_nan")
        if not 0 < rate <= 1:
            return False, t("cb.rv_rate_range")
        sh.update_cashback_rule(rule_id, rate=rate)
        return True, t("cb.rv_rate_ok", pct=f"{rate*100:.0f}")
    return False, t("cb.rv_bad_field")


def delete_rule(rule_id: str) -> bool:
    """Soft-delete (active=FALSE). Reversible by re-adding the same rule_id."""
    return sh.soft_delete_cashback_rule(rule_id)


# ── Rule edit/delete — Telegram inline UI ─────────────────────────
async def _tg_rules_list(account_id: str):
    rules = sh.get_cashback_rules(account_id)
    if not rules:
        await tg.send_text(t("cb.rules_empty"))
    buttons = [[{"text": f"{r['rule_name']} (MCC {r['match_value']})",
                 "callback_data": f"cb_rule_{r['rule_id']}"}] for r in rules]
    buttons.append([{"text": "➕ Thêm rule", "callback_data": f"cb_addr_{account_id}"}])
    buttons.append([{"text": t("btn.back"), "callback_data": f"cb_card_{account_id}"}])
    await tg.send_with_buttons(t("cb.rules_title"), buttons)


async def _tg_rule_detail(rule_id: str):
    r = _find_rule(rule_id)
    if not r:
        await tg.send_text(t("cb.rule_not_found"))
        return
    buttons = [
        [{"text": "✏️ Tên", "callback_data": f"cb_rfn_{rule_id}"},
         {"text": "💰 Cap", "callback_data": f"cb_rfc_{rule_id}"}],
        [{"text": "🔢 Max tx/ngày", "callback_data": f"cb_rfm_{rule_id}"},
         {"text": "％ Rate", "callback_data": f"cb_rfr_{rule_id}"}],
        [{"text": "🗑️ Xoá", "callback_data": f"cb_rdel_{rule_id}"}],
        [{"text": "← Quy tắc", "callback_data": f"cb_rules_{r['account_id']}"}],
    ]
    await tg.send_with_buttons(rule_detail_text(rule_id), buttons)


async def _tg_rule_field_prompt(rule_id: str, field: str):
    if not _find_rule(rule_id):
        await tg.send_text(t("cb.rule_not_exist"))
        return
    sh.set_state(CHAT_ID, {"step": "cb_redit", "rule_id": rule_id, "field": field})
    await tg.send_text(f"✏️ {t(_RULE_FIELD_PROMPT[field])}")


async def handle_cashback_rule_edit_input(text: str, state: dict):
    rule_id, field = state.get("rule_id"), state.get("field")
    ok, msg = apply_rule_field(rule_id, field, text)
    await tg.send_text(msg)
    if ok:                                   # on error keep state so user retries
        sh.set_state(CHAT_ID, {"step": "cashback"})
        await _tg_rule_detail(rule_id)


async def _tg_rule_delete_confirm(rule_id: str):
    r = _find_rule(rule_id)
    if not r:
        await tg.send_text("⚠️ Rule không tồn tại.")
        return
    buttons = [[
        {"text": "🗑️ Xác nhận xoá", "callback_data": f"cb_rdok_{rule_id}"},
        {"text": "Huỷ", "callback_data": f"cb_rule_{rule_id}"},
    ]]
    await tg.send_with_buttons(
        t("cb.rule_delete_confirm", rid=f"{r['rule_name']} (MCC {r['match_value']})"), buttons)


async def _tg_rule_delete_do(rule_id: str):
    r = _find_rule(rule_id)
    account_id = r["account_id"] if r else ""
    ok = delete_rule(rule_id)
    await tg.send_text(t("cb.rule_deleted") if ok else t("cb.rule_delete_fail"))
    if account_id:
        await _tg_rules_list(account_id)


# ── Add rule wizard ───────────────────────────────────────────────
async def _tg_add_prompt(account_id: str):
    sh.set_state(CHAT_ID, {"step": "cb_addr", "account_id": account_id})
    await tg.send_text(t("cb.add_rule_prompt"))


async def handle_cashback_add_input(text: str, state: dict):
    parts = (text or "").split()
    if len(parts) < 4:
        await tg.send_text(t("cb.add_rule_need"))
        return
    mcc, name = parts[0], parts[1].replace("_", " ")
    try:
        cap, max_day = float(parts[2]), int(parts[3])
    except ValueError:
        await tg.send_text(t("cb.add_rule_invalid"))
        return
    account_id = state.get("account_id")
    # Inherit tier_set from card's existing rules (if any), otherwise empty
    existing_rules = sh.get_cashback_rules(account_id)
    tier_set = existing_rules[0]["per_tx_cap_tier"] if existing_rules else ""
    rid = sh.add_cashback_rule(account_id, name, "mcc", mcc, rate="", monthly_cap=cap,
                               per_tx_cap_tier=tier_set, max_eligible_tx_per_day=max_day)
    sh.set_state(CHAT_ID, {"step": "cashback"})
    await tg.send_text(t("cb.add_rule_done", rid=rid, mcc=mcc))
    await _tg_card_view(account_id)


# ── Setup wizard (custom card, no template) ──────────────────────────────
# Steps: pick_card → rate → cap_per_mcc → gate → cap_period → add_mccs (loop) → done

_SETUP_STEPS = [
    "cb_setup_rate",      # "Rate hoàn tiền mặc định? (VD: 0.05 = 5%)"
    "cb_setup_cap",       # "Cap mỗi MCC/kỳ? (VD: 200000)"
    "cb_setup_gate",      # "Cổng kích hoạt (chi tiêu tối thiểu/kỳ)? 0 = không có"
    "cb_setup_period",    # "Kỳ cap: statement_cycle / calendar_month"
    "cb_setup_mcc",       # "Thêm MCC: <code> <tên> [rate] [daily_limit]. Gõ 'done' khi xong"
]

_SETUP_PROMPTS = {
    "cb_setup_rate":   "💰 Rate hoàn tiền mặc định? (VD: `0.05` = 5%, `0.20` = 20%)",
    "cb_setup_cap":    "📊 Cap mỗi MCC/kỳ? (VD: `200000` = 200kđ)",
    "cb_setup_gate":   "🚧 Cổng kích hoạt (chi tiêu tối thiểu/kỳ để được hoàn)?\nGõ `0` nếu không có.",
    "cb_setup_period":  "📆 Kỳ tính cap:\n`1` = Statement cycle (kỳ sao kê)\n`2` = Calendar month (tháng dương lịch)",
    "cb_setup_mcc":    ("➕ Thêm MCC rule. Gõ theo format:\n"
                        "`<mcc_code> <tên> [rate] [daily_limit]`\n\n"
                        "VD: `5411 Siêu_thị 0.02 1`\n"
                        "VD: `5262 TMDT` (rate kế thừa, không giới hạn)\n\n"
                        "Gõ `done` khi xong."),
}


async def _tg_setup_start(args: list):
    """Start the setup wizard: /cashback setup [cc_id]."""
    account_id = args[1] if len(args) > 1 else None
    if not account_id:
        cards = list_cashback_cards()
        if len(cards) == 1:
            account_id = cards[0]["id"]
        elif not cards:
            await tg.send_text("Chưa có thẻ tín dụng. Dùng /accounts để thêm.")
            return
        else:
            buttons = [[{"text": f"💳 {c['name']}", "callback_data": f"cb_setup_pick_{c['id']}"}]
                       for c in cards]
            await tg.send_with_buttons("🔧 Chọn thẻ để setup cashback:", buttons)
            return
    await _setup_begin(account_id)


async def _setup_begin(account_id: str):
    """Initialize wizard state and ask first question."""
    sh.set_state(CHAT_ID, {
        "step": "cb_setup_rate",
        "account_id": account_id,
        "setup": {},  # accumulates: rate, cap, gate, period, rules[]
    })
    acc = sh.find_account_by_id(account_id)
    name = acc.get("name", account_id) if acc else account_id
    await tg.send_text(
        f"🔧 *Setup cashback cho {name}*\n\n" + _SETUP_PROMPTS["cb_setup_rate"]
    )


async def handle_cashback_setup_input(text: str, state: dict):
    """Handle text input for setup wizard (dispatched by main.py via step name)."""
    step = state.get("step", "")
    account_id = state.get("account_id")
    setup = state.get("setup", {})
    raw = (text or "").strip()

    if step == "cb_setup_rate":
        try:
            rate = float(raw)
            if not 0 < rate <= 1:
                raise ValueError
        except ValueError:
            await tg.send_text("❌ Rate phải là số 0-1 (VD: 0.05 = 5%). Thử lại:")
            return
        setup["rate"] = rate
        sh.set_state(CHAT_ID, {"step": "cb_setup_cap", "account_id": account_id, "setup": setup})
        await tg.send_text(_SETUP_PROMPTS["cb_setup_cap"])

    elif step == "cb_setup_cap":
        try:
            cap = float(raw)
            if cap < 0:
                raise ValueError
        except ValueError:
            await tg.send_text("❌ Cap phải là số ≥ 0. Thử lại:")
            return
        setup["cap"] = cap
        sh.set_state(CHAT_ID, {"step": "cb_setup_gate", "account_id": account_id, "setup": setup})
        await tg.send_text(_SETUP_PROMPTS["cb_setup_gate"])

    elif step == "cb_setup_gate":
        try:
            gate = float(raw)
            if gate < 0:
                raise ValueError
        except ValueError:
            await tg.send_text("❌ Gate phải là số ≥ 0. Thử lại:")
            return
        setup["gate"] = gate
        sh.set_state(CHAT_ID, {"step": "cb_setup_period", "account_id": account_id, "setup": setup})
        await tg.send_text(_SETUP_PROMPTS["cb_setup_period"])

    elif step == "cb_setup_period":
        if raw == "1":
            setup["period"] = "statement_cycle"
        elif raw == "2":
            setup["period"] = "calendar_month"
        else:
            await tg.send_text("❌ Gõ `1` hoặc `2`. Thử lại:")
            return
        setup["rules"] = []
        sh.set_state(CHAT_ID, {"step": "cb_setup_mcc", "account_id": account_id, "setup": setup})
        await tg.send_text(_SETUP_PROMPTS["cb_setup_mcc"])

    elif step == "cb_setup_mcc":
        if raw.lower() == "done":
            await _setup_finish(account_id, setup)
            return
        # Parse: <mcc> <name> [rate] [daily_limit]
        parts = raw.split()
        if len(parts) < 2:
            await tg.send_text("❌ Cần ít nhất: `<mcc> <tên>`. Thử lại:")
            return
        mcc_code = parts[0]
        mcc_name = parts[1].replace("_", " ")
        rule_rate = None
        daily_limit = 0
        if len(parts) >= 3:
            try:
                rule_rate = float(parts[2])
            except ValueError:
                pass
        if len(parts) >= 4:
            try:
                daily_limit = int(parts[3])
            except ValueError:
                pass
        setup["rules"].append({
            "mcc": mcc_code,
            "name": mcc_name,
            "rate": rule_rate,
            "daily_limit": daily_limit,
        })
        sh.set_state(CHAT_ID, {"step": "cb_setup_mcc", "account_id": account_id, "setup": setup})
        count = len(setup["rules"])
        await tg.send_text(
            f"✅ Đã thêm MCC {mcc_code} ({mcc_name}). Tổng: {count} rule.\n"
            f"Tiếp tục thêm hoặc gõ `done` để hoàn tất."
        )


async def _setup_finish(account_id: str, setup: dict):
    """Apply the wizard's collected config to the card."""
    rate = setup.get("rate", 0.01)
    cap = setup.get("cap", 0)
    gate = setup.get("gate", 0)
    period = setup.get("period", "statement_cycle")
    rules = setup.get("rules", [])

    if not rules:
        await tg.send_text("❌ Chưa thêm MCC nào. Dùng `/cashback setup` lại.")
        sh.set_state(CHAT_ID, {"step": None})
        return

    # Apply config
    sh.upsert_card_config(
        account_id,
        cashback_rate=rate,
        min_eligible_spend=gate,
        cap_period=period,
        alert_pct=0.80,
        active=True,
    )

    # Apply rules
    rule_specs = []
    for r in rules:
        rule_specs.append({
            "account_id": account_id,
            "rule_name": r["name"],
            "match_type": "mcc",
            "match_value": r["mcc"],
            "rate": r["rate"] if r["rate"] is not None else "",
            "monthly_cap": cap,
            "per_tx_cap_tier": "",
            "max_eligible_tx_per_day": r["daily_limit"],
            "notes": f"setup:wizard emoji:🏷️",
        })
    written = sh.add_cashback_rules_bulk(rule_specs)

    sh.set_state(CHAT_ID, {"step": None})

    summary = (
        f"✅ *Setup hoàn tất!*\n\n"
        f"💰 Rate: {rate*100:.0f}%\n"
        f"📊 Cap/MCC/kỳ: {sh.fmt_amount(cap)}\n"
        f"🚧 Cổng: {sh.fmt_amount(gate)}\n"
        f"📆 Kỳ: {period}\n"
        f"📋 Rules: {written}\n"
    )
    await tg.send_text(summary)

    # Auto-save as reusable template
    tpl = _build_template_from_card(account_id)
    if tpl:
        saved_path = _save_template_to_disk(tpl)
        if saved_path:
            from card_templates import invalidate_cache
            invalidate_cache()
            await tg.send_text(
                f"💾 Đã lưu template `{tpl.card_id}` → có thể dùng lại với:\n"
                f"`/cashback seed {tpl.card_id}`"
            )

    await _tg_card_view(account_id)


# ── Export ─────────────────────────────────────────────────────────

async def _tg_export(args: list):
    """Export a card's cashback config as a YAML template: /cashback export [cc_id]."""
    account_id = args[1] if len(args) > 1 else None
    if not account_id:
        cards = list_cashback_cards()
        if len(cards) == 1:
            account_id = cards[0]["id"]
        else:
            await tg.send_text("Dùng: `/cashback export <cc_id>`")
            return
    tpl = _build_template_from_card(account_id)
    if not tpl:
        await tg.send_text(f"❌ Thẻ `{account_id}` chưa có cashback config.")
        return
    from card_templates import export_template
    yaml_str = export_template(tpl)

    # Also save to disk
    saved_path = _save_template_to_disk(tpl)
    save_msg = ""
    if saved_path:
        from card_templates import invalidate_cache
        invalidate_cache()
        save_msg = f"\n💾 Đã lưu: `{saved_path}`\n"

    await tg.send_text(
        f"📤 *Export cashback config* — `{account_id}`\n"
        f"{save_msg}\n"
        f"```yaml\n{yaml_str}```"
    )


def _build_template_from_card(account_id: str):
    """Build a CardTemplate from a card's current Google Sheets data."""
    from card_templates.schema import CardConfig, CardTemplate, RuleConfig, TierConfig
    cfg = sh.get_card_config(account_id)
    if not cfg or not cfg.get("active"):
        return None
    rules_data = sh.get_cashback_rules(account_id)
    if not rules_data:
        return None

    # Card config
    config = CardConfig(
        cashback_rate=float(cfg.get("cashback_rate", 0) or 0),
        min_eligible_spend=float(cfg.get("min_eligible_spend", 0) or 0),
        cap_period=cfg.get("cap_period", "statement_cycle"),
        alert_pct=float(cfg.get("alert_pct", 0.80) or 0.80),
    )

    # Tiers
    tier_set = ""
    tiers = []
    if rules_data and rules_data[0].get("per_tx_cap_tier"):
        tier_set = rules_data[0]["per_tx_cap_tier"]
        tiers_data = sh.get_cashback_tiers(tier_set)
        tiers = [
            TierConfig(
                tx_min=float(t.get("tx_min", 0) or 0),
                tx_max=float(t["tx_max"]) if t.get("tx_max") not in (None, "", "0") else None,
                per_tx_cap=float(t.get("per_tx_cap", 0) or 0),
            )
            for t in tiers_data
        ]

    # Rules
    rules = []
    for r in rules_data:
        emoji = _emoji_from_notes(r.get("notes", ""))
        rate_val = r.get("rate")
        rate = float(rate_val) if rate_val not in (None, "", 0, "0") else None
        rules.append(RuleConfig(
            mcc=r["match_value"],
            name=r["rule_name"],
            emoji=emoji,
            monthly_cap=float(r.get("monthly_cap", 0) or 0),
            daily_limit=int(r.get("max_eligible_tx_per_day", 0) or 0),
            rate=rate,
        ))

    # Patterns from MCC Map
    mcc_map = sh.get_mcc_map()
    patterns: dict[str, list[str]] = {}
    rule_mccs = {r.mcc for r in rules}
    for m in mcc_map:
        code = str(m.get("mcc_code", "")).strip()
        if code in rule_mccs:
            patterns.setdefault(code, []).append(m.get("pattern", ""))

    acc = sh.find_account_by_id(account_id)
    card_name = acc.get("name", account_id) if acc else account_id

    return CardTemplate(
        card_id=account_id.replace(" ", "_").lower(),
        card_name=card_name,
        bank="",
        version=datetime.now().strftime("%Y.%m"),
        description=f"Exported from {card_name}",
        config=config,
        tier_set=tier_set,
        tiers=tiers,
        rules=rules,
        patterns=patterns,
    )


def _save_template_to_disk(tpl, template_name: str | None = None) -> str | None:
    """Write a CardTemplate to a YAML file in card_templates/ directory.

    Returns the filename on success, None on failure.
    """
    import os
    from card_templates import export_template, validate_template
    from pathlib import Path

    errors = validate_template(tpl)
    if errors:
        print(f"[cashback] template validation failed: {errors}")
        return None

    name = template_name or tpl.card_id
    # Sanitize filename
    name = name.replace(" ", "_").replace("/", "_").lower().strip("_")
    if not name:
        return None

    templates_dir = Path(__file__).parent.parent / "card_templates"
    yaml_str = export_template(tpl)
    filepath = templates_dir / f"{name}.yaml"
    try:
        filepath.write_text(yaml_str, encoding="utf-8")
        print(f"[cashback] saved template: {filepath}")
        return name
    except OSError as e:
        print(f"[cashback] failed to save template: {e}")
        return None


async def _tg_savetemplate(args: list):
    """Save a card's config as a reusable template: /cashback savetemplate [cc_id] [name]."""
    account_id = args[1] if len(args) > 1 else None
    template_name = args[2] if len(args) > 2 else None

    if not account_id:
        cards = list_cashback_cards()
        if len(cards) == 1:
            account_id = cards[0]["id"]
        elif not cards:
            await tg.send_text("Chưa có thẻ tín dụng nào.")
            return
        else:
            buttons = [[{"text": f"💳 {c['name']}", "callback_data": f"cb_savetpl_{c['id']}"}]
                       for c in cards]
            await tg.send_with_buttons("💾 Chọn thẻ để lưu template:", buttons)
            return

    tpl = _build_template_from_card(account_id)
    if not tpl:
        await tg.send_text(f"❌ Thẻ `{account_id}` chưa có cashback config.")
        return

    saved = _save_template_to_disk(tpl, template_name)
    if saved:
        from card_templates import invalidate_cache
        invalidate_cache()
        await tg.send_text(
            f"💾 *Đã lưu template* `{saved}`\n\n"
            f"Dùng lại: `/cashback seed {saved}`\n"
            f"Xem tất cả: `/cashback templates`"
        )
    else:
        await tg.send_text("❌ Không thể lưu template (validation failed).")


# ════════════════════════════════════════════════════════════════
# Zalo flow (numbered text)
# ════════════════════════════════════════════════════════════════

async def _zalo_send(chat_id: str, text: str):
    await messenger.send_text(text, channel="zalo", recipient_id=chat_id)


async def zalo_start_cashback(chat_id: str, text: str, zalo_state_key: str):
    args = (text or "").split()[1:]
    if args and args[0] == "seed":
        template_name = args[1] if len(args) > 1 else "cake_freedom"
        account_id = args[2] if len(args) > 2 else None
        cards = list_cashback_cards()
        if not account_id and len(cards) == 1:
            account_id = cards[0]["id"]
        if not account_id:
            await _zalo_send(chat_id, "Dùng: /cashback seed <template> <cc_id>")
            return
        res = seed_from_template(account_id, template_name)
        if not res["ok"]:
            err = res.get("error", f"{account_id} không phải thẻ tín dụng.")
            await _zalo_send(chat_id, f"Lỗi: {err}")
            return
        await _zalo_send(chat_id, f"Seeded {template_name} → {account_id}: "
                         f"{res['rules']} rule, {res['patterns']} pattern.\n\n"
                         + _plain(card_overview_text(account_id)))
        return
    if args and args[0] == "recompute" and len(args) >= 2:
        n = recompute_cycle(args[1], args[2] if len(args) > 2 else None)
        await _zalo_send(chat_id, f"Recompute {args[1]}: {n} giao dịch.")
        return
    cards = list_cashback_cards()
    if not cards:
        await _zalo_send(chat_id, "Chưa có thẻ tín dụng. Dùng /accounts để thêm thẻ credit.")
        return
    lines = ["Cashback — chọn thẻ (gõ số):"]
    for i, c in enumerate(cards, 1):
        lines.append(f"{i}. {c['name']}")
    sh.set_state(zalo_state_key, {"step": "zalo_cashback_pick", "cards": [c["id"] for c in cards]})
    await _zalo_send(chat_id, "\n".join(lines))


async def zalo_handle_pick(chat_id: str, text: str, state: dict, zalo_state_key: str):
    cards = state.get("cards") or []
    try:
        idx = int(text.strip()) - 1
    except ValueError:
        idx = -1
    if not (0 <= idx < len(cards)):  # reject 0/negative/out-of-range (no wrap)
        await _zalo_send(chat_id, "Số không hợp lệ. /cashback để thử lại.")
        return
    account_id = cards[idx]
    sh.set_state(zalo_state_key, {"step": "zalo_cashback_menu", "account_id": account_id})
    tpl_names = ", ".join(list_templates())
    await _zalo_send(
        chat_id,
        _plain(card_overview_text(account_id)) +
        f"\n\nGõ: 1=Seed template · 2=Recompute kỳ này · 3=Xem cashback kỳ này · 4=Sửa/xoá rule"
        f"\nTemplates: {tpl_names}"
        "\n(Thêm rule mới, MCC, config: dùng /cashback trên Telegram.)"
    )


async def zalo_handle_menu(chat_id: str, text: str, state: dict, zalo_state_key: str):
    account_id = state.get("account_id")
    choice = text.strip()
    if choice == "1":
        # Default to cake_freedom for backward compat; user can use /cashback seed <name> for others
        res = seed_from_template(account_id, "cake_freedom")
        await _zalo_send(chat_id, f"Seeded cake_freedom: {res['rules']} rule, {res['patterns']} pattern.")
    elif choice == "2":
        n = recompute_cycle(account_id)
        await _zalo_send(chat_id, f"Recompute kỳ hiện tại: {n} giao dịch.")
    elif choice == "3":
        from handlers.report import render_cashback_tx_detail
        msg = render_cashback_tx_detail(account_id, current_cycle(account_id), "")
        await _zalo_send(chat_id, _plain(msg) if msg else "Thẻ này chưa cấu hình cashback.")
        return  # keep the menu open so they can pick again
    elif choice == "4":
        rules = sh.get_cashback_rules(account_id)
        if not rules:
            await _zalo_send(chat_id, "Chưa có rule nào. Dùng /cashback trên Telegram để thêm.")
            return
        lines = ["Chọn rule để sửa/xoá (gõ số):"]
        for i, r in enumerate(rules, 1):
            lines.append(f"{i}. {r['rule_name']} (MCC {r['match_value']})")
        sh.set_state(zalo_state_key, {"step": "zalo_cashback_rule_pick",
                                      "account_id": account_id,
                                      "rule_ids": [r["rule_id"] for r in rules]})
        await _zalo_send(chat_id, "\n".join(lines))
        return
    else:
        await _zalo_send(chat_id, "Gõ 1, 2, 3 hoặc 4, hoặc /cashback để thoát.")
        return
    sh.set_state(zalo_state_key, {"step": None})


async def zalo_handle_rule_pick(chat_id: str, text: str, state: dict, zalo_state_key: str):
    rids = state.get("rule_ids") or []
    try:
        idx = int(text.strip()) - 1
    except ValueError:
        idx = -1
    if not (0 <= idx < len(rids)):
        await _zalo_send(chat_id, "Số không hợp lệ. /cashback để thử lại.")
        return
    rid = rids[idx]
    sh.set_state(zalo_state_key, {"step": "zalo_cashback_rule_menu",
                                  "account_id": state.get("account_id"), "rule_id": rid})
    await _zalo_send(chat_id, _plain(rule_detail_text(rid)) +
                     "\n\nGõ: 1=tên · 2=cap · 3=max tx/ngày · 4=rate · 5=xoá")


async def zalo_handle_rule_menu(chat_id: str, text: str, state: dict, zalo_state_key: str):
    rid = state.get("rule_id")
    field_map = {"1": "name", "2": "cap", "3": "max", "4": "rate"}
    choice = text.strip()
    if choice in field_map:
        sh.set_state(zalo_state_key, {**state, "step": "zalo_cashback_rule_edit",
                                      "field": field_map[choice]})
        # t(...) — _RULE_FIELD_PROMPT holds i18n KEYS; sending the raw key
        # used to show the user literally "cb.rf_name".
        await _zalo_send(chat_id, _plain(t(_RULE_FIELD_PROMPT[field_map[choice]])))
    elif choice == "5":
        r = _find_rule(rid)
        sh.set_state(zalo_state_key, {**state, "step": "zalo_cashback_rule_delconfirm"})
        await _zalo_send(chat_id, f"Xoá rule {r['rule_name'] if r else rid}? "
                         "Gõ 'xoa' để xác nhận, gì khác để huỷ.")
    else:
        await _zalo_send(chat_id, "Gõ 1–5, hoặc /cashback để thoát.")


async def zalo_handle_rule_edit(chat_id: str, text: str, state: dict, zalo_state_key: str):
    rid, field = state.get("rule_id"), state.get("field")
    ok, msg = apply_rule_field(rid, field, text)
    await _zalo_send(chat_id, _plain(msg))
    if ok:                                   # back to the rule menu; else retry
        sh.set_state(zalo_state_key, {"step": "zalo_cashback_rule_menu",
                                      "account_id": state.get("account_id"), "rule_id": rid})
        await _zalo_send(chat_id, _plain(rule_detail_text(rid)) +
                         "\n\nGõ: 1=tên · 2=cap · 3=max tx/ngày · 4=rate · 5=xoá")


async def zalo_handle_rule_delconfirm(chat_id: str, text: str, state: dict, zalo_state_key: str):
    rid = state.get("rule_id")
    if text.strip().lower() in ("xoa", "xóa", "y", "yes", "co", "có"):
        delete_rule(rid)
        await _zalo_send(chat_id, "Đã xoá rule.")
    else:
        await _zalo_send(chat_id, "Đã huỷ, không xoá.")
    sh.set_state(zalo_state_key, {"step": None})


def _plain(md: str) -> str:
    """Strip Telegram markdown markers for Zalo plain text."""
    return md.replace("*", "").replace("`", "")


# ════════════════════════════════════════════════════════════════
# Dynamic MCC helpers (replaces hardcoded _MCC_CHOICES / emoji map)
# ════════════════════════════════════════════════════════════════

def _get_mcc_choices(account_id: str | None = None) -> list[tuple[str, str]]:
    """Build MCC picker choices dynamically from the card's cashback rules.

    Falls back to all known rules if account_id is None. Returns
    [(mcc_code, "emoji name"), ...].
    """
    rules = sh.get_cashback_rules(account_id)
    if not rules:
        # Fallback: aggregate from all rules across all cards
        rules = sh.get_cashback_rules()
    seen = set()
    choices = []
    for r in rules:
        mcc = r["match_value"]
        if mcc in seen:
            continue
        seen.add(mcc)
        emoji = _emoji_from_notes(r.get("notes", ""))
        choices.append((mcc, f"{emoji} {r['rule_name']}"))
    return choices


def _get_emoji_map(account_id: str | None = None) -> dict[str, str]:
    """Build MCC code → emoji map from the card's rules."""
    rules = sh.get_cashback_rules(account_id) if account_id else sh.get_cashback_rules()
    return {r["match_value"]: _emoji_from_notes(r.get("notes", "")) for r in rules}


def _emoji_from_notes(notes: str) -> str:
    """Extract emoji from rule notes field (format: 'template:xxx emoji:🛒')."""
    if not notes:
        return "🏷️"
    for part in notes.split():
        if part.startswith("emoji:"):
            return part[6:] or "🏷️"
    return "🏷️"


# ════════════════════════════════════════════════════════════════
# Interactive cashback learning (unknown MCC)
# ════════════════════════════════════════════════════════════════
# Called from sepay._ask_cashback_learn via callback routing in main.py.
# Flow: cb_learn_yes → MCC picker → cb_learn_mcc → add pattern + recompute
#       cb_learn_no → add exclusion


async def handle_cashback_learn_callback(parts: list[str], message_id: int):
    """Route cb_learn_* callbacks from the unknown-MCC question.

    Callback patterns:
      cb_learn_yes_{row_num}           → show MCC picker
      cb_learn_mcc_{row_num}_{mcc}     → add pattern + recompute
      cb_learn_no_{row_num}            → add exclusion
      cb_learn_wrong_{row_num}         → void cashback + add specific exclusion
    """
    if len(parts) < 4:
        return

    action = parts[2]  # "mcc" / "no" / "wrong"

    if action == "mcc" and len(parts) >= 5:
        row_num = int(parts[3])
        mcc_code = parts[4]
        await _learn_apply_mcc(row_num, mcc_code, message_id)

    elif action == "no":
        row_num = int(parts[3])
        await _learn_exclude(row_num, message_id)

    elif action == "wrong":
        row_num = int(parts[3])
        await _learn_wrong(row_num, message_id)


async def _learn_apply_mcc(row_num: int, mcc_code: str, message_id: int):
    """User picked an MCC → extract keyword, add to MCC Map, recompute cashback."""
    try:
        tx_row = sh.get_transaction_row(row_num)
        description = tx_row[5] if len(tx_row) > 5 else ""
        amount = sh._parse_amount(tx_row[7]) if len(tx_row) > 7 else 0

        keyword = sh.extract_keyword_from_description(description)
        if not keyword:
            await tg.edit_message(message_id,
                t("cb.learn_no_kw"), [])
            return

        # Find MCC label from card's rules (dynamic)
        account_id = (tx_row[16] if len(tx_row) > 16 else "").strip()
        choices = _get_mcc_choices(account_id or None)
        mcc_label = next(
            (label for code, label in choices if code == mcc_code),
            mcc_code
        )
        # Strip emoji from label for storage
        mcc_label_clean = mcc_label.lstrip("🛒🛍✈️👗🚗 ")

        # Add to MCC Map (auto-apply for future)
        added = sh.add_mcc_map(
            pattern=keyword,
            mcc_code=mcc_code,
            mcc_label=mcc_label_clean,
            notes=f"learned from tx row {row_num}",
        )

        # Recompute cashback for this transaction
        try:
            result = sh.recompute_cashback_for_tx(row_num)
            cb_lines = [l for l in result.get("lines", []) if l.get("cashback_amount", 0) > 0]
            cb_total = sum(l.get("cashback_amount", 0) for l in cb_lines)
        except Exception:
            cb_total = 0

        status = t("cb.learn_exists") if not added else t("cb.learn_added")
        msg = (
            f"{status} `{keyword}` → {mcc_label} ({mcc_code})\n"
        )
        if cb_total > 0:
            msg += t("cb.learn_cb_earned", amount=sh.fmt_amount(cb_total))
        else:
            msg += t("cb.learn_saved")

        await tg.edit_message(message_id, msg, [])
    except Exception as e:
        print(f"[cashback] learn_apply error row={row_num}: {e}")
        try:
            await tg.edit_message(message_id, t("cb.learn_error", err=str(e)), [])
        except Exception:
            pass


async def _learn_exclude(row_num: int, message_id: int):
    """User said 'no cashback' → add keyword to exclusion list."""
    try:
        tx_row = sh.get_transaction_row(row_num)
        description = tx_row[5] if len(tx_row) > 5 else ""

        keyword = sh.extract_keyword_from_description(description)
        if keyword:
            sh.add_mcc_exclusion(keyword, notes=f"declined from tx row {row_num}")
            msg = t("cb.learn_excl", keyword=keyword)
        else:
            msg = t("cb.learn_skip")

        await tg.edit_message(message_id, msg, [])
    except Exception as e:
        print(f"[cashback] learn_exclude error row={row_num}: {e}")
        try:
            await tg.edit_message(message_id, t("cb.learn_skip"), [])
        except Exception:
            pass


async def _learn_wrong(row_num: int, message_id: int):
    """User said 'Sai, không CB' on a matched-MCC cashback notification.

    1. Extract a MORE SPECIFIC keyword from the full description (multi-word)
       so the exclusion pattern is longer than the MCC pattern.
    2. Add it to MCC Exclusions.
    3. Void the cashback entry for this transaction.
    4. Future txs matching this specific pattern auto-skip (exclusion wins by length).

    Example: MCC Map has "shopee" (6 chars) → 5262.
    User taps "Sai" on "SHOPEE FOOD ORDER 456".
    We extract "shopee food" (11 chars) → exclusion.
    Next "SHOPEE FOOD" tx: exclusion (11) > MCC (6) → auto-skip.
    Next "SHOPEE ELECTRONICS" tx: MCC (6) > no exclusion → cashback.
    """
    try:
        tx_row = sh.get_transaction_row(row_num)
        description = tx_row[5] if len(tx_row) > 5 else ""

        # Extract specific (multi-word) keyword for more precise exclusion
        keyword_specific = sh.extract_keyword_from_description(description, specific=True)
        keyword_broad = sh.extract_keyword_from_description(description, specific=False)

        # Use specific keyword if it's longer than the broad one (more precise)
        keyword = keyword_specific if len(keyword_specific) > len(keyword_broad) else keyword_broad

        if keyword:
            sh.add_mcc_exclusion(keyword, notes=f"wrong cashback from tx row {row_num}")

        # Void cashback for this transaction + recompute (will now hit exclusion)
        try:
            sh.void_cashback_for_tx(row_num)
            sh.recompute_cashback_for_tx(row_num)
        except Exception:
            pass  # void is best-effort

        if keyword:
            msg = t("cb.learn_wrong", keyword=keyword)
        else:
            msg = t("cb.learn_voided")

        await tg.edit_message(message_id, msg, [])
    except Exception as e:
        print(f"[cashback] learn_wrong error row={row_num}: {e}")
        try:
            await tg.edit_message(message_id, t("cb.learn_voided"), [])
        except Exception:
            pass
