# -*- coding: utf-8 -*-
"""qc_content.py — Cổng chặn cuối cùng trước khi sync body_html lên Haravan.

Prompt có thể bị AI phớt lờ. QC thì không. **Luôn chạy hàm này trước khi PUT.**

Nguồn luật: SINTECH_CONTENT_RULES.md (v2026-07-15, PHẦN 1B) + sintech_rules.py.
Sửa rules → sửa cả 3 nơi.

Dùng:
    from qc_content import check_product_body, check_blog_body, check_links
    errs = check_product_body(html)      # bài SP
    errs = check_blog_body(html)         # bài blog/guide (trọng tâm 1B.3)
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
    # 3 triệu (giá) — né spec "triệu màu / điểm / pixel / giờ / lượt / người / năm / lần"
    r"|\d+(?:[.,]\d+)?\s*triệu(?!\s*(?:giờ|màu|điểm|pixel|px|sắc|lượt|người|năm|lần))\s*(?:đồng|rưỡi)?"
    r"|giá rẻ|giá sốc|rẻ nhất|mức giá \d",
    re.I,
)
_BANNED = ["research", "SERP", "đối thủ", "theo nguồn", "inventory", "tại đây",
           "xem thêm tại đây", "click here"]
# Blog nới: "đối thủ" (đối thủ trong game) và "theo nguồn" (theo nguồn tin) là từ
# hợp lệ trong bài blog → chỉ chặn các từ lộ nội bộ/quy trình.
_BANNED_BLOG = ["research", "SERP", "inventory", "tại đây",
                "xem thêm tại đây", "click here"]

MAX_HEADING = 60          # ≤55 là target, >60 là chặn cứng
MAX_H2_FIRST = 50
LINK_MIN, LINK_MAX = 3, 6
MONEY_LINK_MIN = 2        # 1B.3 — blog/guide phải có ≥2 link về collection/product

# Link về MONEY PAGE: /collections/... hoặc /products/... (tuyệt đối hoặc tương đối)
_MONEY_LINK = re.compile(
    r'href="(?:https?://(?:www\.)?sintech\.vn)?/(?:collections|products)/[^"#?\s]+',
    re.I,
)


# ── Hai luật vợ đã chốt mà TRƯỚC 4/9/2026 chỉ nằm trong prompt gửi AI ─────────
# Docstring trên đầu file viết: "Prompt có thể bị AI phớt lờ. QC thì không." —
# nhưng chính hai luật này lại không có cổng nào kiểm:
#   · Từ so sánh tuyệt đối (Luật Quảng cáo cấm khi không có tài liệu chứng minh)
#   · Gạch ngang dài — vợ chốt 17/7/2026
#
# 🚨 5/9/2026 — VÁ CÁI THƯỚC. Bản 4/9 quét thô cả bài, báo 377 SP "cần soi";
# soi tay 408 lượt thì gần như TOÀN BÁO ĐỘNG GIẢ:
#   · 45/45 lượt "số 1" là "thông số 1300Mbps", "tần số 144Hz" — cắt giữa con số
#   · 195/195 lượt "duy nhất" mang nghĩa "chỉ một" (một ổ duy nhất, một chuẩn duy nhất)
#   · 91/91 lượt "tốt nhất" là thành ngữ ("phát huy tốt nhất khi…", "tốt nhất là bạn nên…")
# Luật vợ chốt 19/7: chỉ CẤM khi nói về hàng/dịch vụ CỦA SINTECH. Nên bản này soi
# theo TỪNG CÂU + ngữ cảnh, chia 2 mức:
#   · "cao"  = câu nhắc Sintech/cửa hàng, hoặc tự khen hàng mình  → phải sửa
#   · "thap" = khoa trương khi tả hàng hãng thứ ba                → soi khi rảnh
#
# ⚠️ Vẫn CẢNH BÁO, KHÔNG CHẶN sync.
_TU_TUYET_DOI = (r"tốt nhất|số một|số 1|duy nhất|rẻ nhất|nhanh nhất|mạnh nhất"
                 r"|uy tín nhất|hàng đầu|đáng mua nhất|chất lượng nhất|vượt trội|đỉnh cao")
_TUYET_DOI = re.compile(_TU_TUYET_DOI, re.I)

# Nhắc tới chính Sintech → mọi từ tuyệt đối trong câu đều là mức "cao"
_NHAC_SHOP = re.compile(r"sintech|cửa hàng|shop\b|showroom|bên mình|chúng tôi"
                        r"|nơi bán|địa chỉ mua|đơn vị cung cấp", re.I)
# Tự khen hàng/dịch vụ mình dù không gọi tên shop
_TU_KHEN = re.compile(
    r"(sản phẩm|dịch vụ|giá|chất lượng|bảo hành|hỗ trợ|tư vấn|kỹ thuật|đội ngũ)"
    r"[^.]{0,30}(tốt nhất|hàng đầu|số 1|số một|uy tín nhất|nhanh nhất|rẻ nhất)", re.I)
# Mẫu HỢP LỆ — cắt trước khi tính, đây là chỗ bản 4/9 báo nhầm
_HOP_LE = re.compile(
    r"(thông|tần|con|sai|chỉ|mã|ký|hệ|đa|tỉ|tỷ)\s*số\s*1"        # "thông số 1300Mbps"
    r"|số\s*1[\d.,]"                                              # "số 144Hz", "số 1.5"
    r"|(ưu tiên|tiêu chí|đặt lên|lên|không phải)\s+(số một|hàng đầu)"
    r"|thông số một cách"
    r"|tốt nhất là\b|phát huy tốt nhất|hoạt động tốt nhất|khai thác tốt nhất"
    r"|thể hiện tốt nhất|làm việc tốt nhất|chạy tốt nhất"
    r"|phát huy[^.]{0,14}tốt nhất"                              # "phát huy giá trị tốt nhất khi…"
    r"|(hỗ trợ|tương thích|ăn|hợp)\s+tốt nhất\s+(với|cho)"      # tương thích kỹ thuật, không phải tự khen
    r"|(cảm giác|tốc độ|phản hồi)\s+nhanh nhất\s+(ở|khi|trong)"  # tả trải nghiệm hàng hãng
    r"|(đừng|không nên|thay vì|chỉ|không)\s+(chọn|mua|nhìn)[^.]{0,30}(rẻ nhất|tốt nhất)",
    re.I)
# "duy nhất" theo sau danh từ = "chỉ một", cách viết đúng — chỉ sai khi khoe shop
_DUY_NHAT_CHI_MOT = re.compile(
    r"(một|1|kiểu|chuẩn|nhóm|thiết bị|ổ|khe|cổng|màu|tác vụ|setup|bản|loại|máy"
    r"|thanh|dây|nguồn|file|gói|mật khẩu|tài khoản|lần|điểm|vùng|kênh)\s+[^.]{0,18}duy nhất", re.I)

_DASH = re.compile(r"[—–]")
# "khoảng số": vế trước kết thúc bằng chữ số kèm đơn vị tuỳ ý (70, 5, 0°C, 256GB),
# vế sau bắt đầu bằng chữ số. Đây là cách viết ĐÚNG, không được báo.
#   0°C – 70°C · 5 – 10 phút · 100 – 240V
_TRUOC_LA_SO = re.compile(r"\d+\s*[^\s\d]{0,3}\s*$")
_SAU_LA_SO = re.compile(r"^\s*\d")


def _dash_xau(t: str):
    """Trả (vị trí, đoạn) của gạch ngang dài KHÔNG phải khoảng số. None nếu sạch."""
    for m in _DASH.finditer(t):
        i = m.start()
        if _TRUOC_LA_SO.search(t[max(0, i - 12):i]) and _SAU_LA_SO.search(t[i + 1:i + 13]):
            continue                      # khoảng số → hợp lệ
        return i, t[max(0, i - 40):i + 40].strip()
    return None


def _van_ban_thuan(html: str) -> str:
    """HTML → chữ thuần, đã gỡ signature (bản thân nó có ' — Hotline' đúng chuẩn)."""
    import html as _h
    t = _h.unescape(re.sub(r"<[^>]+>", " ", html or ""))
    t = re.sub(r"\s+", " ", t)
    for sig in ("Sintech — Hotline", "Sintech – Hotline"):
        t = t.replace(sig, "Sintech Hotline")
    return t


def soi_tu_tuyet_doi(html: str) -> list:
    """Soi từ so sánh tuyệt đối THEO CÂU. Trả [{tu, muc, cau}].

    muc "cao"  → câu nói về Sintech / tự khen hàng mình: phải sửa (Luật Quảng cáo).
    muc "thap" → khoa trương khi tả hàng hãng thứ ba: soi khi rảnh, rủi ro thấp.
    Câu mang nghĩa thông thường ("một ổ duy nhất", "thông số 144Hz") KHÔNG trả về.
    """
    t = _van_ban_thuan(html)
    ket = []
    for cau in re.split(r"(?<=[.!?])\s+", t):
        if not _TUYET_DOI.search(cau):
            continue
        co_shop = bool(_NHAC_SHOP.search(cau))
        for m in _TUYET_DOI.finditer(cau):
            tu = m.group(0).lower()
            i = m.start()
            cua_so = cau[max(0, i - 35):i + 35]
            if _HOP_LE.search(cua_so):
                continue
            if tu == "duy nhất" and _DUY_NHAT_CHI_MOT.search(cua_so):
                continue
            if co_shop or _TU_KHEN.search(cau):
                muc = "cao"
            elif tu in ("duy nhất", "số 1", "số một"):
                continue                  # không khoe shop thì đây là nghĩa thường
            else:
                muc = "thap"
            ket.append({"tu": tu, "muc": muc, "cau": cau.strip()[:220]})
            break                         # mỗi câu báo 1 lần là đủ để soi
    return ket


def check_content_warnings(html: str) -> list:
    """Cảnh báo 2 luật cần người soi ngữ cảnh. KHÔNG dùng để chặn sync.

    Trả list chuỗi mô tả, kèm câu chứa lỗi để soi nhanh.
    """
    canh_bao = [f"[{h['muc']}] từ tuyệt đối {h['tu']!r}: …{h['cau']}…"
                for h in soi_tu_tuyet_doi(html)]
    hit = _dash_xau(_van_ban_thuan(html))
    if hit:
        canh_bao.append(f"gạch ngang dài ngoài khoảng số: …{hit[1]}…")
    return canh_bao


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

    # <strong> được dùng trong: khối spec, anchor, VÀ nhãn đầu bullet <li> (vợ chốt 15/7).
    # Bỏ anchor + nội dung <li> ra trước khi soi <strong> lạc trong đoạn văn thân bài.
    _wo = re.sub(r"<a\b.*?</a>", "", body, flags=re.S | re.I)
    _wo = re.sub(r"<li\b.*?</li>", "", _wo, flags=re.S | re.I)
    if re.search(r"<strong[ >]", _wo, re.I):
        e.append("có <strong> trong đoạn văn thân bài (chỉ được ở spec, anchor, hoặc nhãn bullet)")

    if ";" in re.sub(r"<[^>]+>", "", body):
        e.append("còn dấu ';' trong body")

    for w in _BANNED:
        if re.search(rf"\b{re.escape(w)}\b", body, re.I):
            e.append(f"từ cấm: {w!r}")

    nlink = len(re.findall(r'<a [^>]*href="https://sintech\.vn', body))
    if not LINK_MIN <= nlink <= LINK_MAX:
        e.append(f"internal link = {nlink} (phải {LINK_MIN}-{LINK_MAX})")

    # strip tag trước khi so — signature có thể chứa nút SĐT (tel:) chèn tag vào giữa
    _sig_text = re.sub(r"<[^>]+>", "", html)
    # chấp nhận cả địa chỉ dạng CŨ (bài đã live trước 28/7/2026) để khỏi báo lỗi giả hàng loạt
    if (sintech_rules.SIGNATURE.rstrip(".") not in _sig_text
            and sintech_rules.LEGACY_SIGNATURE.rstrip(".") not in _sig_text):
        e.append("signature sai chuẩn hoặc thiếu")
    _addr_dot = "(?:%s|%s)\\." % (re.escape(sintech_rules.ADDRESS),
                                 re.escape(sintech_rules.LEGACY_ADDRESS))
    if not re.search(_addr_dot, html):
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


def check_blog_body(html: str) -> list:
    """Trả list lỗi (rỗng = đạt). Áp cho bài BLOG / GUIDE.

    Trọng tâm 1B.3: bài mồi phải có ≥2 internal link về MONEY PAGE
    (collection/product), không được là ngõ cụt. Blog nới hơn bài SP:
    ĐƯỢC nhắc giá (ghi "tham khảo"), ĐƯỢC dùng H3/bảng — nên KHÔNG áp
    check giá / blockquote / signature như check_product_body.
    """
    e: list = []

    if re.search(r"<h1", html, re.I):
        e.append("có <h1>")

    hs = _headings(html)
    if len(set(hs)) != len(hs):
        dup = [h for h in set(hs) if hs.count(h) > 1]
        e.append(f"heading trùng: {dup[:2]}")

    for w in _BANNED_BLOG:
        if re.search(rf"\b{re.escape(w)}\b", html, re.I):
            e.append(f"từ cấm: {w!r}")

    # (Blog ĐƯỢC dùng <strong>/bold, kể cả trong anchor — khác bài SP; không check ở đây.)

    # 1B.3 — link về money page (đếm URL riêng biệt, tránh cùng 1 đích tính 2 lần)
    money = set(m.group(0) for m in _MONEY_LINK.finditer(html))
    if len(money) < MONEY_LINK_MIN:
        e.append(
            f"chỉ {len(money)} link về money page (collection/product), "
            f"cần ≥{MONEY_LINK_MIN} — bài mồi không được là ngõ cụt (1B.3)"
        )
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


def _is_product(html: str) -> bool:
    """Bài SP luôn kết bằng khối <blockquote> spec; blog/guide thì không."""
    return bool(re.search(r"<blockquote", html, re.I))


def main(paths) -> int:
    bad = 0
    for p in paths:
        with open(p, encoding="utf-8") as f:
            html = f.read()
        checker = check_product_body if _is_product(html) else check_blog_body
        kind = "SP" if _is_product(html) else "blog"
        errs = checker(html) + [f"link chết: {u}" for u in check_links(html)]
        errs = [f"[{kind}] {x}" for x in errs]
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


# ── Dọn gạch ngang dài trong body AI sinh ra (vợ chốt 17/7/2026) ──────────────
# Trước 5/9/2026 luật này chỉ nằm trong prompt: `sanitize_pasted_html()` chỉ gỡ
# wrapper HTML của ChatGPT, không đụng dash. Bản này dọn ngay ở khâu writer.
#
# 🚫 KHÔNG đụng: khoảng số ("0°C – 70°C"), khối signature, và chữ trong
#    <strong>/<b>/<h1>/<a>/<code> — TÊN SP hay nằm ở đó ("Ventus XS OC – Cũ",
#    "Usb C – Hdmi"), mà luật 18/7 chốt giữ nguyên dấu trong tên SP.
_KHONG_DUNG_DASH = ("strong", "b", "h1", "a", "code", "title")


def sanitize_dash(html: str) -> str:
    """Thay gạch ngang dài bằng dấu phẩy ở phần VĂN XUÔI. Giữ tên SP + khoảng số."""
    if not html or ("—" not in html and "–" not in html):
        return html
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return html
    soup = BeautifulSoup(html, "html.parser")
    for node in list(soup.find_all(string=True)):
        s = str(node)
        if "—" not in s and "–" not in s:
            continue
        if any(p.name in _KHONG_DUNG_DASH for p in node.parents if p.name):
            continue
        if "Hotline" in s:                      # khối signature giữ nguyên
            continue
        # trong tiêu đề, dash thường là "Nhãn – Mô tả" → dấu hai chấm đọc mượt hơn
        trong_heading = any(p.name in ("h2", "h3", "h4") for p in node.parents if p.name)
        dau_thay = ":" if trong_heading else ","
        moi, i = [], 0
        for m in _DASH.finditer(s):
            j = m.start()
            truoc, sau = s[max(0, j - 12):j], s[j + 1:j + 13]
            moi.append(s[i:j])
            if _TRUOC_LA_SO.search(truoc) and _SAU_LA_SO.search(sau):
                moi.append(m.group(0))          # khoảng số ("0°C – 70°C") giữ nguyên
            elif _SAU_LA_SO.search(sau):
                moi.append(":")                 # "Rear – 80mm" là nhãn : trị số
            else:
                moi.append(dau_thay)          # khoảng số giữ, còn lại thành dấu câu thường
            i = j + 1
        moi.append(s[i:])
        moi = "".join(moi)
        moi = re.sub(r"\s*([,:])\s*", lambda m: m.group(1) + " ", moi).rstrip()
        if moi != s:
            node.replace_with(moi)
    return str(soup)
