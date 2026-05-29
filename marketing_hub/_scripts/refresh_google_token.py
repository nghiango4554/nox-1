"""Re-auth Google OAuth (Sheets scope).

Chạy: py -3.12 marketing_hub/_scripts/refresh_google_token.py
Sẽ in URL → vợ mở browser → chọn Gmail → Allow → token lưu lại.
"""
from __future__ import annotations
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

SECRETS = Path(__file__).resolve().parent.parent.parent / ".secrets"
OAUTH = SECRETS / "google_oauth.json"
TOKEN = SECRETS / "google_token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

print(f"[*] Client secrets: {OAUTH}")
print(f"[*] Token đầu ra:   {TOKEN}")

flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH), SCOPES)
# Timeout 5 phút (mặc định 60s) — vợ click chậm vẫn OK
creds = flow.run_local_server(
    port=8765,
    prompt="consent",
    access_type="offline",
    open_browser=False,
    timeout_seconds=900,
    authorization_prompt_message=(
        "\n=== OAUTH URL ===\n"
        "{url}\n"
        "=== Vợ copy URL trên, dán vào browser, chọn Gmail Sintech, bấm Allow ===\n"
    ),
)

if TOKEN.exists():
    bak = TOKEN.with_suffix(".json.bak")
    bak.write_bytes(TOKEN.read_bytes())
    print(f"[+] Backup token cũ -> {bak.name}")

TOKEN.write_text(creds.to_json(), encoding="utf-8")
print(f"[+] Token mới đã lưu. Scope: {creds.scopes}")
print(f"[+] Refresh token: {'YES' if creds.refresh_token else 'NO'}")

svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
meta = svc.spreadsheets().get(
    spreadsheetId="1rsNjlEJRxTWaMFnGhmKErTsZlZB4CDsXbpPPpr7XNLQ"
).execute()
print(f'[+] TEST read sheet OK: "{meta["properties"]["title"]}"')
