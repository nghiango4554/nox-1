"""product_parser.py — parse SP name → loại, hãng, spec tags, slug.

Phase 1 of `/products/new` flow. Skips Mainboard (vợ tự viết bài).
Supports 13 loại theo `product_naming_rules.md`:
    Card Màn Hình, Ổ Cứng SSD/HDD, Vỏ Case, Tản Nhiệt, Fan Case, Màn Hình,
    Nguồn, Phím, Chuột, RAM, CPU, PC, Laptop.

Hãng matched against `data/brands.json` (master list). Hãng KHÔNG có trong list
→ flag `brand_is_new=True` để UI cảnh báo trước khi tạo SP mới (tránh tạo hãng dup).
"""

import json
import re
import unicodedata
from pathlib import Path


# (display_name, internal_key, prefix patterns at start of name — lowercased).
# Order matters — longer prefixes first to avoid partial matches.
LOAI_PATTERNS = [
    ("Card Màn Hình", "card_man_hinh", ["card màn hình"]),
    ("Ổ Cứng SSD",   "ssd",           ["ổ cứng ssd"]),
    ("Ổ Cứng HDD",   "hdd",           ["ổ cứng hdd"]),
    ("Vỏ Case",      "vo_case",       ["vỏ case"]),
    ("Tản Nhiệt",    "tan_nhiet",     ["tản nhiệt"]),
    ("Fan Case",     "fan_case",      ["fan case"]),
    ("Màn Hình",     "man_hinh",      ["màn hình"]),
    ("Nguồn",        "nguon",         ["nguồn"]),
    ("Phím",         "phim",          ["phím"]),
    ("Chuột",        "chuot",         ["chuột"]),
    ("RAM",          "ram",           ["ram"]),
    ("CPU",          "cpu",           ["cpu"]),
    ("PC",           "pc",            ["pc"]),
    ("Laptop",       "laptop",        ["laptop"]),
    # Mainboard skipped — vợ tự viết.
]

SUB_LOAI_MAP = {
    "man_hinh":  ["văn phòng", "gaming", "cong"],
    "phim":      ["cơ", "văn phòng"],
    "chuot":     ["gaming", "văn phòng"],
    "pc":        ["gaming", "văn phòng"],
    "laptop":    ["gaming", "văn phòng", "ai creator", "đồ họa"],
    "tan_nhiet": ["khí", "nước"],
}


def parse(name: str) -> dict:
    raw = (name or "").strip()
    if not raw:
        return _empty("Tên SP rỗng")

    name_l = raw.lower()

    loai = loai_key = None
    rest = raw
    for display, key, prefixes in LOAI_PATTERNS:
        for pfx in prefixes:
            if name_l == pfx or name_l.startswith(pfx + " "):
                loai = display
                loai_key = key
                rest = raw[len(pfx):].strip()
                break
        if loai:
            break

    if not loai:
        return _empty(
            "Không nhận diện được loại SP. Tên phải bắt đầu bằng 1 trong: "
            "Card Màn Hình / Ổ Cứng SSD / Ổ Cứng HDD / Vỏ Case / Tản Nhiệt / "
            "Fan Case / Màn Hình / Nguồn / Phím / Chuột / RAM / CPU / PC / Laptop. "
            "(Mainboard không hỗ trợ — vợ tự viết.)"
        )

    sub_loai = None
    rest_l = rest.lower()
    for sub in SUB_LOAI_MAP.get(loai_key, []):
        if rest_l == sub or rest_l.startswith(sub + " "):
            sub_loai = sub
            rest = rest[len(sub):].strip()
            break

    canonical, taken_len = _match_brand(rest)
    if canonical:
        hang = canonical
        brand_is_new = False
        rest_after_brand = rest[taken_len:].strip()
    else:
        parts = rest.split()
        hang = parts[0] if parts else None
        brand_is_new = bool(hang)
        rest_after_brand = " ".join(parts[1:]) if len(parts) > 1 else ""

    tags = []
    if sub_loai:
        tags.append(f"loai_{_norm_key(sub_loai)}")
    if hang:
        tags.append(f"hang_{_norm_key(hang)}")
    tags.extend(_spec_tags(loai_key, rest.lower()))

    return {
        "loai": loai,
        "loai_key": loai_key,
        "sub_loai": sub_loai,
        "hang": hang,
        "brand_is_new": brand_is_new,
        "tags": _dedupe(tags),
        "slug": _make_slug(raw),
        "note": "",
    }


def _empty(msg: str) -> dict:
    return {"loai": None, "loai_key": None, "sub_loai": None, "hang": None,
            "brand_is_new": False, "tags": [], "slug": "", "note": msg}


_BRANDS_PATH = Path(__file__).parent / "data" / "brands.json"
_BRANDS_CACHE = None  # list of (canonical, normalized) sorted by -len(normalized)


def _load_brands():
    global _BRANDS_CACHE
    if _BRANDS_CACHE is None:
        try:
            raw = json.loads(_BRANDS_PATH.read_text(encoding="utf-8"))
        except Exception:
            raw = []
        items = []
        for b in raw:
            b = (b or "").strip()
            if not b:
                continue
            items.append((b, _norm_match(b)))
        items.sort(key=lambda x: -len(x[1]))
        _BRANDS_CACHE = items
    return _BRANDS_CACHE


def _norm_match(s: str) -> str:
    """Normalize for brand match: lowercase + strip Vietnamese diacritics + collapse spaces.
    Keep hyphens, dots, `&` to distinguish E-DRA vs EDRA, G.SKILL vs GSKILL, etc."""
    s = (s or "").lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d")
    s = re.sub(r"\s+", " ", s)
    return s


def _match_brand(rest: str):
    """Return (canonical_form, length_in_orig_text) or (None, 0)."""
    if not rest:
        return None, 0
    rest_norm = _norm_match(rest)
    for canonical, b_norm in _load_brands():
        if not b_norm:
            continue
        if rest_norm == b_norm or rest_norm.startswith(b_norm + " "):
            n_words = b_norm.count(" ") + 1
            words = rest.split()
            taken_words = words[:n_words]
            taken = " ".join(taken_words)
            return canonical, len(taken)
    return None, 0


def _norm_key(s: str) -> str:
    s = (s or "").lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def _make_slug(name: str) -> str:
    s = _norm_key(name).replace("_", "-").strip("-")
    return re.sub(r"-+", "-", s)


def _dedupe(items):
    seen, out = set(), []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _spec_tags(loai_key: str, spec_l: str) -> list:
    tags = []

    # Cross-loại generic
    if "ddr5" in spec_l:
        tags.append("ddr5")
    elif "ddr4" in spec_l:
        tags.append("ddr4")
    if "rgb" in spec_l:
        tags.append("rgb")
    if "trắng" in spec_l:
        tags.append("mau_trắng")

    if loai_key == "ram":
        m = re.search(r"(\d+)\s*gb", spec_l)
        if m:
            tags.append(f"dl_{m.group(1)}gb")
        m = re.search(r"\b(\d{4})\b", spec_l)
        if m:
            tags.append(f"bus_{m.group(1)}")

    elif loai_key in ("ssd", "hdd"):
        m = re.search(r"(\d+(?:\.\d+)?)\s*(tb|gb)\b", spec_l)
        if m:
            n = m.group(1).replace(".", "_")
            tags.append(f"dl_{n}{m.group(2)}")
        if "nvme" in spec_l:
            tags.append("m2_nvme")
        elif "sata" in spec_l:
            tags.append("sata_iii")
        m = re.search(r"gen\s*(\d)\s*x\s*(\d)", spec_l)
        if m:
            tags.append(f"gen_pcie_{m.group(1)}x{m.group(2)}")

    elif loai_key == "cpu":
        m = re.search(r"core\s+(i\d)", spec_l)
        if m:
            tags.append(f"dong_{m.group(1)}")
        m = re.search(r"ryzen\s+(\d)", spec_l)
        if m:
            tags.append(f"dong_ryzen_{m.group(1)}")

    elif loai_key == "card_man_hinh":
        m = re.search(r"(rtx|gtx)\s*(\d{3,4})", spec_l)
        if m:
            tags.append(f"series_{m.group(1)}")
            tags.append(f"model_{m.group(1)}_{m.group(2)}")
        m = re.search(r"(\d+)\s*gb", spec_l)
        if m:
            tags.append(f"vram_{m.group(1)}gb")

    elif loai_key == "vo_case":
        for sz_match, sz_tag in [
            ("e-atx", "e_atx"), ("m-atx", "m_atx"), ("matx", "m_atx"),
            ("mini-itx", "mini_itx"), ("atx", "atx"),
        ]:
            if sz_match in spec_l:
                tags.append(f"size_{sz_tag}")
                break

    elif loai_key == "nguon":
        m = re.search(r"(\d{3,4})\s*w\b", spec_l)
        if m:
            tags.append(f"wattage_{m.group(1)}w")
        for lv in ["titanium", "platinum", "gold", "silver", "bronze"]:
            if lv in spec_l:
                tags.append(f"plus_{lv}")
                break

    elif loai_key == "tan_nhiet":
        if "dual" in spec_l:
            tags.append("dual_tower")
        m = re.search(r"(\d{2,3})\s*mm", spec_l)
        if m:
            tags.append(f"size_{m.group(1)}mm")

    elif loai_key == "man_hinh":
        m = re.search(r"(\d{2}(?:[.,]\d)?)\s*(?:inch|in\b|''|\")", spec_l)
        if m:
            tags.append(f"size_{m.group(1).replace('.', '_').replace(',', '_')}inch")
        m = re.search(r"(\d{2,3})\s*hz", spec_l)
        if m:
            tags.append(f"hz_{m.group(1)}")
        for panel in ["ips", "va", "oled", "tn"]:
            if panel in spec_l:
                tags.append(f"tam_{panel}")
                break
        for res in ["4k", "2k", "fhd", "wuxga", "qhd", "uhd"]:
            if res in spec_l:
                tags.append(f"res_{res}")
                break

    elif loai_key in ("phim", "chuot"):
        if "không dây" in spec_l:
            tags.append("ket_noi_khong_day")
        elif "có dây" in spec_l:
            tags.append("ket_noi_co_day")

    elif loai_key == "laptop":
        m = re.search(r"(\d{2}(?:[.,]\d)?)''", spec_l)
        if m:
            tags.append(f"size_{m.group(1).replace('.', '_').replace(',', '_')}inch")
        if "rtx" in spec_l or "gtx" in spec_l:
            tags.append("co_vga_roi")

    return tags


if __name__ == "__main__":
    # Quick smoke test
    samples = [
        "Card Màn Hình Asus Dual RTX 3060 12GB V1",
        "RAM Centaur Ragnarok Pro RGB 8GB DDR4 3200 Đen",
        "Ổ Cứng SSD Colorful CN600 Pro 1TB M2 NVMe",
        "Màn Hình Gaming MSI G275L 27 Inch (FHD, IPS, 144Hz, 1ms)",
        "Phím Cơ Aula S98 Pro Không Dây",
        "Nguồn Gigabyte P650SS ICE 650W 80 Plus Silver",
        "Laptop Asus Gaming TUF F16 FX607JU-N3139W (i7-13650HX, 16GB, 512GB, RTX 4050, 16'' WUXGA 165Hz)",
        "Mainboard Asus Prime H610M-K DDR4",  # should be rejected
    ]
    import json
    for s in samples:
        print(s)
        print(" ", json.dumps(parse(s), ensure_ascii=False))
        print()
