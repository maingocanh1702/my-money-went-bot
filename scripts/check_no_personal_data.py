#!/usr/bin/env python3
"""Fail the build if the maintainer's own data reaches the public repository.

This repository is open source so other people can run their own bot. The
maintainer's live deployment is a different, private repository. Keeping the
two apart was a manual step for a while, and it failed three times in two
days: real screenshots were restored unchecked, a real forwarded bank email
sat in a test fixture, and a real bank account number was spread across five
files. This check replaces "remember to sanitize" with something that fails.

Two mechanisms, because the risks differ:

* Known literals are matched by SHA-256 of the token, never by the value.
  Writing a bank account number into the guard that protects it would simply
  publish it again, so only hashes live here.

* Everything else is an allowlist. Shapes that could carry personal data —
  a SePay source key, a Hang Seng account or transaction id, the Apps Script
  credentials, any image under docs/ — must match a value that somebody
  deliberately added below. A new capture cannot arrive silently.

Run: python3 scripts/check_no_personal_data.py
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

# SHA-256 of lowercased literals that must never appear. Values intentionally absent.
BANNED_TOKEN_HASHES = {
    "e6ecf4d71db25b894c4fc4e4b1f2535ca8e204f667d1e062599216be6502b5ee": "maintainer's forwarder mailbox",
    "8046f96d41303ee1a317ce0cdabdd69cf2e4bd60417c465c938a1eef6e0d99b1": "maintainer's forwarder local-part",
    "71204b92f0d3a243f5ea3eec9375f838addd970f38f27a8687349d70f92f3e92": "production host label",
    "447c8cf7aee5ae931e86368f97b625182cb65578040d702c0f04589032fe2a77": "retired email webhook secret",
    "ef456036237202c9ad50e33b3961205c27c87cfbc11ad366939b97c48c0423ea": "a real bank account number",
    "ce937dafac10cca2cd698f66416f93b60e75583328325704934f6566f234d9d2": "a real Hang Seng account",
    "8da7ed7e9f7ee9137f791376bdb38d17f0de2801f6cd51f492f6eafb3eeca436": "a real Hang Seng account",
    "152649eba519a1ff8fd30015e613c9b4d5f7f180bc597d901c80eca1d967d5c9": "a real Hang Seng payee account",
    "4d2283735cfd8d78f653385a6f65b37f05836162176f8c3349b62f2dfdfbdd64": "a real Hang Seng transaction id",
    "32cb72eaa10f99f30faa56be5db4034e3c5dffd2ac673e9f8629bd44bfe9d54a": "a real Hang Seng reference number",
    "f2876f5f009f9b4b4926a71340d108c35f950a92f05d4e83347372a439368ef0": "a real merchant store code",
    "5a83e3d416130b51d84672430db102d600f24d0db25cb4f819d6bfd8d830297d": "a real account slug",
    "aff666685a5662baef9928a807d31be4724f9d290a2684633e64f8b57c06b70a": "the maintainer's Zalo chat id",
    "818503b40774d1eeffe7893a8d8df633b949c5e37f56f7626e5ba404ebb91612": "the maintainer's GCP service-account email",
    "06bd3dbf173f337103d1d69dc0875554a6676741289f3a718c5490d01b4a8086": "the maintainer's GCP project id",
    "ee311c213b03ccd0b0bf97b56ce537c50fbd48ff41f867cdd96ebaa5da46d207": "the maintainer's GCP service-account client id",
    "a2be7edf6a721fbdc669e8c88a7bcc0e424874061377b1fbe05d04e94ec0c1c8": "the maintainer's GCP service-account key id",
}

# Synthetic values the fixtures are allowed to use. Add here, deliberately.
ALLOWED_SEPAY_KEYS = {"1900123456", "1903888777", "1903999888", "1903999889"}
ALLOWED_HANGSENG = {"123-456XXX-789", "123-456999-789", "99XXXX111",
                    "HD12000000000001", "HD12999999999999",
                    "N50000000001", "N50000000002"}
# Images shipped with the repo. A new one must be added here on purpose.
ALLOWED_MEDIA = {
    "docs/screenshots/banner.png",
    "docs/screenshots/how-it-works.png",
    "docs/screenshots/features-architecture.png",
    "docs/screenshots/auto-categorize.png",
    "docs/screenshots/report-monthly.png",
    "docs/screenshots/report-monthly-category-telegram.png",
    "docs/screenshots/zalo-bot.PNG",
    "docs/media/my-money-went-bot-demo-preview.gif",
    "docs/media/my-money-went-bot-demo.mp4",
    "docs/media/my-money-went-bot-demo-thumbnail.jpg",
}
APPS_SCRIPT_PLACEHOLDERS = ("SET_YOUR_RAILWAY_WEBHOOK_EMAIL_URL", "SET_EMAIL_SECRET_IN_APPS_SCRIPT")

TOKEN = re.compile(r"[A-Za-z0-9_.+@*-]{5,}")
SEPAY_KEY = re.compile(r"sepay:([0-9]{6,})")
# Only the shapes a Hang Seng notification actually uses: a dashed account, or
# a bank-masked one. A plain run of digits is left to the SePay rule above.
HANGSENG_ACCT = re.compile(r"\b\d{2,3}-\d{3}[X\d]{3}-\d{3}\b|\b\d{2}X{4}\d{3}\b")
HANGSENG_ID = re.compile(r"\b(?:HD\d{14,}|N\d{10,})\b")
TEXT_SUFFIX = {".py", ".js", ".cjs", ".md", ".yml", ".yaml", ".json", ".txt", ".sh", ".ini", ".toml", ".example"}


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def main() -> int:
    findings: list[str] = []
    self_path = "scripts/check_no_personal_data.py"

    for rel in tracked_files():
        path = Path(rel)

        if rel.startswith(("docs/screenshots/", "docs/media/")) and rel not in ALLOWED_MEDIA:
            findings.append(
                f"{rel}: image or recording is not in ALLOWED_MEDIA. Open it, confirm it "
                f"shows no account identifier, then add it to the allowlist on purpose."
            )
            continue

        if path.suffix not in TEXT_SUFFIX or rel == self_path:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for token in set(TOKEN.findall(text)):
            digest = hashlib.sha256(token.lower().encode()).hexdigest()
            if digest in BANNED_TOKEN_HASHES:
                findings.append(f"{rel}: contains {BANNED_TOKEN_HASHES[digest]}")

        for key in set(SEPAY_KEY.findall(text)):
            if key not in ALLOWED_SEPAY_KEYS:
                findings.append(f"{rel}: SePay source key 'sepay:{key}' is not a known synthetic value")

        for match in set(HANGSENG_ACCT.findall(text)) | set(HANGSENG_ID.findall(text)):
            if match not in ALLOWED_HANGSENG:
                findings.append(f"{rel}: '{match}' looks like a real Hang Seng identifier")

        if rel == "google_apps_script.js":
            for placeholder in APPS_SCRIPT_PLACEHOLDERS:
                if placeholder not in text:
                    findings.append(
                        f"{rel}: expected the placeholder {placeholder}. The deployed Apps "
                        f"Script carries the real value; this file must not."
                    )

    if findings:
        print("Personal data check FAILED:\n")
        for f in sorted(set(findings)):
            print(f"  - {f}")
        print(
            "\nThis repository is public and is meant for other people to run their own bot.\n"
            "Nothing from a live deployment belongs in it."
        )
        return 1

    print(f"Personal data check passed ({len(tracked_files())} tracked files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
