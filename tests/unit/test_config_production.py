"""Production configuration accepts either supported Google credential source."""
import importlib.util
from pathlib import Path
import pytest
from google.oauth2.service_account import Credentials


def _load_config(monkeypatch, name="config_production_test"):
    root = Path(__file__).resolve().parents[2]
    # Do not reload a developer's local .env while testing a production-shaped
    # process environment.
    import dotenv
    monkeypatch.setattr(dotenv, "load_dotenv", lambda: False)
    spec = importlib.util.spec_from_file_location(name, root / "config.py")
    assert spec and spec.loader
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


def test_production_validates_google_credentials_file(monkeypatch, tmp_path):
    credential_path = tmp_path / "credentials.json"
    credential_path.write_text("{}", encoding="utf-8")
    required = {
        "BOT_TOKEN": "123456:production-token",
        "CHAT_ID": "123",
        "SHEET_ID": "sheet-id",
        "GOOGLE_CREDS": str(credential_path),
        "SEPAY_SECRET": "sepay-secret",
        "TELEGRAM_WEBHOOK_SECRET": "telegram-secret",
        "EMAIL_SECRET": "email-secret",
        "CRON_SECRET": "cron-secret",
    }
    for name, value in required.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("GOOGLE_CREDS_JSON", raising=False)
    seen = []
    monkeypatch.setattr(
        Credentials,
        "from_service_account_file",
        staticmethod(lambda path: seen.append(path) or object()),
    )

    config = _load_config(monkeypatch, "config_file_credentials_test")

    assert config.CREDS_FILE == str(credential_path)
    assert seen == [str(credential_path)]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("GOOGLE_CREDS", "/definitely/missing/credentials.json"),
        ("GOOGLE_CREDS_JSON", "not-json"),
    ],
)
def test_production_rejects_unusable_google_credentials(monkeypatch, name, value):
    required = {
        "BOT_TOKEN": "123456:production-token",
        "CHAT_ID": "123",
        "SHEET_ID": "sheet-id",
        "SEPAY_SECRET": "sepay-secret",
        "TELEGRAM_WEBHOOK_SECRET": "telegram-secret",
        "EMAIL_SECRET": "email-secret",
        "CRON_SECRET": "cron-secret",
    }
    for env_name, env_value in required.items():
        monkeypatch.setenv(env_name, env_value)
    monkeypatch.delenv("GOOGLE_CREDS", raising=False)
    monkeypatch.delenv("GOOGLE_CREDS_JSON", raising=False)
    monkeypatch.setenv(name, value)

    with pytest.raises(RuntimeError, match="Invalid Google credentials"):
        _load_config(monkeypatch, f"config_invalid_{name}")
