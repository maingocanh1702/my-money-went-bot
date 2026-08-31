"""Smoke test for the FakeWorksheet — make sure the test infra itself works."""


def test_update_and_get_all_values(fake_ws):
    ws = fake_ws("Test", header=["a", "b", "c"])
    ws.update("A2:C2", [["1", "2", "3"]])
    rows = ws.get_all_values()
    assert rows[0] == ["a", "b", "c"]
    assert rows[1] == ["1", "2", "3"]


def test_col_values_truncates_at_last_nonempty(fake_ws):
    ws = fake_ws("X", header=["h"])
    ws.update("A2:A2", [["v1"]])
    ws.update("A4:A4", [["v3"]])
    # col_values returns up to last non-empty (row 4)
    assert ws.col_values(1) == ["h", "v1", "", "v3"]


def test_update_cell(fake_ws):
    ws = fake_ws("Y", header=["a", "b"])
    ws.update_cell(2, 2, "hello")
    assert ws.cell(2, 2).value == "hello"


def test_append_row(fake_ws):
    ws = fake_ws("Z", header=["a"])
    ws.append_row(["v1"])
    ws.append_row(["v2"])
    assert ws.get_all_values() == [["a"], ["v1"], ["v2"]]
