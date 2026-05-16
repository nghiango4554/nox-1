"""SEO crawler + analyzer cho sintech.vn — fetch sitemap, crawl, chấm điểm."""
import json
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlparse, urljoin

import requests
from requests.exceptions import (
    SSLError, ConnectTimeout, ReadTimeout, Timeout,
    ConnectionError as ReqConnError, TooManyRedirects, ChunkedEncodingError,
    InvalidURL, MissingSchema, InvalidSchema,
)
from bs4 import BeautifulSoup

import db
import haravan_client
from pathlib import Path

# Readability scorer cho tiếng Việt (refactor C: moved to scoring_core).
# Vẫn re-export _readability_score qua scoring_core để backward compat.
try:
    from scoring_core import readability_metrics as _readability_score
except Exception:
    _readability_score = None

# Shared scoring helpers (unified scoring engine — refactor C 2026-05-16).
try:
    import scoring_core as _sc
except Exception:
    _sc = None


# Mã lỗi chi tiết khi check link (status_code = 0)
LINK_ERROR_LABELS = {
    "dns_fail":           ("🌐", "DNS không tìm thấy",   "Domain không tồn tại / hết hạn / DNS chưa setup"),
    "conn_refused":       ("🚫", "Server từ chối",       "Server đang tắt hoặc firewall chặn cổng"),
    "conn_timeout":       ("⏳", "Connect timeout",       "Không bắt tay TCP được trong 10s — server quá tải hoặc nghẽn mạng"),
    "read_timeout":       ("📭", "Read timeout",          "Server tiếp nhận nhưng không trả response trong 12s"),
    "ssl_error":          ("🔒", "SSL/HTTPS lỗi",         "Chứng chỉ HTTPS hết hạn / sai domain / không tin cậy"),
    "too_many_redirects": ("🔁", "Redirect loop",         "Chuỗi redirect quá dài (>30) — vòng lặp"),
    "unreachable":        ("📡", "Network unreachable",   "Không có route tới server (cấu hình mạng)"),
    "invalid_url":        ("❓", "URL sai cú pháp",       "Link viết sai chuẩn URL"),
    "chunked_error":      ("📦", "Response truyền dở",    "Server đứt giữa chừng khi gửi"),
    "other_error":        ("⚠️", "Lỗi khác",              "Lỗi không phân loại được"),
}


def _classify_link_error(exc: Exception) -> str:
    """Map requests exception → mã lỗi chi tiết."""
    if isinstance(exc, SSLError):
        return "ssl_error"
    if isinstance(exc, TooManyRedirects):
        return "too_many_redirects"
    if isinstance(exc, ConnectTimeout):
        return "conn_timeout"
    if isinstance(exc, ReadTimeout):
        return "read_timeout"
    if isinstance(exc, (InvalidURL, MissingSchema, InvalidSchema)):
        return "invalid_url"
    if isinstance(exc, ChunkedEncodingError):
        return "chunked_error"
    if isinstance(exc, ReqConnError):
        msg = str(exc).lower()
        if any(k in msg for k in (
            "name or service not known", "getaddrinfo failed",
            "nodename nor servname", "name resolution",
            "no address associated", "temporary failure in name resolution",
        )):
            return "dns_fail"
        if "connection refused" in msg or "[errno 111]" in msg or "[winerror 10061]" in msg:
            return "conn_refused"
        if "no route to host" in msg or "network is unreachable" in msg or "[winerror 10065]" in msg:
            return "unreachable"
        if "timed out" in msg or "timeout" in msg:
            return "conn_timeout"
        return "other_error"
    if isinstance(exc, Timeout):
        return "conn_timeout"
    return "other_error"


SITEMAP_INDEX = "https://sintech.vn/sitemap.xml"
USER_AGENT = "SintechHubSEOBot/1.0 (+marketing_hub)"


# ─────────── SEO RULES CONFIG (editable via /seo/rules UI) ───────────
import os as _os_seo
RULES_CONFIG_PATH = _os_seo.path.join(_os_seo.path.dirname(__file__), "data", "seo_rules_config.json")
_rules_cache = {"data": None, "mtime": 0}
_rules_lock = threading.Lock()


def load_rules_config(force: bool = False) -> dict:
    """Load + cache config. Auto-reload nếu file mtime đổi."""
    try:
        mtime = _os_seo.path.getmtime(RULES_CONFIG_PATH)
    except OSError:
        return {"version": "default", "thresholds": {"good": 65, "ok": 50}, "rules": []}
    with _rules_lock:
        if force or _rules_cache["data"] is None or mtime != _rules_cache["mtime"]:
            try:
                with open(RULES_CONFIG_PATH, "r", encoding="utf-8") as f:
                    _rules_cache["data"] = json.load(f)
                _rules_cache["mtime"] = mtime
            except Exception as e:
                print(f"[rules_config] load fail: {e}")
                if _rules_cache["data"] is None:
                    _rules_cache["data"] = {"version": "fallback", "thresholds": {"good": 65, "ok": 50}, "rules": []}
        return _rules_cache["data"]


def save_rules_config(cfg: dict):
    """Atomic write config + invalidate cache."""
    tmp = RULES_CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    _os_seo.replace(tmp, RULES_CONFIG_PATH)
    with _rules_lock:
        _rules_cache["data"] = None
        _rules_cache["mtime"] = 0


def _rule(code: str) -> dict:
    """Lookup rule config by code. Return default-enabled if missing."""
    cfg = load_rules_config()
    for r in cfg.get("rules", []):
        if r.get("code") == code:
            return r
    return {"code": code, "enabled": True, "level": "warn", "score": 0, "msg": code}


def _rule_apply(code: str, condition: bool, **fmt) -> tuple:
    """Helper: check rule enabled + condition met → return (passed, issue_dict, score).

    passed=True nếu condition pass (rule không trigger issue) — caller dùng score như bonus.
    passed=False nếu rule trigger → return issue dict.
    Khi rule disabled → passed=True, no issue, score=0.
    """
    r = _rule(code)
    if not r.get("enabled", True):
        return True, None, 0
    if not condition:  # condition fail = rule triggered
        msg = r.get("msg", code)
        try:
            msg = msg.format(**fmt, **r)
        except Exception:
            pass
        return False, {"level": r.get("level", "warn"), "code": code, "msg": msg}, 0
    # Condition pass — không trigger, không add issue. Trả score bonus nếu có.
    return True, None, r.get("score", 0) if r.get("hidden_pass") else 0
TIMEOUT = 10  # Aggressive (B): bỏ retry, accept URL chậm/fail để ưu tiên throughput
WORKERS = 15  # sweet spot — Haravan/Sintech throttle khi >20 concurrent từ 1 IP
DELAY_PER_WORKER = 0.05  # stagger nhỏ để tránh burst → throttle
CRAWL_BATCH_SIZE = 20  # update progress mỗi 20 → status tick mượt, dễ debug stuck
SITEMAP_TIMEOUT = 60  # sitemap.xml chậm thật → giữ timeout cao
CRAWL_RETRY = 0  # Aggressive: KHÔNG retry, fail thì fail (~5-10% URL slow) — tăng tốc 2-3x

# Link check params (tuned 2026-05-12 — 5-8x faster)
LINK_CHECK_WORKERS = 30
LINK_CHECK_TIMEOUT = 8  # HEAD timeout
LINK_CHECK_TIMEOUT_GET = 8  # GET fallback timeout
LINK_CHECK_BATCH_SIZE = 50  # DB write batch
HOST_FAIL_THRESHOLD = 3  # Sau N link cùng host fail → skip remaining cùng host

# In-memory state cho run đang chạy (1 lần / process)
_state_lock = threading.Lock()
_current_run = {
    "run_id": None,
    "status": "idle",  # idle|fetching_sitemap|crawling|done|failed|stopping
    "total": 0,
    "done": 0,
    "success": 0,
    "failed": 0,
    "started_at": None,
    "message": "",
    "should_stop": False,
}


ISSUE_LABELS = {
    "broken":        ("🔴", "Trang lỗi (HTTP fail)", "Fix server hoặc redirect 301 sang URL mới."),
    "fetch_fail":    ("🔴", "Không fetch được", "Kiểm tra mạng / firewall / domain. Có thể site đang block bot."),
    "no_title":      ("🔴", "Thiếu thẻ <title>", "Bắt buộc có. Đặt 30-60 ký tự, chứa từ khoá chính + brand."),
    "title_short":   ("🟡", "Title quá ngắn", "Mở rộng lên 50-60 ký tự, thêm từ khoá phụ + brand 'Sintech'."),
    "title_long":    ("🟡", "Title quá dài", "Rút xuống ≤60 ký tự — Google sẽ cắt phần thừa."),
    "no_meta":       ("🔴", "Thiếu meta description", "Viết 120-160 ký tự, có CTA + từ khoá. Google dùng để hiện snippet."),
    "meta_short":    ("🟡", "Meta description ngắn", "Mở rộng lên 140-160 ký tự để tăng tỉ lệ click."),
    "meta_long":     ("🟡", "Meta description dài", "Rút xuống ≤160 ký tự — phần thừa bị cắt."),
    "no_h1":         ("🔴", "Thiếu thẻ <h1>", "Mỗi trang cần đúng 1 H1, nên trùng/gần với title."),
    "multi_h1":      ("🟡", "Nhiều H1", "Chỉ giữ 1 H1 đầu trang, các tiêu đề con dùng H2/H3."),
    "low_content":   ("🟡", "Nội dung mỏng", "Bổ sung mô tả, thông số, FAQ — nên ≥300 từ để Google đánh giá tốt."),
    "thin_content":  ("🔵", "Nội dung khá ngắn", "Có thể thêm so sánh / hướng dẫn / review khách hàng."),
    "img_no_alt":    ("🟡", "Ảnh thiếu alt", "Thêm thuộc tính alt mô tả ảnh — tốt cho SEO + accessibility."),
    "few_internal":  ("🔵", "Ít internal link", "Link sang sản phẩm liên quan / collection / blog hướng dẫn (≥3)."),
    "no_internal":   ("🟡", "Không có internal link", "Quan trọng: link từ trang này sang ≥3 trang khác trong site."),
    "no_canonical":  ("🟡", "Thiếu canonical", "Thêm <link rel='canonical'> để tránh duplicate content."),
    "no_og":         ("🟡", "Thiếu OG tags", "Thêm og:title, og:description, og:image — để FB/Zalo share đẹp."),
    "no_schema":     ("🔵", "Thiếu schema.org", "Thêm JSON-LD (Product/Article/Breadcrumb) — giúp rich snippet trên Google."),
    "slow":          ("🔵", "Tải hơi chậm", "Tối ưu ảnh, lazy-load, bật cache CDN."),
    "very_slow":     ("🟡", "Tải chậm", "Cấp bách: nén ảnh, giảm script, dùng CDN."),
    # Sintech-specific
    "sintech_in_title":         ("🟡", "Title có 'Sintech'", "Bỏ chữ 'Sintech' khỏi title — rule nội bộ. Sintech chỉ xuất hiện trong meta + bài viết."),
    "seoer_phrases":            ("🟡", "Có cụm SEOer cấm", "Sửa các cụm: 'trong bài này', 'sản phẩm này mang lại', 'người dùng sẽ', 'category này', 'chia sẻ với bạn', 'đem đến'."),
    "separator_dashes":         ("🟡", "Có dấu '---' hoặc '***'", "Bỏ separator. Rule Sintech cấm dùng dấu phân cách kiểu này."),
    "meta_no_cta":              ("🟡", "Meta thiếu CTA viết HOA", "Thêm CTA: 'XEM NGAY tại Sintech', 'CHỌN NGAY', 'THAM KHẢO NGAY', 'KHÁM PHÁ NGAY'."),
    "missing_sintech_section":  ("🟡", "Thiếu 'Vì sao mua tại Sintech'", "Thêm section H2 'Vì sao nên mua tại Sintech' — đúng 2 đoạn × 2 câu."),
    "missing_sintech_policy":   ("🔵", "Thiếu câu chính sách Sintech", "Chèn nguyên văn: 'Sintech hiện công bố chính sách bán hàng, kiểm hàng, vận chuyển và trả góp 0% qua thẻ tín dụng đối với 1 số sản phẩm.'"),
    "missing_faq":              ("🟡", "Thiếu FAQ", "Thêm section H2 'Câu hỏi thường gặp' — 4-6 câu hỏi thực tế."),
    "missing_real_experience":  ("🔵", "Thiếu 'Trải nghiệm thực tế'", "Thêm section trả lời: dùng mượt không / dễ làm quen / dùng lâu thoải mái / cảm giác thực tế."),
    "missing_suitable":         ("🔵", "Thiếu 'Phù hợp với ai'", "Thêm section chia 2 nhóm bullet: 'Phù hợp với' + 'Không quá phù hợp nếu'."),
    # Heading hierarchy + redirect chain
    "no_h2":                    ("🟡", "Không có thẻ <h2>", "Chia nội dung thành các section H2 — Google đánh giá structure tốt hơn."),
    "h2_after_h3":              ("🔵", "Heading nhảy cấp", "Heading H3 xuất hiện trước H2 — sửa lại hierarchy: H1 → H2 → H3."),
    "many_h2":                  ("🔵", "Quá nhiều H2", "Có >15 thẻ H2 — gom lại các section nhỏ vào H3 trong cùng H2 lớn."),
    "redirect_chain":           ("🟡", "Redirect chain dài", "Chain ≥2 hop làm chậm site và mất link juice. Sửa redirect trực tiếp tới URL đích cuối."),
    "redirect_long_chain":      ("🟡", "Redirect chain rất dài", "Chain ≥3 hop — fix gấp. Cập nhật 301 trực tiếp về URL cuối."),
    "h1_in_desc":               ("🔴", "Có thẻ <h1> trong mô tả",
                                  "Mở Haravan → tab Mã HTML phần 'Mô tả sản phẩm' → đổi <h1> thành <h2>. Trang đã có H1 ở title rồi, thêm H1 nữa = duplicate."),
}


# Selector cho phần "Mô tả" admin tự viết trong Haravan (rich-text editor).
# `.rte` là class chuẩn Haravan dùng cho RTE content; bao luôn các biến thể có thêm class.
DESC_SELECTOR = ".rte"
# Selector chuyên cho mô tả SẢN PHẨM (chính xác hơn để check empty-desc cho /products/...).
PRODUCT_DESC_SELECTOR = ".rte.product_getcontent, .product_getcontent"
# Ngưỡng mặc định coi là "thiếu mô tả" (số từ) — chuẩn Sintech mong ≥800 từ.
EMPTY_DESC_THRESHOLD = 800


def enrich_issue(issue: dict) -> dict:
    code = issue.get("code", "")
    icon, label, fix = ISSUE_LABELS.get(code, ("⚪", code, "Tham khảo tài liệu SEO."))
    return {**issue, "icon": icon, "label": label, "fix": fix}


def state_snapshot():
    with _state_lock:
        return dict(_current_run)


def _set_state(**kw):
    with _state_lock:
        _current_run.update(kw)


# ─────────────────────────── SITEMAP ───────────────────────────


def fetch_sitemap_urls(sitemap_index_url: str = SITEMAP_INDEX) -> list:
    """Fetch sitemap index → list of all URLs (loc) in child sitemaps.

    Dùng SITEMAP_TIMEOUT (cao hơn TIMEOUT thường) + retry vì sitemap.xml hay chậm.
    """
    headers = {"User-Agent": USER_AGENT}
    out = []

    def _fetch_with_retry(url: str, retries: int = 2):
        last_err = None
        for attempt in range(retries + 1):
            try:
                return requests.get(url, headers=headers, timeout=SITEMAP_TIMEOUT)
            except requests.exceptions.Timeout as e:
                last_err = e
                if attempt < retries:
                    time.sleep(2 ** attempt)  # backoff: 1s, 2s
                    continue
                raise
            except Exception as e:
                last_err = e
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                raise
        if last_err:
            raise last_err

    r = _fetch_with_retry(sitemap_index_url)
    r.raise_for_status()
    soup = BeautifulSoup(r.content, "xml")
    child_sitemaps = [el.get_text(strip=True) for el in soup.select("sitemap > loc")]
    if not child_sitemaps:
        out.extend(el.get_text(strip=True) for el in soup.select("url > loc"))
        return out
    for sm_url in child_sitemaps:
        try:
            rr = _fetch_with_retry(sm_url)
            rr.raise_for_status()
            ss = BeautifulSoup(rr.content, "xml")
            urls = [el.get_text(strip=True) for el in ss.select("url > loc")]
            out.extend(urls)
        except Exception as e:
            print(f"[sitemap] SKIP {sm_url}: {e.__class__.__name__}")
            continue
    # dedupe + lọc rỗng
    seen = set()
    uniq = []
    for u in out:
        if u and u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def classify_url(url: str) -> str:
    """Phân loại URL theo path."""
    p = urlparse(url).path.lower()
    if "/products/" in p:
        return "product"
    if "/blogs/" in p or "/blog/" in p:
        return "blog"
    if "/collections/" in p:
        return "collection"
    if p in ("/", "") or "/pages/" in p:
        return "page"
    return "other"


# ─────────────────────────── ANALYZER ───────────────────────────


def analyze_html(url: str, html: bytes, status_code: int, load_ms: int,
                 final_url: str = None, x_robots_tag: str = "",
                 redirect_chain: list = None) -> dict:
    """Parse HTML + chấm điểm. Trả dict đủ field cho seo_pages."""
    issues = []
    score = 0
    final_url = final_url or url
    page_size_bytes = len(html) if html else 0
    redirect_chain = redirect_chain or []
    redirect_chain_json = json.dumps(redirect_chain, ensure_ascii=False) if redirect_chain else None

    if status_code >= 400 or status_code == 0:
        issues.append({"level": "error", "code": "broken", "msg": f"HTTP {status_code} — trang lỗi"})
        return {
            "url": url, "final_url": final_url,
            "url_type": classify_url(url),
            "status_code": status_code,
            "title": None, "title_len": 0,
            "meta_desc": None, "meta_desc_len": 0,
            "h1": None, "h1_count": 0,
            "word_count": 0,
            "images_total": 0, "images_no_alt": 0,
            "internal_links": 0, "external_links": 0,
            "has_canonical": 0, "canonical_url": None,
            "has_og": 0, "has_schema": 0,
            "indexable": 0, "indexability_reason": f"HTTP {status_code}",
            "page_size_bytes": page_size_bytes,
            "h2_list": None, "redirect_chain": redirect_chain_json,
            "desc_h1_count": 0, "desc_h1_text": None, "desc_h1_scanned_at": None,
            "load_ms": load_ms,
            "score": 0,
            "_links": [],
            "issues": json.dumps(issues, ensure_ascii=False),
            "last_crawled": datetime.now().isoformat(timespec="seconds"),
        }

    soup = BeautifulSoup(html, "lxml")
    host = urlparse(url).netloc

    # ─── Helper rút gọn: lookup rule config ───
    def _add_issue(code: str, **fmt):
        """Thêm issue NẾU rule enabled. Trả score weight (cho fail case = score field)."""
        r = _rule(code)
        if not r.get("enabled", True):
            return 0
        msg = r.get("msg", code)
        try:
            msg = msg.format(**fmt)
        except Exception:
            pass
        issues.append({"level": r.get("level", "warn"), "code": code, "msg": msg})
        return r.get("score", 0)

    def _pass_score(code: str) -> int:
        """Lookup score weight của rule khi PASS (hidden_pass)."""
        r = _rule(code)
        if not r.get("enabled", True):
            return 0
        return r.get("score", 0) if r.get("hidden_pass") else 0

    def _thr(code: str, default):
        """Lookup threshold từ config (fallback default)."""
        r = _rule(code)
        return r.get("threshold", default)

    def _word_thresholds(ut: str) -> tuple:
        """Trả (low_thr, ok_thr) theo url_type. Đọc từ config key
        `word_count_thresholds`, fallback default kiểu product."""
        cfg = load_rules_config() or {}
        wt = (cfg.get("word_count_thresholds") or {})
        defaults = {
            "blog":       {"low": 700, "ok": 1500},
            "product":    {"low": 500, "ok": 800},
            "collection": {"low": 150, "ok": 300},
            "page":       {"low": 500, "ok": 800},
            "other":      {"low": 500, "ok": 800},
        }
        d = wt.get(ut) or defaults.get(ut) or defaults["product"]
        return int(d.get("low", 500)), int(d.get("ok", 800))

    # Title
    title_tag = soup.find("title")
    title = re.sub(r"\s+", " ", title_tag.get_text()).strip() if title_tag else ""
    title_len = len(title)
    t_long = _thr("title_long", 61)
    t_short = _thr("title_short", 20)
    if not title:
        _add_issue("no_title")
    elif title_len > t_long:
        score += _add_issue("title_long", len=title_len, threshold=t_long)
    elif title_len < t_short:
        score += _add_issue("title_short", len=title_len, threshold=t_short)
    else:
        score += _pass_score("title_ok")

    # Meta description
    md_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc_raw = md_tag.get("content", "") if md_tag else ""
    meta_desc = re.sub(r"\s+", " ", meta_desc_raw).strip()
    meta_desc_len = len(meta_desc)
    m_short = _thr("meta_short", 140)
    m_long = _thr("meta_long", 160)
    if not meta_desc:
        _add_issue("no_meta")
    elif meta_desc_len < m_short:
        score += _add_issue("meta_short", len=meta_desc_len, threshold=m_short)
    elif meta_desc_len > m_long:
        score += _add_issue("meta_long", len=meta_desc_len, threshold=m_long)
    else:
        score += _pass_score("meta_ok")

    # H1
    h1_tags = soup.find_all("h1")
    h1_count = len(h1_tags)
    h1 = re.sub(r"\s+", " ", h1_tags[0].get_text()).strip() if h1_tags else None
    if h1_count == 0:
        _add_issue("no_h1")
    elif h1_count > 1:
        score += _add_issue("multi_h1", count=h1_count)
    else:
        score += _pass_score("h1_ok")

    # H2 list + heading hierarchy
    h2_tags = soup.find_all("h2")
    h2_list = [
        re.sub(r"\s+", " ", h.get_text()).strip()[:200]
        for h in h2_tags
        if re.sub(r"\s+", " ", h.get_text()).strip()
    ]
    h2_list_json = json.dumps(h2_list, ensure_ascii=False) if h2_list else None
    if not h2_list:
        issues.append({"level": "warn", "code": "no_h2", "msg": "Không có thẻ <h2> — nội dung không chia section"})
    elif len(h2_list) > 15:
        issues.append({"level": "info", "code": "many_h2", "msg": f"Có {len(h2_list)} thẻ H2 — quá nhiều"})
    # Check H3 xuất hiện trước H2 đầu tiên
    headings_in_order = soup.find_all(["h1", "h2", "h3"])
    saw_h2 = False
    h3_before_h2 = False
    for hd in headings_in_order:
        nm = hd.name
        if nm == "h2":
            saw_h2 = True
        elif nm == "h3" and not saw_h2 and h2_list:
            h3_before_h2 = True
            break
    if h3_before_h2:
        issues.append({"level": "info", "code": "h2_after_h3", "msg": "Heading H3 xuất hiện trước H2 đầu tiên"})

    # Word count — threshold theo url_type (blog/product/collection/page)
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    text = soup.get_text(" ", strip=True)
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    word_count = len(words)
    _ut_for_wc = classify_url(url)
    _low_thr, _ok_thr = _word_thresholds(_ut_for_wc)
    if word_count < _low_thr:
        issues.append({"level": "warn", "code": "low_content",
                       "msg": f"Nội dung mỏng ({word_count} từ, chuẩn {_ut_for_wc} ≥ {_ok_thr})"})
    elif word_count < _ok_thr:
        issues.append({"level": "info", "code": "thin_content",
                       "msg": f"Nội dung khá ngắn ({word_count} từ, chuẩn {_ut_for_wc} ≥ {_ok_thr})"})
        score += 5
    else:
        score += 10

    # Images alt
    imgs = soup.find_all("img")
    images_total = len(imgs)
    images_no_alt = sum(1 for i in imgs if not (i.get("alt") or "").strip())
    if images_total == 0:
        score += 5  # không có ảnh thì không trừ
    elif images_no_alt == 0:
        score += 10
    elif images_no_alt < images_total / 2:
        issues.append({"level": "warn", "code": "img_no_alt", "msg": f"{images_no_alt}/{images_total} ảnh thiếu alt"})
        score += 5
    else:
        issues.append({"level": "error", "code": "img_no_alt", "msg": f"{images_no_alt}/{images_total} ảnh thiếu alt"})

    # Links — gom + dedupe để check broken sau
    internal = 0
    external = 0
    link_set = {}  # absolute_url -> is_internal
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        try:
            absolute = urljoin(url, href).split("#")[0]
            target_host = urlparse(absolute).netloc
        except Exception:
            continue
        if not target_host:
            continue
        is_internal = (target_host == host)
        if is_internal:
            internal += 1
        else:
            external += 1
        if absolute not in link_set:
            link_set[absolute] = is_internal
    links_collected = [(t, internal_flag) for t, internal_flag in link_set.items()]
    if internal >= 3:
        score += 10
    elif internal >= 1:
        issues.append({"level": "info", "code": "few_internal", "msg": f"Chỉ có {internal} internal link, nên ≥ 3"})
        score += 5
    else:
        issues.append({"level": "warn", "code": "no_internal", "msg": "Không có internal link nào"})

    # Canonical
    canon = soup.find("link", attrs={"rel": "canonical"})
    canonical_url = (canon.get("href") or "").strip() if canon else None
    has_canonical = 1 if canonical_url else 0
    if has_canonical:
        score += 5
        # Canonical trỏ URL khác → có thể duplicate
        try:
            if canonical_url and urljoin(url, canonical_url).rstrip("/") != url.rstrip("/"):
                issues.append({"level": "info", "code": "canonical_other", "msg": f"Canonical trỏ URL khác: {canonical_url}"})
        except Exception:
            pass
    else:
        issues.append({"level": "warn", "code": "no_canonical", "msg": "Thiếu thẻ canonical"})

    # Indexability
    meta_robots_tag = soup.find("meta", attrs={"name": "robots"})
    meta_robots = (meta_robots_tag.get("content", "") if meta_robots_tag else "").lower()
    x_robots_lower = (x_robots_tag or "").lower()
    indexable = 1
    indexability_reason = "indexable"
    if "noindex" in meta_robots:
        indexable = 0
        indexability_reason = "meta robots noindex"
        issues.append({"level": "error", "code": "noindex_meta", "msg": "Meta robots noindex — Google sẽ KHÔNG index"})
    elif "noindex" in x_robots_lower:
        indexable = 0
        indexability_reason = "X-Robots-Tag noindex"
        issues.append({"level": "error", "code": "noindex_header", "msg": "X-Robots-Tag noindex — Google sẽ KHÔNG index"})
    elif final_url and final_url.rstrip("/") != url.rstrip("/"):
        indexability_reason = f"redirect → {final_url}"

    # OG tags
    og = soup.find("meta", attrs={"property": "og:title"})
    has_og = 1 if og and og.get("content") else 0
    if has_og:
        score += 5
    else:
        issues.append({"level": "warn", "code": "no_og", "msg": "Thiếu Open Graph tags (og:title)"})

    # Schema.org JSON-LD
    schema_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    has_schema = 1 if schema_scripts else 0
    if has_schema:
        score += 5
    else:
        issues.append({"level": "info", "code": "no_schema", "msg": "Thiếu schema.org JSON-LD"})

    # Load time bonus
    if load_ms <= 1500:
        score += 10
    elif load_ms <= 3000:
        issues.append({"level": "info", "code": "slow", "msg": f"Tải hơi chậm ({load_ms}ms, mong < 1500ms)"})
        score += 5
    else:
        issues.append({"level": "warn", "code": "very_slow", "msg": f"Tải chậm ({load_ms}ms)"})

    # Redirect chain
    if len(redirect_chain) >= 3:
        issues.append({"level": "warn", "code": "redirect_long_chain",
                       "msg": f"Redirect chain dài {len(redirect_chain)} hop"})
    elif len(redirect_chain) >= 2:
        issues.append({"level": "warn", "code": "redirect_chain",
                       "msg": f"Redirect chain {len(redirect_chain)} hop"})

    # ─── SINTECH-SPECIFIC RULES (chỉ apply cho /products/) ───
    url_type = classify_url(url)
    body_text = text  # đã extract ở trên
    body_lower = body_text.lower()

    # 1. Sintech trong title — CHỈ flag nếu Sintech KHÔNG nằm cuối " - Sintech"
    # (vì Haravan auto-suffix " - Sintech" cho mọi title public → false positive).
    if title:
        title_lower = title.lower()
        # Strip suffix Haravan tự thêm
        cleaned = re.sub(r"\s*[-–—|]\s*sintech.*$", "", title_lower).strip()
        if "sintech" in cleaned:
            issues.append({"level": "warn", "code": "sintech_in_title",
                           "msg": "Title gốc chứa 'Sintech' (không tính suffix Haravan) — rule cấm"})

    # 2. Cụm SEOer cấm
    seoer_phrases = [
        "trong bài này",
        "sản phẩm này mang lại",
        "người dùng sẽ",
        "category này",
        "chia sẻ với bạn",
        "đem đến",
    ]
    found_phrases = [p for p in seoer_phrases if p in body_lower]
    if found_phrases:
        issues.append({
            "level": "warn",
            "code": "seoer_phrases",
            "msg": f"Có cụm SEOer cấm: {', '.join(found_phrases[:3])}",
        })

    # 3. Dấu separator --- hoặc *** (cấm)
    raw_html_text = soup.get_text("\n", strip=True)
    if re.search(r"^---+$", raw_html_text, flags=re.MULTILINE) or re.search(r"^\*\*\*+$", raw_html_text, flags=re.MULTILINE):
        issues.append({"level": "warn", "code": "separator_dashes", "msg": "Có dấu '---' hoặc '***' — rule Sintech cấm"})

    # 4. Meta thiếu CTA viết HOA (apply cho product) — PASS cộng điểm
    if url_type == "product" and meta_desc:
        cta_keywords = ["XEM NGAY", "CHỌN NGAY", "THAM KHẢO NGAY", "KHÁM PHÁ NGAY", "MUA NGAY"]
        if any(kw in meta_desc for kw in cta_keywords):
            score += _pass_score("meta_cta_ok")
        else:
            issues.append({"level": "warn", "code": "meta_no_cta", "msg": "Meta description thiếu CTA viết HOA"})

    # 5. Trang sản phẩm thiếu section "Vì sao mua tại Sintech" — PASS cộng điểm
    if url_type == "product":
        if "vì sao" in body_lower and "sintech" in body_lower:
            score += _pass_score("sintech_section_ok")
            if "trả góp 0%" not in body_lower and "thẻ tín dụng" not in body_lower:
                issues.append({"level": "info", "code": "missing_sintech_policy",
                               "msg": "Thiếu câu chính sách Sintech (trả góp 0%, kiểm hàng...)"})
        else:
            issues.append({"level": "warn", "code": "missing_sintech_section",
                           "msg": "Thiếu section 'Vì sao nên mua tại Sintech'"})

    # 6. Trang sản phẩm thiếu FAQ — PASS cộng điểm
    if url_type == "product":
        faq_signals = ["câu hỏi thường gặp", "faq", "hỏi đáp", "thường gặp"]
        if any(sig in body_lower for sig in faq_signals):
            score += _pass_score("faq_ok")
        else:
            issues.append({"level": "warn", "code": "missing_faq",
                           "msg": "Trang sản phẩm thiếu section FAQ"})

    # 6b. Signature Sintech cuối bài — PASS cộng điểm
    if url_type == "product":
        sig_signals = [
            "tư vấn cấu hình bởi team kỹ thuật sintech",
            "tư vấn bởi team kỹ thuật sintech",
            "team kỹ thuật sintech",
        ]
        if any(sig in body_lower for sig in sig_signals):
            score += _pass_score("signature_ok")
        else:
            issues.append({"level": "info", "code": "missing_signature",
                           "msg": "Thiếu signature 'Tư vấn cấu hình bởi team kỹ thuật Sintech' cuối bài"})

    # 7. Trang sản phẩm thiếu "Trải nghiệm thực tế" — PASS cộng điểm
    if url_type == "product":
        if "trải nghiệm thực tế" in body_lower or "trải nghiệm" in body_lower:
            score += _pass_score("real_experience_ok")
        else:
            issues.append({"level": "info", "code": "missing_real_experience",
                           "msg": "Thiếu section 'Trải nghiệm thực tế'"})

    # 8. Trang sản phẩm thiếu "Phù hợp với ai"
    if url_type == "product":
        if "phù hợp với" not in body_lower and "phù hợp cho" not in body_lower:
            issues.append({"level": "info", "code": "missing_suitable",
                           "msg": "Thiếu section 'Phù hợp với ai'"})

    # ─── READABILITY (apply mọi url_type có ≥50 từ) ───
    if _readability_score is not None and word_count >= 50:
        try:
            rd = _readability_score(text) or {}
            raw_rd = rd.get("score") or 0
            level_rd = rd.get("level", "")
            if raw_rd >= 70:
                score += _pass_score("readability_ok") or 10
                issues.append({"level": "info", "code": "readability",
                               "msg": f"Readability {raw_rd} ({level_rd})"})
            elif raw_rd >= 55:
                score += 7
                issues.append({"level": "info", "code": "readability",
                               "msg": f"Readability {raw_rd} ({level_rd})"})
            elif raw_rd >= 40:
                score += 4
                issues.append({"level": "info", "code": "readability",
                               "msg": f"Readability {raw_rd} ({level_rd})"})
            else:
                # readability_weak — không cộng điểm
                issues.append({"level": "warn", "code": "readability",
                               "msg": f"Readability {raw_rd} ({level_rd}) — khó đọc"})
        except Exception:
            pass

    # ─── H1 trong phần MÔ TẢ (admin tự viết qua Haravan RTE) ───
    desc_h1_count, desc_h1_texts = _count_h1_in_desc(soup)
    if desc_h1_count > 0:
        preview = " | ".join(desc_h1_texts[:3])
        issues.append({
            "level": "error", "code": "h1_in_desc",
            "msg": f"{desc_h1_count} thẻ <h1> trong mô tả: {preview[:160]}",
        })
    desc_h1_text_json = json.dumps(desc_h1_texts, ensure_ascii=False) if desc_h1_texts else None

    score = min(100, max(0, score))

    return {
        "url": url,
        "final_url": final_url,
        "url_type": classify_url(url),
        "status_code": status_code,
        "title": title or None,
        "title_len": title_len,
        "meta_desc": meta_desc or None,
        "meta_desc_len": meta_desc_len,
        "h1": h1,
        "h1_count": h1_count,
        "word_count": word_count,
        "images_total": images_total,
        "images_no_alt": images_no_alt,
        "internal_links": internal,
        "external_links": external,
        "has_canonical": has_canonical,
        "canonical_url": canonical_url,
        "has_og": has_og,
        "has_schema": has_schema,
        "indexable": indexable,
        "indexability_reason": indexability_reason,
        "page_size_bytes": page_size_bytes,
        "h2_list": h2_list_json,
        "redirect_chain": redirect_chain_json,
        "desc_h1_count": desc_h1_count,
        "desc_h1_text": desc_h1_text_json,
        "desc_h1_scanned_at": datetime.now().isoformat(timespec="seconds"),
        "load_ms": load_ms,
        "score": score,
        "_links": links_collected,
        "issues": json.dumps(issues, ensure_ascii=False),
        "last_crawled": datetime.now().isoformat(timespec="seconds"),
    }


def _count_h1_in_desc(soup) -> tuple:
    """Tìm tất cả container `.rte` (Haravan RTE) → đếm H1 bên trong + lấy text.

    Trả: (count, [text1, text2, ...]).
    """
    rte_blocks = soup.select(DESC_SELECTOR)
    count = 0
    texts = []
    for block in rte_blocks:
        for h1 in block.find_all("h1"):
            count += 1
            t = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)).strip()
            if t:
                texts.append(t[:200])
    return count, texts


# ─────────────────────────── CRAWLER ───────────────────────────


def crawl_one(url: str) -> dict:
    """Fetch 1 URL + analyze. Trả dict result. Retry CRAWL_RETRY lần nếu timeout."""
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    t0 = time.time()
    last_err = None
    for attempt in range(CRAWL_RETRY + 1):
        try:
            r = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
            load_ms = int((time.time() - t0) * 1000)
            chain = []
            for hop in r.history:
                chain.append({
                    "url": hop.url,
                    "status_code": hop.status_code,
                    "to": hop.headers.get("Location", ""),
                })
            return analyze_html(
                url, r.content, r.status_code, load_ms,
                final_url=r.url,
                x_robots_tag=r.headers.get("X-Robots-Tag", ""),
                redirect_chain=chain,
            )
        except requests.exceptions.Timeout as e:
            last_err = e
            if attempt < CRAWL_RETRY:
                time.sleep(1)
                continue
            return _crawl_one_fail(url, e, time.time() - t0)
        except Exception as e:
            return _crawl_one_fail(url, e, time.time() - t0)


def _crawl_one_fail(url: str, e: Exception, elapsed: float) -> dict:
    """Build result dict cho URL fail."""
    load_ms = int(elapsed * 1000)
    return {
        "url": url, "final_url": url,
        "url_type": classify_url(url),
        "status_code": 0,
        "title": None, "title_len": 0,
        "meta_desc": None, "meta_desc_len": 0,
        "h1": None, "h1_count": 0,
        "word_count": 0,
        "images_total": 0, "images_no_alt": 0,
        "internal_links": 0, "external_links": 0,
        "has_canonical": 0, "canonical_url": None,
        "has_og": 0, "has_schema": 0,
        "indexable": 0, "indexability_reason": f"fetch_fail: {e.__class__.__name__}",
        "page_size_bytes": 0,
        "h2_list": None, "redirect_chain": None,
        "desc_h1_count": 0, "desc_h1_text": None, "desc_h1_scanned_at": None,
        "_links": [],
        "load_ms": load_ms,
        "score": 0,
        "issues": json.dumps([{"level": "error", "code": "fetch_fail", "msg": f"Lỗi fetch: {e.__class__.__name__}: {str(e)[:200]}"}], ensure_ascii=False),
        "last_crawled": datetime.now().isoformat(timespec="seconds"),
    }


def run_crawl(limit: int = None, auto_check_links: bool = True):
    """Worker chính: fetch sitemap → crawl tất cả URL → ghi DB.
    Sau khi crawl xong, tự động chạy link checker (auto_check_links=True).

    `limit`: nếu set, chỉ crawl N URL đầu tiên (để test).
    `auto_check_links`: tự động trigger link check sau crawl (default True).
    """
    run_id = db.seo_create_run(notes="manual" if limit else "weekly")
    _set_state(
        run_id=run_id, status="fetching_sitemap",
        total=0, done=0, success=0, failed=0,
        started_at=datetime.now().isoformat(timespec="seconds"),
        message="Đang fetch sitemap...",
    )
    try:
        urls = fetch_sitemap_urls()
        if limit:
            urls = urls[:limit]
        total = len(urls)
        _set_state(status="crawling", total=total, message=f"Crawling {total} URL (Phase 1, sequential)...", should_stop=False)

        # SEQUENTIAL mode: Phase 2 sẽ trigger SAU khi Phase 1 done (không parallel)
        # Lý do: Phase 2 query DB liên tục — share IO/CPU với Phase 1 → chậm cả 2

        success = 0
        failed = 0
        done = 0
        stopped = False
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(_crawl_with_delay, u): u for u in urls}
            for fut in as_completed(futures):
                # Check stop signal mỗi vòng lặp
                if _current_run.get("should_stop"):
                    _set_state(status="stopping", message="Đang stop — cancel các URL còn lại...")
                    for f in list(futures.keys()):
                        if not f.done():
                            f.cancel()
                    stopped = True
                    break
                try:
                    result = fut.result()
                    result["last_run_id"] = run_id
                    links = result.pop("_links", [])
                    db.seo_upsert_page(result)
                    if links:
                        db.seo_replace_links(result["url"], links)
                    if (result.get("status_code") or 0) < 400 and result.get("status_code"):
                        success += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
                done += 1
                if done % CRAWL_BATCH_SIZE == 0 or done == total:
                    db.seo_update_run_progress(run_id, total, success, failed)
                    _set_state(done=done, success=success, failed=failed)

        if stopped:
            db.seo_finish_run(run_id, "stopped", done, success, failed)
            _set_state(status="done", done=done, success=success, failed=failed,
                       message=f"Đã stop: {success} OK, {failed} lỗi (còn {total - done} URL chưa crawl).",
                       should_stop=False)
            return  # bỏ qua link check + notify
        db.seo_finish_run(run_id, "done", total, success, failed)
        _set_state(status="done", done=done, success=success, failed=failed,
                   message=f"Xong crawl: {success} OK, {failed} lỗi.")
        # Capture history sau mỗi run thành công
        try:
            db.seo_capture_history(note=f"after_crawl_run_{run_id}")
            db.activity_log(
                kind="seo_crawl_done", icon="🔍",
                title=f"Crawl SEO xong: {success}/{total} URL",
                description=f"Lỗi: {failed}",
                href="/seo",
            )
        except Exception:
            pass
        # SEQUENTIAL: Phase 1 xong → notify, sau đó spawn Phase 2
        try:
            import notifier
            notifier.notify_crawl_done(state_snapshot())
        except Exception:
            pass
        if auto_check_links:
            try:
                started = start_link_check_streaming_async()
                if started:
                    print("[crawl] Phase 2 link check started AFTER Phase 1 done (sequential)")
                    _set_state(message=f"Phase 1 xong ({success} OK). Phase 2 broken-link check vừa start...")
            except Exception as e:
                print(f"[crawl] Phase 2 link check fail to start: {e}")
    except Exception as e:
        db.seo_finish_run(run_id, "failed", 0, 0, 0)
        _set_state(status="failed", message=f"Lỗi: {e.__class__.__name__}: {str(e)[:200]}")
        try:
            import notifier
            notifier.send_telegram(f"❌ Crawl SEO lỗi: {e.__class__.__name__}: {str(e)[:200]}")
        except Exception:
            pass


_link_state = {"running": False, "checked": 0, "total": 0, "broken": 0}
_link_state_lock = threading.Lock()


def link_check_state():
    with _link_state_lock:
        return dict(_link_state)


def _check_link(target: str) -> tuple:
    """HEAD-only by default, fallback GET CHỈ khi 405/403 (method/auth issue, không phải broken).

    Trả (target, status_code, error_kind).
    error_kind = None nếu OK, hoặc 1 trong các key của LINK_ERROR_LABELS nếu fail.
    """
    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.head(target, headers=headers, timeout=LINK_CHECK_TIMEOUT, allow_redirects=True)
        # CHỈ retry GET cho method-not-allowed (405) hoặc auth-blocked HEAD (403)
        # KHÔNG retry cho 500+ (server fail thật sự, đỡ tốn 2x time)
        if r.status_code in (405, 403):
            r = requests.get(target, headers=headers, timeout=LINK_CHECK_TIMEOUT_GET,
                             allow_redirects=True, stream=True)
        return target, r.status_code, None
    except Exception as exc:
        return target, 0, _classify_link_error(exc)


def _host_of(url: str) -> str:
    """Extract hostname for circuit breaker. Return '' nếu parse fail."""
    try:
        from urllib.parse import urlparse
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def run_link_check_streaming(stop_when_crawl_done: bool = True, poll_interval: int = 8):
    """Phase 2 streaming mode — chạy SONG SONG với Phase 1 crawl.

    Logic:
      1. Loop: SELECT links chưa check (status_code IS NULL) → check N links → update
      2. Phase 1 còn chạy → poll mỗi poll_interval giây tìm new links
      3. Phase 1 done + no more unchecked → finish

    Total pipeline time ≈ max(Phase1, Phase2) thay vì Phase1 + Phase2.
    """
    import time as _t
    with _link_state_lock:
        if _link_state["running"]:
            return
        _link_state.update({"running": True, "checked": 0, "total": 0, "broken": 0})

    host_fail_count = {}
    pending_batch = []
    batch_lock = threading.Lock()

    def _flush_batch(force=False):
        with batch_lock:
            if pending_batch and (force or len(pending_batch) >= LINK_CHECK_BATCH_SIZE):
                db.seo_link_status_update_batch(list(pending_batch))
                pending_batch.clear()

    try:
        while True:
            # Lấy batch links chưa check
            targets = db.seo_links_to_check(limit=200)
            if not targets:
                # Hết unchecked links
                if not stop_when_crawl_done or _current_run.get("status") in ("done", "stopped", "idle"):
                    break
                # Phase 1 còn chạy → đợi thêm
                _t.sleep(poll_interval)
                continue

            seen = set()
            deduped = []
            for t in targets:
                if t["target"] not in seen:
                    seen.add(t["target"])
                    deduped.append(t)

            with _link_state_lock:
                _link_state["total"] += len(deduped)

            with ThreadPoolExecutor(max_workers=LINK_CHECK_WORKERS) as ex:
                futures = {}
                for t in deduped:
                    target = t["target"]
                    host = _host_of(target)
                    if host and host_fail_count.get(host, 0) >= HOST_FAIL_THRESHOLD:
                        pending_batch.append((0, "circuit_breaker_skip", target))
                        with _link_state_lock:
                            _link_state["checked"] += 1
                            _link_state["broken"] += 1
                        _flush_batch()
                        continue
                    futures[ex.submit(_check_link, target)] = target

                for fut in as_completed(futures):
                    try:
                        target, status_code, error_kind = fut.result()
                        host = _host_of(target)
                        pending_batch.append((status_code, error_kind, target))
                        with _link_state_lock:
                            _link_state["checked"] += 1
                            if status_code >= 400 or status_code == 0:
                                _link_state["broken"] += 1
                                if host:
                                    host_fail_count[host] = host_fail_count.get(host, 0) + 1
                        _flush_batch()
                    except Exception:
                        with _link_state_lock:
                            _link_state["checked"] += 1
            _flush_batch(force=True)

        # Phase 2 finished — notify
        try:
            import notifier
            crawl_state = state_snapshot()
            link_state = link_check_state()
            broken_summary = db.seo_broken_link_summary()
            stats = db.seo_stats()
            if crawl_state.get("status") == "done" and crawl_state.get("done", 0) > 0:
                notifier.notify_pipeline_complete(crawl_state, link_state, broken_summary, stats)
            else:
                notifier.notify_link_check_done(link_state, broken_summary)
        except Exception:
            pass
    finally:
        with _link_state_lock:
            _link_state["running"] = False


def start_link_check_streaming_async() -> bool:
    """Spawn Phase 2 streaming. Chạy SONG SONG với Phase 1."""
    with _link_state_lock:
        if _link_state["running"]:
            return False
    t = threading.Thread(target=run_link_check_streaming, daemon=True)
    t.start()
    return True


def run_link_check(limit: int = None, only_targets: list = None):
    """Check unique link đã thu thập. Update seo_links.status_code in batch.

    Optimizations 2026-05-12:
      - WORKERS 30 (gấp ~4x cũ)
      - TIMEOUT 8s (giảm từ 15s)
      - HEAD-only, chỉ GET fallback cho 405/403
      - Dedup target URLs (1 target không check 2 lần trong cùng run)
      - Batch DB write mỗi 50 results
      - Host-level circuit breaker: 1 host fail >3 lần → skip remaining cùng host
    """
    targets = db.seo_links_to_check(limit=limit or 0, only_targets=only_targets)
    # Dedup: 1 target chỉ check 1 lần
    seen = set()
    deduped = []
    for t in targets:
        if t["target"] not in seen:
            seen.add(t["target"])
            deduped.append(t)
    targets = deduped

    total = len(targets)
    with _link_state_lock:
        _link_state.update({"running": True, "checked": 0, "total": total, "broken": 0})

    # Host circuit breaker counters
    host_fail_count = {}
    pending_batch = []  # (status, error_kind, target_url)
    batch_lock = threading.Lock()

    def _flush_batch(force=False):
        with batch_lock:
            if pending_batch and (force or len(pending_batch) >= LINK_CHECK_BATCH_SIZE):
                db.seo_link_status_update_batch(list(pending_batch))
                pending_batch.clear()

    try:
        with ThreadPoolExecutor(max_workers=LINK_CHECK_WORKERS) as ex:
            futures = {}
            for t in targets:
                target = t["target"]
                host = _host_of(target)
                # Circuit breaker: nếu host đã fail >threshold → skip + mark như 0
                if host and host_fail_count.get(host, 0) >= HOST_FAIL_THRESHOLD:
                    pending_batch.append((0, "circuit_breaker_skip", target))
                    with _link_state_lock:
                        _link_state["checked"] += 1
                        _link_state["broken"] += 1
                    _flush_batch()
                    continue
                futures[ex.submit(_check_link, target)] = target

            for fut in as_completed(futures):
                try:
                    target, status_code, error_kind = fut.result()
                    host = _host_of(target)
                    pending_batch.append((status_code, error_kind, target))
                    with _link_state_lock:
                        _link_state["checked"] += 1
                        if status_code >= 400 or status_code == 0:
                            _link_state["broken"] += 1
                            if host:
                                host_fail_count[host] = host_fail_count.get(host, 0) + 1
                    _flush_batch()
                except Exception:
                    with _link_state_lock:
                        _link_state["checked"] += 1
            _flush_batch(force=True)
        # Notify khi link check xong (Pipeline complete = crawl + link check)
        try:
            import notifier
            crawl_state = state_snapshot()
            link_state = link_check_state()
            broken_summary = db.seo_broken_link_summary()
            stats = db.seo_stats()
            if crawl_state.get("status") == "done" and crawl_state.get("done", 0) > 0:
                # Pipeline complete (crawl + link check trong 1 lần)
                notifier.notify_pipeline_complete(crawl_state, link_state, broken_summary, stats)
            else:
                # Stand-alone link check
                notifier.notify_link_check_done(link_state, broken_summary)
        except Exception:
            pass
    finally:
        with _link_state_lock:
            _link_state["running"] = False


def start_link_check_async(limit: int = None, only_targets: list = None) -> bool:
    with _link_state_lock:
        if _link_state["running"]:
            return False
    t = threading.Thread(target=run_link_check, args=(limit, only_targets), daemon=True)
    t.start()
    return True


def _crawl_with_delay(url: str) -> dict:
    time.sleep(DELAY_PER_WORKER)
    return crawl_one(url)


def start_crawl_async(limit: int = None, auto_check_links: bool = True) -> bool:
    """Spawn thread crawl. Trả False nếu đang có run khác.
    Sau khi crawl xong, mặc định tự động chạy link check ngầm."""
    snap = state_snapshot()
    if snap["status"] in ("fetching_sitemap", "crawling"):
        return False
    t = threading.Thread(target=run_crawl, args=(limit, auto_check_links), daemon=True)
    t.start()
    return True


def stop_crawl() -> bool:
    """Signal crawl loop dừng sau khi xong các future hiện tại.
    Trả True nếu đang chạy, False nếu idle."""
    with _state_lock:
        if _current_run["status"] in ("fetching_sitemap", "crawling"):
            _current_run["should_stop"] = True
            _current_run["message"] = "Đã nhận lệnh stop — đang dừng..."
            return True
    return False


# ─────────────────────────── DESC-H1 QUICK SCANNER ───────────────────────────
# Quét nhanh chỉ check H1 trong phần `.rte` (mô tả admin tự viết).
# Không chấm điểm, không đụng tới các field khác — ghi thẳng vào seo_pages.

_desc_h1_state = {
    "running": False, "total": 0, "checked": 0, "violations": 0, "failed": 0,
    "started_at": None, "message": "", "url_types": None,
}
_desc_h1_lock = threading.Lock()


def desc_h1_state():
    with _desc_h1_lock:
        return dict(_desc_h1_state)


def _scan_one_desc_h1(url: str) -> dict:
    """Fetch 1 URL → tìm H1 trong `.rte`. Trả dict {url, url_type, count, texts, ok}."""
    headers = {"User-Agent": USER_AGENT}
    url_type = classify_url(url)
    try:
        r = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code >= 400:
            return {"url": url, "url_type": url_type, "count": 0, "texts": [], "ok": False}
        soup = BeautifulSoup(r.content, "lxml")
        count, texts = _count_h1_in_desc(soup)
        return {"url": url, "url_type": url_type, "count": count, "texts": texts, "ok": True}
    except Exception:
        return {"url": url, "url_type": url_type, "count": 0, "texts": [], "ok": False}


def run_desc_h1_scan(url_types: list = None, limit: int = None):
    """Quét sitemap → check H1 trong .rte. url_types lọc loại trang muốn quét."""
    with _desc_h1_lock:
        if _desc_h1_state["running"]:
            return
        _desc_h1_state.update({
            "running": True, "total": 0, "checked": 0, "violations": 0, "failed": 0,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "message": "Đang fetch sitemap...",
            "url_types": list(url_types) if url_types else None,
        })
    try:
        urls = fetch_sitemap_urls()
        if url_types:
            allowed = set(url_types)
            urls = [u for u in urls if classify_url(u) in allowed]
        if limit:
            urls = urls[:limit]
        total = len(urls)
        with _desc_h1_lock:
            _desc_h1_state.update({"total": total, "message": f"Quét {total} URL..."})

        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(_scan_one_desc_h1, u): u for u in urls}
            for fut in as_completed(futures):
                try:
                    res = fut.result()
                    scanned_at = datetime.now().isoformat(timespec="seconds")
                    text_json = json.dumps(res["texts"], ensure_ascii=False) if res["texts"] else None
                    db.seo_upsert_desc_h1(
                        res["url"], res["url_type"], res["count"], text_json, scanned_at,
                    )
                    with _desc_h1_lock:
                        _desc_h1_state["checked"] += 1
                        if not res["ok"]:
                            _desc_h1_state["failed"] += 1
                        if res["count"] > 0:
                            _desc_h1_state["violations"] += 1
                except Exception:
                    with _desc_h1_lock:
                        _desc_h1_state["checked"] += 1
                        _desc_h1_state["failed"] += 1

        with _desc_h1_lock:
            _desc_h1_state["message"] = (
                f"Xong: {_desc_h1_state['violations']} URL có H1 trong mô tả "
                f"({_desc_h1_state['checked']}/{total} đã quét, {_desc_h1_state['failed']} lỗi fetch)."
            )
        try:
            db.activity_log(
                kind="seo_desc_h1_scan", icon="🔎",
                title=f"Quét H1-trong-mô-tả xong: {_desc_h1_state['violations']}/{total}",
                description=f"Lỗi fetch: {_desc_h1_state['failed']}",
                href="/seo/h1-in-desc",
            )
        except Exception:
            pass
    finally:
        with _desc_h1_lock:
            _desc_h1_state["running"] = False


def start_desc_h1_scan_async(url_types: list = None, limit: int = None) -> bool:
    with _desc_h1_lock:
        if _desc_h1_state["running"]:
            return False
    t = threading.Thread(target=run_desc_h1_scan, args=(url_types, limit), daemon=True)
    t.start()
    return True


# ─────────────────────────── H1-IN-DESC AUTO-FIX ───────────────────────────
# Đổi <h1> → <h2> trong body_html của product/blog article qua Haravan API.
# CHỈ động vào body_html (mô tả admin tự viết), KHÔNG đụng đến H1 chính của trang.

_H1_OPEN_RE = re.compile(r"<h1(\s[^>]*)?>", re.IGNORECASE)
_H1_CLOSE_RE = re.compile(r"</h1\s*>", re.IGNORECASE)
_H1_FIX_BACKUP_DIR = Path(__file__).parent.parent / "data" / "h1_fix_backup"


def _replace_h1_with_h2(body_html: str) -> tuple:
    """Replace <h1...> → <h2...> và </h1> → </h2>. Giữ attribute class/style.
    Return (new_body, n_open_replaced).
    """
    n_open = 0
    def _open_repl(m):
        nonlocal n_open
        n_open += 1
        attrs = m.group(1) or ""
        return f"<h2{attrs}>"
    new_body = _H1_OPEN_RE.sub(_open_repl, body_html)
    new_body = _H1_CLOSE_RE.sub("</h2>", new_body)
    return new_body, n_open


def _find_product_by_url(url: str):
    path = urlparse(url).path
    m = re.search(r"/products/([^/]+)", path)
    if not m:
        return None
    handle = m.group(1)
    row = db.hv_get_product_by_handle(handle)
    return row["haravan_id"] if row else None


def _find_article_by_url(url: str) -> tuple:
    """URL: /blogs/<blog-handle>/<article-handle> → (blog_id, article_id) via live API."""
    path = urlparse(url).path
    m = re.search(r"/blogs/([^/]+)/([^/]+)", path)
    if not m:
        return (None, None)
    blog_handle = m.group(1)
    article_handle = m.group(2)
    try:
        blogs = haravan_client.list_blogs()
    except Exception:
        return (None, None)
    for blog in blogs:
        if blog.get("handle") != blog_handle:
            continue
        blog_id = blog["id"]
        for page in range(1, 21):
            articles = haravan_client.list_articles(blog_id, page=page, limit=50)
            if not articles:
                break
            for a in articles:
                if a.get("handle") == article_handle:
                    return (blog_id, a["id"])
    return (None, None)


def fix_h1_in_desc_for_url(url: str) -> dict:
    """Auto-fix <h1> → <h2> trong body_html của 1 URL trên Haravan.
    Support: product, blog. Page/collection: trả error."""
    url_type = classify_url(url)
    if url_type not in ("product", "blog"):
        return {
            "ok": False,
            "error": f"Loại '{url_type}' chưa hỗ trợ auto-fix. Vào Haravan admin sửa tay.",
        }

    if url_type == "product":
        haravan_id = _find_product_by_url(url)
        if not haravan_id:
            return {"ok": False, "error": "Không tìm thấy SP trong DB local. Vào trang Haravan sync trước."}
        try:
            item = haravan_client.get_product(haravan_id)
        except Exception as e:
            return {"ok": False, "error": f"Fetch product lỗi: {e}"}
        resource_label = f"product#{haravan_id}"
    else:
        blog_id, article_id = _find_article_by_url(url)
        if not blog_id or not article_id:
            return {"ok": False, "error": "Không tìm thấy article trên Haravan API."}
        try:
            item = haravan_client.get_article(blog_id, article_id)
        except Exception as e:
            return {"ok": False, "error": f"Fetch article lỗi: {e}"}
        resource_label = f"blog{blog_id}_article{article_id}"

    body_html = item.get("body_html") or ""
    if not body_html:
        return {"ok": False, "error": "body_html rỗng — không có gì để fix."}

    new_body, n_replaced = _replace_h1_with_h2(body_html)
    if n_replaced == 0:
        return {
            "ok": False,
            "error": "Không tìm thấy <h1> nào trong body_html admin (có thể H1 nằm ở layout theme).",
        }

    _H1_FIX_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = _H1_FIX_BACKUP_DIR / f"{resource_label}_{ts}.html"
    try:
        backup_file.write_text(body_html, encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"Backup body cũ thất bại: {e}"}

    try:
        if url_type == "product":
            haravan_client.update_product(haravan_id, {"body_html": new_body})
        else:
            haravan_client.update_article(blog_id, article_id, {"body_html": new_body})
    except Exception as e:
        return {"ok": False, "error": f"PUT Haravan lỗi: {e}", "backup": str(backup_file)}

    time.sleep(2)
    rescan = _scan_one_desc_h1(url)
    new_count = rescan["count"]
    text_json = json.dumps(rescan["texts"], ensure_ascii=False) if rescan["texts"] else None
    db.seo_upsert_desc_h1(
        url, url_type, new_count, text_json,
        datetime.now().isoformat(timespec="seconds"),
    )

    return {
        "ok": True,
        "url": url,
        "url_type": url_type,
        "replaced": n_replaced,
        "after_count": new_count,
        "backup": backup_file.name,
        "message": (
            f"Đã đổi {n_replaced} <h1> → <h2>. "
            f"Re-scan public URL: còn {new_count} H1 trong mô tả."
        ),
    }


# ─────────────────────────── H1-IN-DESC FIX-ALL BACKGROUND JOB ───────────────────────────

_h1_fix_all_state = {
    "running": False,
    "stop_requested": False,
    "total": 0,
    "checked": 0,
    "success": 0,
    "partial": 0,
    "failed": 0,
    "skipped": 0,
    "current_url": "",
    "url_type_filter": None,
    "started_at": None,
    "finished_at": None,
    "message": "",
    "results": {},
}
_h1_fix_all_lock = threading.Lock()


def h1_fix_all_state() -> dict:
    """Snapshot state job fix-all (thread-safe)."""
    with _h1_fix_all_lock:
        return {
            "running": _h1_fix_all_state["running"],
            "stop_requested": _h1_fix_all_state["stop_requested"],
            "total": _h1_fix_all_state["total"],
            "checked": _h1_fix_all_state["checked"],
            "success": _h1_fix_all_state["success"],
            "partial": _h1_fix_all_state["partial"],
            "failed": _h1_fix_all_state["failed"],
            "skipped": _h1_fix_all_state["skipped"],
            "current_url": _h1_fix_all_state["current_url"],
            "url_type_filter": _h1_fix_all_state["url_type_filter"],
            "started_at": _h1_fix_all_state["started_at"],
            "finished_at": _h1_fix_all_state["finished_at"],
            "message": _h1_fix_all_state["message"],
            "results": dict(_h1_fix_all_state["results"]),
        }


def stop_h1_fix_all() -> bool:
    """Đặt cờ stop. Worker sẽ kiểm tra giữa các bài và thoát."""
    with _h1_fix_all_lock:
        if _h1_fix_all_state["running"]:
            _h1_fix_all_state["stop_requested"] = True
            _h1_fix_all_state["message"] = "⏹️ Đã nhận yêu cầu dừng — đợi bài hiện tại xong..."
            return True
    return False


def run_h1_fix_all(url_type: str = None):
    """Worker: lấy tất cả URL vi phạm → fix sequential. Chỉ product+blog."""
    items = db.seo_h1_in_desc_list(url_type=url_type, only_violations=True, limit=5000)
    fixable = [it for it in items if it.get("url_type") in ("product", "blog")]
    skipped = len(items) - len(fixable)

    with _h1_fix_all_lock:
        _h1_fix_all_state.update({
            "running": True,
            "stop_requested": False,
            "total": len(fixable),
            "checked": 0,
            "success": 0,
            "partial": 0,
            "failed": 0,
            "skipped": skipped,
            "current_url": "",
            "url_type_filter": url_type,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": None,
            "message": f"Bắt đầu fix {len(fixable)} bài (bỏ qua {skipped} page/collection).",
            "results": {},
        })

    for it in fixable:
        with _h1_fix_all_lock:
            if _h1_fix_all_state["stop_requested"]:
                break
            _h1_fix_all_state["current_url"] = it["url"]

        url = it["url"]
        try:
            result = fix_h1_in_desc_for_url(url)
        except Exception as e:
            result = {"ok": False, "error": f"Exception: {e}"}

        with _h1_fix_all_lock:
            _h1_fix_all_state["checked"] += 1
            if result.get("ok"):
                if (result.get("after_count") or 0) == 0:
                    _h1_fix_all_state["success"] += 1
                    status = "success"
                else:
                    _h1_fix_all_state["partial"] += 1
                    status = "partial"
            else:
                _h1_fix_all_state["failed"] += 1
                status = "failed"
            _h1_fix_all_state["results"][url] = {
                "status": status,
                "after_count": result.get("after_count"),
                "replaced": result.get("replaced"),
                "error": result.get("error"),
                "message": result.get("message"),
            }

    with _h1_fix_all_lock:
        was_stopped = _h1_fix_all_state["stop_requested"]
        _h1_fix_all_state["running"] = False
        _h1_fix_all_state["finished_at"] = datetime.now().isoformat(timespec="seconds")
        _h1_fix_all_state["current_url"] = ""
        if was_stopped:
            _h1_fix_all_state["message"] = (
                f"⏹️ Đã dừng. Xử lý {_h1_fix_all_state['checked']}/{_h1_fix_all_state['total']} bài "
                f"(✅ {_h1_fix_all_state['success']} · ⚠️ {_h1_fix_all_state['partial']} · ❌ {_h1_fix_all_state['failed']})."
            )
        else:
            _h1_fix_all_state["message"] = (
                f"🏁 Hoàn tất {_h1_fix_all_state['checked']}/{_h1_fix_all_state['total']} bài "
                f"(✅ {_h1_fix_all_state['success']} · ⚠️ {_h1_fix_all_state['partial']} · ❌ {_h1_fix_all_state['failed']})."
            )


def start_h1_fix_all_async(url_type: str = None) -> bool:
    """Spawn worker thread. Trả False nếu job đang chạy."""
    with _h1_fix_all_lock:
        if _h1_fix_all_state["running"]:
            return False
    t = threading.Thread(target=run_h1_fix_all, args=(url_type,), daemon=True)
    t.start()
    return True


# ─────────────────────────── TITLE / META UNIFIED HUB ───────────────────────────
# Gom 8 loại lỗi title/meta vào 1 view: no_title, title_short, title_long, sintech_in_title,
# no_meta, meta_short, meta_long, meta_no_cta + 2 lỗi dup (duplicate_title, duplicate_meta).
# Auto-fix: gọi Codex CLI sinh 3 title + 3 meta → pick M1 → PUT Haravan metafields.

TITLE_META_ISSUE_CODES = {
    "no_title", "title_short", "title_long", "sintech_in_title",
    "no_meta", "meta_short", "meta_long", "meta_no_cta",
}
TITLE_META_DUP_CODES = {"duplicate_title", "duplicate_meta"}
ALL_TITLE_META_CODES = TITLE_META_ISSUE_CODES | TITLE_META_DUP_CODES

TITLE_META_LABELS = {
    "no_title":          ("🔴", "Thiếu title"),
    "title_short":       ("🟡", "Title ngắn"),
    "title_long":        ("🟡", "Title dài"),
    "sintech_in_title":  ("🟠", "Có 'Sintech' trong title"),
    "no_meta":           ("🔴", "Thiếu meta"),
    "meta_short":        ("🟡", "Meta ngắn"),
    "meta_long":         ("🟡", "Meta dài"),
    "meta_no_cta":       ("🟡", "Meta thiếu CTA HOA"),
    "duplicate_title":   ("🔁", "Title trùng URL khác"),
    "duplicate_meta":    ("🔁", "Meta trùng URL khác"),
}


def list_title_meta_pages(url_type: str = None, issue_filter: str = None,
                           sort: str = "score_asc", limit: int = 2000) -> list:
    """Lấy URL có ít nhất 1 lỗi title/meta, kèm full list issue codes.
    Tự tính thêm 2 mã duplicate_title / duplicate_meta từ DB.
    """
    conn = db.get_conn()
    rows = conn.execute("""
        SELECT id, url, url_type, title, title_len, meta_desc, meta_desc_len,
               score, issues, last_crawled
        FROM seo_pages
        WHERE last_crawled IS NOT NULL
    """).fetchall()
    conn.close()

    # Build dup sets
    dup_titles = set()
    for grp in db.seo_find_duplicates("title"):
        for u in grp["urls"]:
            dup_titles.add(u)
    dup_metas = set()
    for grp in db.seo_find_duplicates("meta_desc"):
        for u in grp["urls"]:
            dup_metas.add(u)

    out = []
    for r in rows:
        try:
            issue_list = json.loads(r["issues"]) if r["issues"] else []
        except Exception:
            issue_list = []
        codes = {it.get("code") for it in issue_list if it.get("code") in TITLE_META_ISSUE_CODES}
        if r["url"] in dup_titles:
            codes.add("duplicate_title")
        if r["url"] in dup_metas:
            codes.add("duplicate_meta")
        if not codes:
            continue
        if url_type and r["url_type"] != url_type:
            continue
        if issue_filter and issue_filter not in codes:
            continue
        out.append({
            "id": r["id"],
            "url": r["url"],
            "url_type": r["url_type"],
            "title": r["title"] or "",
            "title_len": r["title_len"] or 0,
            "meta_desc": r["meta_desc"] or "",
            "meta_desc_len": r["meta_desc_len"] or 0,
            "score": r["score"],
            "issue_codes": sorted(codes),
            "n_issues": len(codes),
            "last_crawled": r["last_crawled"],
        })

    if sort == "score_asc":
        out.sort(key=lambda x: (x["score"] if x["score"] is not None else 100, -x["n_issues"]))
    elif sort == "n_issues_desc":
        out.sort(key=lambda x: -x["n_issues"])
    elif sort == "url":
        out.sort(key=lambda x: x["url"])
    return out[:limit]


def title_meta_summary() -> dict:
    """Đếm số URL theo từng mã issue title/meta + tổng."""
    pages = list_title_meta_pages(limit=10000)
    by_code = {}
    by_type = {}
    for p in pages:
        for c in p["issue_codes"]:
            by_code[c] = by_code.get(c, 0) + 1
        t = p["url_type"] or "other"
        by_type[t] = by_type.get(t, 0) + 1
    return {
        "total": len(pages),
        "by_code": by_code,
        "by_type": by_type,
    }


_TITLE_META_SYSTEM_PROMPT = """Bạn là chuyên gia SEO cho Sintech.vn (shop PC/laptop/gaming gear, nền tảng Haravan).
NHIỆM VỤ: Viết 3 title + 3 meta description khác nhau cho 1 trang sản phẩm/bài viết.

⚠️ LIMIT KÝ TỰ — TUÂN THỦ TUYỆT ĐỐI:
- Mỗi TITLE: 45-58 ký tự (TỐI ĐA TUYỆT ĐỐI là 61). Nếu vượt 58 → REWRITE NGẮN.
- Mỗi META: 145-158 ký tự (min 140, max 160). Nếu ngắn hơn 145 hoặc dài hơn 158 → REWRITE.
- TRƯỚC KHI TRẢ VỀ: tự đếm len(title) và len(meta), nếu vi phạm phải sửa.

LUẬT TITLE:
- KHÔNG chứa từ "Sintech" (Haravan tự thêm " - Sintech" sau)
- BẮT BUỘC có: tên model/sản phẩm + spec mạnh nhất + ngữ cảnh dùng/mua
- Chuẩn hóa kỹ thuật: GDDR6 (không viết DDR6), giữ đúng độ phân giải/tỷ lệ thật
- TRÁNH: nhồi keyword, lặp từ, lan man, spec không chắc

LUẬT META DESCRIPTION (3 cái KHÁC GÓC NHÌN):
- M1 = SPEC: format `[Tên SP] [spec chính], [đặc điểm]. XEM NGAY tại Sintech.`
- M2 = SETUP/NHU CẦU: format `Setup/Build [tone/use case] cùng [SP] - [tính năng]. THAM KHẢO NGAY tại Sintech.`
- M3 = GIẢI PHÁP: format `[SP] - giải pháp [phục vụ ai], [đặc điểm]. CHỌN NGAY mẫu phù hợp tại Sintech.`
- CTA viết IN HOA cụm hành động — KHÔNG in hoa toàn câu
- 3 meta dùng 3 CTA khác nhau

CẤM TRONG META: "bền bỉ", "đẹp mắt", "Free ship", "đáng mua nhất", "tốt nhất 2026", "khôn nhất", "rẻ nhất", "Sintech" trong title, ghi giá nếu user không cung cấp.

QUY TẮC NGHIÊM:
- Nếu spec không chắc → viết an toàn theo tên + nhu cầu, KHÔNG bịa
- 3 title phải KHÁC nhau rõ rệt (theo spec / theo nhu cầu / theo brand)

OUTPUT BẮT BUỘC: chỉ JSON thuần (KHÔNG markdown code fence, KHÔNG text gì khác).
{
  "titles": ["...", "...", "..."],
  "metas": ["...", "...", "..."]
}"""


def _gen_title_meta_via_codex(product_title: str, url: str,
                              current_title: str = "", current_meta: str = "") -> dict:
    """Gọi Codex CLI sinh 3 title + 3 meta. Return {ok, titles[], metas[], error}."""
    import codex_provider
    if not codex_provider.is_codex_available():
        return {"ok": False, "error": "Codex CLI chưa cài (npm install -g @openai/codex)."}

    user_msg = f"""SP cần viết:
- Tên SP / chủ đề: {product_title}
- URL: {url}
- Title hiện tại (cần thay): {current_title or '(rỗng)'} [{len(current_title)}c]
- Meta hiện tại (cần thay): {current_meta or '(rỗng)'} [{len(current_meta)}c]

Sinh 3 title + 3 meta mới theo rule. Trả JSON thuần."""

    try:
        raw = codex_provider.call_codex(_TITLE_META_SYSTEM_PROMPT, user_msg, timeout=120)
    except codex_provider.CodexRateLimitError as e:
        return {"ok": False, "error": f"Codex rate limit: {e}"}
    except Exception as e:
        return {"ok": False, "error": f"Codex error: {e}"}

    text = raw.strip()
    # Strip code fence nếu có
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return {"ok": False, "error": "Codex trả không phải JSON.", "raw": text[:500]}
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"JSON parse lỗi: {e}", "raw": text[:500]}

    titles = data.get("titles") or []
    metas = data.get("metas") or []
    if len(titles) < 1 or len(metas) < 1:
        return {"ok": False, "error": "Codex không trả đủ titles/metas.", "raw": text[:500]}
    return {"ok": True, "titles": titles, "metas": metas}


_TITLE_META_BACKUP_DIR = Path(__file__).parent.parent / "data" / "title_meta_fix_backup"


def fix_title_meta_for_url(url: str, force_title: str = None, force_meta: str = None) -> dict:
    """Auto-fix title + meta của 1 URL: gọi Codex gen → PUT Haravan metafields_global_*.
    Nếu force_title/force_meta cung cấp thì dùng luôn, skip Codex.
    Support: product. Blog/page/collection: TODO sau.
    """
    url_type = classify_url(url)
    if url_type != "product":
        return {"ok": False, "error": f"Loại '{url_type}' chưa hỗ trợ auto-fix (chỉ product)."}

    path = urlparse(url).path
    m = re.search(r"/products/([^/]+)", path)
    if not m:
        return {"ok": False, "error": "URL không match pattern /products/<handle>."}
    handle = m.group(1)
    row = db.hv_get_product_by_handle(handle)
    if not row:
        return {"ok": False, "error": "Không tìm thấy SP trong DB local. Sync Haravan products trước."}
    haravan_id = row["haravan_id"]

    try:
        product = haravan_client.get_product(haravan_id)
    except Exception as e:
        return {"ok": False, "error": f"Fetch product lỗi: {e}"}

    product_name = product.get("title") or row.get("title") or handle
    old_title = product.get("metafields_global_title_tag") or ""
    old_meta = product.get("metafields_global_description_tag") or ""

    if force_title and force_meta:
        new_title = force_title.strip()
        new_meta = force_meta.strip()
        ai_used = False
    else:
        gen = _gen_title_meta_via_codex(product_name, url, old_title, old_meta)
        if not gen["ok"]:
            return {"ok": False, "error": gen["error"], "raw": gen.get("raw")}
        new_title = gen["titles"][0].strip()
        new_meta = gen["metas"][0].strip()
        ai_used = True

    # Validate length cứng
    if len(new_title) > 61:
        return {"ok": False, "error": f"Title gen {len(new_title)}c > 61c — Codex output sai.",
                "gen_title": new_title, "gen_meta": new_meta}
    if len(new_meta) > 160 or len(new_meta) < 140:
        return {"ok": False, "error": f"Meta gen {len(new_meta)}c ngoài 140-160 — Codex output sai.",
                "gen_title": new_title, "gen_meta": new_meta}

    # Backup
    _TITLE_META_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = _TITLE_META_BACKUP_DIR / f"product_{haravan_id}_{ts}.json"
    try:
        backup_file.write_text(
            json.dumps({
                "haravan_id": haravan_id, "url": url,
                "old_title": old_title, "old_meta": old_meta,
                "new_title": new_title, "new_meta": new_meta,
                "ai_used": ai_used, "ts": ts,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        return {"ok": False, "error": f"Backup lỗi: {e}"}

    # PUT Haravan
    try:
        haravan_client.update_product(haravan_id, {
            "metafields_global_title_tag": new_title,
            "metafields_global_description_tag": new_meta,
        })
    except Exception as e:
        return {"ok": False, "error": f"PUT Haravan lỗi: {e}", "backup": backup_file.name}

    return {
        "ok": True,
        "url": url,
        "ai_used": ai_used,
        "old_title": old_title,
        "old_meta": old_meta,
        "new_title": new_title,
        "new_meta": new_meta,
        "title_len": len(new_title),
        "meta_len": len(new_meta),
        "backup": backup_file.name,
        "message": f"Đã update title ({len(new_title)}c) + meta ({len(new_meta)}c) lên Haravan.",
    }


# ─── Background job fix-all title/meta ───

_title_meta_fix_state = {
    "running": False,
    "stop_requested": False,
    "total": 0,
    "checked": 0,
    "success": 0,
    "failed": 0,
    "skipped": 0,
    "current_url": "",
    "started_at": None,
    "finished_at": None,
    "message": "",
    "results": {},
}
_title_meta_fix_lock = threading.Lock()


def title_meta_fix_state() -> dict:
    with _title_meta_fix_lock:
        return {
            **{k: v for k, v in _title_meta_fix_state.items() if k != "results"},
            "results": dict(_title_meta_fix_state["results"]),
        }


def stop_title_meta_fix() -> bool:
    with _title_meta_fix_lock:
        if _title_meta_fix_state["running"]:
            _title_meta_fix_state["stop_requested"] = True
            _title_meta_fix_state["message"] = "⏹️ Đã nhận yêu cầu dừng — đợi bài hiện tại xong..."
            return True
    return False


def run_title_meta_fix_all(url_type: str = None, issue_filter: str = None):
    pages = list_title_meta_pages(url_type=url_type, issue_filter=issue_filter, limit=10000)
    fixable = [p for p in pages if p["url_type"] == "product"]
    skipped = len(pages) - len(fixable)

    with _title_meta_fix_lock:
        _title_meta_fix_state.update({
            "running": True, "stop_requested": False,
            "total": len(fixable), "checked": 0,
            "success": 0, "failed": 0, "skipped": skipped,
            "current_url": "",
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": None,
            "message": f"Bắt đầu fix {len(fixable)} SP (bỏ qua {skipped} blog/page/collection).",
            "results": {},
        })

    for p in fixable:
        with _title_meta_fix_lock:
            if _title_meta_fix_state["stop_requested"]:
                break
            _title_meta_fix_state["current_url"] = p["url"]

        try:
            result = fix_title_meta_for_url(p["url"])
        except Exception as e:
            result = {"ok": False, "error": f"Exception: {e}"}

        with _title_meta_fix_lock:
            _title_meta_fix_state["checked"] += 1
            if result.get("ok"):
                _title_meta_fix_state["success"] += 1
                status = "success"
            else:
                _title_meta_fix_state["failed"] += 1
                status = "failed"
            _title_meta_fix_state["results"][p["url"]] = {
                "status": status,
                "new_title": result.get("new_title"),
                "new_meta": result.get("new_meta"),
                "title_len": result.get("title_len"),
                "meta_len": result.get("meta_len"),
                "error": result.get("error"),
            }

    with _title_meta_fix_lock:
        was_stopped = _title_meta_fix_state["stop_requested"]
        _title_meta_fix_state["running"] = False
        _title_meta_fix_state["finished_at"] = datetime.now().isoformat(timespec="seconds")
        _title_meta_fix_state["current_url"] = ""
        prefix = "⏹️ Đã dừng" if was_stopped else "🏁 Hoàn tất"
        _title_meta_fix_state["message"] = (
            f"{prefix} {_title_meta_fix_state['checked']}/{_title_meta_fix_state['total']} bài "
            f"(✅ {_title_meta_fix_state['success']} · ❌ {_title_meta_fix_state['failed']})."
        )


def start_title_meta_fix_all_async(url_type: str = None, issue_filter: str = None) -> bool:
    with _title_meta_fix_lock:
        if _title_meta_fix_state["running"]:
            return False
    t = threading.Thread(target=run_title_meta_fix_all,
                         args=(url_type, issue_filter), daemon=True)
    t.start()
    return True


# ─────────────────────────── GSC INSIGHTS ───────────────────────────
# Cache data từ 2 Google Sheet export (GSC Performance + Coverage). Build
# task list tổng hợp + chi tiết từng task. Khi nào có GSC API token sẽ
# refactor sang fetch trực tiếp.

_GSC_CACHE_PATH = Path(__file__).parent / "data" / "gsc_cache.json"


def gsc_load_cache():
    """Đọc cache JSON. Trả None nếu chưa fetch."""
    if not _GSC_CACHE_PATH.exists():
        return None
    try:
        return json.loads(_GSC_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def gsc_build_tasks(cache: dict) -> list:
    """Build danh sách task action từ cache GSC. Mỗi task có id/title/desc/level/count/items."""
    if not cache:
        return []
    cov = cache.get("coverage", {}).get("critical", {})
    perf = cache.get("performance", {})
    task_urls = cache.get("task_urls", {})  # URL list từ 5 sheet drilldown
    tasks = []

    # 1. 404
    c = cov.get("not_found_404", {}).get("count", 0)
    url_list = task_urls.get("not_found_404", [])
    tasks.append({
        "id": "not_found_404", "level": "critical", "count": c,
        "icon": "❌",
        "title": f"Fix {c} URL trả 404",
        "desc": "Google đã crawl URL nhưng giờ trả 404 — mất hoàn toàn SEO juice. Cần 301 redirect sang URL tương đương hoặc category.",
        "action": "Phân loại: SP đã xóa / SP đổi handle / typo cũ → build redirect map 301 qua Haravan hoặc Cloudflare.",
        "needs_export": not bool(url_list), "items": url_list,
    })

    # 2. Crawled not indexed (KHỦNG HOẢNG)
    c = cov.get("crawled_not_indexed", {}).get("count", 0)
    url_list = task_urls.get("crawled_not_indexed", [])
    tasks.append({
        "id": "crawled_not_indexed", "level": "critical", "count": c,
        "icon": "🚨",
        "title": f"{c} URL chưa được Google index",
        "desc": "URL được crawl nhưng Google quyết định KHÔNG index — content thin/duplicate/thiếu authority. Đây là nguyên nhân chính trafic không bùng nổ.",
        "action": "Trigger /content-jobs queue (1233 SP đang pending) để gen content đầy đủ. Mỗi bài 800-2700 từ + title/meta chuẩn + 4-6 ảnh + internal link.",
        "needs_export": not bool(url_list), "items": url_list,
    })

    # 3. CTR thấp + impression cao — auto-populated
    low_ctr = [p for p in perf.get("pages", [])
               if p["imp"] >= 1000 and p["ctr"] < 3.0]
    low_ctr.sort(key=lambda x: -x["imp"])
    tasks.append({
        "id": "ctr_low_high_imp", "level": "high", "count": len(low_ctr),
        "icon": "📉",
        "title": f"{len(low_ctr)} URL impression cao + CTR thấp (<3%)",
        "desc": "Google show URL nhiều nhưng khách ít click → title/meta không hấp dẫn. Sửa title/meta = boost click ngay.",
        "action": "Mở /seo/title-meta → AI auto-fix Codex theo rule SEO Sintech (title 45-61c, meta 140-160c, CTA HOA).",
        "needs_export": False, "items": low_ctr[:50],  # cap 50 cho UI
    })

    # 4. Keyword position 11-20 — auto-populated
    pos_11_20 = [q for q in perf.get("queries", [])
                 if 11 <= q["pos"] <= 20 and q["imp"] >= 100]
    pos_11_20.sort(key=lambda x: -x["imp"])
    tasks.append({
        "id": "pos_11_20", "level": "high", "count": len(pos_11_20),
        "icon": "🚀",
        "title": f"{len(pos_11_20)} keyword đang pos 11-20 (page 2)",
        "desc": "Keyword sắp lên top 10 — chỉ cần đẩy nhẹ là leo lên trang 1 → boost traffic 50-200%.",
        "action": "Audit URL match → thêm 5-10 internal link từ blog/SP về URL đó + bổ sung 300-500 từ content.",
        "needs_export": False, "items": pos_11_20[:50],
    })

    # 5. Top CTR (đang tốt — giữ vững)
    top_ctr = [q for q in perf.get("queries", [])
               if q["imp"] >= 200 and q["ctr"] >= 10]
    top_ctr.sort(key=lambda x: -x["click"])
    tasks.append({
        "id": "top_cash_cow", "level": "info", "count": len(top_ctr),
        "icon": "💰",
        "title": f"{len(top_ctr)} keyword đang cash cow (CTR >10%)",
        "desc": "Keyword đang mang traffic mạnh — cần MONITOR + giữ vững thứ hạng. Không để fall.",
        "action": "Update content định kỳ (2 tháng/lần) + check competitor.",
        "needs_export": False, "items": top_ctr[:50],
    })

    # 6. Discovered not crawled
    c = cov.get("discovered_not_indexed", {}).get("count", 0)
    url_list = task_urls.get("discovered_not_indexed", [])
    tasks.append({
        "id": "discovered_not_indexed", "level": "medium", "count": c,
        "icon": "🟡",
        "title": f"{c} URL Google biết nhưng chưa crawl",
        "desc": "URL đã phát hiện qua sitemap nhưng Google chưa thu thập dữ liệu. Có thể do crawl budget.",
        "action": "GSC → URL Inspection → paste từng URL → 'Request indexing'. Hoặc thêm internal link để tăng độ ưu tiên crawl.",
        "needs_export": not bool(url_list), "items": url_list,
    })

    # 7. Noindex review
    c = cov.get("noindex_excluded", {}).get("count", 0)
    url_list = task_urls.get("noindex_excluded", [])
    tasks.append({
        "id": "noindex_excluded", "level": "medium", "count": c,
        "icon": "🟠",
        "title": f"{c} URL bị noindex — audit có nhầm không",
        "desc": "URL có meta `noindex` (vd page /cart, /search) → kiểm tra SP/blog nào nhầm noindex.",
        "action": "Audit list — verify URL nào nhầm noindex thì bỏ tag noindex trong Haravan admin.",
        "needs_export": not bool(url_list), "items": url_list,
    })

    # 8. Duplicate canonical
    c = cov.get("duplicate_canonical", {}).get("count", 0)
    url_list = task_urls.get("duplicate_canonical", [])
    tasks.append({
        "id": "duplicate_canonical", "level": "medium", "count": c,
        "icon": "🟠",
        "title": f"{c} URL Google chọn canonical khác",
        "desc": "Có thể variant SP đang conflict canonical với SP gốc.",
        "action": "Audit từng URL — verify canonical đang trỏ đúng chỗ hay không.",
        "needs_export": not bool(url_list), "items": url_list,
    })

    return tasks


def gsc_get_task(task_id: str) -> dict:
    """Lấy task theo id."""
    cache = gsc_load_cache()
    if not cache:
        return None
    for t in gsc_build_tasks(cache):
        if t["id"] == task_id:
            return t
    return None


# ─────────────────────────── EMPTY-DESC QUICK SCANNER (PRODUCT) ───────────────────────────
# Quét nhanh các URL sản phẩm → đếm số từ trong `.rte.product_getcontent`.
# Mục đích: tìm SP chưa có mô tả (hoặc mô tả quá ngắn) để bổ sung content.

_empty_desc_state = {
    "running": False, "total": 0, "checked": 0,
    "empty": 0, "short": 0, "ok": 0, "failed": 0,
    "started_at": None, "message": "", "threshold": EMPTY_DESC_THRESHOLD,
}
_empty_desc_lock = threading.Lock()


def empty_desc_state():
    with _empty_desc_lock:
        return dict(_empty_desc_state)


def _count_desc_words(soup) -> int:
    """Đếm số từ text trong container mô tả SP (`.rte.product_getcontent`).

    Strip script/style trước khi đếm. Trả 0 nếu không tìm thấy container.
    """
    blocks = soup.select(PRODUCT_DESC_SELECTOR)
    if not blocks:
        return 0
    total = 0
    for block in blocks:
        # clone-like: remove script/style trong block
        for s in block.select("script, style, noscript"):
            s.decompose()
        text = block.get_text(" ", strip=True)
        total += len(re.findall(r"\w+", text, flags=re.UNICODE))
    return total


def _scan_one_empty_desc(url: str) -> dict:
    """Fetch 1 URL → đếm số từ trong .rte.product_getcontent. Trả dict."""
    headers = {"User-Agent": USER_AGENT}
    url_type = classify_url(url)
    try:
        r = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code >= 400:
            return {"url": url, "url_type": url_type, "word_count": 0, "ok": False}
        soup = BeautifulSoup(r.content, "lxml")
        wc = _count_desc_words(soup)
        return {"url": url, "url_type": url_type, "word_count": wc, "ok": True}
    except Exception:
        return {"url": url, "url_type": url_type, "word_count": 0, "ok": False}


def run_empty_desc_scan(threshold: int = EMPTY_DESC_THRESHOLD, limit: int = None):
    """Quét sitemap chỉ với /products/... → đếm số từ trong mô tả → ghi DB."""
    with _empty_desc_lock:
        if _empty_desc_state["running"]:
            return
        _empty_desc_state.update({
            "running": True, "total": 0, "checked": 0,
            "empty": 0, "short": 0, "ok": 0, "failed": 0,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "message": "Đang fetch sitemap...",
            "threshold": threshold,
        })
    try:
        urls = [u for u in fetch_sitemap_urls() if classify_url(u) == "product"]
        if limit:
            urls = urls[:limit]
        total = len(urls)
        with _empty_desc_lock:
            _empty_desc_state.update({"total": total, "message": f"Quét {total} sản phẩm..."})

        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(_scan_one_empty_desc, u): u for u in urls}
            for fut in as_completed(futures):
                try:
                    res = fut.result()
                    scanned_at = datetime.now().isoformat(timespec="seconds")
                    db.seo_upsert_empty_desc(
                        res["url"], res["url_type"], res["word_count"], scanned_at,
                    )
                    with _empty_desc_lock:
                        _empty_desc_state["checked"] += 1
                        if not res["ok"]:
                            _empty_desc_state["failed"] += 1
                        elif res["word_count"] == 0:
                            _empty_desc_state["empty"] += 1
                        elif res["word_count"] < threshold:
                            _empty_desc_state["short"] += 1
                        else:
                            _empty_desc_state["ok"] += 1
                except Exception:
                    with _empty_desc_lock:
                        _empty_desc_state["checked"] += 1
                        _empty_desc_state["failed"] += 1

        with _empty_desc_lock:
            s = _empty_desc_state
            s["message"] = (
                f"Xong: {s['empty']} SP rỗng, {s['short']} SP <{threshold} từ "
                f"({s['checked']}/{total} đã quét, {s['failed']} lỗi fetch)."
            )
        try:
            db.activity_log(
                kind="seo_empty_desc_scan", icon="📭",
                title=f"Quét SP thiếu mô tả: {s['empty']} rỗng + {s['short']} ngắn",
                description=f"Quét {s['checked']}/{total} SP, threshold={threshold} từ",
                href="/seo/empty-desc",
            )
        except Exception:
            pass
    finally:
        with _empty_desc_lock:
            _empty_desc_state["running"] = False


def start_empty_desc_scan_async(threshold: int = EMPTY_DESC_THRESHOLD, limit: int = None) -> bool:
    with _empty_desc_lock:
        if _empty_desc_state["running"]:
            return False
    t = threading.Thread(target=run_empty_desc_scan, args=(threshold, limit), daemon=True)
    t.start()
    return True


# ─────────────────────────── DUPLICATE TITLE / META POST-PROCESS ───────────────────────────


_DUP_TITLE_SUFFIX_RE = re.compile(r"\s*[-–—|]\s*sintech.*$", re.IGNORECASE)


def _norm_title(s: str) -> str:
    if not s:
        return ""
    t = _DUP_TITLE_SUFFIX_RE.sub("", str(s)).strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _norm_meta(s: str) -> str:
    if not s:
        return ""
    t = str(s).strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def recompute_dup_flags() -> dict:
    """Detect duplicate title/meta cross-site. Trừ điểm + thêm issue vào seo_pages.

    Algo:
      - Query mọi page status 2xx có title not null.
      - Group theo normalized title (bỏ suffix Haravan ' - Sintech') → groups ≥2 page = dup.
      - Tương tự cho meta_desc.
      - Mỗi page bị dup: trừ -5 cho dup_title, -5 cho dup_meta (max -10), update issues + score.
      - Cap score min 0.

    Trả dict stats.
    """
    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT id, url, title, meta_desc, score, issues FROM seo_pages "
            "WHERE status_code BETWEEN 200 AND 299 AND title IS NOT NULL"
        ).fetchall()
    except Exception:
        conn.close()
        return {"dup_title_count": 0, "dup_meta_count": 0,
                "affected_pages": 0, "total_deducted": 0}

    # Build groups
    by_title: dict = {}
    by_meta: dict = {}
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        nt = _norm_title(d.get("title"))
        nm = _norm_meta(d.get("meta_desc"))
        if nt:
            by_title.setdefault(nt, []).append(d)
        if nm:
            by_meta.setdefault(nm, []).append(d)

    dup_title_groups = {k: v for k, v in by_title.items() if len(v) >= 2}
    dup_meta_groups = {k: v for k, v in by_meta.items() if len(v) >= 2}

    affected: dict = {}  # id -> {deduct, new_issues_codes}
    # Title dups
    for grp in dup_title_groups.values():
        urls = [g["url"] for g in grp]
        for g in grp:
            others = [u for u in urls if u != g["url"]][:3]
            entry = affected.setdefault(g["id"], {"page": g, "deduct": 0, "issues_extra": []})
            entry["deduct"] += 5
            entry["issues_extra"].append({
                "level": "warn", "code": "dup_title",
                "msg": f"Title trùng với {len(urls) - 1} URL khác: " + ", ".join(others),
            })
    # Meta dups
    for grp in dup_meta_groups.values():
        urls = [g["url"] for g in grp]
        for g in grp:
            others = [u for u in urls if u != g["url"]][:3]
            entry = affected.setdefault(g["id"], {"page": g, "deduct": 0, "issues_extra": []})
            entry["deduct"] += 5
            entry["issues_extra"].append({
                "level": "warn", "code": "dup_meta",
                "msg": f"Meta description trùng với {len(urls) - 1} URL khác: " + ", ".join(others),
            })

    total_deducted = 0
    updated = 0
    try:
        for pid, info in affected.items():
            page = info["page"]
            deduct = min(info["deduct"], 10)  # cap -10
            # parse existing issues
            try:
                cur_issues = json.loads(page.get("issues") or "[]") or []
                if not isinstance(cur_issues, list):
                    cur_issues = []
            except Exception:
                cur_issues = []
            # remove any previous dup_title/dup_meta issues to avoid duplication on re-run
            cur_issues = [i for i in cur_issues if i.get("code") not in ("dup_title", "dup_meta")]
            cur_issues.extend(info["issues_extra"])
            new_score = max(0, (page.get("score") or 0) - deduct)
            total_deducted += deduct
            conn.execute(
                "UPDATE seo_pages SET score = ?, issues = ? WHERE id = ?",
                (new_score, json.dumps(cur_issues, ensure_ascii=False), pid),
            )
            updated += 1
        conn.commit()
    finally:
        conn.close()

    # Also re-run for pages that previously had dup flags but are no longer dup,
    # so we strip stale dup_title/dup_meta and restore points.
    try:
        conn2 = db.get_conn()
        stale_rows = conn2.execute(
            "SELECT id, score, issues FROM seo_pages WHERE issues LIKE '%dup_title%' OR issues LIKE '%dup_meta%'"
        ).fetchall()
        for r in stale_rows:
            d = dict(r)
            if d["id"] in affected:
                continue  # was just updated, fresh
            try:
                cur_issues = json.loads(d.get("issues") or "[]") or []
            except Exception:
                cur_issues = []
            removed = [i for i in cur_issues if i.get("code") in ("dup_title", "dup_meta")]
            if not removed:
                continue
            kept = [i for i in cur_issues if i.get("code") not in ("dup_title", "dup_meta")]
            restore = min(5 * len(removed), 10)
            new_score = min(100, (d.get("score") or 0) + restore)
            conn2.execute(
                "UPDATE seo_pages SET score = ?, issues = ? WHERE id = ?",
                (new_score, json.dumps(kept, ensure_ascii=False), d["id"]),
            )
        conn2.commit()
        conn2.close()
    except Exception:
        pass

    return {
        "dup_title_count": len(dup_title_groups),
        "dup_meta_count": len(dup_meta_groups),
        "affected_pages": updated,
        "total_deducted": total_deducted,
    }
