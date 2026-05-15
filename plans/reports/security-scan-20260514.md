# Security Scan Report

**Project:** MyMoneyWent (Telegram bot, Python/FastAPI)
**Scanned:** 2026-05-14
**Scope:** Repo root excluding `.venv/`, `.git/`, caches, `__pycache__/`, `migrations/`, `mymoneywent.egg-info/`, `.autopilot/`
**Files checked:** ~120 Python files + JS/TOML/JSON/YAML
**Dep audit:** pip-audit 2.10.0 against installed venv

## Summary

| Category | Critical | High | Medium | Low |
|----------|---------:|-----:|-------:|----:|
| Secrets  | 0 | 1 | 2 | 0 |
| Deps     | 0 | 3 | 0 | 1 |
| Code     | 0 | 0 | 2 | 1 |

No secrets were ever committed to git history (verified via `git log --all --full-history`).
No SQL injection, command injection, eval/exec, unsafe deserialization, or disabled-TLS findings.

---

## Findings

### HIGH

1. **[SECRET]** Real Google Cloud service-account private key on disk — `credentials.json`
   - File contains a working RSA private key for `create@financial-assistant-bot.iam.gserviceaccount.com` (key id `eaba…79`).
   - Properly gitignored (`.gitignore:2`), `git log` confirms never committed, perms 0600.
   - Risk: still exposed if laptop is compromised, backed up to cloud storage, or synced to another machine.
   - Fix: rotate the service-account key in GCP IAM regardless of local exposure — treat any key checked into a repo dir as compromised. Replace with a new key; consider Workload Identity Federation or move to runtime secret injection (Railway env var holding JSON).

### MEDIUM

2. **[SECRET]** Real credentials in local `.env` (not committed)
   - `.env:5` → Telegram bot token (redacted: `8599…i8`)
   - `.env:17` → Linear API key (redacted: `lin_…V2`)
   - File is gitignored, never committed, perms 0600 — exposure is local-only.
   - Fix: rotate both if the laptop has been shared or backed up off-disk. Otherwise document in onboarding that these stay local.

3. **[AUTH]** Webhook auth fails open when secret unset — `main.py:77`, `handlers/sepay.py:124`
   - `if EMAIL_SECRET and body.get("secret") != EMAIL_SECRET:` — when `EMAIL_SECRET` is empty string (default in `config.py:29`), the check is skipped and all `/webhook/email` requests are accepted.
   - Same pattern for `SEPAY_SECRET` (`handlers/sepay.py:124`).
   - Risk: misconfiguration on a fresh deploy lets anyone POST fake bank-transaction emails, polluting user ledger.
   - Fix: in `config.py`, raise on missing secrets at startup, or fail-closed in the handler (`if not EMAIL_SECRET: return 503` rather than skipping the check).

### LOW

4. **[AUTH]** Plain-string comparison for webhook secret — `main.py:77`, `handlers/sepay.py:131`
   - Timing-attack surface exists but is negligible for a high-entropy 32-char token over public HTTPS. Worth fixing if doing a security pass.
   - Fix: use `hmac.compare_digest(body.get("secret", ""), EMAIL_SECRET)`.

---

### Dependency Vulnerabilities (3 HIGH, 1 LOW)

5. **[DEP] HIGH** `jinja2==3.1.4` — three sandbox-escape CVEs
   - CVE-2024-56326 (`str.format` indirect call), CVE-2024-56201 (filename+content RCE), CVE-2025-27516 (`|attr` sandbox bypass).
   - Exploitable only with attacker-controlled templates. Project does not appear to render user-supplied templates — jinja2 is pinned because sentry-sdk needs it (per requirements comment).
   - Fix: bump to `jinja2==3.1.6` in `requirements.txt`.

6. **[DEP] LOW** `black==24.4.2` — CVE-2026-32274 (dev-only)
   - Cache file path injection via `--python-cell-magics`. Dev tool, no runtime impact.
   - Fix: bump dev pin to `black==26.3.1` (pyproject `[dev]` extras).

---

## Recommendations (priority order)

1. **Rotate the GCP service-account key now** (`create@financial-assistant-bot.iam.gserviceaccount.com`) and consider moving `credentials.json` content into a Railway env var (load via `json.loads(os.environ["GOOGLE_CREDS_JSON"])`) so the file does not need to exist on disk in any deploy environment.
2. **Make webhook secrets mandatory** in `config.py` — raise `RuntimeError` at import if `EMAIL_SECRET` or `SEPAY_SECRET` is empty in production (gate on a `RAILWAY_ENVIRONMENT`/`ENV` check so local dev still works).
3. **Bump jinja2 → 3.1.6** in `requirements.txt`. Bump black → 26.3.1 in dev deps.
4. **Switch to `hmac.compare_digest`** for webhook secret comparison at `main.py:77` and `handlers/sepay.py:131`.
5. **Optional:** add `pip-audit` to pre-commit (`.pre-commit-config.yaml`) or CI (`.github/workflows/`) so dependency CVEs surface automatically.

## Unresolved Questions

- Is the `financial-assistant-bot` GCP project still active, or has the key already been retired? Need GCP IAM check before deciding whether rotation is "urgent" vs "housekeeping".
- Has `.env` or `credentials.json` ever been copied off this laptop (backups, second machine, screen-share)? Determines whether rotation is mandatory or precautionary.
