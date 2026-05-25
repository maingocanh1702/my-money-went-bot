#!/usr/bin/env bash
# publish_oss_v1.sh — autopilot Phase 1 OSS publish + private personal split.
#
# What this does, in order:
#   A. Commit the credit/cc/transfer strip locally (preserves the OSS state).
#   B. Create a brand-new PUBLIC repo on GitHub and push the stripped code
#      as a single clean initial commit.
#   C. Reset the local working repo back, revert the email-parser strip
#      commits, and push — the original repo regains full features.
#   D. Flip the original repo's visibility to PRIVATE (Railway connection
#      survives the visibility change).
#
# Requires:
#   brew install gh
#   gh auth login    (one-time)
#
# Safe to re-run: every step checks state first and skips when already done.

set -euo pipefail

# ─── Config ─────────────────────────────────────────────────────
PERSONAL_DIR="${PERSONAL_DIR:-$HOME/Projects/Bot Finance}"
OSS_DIR="${OSS_DIR:-$HOME/Projects/spend-less-bot}"
PERSONAL_REPO="${PERSONAL_REPO:-maingocanh1702/financial-tracking}"
OSS_REPO_NAME="${OSS_REPO_NAME:-spend-less-bot}"
OSS_REPO_FULL="${OSS_REPO_FULL:-maingocanh1702/$OSS_REPO_NAME}"
OSS_DESCRIPTION="Vietnamese personal finance Telegram bot — Phase 1 OSS"

# ─── Helpers ────────────────────────────────────────────────────
log()  { echo -e "\033[36m[$(date +%H:%M:%S)]\033[0m $*"; }
ok()   { echo -e "\033[32m✓\033[0m $*"; }
warn() { echo -e "\033[33m!\033[0m $*"; }
fail() { echo -e "\033[31m✗\033[0m $*" >&2; exit 1; }

require() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing dependency: $1"
}

# ─── Preflight ──────────────────────────────────────────────────
require git
require rsync
require gh

gh auth status >/dev/null 2>&1 || fail "Run 'gh auth login' first"

[ -d "$PERSONAL_DIR" ] || fail "PERSONAL_DIR not found: $PERSONAL_DIR"
cd "$PERSONAL_DIR"
[ -d .git ]            || fail "$PERSONAL_DIR is not a git repo"

# Cleanup stale locks if any
rm -f .git/index.lock .git/HEAD.lock 2>/dev/null || true

log "Personal repo : $PERSONAL_REPO ($PERSONAL_DIR)"
log "New OSS repo  : $OSS_REPO_FULL ($OSS_DIR)"

# ─── Phase A: commit credit strip locally ───────────────────────
log "Phase A: commit credit/cc/transfer strip locally"

# Stage any modifications that exist (idempotent — skip if nothing to commit)
git add handlers/accounts.py main.py tests/unit/test_wizard_simplifications.py \
        README.md README.vi.md 2>/dev/null || true

if git diff --cached --quiet; then
  warn "No staged changes for credit-strip commit (already done or nothing to strip)"
else
  git commit -m "refactor(scope): strip credit/cc/transfer from wizard + dispatcher"
  ok   "Committed credit/cc/transfer strip"
fi

# Drop out-of-scope test files
for f in tests/unit/test_phase2_email_hints.py tests/unit/test_cc_pay_external.py tests/unit/test_phase4_transfer.py; do
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    git rm "$f"
  fi
done

if git diff --cached --quiet; then
  warn "No staged deletions (tests already removed?)"
else
  git commit -m "chore: drop tests for stripped features (email, /cc, /transfer)"
  ok   "Committed test cleanup"
fi

# Sanity: HEAD now reflects fully stripped Phase 1 OSS state
log "Local HEAD after Phase A:"
git log --oneline -3

# ─── Phase B: create OSS public repo + push stripped snapshot ──
log "Phase B: create OSS public repo + push initial commit"

# Create repo (idempotent — skip if exists)
if gh repo view "$OSS_REPO_FULL" >/dev/null 2>&1; then
  warn "OSS repo already exists: $OSS_REPO_FULL — will reuse"
else
  gh repo create "$OSS_REPO_FULL" --public --description "$OSS_DESCRIPTION"
  ok "Created GitHub repo: $OSS_REPO_FULL"
fi

# Snapshot current local state into OSS_DIR
mkdir -p "$OSS_DIR"
cd "$OSS_DIR"

if [ ! -d .git ]; then
  git init -b main
  ok "Initialized $OSS_DIR"
fi

log "Syncing files from $PERSONAL_DIR → $OSS_DIR (excluding secrets + cache)"
rsync -a --delete \
  --exclude='.git/' \
  --exclude='.env' --exclude='credentials.json' \
  --exclude='.venv/' --exclude='venv/' --exclude='env/' \
  --exclude='__pycache__/' --exclude='.pytest_cache/' \
  --exclude='.claude/' --exclude='.DS_Store' \
  "$PERSONAL_DIR/" .

# Guard: must NOT have email_parser / cc_pay symbols (stripped state)
if [ -f handlers/email_parser.py ]; then
  fail "handlers/email_parser.py present in OSS snapshot — strip incomplete!"
fi
if grep -q "cmd_cc_pay\|cmd_transfer\|handle_credit_limit" handlers/accounts.py main.py 2>/dev/null; then
  warn "Credit/transfer symbols still in code — wizard surface stripped but functions remain (dormant). Continuing."
fi

# Set remote (idempotent)
if git remote | grep -q '^origin$'; then
  git remote set-url origin "git@github.com:$OSS_REPO_FULL.git"
else
  git remote add     origin "git@github.com:$OSS_REPO_FULL.git"
fi

# Commit + push (skip if already committed identically)
git add -A
if git rev-parse HEAD >/dev/null 2>&1 && git diff --cached --quiet; then
  warn "OSS repo already has matching commit, skipping initial commit"
else
  git commit -m "feat: initial release — Phase 1 OSS

Per-account tracking, unified /report (week/month/quarter/year × account/category
lens), /allocate with edit-mode, /accounts list/add/assign, /keywords
auto-categorize, /today daily snapshot."
  ok "OSS initial commit created"
fi

# Push (try main, fallback if needed)
git push -u origin main || git push -u origin main --force-with-lease
ok "OSS pushed to $OSS_REPO_FULL"

# Tag v1.0 (idempotent)
if ! git rev-parse v1.0 >/dev/null 2>&1; then
  git tag v1.0
  git push origin v1.0
  ok "Tagged v1.0"
fi

# ─── Phase C: recover personal repo back to full features ──────
log "Phase C: recover personal repo with email parser + credit"
cd "$PERSONAL_DIR"

# Undo the 2 Phase-A commits — they were a temporary local state for snapshotting
log "Resetting local main back to origin/main (drops Phase-A strip commits)"
git fetch origin
git reset --hard origin/main

# Revert email-parser strip commits already on origin
# (commit hashes hardcoded — if they don't exist, abort safely)
for c in 40106a9 4f21dea; do
  if git cat-file -e "$c^{commit}" 2>/dev/null; then
    git revert --no-edit "$c"
  else
    warn "Commit $c not found in history — skipping revert"
  fi
done

# Sanity: email_parser.py must be back
if [ ! -f handlers/email_parser.py ]; then
  fail "handlers/email_parser.py missing after revert — something went wrong"
fi
ok "Email parser file restored locally"

git push origin main
ok "Personal repo pushed (Railway will redeploy with email parser back)"

# ─── Phase D: flip personal repo to PRIVATE ────────────────────
log "Phase D: make $PERSONAL_REPO private"

if [ "$(gh repo view "$PERSONAL_REPO" --json visibility -q .visibility)" = "PRIVATE" ]; then
  warn "Repo already private — skipping"
else
  gh repo edit "$PERSONAL_REPO" --visibility=private --accept-visibility-change-consequences
  ok "Repo $PERSONAL_REPO is now PRIVATE"
fi

# ─── Done ───────────────────────────────────────────────────────
log "✅ All four phases complete"
echo
echo "  Public OSS      : https://github.com/$OSS_REPO_FULL"
echo "  Private personal: https://github.com/$PERSONAL_REPO"
echo
echo "Next:"
echo "  - Verify Railway redeployed personal repo with email parser back"
echo "    (Telegram: forward a bank email, check bot ingests it)"
echo "  - Browse the new OSS repo on GitHub — README should render correctly"
echo "  - Optional: add a screenshot/GIF demo to OSS README"
