# -*- coding: utf-8 -*-
"""Quét toàn bộ blog Haravan tìm dấu hiệu copy bài đối thủ (read-only).

Dấu hiệu:
  - HOTLINK ảnh từ CDN đối thủ / domain ngoài (img src không phải hstatic/sintech/haravan).
  - LINK <a href> trỏ tới domain đối thủ.
  - NHẮC tên đối thủ trong text (FPT Shop, Thế Giới Di Động...).
Xuất bảng: tiêu đề | người viết | ngày hiển thị | dấu hiệu.
KHÔNG sửa gì.
"""
import json, re, sys, urllib3
from pathlib import Path
from urllib.parse import urlparse
import requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CFG = json.loads((Path(__file__).parent.parent.parent / "state" / "haravan_token.json").read_text(encoding="utf-8"))
TOK = CFG["blog_access_token"]; BASE = CFG["open_api_base"]; BLOG_IDS = CFG["blog_ids"]
H = {"Authorization": f"Bearer {TOK}", "Accept": "application/json"}

# host của mình (ảnh hợp lệ)
OWN = ("hstatic.net", "sintech.vn", "myharavan.com", "haravan.com", "haravanstatic", "ggpht", "youtube", "ytimg")
# CDN/domain đối thủ phổ biến ở VN (img hotlink hoặc link)
COMPETITORS = {
    "fptshop.com.vn": "FPT Shop", "thegioididong.com": "TGDĐ", "tgdd.vn": "TGDĐ",
    "dienmayxanh.com": "Điện Máy Xanh", "cellphones.com.vn": "CellphoneS",
    "memoryzone.com.vn": "MemoryZone", "hoanghamobile.com": "Hoàng Hà",
    "anphatpc.com.vn": "An Phát", "phongvu.vn": "Phong Vũ", "gearvn.com": "GearVN",
    "maytinhcdc.vn": "Máy Tính CDC", "nguyenkim.com": "Nguyễn Kim",
    "hanoicomputer": "HACOM", "hacom.vn": "HACOM", "minhtuanmobile": "Minh Tuấn",
    "xuanvinh": "Xuân Vinh", "phucanh": "Phúc Anh", "didongviet": "Di Động Việt",
    "clickbuy": "ClickBuy", "vienthonga": "Viễn Thông A", "hnam": "HNAM",
    "tinhocngoisao": "Tin Học Ngôi Sao", "nguyencongpc": "Nguyễn Công PC",
    "gearvn": "GearVN", "h3t.vn": "H3T", "binhminhdigital": "Bình Minh",
}


def host_of(u):
    try:
        h = (urlparse(u).hostname or "").lower()
        return h
    except Exception:
        return ""


def is_own(h):
    return any(o in h for o in OWN)


def comp_name(h):
    for dom, name in COMPETITORS.items():
        if dom in h:
            return name
    return None


def fetch_all(blog_id):
    out = []
    page = 1
    while True:
        r = requests.get(f"{BASE}/blogs/{blog_id}/articles.json", headers=H,
                         params={"limit": 250, "page": page}, verify=False, timeout=40)
        if r.status_code != 200:
            print(f"  blog {blog_id} page {page}: HTTP {r.status_code}", file=sys.stderr); break
        arts = r.json().get("articles", [])
        if not arts:
            break
        out += arts
        if len(arts) < 250:
            break
        page += 1
    return out


def scan_article(a):
    body = a.get("body_html") or ""
    img_hosts = set(); link_comps = set(); ext_img = set()
    for src in re.findall(r'<img[^>]+src="([^"]+)"', body, re.I):
        h = host_of(src)
        if not h or is_own(h):
            continue
        ext_img.add(h)
        cn = comp_name(h)
        if cn:
            img_hosts.add(cn)
    for href in re.findall(r'<a[^>]+href="([^"]+)"', body, re.I):
        h = host_of(href)
        cn = comp_name(h)
        if cn:
            link_comps.add(cn)
    text = re.sub(r"<[^>]+>", " ", body)
    text_comps = set()
    for kw in ("FPT Shop", "Thế Giới Di Động", "Điện Máy Xanh", "CellphoneS",
               "GearVN", "Phong Vũ", "Hoàng Hà", "Nguyễn Kim", "Minh Tuấn Mobile"):
        if kw.lower() in text.lower():
            text_comps.add(kw)
    return {
        "comp_img": sorted(img_hosts), "ext_img_hosts": sorted(ext_img),
        "comp_link": sorted(link_comps), "comp_text": sorted(text_comps),
        "n_ext_img": len(ext_img),
    }


def score(sig):
    # mức độ nghi: ảnh CDN đối thủ = mạnh nhất; ảnh ngoài bất kỳ = vừa; link/text = nhẹ
    s = 0
    if sig["comp_img"]:  s += 5
    if sig["ext_img_hosts"]: s += 2
    if sig["comp_link"]: s += 2
    if sig["comp_text"]: s += 1
    return s


def main():
    all_arts = []
    for name, bid in BLOG_IDS.items():
        arts = fetch_all(bid)
        for a in arts:
            a["_blog"] = name
        all_arts += arts
        print(f"blog '{name}' ({bid}): {len(arts)} bài", file=sys.stderr)
    print(f"TỔNG: {len(all_arts)} bài", file=sys.stderr)

    rows = []
    for a in all_arts:
        sig = scan_article(a)
        sc = score(sig)
        if sc == 0:
            continue
        rows.append({
            "title": a.get("title", ""),
            "author": a.get("author", ""),
            "published": (a.get("published_at") or a.get("created_at") or "")[:10],
            "blog": a.get("_blog", ""),
            "handle": a.get("handle", ""),
            "score": sc, **sig,
        })
    rows.sort(key=lambda r: (-r["score"], r["published"]))

    # CSV
    import csv
    out_csv = Path(__file__).parent.parent / "docs" / "blog_plagiarism_scan_20260610.csv"
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Tiêu đề", "Người viết", "Ngày hiển thị", "Blog", "Mức nghi",
                    "Ảnh CDN đối thủ", "Host ảnh ngoài", "Link đối thủ", "Nhắc tên ĐT", "Handle"])
        for r in rows:
            w.writerow([r["title"], r["author"], r["published"], r["blog"], r["score"],
                        "; ".join(r["comp_img"]), "; ".join(r["ext_img_hosts"][:6]),
                        "; ".join(r["comp_link"]), "; ".join(r["comp_text"]), r["handle"]])
    # tóm tắt stdout
    strong = [r for r in rows if r["comp_img"]]
    extimg = [r for r in rows if r["ext_img_hosts"] and not r["comp_img"]]
    print(f"\n=== {len(rows)}/{len(all_arts)} bài CÓ dấu hiệu ===")
    print(f"  - {len(strong)} bài ảnh hotlink CDN đối thủ (NGHI CAO)")
    print(f"  - {len(extimg)} bài ảnh hotlink domain ngoài khác (nghi vừa)")
    print(f"CSV -> {out_csv}")
    print(f"\n--- TOP NGHI CAO (ảnh CDN đối thủ) ---")
    for r in strong[:40]:
        print(f"  [{r['published']}] {r['author'][:14]:14} | {', '.join(r['comp_img'])[:25]:25} | {r['title'][:50]}")
    return rows


if __name__ == "__main__":
    main()
