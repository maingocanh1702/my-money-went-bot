"""Production configuration accepts either supported Google credential source."""
import importlib.util
from pathlib import Path


def test_production_accepts_google_credentials_file(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    required = {
        "BOT_TOKEN": "123456:production-token",
        "CHAT_ID": "123",
        "SHEET_ID": "sheet-id",
        "GOOGLE_CREDS": "credentials.json",
        "SEPAY_SECRET": "sepay-secret",
        "TELEGRAM_WEBHOOK_SECRET": "telegram-secret",
        "EMAIL_SECRET": "email-secret",
        "CRON_SECRET": "cron-secret",
    }
    for name, value in required.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("GOOGLE_CREDS_JSON", raising=False)

    spec = importlib.util.spec_from_file_location("config_file_credentials_test", root / "config.py")
    assert spec and spec.loader
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)

    assert config.CREDS_FILE == "credentials.json"
