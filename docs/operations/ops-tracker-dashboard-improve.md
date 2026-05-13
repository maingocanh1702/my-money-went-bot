# Ops Tracker Dashboard — Improvement Plan

> **Version:** v3.1.0
> **Ngày tạo:** 2026-05-13
> **Cập nhật:** 2026-05-13
> **Target:** `docs/dashboard.html` + `scripts/build-dashboard.py` + Linear integration + Railway `/ops-dashboard.json` endpoint
> **Ref:** [Dashboard Realtime Explained](dashboard-realtime-explained.md) | [Roadmap](../mymoneywent-roadmap.md) | [Tracker](../implementation-tracker.md)
> **Decision:** Task management → **Linear** (free tier). GitHub Projects evaluated — Linear thắng ở UX, automation, velocity tracking, multi-dev scalability.

---

## Tóm tắt

Dashboard hiện chỉ parse **1 nguồn** (`implementation-tracker.md`) → chỉ thấy PR status. Plan này gồm **4 phần**:

- **Phần A — Bug fixes** (P0-P2): 6 items fix vấn đề hiện tại (~4-6 giờ)
- **Phần B — Feature upgrade (v2)**: Multi-source parsing + 5-tab UI (~9-11 giờ)
- **Phần C — Linear migration + Railway backend**: Workspace với 10 phase-Projects, scripted migration với QA, Railway `/ops-dashboard.json` endpoint (Linear+GitHub aggregator với cache+fallback), 4-phase mirror migration (~15-17 giờ)
- **Phần D — Multi-dev readiness**: 5 gaps cho 1-2 dev mới — branch/PR convention, playbook, onboarding, CI gates via GitHub Actions → Linear (~6-7 giờ)

**Tổng: ~27-32 giờ (~7-8 sessions)**

| Phase | Items | Effort | Scope |
|-------|:-----:|--------|-------|
| A-P0 (fix ngay) | 2 | ~1 giờ | Rate limit, naming |
| A-P1 (nên fix) | 2 | ~2 giờ | CDN cache, DOM swap |
| A-P2 (nice to have) | 2 | ~2 giờ | Rate display, unauth fallback |
| B-Phase 1 | 4 | ~3-4 giờ | Multi-source parse |
| B-Phase 2 | 7 | ~4-5 giờ | Tab UI + rendering |
| B-Phase 3 | 3 | ~2 giờ | Polish, Gantt, aggregation |
| C-2 Setup | 1 | ~2 giờ | Workspace + 10 phase-Projects + Views + fields + state machine |
| C-3 Migration | 8 | ~6-8 giờ | Free-tier verify + scripted PR/feature migration + manual QA |
| C-4 Backend | 7 | ~7 giờ | Railway `/ops-dashboard.json` + cache + fallback + dashboard refactor |
| C-5 Mirror plan | 4 phases | ~2 giờ | Phase 0-3 sequencing + acceptance criteria + archive |
| C-6 SoT contract | doc | ~30 min | Source-of-truth table + anti-patterns |
| D-P0 multi-dev | 3 | ~2 giờ | Branch+PR convention, dashboard verify |
| D-P1 multi-dev | 7 | ~4.5 giờ | Playbook, onboarding doc, CI sync workflow, branch protection |

---

# Phần A — Bug Fixes

## A-P0 — Fix ngay

### 1. Polling interval gây guaranteed rate limit

**Vấn đề:** `POLL_INTERVAL_MS = 30000` (30s) = 120 requests/hour. GitHub unauth limit = 60/hr. Sau **30 phút** dashboard chắc chắn hit rate limit nếu không có PAT.

**Impact:** Indicator stuck 🟡 cho user chưa setup PAT. Bad first-run experience.

**Fix:**

```javascript
// scripts/build-dashboard.py — HTML_LIVE_JS constant
// Before:
var POLL_INTERVAL_MS = 30000;

// After:
var PAT = localStorage.getItem('github_pat');
var POLL_INTERVAL_MS = PAT ? 30000 : 120000;  // 30s if authed, 2min if unauth
```

**Rationale:** Unauth 120s = 30 req/hr = safely under 60/hr limit. Authed vẫn giữ 30s (5000/hr budget).

**Files:** `scripts/build-dashboard.py` (HTML_LIVE_JS)
**Test:** Mở dashboard incognito (no PAT) → verify indicator stays 🟢 sau 1 giờ.

---

### 2. Naming confusion với user-facing web dashboard

**Vấn đề:** File `dashboard-realtime-explained.md` và route `/dashboard` dễ nhầm với `web-dashboard/` (Phase W user-facing companion UI).

**Fix (3 steps):**

1. **Rename file:**
   ```bash
   git mv docs/operations/dashboard-realtime-explained.md \
          docs/operations/ops-tracker-dashboard-explained.md
   ```

2. **Add disclaimer header** vào file (ngay sau Version block):
   ```markdown
   > **⚠️ Đây là INTERNAL development tracker dashboard** — hiển thị tiến độ
   > implementation cho developer. KHÔNG phải user-facing web dashboard.
   > User-facing dashboard: xem [web-dashboard/](../../web-dashboard/).
   ```

3. **Update cross-references** (grep toàn repo):
   ```bash
   grep -rn "dashboard-realtime-explained" docs/ --include="*.md"
   # Replace all occurrences with ops-tracker-dashboard-explained
   ```

**Files:** `docs/operations/`, any cross-refs
**Test:** `grep -rn "dashboard-realtime-explained" docs/` returns 0 results.

---

## A-P1 — Nên fix

### 3. raw.githubusercontent.com CDN cache ≠ realtime

**Vấn đề:** `raw.githubusercontent.com` có edge CDN cache **5 phút**. Cache-bust `?_t=Date.now()` có thể bị CDN ignore.

**Recommended: Self-host via Railway** — fetch từ `location.origin + '/dashboard'` thay vì raw.githubusercontent.

```javascript
// Before:
var RAW_URL = 'https://raw.githubusercontent.com/' + REPO + '/main/docs/dashboard.html';

// After:
var RAW_URL = location.origin + '/dashboard';  // Self-hosted, no CDN cache
```

**Files:** `scripts/build-dashboard.py` (HTML_LIVE_JS)
**Test:** Push commit → verify dashboard updates trong <3 min.

---

### 4. innerHTML swap sẽ break nếu thêm inline scripts

**Vấn đề:** `oldContainer.innerHTML = newContainer.innerHTML` drops `<script>` tags. Blocked cho v2 tab UI (cần inline scripts cho Chart.js, filters).

**Fix:** `replaceChild` + script re-execution:

```javascript
function refreshDashboardDOM() {
  return fetch(RAW_URL, { cache: 'no-store' })
    .then(r => r.text())
    .then(text => {
      var parser = new DOMParser();
      var newDoc = parser.parseFromString(text, 'text/html');
      var newContainer = newDoc.querySelector('.container');
      var oldContainer = document.querySelector('.container');
      if (newContainer && oldContainer) {
        var scrollY = window.scrollY;
        var clone = document.importNode(newContainer, true);
        oldContainer.parentNode.replaceChild(clone, oldContainer);
        clone.querySelectorAll('script').forEach(function(oldScript) {
          var newScript = document.createElement('script');
          newScript.textContent = oldScript.textContent;
          oldScript.parentNode.replaceChild(newScript, oldScript);
        });
        window.scrollTo(0, scrollY);
      }
    });
}
```

**Files:** `scripts/build-dashboard.py` (HTML_LIVE_JS)

---

## A-P2 — Nice to have

### 5. Rate limit remaining display

Hover indicator → tooltip: "4923/5000 calls · resets in 42min"

```javascript
function updateRateLimitDisplay(response) {
  var remaining = response.headers.get('X-RateLimit-Remaining');
  var limit = response.headers.get('X-RateLimit-Limit');
  var resetTs = response.headers.get('X-RateLimit-Reset');
  if (remaining !== null) {
    var resetDate = new Date(parseInt(resetTs) * 1000);
    var resetMin = Math.ceil((resetDate - Date.now()) / 60000);
    indicator.title = remaining + '/' + limit + ' calls · resets in ' + resetMin + 'min';
  }
}
```

---

### 6. Graceful unauth fallback

Dashboard works without PAT via ETag-based self-hosted change detection:

```javascript
function fetchSelfHostedVersion() {
  return fetch(location.origin + '/dashboard', { method: 'HEAD' })
    .then(r => r.headers.get('ETag') || r.headers.get('Last-Modified'));
}
```

---

# Phần B — Dashboard v2: Multi-source + 5-tab UI

## B1. Vấn đề

Dashboard chỉ parse `implementation-tracker.md`. Thiếu data từ roadmap:

| Data | Source | Tại sao cần |
|------|--------|-------------|
| Feature list + spec/code status | `roadmap.md` §2 | Biết feature nào spec xong, code chưa |
| Overall progress + phase status | `roadmap.md` §1 | Nhìn nhanh toàn cảnh dự án |
| Blockers & dependencies | `roadmap.md` §6 | Biết gì đang chặn |
| Risk register | `roadmap.md` §7 | Theo dõi risk level |
| Key metrics targets | `roadmap.md` §8 | Track KPIs |
| Doc versions | All doc headers | Verify docs fresh |
| Cross-phase invariants | `tracker.md` §2 | Quality gates status |

---

## B2. Proposed v2 Layout

```
+================================================================+
|  MyMoneyWent — Project Dashboard                    🟢 Live     |
|  MVP: 17% (6/35)  |  Target: Sep 2026  |  Runway: 16w         |
+================================================================+

+--[ Tab Bar ]---------------------------------------------------+
| [Overview]  [Features]  [PRs]  [Risks]  [Docs]               |
+----------------------------------------------------------------+
```

### Tab 1: Overview (default)

```
+---------------------------+------------------------------------+
| Phase Progress            | Key Metrics                        |
| P0 Docs    ██████████ 100%| Launch target:  Sep 2026           |
| P1 Found.  ███████░░░  75%| Active users:   TBD                |
| P2 Handler ██░░░░░░░░  22%| Paid conv:      TBD                |
| P3-P8      ░░░░░░░░░░   0%| Docs freshness: 6/6 current       |
| PW Dash.   ⏸️ Deferred    |                                    |
+---------------------------+ Blockers                           |
| Gantt Timeline            | ⚠ Docker Compose (W1.1)           |
| (Phase 1-8 bars w/ dates) | ⚠ Discord adapter (W1.2)          |
+---------------------------+------------------------------------+
```

### Tab 2: Features

```
+----------------------------------------------------------------+
| Module | Feature              | Spec | BE  | Code | Bot | Phase|
|--------|----------------------|:----:|:---:|:----:|:---:|:----:|
| F01    | 3-Path Onboarding    |  ✅  | ✅  |  🟡  | ⬜  | 1,4 |
| F02    | Transaction Capture  |  ✅  | ✅  |  🟡  | ⬜  | 1,5 |
| ...                                                            |
+----------------------------------------------------------------+
| Readiness:  Spec 85% | BE Tech 75% | Code 15% | Bot 5%        |
+----------------------------------------------------------------+
```

### Tab 3: PRs (current dashboard, enhanced)

Existing PR table + filter buttons (All/In-progress/Blocked/Merged) + search.

### Tab 4: Risks

```
+----------------------------------------------------------------+
| # | Risk                        | Level  | Mitigation         |
| 1 | SePay API change            | Trung  | Adapter pattern     |
| 2 | Telegram bot blocked        | Thấp   | Discord co-primary  |
+----------------------------------------------------------------+
```

### Tab 5: Docs

```
+----------------------------------------------------------------+
| Doc            | Version | Last Updated | Status               |
| BRD-vi         | v3.3.0  | 2026-05-13   | ✅ Current           |
| PRD-vi         | v1.8.0  | 2026-05-13   | ✅ Current           |
| TDD-vi         | v1.8.1  | 2026-05-08   | ⚠ 5 days old        |
+----------------------------------------------------------------+
| Feature Spec Coverage: 15/17 features have specs (88%)         |
+----------------------------------------------------------------+
```

---

## B3. Data Sources & Parse Strategy

> **⚠️ Note (v3.1.0):** Sau khi C4 Railway endpoint ra đời, phần lớn data sources dưới đây được Railway backend fetch trực tiếp từ Linear API + GitHub API, **không** qua build script parse markdown nữa. Section này giữ lại làm reference cho roadmap/doc parsing (vẫn cần parse markdown headers). Xem C4 cho architecture mới.

Build script upgrade từ 1 → 5 file sources (pre-C4 design):

```python
SOURCES = {
    'tracker': 'docs/implementation-tracker.md',
    'roadmap': 'docs/mymoneywent-roadmap.md',
    'brd': 'docs/brd-vi.md',
    'prd': 'docs/prd-vi.md',
    'tdd': 'docs/tdd-vi.md',
}

def build_dashboard():
    tracker_data = parse_tracker(SOURCES['tracker'])   # Existing
    roadmap_data = parse_roadmap(SOURCES['roadmap'])    # NEW
    doc_versions = parse_doc_versions(SOURCES)          # NEW
    
    html = render_dashboard(tracker_data, roadmap_data, doc_versions)
    write_output(html, json_output=True)  # Also emit dashboard.json
```

**Roadmap parser extracts:**

| Section | Output |
|---------|--------|
| §1 Overall Progress | `overall_progress`, `phases[]` |
| §2 Feature Modules | `features[]` with spec/be/code/bot status |
| §3 Timeline | `timeline` for Gantt |
| §6 Blockers | `blockers[]` |
| §7 Risk Register | `risks[]` |
| §8 Key Metrics | `metrics[]` |

---

## B4. JSON Intermediate Format

> **⚠️ Note (v3.1.0):** JSON format dưới đây trở thành **contract cho Railway endpoint** `GET /ops-dashboard.json` (xem C4). Không còn write ra file — serve trực tiếp qua HTTP.

Build script outputs `dashboard.json` trước rồi render HTML từ đó. Lợi ích: testable, debuggable, future API endpoint.

```json
{
  "generated_at": "2026-05-13T18:59:00",
  "overall": {
    "mvp_progress": 17,
    "merged": 6,
    "total": 35,
    "target_launch": "2026-09",
    "runway_weeks": 16
  },
  "phases": [
    { "id": "P1", "name": "Foundation", "status": "in_progress", "progress": 75, "merged": 4, "total": 7 }
  ],
  "features": [
    { "id": "F01", "name": "3-Path Onboarding", "spec": "done", "be_tech": "done", "be_code": "partial", "bot_code": "not_started", "phase": [1, 4] }
  ],
  "blockers": [
    { "description": "Docker Compose", "pr": "W1.1", "severity": "medium" }
  ],
  "risks": [
    { "id": 1, "description": "SePay API change", "level": "medium", "mitigation": "Adapter pattern" }
  ],
  "docs": [
    { "name": "BRD-vi", "version": "v3.3.0", "updated": "2026-05-13", "stale_days": 0, "status": "current" }
  ]
}
```

---

## B5. Pre-commit Hook Update

> **⚠️ Note (v3.1.0):** Sau C4, pre-commit hook chỉ cần rebuild `dashboard.html` (static shell). JSON data đến từ Railway endpoint realtime, không commit. Hook dưới đây là pre-C4 design, giữ lại nếu muốn fallback static build.

```yaml
# .pre-commit-config.yaml — expand trigger files (pre-C4 fallback)
- id: build-dashboard
  name: Rebuild dashboard HTML shell
  entry: bash -c 'python scripts/build-dashboard.py && git add docs/dashboard.html docs/dashboard.md'
  language: system
  files: ^(docs/mymoneywent-roadmap\.md|docs/brd-vi\.md|docs/prd-vi\.md|scripts/build-dashboard\.py)$
  pass_filenames: false
  require_serial: true
```

---

## B6. Implementation Tasks

### Phase 1: Multi-source parse (3-4h)

| # | Task | Effort |
|---|------|--------|
| B1.1 | Roadmap parser (§1, §2, §6, §7) | 1.5h |
| B1.2 | Doc version parser (5 docs headers) | 30min |
| B1.3 | Merge roadmap + tracker data | 1h |
| B1.4 | Unit tests for new parsers | 1h |

### Phase 2: Tab UI + rendering (4-5h)

| # | Task | Effort |
|---|------|--------|
| B2.1 | Tab component (vanilla JS, localStorage remember) | 1h |
| B2.2 | Overview tab (progress bars + metrics + blockers) | 1h |
| B2.3 | Features tab (matrix table + readiness summary) | 1h |
| B2.4 | Enhanced PR tab (filters + search) | 30min |
| B2.5 | Risks tab (severity color coding) | 30min |
| B2.6 | Docs tab (version table + staleness) | 30min |
| B2.7 | Responsive (tabs → dropdown on mobile) | 30min |

### Phase 3: Polish (2h)

| # | Task | Effort |
|---|------|--------|
| B3.1 | Gantt timeline (CSS div bars, no Chart.js) | 1h |
| B3.2 | Feature readiness aggregation bar | 30min |
| B3.3 | Staleness warnings (yellow >7d, red >14d) | 30min |

---

## B7. Open Questions

| # | Question | Options | Lean |
|---|----------|---------|------|
| 1 | Tab framework | Vanilla JS vs micro lib | Vanilla (zero deps) |
| 2 | Gantt rendering | Chart.js vs CSS div bars | CSS (no extra dep) |
| 3 | JSON output | Also write `dashboard.json`? | Yes — future API |
| 4 | Feature spec coverage | Scan `docs/features/feature-*.md` existence? | Yes — glob |
| 5 | GH Action trigger expansion | Add roadmap.md to workflow paths? | Yes |

---

# Phần C — Linear Migration

## C1. Tại sao Linear (không phải GitHub Projects)

| Tiêu chí | Linear | GitHub Projects |
|----------|:------:|:---------------:|
| PR → status auto-sync | ✅ Built-in | ⚠️ Basic |
| Sprint velocity/burndown | ✅ Built-in | ❌ Build yourself |
| Progress % auto-calculate | ✅ Per project/cycle | ❌ Script |
| Cycle auto-rollover | ✅ | ❌ |
| Scale 2-3 devs | ✅ My Issues, workload view | ⚠️ Có nhưng UX kém |
| UX speed | ✅ 50ms, keyboard-first | ⚠️ Chậm, React heavy |
| Cost (≤250 issues) | Free | Free |
| Cost (scale) | $8/user/month | Free |

**Decision:** Linear cho task management. GitHub Projects không đủ automation cho multi-dev scenario.

---

## C2. Linear Setup Plan

### Workspace / Team / Projects / Views

```
Workspace: MyMoneyWent
└── Team: Engineering
    ├── Projects (1 per phase — Linear `project.progress` = phase completion %):
    │     P0 — Docs & Foundation Specs
    │     P1 — Foundation
    │     P2 — Handlers
    │     P3 — Pricing & Billing
    │     P4 — SePay Integration
    │     P5 — Email Parsers
    │     P6 — Deploy & DevOps
    │     P7 — Beta Testing
    │     P8 — Public Launch
    │     PW — Web Dashboard (deferred)
    └── Views (cross-project filters — NOT Projects):
          "MVP Tracker"     = all issues across P0-P8 projects, group by Project
          "Backlog"         = filter status = Backlog (across all projects)
          "Current Cycle"   = filter cycle = active
          "Workload"        = group by assignee, status In Progress/In Review (WIP visibility)
          "Blocked"         = label = blocked
```

**Decision:** "MVP Tracker" là **View**, không phải Project. Dev mới luôn tạo issue vào Project tương ứng phase (P1, P2, ...). "MVP Tracker" view chỉ aggregate read-only.

### Labels

| Label | Color | Usage |
|-------|-------|-------|
| feature | Blue | Feature implementation |
| infra | Purple | Infrastructure/DevOps |
| bug | Red | Bug fixes |
| docs | Green | Documentation |
| chore | Gray | Maintenance |
| blocked | Orange | Has unresolved dependency |
| ci-failing | Red | CI check failed (auto-applied) |
| changes-requested | Yellow | PR review requested changes (auto-applied) |

### Custom Fields

| Field | Type | Values | Required to leave Backlog? |
|-------|------|--------|:---:|
| Phase | Select | P0-Docs, P1-Foundation, P2-Handlers, P3-Pricing, P4-SePay, P5-Email, P6-Deploy, P7-Beta, P8-Launch, PW-Dashboard | ✅ |
| Feature | Select | F01-F17, FAM, F-i18n, F-saas, WD-01-07, (none) | ✅ |
| Priority | Select | Urgent / High / Medium / Low | ✅ |
| Risk Tier | Select | P0-critical / P1-elevated / P2-standard | ✅ if touches DB/security/payment |
| Spec link | URL | URL to `docs/features/feature-*.md` or BRD/PRD section | ✅ for `feature` label |
| Acceptance criteria | Long text | Bullet list, testable | ✅ before move to Todo |

### Cycles

2-week sprints. Auto-rollover unfinished issues to next cycle.

### Status state machine

Status transitions auto-driven by GitHub events (via GitHub Actions → Linear API; see D6 Option A):

| Event | New status | Notes |
|-------|-----------|-------|
| Issue created (no template) | `Triage` | Founder reviews, fills required fields |
| Issue created (template) | `Backlog` | Required fields enforced by template |
| Added to cycle / assigned + required fields complete | `Todo` | Pre-condition: Phase + Feature + Priority + Acceptance criteria all set |
| Branch created matching `*/MMW-<id>-*` (first push) | `In Progress` | Linear GitHub integration auto-trigger |
| Draft PR opened | `In Progress` | Stays In Progress until ready-for-review |
| PR marked "Ready for review" | `In Review` | |
| Review state = `CHANGES_REQUESTED` | `In Review` + label `changes-requested` | Status doesn't regress, label added |
| CI check failed (required check) | `In Review` + label `ci-failing` | Blocks merge via branch protection |
| CI check passing + ≥1 review approval | `In Review` (label `ci-failing` / `changes-requested` cleared) | Ready to merge |
| PR merged | `Done` | Linear MagicWord `Closes MMW-XXX` required |
| PR closed unmerged | `Todo` if work continues, `Canceled` if abandoned | Manual triage by assignee |
| Cycle ends | Unfinished → rollover next cycle | Linear built-in |

### Required-fields enforcement

| Layer | Mechanism |
|-------|-----------|
| Linear UI | Issue template (D5) marks fields required; cannot save without |
| Pre-Todo gate | Linear workflow rule: block status transition Backlog → Todo if any required field empty |
| Pre-Done gate | Branch protection: require CI pass + 1 review (2 for `core/` and `markets/*/adapters/`) |

---

## C3. Migration Tasks

### C3.0 — Free tier verification (do FIRST, blocks everything else)

Linear free tier limits change. Before committing to setup, verify in current Linear plan:

| Capability | Need | Free tier? | Fallback if not free |
|-----------|------|:---:|----------------------|
| Custom fields (Phase, Feature, Priority, Risk Tier, Spec link, Acceptance criteria) | 6 fields | ❓ Verify | Use labels: `phase:P1`, `feature:F02`, `pri:high`, `risk:P0` |
| Cycles (2-week sprints) | Yes | ❓ Verify | Manual cycle tracking via labels `cycle:2026-W21` |
| Automations / Workflow rules | ≥4 rules | ❓ Verify | Move logic to GitHub Actions (call Linear API) |
| GitHub integration | Built-in | ✅ Free | — |
| Issue templates | 4 templates | ❓ Verify | Markdown checklist in description |
| Project progress field | Native | ✅ Free | — |
| Seats | 3-5 dev | ✅ Free 10 seats | — |

**Action:** anh log vào Linear → Settings → Plan, check each capability. Document gaps in this section. Effort: 20 min.

### Migration tasks

| # | Task | Effort | Detail |
|---|------|--------|--------|
| C3.0 | Free tier capability verification | 20 min | Above table; document any fallbacks needed |
| C3.1 | Create Engineering team + 10 phase Projects | 30 min | One per phase P0-P8 + PW |
| C3.2 | Enable GitHub integration | 10 min | Settings → Integrations → GitHub → select repo + magic word format |
| C3.3 | Create labels + custom fields + workflow rules | 30 min | Per C2 tables; verify required-fields enforcement works |
| C3.4 | Migrate 35 PRs → Linear issues (scripted) | 2-3h | Python script reads `implementation-tracker.md`, calls Linear GraphQL `issueCreate` mutation per PR. Preserves phase, feature, status, PR URL. |
| C3.5 | Migrate 21 features → Linear issues (parent + sub) | 1h scripted | Parent issue per feature with sub-issues for each PR |
| C3.6 | Manual QA migration result | 1-2h | Spot-check 5-10 issues: required fields present? GitHub links work? Phase assignment correct? Fix script bugs and re-run if needed. |
| C3.7 | Create Views (MVP Tracker, Backlog, Current Cycle, Workload, Blocked) | 20 min | Per C2 Views block |
| C3.8 | Smoke test PR↔issue sync | 30 min | Open 1 test PR on burner branch matching `MMW-XXX` convention → verify status auto-moves |

**Subtotal: ~6-8 giờ** (was 1.5h; 35 PR + 21 feature migration with QA + free-tier verification is the bulk)

---

## C4. Ops Dashboard → Live JSON endpoint (Railway backend)

### Vấn đề với build-script approach (đã loại)

Nếu build script gọi Linear API và commit `dashboard.html`/`dashboard.json` mỗi lần Linear status đổi:

- Không realtime (chờ pre-commit hoặc CI run)
- Spam commits cho mỗi drag-drop Linear (Backlog → Todo → In Progress)
- Conflict với parallel sessions (memory `feedback_concurrency_one_session.md`)
- Static dashboard fetch raw.githubusercontent.com → CDN cache 5 phút (memory đã document A-P1-3)

### Architecture mới — Railway backend với JSON endpoint

```
                                 ┌──────────────────┐
                                 │  Linear GraphQL  │
                                 └────────┬─────────┘
                                          │
                                 ┌────────▼──────────┐
                                 │  GitHub REST/GQL  │
                                 └────────┬──────────┘
                                          │
   ┌──────────────────────────────────────▼──────────────────────┐
   │   Railway backend:  GET /ops-dashboard.json                 │
   │   - Fetches Linear (issues, projects, cycles)               │
   │   - Fetches GitHub (PRs, check_runs, branch protection)     │
   │   - Aggregates → JSON                                       │
   │   - In-memory cache 60-120s (configurable via env)          │
   │   - Fallback: last-good-JSON stored on disk if Linear/GH down│
   │   - ETag + Last-Modified headers                            │
   └──────────────────────────────────────┬──────────────────────┘
                                          │
                            ┌─────────────▼──────────────┐
                            │  dashboard.html            │
                            │  polls /ops-dashboard.json │
                            │  every 30s (60s unauth)    │
                            └────────────────────────────┘
```

### Endpoint contract

```http
GET /ops-dashboard.json
Cache-Control: public, max-age=60
ETag: "<sha256 of payload>"
Content-Type: application/json

{
  "generated_at": "2026-05-13T18:59:00Z",
  "data_age_seconds": 47,           // age of cached upstream data
  "sources_status": {
    "linear": "ok" | "degraded" | "stale",
    "github": "ok" | "degraded" | "stale"
  },
  "overall": { ... },
  "phases": [ ... from Linear project.progress ... ],
  "features": [ ... ],
  "blockers": [ ... ],
  "risks": [ ... from roadmap.md (manual) ... ],
  "docs": [ ... ]
}
```

### Tasks

| # | Task | Effort | Detail |
|---|------|--------|--------|
| C4.1 | Railway endpoint scaffold (`ops_api/main.py`) | 1h | FastAPI route `/ops-dashboard.json`, env vars `LINEAR_API_KEY`, `GITHUB_TOKEN`, `CACHE_TTL_SECONDS` |
| C4.2 | Linear GraphQL client (issues, projects, cycles) | 1.5h | Queries: `PhaseProgress` (per-project progress + counts), `ActiveCycleIssues`, `BlockedIssues` |
| C4.3 | GitHub REST/GraphQL client (PRs, checks) | 1h | Merge PR state + check_run aggregation per Linear issue (via magic-word link) |
| C4.4 | Cache + fallback layer | 1h | TTL-based memory cache; disk-write last-good payload; serve stale on upstream error |
| C4.5 | `dashboard.html` polling refactor | 1h | Replace `RAW_URL` fetch (raw.githubusercontent.com) with `location.origin + '/ops-dashboard.json'`; render from JSON |
| C4.6 | Health endpoint `/healthz` + Sentry integration | 30 min | Monitor upstream errors, cache hit rate |
| C4.7 | Deploy to Railway + smoke test | 1h | Reuse existing Railway project; add new service or `/ops-*` route prefix |

**Subtotal: ~7 giờ** (was 1.5h; backend service is real work, not just a script)

### Why this is better

| Concern | Build script approach | Railway endpoint approach |
|---------|----------------------|---------------------------|
| Realtime | ❌ Wait for commit | ✅ ≤60s lag |
| Commit spam | ❌ Many status-change commits | ✅ Zero status-driven commits |
| Concurrency | ❌ Conflicts with multi-session | ✅ Single source, no git involved |
| Fallback if Linear down | ❌ Stale committed JSON | ✅ Serve last-good with `data_age_seconds` |
| Cost | ✅ Free | ✅ Free (Railway hobby tier OR existing service) |
| Dashboard reload | ❌ CDN cache 5min | ✅ ETag + 60s max-age |

---

## C5. Mirror Migration Plan (4 phases — NOT a single 30-min deprecation step)

**Rule:** Never deprecate `implementation-tracker.md` before Linear has proven equivalent for ≥1 week of real activity.

### Phase 0 — Linear setup, zero dashboard dependency (Week 1)

- Linear team + projects + custom fields + workflow rules created (per C2)
- Free tier capabilities verified (C3.0)
- Existing tracker.md and dashboard build script keep running unchanged
- **Exit criteria:** Linear infrastructure ready; founder + 1 burner issue smoke-tested

### Phase 1 — Mirror mode (Week 2)

- Migrate 35 PRs + 21 features to Linear (C3.4-C3.6)
- **Both** sources stay updated: tracker.md manually as today, Linear via new convention
- Dashboard still parses tracker.md (not Linear yet)
- Daily reconciliation: founder reviews diff between tracker.md and Linear; documents drift
- **Exit criteria after 7 days:** Drift log shows ≤2 minor discrepancies/week, all explainable

### Phase 2 — Read-from-Linear (Week 3)

- Deploy Railway `/ops-dashboard.json` endpoint (C4.1-C4.7)
- Dashboard reads from Railway JSON (Linear-sourced)
- tracker.md becomes **read-only mirror** — generated by nightly script from Linear, never hand-edited
- **Exit criteria after 7 days:** Dashboard data matches manually-curated tracker for 7 consecutive days with zero unexplained drift

### Phase 3 — Archive tracker (Week 4+)

- Move `implementation-tracker.md` → `docs/archive/implementation-tracker-2026-05.md` (frozen snapshot)
- Linear is sole source of truth for tasks
- Roadmap.md stays as strategic doc (manual updates, weekly cadence)

### Acceptance criteria (all must hold before Phase 3)

| # | Criterion | Verification |
|---|----------|--------------|
| 1 | 100% active PRs have linked Linear issue | Script: scan open PRs, all must reference `MMW-\d+` |
| 2 | Dashboard Linear data matches tracker for 7 consecutive days | Daily diff log, zero unexplained drift |
| 3 | Branch/PR convention enforced in CI | GitHub Action `pr-validate` green on ≥10 PRs |
| 4 | Dev onboarding doc tested | One new contributor (or dry-run by anh as if new dev) completes first-day setup → first PR merged using only the doc |
| 5 | Railway endpoint uptime ≥99% over 7 days | `/healthz` checks + Sentry error rate <1% |
| 6 | Free-tier capabilities sufficient (or fallbacks documented) | C3.0 table fully filled with ✅ or fallback noted |

**Subtotal C5 effort:** ~2h (mostly diff-tracking discipline; bulk work is in C3 + C4)

---

## C6. Source-of-Truth Contract

Explicit contract to prevent drift. Every type of project data has exactly **one** authoritative source. Other places that show the same data are **read-only views** generated from the source.

| Domain | Source of truth | Read-only views | Notes |
|--------|-----------------|-----------------|-------|
| Tasks: status, assignee, cycle, priority, custom fields | **Linear** | Ops dashboard, `tracker.md` (generated, mirror phase only) | NEVER edit dashboard/tracker manually for task data |
| Code implementation | **GitHub** (PRs + branches + CI) | Linear shows PR links/CI badges; dashboard shows merge state | Merge truth lives in GitHub; Linear reflects, never originates |
| Product strategy + timeline + phase definitions | **`docs/mymoneywent-roadmap.md`** | Dashboard `Overview` tab (manual snapshot, weekly), Linear Project names map to phases | Manual strategic doc; not operational truth. Auto-progress shown in dashboard via Linear, NOT auto-edited into roadmap.md |
| Specs / requirements / acceptance criteria | **`docs/features/feature-*.md`, BRD-vi.md, PRD-vi.md, TDD-vi.md** | Linear issue "Spec link" field references these | Spec-first workflow: spec exists before issue moves to Todo |
| Ops dashboard view | **Railway `/ops-dashboard.json` endpoint** | `docs/dashboard.html` (rendered from JSON) | Generated read-only view. No manual edits to dashboard.html outside `build-dashboard.py` |
| `docs/implementation-tracker.md` | **Generated from Linear** (mirror phase only) | — | DEPRECATED after C5 Phase 3. Frozen snapshot archived. |
| Risk register | **`docs/mymoneywent-roadmap.md` §7** | Dashboard `Risks` tab | Manual; weekly review cadence |
| Doc versions | **Doc file headers** (`> **Version:** ...`) | Dashboard `Docs` tab parses these | Single source: the doc itself |
| Project memory / conventions | **`MEMORY.md` + `memory/*.md`** | Agent/runtime context | Update in `memory/*.md`, `MEMORY.md` is the index |

### Anti-patterns (FORBIDDEN)

1. ❌ Editing `dashboard.html` directly → it's generated
2. ❌ Editing `implementation-tracker.md` manually after C5 Phase 2 → it's a mirror
3. ❌ Auto-committing roadmap.md progress numbers from a script → roadmap is manual strategy
4. ❌ Tracking task status outside Linear (Notion, Slack canvas, separate Markdown) → drift guaranteed
5. ❌ Hand-editing custom field values in Linear UI when an automation should set them → use rules

### When sources conflict

Always trust the source-of-truth. Fix downstream views, never edit the view to match a stale source. If the source itself is wrong, update the source (and the view will auto-refresh).

---

# Phần D — Multi-dev Readiness

## D1. Tại sao cần Phần D

Phần C đặt Linear foundation, nhưng **chưa đủ** cho scenario 1-2 dev mới onboard. Phần D fill 5 gaps:

| # | Gap | Symptom nếu không fix |
|---|-----|------------------------|
| 1 | Roadmap auto-aggregate progress | Dashboard show "P1 = 75%" nhưng phải compute manual; roadmap.md vẫn manual update |
| 2 | PR ↔ Linear issue auto-link | Branch `W0.9-...` không match Linear pattern → automation không trigger → status không sync |
| 3 | Multi-dev workflow | Không define ai pick task, WIP limit, review rotation → 1 dev grab 5 tasks, dev khác idle |
| 4 | Onboarding playbook | Dev mới hỏi anh từng bước → time sink, không scale |
| 5 | Quality gates | Merge nhầm khi CI fail, không có required reviews |

**Effort tổng Phần D: ~6-7 giờ.**

---

## D2. Roadmap Progress in Dashboard (Gap 1 — P0)

**Note:** Creating 10 phase-Projects in Linear is now in **C2** (the source-of-truth structure). D2 is only about exposing phase progress in the **dashboard**, not editing `roadmap.md`.

### Approach

The Railway `/ops-dashboard.json` endpoint (C4) already queries `linear.projects` and includes phase progress in its `phases[]` payload. The dashboard `Overview` tab renders the progress bars from that JSON.

```graphql
query PhaseProgress {
  projects(filter: { name: { startsWith: "P" } }) {
    nodes {
      name
      progress       # Linear built-in 0.0-1.0
      issueCount
      completedIssueCount
      startDate
      targetDate
      state          # backlog | planned | started | completed
    }
  }
}
```

### What NOT to do

❌ **Do not** auto-edit `mymoneywent-roadmap.md` §1 table with a script. Per memory `feedback_dashboard_auto_gen.md` and C6 contract, `roadmap.md` is **manual strategic doc**, not operational mirror. Auto-commits would:
- Spam git history with every Linear status change
- Conflict with concurrent founder edits (memory `feedback_concurrency_one_session.md`)
- Create circular dependency: roadmap defines phases, phases define progress, progress edits roadmap

❌ **Do not** add `<!-- AUTO-GEN START/END -->` markers in `roadmap.md`.

### What TO do

✅ Dashboard `Overview` tab reads phases from Railway JSON → renders live progress bars
✅ Roadmap.md §1 table stays manual, updated weekly during strategy review
✅ Optional: weekly snapshot script (run manually before stakeholder updates) outputs a markdown blob anh can paste into stakeholder update emails — but the source remains Linear and the operational dashboard

**Files:** Railway backend (`ops_api/`), `docs/dashboard.html` rendering
**Effort:** 0h additional — covered by C4.2 (Linear GraphQL) and C4.5 (dashboard polling refactor)

**D2 is now reduced to a verification task:** confirm Linear `project.progress` aggregates correctly after C3 migration and renders in dashboard Overview tab. ~30 min.

---

## D3. Branch + PR Convention với Linear Magic Word (Gap 2 — P0)

**Vấn đề:** Linear PR auto-sync trigger qua:
1. Branch name chứa Linear issue ID (`username/MMW-123-slug`), HOẶC
2. PR title/body có magic word (`Fixes MMW-123`, `Closes MMW-123`, `Ref MMW-123`)

Convention hiện tại `W0.9-dashboard-realtime` **không match** → automation không trigger.

### Branch naming convention (mới)

```
Format: <dev-handle>/MMW-<issue-id>-<kebab-slug>
Example: anh/MMW-42-multi-source-parse
         devB/MMW-58-linear-graphql-integration
```

**Linear UI "Copy git branch name"** tự gen format này nếu set Settings → Workspace → Git branch format = `{username}/MMW-{issueId}-{title-kebab}`.

### PR template (`.github/pull_request_template.md`)

```markdown
## Summary
<!-- 1-2 sentences what & why -->

## Linear Issue
Closes MMW-XXX
<!-- Required: at least one Linear magic word -->
<!-- Multi-issue PR: list each on separate line -->

## Changes
- [ ] Item 1
- [ ] Item 2

## Testing
- [ ] Unit tests pass (`pytest`)
- [ ] Manual smoke test in dev
- [ ] No regressions in adjacent features

## Checklist (Definition of Done)
- [ ] CI green
- [ ] At least 1 review approval
- [ ] Linear issue auto-moved to "In Review" (verify after PR open)
- [ ] Docs updated nếu touch public API/contract
```

### Enforcement

| Layer | Mechanism |
|-------|-----------|
| Local | Git hook (`pre-push`) check branch name regex match `^[a-z0-9-]+/MMW-\d+-` |
| CI | GitHub Action validate PR body chứa `(Closes|Fixes|Ref) MMW-\d+` |
| Linear | Settings → Integrations → GitHub → enable "Auto-link PRs by branch + magic word" |

**Migration của 35 existing PRs:**
- Bulk edit Linear issues to add `MMW-XXX` to legacy branch names? **No** — quá noisy
- Strategy: legacy PRs (W0.*) link manual qua Linear UI "Link to GitHub PR" 1 lần; PRs mới từ migration trở đi dùng convention mới

**Files:** `.github/pull_request_template.md` (NEW), `.git/hooks/pre-push` hoặc `scripts/git-hooks/pre-push.sh`, `.github/workflows/pr-validate.yml` (NEW or extend existing)
**Effort:** 1.5h

---

## D4. Multi-dev Playbook (Gap 3 — P1)

### Task assignment rules

| Scenario | Rule |
|----------|------|
| Dev tự pick task | Filter Backlog by phase + label, drag to "Todo" + self-assign |
| Anh phân task | Mention dev trong issue comment + assign + move to Todo |
| Urgent bug | Priority field = Urgent, auto-assign to oncall (rotate weekly) |
| Cross-feature task | Parent issue assigned to anh; sub-issues split per dev |

### WIP limits

```
Per dev: ≤2 issues trong "In Progress" + "In Review" cùng lúc
Soft enforcement: Linear view warning when threshold exceeded
Hard enforcement: Slack/Discord bot ping anh khi dev có >3 active
```

**Linear View setup:** "Workload" view group by assignee, filter status In Progress/Review.

### Code review rotation

| Trigger | Reviewer |
|---------|----------|
| PR opened by dev A | Auto request review from dev B (and anh as backup) |
| PR opened by anh | Auto request from any dev available |
| Architectural/security change | Require anh approval (CODEOWNERS rule) |

**GitHub setup:** `.github/CODEOWNERS` + branch protection → require 1 review (2 for `main`).

### Standup automation

| Cadence | Mechanism |
|---------|-----------|
| Daily 9am VN | Linear daily digest → Discord channel `#mmw-dev` (Linear → Slack/Discord integration) |
| Weekly Mon 9am | Auto-post cycle summary: completed, in progress, blocked |

**Files:** `.github/CODEOWNERS` (NEW), Linear automation rules (UI), `docs/operations/multi-dev-playbook.md` (NEW)
**Effort:** 1.5h

---

## D5. Onboarding Doc + Issue Templates (Gap 4 — P1)

### `docs/operations/dev-onboarding.md` (NEW)

Sections:

1. **First-day setup** (30 min):
   - Clone repo, run `make setup` (creates venv, installs hooks)
   - Linear account access (anh invites via team settings)
   - GitHub repo collaborator + Linear integration check
2. **Workflow cheat sheet**:
   - Picking task: Linear Backlog → drag to Todo → click "Copy branch name" → checkout
   - During work: commits, status auto-syncs khi push first commit
   - Opening PR: use template, ensure `Closes MMW-XXX` present
   - DoD: CI green + 1 approval + Linear status auto-moved to Done after merge
3. **Conventions index** (links to existing docs):
   - Branch naming → §D3
   - Commit message → `docs/operations/contribution.md` (existing)
   - Doc updates → `MEMORY.md` rules (kebab-case, no auto-delete)
4. **Where to ask**:
   - Spec questions → Linear comment on issue
   - Infra/setup → Discord `#mmw-dev`
   - Founder review → tag `@anh` in PR

### Issue templates (Linear)

| Template | Required fields |
|----------|-----------------|
| **Feature** | Phase, Feature ID (F01-F17), spec link, acceptance criteria |
| **Bug** | Repro steps, expected vs actual, severity, affected version |
| **Chore** | Scope, why now, impact if not done |
| **Docs** | Which doc, what changes, audience |

**Linear UI:** Settings → Team → Templates → create 4 templates above.

**Files:** `docs/operations/dev-onboarding.md` (NEW), Linear templates (UI)
**Effort:** 2h (mostly writing onboarding doc với screenshots)

---

## D6. CI Integration + Branch Protection (Gap 5 — P1)

### Linear ↔ CI sync — GitHub Actions calls Linear GraphQL (Option A)

**Architecture clarification:** Linear webhooks do NOT receive GitHub `check_run` events directly. GitHub check events fire from GitHub's webhook system. To propagate them to Linear, **GitHub Actions** listens and calls Linear's GraphQL API.

```
GitHub Actions trigger
  on: [check_run, pull_request, pull_request_review]
       │
       ▼
  workflow: linear-status-sync.yml
       │
       ▼
  Steps:
    1. Extract Linear issue ID from PR body (`Closes MMW-\d+`)
    2. Determine new state based on event:
       - check_run.conclusion == 'failure'  → add label `ci-failing`
       - check_run.conclusion == 'success'  → remove label `ci-failing`
       - review.state == 'changes_requested' → add label `changes-requested`
       - review.state == 'approved' AND all checks pass → ready-to-merge comment
       - PR merged → status `Done` (via magic word, but also explicit API call for reliability)
    3. Call Linear GraphQL `issueUpdate` / `issueAddLabel`
       Auth: secret `LINEAR_API_KEY` stored in GitHub repo secrets
```

### Why Option A vs Option B (Railway aggregator)

| Aspect | Option A (GH Actions → Linear) | Option B (Railway aggregator) |
|--------|:------------------------------:|:-----------------------------:|
| Simplicity | ✅ One workflow file | ❌ Backend service + 2 webhook endpoints |
| Latency | ~5-30s | ~2-5s |
| Failure mode | Workflow re-run on failure | Need retry queue logic |
| Solo / early team fit | ✅ Recommended | ❌ Over-engineering |
| Future scale (>5 dev) | OK | Consider migration |

**Decision (lean for early team):** Option A. Re-evaluate if event volume exceeds GitHub Actions free minutes.

### Workflow file

`.github/workflows/linear-status-sync.yml` — implementation effort 1h (was 30 min in original D6.2).

### Branch protection (unchanged, just cleaned up)

The actual merge gate is GitHub branch protection — Linear labels are visibility only, NOT the gate. Branch protection rules (`main`):

| Rule | Setting |
|------|---------|
| Require PR | Yes |
| Required approvals | 1 (2 nếu touch `core/` or `markets/*/adapters/`) |
| Required status checks | `ci/pytest`, `ci/lint`, `ci/import-linter`, `ci/pr-validate` (branch name + magic word) |
| Require branches up to date | Yes |
| Restrict force-push | Yes |
| Restrict deletions | Yes |
| Required signatures | Optional (defer) |

### Deploy gate (post-merge)

| Check | Trigger | Block deploy if |
|-------|---------|-----------------|
| Smoke tests | After merge to `main` | Any smoke fail |
| Migration safety | Detect new migration file | No matching rollback script |
| Doc freshness | Detect API change | Touched spec không update version |

**Files:** `.github/branch-protection.json` (managed via Terraform OR manual UI), `.github/workflows/post-merge-smoke.yml` (extend existing), Linear automation rules
**Effort:** 1h

---

## D7. Implementation Tasks Tổng

| # | Task | Gap | Effort | Priority |
|---|------|-----|--------|----------|
| D2.1 | Verify Linear `project.progress` renders in dashboard Overview tab | 1 | 30 min | P0 |
| D3.1 | PR template + branch convention doc | 2 | 30 min | P0 |
| D3.2 | Git pre-push hook + CI validator (`ci/pr-validate` check) | 2 | 1h | P0 |
| D4.1 | Linear assignment + WIP rules setup | 3 | 30 min | P1 |
| D4.2 | CODEOWNERS + review rotation | 3 | 30 min | P1 |
| D4.3 | Standup automation (Linear → Discord) | 3 | 30 min | P1 |
| D5.1 | `dev-onboarding.md` write | 4 | 1.5h | P1 |
| D5.2 | 4 Linear issue templates | 4 | 30 min | P1 |
| D6.1 | Branch protection rules | 5 | 30 min | P1 |
| D6.2 | `.github/workflows/linear-status-sync.yml` (Option A) | 5 | 1h | P1 |

**Subtotal: ~6.5 giờ** (P0 ≈ 2h, P1 ≈ 4.5h)

*Note:* Creating 10 phase-Projects in Linear moved to **C3.1** (it's foundational structure, not multi-dev specific). Roadmap.md auto-edit script **removed** (anti-pattern per C6 contract).

---

## D8. Open Questions

| # | Question | Options | Lean |
|---|----------|---------|------|
| 1 | Linear Workspace seat count | Free tier = 10 seats. Đủ cho 3 dev? | Yes, free đủ early |
| 2 | Roadmap progress display | Dashboard live view vs auto-edit `roadmap.md` | **Dashboard live view; no roadmap auto-gen** (locked per C6 contract — `roadmap.md` is manual strategic doc, not operational mirror) |
| 3 | CODEOWNERS granularity | Per-file vs per-directory? | Per-directory (`core/`, `markets/`, `docs/`) |
| 4 | Standup channel | Discord vs Telegram? | Discord (richer formatting cho Linear digest) |
| 5 | WIP limit enforcement | Soft (warning) vs hard (block)? | Soft (trust team) |
| 6 | Branch protection 2-approval | Apply to all PRs vs only `core/`? | Only `core/` + adapters |

---

## D9. Migration Sequencing

Phần D nên ship **trước khi tuyển dev thứ 2** để dev mới onboard vào convention mới luôn, không phải sửa convention sau. Sequencing aligned with C5 mirror phases:

```
Week 1 (C5 Phase 0):  C2 setup (workspace/team/10 phase-projects/views/fields/rules) +
                      C3.0 free-tier verification
Week 2 (C5 Phase 1):  C3.1-C3.8 migration (mirror mode) +
                      D3 branch/PR convention (P0) +
                      D2.1 verify Linear progress renders
Week 3 (C5 Phase 2):  C4 Railway endpoint deployed +
                      Dashboard reads Linear via JSON +
                      D6 branch protection + CI sync workflow
Week 4 (C5 Phase 3):  D4 multi-dev playbook + D5 onboarding doc (P1) +
                      Archive tracker.md after 7-day drift-free window
Week 5:               Tuyển dev #2, onboard theo doc D5
```

---

# Implementation Order (Full)

```
A-P0-1  Fix polling interval (30 min)
A-P0-2  Rename + disclaimer (30 min)
        ↓ commit: fix(ops-dashboard): rate limit safe + naming clarity

A-P1-3  Self-host fetch URL (30 min)            [skip if C4 ships first — JSON endpoint supersedes]
A-P1-4  Script-safe DOM swap (1 hr)
        ↓ commit: feat(ops-dashboard): script-safe DOM swap

═══ C5 Phase 0: Linear infrastructure setup ═══
C-3.0   Free-tier verification (20 min)
C-2     Workspace + Engineering team + 10 phase Projects + Views +
        Labels + Custom Fields + Status state machine + Workflow rules (~2h)
        ↓ Linear infrastructure ready, no dashboard dep yet

═══ C5 Phase 1: Mirror migration ═══
C-3     PR + feature migration scripted + manual QA (~5h)
D-3     Branch + PR convention + pre-push hook + ci/pr-validate (1.5h) [P0]
D-2.1   Verify Linear project.progress renders (30 min) [P0]
        ↓ Linear sole source for new work; tracker.md still updated as mirror

═══ C5 Phase 2: Dashboard reads Linear ═══
C-4     Railway /ops-dashboard.json endpoint (Linear+GitHub aggregator) (~7h)
        ↓ commit: feat(ops-api): Railway dashboard endpoint with cache + fallback
D-6     Branch protection + linear-status-sync.yml workflow (1.5h) [P1]
        ↓ commit: feat(ci): branch protection + Linear status sync (Option A)

═══ B-phase upgrades (parallel-OK with above) ═══
B-1     Roadmap + doc-version parsing (still useful) (2-3h)
B-2     Tab UI: Overview/Features/PRs/Risks/Docs (4-5h)
B-3     Polish: Gantt, readiness, staleness (2h)
        ↓ commit(s): feat(ops-dashboard): v2 tab UI

═══ C5 Phase 3: Archive tracker after acceptance criteria met ═══
C-5.3   Archive tracker.md → docs/archive/ (30 min)
        ↓ commit: chore(docs): archive implementation-tracker after mirror window

═══ Multi-dev P1 (before hiring dev #2) ═══
D-4     Playbook + CODEOWNERS + standup auto (1.5h) [P1]
D-5     Onboarding doc + issue templates (2h) [P1]
        ↓ commit: docs(onboarding): dev playbook + templates

═══ Nice-to-have ═══
A-P2-5  Rate limit display (30 min)
A-P2-6  Unauth fallback (1 hr)
        ↓ commit: feat(ops-dashboard): rate limit UX + unauth fallback
```

**Total: ~27-32 giờ** (was 22-27h; C2/C3/C4 grew with realistic estimates + Railway backend + 4-phase migration). Order respects C5 mirror plan: no archival before 7-day drift-free window. D4-D5 ship trước khi tuyển dev #2.

---

## Changelog

| Version | Date | Notes |
|---------|------|-------|
| v1.0.0 | 2026-05-13 | Initial improvement plan. 6 bug fix items across P0/P1/P2. |
| v2.0.0 | 2026-05-13 | Merged v2 roadmap integration proposal. Added Phần B: multi-source parse, 5-tab UI, JSON intermediate, implementation tasks. Deleted separate v2 file. |
| v3.0.0 | 2026-05-13 | Added Phần C: Linear migration. Decision: Linear > GitHub Projects cho task management (auto PR sync, velocity, burndown, multi-dev scale). Migration plan: 1.5h setup + 1.5h dashboard API integration. Source of Truth: Linear (tasks) + roadmap.md (strategy). implementation-tracker.md deprecated. |
| v3.1.0 | 2026-05-13 | Review fixes: C2 "MVP Tracker" là View không phải Project (1 Project per phase P0-P8+PW); C4 rewrite → Railway `/ops-dashboard.json` live endpoint với cache+fallback (thay vì build-script approach); C5 4-phase mirror migration với acceptance criteria (thay vì 30-min deprecation); NEW C6 source-of-truth contract + anti-patterns; D6 GitHub Actions → Linear GraphQL Option A (thay vì sai phrasing "Linear webhook receives check_run"); C2 status state machine table 12 events; C3.0 free-tier verification gate; required-fields-before-Todo enforcement; D2 stripped to verify-only (anti-pattern: auto-edit roadmap.md). Realistic estimate 27–32h. Added Phần D: multi-dev readiness (5 gaps). |
