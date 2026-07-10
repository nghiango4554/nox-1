"""SEO Opportunity + SERP Brief Engine.

Hai gap được lấp:
  1. Keyword Opportunity Engine — gom keyword từ GSC (data thật) + import CSV
     (SEMrush/Ahrefs/Keyword Planner/DataForSEO/manual) → chấm opportunity_score
     giải thích được → phân loại page_type + status.
  2. SERP Brief Builder — fetch 3-5 URL top SERP do người dùng NHẬP TAY → trích
     cấu trúc (title/meta/H1/H2/H3/word_count/image_count/schema/canonical) → tổng
     hợp khuôn bài "inspired by" (KHÔNG clone) → outline + title/meta options +
     internal link gợi ý + risk notes.

NGUYÊN TẮC AN TOÀN (bất biến):
  - KHÔNG publish, KHÔNG PUT/POST Haravan, KHÔNG tạo content job live.
  - KHÔNG gọi API SERP trả phí (DataForSEO/SerpAPI) — chỉ chừa interface, disabled.
  - KHÔNG scrape cả site đối thủ — chỉ fetch đúng URL người dùng nhập, timeout thấp.
  - KHÔNG copy nội dung đối thủ — chỉ lấy cấu trúc/heading/độ dài/độ phủ topic.
  - Không bịa KD/volume: thiếu dữ liệu thì để NULL, source ghi rõ.

Schema additive idempotent (CREATE TABLE IF NOT EXISTS) — ensure_schema() gọi ở
mỗi route entry (giống bcc.ensure_schema()), nên không cần restart để có bảng.
"""
from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from datetime import datetime
from urllib.parse import urlparse

import db

# ───────────────────────── constants ─────────────────────────

PAGE_TYPES = (
    "blog_info", "blog_commercial", "landing_page", "service_page", "support_page",
    "collection_page", "product_page", "faq", "ignore",
)
STATUSES = (
    "new", "review", "approved", "brief_ready",
    "writing", "published", "monitoring", "ignored",
)
INTENTS = ("informational", "commercial", "transactional", "navigational")

DEFAULT_COUNTRY = "VN"
DEFAULT_LANGUAGE = "vi"

# Cột CSV hỗ trợ (header nhận diện case-insensitive, thiếu cột vẫn import được).
CSV_FIELDS = (
    "keyword", "volume", "keyword_difficulty", "cpc", "intent",
    "serp_features", "source", "country", "language", "topic", "note",
)

# Alias header phổ biến từ SEMrush/Ahrefs/Keyword Planner → field nội bộ.
_CSV_ALIASES = {
    "keyword": "keyword",
    "keywords": "keyword",
    "search term": "keyword",
    "query": "keyword",
    "volume": "volume",
    "search volume": "volume",
    "avg. monthly searches": "volume",
    "avg monthly searches": "volume",
    "kd": "keyword_difficulty",
    "kd %": "keyword_difficulty",
    "keyword difficulty": "keyword_difficulty",
    "difficulty": "keyword_difficulty",
    "cpc": "cpc",
    "cpc (usd)": "cpc",
    "intent": "intent",
    "search intent": "intent",
    "serp features": "serp_features",
    "serp_features": "serp_features",
    "source": "source",
    "country": "country",
    "language": "language",
    "topic": "topic",
    "topic cluster": "topic",
    "note": "note",
    "notes": "note",
}

USER_AGENT = "SintechHubSEOBot/1.0 (+marketing_hub serp-brief)"

# ───────────────────────── schema ─────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS seo_keyword_opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    normalized_keyword TEXT NOT NULL,
    source TEXT,
    source_row_id TEXT,
    volume INTEGER,
    keyword_difficulty REAL,
    cpc REAL,
    intent TEXT,
    country TEXT DEFAULT 'VN',
    language TEXT DEFAULT 'vi',
    gsc_clicks INTEGER,
    gsc_impressions INTEGER,
    gsc_ctr REAL,
    gsc_position REAL,
    current_target_url TEXT,
    suggested_page_type TEXT,
    topic_cluster TEXT,
    opportunity_score REAL,
    priority TEXT,
    status TEXT DEFAULT 'new',
    notes TEXT,
    created_at TEXT,
    updated_at TEXT,
    UNIQUE(normalized_keyword, source, country, language)
);
CREATE INDEX IF NOT EXISTS idx_seo_kw_opp_score ON seo_keyword_opportunities(opportunity_score DESC);
CREATE INDEX IF NOT EXISTS idx_seo_kw_opp_status ON seo_keyword_opportunities(status);
CREATE INDEX IF NOT EXISTS idx_seo_kw_opp_source ON seo_keyword_opportunities(source);
CREATE INDEX IF NOT EXISTS idx_seo_kw_opp_ptype ON seo_keyword_opportunities(suggested_page_type);

CREATE TABLE IF NOT EXISTS seo_keyword_import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    filename TEXT,
    imported_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    created_at TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS seo_serp_briefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword_id INTEGER,
    keyword TEXT NOT NULL,
    source_mode TEXT,
    serp_urls_json TEXT,
    competitor_summary_json TEXT,
    avg_word_count REAL,
    avg_h2_count REAL,
    avg_image_count REAL,
    common_headings_json TEXT,
    missing_angles_json TEXT,
    recommended_outline_json TEXT,
    recommended_title_options_json TEXT,
    recommended_meta_options_json TEXT,
    internal_link_suggestions_json TEXT,
    risk_notes TEXT,
    status TEXT DEFAULT 'new',
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_seo_serp_briefs_kw ON seo_serp_briefs(keyword_id);

CREATE TABLE IF NOT EXISTS seo_serp_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brief_id INTEGER,
    url TEXT,
    title TEXT,
    meta_description TEXT,
    h1 TEXT,
    h2_json TEXT,
    h3_json TEXT,
    word_count INTEGER,
    image_count INTEGER,
    schema_types_json TEXT,
    canonical_url TEXT,
    fetch_status TEXT,
    extracted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_seo_serp_pages_brief ON seo_serp_pages(brief_id);
"""


def ensure_schema():
    """Tạo 4 bảng nếu chưa có. Idempotent — an toàn gọi mỗi request."""
    conn = db.get_conn()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ───────────────────────── helpers ─────────────────────────

def normalize_keyword(kw: str) -> str:
    """Chuẩn hoá để dedup: lowercase + gộp khoảng trắng + bỏ ký tự control.
    GIỮ dấu tiếng Việt (bỏ dấu sẽ gộp nhầm keyword khác nghĩa)."""
    if not kw:
        return ""
    s = unicodedata.normalize("NFC", str(kw)).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _to_int(v):
    if v is None:
        return None
    s = re.sub(r"[^\d\-]", "", str(v))
    if s in ("", "-"):
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _to_float(v):
    if v is None:
        return None
    s = re.sub(r"[^\d.\-]", "", str(v).replace(",", "."))
    if s in ("", "-", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _norm_intent(v):
    if not v:
        return None
    s = str(v).strip().lower()
    mapping = {
        "i": "informational", "info": "informational", "informational": "informational",
        "c": "commercial", "commercial": "commercial",
        "t": "transactional", "transactional": "transactional", "transaction": "transactional",
        "n": "navigational", "navigational": "navigational", "branded": "navigational",
    }
    return mapping.get(s, s if s in INTENTS else None)


# ───────────────────────── opportunity scoring ─────────────────────────

def compute_score(row: dict) -> tuple[float, dict]:
    """Score 0-100 giải thích được. Trả (score, breakdown).

    opportunity_score =
        intent_weight + impression_or_volume_weight + low_difficulty_weight
        + current_position_weight + ctr_gap_weight + business_priority_weight
        - cannibalization_risk - too_broad_penalty

    Không bịa KD/volume: thiếu thì component đó = 0 + ghi note trong breakdown.
    """
    import math
    bd: dict = {}

    # 1) intent_weight (0-20): mua/dịch vụ > thông tin.
    intent = (row.get("intent") or "").lower()
    intent_map = {"transactional": 20, "commercial": 16, "informational": 10, "navigational": 4}
    iw = intent_map.get(intent, 8)
    bd["intent_weight"] = iw

    # 2) impression_or_volume_weight (0-25): log-scale theo max(volume, gsc_impressions).
    vol = row.get("volume")
    imp = row.get("gsc_impressions")
    demand = max([v for v in (vol, imp) if v] or [0])
    if demand > 0:
        vw = min(25.0, round(math.log10(demand + 1) * 7.0, 1))
        bd["volume_weight"] = vw
    else:
        vw = 0.0
        bd["volume_weight"] = 0.0
        bd["volume_note"] = "không có volume/impression → 0"

    # 3) low_difficulty_weight (0-20): KD thấp dễ rank. Không có KD → 0 (an toàn).
    kd = row.get("keyword_difficulty")
    if kd is not None:
        dw = round(max(0.0, (100.0 - float(kd)) / 100.0) * 20.0, 1)
        bd["low_difficulty_weight"] = dw
    else:
        dw = 0.0
        bd["low_difficulty_weight"] = 0.0
        bd["kd_note"] = "không có KD → 0"

    # 4) current_position_weight (0-20): striking distance (pos 4-20) cao nhất.
    pos = row.get("gsc_position")
    pw = 0.0
    if pos:
        if pos <= 3:
            pw = 4.0  # đã top, ít dư địa
        elif pos <= 10:
            pw = 20.0  # trang 1 nửa dưới — đẩy lên dễ ăn
        elif pos <= 20:
            pw = 15.0  # trang 2 — striking distance
        elif pos <= 40:
            pw = 8.0
        else:
            pw = 3.0
    bd["position_weight"] = pw

    # 5) ctr_gap_weight (0-10): position tốt nhưng CTR thấp → cải thiện title/meta.
    ctr = row.get("gsc_ctr")
    cw = 0.0
    if pos and ctr is not None and pos <= 20:
        # CTR kỳ vọng thô theo vị trí (giảm dần). ctr lưu dạng tỉ lệ 0-1.
        expected = max(0.01, 0.30 / pos)
        if ctr < expected:
            cw = round(min(10.0, (expected - ctr) / expected * 10.0), 1)
    bd["ctr_gap_weight"] = cw

    # 6) business_priority_weight (0-10): manual priority.
    prio = (row.get("priority") or "").lower()
    pri_map = {"high": 10, "cao": 10, "medium": 5, "trung bình": 5, "trung binh": 5,
               "low": 2, "thấp": 2, "thap": 2}
    bw = pri_map.get(prio, 0)
    bd["priority_weight"] = bw

    # 7) cannibalization_risk (penalty 0-10): nhiều keyword đã trỏ cùng target url.
    cann = float(row.get("_cannibalization_risk") or 0)
    bd["cannibalization_risk"] = -cann

    # 8) too_broad_penalty (penalty 0-8): keyword 1 từ thường quá rộng/khó.
    kw = (row.get("keyword") or "").strip()
    broad = 8.0 if (kw and len(kw.split()) <= 1) else 0.0
    bd["too_broad_penalty"] = -broad

    score = iw + vw + dw + pw + cw + bw - cann - broad
    score = round(max(0.0, min(100.0, score)), 1)
    bd["total"] = score
    return score, bd


# ───────────────────────── classification (derive-on-read) ─────────────────────────
#
# 3 nguyên tắc (đã phản biện, đừng bỏ):
#   1) Match theo RANH GIỚI TỪ + token CÓ DẤU. KHÔNG substring thô với token ngắn
#      ("đánh giá" chứa "gia" nếu bỏ dấu → false-positive). Token "giá" (có dấu) khớp
#      "laptop giá rẻ" nhưng KHÔNG khớp "gia đình"/"tham gia"/"gia công" (chữ "gia" không dấu).
#   2) intent / suggested_page_type / recommended_action / reason / flags đều tính LÚC ĐỌC.
#      KHÔNG backfill hàng loạt vào DB. Cột DB chỉ giữ giá trị người dùng sửa tay (override).
#   3) MỘT hàm derive(row) là nguồn chân lý duy nhất → không lệch nhau.

# Token có dấu, khớp theo ranh giới từ. Cụm nhiều từ khớp nguyên cụm (cũng theo biên).
_INTENT_TOKENS = {
    "transactional": ("mua", "bán", "đặt mua", "order", "trả góp", "khuyến mãi",
                      "giảm giá", "sale", "ở đâu", "chỗ nào", "cửa hàng", "chính hãng"),
    "commercial": ("giá", "giá rẻ", "bao nhiêu", "tốt nhất", "loại nào", "nên chọn",
                   "nên mua", "so sánh", "review", "đánh giá", "có tốt", "có nên"),
    "informational": ("là gì", "tại sao", "vì sao", "cách", "hướng dẫn", "mẹo",
                      "kinh nghiệm", "how", "what", "why", "lỗi", "sửa"),
}


def _kw_has(kw_norm: str, token: str) -> bool:
    """True nếu `token` (có dấu) xuất hiện trong kw như MỘT TỪ/CỤM TỪ trọn vẹn.
    Dùng ranh giới từ Unicode (\\w bao gồm ký tự tiếng Việt) → không dính substring."""
    return re.search(r"(?<!\w)" + re.escape(token) + r"(?!\w)", kw_norm) is not None


def _classify_intent(kw_norm: str) -> str | None:
    """Suy luận intent từ keyword. Không chắc → None (KHÔNG ép bucket)."""
    if not kw_norm:
        return None
    # Ưu tiên transactional > commercial > informational khi trùng tín hiệu.
    for intent in ("transactional", "commercial", "informational"):
        for tok in _INTENT_TOKENS[intent]:
            if _kw_has(kw_norm, tok):
                return intent
    return None


def _suggest_page_type(kw_norm: str, intent: str | None) -> str:
    """Heuristic page_type LƯU DB (default khi upsert). Giữ đơn giản, ổn định."""
    if any(_kw_has(kw_norm, t) for t in ("là gì", "tại sao", "vì sao", "cách",
                                         "hướng dẫn", "how", "what", "why", "mẹo")):
        return "blog_info"
    if kw_norm.startswith(("có nên", "nên", "bao nhiêu")) or _kw_has(kw_norm, "có nên"):
        return "faq"
    if intent == "transactional":
        return "product_page"
    if intent == "commercial":
        return "collection_page"
    return "blog_info"


# ── safety / noise pre-check (chặn keyword rủi ro & nhiễu khỏi "quick win") ──
# 'crack'/'keygen' distinctive → substring; cụm có dấu match theo cụm.
_RISKY_SUBSTR = ("crack", "keygen", "bẻ khóa", "be khoa", "key lậu", "key lau",
                 "tải lậu", "tai lau", "kích hoạt lậu", "kich hoat lau", "bản quyền lậu")
# Domain / đối thủ hay lẫn vào GSC query.
_NOISE_DOMAINS = ("gearvn", "hacom", "cellphones", "phongvu", "phong vu", "baotintech",
                  "baotinhtech", "anphat", "an phat", "tncstore", "hanoicomputer",
                  "nguyenkim", "thegioididong", "fptshop")


def _is_risky(kw_norm: str) -> bool:
    return any(t in kw_norm for t in _RISKY_SUBSTR)


def _is_noise(kw_norm: str) -> bool:
    if ".com" in kw_norm or ".vn" in kw_norm:
        return True
    return any(_kw_has(kw_norm, d) or d in kw_norm for d in _NOISE_DOMAINS)


def _dynamic_page_type(kw_norm: str, intent: str | None) -> str:
    """Gợi ý page_type ĐỘNG (badge, KHÔNG ghi DB). Nhận diện landing/service/support
    — những loại mà 'chỉ sửa meta' là sai hướng. Thứ tự: service > landing > support > blog."""
    if any(_kw_has(kw_norm, t) for t in (
            "sửa laptop", "sua laptop", "sửa máy tính", "sua may tinh", "sửa pc",
            "vệ sinh laptop", "ve sinh laptop", "cài win", "cai win", "cài windows",
            "cai windows", "cài đặt win", "cai dat win", "cài mac", "cài macbook",
            "bảo trì", "bao tri")):
        return "service_page"
    if any(_kw_has(kw_norm, t) for t in (
            "build pc", "pc online", "xây dựng cấu hình", "xay dung cau hinh",
            "build online", "web build", "trang web build", "pc build")):
        return "landing_page"
    if any(_kw_has(kw_norm, t) for t in (
            "driver", "download", "tải", "tai", "phần mềm", "phan mem",
            "benchmark", "cài đặt", "cai dat")):
        return "support_page"
    if any(_kw_has(kw_norm, t) for t in (
            "là gì", "tại sao", "vì sao", "cách", "hướng dẫn", "so sánh", "khác gì",
            "how", "what", "why", "mẹo")):
        return "blog_info"
    return ""  # unknown — không ép


def derive(row: dict) -> dict:
    """NGUỒN CHÂN LÝ phân loại — tính lúc đọc, KHÔNG ghi DB.
    Trả {intent, suggested_page_type, page_type_suggest, recommended_action, reason, flags}.
    intent/suggested_page_type: ưu tiên giá trị người dùng đã lưu (override), else suy luận.
    page_type_suggest: gợi ý ĐỘNG (landing/service/support/blog) — chỉ badge, không ghi DB."""
    kw = normalize_keyword(row.get("keyword") or "")

    # intent: giữ giá trị đã set (CSV/GSC/sửa tay) nếu hợp lệ, else suy luận keyword.
    intent = (row.get("intent") or "").strip().lower() or None
    if intent not in INTENTS:
        intent = _classify_intent(kw)

    # page_type: giữ override đã lưu, else heuristic ổn định (cho <select>).
    page_type = row.get("suggested_page_type") or _suggest_page_type(kw, intent)
    pt_suggest = _dynamic_page_type(kw, intent)  # động — badge

    # flags — tín hiệu để người vận hành để mắt.
    flags: list[str] = []
    risky = _is_risky(kw)
    noise = _is_noise(kw)
    if risky:
        flags.append("risky")
    if noise:
        flags.append("noise")
    pos = row.get("gsc_position")
    ctr = row.get("gsc_ctr")
    demand = max([v for v in (row.get("volume"), row.get("gsc_impressions")) if v] or [0])
    if kw and len(kw.split()) <= 1:
        flags.append("too_broad")
    if pos and 4 <= pos <= 20:
        flags.append("striking_distance")
    if pos and ctr is not None and pos <= 20 and ctr < max(0.01, 0.30 / pos):
        flags.append("ctr_gap")
    if not intent:
        flags.append("intent_unclear")

    # recommended_action — SAFETY thắng trước (risky/noise → review_manual bất kể CTR gap).
    if risky:
        action = "review_manual"
        reason = "Keyword nhạy cảm/rủi ro (crack/bẻ khóa) → review thủ công, chỉ xử lý theo hướng bản quyền/an toàn."
    elif noise:
        action = "review_manual"
        reason = "Keyword có dấu hiệu nhiễu/domain/đối thủ → review trước khi xử lý."
    elif "ctr_gap" in flags and pos and pos <= 20:
        action = "improve_metadata"  # nhãn hiển thị = "CTR gap — cần xử lý" (không chỉ meta)
        reason = f"Đã rank (pos {pos}) nhưng CTR dưới kỳ vọng → soi snippet/page; sửa title/meta hoặc đúng loại page ({pt_suggest or page_type})."
    elif "striking_distance" in flags:
        action = "optimize_page"
        reason = f"Striking distance (pos {pos}) → tối ưu on-page/nội dung đẩy lên top."
    elif intent and (not pos or pos > 40) and demand > 0:
        action = "create_content"
        reason = f"Chưa rank, có nhu cầu (~{int(demand)} imp/vol), intent {intent} → tạo nội dung mới."
    elif not intent or "too_broad" in flags:
        action = "review_manual"
        reason = "Keyword mơ hồ/quá rộng — cần người xem quyết định, không tự phân loại."
    else:
        action = "low_priority"
        reason = "Ít tín hiệu nổi bật — để theo dõi thêm."

    return {"intent": intent, "suggested_page_type": page_type,
            "page_type_suggest": pt_suggest, "recommended_action": action,
            "reason": reason, "flags": flags}


def suggest_page_type(row: dict) -> str:
    """Wrapper tương thích ngược — dùng derive() làm nguồn chung."""
    return derive(row)["suggested_page_type"]


# ───────────────────────── upsert / queries ─────────────────────────

def upsert_keyword(conn, data: dict) -> str:
    """Upsert 1 keyword theo unique(normalized_keyword, source, country, language).
    Trả 'inserted' | 'updated'. Tự tính score + suggested_page_type nếu thiếu."""
    kw = (data.get("keyword") or "").strip()
    if not kw:
        return "skipped"
    norm = normalize_keyword(kw)
    source = (data.get("source") or "manual").strip() or "manual"
    country = (data.get("country") or DEFAULT_COUNTRY).strip() or DEFAULT_COUNTRY
    language = (data.get("language") or DEFAULT_LANGUAGE).strip() or DEFAULT_LANGUAGE

    existing = conn.execute(
        "SELECT * FROM seo_keyword_opportunities "
        "WHERE normalized_keyword=? AND source=? AND country=? AND language=?",
        (norm, source, country, language),
    ).fetchone()

    merged = dict(existing) if existing else {}
    # Cập nhật field có giá trị mới (None không ghi đè giá trị cũ).
    for k in ("volume", "keyword_difficulty", "cpc", "intent", "gsc_clicks",
              "gsc_impressions", "gsc_ctr", "gsc_position", "current_target_url",
              "topic_cluster", "priority", "notes"):
        v = data.get(k)
        if v is not None and v != "":
            merged[k] = v
    merged["keyword"] = kw
    merged["normalized_keyword"] = norm
    merged["source"] = source
    merged["country"] = country
    merged["language"] = language
    merged.setdefault("status", data.get("status") or "new")
    if data.get("suggested_page_type"):
        merged["suggested_page_type"] = data["suggested_page_type"]
    elif not merged.get("suggested_page_type"):
        merged["suggested_page_type"] = suggest_page_type(merged)

    score, _ = compute_score(merged)
    merged["opportunity_score"] = score

    now = _now()
    if existing:
        conn.execute(
            "UPDATE seo_keyword_opportunities SET "
            "keyword=?, volume=?, keyword_difficulty=?, cpc=?, intent=?, "
            "gsc_clicks=?, gsc_impressions=?, gsc_ctr=?, gsc_position=?, "
            "current_target_url=?, suggested_page_type=?, topic_cluster=?, "
            "opportunity_score=?, priority=?, status=?, notes=?, updated_at=? "
            "WHERE id=?",
            (merged.get("keyword"), merged.get("volume"), merged.get("keyword_difficulty"),
             merged.get("cpc"), merged.get("intent"), merged.get("gsc_clicks"),
             merged.get("gsc_impressions"), merged.get("gsc_ctr"), merged.get("gsc_position"),
             merged.get("current_target_url"), merged.get("suggested_page_type"),
             merged.get("topic_cluster"), merged.get("opportunity_score"),
             merged.get("priority"), merged.get("status"), merged.get("notes"),
             now, existing["id"]),
        )
        return "updated"
    conn.execute(
        "INSERT INTO seo_keyword_opportunities "
        "(keyword, normalized_keyword, source, source_row_id, volume, keyword_difficulty, "
        " cpc, intent, country, language, gsc_clicks, gsc_impressions, gsc_ctr, gsc_position, "
        " current_target_url, suggested_page_type, topic_cluster, opportunity_score, priority, "
        " status, notes, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (merged.get("keyword"), norm, source, data.get("source_row_id"),
         merged.get("volume"), merged.get("keyword_difficulty"), merged.get("cpc"),
         merged.get("intent"), country, language, merged.get("gsc_clicks"),
         merged.get("gsc_impressions"), merged.get("gsc_ctr"), merged.get("gsc_position"),
         merged.get("current_target_url"), merged.get("suggested_page_type"),
         merged.get("topic_cluster"), merged.get("opportunity_score"),
         merged.get("priority"), merged.get("status"), merged.get("notes"), now, now),
    )
    return "inserted"


def import_csv(text: str, source: str = "csv", filename: str = "",
               country: str = DEFAULT_COUNTRY, language: str = DEFAULT_LANGUAGE) -> dict:
    """Import keyword từ CSV text. Thiếu cột vẫn chạy. Dedup qua upsert.
    Trả {ok, imported, updated, skipped, batch_id}."""
    ensure_schema()
    # Hỗ trợ cả dấu phẩy & tab; sniff đơn giản.
    sample = text[:2048]
    delimiter = "\t" if (sample.count("\t") > sample.count(",")) else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        return {"ok": False, "error": "CSV rỗng / không có header"}

    # Map header → field nội bộ (case-insensitive, theo alias).
    header_map = {}
    for h in reader.fieldnames:
        key = (h or "").strip().lower()
        if key in _CSV_ALIASES:
            header_map[h] = _CSV_ALIASES[key]
        elif key in CSV_FIELDS:
            header_map[h] = key

    if "keyword" not in header_map.values():
        return {"ok": False,
                "error": "CSV không có cột keyword (chấp nhận: keyword/keywords/query/search term)"}

    imported = updated = skipped = 0
    conn = db.get_conn()
    try:
        for raw in reader:
            rec = {}
            for h, field in header_map.items():
                rec[field] = (raw.get(h) or "").strip()
            kw = rec.get("keyword", "").strip()
            if not kw:
                skipped += 1
                continue
            data = {
                "keyword": kw,
                "volume": _to_int(rec.get("volume")),
                "keyword_difficulty": _to_float(rec.get("keyword_difficulty")),
                "cpc": _to_float(rec.get("cpc")),
                "intent": _norm_intent(rec.get("intent")),
                "topic_cluster": rec.get("topic") or None,
                "notes": rec.get("note") or None,
                # source/country/language trong CSV (nếu có) ưu tiên hơn tham số.
                "source": rec.get("source") or source,
                "country": rec.get("country") or country,
                "language": rec.get("language") or language,
            }
            res = upsert_keyword(conn, data)
            if res == "inserted":
                imported += 1
            elif res == "updated":
                updated += 1
            else:
                skipped += 1
        cur = conn.execute(
            "INSERT INTO seo_keyword_import_batches "
            "(source, filename, imported_count, skipped_count, created_at, notes) "
            "VALUES (?,?,?,?,?,?)",
            (source, filename, imported, skipped, _now(),
             f"updated={updated}"),
        )
        batch_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "imported": imported, "updated": updated,
            "skipped": skipped, "batch_id": batch_id}


def sync_from_gsc(days: int = 90, min_impressions: int = 30, limit: int = 1000) -> dict:
    """Gom keyword từ gsc_queries_daily (data GSC thật) vào opportunity table.
    Aggregate theo query trong N ngày gần nhất. KD/volume để NULL (source=gsc)."""
    ensure_schema()
    conn = db.get_conn()
    try:
        # Có data không?
        have = conn.execute(
            "SELECT COUNT(*) c FROM sqlite_master WHERE type='table' AND name='gsc_queries_daily'"
        ).fetchone()
        if not have or not have["c"]:
            return {"ok": False, "error": "Chưa có bảng gsc_queries_daily (chưa sync GSC)"}
        rows = conn.execute(
            "SELECT query, "
            "       SUM(clicks) AS clicks, SUM(impressions) AS impressions, "
            "       CASE WHEN SUM(impressions)>0 THEN CAST(SUM(clicks) AS REAL)/SUM(impressions) ELSE 0 END AS ctr, "
            "       SUM(impressions*position)/NULLIF(SUM(impressions),0) AS position "
            "FROM gsc_queries_daily "
            "WHERE search_type='web' AND date >= date('now', ?) "
            "GROUP BY query "
            "HAVING SUM(impressions) >= ? "
            "ORDER BY SUM(impressions) DESC LIMIT ?",
            (f"-{int(days)} days", int(min_impressions), int(limit)),
        ).fetchall()
        imported = updated = 0
        for r in rows:
            data = {
                "keyword": r["query"],
                "source": "gsc",
                "gsc_clicks": _to_int(r["clicks"]),
                "gsc_impressions": _to_int(r["impressions"]),
                "gsc_ctr": round(r["ctr"], 4) if r["ctr"] is not None else None,
                "gsc_position": round(r["position"], 1) if r["position"] is not None else None,
            }
            res = upsert_keyword(conn, data)
            if res == "inserted":
                imported += 1
            elif res == "updated":
                updated += 1
        conn.execute(
            "INSERT INTO seo_keyword_import_batches "
            "(source, filename, imported_count, skipped_count, created_at, notes) "
            "VALUES (?,?,?,?,?,?)",
            ("gsc", f"gsc_last_{days}d", imported, 0, _now(), f"updated={updated}")
        )
        conn.commit()
        return {"ok": True, "imported": imported, "updated": updated, "scanned": len(rows)}
    finally:
        conn.close()


def list_keywords(source=None, intent=None, status=None, priority=None,
                  page_type=None, q=None, sort="score", limit=500) -> list[dict]:
    ensure_schema()
    conn = db.get_conn()
    sql = "SELECT * FROM seo_keyword_opportunities WHERE 1=1"
    args = []
    if source:
        sql += " AND source=?"; args.append(source)
    if intent:
        sql += " AND intent=?"; args.append(intent)
    if status:
        sql += " AND status=?"; args.append(status)
    if priority:
        sql += " AND priority=?"; args.append(priority)
    if page_type:
        sql += " AND suggested_page_type=?"; args.append(page_type)
    if q:
        sql += " AND keyword LIKE ?"; args.append(f"%{q}%")
    order = {"score": "opportunity_score DESC",
             "volume": "volume DESC",
             "impressions": "gsc_impressions DESC",
             "position": "gsc_position ASC",
             "keyword": "keyword ASC"}.get(sort, "opportunity_score DESC")
    sql += f" ORDER BY {order} LIMIT ?"
    args.append(int(limit))
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        # Derive-on-read: gắn gợi ý (KHÔNG ghi DB). intent/page_type_suggest để UI
        # hiển thị khi cột lưu còn trống; action/reason/flags luôn tính động.
        dv = derive(d)
        d["intent_suggest"] = dv["intent"]
        d["page_type_default"] = dv["suggested_page_type"]   # ổn định — fallback cho <select>
        d["page_type_suggest"] = dv["page_type_suggest"]     # động — badge (landing/service/support/"")
        d["recommended_action"] = dv["recommended_action"]
        d["reason"] = dv["reason"]
        d["flags"] = dv["flags"]
        out.append(d)
    return out


def count_keywords(source=None, intent=None, status=None, priority=None,
                   page_type=None, q=None) -> int:
    """Tổng số keyword khớp filter (bỏ qua limit) — để UI hiện shown/total."""
    ensure_schema()
    conn = db.get_conn()
    sql = "SELECT COUNT(*) c FROM seo_keyword_opportunities WHERE 1=1"
    args = []
    if source:
        sql += " AND source=?"; args.append(source)
    if intent:
        sql += " AND intent=?"; args.append(intent)
    if status:
        sql += " AND status=?"; args.append(status)
    if priority:
        sql += " AND priority=?"; args.append(priority)
    if page_type:
        sql += " AND suggested_page_type=?"; args.append(page_type)
    if q:
        sql += " AND keyword LIKE ?"; args.append(f"%{q}%")
    n = conn.execute(sql, args).fetchone()["c"]
    conn.close()
    return n


def get_keyword(kid: int) -> dict | None:
    ensure_schema()
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM seo_keyword_opportunities WHERE id=?", (kid,)).fetchone()
    conn.close()
    return dict(r) if r else None


def update_keyword_fields(kid: int, **fields) -> bool:
    """Cập nhật field cho phép từ UI: status, priority, suggested_page_type,
    topic_cluster, notes, intent. Recompute score sau khi đổi."""
    allowed = {"status", "priority", "suggested_page_type", "topic_cluster", "notes", "intent"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return False
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM seo_keyword_opportunities WHERE id=?", (kid,)).fetchone()
        if not row:
            return False
        merged = dict(row)
        merged.update(sets)
        score, _ = compute_score(merged)
        cols = ", ".join(f"{k}=?" for k in sets) + ", opportunity_score=?, updated_at=?"
        args = list(sets.values()) + [score, _now(), kid]
        conn.execute(f"UPDATE seo_keyword_opportunities SET {cols} WHERE id=?", args)
        conn.commit()
        return True
    finally:
        conn.close()


def keyword_stats() -> dict:
    ensure_schema()
    conn = db.get_conn()
    total = conn.execute("SELECT COUNT(*) c FROM seo_keyword_opportunities").fetchone()["c"]
    by_status = {r["status"]: r["c"] for r in conn.execute(
        "SELECT status, COUNT(*) c FROM seo_keyword_opportunities GROUP BY status")}
    by_source = {r["source"]: r["c"] for r in conn.execute(
        "SELECT source, COUNT(*) c FROM seo_keyword_opportunities GROUP BY source")}
    conn.close()
    return {"total": total, "by_status": by_status, "by_source": by_source}


# ───────────────────────── SERP extractor (an toàn) ─────────────────────────

# Stopword tiếng Việt + Anh tối thiểu để tìm common heading topics.
_STOP = set(
    "và là của có các một cho khi trong với được những này đó cũng để theo từ "
    "the a an of for to in on with and or is are how what why your you".split()
)


def _clean_soup(soup):
    """Bỏ noise không phải nội dung chính."""
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header",
                     "aside", "form", "svg", "iframe"]):
        tag.decompose()
    return soup


def fetch_serp_page(url: str, timeout: int = 12) -> dict:
    """Fetch 1 URL người dùng nhập, parse cấu trúc. KHÔNG follow link nội bộ,
    KHÔNG crawl site. Retry 0. Trả dict (luôn có fetch_status)."""
    import requests
    from bs4 import BeautifulSoup

    out = {"url": url, "title": None, "meta_description": None, "h1": None,
           "h2_json": "[]", "h3_json": "[]", "word_count": 0, "image_count": 0,
           "schema_types_json": "[]", "canonical_url": None,
           "fetch_status": "pending", "extracted_at": _now()}
    if not url or not url.lower().startswith(("http://", "https://")):
        out["fetch_status"] = "error: URL không hợp lệ"
        return out
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate",
               "Accept-Language": "vi,en;q=0.8"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    except Exception as e:
        out["fetch_status"] = f"error: {type(e).__name__}: {str(e)[:100]}"
        return out
    if r.status_code != 200:
        out["fetch_status"] = f"http {r.status_code}"
        return out
    try:
        soup = BeautifulSoup(r.content, "html.parser")
        # Title + meta description (lấy TRƯỚC khi strip).
        if soup.title and soup.title.string:
            out["title"] = soup.title.string.strip()[:300]
        md = soup.find("meta", attrs={"name": "description"})
        if md and md.get("content"):
            out["meta_description"] = md["content"].strip()[:400]
        can = soup.find("link", attrs={"rel": "canonical"})
        if can and can.get("href"):
            out["canonical_url"] = can["href"].strip()[:500]
        # Schema types (ld+json).
        schema_types = []
        for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(s.string or "")
            except Exception:
                continue
            for obj in (data if isinstance(data, list) else [data]):
                if isinstance(obj, dict):
                    t = obj.get("@type")
                    if isinstance(t, list):
                        schema_types.extend(str(x) for x in t)
                    elif t:
                        schema_types.append(str(t))
        out["schema_types_json"] = json.dumps(sorted(set(schema_types)), ensure_ascii=False)
        # Strip noise rồi mới lấy heading/word/image.
        soup = _clean_soup(soup)
        h1 = soup.find("h1")
        if h1:
            out["h1"] = h1.get_text(" ", strip=True)[:300]
        h2s = [h.get_text(" ", strip=True) for h in soup.find_all("h2")]
        h3s = [h.get_text(" ", strip=True) for h in soup.find_all("h3")]
        h2s = [x for x in h2s if x][:40]
        h3s = [x for x in h3s if x][:60]
        out["h2_json"] = json.dumps(h2s, ensure_ascii=False)
        out["h3_json"] = json.dumps(h3s, ensure_ascii=False)
        out["image_count"] = len(soup.find_all("img"))
        text = soup.get_text(" ", strip=True)
        out["word_count"] = len(text.split())
        out["fetch_status"] = "ok"
    except Exception as e:
        out["fetch_status"] = f"parse_error: {type(e).__name__}: {str(e)[:80]}"
    return out


def _common_headings(pages: list[dict], top_n: int = 15) -> list[dict]:
    """Đếm tần suất topic xuất hiện trong H2/H3 (đã chuẩn hoá), KHÔNG copy nguyên câu."""
    from collections import Counter
    cnt = Counter()
    examples: dict[str, str] = {}
    for p in pages:
        heads = json.loads(p.get("h2_json") or "[]") + json.loads(p.get("h3_json") or "[]")
        seen_in_page = set()
        for h in heads:
            norm = normalize_keyword(h)
            words = [w for w in re.findall(r"[0-9a-zA-ZÀ-ỹ]+", norm) if w not in _STOP and len(w) > 2]
            # token bậc 2 (bigram) để giữ chủ đề có nghĩa
            grams = words + [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
            for g in set(grams):
                if g in seen_in_page:
                    continue
                seen_in_page.add(g)
                cnt[g] += 1
                examples.setdefault(g, h[:80])
    out = []
    for term, c in cnt.most_common(top_n * 3):
        if c < 2:  # chỉ giữ topic xuất hiện ở ≥2 trang
            continue
        out.append({"topic": term, "pages": c, "example": examples.get(term, "")})
        if len(out) >= top_n:
            break
    return out


def analyze_serp(keyword: str, urls: list[str], source_mode: str = "manual",
                 keyword_id: int | None = None, timeout: int = 12) -> dict:
    """Mode A — Manual URLs: fetch 3-5 URL, trích cấu trúc, tổng hợp brief heuristic.
    Trả dict brief đã LƯU (kèm id). KHÔNG gọi AI ở bước này (AI là enhance riêng)."""
    ensure_schema()
    urls = [u.strip() for u in urls if u and u.strip()][:5]
    if not keyword or not keyword.strip():
        return {"ok": False, "error": "Thiếu keyword"}
    if not urls:
        return {"ok": False, "error": "Cần ít nhất 1 URL top SERP"}

    pages = [fetch_serp_page(u, timeout=timeout) for u in urls]
    ok_pages = [p for p in pages if p["fetch_status"] == "ok"]

    def _avg(key):
        vals = [p[key] for p in ok_pages if p.get(key)]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    avg_wc = _avg("word_count")
    avg_h2 = round(sum(len(json.loads(p["h2_json"])) for p in ok_pages) / len(ok_pages), 1) if ok_pages else 0.0
    avg_img = _avg("image_count")
    common = _common_headings(ok_pages)

    # Outline gợi ý heuristic: dựng từ common headings (chủ đề lặp ≥2 trang).
    outline = [{"h2": c["topic"], "from_pages": c["pages"]} for c in common[:8]]

    # Missing angles: heuristic — gợi nhắc góc Sintech nên có mà đối thủ ít đụng.
    missing = [
        "Góc trải nghiệm thực tế Sintech (đã lắp/đã test cho khách)",
        "Bảng so sánh nhanh + tư vấn chọn theo ngân sách",
        "FAQ ngắn trả lời ý định tìm kiếm phụ",
        "CTA tư vấn 1-1 (hotline/inbox) thay vì chỉ bán",
    ]

    title_opts = _heuristic_titles(keyword)
    meta_opts = _heuristic_metas(keyword)
    links = _heuristic_internal_links(keyword)
    risk = ("KHÔNG copy câu chữ đối thủ — chỉ lấy cấu trúc/độ dài/độ phủ topic. "
            "KHÔNG bịa giá/FPS/thông số. Viết theo giọng Sintech, thêm trải nghiệm thật. "
            "Tránh nhồi keyword. Title 45-60 ký tự (KHÔNG thêm 'Sintech'), meta 140-160 ký tự.")

    summary = [{
        "url": p["url"], "title": p.get("title"), "meta_description": p.get("meta_description"),
        "h1": p.get("h1"), "word_count": p.get("word_count"), "image_count": p.get("image_count"),
        "h2_count": len(json.loads(p.get("h2_json") or "[]")),
        "schema_types": json.loads(p.get("schema_types_json") or "[]"),
        "fetch_status": p.get("fetch_status"),
    } for p in pages]

    conn = db.get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO seo_serp_briefs "
            "(keyword_id, keyword, source_mode, serp_urls_json, competitor_summary_json, "
            " avg_word_count, avg_h2_count, avg_image_count, common_headings_json, "
            " missing_angles_json, recommended_outline_json, recommended_title_options_json, "
            " recommended_meta_options_json, internal_link_suggestions_json, risk_notes, "
            " status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (keyword_id, keyword.strip(), source_mode, json.dumps(urls, ensure_ascii=False),
             json.dumps(summary, ensure_ascii=False), avg_wc, avg_h2, avg_img,
             json.dumps(common, ensure_ascii=False), json.dumps(missing, ensure_ascii=False),
             json.dumps(outline, ensure_ascii=False), json.dumps(title_opts, ensure_ascii=False),
             json.dumps(meta_opts, ensure_ascii=False), json.dumps(links, ensure_ascii=False),
             risk, "new", _now(), _now()),
        )
        brief_id = cur.lastrowid
        for p in pages:
            conn.execute(
                "INSERT INTO seo_serp_pages "
                "(brief_id, url, title, meta_description, h1, h2_json, h3_json, "
                " word_count, image_count, schema_types_json, canonical_url, "
                " fetch_status, extracted_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (brief_id, p["url"], p.get("title"), p.get("meta_description"), p.get("h1"),
                 p.get("h2_json"), p.get("h3_json"), p.get("word_count"), p.get("image_count"),
                 p.get("schema_types_json"), p.get("canonical_url"), p.get("fetch_status"),
                 p.get("extracted_at")),
            )
        # keyword status → brief_ready nếu gắn keyword_id.
        if keyword_id:
            conn.execute(
                "UPDATE seo_keyword_opportunities SET status='brief_ready', updated_at=? "
                "WHERE id=? AND status IN ('new','review','approved')",
                (_now(), keyword_id))
        conn.commit()
    finally:
        conn.close()
    res = get_brief(brief_id)
    res["ok"] = True
    res["fetched"] = len(ok_pages)
    res["failed"] = len(pages) - len(ok_pages)
    return res


def _heuristic_titles(keyword: str) -> list[str]:
    kw = keyword.strip()
    cap = kw[:1].upper() + kw[1:] if kw else kw
    opts = [
        f"{cap}: hướng dẫn chi tiết & lưu ý quan trọng",
        f"{cap} — kinh nghiệm chọn đúng, tránh sai lầm",
        f"{cap}? Giải đáp nhanh từ chuyên gia",
    ]
    return [o[:60] for o in opts]


def _heuristic_metas(keyword: str) -> list[str]:
    kw = keyword.strip()
    opts = [
        f"Tất tần tật về {kw}: tiêu chí chọn, so sánh nhanh và lời khuyên thực tế giúp bạn quyết định đúng. Tư vấn 1-1 nếu cần.",
        f"Bạn đang tìm hiểu {kw}? Bài viết tổng hợp kinh nghiệm thực tế, các lỗi thường gặp và cách chọn phù hợp ngân sách.",
        f"{kw} — giải pháp & gợi ý từ đội ngũ Sintech, kèm trải nghiệm lắp đặt thực tế cho khách. Đọc để chọn không hối hận.",
    ]
    return [o[:160] for o in opts]


def _heuristic_internal_links(keyword: str) -> list[dict]:
    """Gợi ý anchor → để người viết tự gắn URL nội bộ phù hợp (KHÔNG auto-resolve)."""
    return [
        {"anchor": "bài liên quan cùng chủ đề", "note": "trỏ về pillar/cluster cùng topic"},
        {"anchor": "danh mục sản phẩm liên quan", "note": "trỏ collection phù hợp intent"},
        {"anchor": "hướng dẫn chi tiết", "note": "trỏ blog how-to nếu có"},
    ]


def get_brief(brief_id: int) -> dict | None:
    ensure_schema()
    conn = db.get_conn()
    b = conn.execute("SELECT * FROM seo_serp_briefs WHERE id=?", (brief_id,)).fetchone()
    if not b:
        conn.close()
        return None
    pages = conn.execute("SELECT * FROM seo_serp_pages WHERE brief_id=? ORDER BY id", (brief_id,)).fetchall()
    conn.close()
    d = dict(b)
    d["pages"] = [dict(p) for p in pages]
    return d


def list_briefs(limit: int = 100) -> list[dict]:
    ensure_schema()
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT id, keyword_id, keyword, source_mode, avg_word_count, avg_h2_count, "
        "avg_image_count, status, created_at FROM seo_serp_briefs ORDER BY id DESC LIMIT ?",
        (int(limit),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def ai_enhance_brief(brief_id: int) -> dict:
    """(Optional) Nhờ AI (Codex/Claude/Gemini CLI — KHÔNG phải API trả phí) viết lại
    outline + title/meta + unique angle dựa trên cấu trúc SERP đã trích. Fallback
    heuristic nếu hết quota. KHÔNG publish, chỉ ghi vào brief."""
    brief = get_brief(brief_id)
    if not brief:
        return {"ok": False, "error": "Không tìm thấy brief"}
    import ai_provider
    common = json.loads(brief.get("common_headings_json") or "[]")
    topics = ", ".join(c["topic"] for c in common[:12]) or "(không có)"
    sys_p = ("Bạn là chuyên gia SEO content tiếng Việt cho Sintech (PC gaming & gear). "
             "Chỉ dùng CẤU TRÚC/chủ đề từ SERP để gợi ý khung bài, KHÔNG copy câu chữ đối thủ, "
             "KHÔNG bịa giá/thông số/FPS. Trả về JSON.")
    user_p = (
        f"Keyword chính: {brief['keyword']}\n"
        f"Độ dài TB đối thủ: {brief.get('avg_word_count')} từ, {brief.get('avg_h2_count')} H2.\n"
        f"Chủ đề lặp lại nhiều trên SERP: {topics}\n\n"
        "Tạo JSON gồm các khoá:\n"
        '  "outline": [{"h2": "...", "h3": ["..."]}],  // 6-9 mục H2, bám chủ đề trên\n'
        '  "title_options": ["...","...","..."],  // 3 title ≤60 ký tự, KHÔNG chứa "Sintech"\n'
        '  "meta_options": ["...","...","..."],   // 3 meta 140-160 ký tự\n'
        '  "unique_angle": "góc khác biệt Sintech nên khai thác",\n'
        '  "faq": ["câu hỏi 1","câu hỏi 2","câu hỏi 3"]\n'
        "Chỉ trả JSON thuần, không giải thích."
    )
    try:
        raw = ai_provider.call_ai(sys_p, user_p, timeout=120, reasoning_effort="low")
    except ai_provider.AIQuotaError as e:
        return {"ok": False, "error": f"AI hết quota: {str(e)[:120]}", "quota": True}
    except Exception as e:
        return {"ok": False, "error": f"AI lỗi: {str(e)[:120]}"}

    parsed = _extract_json(raw)
    if not parsed:
        return {"ok": False, "error": "AI trả về không phải JSON hợp lệ"}

    conn = db.get_conn()
    try:
        outline = parsed.get("outline")
        titles = parsed.get("title_options")
        metas = parsed.get("meta_options")
        sets, args = [], []
        if outline:
            sets.append("recommended_outline_json=?"); args.append(json.dumps(outline, ensure_ascii=False))
        if titles:
            sets.append("recommended_title_options_json=?"); args.append(json.dumps(titles, ensure_ascii=False))
        if metas:
            sets.append("recommended_meta_options_json=?"); args.append(json.dumps(metas, ensure_ascii=False))
        # gộp unique_angle + faq vào missing_angles_json để hiển thị.
        extra = []
        if parsed.get("unique_angle"):
            extra.append("Góc Sintech: " + str(parsed["unique_angle"]))
        for q in (parsed.get("faq") or []):
            extra.append("FAQ: " + str(q))
        if extra:
            sets.append("missing_angles_json=?"); args.append(json.dumps(extra, ensure_ascii=False))
        if sets:
            sets.append("status=?"); args.append("ai_enhanced")
            sets.append("updated_at=?"); args.append(_now())
            args.append(brief_id)
            conn.execute(f"UPDATE seo_serp_briefs SET {', '.join(sets)} WHERE id=?", args)
            conn.commit()
    finally:
        conn.close()
    res = get_brief(brief_id)
    res["ok"] = True
    return res


def _extract_json(raw: str):
    """Lấy object JSON đầu tiên trong text (AI hay bọc ```json)."""
    if not raw:
        return None
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


# ───────────────────────── exports ─────────────────────────

def export_keywords_csv() -> str:
    rows = list_keywords(limit=100000)
    cols = ["id", "keyword", "source", "intent", "intent_suggest", "volume",
            "keyword_difficulty", "cpc", "gsc_clicks", "gsc_impressions", "gsc_ctr",
            "gsc_position", "suggested_page_type", "page_type_suggest",
            "recommended_action", "reason", "flags", "opportunity_score", "priority",
            "status", "topic_cluster", "country", "language", "notes", "updated_at"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        row = dict(r)
        row["flags"] = "|".join(row.get("flags") or [])
        w.writerow([row.get(c, "") for c in cols])
    return buf.getvalue()


def brief_to_markdown(brief_id: int) -> str:
    b = get_brief(brief_id)
    if not b:
        return "# Brief không tồn tại"
    out = [f"# Content Brief — {b['keyword']}", ""]
    out.append(f"- **Source mode**: {b.get('source_mode')}")
    out.append(f"- **Avg đối thủ**: {b.get('avg_word_count')} từ · {b.get('avg_h2_count')} H2 · {b.get('avg_image_count')} ảnh")
    out.append("")
    out.append("## Outline đề xuất (H2/H3)")
    for o in json.loads(b.get("recommended_outline_json") or "[]"):
        if isinstance(o, dict):
            out.append(f"- **{o.get('h2','')}**")
            for h3 in (o.get("h3") or []):
                out.append(f"  - {h3}")
    out.append("")
    out.append("## 3 Title options (≤60 ký tự, KHÔNG 'Sintech')")
    for t in json.loads(b.get("recommended_title_options_json") or "[]"):
        out.append(f"- {t}  ({len(t)} ký tự)")
    out.append("")
    out.append("## 3 Meta options (140-160 ký tự)")
    for m in json.loads(b.get("recommended_meta_options_json") or "[]"):
        out.append(f"- {m}  ({len(m)} ký tự)")
    out.append("")
    out.append("## Góc khác biệt / FAQ nên có")
    for a in json.loads(b.get("missing_angles_json") or "[]"):
        out.append(f"- {a}")
    out.append("")
    out.append("## Internal link gợi ý")
    for l in json.loads(b.get("internal_link_suggestions_json") or "[]"):
        if isinstance(l, dict):
            out.append(f"- `{l.get('anchor','')}` — {l.get('note','')}")
    out.append("")
    out.append("## Chủ đề lặp trên SERP (inspired-by, KHÔNG copy)")
    for c in json.loads(b.get("common_headings_json") or "[]"):
        out.append(f"- {c.get('topic','')} (xuất hiện {c.get('pages')} trang)")
    out.append("")
    out.append("## Risk notes")
    out.append(b.get("risk_notes") or "")
    return "\n".join(out)
