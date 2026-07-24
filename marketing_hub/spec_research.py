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
# Bẫy 23/7: bảng "thông số" của nhiều trang bán hàng có kèm KHỐI LIÊN HỆ / PHÁP NHÂN
# (Marketing | 028 62773767 · Email | support@... · Địa chỉ | 119 Nguyễn Văn Công...).
# Cổng giá chặn được tiền nhưng KHÔNG chặn mấy dòng này → 117 nguồn 'dung' bị dính.
# ⚠️ Nhãn KHỚP TRỌN VẸN — nếu dùng match() theo tiền tố sẽ giết luôn dòng spec thật
# ("Hỗ trợ mainboard", "Hỗ trợ VGA tối đa", "Hỗ trợ radiator"...).
CONTACT_KEY_EXACT = re.compile(
    r"(?i)^[»\-\s]*(hotline|điện thoại|đt|tel|fax|sđt|số điện thoại|email|mail|e-mail"
    r"|zalo|website|web|fanpage|facebook|địa chỉ|dia chi|showroom|chi nhánh|cửa hàng"
    r"|trụ sở|văn phòng|mã số thuế|mst)\s*$")
# ⚠️ Nhãn phòng ban CÓ THỂ là nhãn spec thật ("Hỗ trợ | 2xSSD;2xHDD; ATX PSU",
# "Hỗ trợ | DLSS 3.0, Ray Tracing"). CHỈ gỡ khi GIÁ TRỊ là thông tin liên hệ.
DEPT_KEY = re.compile(r"(?i)^[»\-\s]*(kinh doanh|kế toán|marketing|cskh|hỗ trợ|tư vấn"
                      r"|bán hàng|k[ỹĩ] thuật|chăm sóc khách hàng)\s*$")
# Nhãn nhiều từ, không thể nhầm với spec
CONTACT_KEY_START = re.compile(
    r"(?i)^[»\-\s]*(mail cskh|giờ mở cửa|giờ làm việc|số đăng ký kinh doanh|giấy phép"
    r"|người đại diện|đại diện pháp luật|địa chỉ đăng k[íý] kinh doanh|bảo hành tại)")
# Rò rỉ 23/7: dòng giờ mở cửa nhưng nhãn chỉ là "Sáng" / "Chiều"
#   Sáng | 8h - 12h Chiều: 13h30 - 17h30
# ⚠️ KHÔNG chặn theo khoảng giờ trần: "Thời lượng pin | 8h - 12h" là spec THẬT.
# Chỉ chặn khi có khoảng giờ ĐI KÈM từ chỉ buổi/thứ trong ngày.
WORKHOUR_VAL = re.compile(
    r"(?i)\d{1,2}\s*[h:]\s*\d{0,2}\s*[-–]\s*\d{1,2}\s*[h:]"
    r".*(sáng|chiều|tối|t2|t7|thứ\s*[2-7]|chủ nhật|hàng ngày|cả tuần)"
    r"|(sáng|chiều|tối|thứ\s*[2-7]|chủ nhật)\s*:?\s*\d{1,2}\s*[h:]\s*\d{0,2}\s*[-–]")
WORKHOUR_KEY = re.compile(r"(?i)^[»\-\s]*(sáng|chiều|tối|buổi sáng|buổi chiều|buổi tối)\s*$")
CONTACT_VAL = re.compile(
    r"(?i)[\w.\-]+@[\w.\-]+\.\w+"                    # email
    r"|(?:https?://|www\.)\S+"                        # link
    r"|(?<!\d)0\d{2,3}[\s.\-]?\d{3}[\s.\-]?\d{3,4}(?!\d)"   # số điện thoại VN
    r"|\b\d+\s*sản phẩm\b")                           # dòng tồn kho chi nhánh
# Địa chỉ: cần ĐỒNG THỜI có từ khoá địa danh VÀ chữ số. KHÔNG đưa "đường" vào đây,
# nếu không sẽ giết "Đường kính quạt | 120mm".
ADDR_HINT = re.compile(r"(?i)\b(quận|phường|ngõ|tp\.?\s?[–\-]?\s?hcm|hà nội|đà nẵng|hải phòng"
                       r"|thành phố hồ chí minh|bạch mai|cầu giấy)\b")
# Số điện thoại viết đủ kiểu ngắt ("028 6272 2845", "0934 019 488"): bỏ hết dấu ngắt
# rồi tìm dãy 9-11 chữ số mở đầu bằng 0. Không dính "0,16A" hay "0.26-1,81 mmH2O".
_PHONE_DIGITS = re.compile(r"(?<!\d)0\d{8,10}(?!\d)")


def _has_phone(v: str) -> bool:
    return bool(_PHONE_DIGITS.search(re.sub(r"[\s.\-()]+", "", v or "")))


def _is_contact_value(v: str) -> bool:
    return bool(CONTACT_VAL.search(v) or _has_phone(v)
                or (ADDR_HINT.search(v) and re.search(r"\d", v)))
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
    r"(thông số kỹ thuật|thông số chi tiết|thông tin chi tiết|specification|tech spec"
    r"|specifications|parameters|product parameters|technical data|规格参数)"
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
            elif len(cells) == 1:
                # Bẫy 23/7 (trang hãng Jonsbo): mỗi hàng CHỈ 1 ô, nội dung dạng
                # "Model：CR-1000 EVO ARGB Black" với dấu hai chấm FULL-WIDTH ：
                # (U+FF1A) kiểu Trung/Nhật. Không bắt thì trang hãng ra 0 dòng.
                t1 = _txt(cells[0])
                m1 = re.match(r"^([^:：]{2,44})\s*[:：]\s*(.+)$", t1)
                if m1 and len(m1.group(2).strip()) <= 220:
                    lbl, val = m1.group(1).strip(), m1.group(2)
                    # Bẫy 23/7: trang hãng Jonsbo xếp 2 MODEL cạnh nhau trong CÙNG 1 ô
                    #   "Speed：700-2400rpm  Speed：700-1800rpm"
                    # → nhãn lặp lại lần 2 = sang model khác, phải CẮT.
                    # Không cắt theo mọi dấu ： vì "Scope: INTEL：LGA1700 AMD：AM4" là hợp lệ.
                    cut = re.search(rf"(?i)\s{re.escape(lbl)}\s*[:：]", val)
                    if cut:
                        val = val[:cut.start()]
                    val = re.sub(r"\s+", " ", val).strip()
                    # ⚠️ Bẫy 23/7 (trang AOC): giá trị "16:9" hay "1300:1" CHỨA dấu hai
                    # chấm → cắt ở dấu ĐẦU khiến nhãn nuốt số, value trơ lại "9"/"1".
                    # Dấu hiệu: value chỉ còn 1-3 chữ số VÀ nhãn kết thúc bằng số.
                    if re.fullmatch(r"\d{1,3}", val) and re.search(r"\d\s*$", lbl):
                        continue
                    if val:
                        out.append({"label": lbl, "value": val})
        for dl in re.findall(r"(?is)<dl[^>]*>(.*?)</dl>", frag):
            dts = re.findall(r"(?is)<dt[^>]*>(.*?)</dt>", dl)
            dds = re.findall(r"(?is)<dd[^>]*>(.*?)</dd>", dl)
            for a, b in zip(dts, dds):
                out.append({"label": _txt(a), "value": _txt(b)})
        for li in re.findall(r"(?is)<li[^>]*>(.*?)</li>", frag):
            t = _txt(li)
            mm = re.match(r"^([^:：]{2,44})[:：]\s*(.+)$", t)
            if mm:
                lb, vl = mm.group(1), mm.group(2).strip()
                # cùng bẫy "16:9" / "1300:1" như nhánh ô đơn ở trên
                if re.fullmatch(r"\d{1,3}", vl) and re.search(r"\d\s*$", lb):
                    continue
                out.append({"label": lb, "value": vl})
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
        if (CONTACT_KEY_EXACT.match(k) or CONTACT_KEY_START.match(k)
                or _is_contact_value(v)
                or (DEPT_KEY.match(k) and _is_contact_value(v))
                or WORKHOUR_VAL.search(v)
                or (WORKHOUR_KEY.match(k) and re.search(r"\d\s*[h:]", v))):
            continue                                       # liên hệ / pháp nhân của shop
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


# ── Cổng 23/7: TRANG NGUỒN TRỘN BẢNG CỦA SP KHÁC ─────────────────────────────
# Ca thật: trang SSD Apacer 500GB có dòng "Dung lượng | 12GB GDDR6X" (spec card đồ
# hoạ lẫn vào); trang màn AIWA 23.8" có cả "Panel IPS/1ms" (đúng) lẫn "32Inch/VA/
# 165Hz" (của SP khác). Tiêu đề trang vẫn khớp đúng SP nên mọi cổng cũ đều cho qua.
# → Đối chiếu NGƯỢC với chính TÊN SP của mình, gỡ đúng dòng mâu thuẫn.
# KHÔNG soi "ms": GtG / MPRT / có OD chênh nhau là chuyện bình thường, không phải trộn.
_T_HZ = re.compile(r"(\d{2,3})\s*hz", re.I)
_T_IN = re.compile(r"(\d{2}(?:[.,]\d)?)\s*(?:inch|\")", re.I)
_T_CAP = re.compile(r"(\d{1,4})\s*(gb|tb)\b", re.I)
_T_W = re.compile(r"(\d{3,4})\s*w\b", re.I)
_T_PANEL = re.compile(r"\b(IPS|HVA|VA|TN|OLED)\b", re.I)
# (mẫu số, mẫu nhãn, dung sai tuyệt đối)
_TITLE_GATES = [
    (_T_HZ, re.compile(r"(?i)tần số|refresh"), 0.0),
    (_T_IN, re.compile(r"(?i)kích thước màn|kích cỡ màn|kích thước tấm nền|screen size"
                       r"|^kích thước$"), 1.0),     # 32" vs 31.5" là làm tròn, không gỡ
    (_T_CAP, re.compile(r"(?i)dung lượng|capacity"), 0.0),
    (_T_W, re.compile(r"(?i)công suất(?! tiêu thụ)"), 0.0),
]
# ⚠️ Nhãn nói về mức TỐI ĐA / HỖ TRỢ / một ĐƯỜNG ĐIỆN riêng thì KHÔNG được đem so với
# con số trong tên SP. Ca thật: nguồn 500W có dòng "Công suất 12V tối đa: 402W";
# nguồn 850W có "Công suất qua PCI-E 5.0 16 pin: 600W"; laptop 16GB có
# "Dung lượng RAM tối đa: Up to 24GB". Cả ba đều đúng, trước đó bị gỡ oan.
_GATE_SKIP = re.compile(r"(?i)tối đa|tối thiểu|hỗ trợ|up to|maximum|\bmax\b|nâng cấp"
                        r"|12\s*v|pci|đầu cắm|mỗi |trên mỗi|combined|tổng cộng")


def _nums(pairs) -> list[float]:
    out = []
    for x in pairs:
        t = x[0] if isinstance(x, tuple) else x
        try:
            out.append(float(str(t).replace(",", ".")))
        except ValueError:
            pass
    return out


def drop_title_conflicts(title: str, rows: list[list[str]]) -> tuple[list, list]:
    """Gỡ dòng cãi lại TÊN SP của mình. Trả (giữ lại, đã gỡ)."""
    keep, drop = [], []
    t_panel = {p.upper() for p in _T_PANEL.findall(title or "")}
    for k, v in rows:
        bad = False
        if _GATE_SKIP.search(k):
            keep.append([k, v])
            continue
        for pat, kpat, tol in _TITLE_GATES:
            if not kpat.search(k):
                continue
            tv, sv = _nums(pat.findall(title or "")), _nums(pat.findall(v))
            if tv and sv and not any(abs(a - b) <= tol for a in tv for b in sv):
                bad = True
                break
        if not bad and t_panel and re.search(r"(?i)tấm nền|panel|loại màn", k):
            sp = {p.upper() for p in _T_PANEL.findall(v)}
            if sp and not (t_panel & sp):
                bad = True
        (drop if bad else keep).append([k, v])
    return keep, drop


# ── Cổng 23/7 (2): BẢNG SPEC CỦA LOẠI HÀNG KHÁC ──────────────────────────────
# Ca thật: trang "Vỏ Case E-DRA ECS1303 White" (tiêu đề khớp đúng SP mình) nhưng
# bảng spec là của card TUF-RTX5080: GPU, Nhân CUDA, Dung lượng bộ nhớ 16GB.
# Cổng kind_words chỉ soi TIÊU ĐỀ nên cho qua. Phải soi luôn NHÃN trong bảng.
# ⚠️ Dấu vân tay phải là thứ CHỈ loại hàng đó mới có. Bản đầu 23/7 quá rộng nên
# báo nhầm 7/7 ca: "Số nhân CUDA" + "Xung nhịp cơ bản" của VGA bị chấm là CPU,
# "Chipset"/"Socket" của VGA bị chấm là MAINBOARD. Đã siết lại:
_FINGERPRINT = {
    # "^gpu$" an toàn: SP loại VGA đã tự loại mình khỏi danh sách cấm qua _SELF_KIND,
    # nên nhãn này chỉ kích hoạt trên vỏ case / ghế / loa... vốn không bao giờ có GPU.
    "VGA": re.compile(r"(?i)nhân cuda|cuda core|tensor core|ray tracing core|^gpu$"),
    # khe cắm là thứ chỉ bo mạch chủ mới liệt kê; KHÔNG dùng chipset/socket vì VGA cũng có
    "MAINBOARD": re.compile(r"(?i)khe pcie|khe ram|khe m\.2|số khe ram|form factor bo mạch"),
    # "số nhân" dính "Số nhân CUDA"; phải là nhân/luồng của CPU
    "CPU": re.compile(r"(?i)số luồng|số nhân xử lý|bộ nhớ đệm l[123]|tdp cpu"),
    "MÀN HÌNH": re.compile(r"(?i)tần số quét|tấm nền|độ phủ màu"),
    "SSD/HDD": re.compile(r"(?i)tốc độ đọc|tốc độ ghi|\bnand\b|\btbw\b"),
    "NGUỒN": re.compile(r"(?i)chứng nhận 80|80 plus|full[- ]modular"),
    # 23/7: chuột và bàn phím hay TRÙNG MÃ (DarkFlash DK104 có cả 2) → trang hãng
    # chỉ có 1 trang, SP kia vớ nhầm. Phải cho 2 loại này chặn lẫn nhau.
    "CHUỘT": re.compile(r"(?i)\bdpi\b|cảm biến quang|microswitch|độ phân giải chuột"),
    "BÀN PHÍM": re.compile(r"(?i)số phím|layout bàn phím|keycap|hot[- ]swap|switch quang"),
}
_FORBID = {
    "VỎ CASE": ["VGA", "MAINBOARD", "CPU", "SSD/HDD"],
    "BÀN PHÍM": ["VGA", "MAINBOARD", "CPU", "MÀN HÌNH", "SSD/HDD", "CHUỘT"],
    "CHUỘT": ["VGA", "MAINBOARD", "CPU", "MÀN HÌNH", "SSD/HDD", "BÀN PHÍM"],
    "TAI NGHE": ["VGA", "MAINBOARD", "CPU", "MÀN HÌNH", "SSD/HDD"],
    "LOA": ["VGA", "MAINBOARD", "CPU", "MÀN HÌNH", "SSD/HDD"],
    "GHẾ": ["VGA", "MAINBOARD", "CPU", "MÀN HÌNH", "SSD/HDD", "NGUỒN"],
    "FAN": ["VGA", "MAINBOARD", "CPU", "MÀN HÌNH", "SSD/HDD"],
    "TẢN NHIỆT": ["VGA", "MAINBOARD", "MÀN HÌNH", "SSD/HDD"],
    "MÀN HÌNH": ["VGA", "MAINBOARD", "CPU", "SSD/HDD"],
}


# ⚠️ "Card màn hình" chứa chữ "màn hình" → dính luật của MÀN HÌNH rồi tự chặn chính nó.
# Phải nhận diện SP thuộc loại gì TRƯỚC, rồi loại chính nó khỏi danh sách cấm.
_SELF_KIND = [
    ("VGA", re.compile(r"(?i)\bvga\b|card màn hình|card đồ họa|card đồ hoạ")),
    ("MÀN HÌNH", re.compile(r"(?i)^màn hình|\bmonitor\b")),
    ("MAINBOARD", re.compile(r"(?i)mainboard|bo mạch chủ")),
    ("CPU", re.compile(r"(?i)\bcpu\b|bộ vi xử lý")),
    ("SSD/HDD", re.compile(r"(?i)\bssd\b|\bhdd\b|ổ cứng")),
    ("NGUỒN", re.compile(r"(?i)^nguồn|nguồn máy tính|\bpsu\b")),
]


def wrong_kind(product_type: str, title: str, rows: list[list[str]]) -> str:
    """Trả tên loại hàng bị lẫn vào, '' nếu sạch. Cần >=2 nhãn mới tính."""
    raw = f"{product_type} {title}"
    own = [k for k, pat in _SELF_KIND if pat.search(raw)]
    blob = norm(raw).upper()
    forb = next((v for k, v in _FORBID.items() if norm(k).upper() in blob), None)
    if not forb:
        return ""
    forb = [k for k in forb if k not in own]
    if not forb:
        return ""
    labels = [str(r[0]) for r in rows if isinstance(r, (list, tuple)) and len(r) >= 2]
    for kind in forb:
        if sum(1 for l in labels if _FINGERPRINT[kind].search(l)) >= 2:
            return kind
    return ""


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
            resp = ss.requests.get(url, headers=ss.HEAD, timeout=16, verify=False)
            # Bẫy 23/7: trang không khai báo charset → requests rơi về ISO-8859-1 →
            # spec lưu vào DB thành "ThÆ°Æ¡ng hiá»u" (93 nguồn đã dính). Đoán lại bảng mã.
            if not resp.encoding or resp.encoding.lower() in ("iso-8859-1", "ascii"):
                resp.encoding = resp.apparent_encoding or "utf-8"
            html = resp.text
            rows = clean_rows(extract_spec_rows(html))
            rows, conflicted = drop_title_conflicts(title, rows)
        except Exception:  # noqa: BLE001
            continue
        if conflicted:
            rejected.append((url, f"gỡ {len(conflicted)} dòng cãi lại tên SP "
                                  f"({conflicted[0][0]}: {conflicted[0][1][:38]}) → trang trộn "
                                  f"bảng của SP khác", h.get("title", "")))
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
        lan = wrong_kind(product_type, title, rows)
        if lan:
            rejected.append((url, f"bảng spec là của {lan}, không phải loại hàng này",
                             h.get("title", "")))
            continue
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
