# -*- coding: utf-8 -*-
"""qc_content.py — Cổng chặn cuối cùng trước khi sync body_html lên Haravan.

Prompt có thể bị AI phớt lờ. QC thì không. **Luôn chạy hàm này trước khi PUT.**

Nguồn luật: SINTECH_CONTENT_RULES.md (v2026-07-09) + sintech_rules.py.
Sửa rules → sửa cả 3 nơi.

Dùng:
    from qc_content import check_product_body, check_links
    errs = check_product_body(html)
    if errs: raise SystemExit(errs)      # hoặc log rồi bỏ qua bài đó

CLI:
    python qc_content.py bai1.html bai2.html
"""
from __future__ import annotations

import re
import sys
import urllib.request

import sintech_rules

# ── Regex luật ────────────────────────────────────────────────────────────────
_PRICE = re.compile(
    r"\d{1,3}[\.,]\d{3}\s*(?:đồng|đ)\b"      # 45.000 đồng
    r"|\btầm\s+\d+\s*k\b"                     # tầm 149k
    r"|\d+\s*triệu\s*(?:đồng|rưỡi)?(?!\s*giờ)"  # 3 triệu (né "1 triệu giờ")
    r"|giá rẻ|giá sốc|rẻ nhất|mức giá \d",
    re.I,
)
_BANNED = ["research", "SERP", "đối thủ", "theo nguồn", "inventory", "tại đây",
           "xem thêm tại đây", "click here"]

MAX_HEADING = 60          # ≤55 là target, >60 là chặn cứng
MAX_H2_FIRST = 50
LINK_MIN, LINK_MAX = 3, 6


def _strip_blockquote(html: str) -> str:
    return re.sub(r"<blockquote>.*?</blockquote>", "", html, flags=re.S | re.I)


def _headings(html: str) -> list:
    return [re.sub(r"<[^>]+>", "", m.group(2)).strip()
            for m in re.finditer(r"<(h[23])[^>]*>(.*?)</\1>", html, re.S | re.I)]


def check_product_body(html: str) -> list:
    """Trả list lỗi (rỗng = đạt). Áp cho bài SẢN PHẨM."""
    e: list = []
    body = _strip_blockquote(html)

    if re.search(r"<h1", html, re.I):
        e.append("có <h1>")

    # H2 đầu = tên SP
    m = re.search(r"<h2[^>]*>(.*?)</h2>", html, re.S | re.I)
    if not m:
        e.append("không có <h2> nào")
    else:
        t = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if ":" in t:
            e.append(f"H2 đầu có dấu ':' → {t[:45]}")
        if len(t) > MAX_H2_FIRST:
            e.append(f"H2 đầu dài {len(t)}c (tối đa {MAX_H2_FIRST})")

    hs = _headings(html)
    for h in hs:
        if len(h) > MAX_HEADING:
            e.append(f"heading >{MAX_HEADING}c: {h[:45]}")
    if len(set(hs)) != len(hs):
        dup = [h for h in set(hs) if hs.count(h) > 1]
        e.append(f"heading trùng: {dup[:2]}")

    for m in _PRICE.finditer(body):
        e.append(f"nhắc giá: {m.group(0)!r}")

    if re.search(r"<strong[ >]", body, re.I):
        e.append("có <strong> trong thân bài (chỉ được dùng trong khối spec)")

    if ";" in re.sub(r"<[^>]+>", "", body):
        e.append("còn dấu ';' trong body")

    for w in _BANNED:
        if re.search(rf"\b{re.escape(w)}\b", body, re.I):
            e.append(f"từ cấm: {w!r}")

    nlink = len(re.findall(r'<a [^>]*href="https://sintech\.vn', body))
    if not LINK_MIN <= nlink <= LINK_MAX:
        e.append(f"internal link = {nlink} (phải {LINK_MIN}-{LINK_MAX})")
    if re.search(r'<a [^>]*>\s*<strong>', body, re.I):
        e.append("anchor bọc <strong> (phải là thẻ <a> thường)")

    if sintech_rules.SIGNATURE.rstrip(".") not in html:
        e.append("signature sai chuẩn hoặc thiếu")
    if not re.search(r"457 Trần Xuân Soạn, Q7, TP\.HCM\.", html):
        e.append("signature thiếu dấu chấm cuối")

    if "chính sách bán hàng, kiểm hàng" not in body:
        e.append("thiếu câu chính sách bắt buộc")

    # Khối spec
    bqs = list(re.finditer(r"<blockquote[^>]*>.*?</blockquote>", html, re.S | re.I))
    if not bqs:
        e.append("thiếu <blockquote> spec")
    else:
        if len(bqs) > 1:
            e.append(f"{len(bqs)} blockquote (phải đúng 1)")
        if html[bqs[-1].end():].strip():
            e.append("có nội dung SAU blockquote (phải là block cuối cùng)")
        tag = re.search(r"<blockquote[^>]*>", html, re.I).group(0)
        if "style" in tag.lower():
            e.append("blockquote có inline style → theme không render thành bảng")
        inner = bqs[-1].group(0)
        if re.search(r"<table", inner, re.I):
            e.append("có <table> trong blockquote → không hiển thị trên trang SP")
        low = inner.lower()
        if "bảo hành" in low or "tình trạng" in low:
            e.append("blockquote còn Bảo hành/Tình trạng (phải loại)")
    return e


def check_links(html: str, timeout: int = 15) -> list:
    """Trả list URL chết. Gọi mạng — tách riêng để test offline được."""
    dead = []
    for u in set(re.findall(r'href="(https?://[^"]+)"', html)):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
            if urllib.request.urlopen(req, timeout=timeout).status != 200:
                dead.append(u)
        except Exception:
            dead.append(u)
    return dead


def main(paths) -> int:
    bad = 0
    for p in paths:
        with open(p, encoding="utf-8") as f:
            html = f.read()
        errs = check_product_body(html) + [f"link chết: {u}" for u in check_links(html)]
        if errs:
            bad += 1
            print(f"\n!! {p}")
            for x in errs:
                print(f"   - {x}")
        else:
            print(f"OK {p}")
    print(f"\n{len(paths) - bad}/{len(paths)} đạt.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["-"]))
