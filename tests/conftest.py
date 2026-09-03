"""tests/conftest.py — shared fixtures.

Sets dummy env vars before any project import so config.py loads in test mode.
Provides an in-memory `fake_ws` that mimics enough of gspread's Worksheet API
for unit tests to exercise sheets.py functions without hitting Google.
"""
import os
import re
import sys
import pytest

# Project root on sys.path so `import sheets`, `import handlers...` work.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Required by config.py at import time. Use harmless dummies for unit tests.
os.environ.setdefault("BOT_TOKEN", "test:dummy")
os.environ.setdefault("CHAT_ID", "0")
os.environ.setdefault("SHEET_ID", "test_sheet_id")
os.environ.setdefault("GOOGLE_CREDS", "credentials.json")  # not actually opened in unit tests


def _col_letter_to_idx(letter: str) -> int:
    """A→0, B→1, ..., Z→25, AA→26."""
    n = 0
    for ch in letter.upper():
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


_RANGE_RE = re.compile(r"^([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?$")


class FakeWorksheet:
    """In-memory worksheet supporting the subset of gspread API used by sheets.py.

    Stores rows as `list[list[str]]`, row 0 is header. Cells autopad on writes.
    """

    def __init__(self, header: list[str] | None = None):
        self._rows: list[list[str]] = []
        self._row_count: int = 100_000  # simulate large sheet
        self.title: str = "FakeSheet"
        if header:
            self._rows.append([str(c) for c in header])

    @property
    def row_count(self) -> int:
        return max(self._row_count, len(self._rows))

    def resize(self, rows: int = 0, cols: int = 0) -> None:
        """Simulate gspread worksheet resize."""
        if rows:
            self._row_count = rows

    def _ensure_size(self, row_idx: int, col_idx: int):
        while len(self._rows) <= row_idx:
            self._rows.append([])
        row = self._rows[row_idx]
        while len(row) <= col_idx:
            row.append("")

    def get_all_values(self) -> list[list[str]]:
        # gspread normalizes row width to the widest row
        if not self._rows:
            return []
        width = max(len(r) for r in self._rows)
        return [r + [""] * (width - len(r)) for r in self._rows]

    def col_values(self, col: int) -> list[str]:
        # 1-indexed col. Returns up to last non-empty cell in that column.
        idx = col - 1
        out: list[str] = []
        last_nonempty = -1
        for i, r in enumerate(self._rows):
            v = r[idx] if idx < len(r) else ""
            out.append(v)
            if v != "":
                last_nonempty = i
        return out[: last_nonempty + 1]

    def row_values(self, row: int) -> list[str]:
        # 1-indexed
        idx = row - 1
        if idx < 0 or idx >= len(self._rows):
            return []
        return list(self._rows[idx])

    def cell(self, row: int, col: int):
        idx_r, idx_c = row - 1, col - 1
        v = ""
        if 0 <= idx_r < len(self._rows) and idx_c < len(self._rows[idx_r]):
            v = self._rows[idx_r][idx_c]

        class _Cell:
            value = v

        return _Cell()

    def update_cell(self, row: int, col: int, value):
        idx_r, idx_c = row - 1, col - 1
        self._ensure_size(idx_r, idx_c)
        self._rows[idx_r][idx_c] = str(value) if value is not None else ""

    def update(self, range_str: str, values: list[list]):
        m = _RANGE_RE.match(range_str.strip())
        if not m:
            raise ValueError(f"FakeWorksheet.update: bad range {range_str!r}")
        c1, r1, c2, r2 = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        start_r, start_c = r1 - 1, _col_letter_to_idx(c1)
        end_c = _col_letter_to_idx(c2) if c2 else start_c + len(values[0]) - 1
        end_r = (int(r2) - 1) if r2 else start_r + len(values) - 1

        for ri, row in enumerate(values):
            for ci, val in enumerate(row):
                self._ensure_size(start_r + ri, start_c + ci)
                self._rows[start_r + ri][start_c + ci] = (
                    str(val) if val is not None else ""
                )
        # Pad any missing cells in the range
        self._ensure_size(end_r, end_c)

    def append_row(self, row: list):
        self._rows.append([str(v) if v is not None else "" for v in row])

    def batch_update(self, data: list[dict]):
        """Mimic gspread's batch_update — each entry is {range, values}.
        We just dispatch to .update() per entry so range parsing stays in
        one place.
        """
        for entry in data:
            self.update(entry["range"], entry["values"])


class FakeSpreadsheet:
    """Holds a dict of sheet_name → FakeWorksheet."""

    def __init__(self):
        self._sheets: dict[str, FakeWorksheet] = {}

    def worksheet(self, name: str) -> FakeWorksheet:
        if name not in self._sheets:
            import gspread

            raise gspread.WorksheetNotFound(name)
        return self._sheets[name]

    def add_worksheet(self, title: str, rows: int = 100, cols: int = 26) -> FakeWorksheet:
        ws = FakeWorksheet()
        self._sheets[title] = ws
        return ws


@pytest.fixture
def fake_ss(monkeypatch):
    """Patch sheets._get_spreadsheet to return an in-memory FakeSpreadsheet."""
    import sheets as sh

    ss = FakeSpreadsheet()
    monkeypatch.setattr(sh, "_get_spreadsheet", lambda: ss)
    monkeypatch.setattr(sh, "_sheet", lambda name: ss.worksheet(name))
    # Reset module-level caches so tests are isolated
    sh._buckets_cache = {}
    sh._tx_rows_cache.update({"ts": 0.0, "rows": None})
    sh._processed_refs.clear()
    sh._reset_processed_ref_cache()
    sh._keyword_rules_cache = None
    sh._state_cache.clear()
    sh._state_row_cache.clear()
    sh._accounts_cache = None
    sh._mcc_exclusion_cache = None
    sh._mcc_map_cache = None
    return ss


@pytest.fixture
def fake_ws(fake_ss):
    """Convenience: return a callable to create/get a sheet by name."""

    def _get_or_create(name: str, header: list[str] | None = None):
        if name not in fake_ss._sheets:
            ws = fake_ss.add_worksheet(name)
            if header:
                ws.update(
                    f"A1:{chr(ord('A') + len(header) - 1)}1", [list(header)]
                )
            return ws
        return fake_ss._sheets[name]

    return _get_or_create
