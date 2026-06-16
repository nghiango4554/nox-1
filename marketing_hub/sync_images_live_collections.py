# -*- coding: utf-8 -*-
"""Chèn ảnh research → collection LIVE Haravan (body-only PUT, KHÔNG đổi title/meta/rules).

Cho các collection có content trên web nhưng KHÔNG track ở collection_jobs.
Flow mỗi collection:
  fetch live (smart/custom) → curate ~7 ảnh research → upload Theme Assets 600px →
  chèn snap H2 (1 dưới intro · giàn đều · 1 trên outro, tránh FAQ) → backup body local →
  PUT body_html ONLY → log.
Bài <2 H2 (lấp liếm/trống) → skip (không có chỗ chèn). Idempotent qua backup + strip_our_imgs.
"""
import sys, io, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # workspace root (research script)
if (getattr(sys.stdout, "encoding", "") or "").lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import sync_collection_images as scs
import research_collection_images as rci
import haravan_client as hc

KEYS_JSON = Path(r"C:\Users\NGHIANGO\Downloads\sintech_collection_image_search_keywords.json")
RESEARCH = Path(r"C:\Users\NGHIANGO\Desktop\Sintech-img\pic content carte\research")
BACKUP = Path(__file__).parent / "data" / "cc_img_backup_live"
N_IMG = 7
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def fetch_live():
    """Tất cả collection live → dict norm(title) → {id, handle, title, body_html, type}."""
    out = {}
    for typ, fn in (("smart", hc.list_smart_collections), ("custom", hc.list_custom_collections)):
        p = 1
        while True:
            try:
                batch = fn(page=p, limit=50)
            except Exception:
                break
            if not batch:
                break
            for c in batch:
                out[scs.norm(c.get("title") or "")] = {
                    "id": c.get("id"), "handle": c.get("handle"), "title": c.get("title") or "",
                    "body_html": c.get("body_html") or "", "type": typ}
            if len(batch) < 50:
                break
            p += 1
    return out


def find_research_folder(title):
    safe = rci.safe_name(title)
    cand = RESEARCH / safe
    if cand.is_dir():
        return cand
    key = re.sub(r"\s+", "", rci.safe_name(title).lower())
    for p in RESEARCH.iterdir():
        if p.is_dir() and re.sub(r"\s+", "", rci.safe_name(p.name).lower()) == key:
            return p
    return None


def curate(folder, n):
    imgs = sorted([p for p in folder.iterdir() if p.suffix.lower() in EXTS])
    if len(imgs) <= n:
        return imgs
    return [imgs[round(i * (len(imgs) - 1) / (n - 1))] for i in range(n)]


def put_body_only(coll):
    ep = "smart_collections" if coll["type"] == "smart" else "custom_collections"
    key = "smart_collection" if coll["type"] == "smart" else "custom_collection"
    return hc._request("PUT", f"/{ep}/{coll['id']}.json",
                       payload={key: {"id": coll["id"], "body_html": coll["_new_body"]}})


def process(title, coll, short):
    body = coll["body_html"]
    if len(re.findall(r"<h2", body, re.I)) < 2:
        return "skip", "lấp liếm/trống (<2 H2) — cần viết content trước"
    folder = find_research_folder(title)
    if not folder:
        return "skip", "không thấy folder ảnh research"
    imgs = curate(folder, N_IMG)
    if not imgs:
        return "skip", "folder rỗng"
    handle = coll["handle"]
    BACKUP.mkdir(parents=True, exist_ok=True)
    bpath = BACKUP / f"{handle}.html"
    if not bpath.exists():
        bpath.write_text(scs.strip_our_imgs(body, handle), encoding="utf-8")
    base = bpath.read_text(encoding="utf-8")  # luôn dựng từ gốc (idempotent)
    pts = scs.insertion_points(base, title, len(imgs))
    if not pts:
        return "skip", "không tìm được vị trí chèn"
    k = len(pts)
    inserts = []
    for idx, ((off, h2), local) in enumerate(zip(pts, imgs[:k]), 1):
        url = scs.upload_asset(scs.resize_bytes(local), f"cc-{handle}-{idx:02d}.jpg")
        inserts.append((off, scs.img_block(url, f"{short} - {h2}")))
    new_body = base
    for off, html in sorted(inserts, key=lambda x: -x[0]):
        new_body = new_body[:off] + html + new_body[off:]
    coll["_new_body"] = new_body
    put_body_only(coll)
    return "ok", f"{k} ảnh chèn + PUT body-only"


def main():
    data = json.loads(KEYS_JSON.read_text(encoding="utf-8"))
    live = fetch_live()
    print(f"{len(data)} collection · {len(live)} live · chèn ≤{N_IMG} ảnh/collection (body-only)\n")
    ok = skip = fail = 0
    for i, title in enumerate(data, 1):
        coll = live.get(scs.norm(title))
        if not coll:
            print(f"  [{i:02d}] ⏭ {title}: không match live"); skip += 1; continue
        try:
            st, detail = process(title, coll, title)
        except Exception as e:
            st, detail = "fail", str(e)[:120]
        print(f"  [{i:02d}] {'✅' if st=='ok' else ('⏭' if st=='skip' else '❌')} {title}: {detail}")
        ok += st == "ok"; skip += st == "skip"; fail += st == "fail"
    print(f"\n🎉 Xong: {ok} sync · {skip} skip · {fail} fail")


if __name__ == "__main__":
    main()
