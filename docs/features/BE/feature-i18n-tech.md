# BE Tech Doc: i18n — Multilingual Bot (F14)

> **Version:** v1.0.0
> **Ngày tạo:** 2026-05-08
> **Feature doc:** [feature-i18n.md](file:///Users/maingocanh/Projects/MyMoneyWent/docs/features/feature-i18n.md)
> **TDD ref:** [TDD v1.7.0 §2.1 users.locale](file:///Users/maingocanh/Projects/MyMoneyWent/docs/tdd-vi.md)

---

## 1. Implementation Overview

| Module | File | Responsibility |
|--------|------|---------------|
| i18n Core | `i18n/__init__.py` | `t()` helper, pack loader, fallback |
| Vietnamese | `i18n/vi.py` | `VI` dict (~106 keys) |
| English | `i18n/en.py` | `EN` dict (~106 keys) |
| Detect | `services/locale_svc.py` | Auto-detect from Telegram/Messenger |
| Handler | `handlers/onboarding.py` | Language select step |
| Handler | `handlers/settings.py` | Language change callback |

---

## 2. Database Schema

### 2.1. Schema Change

```sql
-- Added to users table (TDD v1.7.0)
locale VARCHAR(5) NOT NULL DEFAULT 'vi',
CONSTRAINT chk_locale CHECK (locale IN ('vi', 'en'))
```

### 2.2. Key Queries

```sql
-- Save locale during onboarding
UPDATE users SET locale = $1, updated_at = NOW() WHERE id = $2;

-- Change locale from settings
UPDATE users SET locale = $1, updated_at = NOW() WHERE id = $2;

-- Read locale (in every handler — already fetched with user object)
SELECT locale FROM users WHERE id = $1;
```

### 2.3. Edge Cases (Backend)

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Data Integrity | language_code = 'vi-VN' | Normalize: startswith('vi') → 'vi' |
| 2 | Data Integrity | language_code = 'en-US' | Normalize: startswith('en') → 'en' |
| 3 | Data Integrity | language_code = 'pt-BR' | Non-vi → default 'en' |
| 4 | Data Integrity | language_code = NULL | Default 'vi' |
| 5 | Data Integrity | language_code = '' | Default 'vi' |
| 6 | Cross-Feature | Missing key in EN | Fallback to VI value |
| 7 | Data Integrity | t() with wrong format args | Catch KeyError → return template raw |
| 8 | Cross-Feature | Admin messages | Skip i18n, hardcoded English |
| 9 | Concurrency | Locale change mid-message | User object re-fetched per request |
| 10 | Cross-Feature | Default categories → locale | Lookup CATEGORIES_BY_LOCALE[locale] |
| 11 | Data Integrity | Locale = 'fr' (not in CHECK) | DB rejects, app validates first |
| 12 | Cross-Feature | CSV headers locale | Read user.locale at export time |

---

## 3. API Contract

### 3.1. i18n Module Interface

```python
# i18n/__init__.py
from i18n.vi import VI
from i18n.en import EN

PACKS = {'vi': VI, 'en': EN}
DEFAULT_LOCALE = 'vi'

def t(locale: str, key: str, **kwargs) -> str:
    """Translate key using locale pack with format args.
    
    Usage: t('vi', 'onboard.welcome', name='Hùng')
    Falls back to DEFAULT_LOCALE if key missing in target locale.
    Falls back to '[MISSING: key]' if key missing in both packs.
    """
    pack = PACKS.get(locale, PACKS[DEFAULT_LOCALE])
    template = pack.get(key)
    if template is None:
        template = PACKS[DEFAULT_LOCALE].get(key)
    if template is None:
        return f'[MISSING: {key}]'
    try:
        return template.format(**kwargs) if kwargs else template
    except KeyError:
        return template  # Return raw template if format args missing
```

### 3.2. Auto-detect Function

```python
# services/locale_svc.py
def detect_locale_from_telegram(language_code: str | None) -> str:
    """Detect locale from Telegram user.language_code."""
    if not language_code:
        return 'vi'  # Default for NULL
    if language_code.lower().startswith('vi'):
        return 'vi'
    return 'en'  # All non-vi → en

def detect_locale_from_discord(interaction_locale: str | None) -> str:
    """Detect locale from Discord interaction locale field (e.g. 'vi', 'en-US')."""
    if not interaction_locale:
        return 'vi'
    if interaction_locale.lower().startswith('vi'):
        return 'vi'
    return 'en'

def detect_locale_from_messenger(profile_locale: str | None) -> str:
    """Detect locale from Messenger user profile locale (e.g. 'vi_VN')."""
    if not profile_locale:
        return 'vi'
    if profile_locale.lower().startswith('vi'):
        return 'vi'
    return 'en'
```

### 3.3. Callback Data

```python
f"lang:vi"          # Confirm/select Vietnamese
f"lang:en"          # Confirm/select English
f"settings:lang"    # Open language change from settings
```

---

## 4. Implementation Details

### 4.1. Handler Pattern (every handler)

```python
# BEFORE (hardcoded Vietnamese)
await messenger.send(user_id, {"type": "text", "text": "⚠️ Có lỗi xảy ra."})

# AFTER (i18n)
from i18n import t
user = await db.get_user(user_id)
await messenger.send(user_id, {"type": "text", "text": t(user.locale, 'error.generic')})
```

### 4.2. Default Categories by Locale

```python
CATEGORIES_BY_LOCALE = {
    'vi': [
        {'slug': 'daily_spending', 'name': '🛒 Chi tiêu hàng ngày', 'daily_cap': 100_000},
        {'slug': 'saving', 'name': '🏦 Tiết kiệm', 'daily_cap': None},
        {'slug': 'subscription', 'name': '📱 Đăng ký dịch vụ', 'daily_cap': None},
    ],
    'en': [
        {'slug': 'daily_spending', 'name': '🛒 Daily Spending', 'daily_cap': 100_000},
        {'slug': 'saving', 'name': '🏦 Saving', 'daily_cap': None},
        {'slug': 'subscription', 'name': '📱 Subscription', 'daily_cap': None},
    ],
}
```

### 4.3. Onboarding Language Step

```python
async def handle_start(update, context):
    user = await db.get_or_create_user(...)
    if user.locale is None or user.is_new:
        detected = detect_locale_from_telegram(update.effective_user.language_code)
        # Show confirm prompt with detected language pre-selected
        await send_language_confirm(user, detected)
        await db.set_bot_state(user.id, 'language_confirm', {'detected': detected})
    else:
        await send_welcome_back(user)

async def handle_language_callback(update, context, data):
    locale = data.split(':')[1]  # 'lang:vi' → 'vi'
    await db.update_locale(user.id, locale)
    # Create default categories in user's locale
    await db.create_default_categories(user.id, CATEGORIES_BY_LOCALE[locale], current_month())
    # Proceed to path selection
    await send_path_selection(user, locale)
```

### 4.4. Number Formatting

```python
def fmt_currency(amount: int, locale: str) -> str:
    formatted = f"{amount:,.0f}".replace(",", ".")  # 1.500.000
    if locale == 'vi':
        return f"{formatted}đ"
    return f"{formatted} VND"

def fmt_remaining(amount: int, locale: str) -> str:
    return t(locale, 'fmt.remaining', amount=fmt_currency(amount, locale))
```

---

## 5. Testing Plan

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | t() basic vi | t('vi', 'onboard.welcome') | Vietnamese string |
| 2 | t() basic en | t('en', 'onboard.welcome') | English string |
| 3 | t() format args | t('vi', 'cat.confirm_tracking', name='Food', amount='500k') | Formatted string |
| 4 | t() missing en key | t('en', 'nonexistent.key') | Falls back to vi |
| 5 | t() missing both | t('vi', 'truly.missing') | '[MISSING: truly.missing]' |
| 6 | t() unknown locale | t('fr', 'onboard.welcome') | Falls back to vi |
| 7 | t() format error | t('vi', 'cat.confirm_tracking') (no args) | Template raw |
| 8 | Detect vi | language_code='vi' | 'vi' |
| 9 | Detect vi-VN | language_code='vi-VN' | 'vi' |
| 10 | Detect en | language_code='en' | 'en' |
| 11 | Detect en-US | language_code='en-US' | 'en' |
| 12 | Detect pt-BR | language_code='pt-BR' | 'en' |
| 13 | Detect NULL | language_code=None | 'vi' |
| 14 | Detect empty | language_code='' | 'vi' |
| 15 | Detect Messenger vi | profile_locale='vi_VN' | 'vi' |
| 15b | Detect Discord vi | interaction_locale='vi' | 'vi' |
| 15c | Detect Discord en-US | interaction_locale='en-US' | 'en' |
| 16 | Onboard new user vi | language_code='vi' | Confirm prompt in vi |
| 17 | Onboard new user en | language_code='en' | Confirm prompt in en |
| 18 | Onboard confirm vi | Callback 'lang:vi' | locale='vi', categories vi |
| 19 | Onboard override en | Detected vi, pick en | locale='en', categories en |
| 20 | Default cats vi | locale='vi' | 3 cats with Vietnamese names |
| 21 | Default cats en | locale='en' | 3 cats with English names |
| 22 | Settings change | vi→en | All future messages in en |
| 23 | Settings change back | en→vi | All future messages in vi |
| 24 | Key coverage | All keys | Every key in VI exists in EN |
| 25 | Key coverage reverse | All keys | Every key in EN exists in VI |
| 26 | Admin skip i18n | /admin_user 1 | English output |
| 27 | Currency format vi | 1500000, 'vi' | "1.500.000đ" |
| 28 | Currency format en | 1500000, 'en' | "1.500.000 VND" |
| 29 | Daily recap locale | User locale='en' | Recap in English |
| 30 | CSV headers locale | User locale='en' | English headers |

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | 2026-05-08 | Initial BE tech doc for i18n |
