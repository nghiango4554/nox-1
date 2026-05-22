"""T1 — Gom ảnh ứng viên về local cho 1 bài blog (lõi pipeline Blog Content).

Cho 1 bài (keyword + SP liên quan) → gom tối đa `max_n` ảnh ứng viên về local theo
thứ tự ưu tiên nguồn, để vợ vào trang `/blog-content/<id>` tick 2-3 tấm chèn vào bài.

Nguồn (bản 1):
  1. Sintech  — ảnh sản phẩm Haravan trong DB (haravan_products.images) + suffix _grande.
  2. Pexels   — stock free, search theo keyword (cần key state/image_keys.json).
  3. Unsplash — stock free, search theo keyword (cần key, optional).

Lưu: data/blog_images/<job_id>/NN_<source>.<ext> + meta.json
meta.json = list[{idx, file, source, origin_url, page_url, credit, alt, width, height, selected}]

Dedup theo URL gốc + md5 nội dung. Giữ thứ tự ưu tiên. Cap max_n.

Dùng:
    import image_gather
    res = image_gather.gather(job_id=12, query="cách chọn chuột gaming",
                              product_handles=["chuot-logitech-g502"], max_n=10)
"""
import io
import json
import re
import hashlib
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from PIL import Image  # đọc width/height; optional
except Exception:  # pragma: no cover
    Image = None

HERE = Path(__file__).parent
IMAGES_ROOT = HERE / "data" / "blog_images"
KEYS_PATH = HERE.parent / "state" / "image_keys.json"

TIMEOUT = 30
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

# Stopword tiếng Việt + filler để rút keyword search cho stock ảnh.
_STOP = {
    "cách", "chọn", "mua", "tốt", "nhất", "cho", "và", "của", "là", "có", "không",
    "khi", "nào", "gì", "với", "các", "những", "một", "để", "trong", "về", "theo",
    "bài", "hướng", "dẫn", "tin", "tức", "review", "đánh", "giá", "top", "nên",
    "2024", "2025", "2026", "thế", "nào", "ra", "sao", "vì", "bao", "nhiêu",
}


# ------------------------------------------------------------------ helpers
def _keys() -> dict:
    try:
        return json.loads(KEYS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _to_grande_url(src: str) -> str:
    """Haravan CDN: foo.png → foo_grande.png (600x600). Tái dùng logic content_writer."""
    return re.sub(
        r"\.(jpg|jpeg|png|webp|gif)(\?.*)?$",
        r"_grande.\1\2",
        src, count=1, flags=re.IGNORECASE,
    )


def _ext_from(url: str, content_type: str = "") -> str:
    m = re.search(r"\.(jpg|jpeg|png|webp|gif)(?:\?|#|$)", url, flags=re.IGNORECASE)
    if m:
        return m.group(1).lower().replace("jpeg", "jpg")
    ct = (content_type or "").lower()
    for key, ext in (("png", "png"), ("webp", "webp"), ("gif", "gif"), ("jpeg", "jpg"), ("jpg", "jpg")):
        if key in ct:
            return ext
    return "jpg"


def _keywords(query: str) -> list:
    """Rút token có nghĩa từ query (bỏ stopword/dấu câu)."""
    toks = re.findall(r"[0-9A-Za-zÀ-ỹ]+", (query or ""), flags=re.UNICODE)
    out = []
    for t in toks:
        tl = t.lower()
        if len(tl) <= 1 or tl in _STOP:
            continue
        out.append(t)
    return out


# ------------------------------------------------------------------ sources
def _sintech_image_urls(query: str, product_handles=None, want: int = 10) -> list:
    """Ảnh SP Sintech. Ưu tiên handle truyền vào, sau đó match keyword trên title.

    Trả list[{origin_url, page_url, credit, alt}] (đã _grande), giữ thứ tự ưu tiên.
    """
    import db
    conn = db.get_conn()
    rows = []
    seen_handles = set()

    def _take(row):
        h = row["handle"]
        if not h or h in seen_handles:
            return
        seen_handles.add(h)
        rows.append(row)

    try:
        # 1) Handle chỉ định trực tiếp
        for h in (product_handles or []):
            r = conn.execute(
                "SELECT handle, title, images FROM haravan_products WHERE handle = ?",
                (h,)).fetchone()
            if r:
                _take(r)

        # 2) Match keyword trên title (score = số token khớp), chỉ SP có ảnh
        kws = _keywords(query)
        if kws and len(seen_handles) < 12:
            like = " OR ".join(["LOWER(title) LIKE ?"] * len(kws))
            args = [f"%{k.lower()}%" for k in kws]
            cand = conn.execute(
                f"SELECT handle, title, images FROM haravan_products "
                f"WHERE images_count > 0 AND ({like}) LIMIT 60", args).fetchall()
            scored = []
            for r in cand:
                tl = (r["title"] or "").lower()
                score = sum(1 for k in kws if k.lower() in tl)
                scored.append((score, r))
            scored.sort(key=lambda x: x[0], reverse=True)
            for _, r in scored[:12]:
                _take(r)
    finally:
        conn.close()

    out = []
    for r in rows:
        if not r["images"]:
            continue
        try:
            imgs = json.loads(r["images"])
        except Exception:
            continue
        title = r["title"] or ""
        for img in imgs:
            src = img.get("src") or img.get("url") if isinstance(img, dict) else (img if isinstance(img, str) else None)
            if not src:
                continue
            out.append({
                "origin_url": _to_grande_url(src),
                "page_url": f"https://sintech.vn/products/{r['handle']}",
                "credit": "Sintech.vn",
                "alt": title,
            })
            if len(out) >= want:
                return out
    return out


def _pexels_image_urls(query: str, want: int = 10) -> list:
    key = _keys().get("pexels_api_key")
    if not key or not query:
        return []
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": key},
            params={"query": query, "per_page": min(want, 30), "locale": "vi-VN"},
            timeout=TIMEOUT, verify=False)
        if r.status_code >= 400:
            return []
        photos = r.json().get("photos", [])
    except Exception:
        return []
    out = []
    for p in photos:
        src = (p.get("src") or {})
        url = src.get("large") or src.get("medium") or src.get("original")
        if not url:
            continue
        out.append({
            "origin_url": url,
            "page_url": p.get("url", ""),
            "credit": f"Pexels / {p.get('photographer', '')}".strip(" /"),
            "alt": p.get("alt") or query,
        })
    return out


def _unsplash_image_urls(query: str, want: int = 10) -> list:
    key = _keys().get("unsplash_access_key")
    if not key or not query:
        return []
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            headers={"Authorization": f"Client-ID {key}"},
            params={"query": query, "per_page": min(want, 30)},
            timeout=TIMEOUT, verify=False)
        if r.status_code >= 400:
            return []
        results = r.json().get("results", [])
    except Exception:
        return []
    out = []
    for p in results:
        url = (p.get("urls") or {}).get("regular")
        if not url:
            continue
        out.append({
            "origin_url": url,
            "page_url": (p.get("links") or {}).get("html", ""),
            "credit": f"Unsplash / {(p.get('user') or {}).get('name', '')}".strip(" /"),
            "alt": p.get("alt_description") or query,
        })
    return out


# ------------------------------------------------------------------ download
def _download(url: str) -> bytes:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT, verify=False)
    if r.status_code >= 400 or not r.content:
        raise RuntimeError(f"HTTP {r.status_code}")
    return r.content, r.headers.get("Content-Type", "")


def _dimensions(content: bytes):
    if Image is None:
        return None, None
    try:
        with Image.open(io.BytesIO(content)) as im:
            return im.width, im.height
    except Exception:
        return None, None


# ------------------------------------------------------------------ entry
def gather(job_id, query: str, product_handles=None, max_n: int = 10,
           sources=("sintech", "pexels", "unsplash")) -> dict:
    """Gom ≤ max_n ảnh ứng viên về data/blog_images/<job_id>/ + meta.json.

    Returns: {ok, job_id, dir, count, items, by_source, errors}
    """
    job_dir = IMAGES_ROOT / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    # Thu thập candidate URL theo thứ tự ưu tiên nguồn, lấy dư để bù ảnh lỗi.
    candidates = []
    over = max_n + 6
    src_fn = {
        "sintech": lambda: _sintech_image_urls(query, product_handles, want=over),
        "pexels": lambda: _pexels_image_urls(query, want=over),
        "unsplash": lambda: _unsplash_image_urls(query, want=over),
    }
    for s in sources:
        fn = src_fn.get(s)
        if not fn:
            continue
        for item in fn():
            candidates.append({"source": s, **item})

    items = []
    errors = []
    seen_urls = set()
    seen_hash = set()
    by_source = {}

    for cand in candidates:
        if len(items) >= max_n:
            break
        url = cand["origin_url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        try:
            content, ctype = _download(url)
        except Exception as e:
            errors.append(f"{cand['source']}: {url[:80]} -> {e}")
            continue
        h = hashlib.md5(content).hexdigest()
        if h in seen_hash:
            continue
        seen_hash.add(h)

        idx = len(items) + 1
        ext = _ext_from(url, ctype)
        fname = f"{idx:02d}_{cand['source']}.{ext}"
        (job_dir / fname).write_bytes(content)
        w, ht = _dimensions(content)
        items.append({
            "idx": idx,
            "file": fname,
            "source": cand["source"],
            "origin_url": url,
            "page_url": cand.get("page_url", ""),
            "credit": cand.get("credit", ""),
            "alt": cand.get("alt", ""),
            "width": w,
            "height": ht,
            "selected": False,
        })
        by_source[cand["source"]] = by_source.get(cand["source"], 0) + 1

    meta = {
        "job_id": job_id,
        "query": query,
        "product_handles": product_handles or [],
        "count": len(items),
        "by_source": by_source,
        "items": items,
    }
    (job_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "job_id": job_id,
        "dir": str(job_dir),
        "count": len(items),
        "items": items,
        "by_source": by_source,
        "errors": errors,
    }


def load_meta(job_id) -> dict:
    """Đọc meta.json của job (cho T3 picker). Trả {} nếu chưa gom."""
    p = IMAGES_ROOT / str(job_id) / "meta.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def mark_selected(job_id, idxs) -> dict:
    """Đánh dấu selected=True cho các idx truyền vào (còn lại False), ghi lại meta.json.
    Dùng chung cho route tick tay (T3) + auto-pick khi gen (T2)."""
    meta = load_meta(job_id)
    if not meta:
        return {}
    sel = {int(i) for i in (idxs or [])}
    for it in meta.get("items", []):
        it["selected"] = it["idx"] in sel
    (IMAGES_ROOT / str(job_id) / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def set_ai_hero(job_id, origin_url: str, alt: str = "") -> dict:
    """Ghim 1 ảnh AI (đã host public, có URL CDN) làm ảnh đại diện (hero) trong meta.json.

    Tạo meta skeleton nếu job chưa gom ảnh. Bỏ cờ is_hero + selected ở hero cũ
    (mỗi bài 1 hero). Trả item hero mới. Featured ở publish ưu tiên item is_hero này.
    """
    meta = load_meta(job_id)
    if not meta:
        meta = {"job_id": job_id, "query": "", "product_handles": [],
                "count": 0, "by_source": {}, "items": []}
    items = meta.setdefault("items", [])
    for it in items:  # bỏ hero cũ
        if it.get("is_hero"):
            it["is_hero"] = False
            it["selected"] = False
    idx = max([it.get("idx", 0) for it in items], default=0) + 1
    hero = {
        "idx": idx, "file": "", "source": "ai",
        "origin_url": origin_url, "page_url": "", "credit": "",
        "alt": alt, "width": None, "height": None,
        "selected": True, "is_hero": True,
    }
    items.append(hero)
    meta["count"] = len(items)
    bs = meta.setdefault("by_source", {})
    bs["ai"] = bs.get("ai", 0) + 1
    job_dir = IMAGES_ROOT / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return hero


# ------------------------------------------------------------------ auto-pick + insert (T2 → "em chỉ duyệt")
def _is_main_h2(text: str) -> bool:
    """H2 chính để chèn ảnh (bỏ FAQ/câu hỏi thường gặp) — khớp isMainH2 ở blog_content_detail.html."""
    t = (text or "").strip().lower()
    if not t:
        return False
    if re.search(r"c[âa]u\s*h[ỏo]i.*th[ưuờơ]ng\s*g[ặa]p", t):
        return False
    if re.search(r"\bfaq\b", t):
        return False
    if re.match(r"^\s*c[âa]u\s*h[ỏo]i", t):
        return False
    return True


def auto_pick(items, n: int = 3) -> list:
    """Tự chọn ≤ n ảnh hợp lý cho 1 bài: ưu tiên Sintech (ảnh SP thật, đúng ngữ cảnh)
    → bù bằng stock. Bỏ ảnh quá nhỏ. Giữ thứ tự idx gốc khi trả về."""
    if not items:
        return []

    def big_enough(it):
        w, h = it.get("width"), it.get("height")
        if w and h and (w < 350 or h < 230):  # chỉ loại khi biết chắc là nhỏ
            return False
        return True

    pool = [it for it in items if big_enough(it)] or list(items)
    sintech = [it for it in pool if it.get("source") == "sintech"]
    others = [it for it in pool if it.get("source") != "sintech"]
    picked = (sintech[:n] + others)[:n]
    picked.sort(key=lambda it: it.get("idx", 0))
    return picked


def _figure_html(it) -> str:
    """Markup figure khớp _makeFigure() ở blog_content_detail.html (data-blog-img để idempotent)."""
    import html as _html
    src = _html.escape(it.get("origin_url") or "", quote=True)
    alt = _html.escape(it.get("alt") or "", quote=True)
    img = (f'<img src="{src}" alt="{alt}" data-blog-img="1" '
           f'style="max-width:100%;height:auto;border-radius:8px">')
    cap = ""
    if it.get("source") != "sintech" and it.get("credit"):  # stock cần ghi nguồn
        cap = ('<figcaption style="font-size:12px;color:#888;margin-top:4px;'
               f'font-style:italic">Ảnh: {_html.escape(it["credit"])}</figcaption>')
    return ('<figure data-blog-img="1" style="margin:18px 0;text-align:center">'
            f'{img}{cap}</figure>')


def insert_into_body(body_html: str, picked: list):
    """Chèn figure ảnh vào body server-side: tấm đầu sau intro, còn lại rải trước H2 chính.
    Idempotent (xoá figure[data-blog-img] cũ trước). Khớp logic JS insertSelected().

    Trả (new_body_html, used_items) — used = ảnh thực sự được chèn (đã trim theo số slot)."""
    if not body_html or not picked:
        return body_html, []
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(body_html, "lxml")
    container = soup.body or soup

    # 1) Xoá ảnh blog cũ (re-insert sạch, không nhân đôi)
    for el in container.select("figure[data-blog-img], img[data-blog-img]"):
        fig = el.find_parent("figure", attrs={"data-blog-img": True}) or el
        fig.decompose()

    # 2) Anchor vị trí chèn (mỗi slot 1 ảnh, không dồn cục):
    #    tấm đầu SAU intro (≈ ngay trước H2 đầu) → các tấm sau TRƯỚC H2 chính kế tiếp.
    main_h2 = [h for h in container.find_all("h2") if _is_main_h2(h.get_text())]
    first_h2 = container.find("h2")
    p0 = container.find("p")
    # intro chỉ tính khi <p> nằm TRƯỚC H2 đầu tiên (bài mở thẳng bằng H2 → không có intro)
    intro_p = p0 if (p0 and (first_h2 is None or first_h2 in p0.find_all_next("h2"))) else None
    anchors = []  # list[(mode, node)]
    if intro_p:
        anchors.append(("after", intro_p))
        anchors += [("before", h) for h in main_h2[1:]]  # bỏ H2 đầu (ảnh intro đã sát nó)
    else:
        anchors += [("before", h) for h in main_h2]

    used = picked[:len(anchors)] if anchors else picked[:1]
    for i, it in enumerate(used):
        frag = BeautifulSoup(_figure_html(it), "lxml")
        fig = (frag.body or frag).find("figure")
        if anchors and i < len(anchors):
            mode, node = anchors[i]
            (node.insert_after if mode == "after" else node.insert_before)(fig)
        else:
            container.append(fig)

    new_html = "".join(str(c) for c in container.children).strip()
    return new_html, used


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(HERE))
    q = sys.argv[1] if len(sys.argv) > 1 else "chuột gaming không dây"
    jid = sys.argv[2] if len(sys.argv) > 2 else "_test"
    res = gather(jid, q, max_n=10)
    print(json.dumps({k: v for k, v in res.items() if k != "items"}, ensure_ascii=False, indent=2))
    for it in res["items"]:
        print(f"  {it['idx']:>2} [{it['source']:<8}] {it['width']}x{it['height']} {it['file']}  <- {it['origin_url'][:70]}")
