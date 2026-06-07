"""Re-auth Google Search Console API (canonical token).

Chạy: py -3.12 marketing_hub/_scripts/gsc_api_auth.py
Sẽ in URL → vợ mở browser → chọn Gmail GSC sintech.vn → Allow → token lưu lại.

Scope DUY NHẤT: webmasters.readonly.
Output canonical: nox-1/.secrets/gsc_api_token.json (derive từ file, KHÔNG cwd/hard-code).
KHÔNG ghi đè google_token.json (Sheets) / ga4_token.json (GA4). KHÔNG log token value.
"""
from __future__ import annotations
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

SECRETS = Path(__file__).resolve().parent.parent.parent / ".secrets"   # nox-1/.secrets
OAUTH = SECRETS / "gsc_oauth.json"
TOKEN = SECRETS / "gsc_api_token.json"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
SITE = "sc-domain:sintech.vn"

print(f"[*] OAuth client: {OAUTH}")
print(f"[*] Token đầu ra: {TOKEN}")
print(f"[*] Scope:        {SCOPES[0]}")

if not OAUTH.exists():
    print(f"[!] Thiếu OAuth client {OAUTH} — dừng.")
    sys.exit(1)

flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH), SCOPES)
creds = flow.run_local_server(
    port=8766, prompt="consent", access_type="offline", open_browser=False,
    timeout_seconds=900,
    authorization_prompt_message=(
        "\n=== OAUTH URL ===\n"
        "{url}\n"
        "=== Vợ copy URL trên, dán vào browser, chọn Gmail GSC sintech.vn, bấm Allow ===\n"
    ),
)

if TOKEN.exists():
    bak = TOKEN.with_suffix(".json.bak")
    bak.write_bytes(TOKEN.read_bytes())
    print(f"[+] Backup token cũ -> {bak.name}")

TOKEN.write_text(creds.to_json(), encoding="utf-8")
print(f"[+] Token mới đã lưu. Scope: {creds.scopes}")
print(f"[+] Refresh token: {'YES' if creds.refresh_token else 'NO'}")

# Smoke test: list verified properties (không in token)
svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
sites = svc.sites().list().execute().get("siteEntry", [])
mine = [s for s in sites if s.get("siteUrl") == SITE]
print(f"[+] TEST sites: {len(sites)} property | {SITE}: "
      f"{mine[0]['permissionLevel'] if mine else 'NOT FOUND'}")
