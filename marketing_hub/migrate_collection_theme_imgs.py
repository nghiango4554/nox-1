# -*- coding: utf-8 -*-
"""Migrate ảnh collection từ kho THEME -> product ẩn (kho ảnh), rồi xóa asset theme.

Per-collection ATOMIC + resume được:
  đọc body LIVE -> tìm img theme cc-* -> tải về local (GIỮ LẠI) -> upload kho product
  -> thay URL trong body (backup body gốc) -> PUT collection -> verify -> XÓA theme asset
     (chỉ xóa key KHÔNG bị collection khác dùng; xóa ở MỌI theme đang chứa key đó).

An toàn:
  - Không xóa asset nếu key còn được handle khác tham chiếu (ref_map snapshot lúc đầu).
  - Lỗi 1 collection KHÔNG dừng batch.
  - GIỮ file local (Desktop\\Sintech-img\\_theme_migrate\\<handle>\\) để vợ kiểm tra lại.
  - Kho đầy 90 -> tự chuyển kho kế (KHÔNG tạo SP mới).
"""
import io, sys, re, json, time, base64, sqlite3, traceback
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).parent))
import haravan_client as hc

CFG = json.loads((Path(__file__).parent.parent / "state" / "haravan_token.json").read_text(encoding="utf-8"))
H = {"Authorization": f"Bearer {CFG['access_token']}", "Content-Type": "application/json"}
APIS = "https://apis.haravan.com"
DB = str(Path(__file__).parent / "data" / "posts.db")
BACKUP_DIR = Path(__file__).parent / "data" / "cc_img_backup"
LOCAL_ROOT = Path(r"C:\Users\NGHIANGO\Desktop\Sintech-img\_theme_migrate")
LOG = Path(__file__).parent / "data" / "theme_migrate.log"
KHO_CFG = Path(__file__).parent / "state" / "kho_anh_products.json"
KHO_MAX = 90

THEME_IMG = re.compile(r'https://cdn\.hstatic\.net/themes/\d+/\d+/\d+/([^\s"\'?]+\.(?:jpg|jpeg|png|gif))(?:\?[^\s"\']*)?', re.I)


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_collection(cid):
    """Trả (ctype, key, data). ctype in {'smart_collections','custom_collections'}."""
    for ep, key in [("smart_collections", "smart_collection"), ("custom_collections", "custom_collection")]:
        try:
            d = hc._request("GET", f"/{ep}/{cid}.json")
            if d.get(key):
                return ep, key, d[key]
        except Exception:
            pass
    return None, None, None


def list_theme_ids_with_cc():
    """Quét mọi theme 1 lần -> dict {theme_id: set(asset_key)} cho key chứa 'cc-'."""
    out = {}
    try:
        themes = requests.get(f"{APIS}/web/themes.json", headers=H, timeout=60).json().get("themes", [])
    except Exception as e:
        log(f"WARN list themes fail: {e}")
        return out
    for t in themes:
        tid = t.get("id")
        try:
            assets = requests.get(f"{APIS}/web/themes/{tid}/assets.json", headers=H, timeout=60).json().get("assets", [])
            keys = {a["key"] for a in assets if "cc-" in a.get("key", "") and a["key"].lower().endswith((".jpg", ".jpeg", ".png", ".gif"))}
            if keys:
                out[tid] = keys
        except Exception as e:
            log(f"WARN assets theme {tid}: {e}")
    return out


def build_ref_map(rows):
    """asset_key (basename) -> set(handle) tham chiếu, từ DB SNAPSHOT lúc đầu."""
    ref = {}
    for h, body in rows:
        for fn in set(THEME_IMG.findall(body or "")):
            base = fn.split("/")[-1]
            ref.setdefault(base, set()).add(h)
    return ref


def load_kho():
    kho = json.loads(KHO_CFG.read_text(encoding="utf-8"))
    for k in kho:
        try:
            k["count"] = len(hc.get_product(k["id"]).get("images") or [])
        except Exception:
            k["count"] = 0
    return kho


def pick_kho(kho):
    for k in kho:
        if k["count"] < KHO_MAX:
            return k
    return None


def main():
    LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    import os
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    source = os.environ.get("MIGRATE_SOURCE", "db")
    if source == "live":
        live = []; page = 1
        while page <= 30:
            ps = hc.list_smart_collections(page=page, limit=50)
            if not ps:
                break
            live += ps
            if len(ps) < 50:
                break
            page += 1; time.sleep(0.3)
        rows_all = [{"handle": c.get("handle"), "haravan_id": c.get("id"), "edited_body_html": c.get("body_html", "") or ""} for c in live]
        log(f"LIVE scan: {len(rows_all)} collection")
    else:
        rows_all = [dict(r) for r in db.execute("SELECT handle, haravan_id, edited_body_html FROM collection_jobs WHERE haravan_id IS NOT NULL").fetchall()]
    ref_map = build_ref_map([(r["handle"], r["edited_body_html"]) for r in rows_all])
    theme_keys = list_theme_ids_with_cc()
    log(f"Themes chứa cc-asset: {[ (tid,len(ks)) for tid,ks in theme_keys.items() ]}")
    kho = load_kho()
    log(f"Kho: {[(k['name'], k['count']) for k in kho]}")

    MAX_BODY = int(os.environ.get("MIGRATE_MAX_BODY", "90000"))  # body dài hơn -> PUT 422 'Mô tả quá dài', bỏ qua
    targets = [r for r in rows_all if THEME_IMG.search(r["edited_body_html"] or "")]
    lim = os.environ.get("THEME_MIGRATE_LIMIT")
    if lim:
        targets = targets[:int(lim)]
    log(f"=== START migrate {len(targets)} collection ===")
    done = mig_imgs = skipped_del = 0
    for idx, r in enumerate(targets, 1):
        handle, cid = r["handle"], r["haravan_id"]
        try:
            ep, key, data = get_collection(cid)
            if not data:
                log(f"[{idx}/{len(targets)}] {handle}: SKIP (không đọc được collection)")
                continue
            body = data.get("body_html", "") or ""
            urls = []
            for m in THEME_IMG.finditer(body):
                urls.append(m.group(0))
            urls = list(dict.fromkeys(urls))  # dedup, giữ thứ tự
            if not urls:
                log(f"[{idx}/{len(targets)}] {handle}: đã sạch theme (skip)")
                continue
            if len(body) > MAX_BODY:
                log(f"[{idx}/{len(targets)}] {handle}: SKIP — body {len(body)} > {MAX_BODY} (vượt giới hạn PUT, xử tay)")
                continue
            outdir = LOCAL_ROOT / handle
            outdir.mkdir(parents=True, exist_ok=True)
            mapping = {}
            uploaded = []   # (kho_obj, image_id) để dọn nếu PUT fail
            put_ok = False
            for u in urls:
                base = THEME_IMG.search(u).group(1).split("/")[-1]
                lf = outdir / base
                if not lf.exists():
                    b = requests.get(u, timeout=60).content
                    lf.write_bytes(b)
                else:
                    b = lf.read_bytes()
                k = pick_kho(kho)
                if not k:
                    log("!!! HẾT KHO — dừng. Cần thêm SP kho.")
                    db.close(); return
                img = hc.add_product_image(k["id"], base64.b64encode(b).decode(), filename=base, alt=handle)
                src = img.get("src")
                if not src:
                    raise RuntimeError(f"upload {base} no src")
                k["count"] += 1
                uploaded.append((k, img.get("id")))
                mapping[u] = src
                mig_imgs += 1
            # thay URL + backup + PUT
            new = body
            for old, src in mapping.items():
                new = new.replace(old, src)
            (BACKUP_DIR / f"{handle}_pre_thememigrate.html").write_text(body, encoding="utf-8")
            hc._request("PUT", f"/{ep}/{cid}.json", payload={key: {"id": cid, "body_html": new}})
            put_ok = True
            db.execute("UPDATE collection_jobs SET edited_body_html=? WHERE haravan_id=?", (new, cid)); db.commit()
            # verify body live hết theme
            _, _, d2 = get_collection(cid)
            left = len(THEME_IMG.findall(d2.get("body_html", "") or ""))
            # xóa theme asset (an toàn)
            deleted = 0
            for u in urls:
                base = THEME_IMG.search(u).group(1).split("/")[-1]
                key_full = f"assets/{base}"
                owners = ref_map.get(base, set())
                if owners - {handle}:
                    skipped_del += 1
                    log(f"   GIỮ asset {base} (còn dùng bởi {owners - {handle}})")
                    continue
                for tid, ks in theme_keys.items():
                    if key_full in ks:
                        rr = requests.delete(f"{APIS}/web/themes/{tid}/assets.json", headers=H, params={"asset[key]": key_full}, timeout=60)
                        if rr.status_code == 200:
                            deleted += 1
                        time.sleep(0.2)
            done += 1
            log(f"[{idx}/{len(targets)}] {handle}: {len(urls)} ảnh -> kho ok | body theme còn={left} | xóa asset={deleted}")
        except Exception as e:
            log(f"[{idx}/{len(targets)}] {handle}: ERROR {type(e).__name__}: {str(e)[:160]}")
            # dọn ảnh orphan đã up nếu PUT chưa thành công (tránh rác trong kho)
            try:
                if not locals().get("put_ok", False):
                    for kk, iid in locals().get("uploaded", []):
                        if iid:
                            try:
                                hc._request("DELETE", f"/products/{kk['id']}/images/{iid}.json"); kk["count"] -= 1
                            except Exception:
                                pass
                    if locals().get("uploaded"):
                        log(f"   ↳ đã dọn {len(uploaded)} ảnh orphan khỏi kho")
            except Exception:
                pass
            traceback.print_exc()
        time.sleep(0.3)
    log(f"=== DONE: collection migrated={done}, ảnh={mig_imgs}, asset giữ lại={skipped_del} ===")
    log(f"Kho cuối: {[(k['name'], k['count']) for k in kho]}")
    db.close()


if __name__ == "__main__":
    main()
