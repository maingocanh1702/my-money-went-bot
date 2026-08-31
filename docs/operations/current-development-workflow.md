# Quy trình phát triển sản phẩm hiện tại — MyMoneyWent

> **Loại:** Synthesis / tổng hợp (rút ra từ các docs quy trình hiện có)
> **Ngày tạo:** 2026-06-01
> **Trạng thái:** Snapshot — phản ánh quy trình đang áp dụng tại thời điểm tổng hợp
> **Nguồn rút ra:**
> - `CLAUDE.md` (repo root) — hard rules + 3-lane risk-based policy
> - `docs/operations/dev-workflow/development-workflow.md` (v1.1.0) — 11-step manual workflow + Wave graph
> - `docs/autopilot/orchestrator-usage.md` (v0.1.0) — autopilot orchestrator
> - `docs/autopilot/autopilot-prompt-template.md` — risk tier × merge policy
> - `docs/operations/dev-workflow/feature-lockdown-decisions.md` — lockdown trước autopilot
> - `docs/START_HERE.md`, `docs/mymoneywent-roadmap.md`, `docs/implementation-tracker.md`

---

## 0. Bức tranh tổng thể

Quy trình có **2 lớp thực thi cùng một logic** — bản thủ công và bản tự động hóa codify lại chính nó:

```
Spec (FE + BE) → LINT → PREFLIGHT → Codegen → Verify → Codex review/fix loop → Gates → Merge to main
```

- **Manual:** quy trình 11 bước per-feature (`development-workflow.md`).
- **Autopilot:** `python -m tools.autopilot run <feature>` — orchestrator chạy đúng 11 bước đó, có circuit breaker và state checkpoint (`orchestrator-usage.md`).

Autopilot **không thay thế** quy trình thủ công; nó là cùng quy trình được tự động hóa cho các feature đã lock spec + đúng tier rủi ro.

---

## 1. Nguyên tắc nền (áp dụng cho mọi lane)

1. **Spec-first** — không code khi chưa đọc xong FE spec (`features/feature-<name>.md`) + BE tech spec (`features/BE/feature-<name>-tech.md`). Phát hiện gap → **dừng, sửa spec trước**, không code theo giả định.
2. **Cross-model review** — Claude Code viết → **Codex review** (2 model bắt lỗi khác nhau, layered defense). Self-review code **không được phép** cho P1/Foundation.
3. **Test cùng session** — unit + integration (real Postgres) + **tenant isolation test BẮT BUỘC** cho mọi feature chạm DB. Không test → không merge.
4. **1 feature = 1 branch = 1 PR** — squash-merge vào `main`, kể cả solo dev (audit trail + rollback boundary).
5. **Refactor trước, build features sau** — Wave 0 foundation (`core/` + `markets/`) trước, không build feature trên cấu trúc legacy.

---

## 2. Vòng đời 1 feature (11 bước, 0–10)

| Bước | Nội dung |
|------|----------|
| **0** | **Brainstorm** — chỉ khi chưa có spec. AI đóng vai *CTO skeptic*: pushback, challenge assumption (max 5 round). Output PHẢI là spec, không phải code. Skip nếu spec đã tồn tại. |
| **1** | Đọc spec FE + BE tech. Spec gap → dừng, update spec. |
| **2** | Skill `engineering:testing-strategy` → draft test plan (positive / edge / error / isolation / contract). |
| **3** | Plan ngắn ≤10 dòng: files, tests, contracts, migration risk. |
| **4** | Tạo branch `<type>/MYM-<id>-<slug>` (vd `feat/MYM-123-funding-sources`). |
| **5** | Code + viết test **trong cùng session**: unit (parser/rule/formatter) · integration (real Postgres via testcontainers) · **tenant isolation** (bắt buộc nếu chạm DB) · contract test (messenger adapter, bank email parser). |
| **6** | Test local pass → **atomic commits** (mỗi commit 1 logical change, dễ review). |
| **7** | `/codex:review` trên branch — logic + performance + security. |
| **8** | Bug → fix → mini-review trên diff fix → test lại. 2 round liên tiếp pass → tiếp tục. |
| **9** | CHANGELOG entry. **Không bump spec version** khi iterate in-session (chỉ bump khi consumer đã pin version cũ). |
| **10** | PR → squash-merge `<id>: <title>` → update `START_HERE.md` "Current next tasks" + `implementation-tracker.md` status. |

**Fixture strategy:** real captured (SePay payload thật, `.eml` từng bank) cho happy path; synthetic cho edge/error deterministic. Đặt ở `tests/fixtures/real/` và `tests/fixtures/synthetic/`.

---

## 3. Phân lane theo rủi ro (risk tier × merge policy)

Quy trình phân tầng theo **risk tier**, quyết định mức review và quyền merge. Đây là phần tiến hóa mới nhất (CLAUDE.md + autopilot template).

| Tier | Codegen tự động? | Codex review | Merge policy |
|------|:---:|---|---|
| **P0** (security/data, migration không đảo ngược) | ❌ Không | N/A | Manual hoàn toàn. Template chỉ dùng để sinh checklist/review, không sinh implementation. |
| **P1** (foundation, orchestrator, multi-tenant logic) | ✅ | 2× clean liên tiếp | `manual_only` — STOP_AT_READY, founder tự squash + sign-off. |
| **P2 pilot** (<3 lần autopilot chạy thành công trên class này) | ✅ | 1× clean | `manual_only` — STOP_AT_READY. |
| **P2 mature** (≥3 lần thành công) | ✅ | 2× clean liên tiếp | `auto_merge` **chỉ khi** truyền cờ `--auto-merge` rõ ràng; mặc định vẫn manual. |

**Quy tắc vàng:** auto-merge là **opt-in per prompt, không bao giờ default**. Unclear → STOP_AT_READY.

### 3 lane tương ứng (review cap)

- **Fast Lane** — max 2 review round; được self-review cho docs/generated/cosmetic/low-risk.
- **Standard Lane** — max 5 round; cross-model review bắt buộc.
- **Foundation Lane** — max 8 round (founder duyệt sau round 5); **không bao giờ auto-merge**; founder approval = manual squash + sign-off xác nhận acceptance criteria / blast radius / gates.

Vượt cap → split feature / manual review, không loop vô hạn.

---

## 4. Autopilot orchestrator (bản tự động)

Lệnh: `lint <id>` → `preflight` → `run <id> [--auto-merge]` (walk away). Halt → đọc `halt-report.md`, fix, `resume <id>`.

**Phases:** INIT (preflight + spec lint) → A Codegen (claude) → B Verify (ruff/black/mypy/lint-imports/pytest, ALL pass) → C Review/fix loop (codex + claude, tới khi đủ clean round) → D Gates → E Merge (squash).

**Circuit breakers (12+, halt khi trip):** ARCH_FINDING, SECURITY_FINDING, CONCURRENCY_FINDING, RECURRING_FINDING, MAX_ROUNDS, VERIFY_REGRESSION, TYPE_IGNORE_PROPOSED, SECRETS_FINDING, CODEGEN_FAILED, MERGE_GATE_FAIL, **REGION_THRASH** (PR phình một vùng fragile), **CODEX_UNAVAILABLE** (không bao giờ thay bằng self-review).

**Không dùng autopilot cho:** Wave 0 foundation, feature security-critical (payment/admin auth), migration có backfill, lần đầu dùng tool/lib mới → manual.

**Lock trước khi chạy:** lock toàn bộ decisions (branch, scope, test plan, acceptance criteria) trong lockdown doc trước khi sinh prompt — `feature-lockdown-decisions.md`.

---

## 5. Wave dependency graph (thứ tự build)

```
Wave 0 Foundation (SEQUENTIAL, 6 PR: W0.1 → W0.6)
   ↓
Wave 1 User entry (parallel: onboarding, admin, i18n, settings)
   ↓
Wave 2 Core capture (SEQUENTIAL: funding-sources → transaction-capture)
   ↓
Wave 3 Money mgmt (parallel: category-mgmt, categorization, personal/business toggle)
   ↓
Wave 4 Outputs (SEQUENTIAL: reports → scheduled-jobs)
   ↓
Wave 5 Monetization (SEQUENTIAL: pricing-tiers → payment)

Wave 6 Channels (parallel với Wave ≥3: discord, messenger — dùng adapter từ W0)
```

**Solo dev:** tối đa **2 branch song song** (1 chính + 1 filler), dùng `git worktree` để mỗi session có checkout riêng.

---

## 6. Quality gates (CI-enforced, chặn merge)

1. **pre-commit** — ruff, black (force-exclude legacy), mypy strict trên `core|markets|i18n|tests`, detect-secrets, import-linter, dashboard auto-rebuild.
2. **`lint-imports`** — 5 contract (ADR-0001: `core/ ↛ markets/`; `markets/vn ↮ markets/global_`; email parsers pure; `i18n/` pure data).
3. **`pytest tests/`** — testcontainers spin real Postgres; tenant isolation test mandatory.
4. **Branch name** match `^[a-z0-9-]+/MYM-[0-9]+-[a-z0-9-]+$`.
5. **PR body** chứa `Closes/Fixes/Ref MYM-NNN` hoặc `Linear: N/A`.

---

## 7. Hard rules (đọc mỗi session)

1. **STRICT 1 Claude Code session / `.git/`** — đã có 3 sự cố ref-clobber. Parallel → `git worktree`.
2. **NEVER auto-xóa file `.md`** — destructive op trên docs → PAUSE, hỏi founder.
3. **Spec-first** — gap → dừng, sửa spec.
4. **Tenant isolation test mandatory** cho feature chạm DB.
5. **Cross-model review mandatory cho P1/P0** (Standard/Foundation).
6. **Auto-merge opt-in, không default.** Foundation không bao giờ auto-merge.
7. **Autopilot prompt: single-phase scope là default**; mega-prompt chỉ với per-phase checkpoint.
8. **Review cap theo lane** (Fast 2 / Standard 5 / Foundation 8).
9. **Autopilot/Codex blocked** → theo manual fallback, không silently retry, không bypass gate.

---

## 8. Phân cấp source-of-truth (docs)

| Nội dung | Canonical file |
|----------|----------------|
| PR hiện tại / next task | `docs/implementation-tracker.md` |
| Phase timeline + % | `docs/mymoneywent-roadmap.md` |
| Per-feature plan | `docs/implementation-plans/phase-*.md` |
| Feature spec (FE) | `docs/features/feature-<name>.md` |
| Feature spec (BE) | `docs/features/BE/feature-<name>-tech.md` |
| Workflow thực thi | `docs/operations/dev-workflow/development-workflow.md` |
| Autopilot | `docs/autopilot/` |
| ADRs | `docs/adr/` |

---

## Phụ lục — Khoảng cách phát hiện được (gợi ý dọn dẹp)

Khi tổng hợp, phát hiện một số tham chiếu trong `CLAUDE.md` trỏ tới file không đúng vị trí / chưa tồn tại:

- `CLAUDE.md` trỏ `docs/operations/fast-quality-workflow.md` và `docs/operations/manual-fallback-playbook.md` — **chưa tồn tại** trong repo.
- `CLAUDE.md` trỏ `docs/operations/development-workflow.md`, nhưng file thực nằm ở `docs/operations/dev-workflow/development-workflow.md`.
- Mô hình 3-lane / risk-tier hiện sống rải rác trong `CLAUDE.md` + `autopilot-prompt-template.md`, **chưa có doc canonical riêng**.

→ Nên: tạo `fast-quality-workflow.md` canonical (hợp nhất phần 3-lane), sửa lại đường dẫn trong `CLAUDE.md`, hoặc dùng chính doc này làm điểm hợp nhất.
