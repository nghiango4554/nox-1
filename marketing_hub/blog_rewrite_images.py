# -*- coding: utf-8 -*-
"""Blog Rewrite — image classification + availability (store-aware, dùng chung).

ROOT CAUSE: file.hstatic.net là CDN dùng chung MỌI shop Haravan → KHÔNG coi mọi
hstatic = Sintech. Phân loại theo STORE ID trong path (Sintech=200000860097,
GEARVN=1000026716...). Read-only — KHÔNG upload/PUT/rehost.
"""
import json, re, time
from pathlib import Path
from urllib.parse import urlparse
import requests, urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_CFG_PATH = Path(__file__).parent / "state" / "blog_rewrite_config.json"

_COMPETITOR = ("gearvn", "fptshop", "cellphones", "memoryzone", "tgdd", "thegioididong",
               "dienmayxanh", "hacom", "hoangha", "anphat", "phongvu", "didongviet",
               "phucanh", "maytinhcdc", "nguyenkim", "huucomputer")
_NEWS = ("genk", "quantrimang", "tinhte", "vnexpress", "vnecdn", "thanhnien", "kenh14",
         "cafef", "sforum", "futurecdn", "wccftech", "pcworld", "pcmag", "techcrunch",
         "techradar", "notebookcheck", "makeuseof", "laptopnow")
_OFFICIAL = ("intel.com", "asus.com", "nvidia.com", "amd.com", "msi.com", "gigabyte",
             "corsair", "logitech", "razer", "samsung.com", "kingston", "westerndigital",
             "seagate", "apple.com", "microsoft.com", "dell.com", "hp.com", "lenovo",
             "acer.com", "coolermaster", "noctua", "asrock", "leobog", "akko")
# store ID đã biết (chỉ để ghi chú nguồn — KHÔNG ảnh hưởng phân loại Sintech)
KNOWN_STORES = {"200000860097": "Sintech", "1000026716": "GEARVN"}

UA = {"User-Agent": "Mozilla/5.0 (compatible; SintechImgCheck/1.0)", "Referer": "https://sintech.vn/"}


def sintech_store_id():
    try:
        return str(json.loads(_CFG_PATH.read_text(encoding="utf-8")).get("sintech_haravan_store_id") or "").strip()
    except Exception:
        return ""  # thiếu config → KHÔNG auto coi ảnh là Sintech


def extract_hstatic_store_id(src):
    m = re.search(r"hstatic\.net/(\d{6,})/", src or "") or re.search(r"haravanstatic\.com/(\d{6,})/", src or "")
    if m:
        return m.group(1)
    m2 = re.search(r"/(\d{9,})/", src or "")
    return m2.group(1) if m2 else None


def is_sintech_image(src, store_id=None):
    store_id = store_id or sintech_store_id()
    h = (urlparse(src or "").hostname or "").lower()
    if "sintech.vn" in h or "myharavan" in h:
        return True
    if "hstatic.net" in h or "haravanstatic" in h:
        sid = extract_hstatic_store_id(src)
        return bool(store_id) and sid == store_id
    return False


def classify_image_source(src, store_id=None):
    store_id = store_id or sintech_store_id()
    if not src or not src.strip():
        return "INVALID_URL"
    h = (urlparse(src).hostname or "").lower()
    if not h:
        return "INVALID_URL"
    low = src.lower()
    if "sintech.vn" in h or "myharavan" in h:
        return "SINTECH_OWNED"
    if "hstatic.net" in h or "haravanstatic" in h:
        sid = extract_hstatic_store_id(src)
        if not sid:
            return "UNKNOWN_EXTERNAL"
        if store_id and sid == store_id:
            return "SINTECH_OWNED"
        # store khác → nếu brand đối thủ trong path → competitor, else HARAVAN_OTHER_STORE
        if any(b in low for b in _COMPETITOR):
            return "COMPETITOR_SOURCE"
        return "HARAVAN_OTHER_STORE"
    if any(b in low for b in _COMPETITOR):
        return "COMPETITOR_SOURCE"
    if any(b in low for b in _NEWS):
        return "NEWS_MEDIA_SOURCE"
    if any(b in h for b in _OFFICIAL):
        return "OFFICIAL_MANUFACTURER"
    return "UNKNOWN_EXTERNAL"


def check_image_availability(src, timeout=4):
    """Read-only HEAD (GET fallback nếu 403/405). KHÔNG download full."""
    if not src or not (src.startswith("http") or src.startswith("//")):
        return {"reachable": False, "status_code": 0, "error_type": "invalid_url", "final_url": "", "checked_at": _now()}
    url = ("https:" + src) if src.startswith("//") else src
    try:
        r = requests.head(url, headers=UA, timeout=timeout, verify=False, allow_redirects=True)
        sc = r.status_code
        try: r.close()
        except Exception: pass
        if sc in (403, 405):
            r2 = requests.get(url, headers=UA, timeout=timeout + 2, verify=False, allow_redirects=True, stream=True)
            sc = r2.status_code
            try: r2.close()
            except Exception: pass
        if 200 <= sc < 400:
            return {"reachable": True, "status_code": sc, "error_type": None, "final_url": url, "checked_at": _now()}
        if sc in (404, 410):
            return {"reachable": False, "status_code": sc, "error_type": "dead", "final_url": url, "checked_at": _now()}
        return {"reachable": False, "status_code": sc, "error_type": "uncertain", "final_url": url, "checked_at": _now()}
    except Exception as e:
        es = str(e).lower()
        kind = "timeout" if ("timed out" in es or "timeout" in es) else "error"
        return {"reachable": False, "status_code": 0, "error_type": kind, "final_url": url, "checked_at": _now()}


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


_RIGHTS = {
    "SINTECH_OWNED": "OWNED_SINTECH", "OFFICIAL_MANUFACTURER": "OFFICIAL_MANUFACTURER",
    "COMPETITOR_SOURCE": "COMPETITOR_SOURCE", "NEWS_MEDIA_SOURCE": "NEWS_MEDIA_SOURCE",
    "HARAVAN_OTHER_STORE": "UNKNOWN_SOURCE", "UNKNOWN_EXTERNAL": "UNKNOWN_SOURCE",
    "INVALID_URL": "MANUAL_REVIEW",
}


def build_image_audit(src, alt=None, check_availability=True, store_id=None):
    store_id = store_id or sintech_store_id()
    h = (urlparse(src or "").hostname or "").lower()
    fn = (src or "").split("?")[0].rsplit("/", 1)[-1].lower()
    sid = extract_hstatic_store_id(src or "")
    source_class = classify_image_source(src, store_id)
    avail = check_image_availability(src) if check_availability else {"reachable": None, "status_code": None, "error_type": None}
    rights = _RIGHTS.get(source_class, "MANUAL_REVIEW")
    altl = (alt or "").lower()
    brand_alt = sorted(set(b for b in _COMPETITOR if b in altl))
    brand_fn = sorted(set(b for b in _COMPETITOR if b in fn))
    brand_url = sorted(set(b for b in _COMPETITOR if b in (src or "").lower()))
    # recommended action + apply gate
    if avail.get("error_type") == "dead":
        action, gate = "REMOVE_DEAD_IMAGE", "BLOCK_DEAD_IMAGE"
    elif source_class == "SINTECH_OWNED":
        action, gate = "KEEP", "ALLOW"
    elif source_class == "OFFICIAL_MANUFACTURER":
        action, gate = "REHOST_ALLOWED_LATER", "REVIEW_REQUIRED"
    elif source_class == "COMPETITOR_SOURCE":
        action, gate = "REPLACE_WITH_OFFICIAL_IMAGE", "BLOCK_COMPETITOR_IMAGE"
    elif source_class == "NEWS_MEDIA_SOURCE":
        action, gate = "CREATE_ORIGINAL_IMAGE", "BLOCK_COMPETITOR_IMAGE"
    else:  # HARAVAN_OTHER_STORE / UNKNOWN_EXTERNAL / INVALID
        action, gate = "MANUAL_REVIEW", "BLOCK_UNKNOWN_IMAGE"
    return {
        "src": src, "hostname": h, "store_id": sid, "alt": alt or "", "filename": fn,
        "source_class": source_class, "reachable": avail.get("reachable"),
        "status_code": avail.get("status_code"), "error_type": avail.get("error_type"),
        "brand_in_alt": brand_alt, "brand_in_filename": brand_fn, "brand_in_url": brand_url,
        "rights_status": rights, "recommended_action": action, "apply_gate_status": gate,
    }


def audit_body_images(body_html, check_availability=True, store_id=None):
    """Audit mọi <img> trong body. Trả (list audit, gate_summary)."""
    store_id = store_id or sintech_store_id()
    out = []
    seen = set()
    for tag in re.findall(r"<img[^>]+>", body_html or "", re.I):
        sm = re.search(r'src="([^"]+)"', tag, re.I); am = re.search(r'alt="([^"]*)"', tag, re.I)
        if not sm:
            continue
        src = sm.group(1)
        a = build_image_audit(src, am.group(1) if am else "", check_availability and src not in seen, store_id)
        seen.add(src)
        out.append(a)
    blocks = [a for a in out if a["apply_gate_status"].startswith("BLOCK")]
    summary = {
        "total": len(out),
        "safe": sum(1 for a in out if a["apply_gate_status"] == "ALLOW"),
        "blocked": len(blocks),
        "review": sum(1 for a in out if a["apply_gate_status"] == "REVIEW_REQUIRED"),
        "dead": sum(1 for a in out if a["apply_gate_status"] == "BLOCK_DEAD_IMAGE"),
        "competitor": sum(1 for a in out if a["apply_gate_status"] == "BLOCK_COMPETITOR_IMAGE"),
        "unknown": sum(1 for a in out if a["apply_gate_status"] == "BLOCK_UNKNOWN_IMAGE"),
        "other_store": sum(1 for a in out if a["source_class"] == "HARAVAN_OTHER_STORE"),
        "apply_allowed": len(blocks) == 0,
    }
    return out, summary
