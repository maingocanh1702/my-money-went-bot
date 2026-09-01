// The exact shape a readiness.json (the Level 3 readiness-evidence file) may carry — and nothing
// more. `autopilot-review-readiness.mjs` presence/value-checks these keys but historically accepted
// any ADDITIONAL key silently, so the permission classifier was the only thing standing between a
// writer self-asserting extra state (a nested "notes", a "fix_round_count", an invented
// "verification" field) and the gate. That surfaced a true positive on 2026-08-11. This module turns
// the rule into a deterministic, greppable check the gate owns.
//
// Keep this in EXACT agreement with docs/autopilot-manifests/_READINESS_EVIDENCE_TEMPLATE.json; the
// sibling test (autopilot-ephemeral-review-worktree.test.mjs) fails closed if they ever drift.

export const READINESS_EVIDENCE_KEYS = Object.freeze([
  "evidence_schema_version",
  "task_id",
  "feature",
  "base_sha",
  "head_sha",
  "acceptance",
  "breakers",
]);
export const READINESS_ACCEPTANCE_KEYS = Object.freeze(["status"]);
export const READINESS_BREAKER_KEYS = Object.freeze(["status"]);

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

// Pure: return the fully-qualified path of every key OUTSIDE the whitelist — at the top level and
// inside `acceptance`/`breakers`. An empty array means the evidence carries only the allowed
// identity, acceptance and breaker state. No halting and no I/O: the caller maps a non-empty result
// to its own halt, so exit behaviour stays with the gate and this stays unit-testable. A non-object
// evidence value is left to the gate's existing identity/`requireObject` checks (returns []).
export function findUnknownEvidenceKeys(evidence) {
  if (!isPlainObject(evidence)) {
    return [];
  }
  const unknown = Object.keys(evidence).filter((key) => !READINESS_EVIDENCE_KEYS.includes(key));
  for (const [field, allowedKeys] of [
    ["acceptance", READINESS_ACCEPTANCE_KEYS],
    ["breakers", READINESS_BREAKER_KEYS],
  ]) {
    const nested = evidence[field];
    if (isPlainObject(nested)) {
      for (const key of Object.keys(nested)) {
        if (!allowedKeys.includes(key)) {
          unknown.push(`${field}.${key}`);
        }
      }
    }
  }
  return unknown;
}

// Key names come from writer-controlled readiness.json, so they are untrusted data even though they
// are only reported, never executed. Render them safely for the gate's single-line stderr diagnostic.
//
// The rule is deliberately whole-class, not per-character: EVERY code point outside printable ASCII
// (0x20-0x7E), plus the delimiters " and \, is escaped as \uXXXX / \u{...}. JSON.stringify was not
// enough — it leaves C1 controls (U+0080-U+009F, e.g. U+009B CSI) and Unicode format/separator code
// points (U+2028/U+2029, bidi overrides) raw, and terminals/log processors still act on those. By
// emitting ONLY printable ASCII we close the entire control/format-injection class at once: a key can
// never forge a `HALT <CODE>:` line a watchdog or the gate's own parser reads. Count and per-key
// output length are capped so an evidence file with tens of thousands of keys cannot flood the log.
const MAX_REPORTED_KEYS = 10;
const MAX_KEY_LENGTH = 80;

function escapeChar(ch) {
  if (ch === "\\") return "\\\\";
  if (ch === '"') return '\\"';
  const code = ch.codePointAt(0);
  if (code >= 0x20 && code <= 0x7e) return ch;
  if (code <= 0xffff) return `\\u${code.toString(16).padStart(4, "0")}`;
  return `\\u{${code.toString(16)}}`;
}

// Build the escaped, quoted form char by char and stop once the payload reaches MAX_KEY_LENGTH, so one
// giant (or all-control) key cannot bloat the line and no multi-char escape is ever split mid-sequence.
function renderUnknownKey(key) {
  let out = "";
  for (const ch of key) {
    if (out.length >= MAX_KEY_LENGTH) {
      return `"${out}...(len ${key.length})"`;
    }
    out += escapeChar(ch);
  }
  return `"${out}"`;
}

// Pure: turn the raw offending-key paths into ONE bounded, injection-safe line for the halt message.
// Shows at most MAX_REPORTED_KEYS and appends "(+N more)" so the omitted count is never silent.
export function describeUnknownEvidenceKeys(keys) {
  const shown = keys.slice(0, MAX_REPORTED_KEYS).map(renderUnknownKey);
  const omitted = keys.length - shown.length;
  return omitted > 0 ? `${shown.join(", ")} (+${omitted} more)` : shown.join(", ");
}
