# -*- coding: utf-8 -*-
"""Batch sync ảnh content collection lên Haravan.

Mỗi cate: resize ảnh local -> 600px -> upload Theme Assets -> chèn <img> đúng vị trí
(1 dưới intro · giàn đều thân · 1 trên 'Mua tại Sintech') -> sync collection.

An toàn:
- Backup-một-lần body GỐC vào data/cc_img_backup/<handle>.html (luôn dựng ảnh từ bản gốc -> idempotent).
- Lỗi 1 cate KHÔNG dừng batch. Retry upload cho 5xx. Rate-limit sleep.
"""
import io, sys, re, json, time, base64, sqlite3, unicodedata, traceback
from pathlib import Path
import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import collection_content_writer as ccw

CFG = json.loads((Path(__file__).parent.parent / "state" / "haravan_token.json").read_text(encoding="utf-8"))
H = {"Authorization": f"Bearer {CFG['access_token']}", "Content-Type": "application/json"}
APIS = "https://apis.haravan.com"
MAIN_THEME_FALLBACK = 1001494160  # theme live hiện tại (role=main) — fallback nếu query lỗi
_MAIN_THEME_CACHE = None


def get_main_theme_id():
    """Lấy theme id đang chạy (role=main) ĐỘNG — tránh hardcode bị stale khi đổi/backup theme.
    Cache 1 lần/process. Lỗi mạng → dùng fallback."""
    global _MAIN_THEME_CACHE
    if _MAIN_THEME_CACHE:
        return _MAIN_THEME_CACHE
    try:
        themes = requests.get(f"{APIS}/web/themes.json", headers=H, timeout=30).json().get("themes", [])
        for t in themes:
            if t.get("role") == "main":
                _MAIN_THEME_CACHE = t["id"]
                return _MAIN_THEME_CACHE
    except Exception:
        pass
    _MAIN_THEME_CACHE = MAIN_THEME_FALLBACK
    return _MAIN_THEME_CACHE
TARGET_W = 600
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
RESIZED_ROOT = Path(r"C:\Users\NGHIANGO\Desktop\Sintech-img\pic content carte\research _1200x675")
DB = str(Path(__file__).parent / "data" / "posts.db")
BACKUP_DIR = Path(__file__).parent / "data" / "cc_img_backup"
LOG = Path(__file__).parent / "data" / "cc_img_sync.log"
SKIP_HANDLES = {"wifi-mesh"}  # đã làm thử rồi


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn").replace("đ", "d")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def resize_bytes(p: Path, w: int = TARGET_W) -> bytes:
    im = Image.open(p).convert("RGB")
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85, optimize=True)
    return buf.getvalue()


def upload_asset(img_bytes: bytes, key: str) -> str:
    payload = {"asset": {"key": f"assets/{key}", "attachment": base64.b64encode(img_bytes).decode("ascii")}}
    last = None
    for attempt in range(4):
        r = requests.put(f"{APIS}/web/themes/{get_main_theme_id()}/assets.json", headers=H, json=payload, timeout=90)
        if r.status_code in (200, 201):
            return r.json()["asset"]["public_url"]
        last = f"HTTP {r.status_code}"
        time.sleep(2 + attempt * 2)
    raise RuntimeError(f"upload '{key}' fail: {last}")


def img_block(url, alt):
    return (f'<p style="text-align: center;"><img src="{url}" alt="{alt}" '
            f'style="max-width: 600px; width: 100%; height: auto; border-radius: 8px;" /></p>')


def strip_our_imgs(body, handle):
    pat = (r'<p style="text-align: center;"><img [^>]*src="[^"]*cc-'
           + re.escape(handle) + r'-[^"]*"[^>]*>\s*</p>')
    return re.sub(pat, "", body)


def insertion_points(body, title, n):
    """Trả list (offset, h2_text) — N vị trí chèn (snap H2, giàn đều theo nội dung)."""
    h2s = [(m.start(), re.sub(r"<[^>]+>", "", m.group(1)).strip().replace("&amp;", "&"))
           for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", body, re.I | re.S)]
    if len(h2s) < 2:
        return []
    faq_idx = next((i for i, (_, t) in enumerate(h2s)
                    if "câu hỏi thường gặp" in t.lower() or "faq" in t.lower()), len(h2s))
    if faq_idx > 0 and any(w in h2s[faq_idx - 1][1].lower() for w in ("sintech", "mua")):
        outro_idx = faq_idx - 1
    else:
        outro_idx = min(faq_idx, len(h2s) - 1)
    first_body = 1 if norm(h2s[0][1]) and norm(h2s[0][1]) in norm(title) else 0
    if outro_idx <= first_body:
        outro_idx = len(h2s) - 1
    cand = [(h2s[j][0], j, h2s[j][1]) for j in range(first_body, outro_idx + 1)]
    if not cand:
        return []
    k = min(n, len(cand))
    if k == 1:
        return [(cand[0][0], cand[0][2])]
    span0, span1 = cand[0][0], cand[-1][0]
    used, chosen = set(), []
    for i in range(k):
        tgt = span0 + (span1 - span0) * i / (k - 1)
        best = min((o for o in cand if o[1] not in used), key=lambda o: abs(o[0] - tgt))
        used.add(best[1]); chosen.append((best[0], best[2]))
    chosen.sort()
    return chosen


def process_cate(folder: Path, job, short_name):
    handle = job["handle"]
    hv_id = job["haravan_id"]
    title = job["edited_title"]
    meta = job["edited_meta"] or ""
    imgs = sorted([p for p in folder.iterdir() if p.suffix.lower() in EXTS])
    if not imgs:
        return ("skip", "không có ảnh")

    # backup-một-lần bản gốc (sạch, chưa ảnh)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    bpath = BACKUP_DIR / f"{handle}.html"
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur_body = conn.execute("SELECT edited_body_html FROM collection_jobs WHERE handle=?", (handle,)).fetchone()[0]
    if not bpath.exists():
        bpath.write_text(strip_our_imgs(cur_body, handle), encoding="utf-8")
    base_body = bpath.read_text(encoding="utf-8")  # luôn dựng từ gốc

    pts = insertion_points(base_body, title, len(imgs))
    if not pts:
        conn.close()
        return ("skip", "không tìm được vị trí chèn (ít H2)")
    k = len(pts)

    inserts = []
    for idx, ((off, h2text), local) in enumerate(zip(pts, imgs[:k]), 1):
        b = resize_bytes(local)
        url = upload_asset(b, f"cc-{handle}-{idx:02d}.jpg")
        inserts.append((off, img_block(url, f"{short_name} - {h2text}")))
        time.sleep(0.4)

    new_body = base_body
    for off, html in sorted(inserts, key=lambda x: -x[0]):
        new_body = new_body[:off] + html + new_body[off:]

    conn.execute("UPDATE collection_jobs SET edited_body_html=? WHERE handle=?", (new_body, handle))
    conn.commit()
    conn.close()
    res = ccw.sync_collection_to_haravan(int(hv_id), title, meta, new_body)
    if not res.get("ok"):
        return ("fail", f"sync lỗi: {res.get('error','')[:100]}")
    return ("ok", f"{k} ảnh chèn + sync")


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    jobs = conn.execute(
        "SELECT handle, collection_title, haravan_id, edited_title, edited_meta, edited_body_html "
        "FROM collection_jobs WHERE edited_body_html IS NOT NULL AND edited_body_html!='' "
        "AND haravan_id IS NOT NULL AND edited_title IS NOT NULL AND edited_title!=''").fetchall()
    conn.close()
    by_norm = {norm(j["collection_title"]): j for j in jobs}
    by_norm_ns = {norm(j["collection_title"]).replace(" ", ""): j for j in jobs}  # fallback bỏ space

    folders = sorted([p for p in RESIZED_ROOT.iterdir() if p.is_dir()])
    log(f"=== BẮT ĐẦU batch: {len(folders)} folder ảnh · {len(jobs)} cate có content ===")
    ok = fail = skip = 0
    for f in folders:
        base = re.sub(r"\s*\(\d+\)\s*$", "", f.name).strip()
        job = by_norm.get(norm(base)) or by_norm_ns.get(norm(base).replace(" ", ""))
        if not job:
            log(f"⏭  {f.name}: không khớp cate có content"); skip += 1; continue
        if job["handle"] in SKIP_HANDLES:
            log(f"⏭  {f.name}: skip (đã làm)"); skip += 1; continue
        short = job["collection_title"]
        try:
            status, detail = process_cate(f, job, short)
            if status == "ok":
                ok += 1; log(f"✅ {job['handle']}: {detail}")
            elif status == "skip":
                skip += 1; log(f"⏭  {job['handle']}: {detail}")
            else:
                fail += 1; log(f"❌ {job['handle']}: {detail}")
        except Exception as e:
            fail += 1
            log(f"❌ {job['handle']}: EXC {e}")
            log(traceback.format_exc().splitlines()[-1])
        time.sleep(1.0)  # giãn giữa các cate
    log(f"=== XONG: ✅{ok} ❌{fail} ⏭{skip} ===")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    main()
