# Feature Spec Template (FE)

> **Use this template** khi tạo `docs/features/feature-<name>.md` mới.
> **Linter:** `python -m tools.autopilot lint <feature-id>` validate spec trước khi autopilot consume.
> **Existing 17 specs** đã follow format này — template chỉ formalize sections + thêm 2 optional autopilot blocks.

---

<!-- autopilot:meta
feature_id: F##           # F01, F02, ... hoặc F-<name> nếu chưa có số
branch: feat/F##-<short>  # branch name autopilot sẽ dùng
phase: <1-6>              # phase number theo implementation-tracker.md
wave: <0-6>               # wave number theo development-workflow.md §4
depends_on: []            # list feature_id của các PR phải merge trước
be_doc: docs/features/BE/feature-<name>-tech.md
risk_tier: low|medium|high  # high → MUST use Mode 4, không Level 3
-->

# Feature: <Tên> — <Tagline> (<F##>)

> **Version:** v1.0.0
> **Ngày tạo:** YYYY-MM-DD
> **Trạng thái:** Draft | Ready | Locked | Implemented
> **Owner:** Founder (dev)
> **Phase:** Phase <N>
> **Tham chiếu:** [TDD §X.Y](../tdd-vi.md) · [Related feature](feature-<x>.md)

---

## 1. Mô tả

<1-2 đoạn. Vì sao build, key decisions, scope boundary. Cụ thể, không marketing.>

**Key decisions:**
- <decision 1>
- <decision 2>

---

## 2. Use Cases + Edge Cases

### 2.1. Use Cases

| # | Actor | Hành động | Kết quả |
|---|-------|-----------|---------|
| 1 | <actor> | <action> | <expected outcome> |

### 2.2. Edge Cases

| # | Category | Case | Xử lý |
|---|----------|------|-------|
| 1 | Data Integrity / Concurrency / Cross-Feature / Security | <case> | <handling> |

---

## 3. Screens & States

<UI mockups (ASCII or screenshot link), state transitions. N/A nếu pure backend feature → ghi rõ "N/A — backend only".>

---

## 4. Domain Model

<Entities, relationships, state enum. Nếu chỉ dùng existing tables → liệt kê columns đụng vào.>

---

## 5. API Endpoints

<HTTP routes / Telegram commands / webhook handlers. N/A nếu không expose surface mới → ghi "N/A".>

---

## 6. Error Codes

| Code | Khi nào | User message |
|------|---------|--------------|
| | | |

---

## 7. Analytics Events

| Event | Trigger | Properties |
|-------|---------|------------|
| | | |

---

## 8. State Machine

<Diagram (mermaid OK) hoặc table state→event→next-state. N/A nếu stateless.>

---

## 9. Caching Strategy

<TTL, invalidation triggers. N/A nếu không cache.>

---

## 10. Acceptance Criteria

<Checkbox list, mỗi dòng 1 testable invariant. Linter yêu cầu ≥3 items. Tránh từ mập mờ ("works", "good", "fast"). Mỗi item phải map về test concrete.>

- [ ] <invariant 1, testable>
- [ ] <invariant 2>
- [ ] <invariant 3>

---

<!-- autopilot:gaps
# Liệt kê mọi unknown trước khi paste autopilot. Linter sẽ FAIL nếu còn open gap.
# Format: gap-id | question | decision | rationale
# Status: OPEN | CLOSED | DEFERRED:<where>
- id: G1
  question: <design question>
  status: OPEN | CLOSED
  decision: <if CLOSED, the locked answer>
  rationale: <why this choice>
  alternatives_rejected: <briefly>
-->

<!-- autopilot:test_plan
# 5 categories per Wave 0 lesson #4. Linter checks all 5 present (mark N/A if not applicable, with reason).
happy_path:
  - <test name>: <intent>
retry_idempotency:
  - <test name>: <intent>
  # OR: N/A — pure read function, no state mutation
missing_optional_fields:
  - <test name>: <intent>
pathological_inputs:
  - <test name>: <intent>
concurrent_access:
  - <test name>: <intent>
  # OR: N/A — single-user feature
-->

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| v1.0.0 | YYYY-MM-DD | Initial. |
