# Phase 5 — i18n strings for tier-limit UX

## Context Links
- Spec: `docs/features/feature-pricing-tiers.md` §"Upgrade Prompt" lines 78-82, §"Tier Errors" lines 147-151.
- Existing i18n: `i18n/vi.py:101` `upgrade.cta`, `i18n/en.py:85` same. No `limit.*` keys yet.
- Decision D1 determines whether we need a "soft warning" string (D1=B/C) or only hard-block (D1=A).

## Priority
P2 — UX. Strings can ship as English-only placeholder if Phase 2 needs to land first; VI/EN polish next iteration.

## Status
pending — decision-soft on D1 (write all 3 variants; pick at runtime).

## Key Insights
- Spec already has the canonical VI strings (lines 78-82, 147-151). Pull verbatim.
- Need EN parity for global launch (per `docs/strategy/market-product-strategy-en.md` recent work).
- KISS: 6 keys total. No template engine needed; `i18n.t(key, **kwargs)` already supports placeholders per `core/services/user_svc.py:204-207`.

## Requirements
**Functional** — add these keys to BOTH `i18n/vi.py` and `i18n/en.py`:
| Key | VI (from spec) | EN |
|-----|----|----|
| `limit.tx_monthly_hit` | "⚠️ Đã hết {cap}/{cap} giao dịch tháng này.\n\n[⬆️ Upgrade Pro — Unlimited]  [ℹ️ Xem chi tiết]" | "⚠️ You've hit {cap}/{cap} transactions this month.\n\n[⬆️ Upgrade Pro — Unlimited]  [ℹ️ Details]" |
| `limit.tx_monthly_warn` | "Đã dùng {used}/{cap} giao dịch tháng này." | "{used}/{cap} transactions used this month." |
| `limit.tx_monthly_frozen` | "Tài khoản downgrade {downgrade_date}. Tháng này: {used}/{cap}. Upgrade để mở lại." | "Plan downgraded {downgrade_date}. This month: {used}/{cap}. Upgrade to resume." |
| `limit.bank_count_hit` | "Free chỉ 1 ngân hàng. Upgrade Pro (3) / Business (5)." | "Free allows 1 bank. Upgrade Pro (3) / Business (5)." |
| `limit.bank_count_detected` | "Phát hiện ngân hàng mới: {bank}/{last4}. Upgrade để theo dõi." | "New bank detected: {bank}/{last4}. Upgrade to track." |
| `limit.category_hit` | "Đạt giới hạn {n} danh mục." | "Category limit reached ({n})." |

**Non-functional**
- Missing-key fallback per existing `i18n.t` behavior — but verify behavior matches M8 in report (do NOT render `[MISSING: key]` to users; fall back to VI when EN missing).
- All `{...}` placeholders must be tested for `KeyError` on missing kwargs.

## Architecture
None — flat key additions.

## Related Code Files
**Modify**
- `i18n/vi.py` — add 6 keys in the `# ── upgrade / payment` section.
- `i18n/en.py` — same.
- `core/services/plan_limits_svc.py::notify_user_limit_hit` (Phase 2) — references these keys.

## Implementation Steps
1. Append keys to `i18n/vi.py` after line ~110.
2. Same for `i18n/en.py` after line ~94.
3. Add unit test in `tests/test_i18n.py` (or create) that calls `i18n.t('limit.tx_monthly_hit', cap=45, locale='vi')` and asserts no `[MISSING:` substring.
4. Commit: `feat(h1-p5): i18n strings for tier limits`.

## Todo List
- [ ] VI keys added.
- [ ] EN keys added.
- [ ] Unit test confirms render + placeholder substitution.
- [ ] Commit + push.

## Success Criteria
- All 6 keys present in both locales.
- `i18n.t(...)` with valid kwargs returns the formatted string.
- `i18n.t('limit.tx_monthly_hit')` without `cap` kwarg falls back gracefully (KeyError caught → return raw template or `[MISSING_KWARG]` — verify existing behavior).

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Translation tone off (VI native review) | Med | Low | Pulled verbatim from spec written by founder. |
| Telegram markdown injection via `{bank}` | Low | Low | `bank` is whitelisted from SePay `gateway` field (alphanum); sanitize in `notify_user_limit_hit` regardless. |

## Security Considerations
- User-facing strings interpolate webhook-derived data (`bank`, `last4`). Telegram parses MarkdownV2; an attacker controlling SePay payload could inject markdown chars. Sanitize via `telegram_api.escape_markdown_v2` (already exists or use stdlib re.sub for `[_*[]()~`>#+-=|{}.!]`).

## Rollback
Revert commit; Phase 2 falls back to hardcoded English string in `notify_user_limit_hit` (acceptable temporary state).

## Next Steps
Phase 6 (tests) — verifies these strings are rendered correctly in the block-message flow.
