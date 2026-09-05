"""Cap lai token Facebook KEM QUYEN ADS (ads_management + ads_read).

Token cu trong state/fb_token.json chi co quyen dang bai, khong chay duoc ads.
Them scope BAT BUOC phai xin lai token tu dau - khong "nang cap" tai cho duoc.

3 che do:
  --check              Chi soi token hien tai (scope + goi that /me/adaccounts). Khong ghi gi.
  --oauth              Luong OAuth day du: mo trinh duyet, bat code ve localhost, doi token.
  --paste "<token>"    Dan token ngan han lay tu Graph API Explorer, script lo phan con lai.

Sau khi lay duoc token, script LUON:
  1. Doi sang long-lived user token (60 ngay -> khong het han neu la page token)
  2. Lay page access token cua Sintech PC Gaming & Gear
  3. Verify scope bang debug_token
  4. Goi THAT /me/adaccounts - HTTP 200 moi tinh la dat
  5. Backup file cu roi moi ghi de

Chi ghi de fb_token.json khi CA 2 buoc verify deu qua.
"""

import argparse
import io
import json
import shutil
import sys
import threading
import urllib.parse
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

GRAPH = "https://graph.facebook.com/v21.0"
TOKEN_PATH = Path(__file__).resolve().parent.parent.parent / "state" / "fb_token.json"

# Giu nguyen scope cu (de fb_scheduler dang bai khong gay) + them 2 scope ads
SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "business_management",
    "ads_management",
    "ads_read",
]
ADS_SCOPES = {"ads_management", "ads_read"}

REDIRECT_PORT = 8765
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/fb-callback"


def load_cfg():
    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def app_token(cfg):
    return f"{cfg['app_id']}|{cfg['app_secret']}"


def debug_token(cfg, token):
    r = requests.get(
        f"{GRAPH}/debug_token",
        params={"input_token": token, "access_token": app_token(cfg)},
        timeout=30,
    )
    return r.json().get("data", {})


def probe_ads(token):
    """Goi that endpoint ads. Tra (ok, mo_ta)."""
    r = requests.get(
        f"{GRAPH}/me/adaccounts",
        params={"access_token": token, "fields": "id,name,account_status,currency"},
        timeout=30,
    )
    if r.status_code == 200:
        accts = r.json().get("data", [])
        return True, accts
    return False, r.json().get("error", {}).get("message", r.text[:200])


# ---------------------------------------------------------------- che do check

def cmd_check(cfg):
    print(f"File token : {TOKEN_PATH}")
    print(f"App        : {cfg['app_id']}")
    print(f"Page       : {cfg.get('page_name')} ({cfg.get('page_id')})")
    print()

    for key in ("user_access_token", "page_access_token"):
        if key not in cfg:
            continue
        d = debug_token(cfg, cfg[key])
        scopes = set(d.get("scopes") or [])
        exp = d.get("expires_at")
        print(f"=== {key} ===")
        print(f"  loai      : {d.get('type')}")
        print(f"  con song  : {d.get('is_valid')}")
        print(f"  het han   : {'khong bao gio' if exp == 0 else datetime.fromtimestamp(exp) if exp else '?'}")
        print(f"  scopes    : {sorted(scopes)}")
        thieu = ADS_SCOPES - scopes
        print(f"  quyen ads : {'DU' if not thieu else 'THIEU ' + ', '.join(sorted(thieu))}")
        print()

    ok, info = probe_ads(cfg["user_access_token"])
    print("=== Goi that /me/adaccounts ===")
    if ok:
        print(f"  HTTP 200 - {len(info)} tai khoan quang cao:")
        for a in info:
            print(f"    {a.get('id')}  {a.get('name')}  status={a.get('account_status')}  {a.get('currency')}")
    else:
        print(f"  TU CHOI - {info}")
    return ok


# ---------------------------------------------------------------- che do oauth

class _Catcher(BaseHTTPRequestHandler):
    code = None
    error = None

    def do_GET(self):
        q = urllib.parse.urlparse(self.path)
        if not q.path.startswith("/fb-callback"):
            self.send_response(404)
            self.end_headers()
            return
        p = urllib.parse.parse_qs(q.query)
        _Catcher.code = p.get("code", [None])[0]
        _Catcher.error = p.get("error_description", p.get("error", [None]))[0]
        body = (
            "<h2>Xong roi, dong tab nay di ve terminal nhe.</h2>"
            if _Catcher.code
            else f"<h2>Loi: {_Catcher.error}</h2>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, *a):
        pass


def cmd_oauth(cfg):
    auth_url = "https://www.facebook.com/v21.0/dialog/oauth?" + urllib.parse.urlencode(
        {
            "client_id": cfg["app_id"],
            "redirect_uri": REDIRECT_URI,
            "scope": ",".join(SCOPES),
            "response_type": "code",
            "auth_type": "rerequest",  # ep FB hoi lai ca scope da tung tu choi
        }
    )
    print("Dang mo trinh duyet. Neu khong tu mo, dan link nay vao Chrome:\n")
    print(auth_url + "\n")
    print(f"Dang cho FB tra code ve {REDIRECT_URI} ...")
    print("(Neu FB bao 'URL Blocked' -> vao App > Facebook Login > Settings,")
    print(f" them '{REDIRECT_URI}' vao o Valid OAuth Redirect URIs roi chay lai.)\n")

    srv = HTTPServer(("localhost", REDIRECT_PORT), _Catcher)
    webbrowser.open(auth_url)
    srv.serve_forever()
    srv.server_close()

    if not _Catcher.code:
        print(f"Khong lay duoc code. Loi: {_Catcher.error}")
        return None

    r = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "client_id": cfg["app_id"],
            "client_secret": cfg["app_secret"],
            "redirect_uri": REDIRECT_URI,
            "code": _Catcher.code,
        },
        timeout=30,
    )
    if r.status_code != 200:
        print(f"Doi code that bai: {r.text[:300]}")
        return None
    return r.json()["access_token"]


# ------------------------------------------------------- doi token + ghi file

def to_long_lived(cfg, short_token):
    r = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": cfg["app_id"],
            "client_secret": cfg["app_secret"],
            "fb_exchange_token": short_token,
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise SystemExit(f"Doi long-lived that bai: {r.text[:300]}")
    return r.json()


def fetch_page_token(user_token, page_id):
    r = requests.get(
        f"{GRAPH}/me/accounts",
        params={"access_token": user_token, "fields": "id,name,access_token"},
        timeout=30,
    )
    if r.status_code != 200:
        raise SystemExit(f"Lay page token that bai: {r.text[:300]}")
    for p in r.json().get("data", []):
        if p["id"] == page_id:
            return p["access_token"], p["name"]
    have = [f"{p['id']} ({p['name']})" for p in r.json().get("data", [])]
    raise SystemExit(f"Khong thay page {page_id}. Token nay quan ly: {have}")


def finalize(cfg, short_user_token):
    print("\n-> Doi sang long-lived user token ...")
    lt = to_long_lived(cfg, short_user_token)
    user_token = lt["access_token"]

    print("-> Lay page access token ...")
    page_token, page_name = fetch_page_token(user_token, cfg["page_id"])

    # --- CONG VERIFY 1: scope
    print("-> Verify scope bang debug_token ...")
    d = debug_token(cfg, user_token)
    scopes = set(d.get("scopes") or [])
    thieu = ADS_SCOPES - scopes
    print(f"   scopes: {sorted(scopes)}")
    if thieu:
        print(f"\nDUNG LAI. Token moi VAN THIEU: {', '.join(sorted(thieu))}")
        print("Luc duyet vo phai bam 'Cho phep' ca muc quang cao. Chay lai --oauth.")
        print("KHONG ghi de file - token cu con nguyen.")
        return False

    # --- CONG VERIFY 2: goi that
    print("-> Goi that /me/adaccounts ...")
    ok, info = probe_ads(user_token)
    if not ok:
        print(f"\nDUNG LAI. Scope co nhung API van tu choi: {info}")
        print("Thuong la vo chua co vai tro tren tai khoan quang cao do.")
        print("KHONG ghi de file - token cu con nguyen.")
        return False
    print(f"   HTTP 200 - {len(info)} tai khoan quang cao:")
    for a in info:
        print(f"     {a.get('id')}  {a.get('name')}  status={a.get('account_status')}  {a.get('currency')}")

    # --- ghi file
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = TOKEN_PATH.with_suffix(f".json.bak.{stamp}")
    shutil.copy2(TOKEN_PATH, bak)
    print(f"\n-> Backup token cu: {bak.name}")

    page_dbg = debug_token(cfg, page_token)
    cfg.update(
        {
            "user_access_token": user_token,
            "page_access_token": page_token,
            "page_name": page_name,
            "scopes": sorted(scopes),
            "ad_accounts": [{"id": a.get("id"), "name": a.get("name")} for a in info],
            "user_token_expires_in_days": round(lt.get("expires_in", 0) / 86400, 1) if lt.get("expires_in") else "khong het han",
            "page_token_never_expires": page_dbg.get("expires_at") == 0,
            "last_rotated_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"-> Da ghi {TOKEN_PATH}")
    print("\nXONG. Chay lai `--check` de xac nhan lan cuoi.")
    return True


def main():
    ap = argparse.ArgumentParser(description="Cap token FB kem quyen ads")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="Chi soi token hien tai")
    g.add_argument("--oauth", action="store_true", help="Luong OAuth qua trinh duyet")
    g.add_argument("--paste", metavar="TOKEN", help="Dan token tu Graph API Explorer")
    args = ap.parse_args()

    cfg = load_cfg()

    if args.check:
        cmd_check(cfg)
        return

    short = cmd_oauth(cfg) if args.oauth else args.paste.strip()
    if not short:
        return
    finalize(cfg, short)


if __name__ == "__main__":
    main()
