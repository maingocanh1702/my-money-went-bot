"""Guards for the 2026-09-08 audit's security fixes.

Each test here pins a defect that was live in production, so a regression is
a failing test rather than a quiet re-opening.
"""
import main
import sheets as sh
import utils
from config import SHEETS as S


# ─── /trigger/* authentication ───────────────────────────────────

def test_cron_secret_accepted_in_authorization_header(monkeypatch):
    """A long-lived secret must not have to travel in the query string."""
    monkeypatch.setattr(main, "CRON_SECRET", "s3cret")
    assert main._cron_authorized("", "Bearer s3cret") is True
    assert main._cron_authorized("", "bearer s3cret") is True   # scheme is case-insensitive
    assert main._cron_authorized("", "Apikey s3cret") is True


def test_cron_secret_header_rejects_wrong_value(monkeypatch):
    monkeypatch.setattr(main, "CRON_SECRET", "s3cret")
    assert main._cron_authorized("", "Bearer wrong") is False
    assert main._cron_authorized("", "s3cret") is False          # no scheme
    assert main._cron_authorized("", "Basic s3cret") is False    # wrong scheme
    assert main._cron_authorized("", "Bearer ") is False
    assert main._cron_authorized("", None) is False


def test_cron_secret_query_string_still_works(monkeypatch):
    """An existing crontab must not break when the header path lands."""
    monkeypatch.setattr(main, "CRON_SECRET", "s3cret")
    assert main._cron_authorized("s3cret") is True
    assert main._cron_authorized("wrong", "Bearer wrong") is False


def test_every_trigger_route_reads_the_authorization_header():
    """A new /trigger/* route that forgets the header would authenticate by
    query string alone, quietly undoing this fix."""
    import inspect
    routes = [r for r in main.app.routes
              if getattr(r, "path", "").startswith("/trigger/")]
    assert routes, "no /trigger/* routes found"
    for route in routes:
        params = inspect.signature(route.endpoint).parameters
        assert "authorization" in params, f"{route.path} ignores the Authorization header"


# ─── Interactive docs are off in production ──────────────────────

def test_openapi_schema_is_not_served():
    """/docs and /openapi.json enumerate every webhook and spell out how
    /trigger/* authenticates. Nothing needs them on a public host."""
    assert main.app.docs_url is None
    assert main.app.redoc_url is None
    assert main.app.openapi_url is None
    served = {getattr(r, "path", "") for r in main.app.routes}
    assert "/docs" not in served
    assert "/openapi.json" not in served
    assert "/redoc" not in served


# ─── Bank data never reaches stdout ──────────────────────────────

def test_transaction_write_does_not_log_amount_or_source_key(fake_ss, capsys):
    ws = fake_ss.add_worksheet(S.TRANSACTIONS)
    ws.update("A1:T1", [[
        "ID", "Date", "C", "D", "E", "Description", "Type", "Amount",
        "Ref", "Cumulative", "ParentCat", "SubCat", "IsDaily", "Confirmed",
        "Month", "Currency", "account_id", "tx_type", "linked_tx_row",
        "ledger_applied",
    ]])
    """`src_key` IS the bank account number, and stdout is retained by the
    host and shipped to whatever log drain is attached."""
    sh.append_transaction(
        "2026-09-08T10:00:00", "COFFEE SHOP", 1234567, "REFSEC1", "2026-09",
        account_id="acc_main", ledger_tx_type="expense",
        account_source_key="sepay:1903999888",
    )
    out = capsys.readouterr().out
    assert "1903999888" not in out
    assert "1234567" not in out
    assert "src_key_set=True" in out          # the useful half is still there


def test_ledger_append_does_not_log_the_amount(fake_ss, capsys):
    fake_ss.add_worksheet(S.LEDGER)
    sh.append_ledger_entry(
        tx_row_num=2, account_id="acc_main", direction="-",
        amount=987654, currency="VND", tx_type="expense",
    )
    out = capsys.readouterr().out
    assert "987654" not in out
    assert "acc=acc_main" in out


# ─── Untrusted bank memo cannot inject Markdown ──────────────────

def test_recat_picker_escapes_the_bank_memo():
    """A memo is attacker-controlled: anyone who can send the owner money
    chooses its text. Rendered raw inside a code span, a leading backtick
    closes the span and the rest becomes live Markdown."""
    hostile = "`[Xac nhan](http://evil.example)"
    escaped = utils.md_safe(hostile)
    assert "`" not in escaped
    assert escaped != hostile

    src = open("main.py", encoding="utf-8").read()
    assert 'msg += f"  -{amount_str} `{md_safe(desc)}` {status}\\n"' in src, \
        "the /recat picker must escape the description like every other call site"


def test_no_unescaped_description_interpolation_in_markdown_sends():
    """Catch the next site that forgets md_safe, not just this one."""
    import re
    src = open("main.py", encoding="utf-8").read()
    offenders = re.findall(r'`\{(desc|description)\}`', src)
    assert not offenders, f"unescaped memo interpolated into Markdown: {offenders}"
