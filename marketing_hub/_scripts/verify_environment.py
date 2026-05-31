"""Kiem tra moi truong truoc khi chay Marketing Hub.

Chay: python _scripts/verify_environment.py
Bao cao thieu package, thieu secret file, thieu path.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import importlib
from pathlib import Path

ROOT = Path(__file__).parent.parent
OK = "  [OK]"
WARN = "  [WARN]"
FAIL = "  [FAIL]"

errors = []
warnings = []


def check(label, ok, msg=""):
    if ok:
        print(f"{OK}  {label}")
    else:
        print(f"{FAIL}  {label}" + (f" — {msg}" if msg else ""))
        errors.append(label)


def warn(label, msg=""):
    print(f"{WARN}  {label}" + (f" — {msg}" if msg else ""))
    warnings.append(label)


# ── 1. Python version ──────────────────────────────────────────────
print("\n=== Python ===")
ver = sys.version_info
check(f"Python >= 3.10 (current {ver.major}.{ver.minor})", ver >= (3, 10))

# ── 2. Core packages ───────────────────────────────────────────────
print("\n=== Core packages ===")
CORE_PACKAGES = [
    ("flask", "Flask"),
    ("requests", "requests"),
    ("apscheduler", "APScheduler"),
    ("PIL", "Pillow"),
    ("bs4", "beautifulsoup4"),
    ("lxml", "lxml"),
    ("markdown", "markdown"),
    ("anthropic", "anthropic"),
    ("openai", "openai"),
    ("openpyxl", "openpyxl"),
]
for mod, pkg in CORE_PACKAGES:
    try:
        importlib.import_module(mod)
        print(f"{OK}  {pkg}")
    except ImportError:
        print(f"{FAIL}  {pkg} — pip install {pkg}")
        errors.append(pkg)

# ── 3. Google packages ─────────────────────────────────────────────
print("\n=== Google packages ===")
GOOGLE_PACKAGES = [
    ("google.genai", "google-genai"),
    ("googleapiclient.discovery", "google-api-python-client"),
    ("google.auth", "google-auth"),
    ("google.auth.transport.requests", "google-auth"),
    ("google_auth_oauthlib.flow", "google-auth-oauthlib"),
    ("google_auth_httplib2", "google-auth-httplib2"),
]
for mod, pkg in GOOGLE_PACKAGES:
    try:
        importlib.import_module(mod)
        print(f"{OK}  {pkg} ({mod})")
    except ImportError:
        print(f"{FAIL}  {pkg} — pip install {pkg}")
        errors.append(pkg)

# ── 4. Local config ────────────────────────────────────────────────
print("\n=== Local config ===")
cfg_file = ROOT / "config.local.json"
check("config.local.json tồn tại", cfg_file.exists(),
      "copy config.local.json.example → config.local.json rồi điền path")

if cfg_file.exists():
    import json
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    for key in ("LIBRARY_ROOT", "WORKSPACE_ROOT", "PYTHON_BIN", "DESKTOP_SINTECH"):
        val = cfg.get(key)
        if not val:
            warn(f"config.local.json thiếu key '{key}'")
        else:
            path_ok = Path(val).exists()
            if not path_ok:
                warn(f"{key} = {val}", "path không tồn tại")
            else:
                print(f"{OK}  {key} = {val}")

# ── 5. Secret files ────────────────────────────────────────────────
print("\n=== Secret files ===")
SECRETS = [
    (ROOT / "state" / "haravan_token.json", "Haravan token"),
    (ROOT / "state" / "fb_token.json", "Facebook token"),
    (ROOT / ".secrets" / "google_token.json", "Google OAuth token"),
    (ROOT / "state" / "flask_secret.txt", "Flask secret key"),
    (ROOT / "state" / "psi_config.json", "PageSpeed Insights API key"),
]
for path, label in SECRETS:
    if path.exists():
        size = path.stat().st_size
        if size < 5:
            warn(f"{label} ({path.name})", "file rỗng")
        else:
            print(f"{OK}  {label} ({path.name})")
    else:
        warn(f"{label} ({path.name})", "không tìm thấy — một số tính năng sẽ lỗi")

# ── 6. DB ──────────────────────────────────────────────────────────
print("\n=== Database ===")
db_path = ROOT / "data" / "posts.db"
if db_path.exists():
    size_mb = db_path.stat().st_size / 1024 / 1024
    print(f"{OK}  posts.db ({size_mb:.0f} MB)")
else:
    warn("posts.db chưa tồn tại", "sẽ được tạo lần đầu chạy app.py")

# ── 7. Key paths (LIBRARY_ROOT) ────────────────────────────────────
print("\n=== Paths ===")
try:
    sys.path.insert(0, str(ROOT))
    import local_config as lc
    lib = Path(lc.get("LIBRARY_ROOT", ""))
    check(f"LIBRARY_ROOT = {lib}", lib.exists(), "tạo folder hoặc cập nhật config.local.json")
    inbox = lib / "_inbox"
    if lib.exists() and not inbox.exists():
        warn("FB-Library/_inbox chưa có", "mkdir sẽ được tạo tự động khi upload")
except Exception as e:
    warn("Không load được local_config", str(e))

# ── Summary ────────────────────────────────────────────────────────
print()
if errors:
    print(f"[FAIL] {len(errors)} lỗi cần fix: {', '.join(errors)}")
    print("       Chạy: pip install -r requirements.txt")
elif warnings:
    print(f"[WARN] {len(warnings)} cảnh báo (không chặn chạy app): {', '.join(warnings)}")
    print("[OK] Môi trường sẵn sàng chạy app.py")
else:
    print("[OK] Môi trường đầy đủ — sẵn sàng chạy app.py")
