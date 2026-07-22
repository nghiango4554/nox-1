"""Research thông số SP từ web — CÓ CỔNG CHẶN, không đoán, không tự tin mù quáng.

Nguyên tắc vợ chốt 22/7/2026:
- Tầng 1 HTTP thuần (requests + Serper). Trang hãng phần lớn chặn 403 / dựng bằng JS
  → nếu cần thì mới lên tầng 2 (Chrome thật chạy từ script, xem
  [[reference_scrape_without_burning_session]]). KHÔNG dùng Chrome-MCP để cào.
- 5 cổng chặn trước khi tin một trang nguồn:
    1. KHỚP MÃ MODEL   — trang nguồn phải chứa mã trong tên SP
    2. KHỚP LOẠI SP    — "Màn Hình Laptop" ≠ "Laptop" (ca ThinkPad T16 lấy nhầm spec cả máy)
    3. KHÔNG phải site mình — chặn sintech.vn, tránh tự cào lại chính mình
    4. LỌC RÁC         — bỏ dòng giá tiền, menu, đổi tiền tệ, bảo hành, tình trạng
    5. ĐỐI CHIẾU CHÉO  — ưu tiên dòng mà 2 nguồn độc lập nói giống nhau
- Nhóm LAPTOP / máy bộ / linh kiện thay thế (màn hình laptop, pin…): KHÔNG tự động.
"""

import re
import unicodedata
from difflib import SequenceMatcher

import serper_search as ss

OWN_DOMAIN = "sintech.vn"
SKIP_DOMAINS = ("shopee.vn", "lazada.vn", "tiki.vn", "sendo.vn", "facebook.com",
                "youtube.com", "tiktok.com", OWN_DOMAIN)

# nhóm KHÔNG tự động research (vợ chốt: audit tay)
BLOCKED_KIND = re.compile(r"(?i)màn hình laptop|pin laptop|bàn phím laptop|^laptop|máy bộ|"
                          r"mini pc|sạc laptop|adapter")

JUNK_KEY = re.compile(r"(?i)^(hạng mục|thông số|thông tin|chi tiết|tên sản phẩm|mục|stt|danh mục"
                      r"|tiền tệ|ngôn ngữ|currency|menu|khuyến mãi|giá|bảo hành|tình trạng"
                      r"|đánh giá|bình luận|chia sẻ|so sánh|mã sản phẩm cũ)\b")
JUNK_VAL = re.compile(r"(?i)^(vnd|usd|tiếng việt|english|xem thêm|liên hệ|đang cập nhật|-|n/a)$")
PRICE = re.compile(r"(?i)\d[\d\.,]*\s*(₫|đ|vnđ|vnd|đồng)\b|\bgiá\b")
# Bẫy 22/7: mẫu cũ bỏ sót model MỞ ĐẦU BẰNG SỐ (27U411A-B) và tên GPU (GTX 1650, GT 730).
MODEL_TOKEN = re.compile(
    r"(?i)\b("
    r"(?:rtx|gtx|gt|rx)\s?\d{3,4}\s?(?:ti|xt|super|xtx)?"   # GPU: GTX 1650, RTX 4060 Ti
    r"|(?:i[3579]|ryzen\s?[3579]|ultra\s?[3579])[\s-]?\d{3,5}[a-z]{0,3}"  # i7-12700F
    r"|\d{4,5}[a-z]{1,2}(?![a-z])"                           # 12700F, 5600G, 14400F
    r"|[a-z]{1,6}[-–]?\d{2,5}[a-z0-9\-]*"                    # CF-AX90, GM-03, CT9000
    r"|[a-z]{1,6}\d{1,3}(?:[-–]\d{1,4}[a-z0-9]*)"            # P5-240, A3-500
    r"|\d{2,3}[a-z]{1,3}\d{2,4}[a-z0-9\-]*"                  # 27U411A-B
    r")\b")
# Khi tên SP không có mã model: KHÔNG bỏ hẳn, mà đối chiếu bằng ĐỘ TRÙNG TỪ của tên.
_TITLE = {}          # tên SP đang tra, dùng cho cổng trùng-từ
WORD_STOP = set("nguồn nguon card màn hình man cpu ram ssd hdd vỏ case vo bàn phím chuột "
                "tản nhiệt tan nhiet bộ máy tính may tinh gaming đen den trắng trang plus "
                "cho của new mới moi chính hãng chinh hang inch".split())
MAX_ROWS = 40                     # trang trả quá nhiều dòng = trang liệt kê, không phải 1 SP


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", (s or "").lower())
    return re.sub(r"[^0-9a-zà-ỹ]+", " ", s).strip()


def model_tokens(title: str) -> list[str]:
    """Mã model rút từ tên SP: CF-AX90, GM-03, CT9000, V-A601, GTX 1650…"""
    raw = re.sub(r"\(.*?\)", " ", title or "")
    out, seen = [], set()
    for m in MODEL_TOKEN.finditer(raw):
        t = m.group(0).strip().lower().replace("–", "-")
        if t in seen or len(t) < 3:
            continue
        if re.fullmatch(r"(?i)\d{1,2}\s?gb|\d{3,4}\s?w|\d{2,3}\s?hz|ddr\d|usb\d?|pc\d|"
                        r"m[-\s]?atx|\d{1,2}\s?inch|\d{3,4}\s?p", t):
            continue
        seen.add(t)
        out.append(t)
    return out


def kind_words(product_type: str, title: str) -> list[str]:
    """Từ khoá LOẠI sản phẩm để chặn lấy nhầm nhóm hàng."""
    t = norm(product_type)
    m = {"vỏ case": ["case", "vỏ case", "thùng máy"], "màn hình": ["màn hình", "monitor"],
         "vga": ["card màn hình", "vga", "graphics"], "nguồn": ["nguồn", "psu"],
         "ram": ["ram", "bộ nhớ"], "ram laptop": ["ram laptop", "so-dimm", "sodimm"],
         "thiết bị mạng": ["card mạng", "wifi", "card wifi"],
         "phụ kiện": ["cáp", "dây", "adapter", "hub"],
         "phím chuột văn phòng": ["bàn phím", "combo", "chuột"],
         "bàn phím cơ": ["bàn phím"], "chuột": ["chuột"], "tai nghe": ["tai nghe"],
         "ghế": ["ghế"], "loa": ["loa"], "ssd": ["ssd"], "hdd": ["hdd", "ổ cứng"]}
    for k, v in m.items():
        if k in t:
            return v
    return [w for w in norm(title).split()[:2] if len(w) > 2]


# ───────── bóc spec ĐÚNG CHỖ (bẫy 22/7: quét cả trang → ra menu + bảng giá) ─────────
SPEC_HEAD_RE = re.compile(
    r"(?is)<(h[1-4]|div|span|strong|p)[^>]*>[^<]{0,60}"
    r"(thông số kỹ thuật|thông số chi tiết|thông tin chi tiết|specification|tech spec)"
    r"[^<]{0,40}</\1>")
NAV_HINT = re.compile(r"(?i)hotline|giỏ hàng|chat |zalo|facebook|chi nhánh|khuyến mãi|liên hệ"
                      r"|đăng nhập|tài khoản|danh mục|xem thêm|hướng dẫn|chính sách|tra cứu"
                      r"|giao hàng|thanh toán|trả góp|so sánh|yêu thích|lượt xem|mua ngay"
                      r"|giới thiệu|cam kết|hệ thống|ngành hàng|theo hãng|theo nhu cầu")
UNIT = re.compile(r"(?i)\d|mm|cm|kg|gb|tb|mhz|ghz|hz|w\b|v\b|inch|bit|pin|rpm|db|ms\b|nm\b")


def extract_spec_rows(html: str) -> list[dict]:
    """Chỉ bóc trong VÙNG thông số (sau heading 'Thông số kỹ thuật'), không quét cả trang."""
    m = SPEC_HEAD_RE.search(html or "")
    zone = html[m.end(): m.end() + 24000] if m else ""
    out = []
    for frag in (zone, "" if zone else (html or "")):
        if not frag:
            continue
        for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", frag):
            cells = re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", tr)
            if len(cells) == 2:
                out.append({"label": _txt(cells[0]), "value": _txt(cells[1])})
        for dl in re.findall(r"(?is)<dl[^>]*>(.*?)</dl>", frag):
            dts = re.findall(r"(?is)<dt[^>]*>(.*?)</dt>", dl)
            dds = re.findall(r"(?is)<dd[^>]*>(.*?)</dd>", dl)
            for a, b in zip(dts, dds):
                out.append({"label": _txt(a), "value": _txt(b)})
        for li in re.findall(r"(?is)<li[^>]*>(.*?)</li>", frag):
            t = _txt(li)
            mm = re.match(r"^([^:：]{2,44})[:：]\s*(.+)$", t)
            if mm:
                out.append({"label": mm.group(1), "value": mm.group(2)})
        if out:
            break
    return out


def _txt(s: str) -> str:
    import html as _h
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s or "")
    return re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def clean_rows(rows: list[dict]) -> list[list[str]]:
    out, seen = [], set()
    for r in rows:
        k = (r.get("label") or "").strip().rstrip(":")
        v = (r.get("value") or "").strip()
        if not k or not v or len(k) > 46 or len(v) > 160:
            continue
        if JUNK_KEY.match(k) or JUNK_VAL.match(v) or PRICE.search(k) or PRICE.search(v):
            continue
        if NAV_HINT.search(k) or NAV_HINT.search(v):       # dòng menu / điều hướng
            continue
        if "%" in k or re.search(r"\d{3}[\.,]\d{3}", k + v):   # giá / phần trăm giảm
            continue
        if re.fullmatch(r"\d{1,3}", k) or re.match(r"^\d{1,2}\s*[:h]\s*\d{2}\s*-", v):
            continue                                            # nhãn là số / giờ mở cửa
        if len(v.split()) > 14 and not UNIT.search(v):     # câu văn dài, không có đơn vị
            continue
        if norm(k) == norm(v) or norm(k) in seen:
            continue
        seen.add(norm(k))
        out.append([k, v])
    # cổng mật độ kỹ thuật: quá nửa số dòng phải có SỐ hoặc ĐƠN VỊ
    if out and sum(1 for _, v in out if UNIT.search(v)) < len(out) * 0.5:
        return []
    return out


# Bẫy 22/7: SSD Lexar LNQ100X **256GB** của mình khớp nguồn LNQ100X **240GB** — đúng model
# nhưng SAI DUNG LƯỢNG. Bắt buộc khớp cả con số dung lượng / công suất / kích thước.
# phải nuốt cả số thập phân: "21.5 inch" — nếu không sẽ bóc nhầm thành "5inch"
SIZE_TOKEN = re.compile(r"(?i)(?<![\d.])(\d{1,4}(?:[.,]\d)?)\s*(gb|tb|w|inch|\")(?![a-z])")


def size_tokens(title: str) -> list[str]:
    out = []
    for m in SIZE_TOKEN.finditer(title or ""):
        num, unit = m.group(1), m.group(2).lower().replace('"', "inch")
        if unit == "w" and int(num) < 100:      # bỏ "8W" lặt vặt, chỉ giữ công suất nguồn
            continue
        out.append(f"{num}{unit}")
    return list(dict.fromkeys(out))


def _page_ok(url: str, rows: list[list[str]], models: list[str], kinds: list[str],
             page_title: str = "", sizes: list[str] = None) -> tuple[bool, str]:
    """Cổng 1+2+3+4: đúng model, đúng dung lượng, đúng loại hàng, không phải site mình."""
    if any(d in url.lower() for d in SKIP_DOMAINS):
        return False, "nguồn bị chặn (site mình / sàn TMĐT)"
    blob = norm(url + " " + page_title + " " + " ".join(f"{k} {v}" for k, v in rows))
    hit = [m for m in models if norm(m).replace(" ", "") in blob.replace(" ", "")]
    if models and not hit:
        return False, f"không thấy mã model {models[:2]} trên trang"
    if not models:
        # không có mã model → đối chiếu bằng độ trùng TỪ ĐẶC TRƯNG của tên SP
        words = [w for w in norm(page_title or "").split() if len(w) > 2 and w not in WORD_STOP]
        mine = [w for w in norm(_TITLE.get("t", "")).split()
                if len(w) > 2 and w not in WORD_STOP]
        if mine:
            overlap = len(set(mine) & set(words)) / len(set(mine))
            if overlap < 0.6:
                return False, (f"tên SP không có mã model, tên trang nguồn chỉ trùng "
                               f"{int(overlap*100)}% từ khoá → không dám dùng")
            return True, f"khớp {int(overlap*100)}% từ khoá trong tên (không có mã model)"
    if kinds and not any(norm(k) in blob for k in kinds):
        return False, f"không khớp loại SP ({kinds[0]})"
    # Bẫy: phải chuẩn hoá HAI BÊN giống nhau, nếu không "2.5 inch" ↔ 2.5" loại oan.
    flat = blob.replace(" ", "")
    for s in (sizes or []):
        if norm(s).replace(" ", "") not in flat:
            return False, f"lệch dung lượng/kích thước: SP mình ghi {s}, trang nguồn không có"
    return True, (f"khớp model {hit[0] if hit else '—'}"
                  + (f" + đúng {', '.join(sizes)}" if sizes else ""))


def _agree(rows_a: list[list[str]], rows_b: list[list[str]]) -> dict[str, str]:
    """Cổng 5: dòng nào 2 nguồn nói giống nhau (so gần đúng)."""
    idx = {norm(k): v for k, v in rows_b}
    out = {}
    for k, v in rows_a:
        vb = idx.get(norm(k))
        if vb and SequenceMatcher(None, norm(v), norm(vb)).ratio() >= 0.7:
            out[norm(k)] = v
    return out


def research(title: str, product_type: str = "", max_sources: int = 4) -> dict:
    """Trả {ok, rows, sources, confirmed, reason} — rows là cặp [nhãn, giá trị] đã lọc."""
    if BLOCKED_KIND.search(title) or BLOCKED_KIND.search(product_type or ""):
        return {"ok": False, "reason": "nhóm không tự động (laptop / linh kiện thay thế)",
                "rows": [], "sources": [], "confirmed": 0}
    models, kinds = model_tokens(title), kind_words(product_type, title)
    sizes = size_tokens(title)
    _TITLE["t"] = title
    try:
        hits = ss.search_google(f"{title} thông số kỹ thuật", num=max_sources + 4)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"lỗi search: {e}", "rows": [], "sources": [],
                "confirmed": 0}

    cands, rejected = [], []
    for h in hits:
        url = h.get("link") or ""
        if not url or len(cands) >= max_sources:
            continue
        if any(d in url.lower() for d in SKIP_DOMAINS):
            rejected.append((url, "site mình / sàn TMĐT", h.get("title", "")))
            continue
        try:
            html = ss.requests.get(url, headers=ss.HEAD, timeout=16, verify=False).text
            rows = clean_rows(extract_spec_rows(html))
        except Exception:  # noqa: BLE001
            continue
        if len(rows) < 5:
            rejected.append((url, f"chỉ bóc được {len(rows)} dòng", h.get("title", "")))
            continue
        if len(rows) > MAX_ROWS:
            # giữ lại phần dòng có nhắc tới model (bỏ phần liệt kê SP khác)
            keep = [x for x in rows
                    if any(norm(m).replace(" ", "") in norm(f"{x[0]} {x[1]}").replace(" ", "")
                           for m in models)]
            rows = keep if 5 <= len(keep) <= MAX_ROWS else rows[:MAX_ROWS]
            rejected.append((url, f"trang trả {len(rows)} dòng, nghi trang liệt kê", h.get("title", "")))
        good, why = _page_ok(url, rows, models, kinds, h.get("title", ""), sizes)
        if not good:
            rejected.append((url, why, h.get("title", "")))
            continue
        cands.append({"url": url, "rows": rows, "why": why, "title": h.get("title", "")})

    if not cands:
        return {"ok": False, "reason": "không nguồn nào qua cổng kiểm", "rows": [],
                "sources": [], "rejected": rejected, "candidates": [], "confirmed": 0}

    cands.sort(key=lambda c: -len(c["rows"]))
    best = cands[0]
    best["picked"] = True
    confirmed = {}
    for other in cands[1:]:
        confirmed.update(_agree(best["rows"], other["rows"]))
    rows = [[k, v] for k, v in best["rows"]]
    return {"ok": len(rows) >= 6, "rows": rows, "candidates": cands,
            "sources": [c["url"] for c in cands], "rejected": rejected,
            "confirmed": len(confirmed),
            "confirmed_keys": list(confirmed.keys()),
            "reason": "" if len(rows) >= 6 else f"chỉ có {len(rows)} dòng",
            "evidence": best["why"]}
