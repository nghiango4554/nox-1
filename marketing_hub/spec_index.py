"""Spec Index — kho mô tả + thông số SP, phục vụ tab "Thông số SP" trên marketing hub.

Ba việc:
1. `scan_products()`  — kéo SP live từ Haravan → phân loại tình trạng (new/cũ/tray) +
   DẠNG HIỂN THỊ SPEC → lưu bảng `product_spec_index`.
2. `scan_menu()`      — bóc danh sách collection LÁ đang hiện trên menu live sintech.vn
   (chỉ lấy nhánh sâu nhất, bỏ collection mẹ) → bảng `spec_menu_collections`,
   rồi map SP vào nhóm → bảng `spec_group_products`.
3. Chuyển đổi khối spec: blockquote ↔ bảng HTML, và bóc cặp Nhãn↔giá trị.

🔑 CƠ CHẾ RENDER (xác minh live 22/7/2026 trên 15 SP):
   Theme CHỈ bốc khối `<blockquote>` NẰM Ở ĐUÔI body_html vào khung "Thông số kỹ thuật"
   riêng (nút "Xem tất cả thông số kỹ thuật"). Thẻ blockquote bị gỡ khỏi phần mô tả.
   → Đó là dạng ĐÚNG. Spec để dạng <table> / <ul> thường / văn xuôi đều KHÔNG lên khung đó.
"""

import html as htmllib
import json
import re
import sqlite3
import time
from datetime import datetime

import requests

import db
import haravan_client as hc

STORE_URL = "https://sintech.vn"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

FMT_A = "A_BLOCKQUOTE"          # đúng chuẩn: blockquote ở đuôi
FMT_A_LAC = "A_BLOCKQUOTE_LAC"  # có blockquote nhưng KHÔNG ở đuôi → theme không bốc
FMT_B = "B_TABLE"
FMT_B2 = "B2_BANG_CAU_HINH"
FMT_C = "C_LIST_UL"
FMT_D = "D_VAN_XUOI"
FMT_E = "E_KHONG_CO_SPEC"
FMT_F = "F_BODY_RONG"

# Vợ chốt 22/7: trang DỊCH VỤ / SỬA CHỮA không cần khối thông số → loại khỏi phạm vi.
SERVICE_COLLECTIONS = (
    "dich-vu-sua-chua", "dich-vu-ve-sinh-pc", "ve-sinh-pc-tai-cua-hang", "ve-sinh-pc-tan-nha",
    "ve-sinh-laptop", "sua-chua-may-tinh", "nang-cap-pc", "cai-dat-windows-phan-mem",
    "sua-chua-pc-laptop",
)
SERVICE_TYPE = re.compile(r"(?i)sửa chữa|dịch vụ|vệ sinh")

FMT_LABEL = {
    FMT_A:     ("Khối trích dẫn ở đuôi", "ĐÚNG"),
    FMT_A_LAC: ("Khối trích dẫn nhưng KHÔNG ở đuôi", "SAI"),
    FMT_B:     ("Bảng thông số HTML", "SAI"),
    FMT_B2:    ("Bảng cấu hình (combo/máy bộ)", "KHUÔN RIÊNG"),
    FMT_C:     ("Danh sách gạch đầu dòng", "SAI"),
    FMT_D:     ("Văn xuôi", "SAI"),
    FMT_E:     ("Không có khối thông số", "SAI"),
    FMT_F:     ("Mô tả rỗng", "SAI"),
}

# ───────────────────────── regex nhận diện ─────────────────────────
CU = re.compile(r"(?i)(?<![a-zà-ỹ])cũ(?![a-zà-ỹ])")
TRAY = re.compile(r"(?i)\btray\b")
QSD = re.compile(r"(?i)\bqsd\b")
KHO_ANH = re.compile(r"(?i)kho ảnh")
BQ = re.compile(r"(?is)<blockquote.*?</blockquote>")
TABLE = re.compile(r"(?is)<table.*?</table>")
TR = re.compile(r"(?is)<tr[^>]*>(.*?)</tr>")
CELL = re.compile(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>")
LI = re.compile(r"(?is)<li[^>]*>(.*?)</li>")
HEAD = re.compile(r"(?is)<h[2-5][^>]*>(.*?)</h[2-5]>")
SPEC_WORD = re.compile(r"(?i)thông số|thông tin hàng ho|thông tin chung|spec")
# Bẫy 22/7: r"(đ|vnđ)" khớp luôn chữ "đơn vị" → phải chặn hết từ.
MONEY = re.compile(r"(?i)\d[\d\.,]{4,}\s*(đ|vnđ|vnd)(?![\wà-ỹ])")
WARRANTY = re.compile(r"(?i)^bảo hành")
CONDITION_ROW = re.compile(r"(?i)^tình trạng")
# nhãn dính GIÁ ở bất kỳ đâu: "Giá đang hiển thị", "Giá niêm yết", "Khuyến mãi"…
PRICE_KEY = re.compile(r"(?i)\bgiá(?!\s*(trị|đỡ|treo|lắp|kê|sách|nâng))\b|khuyến mãi|niêm yết")
# Bẫy 22/7: <table> trong mô tả đa số là bảng SO SÁNH / TƯ VẤN, không phải bảng spec.
ADVISORY_HEAD = re.compile(
    r"(?i)nhu cầu|tình huống|đối tượng|ai nên|trường hợp|mức độ phù hợp|tiêu chí"
    r"|cần kiểm tra|vì sao|lý do|ý nghĩa|gợi ý|lưu ý|điểm cần|bạn định làm"
    r"|trải nghiệm|có phù hợp|nên chọn|khi nào")
ADVISORY_VAL = re.compile(r"(?i)^(rất )?phù hợp|^không phù hợp|^nên |^cần |^chưa |^có$|^không$")
CONFIG_HEAD = re.compile(r"(?i)^stt$")
SPEC_HEAD = re.compile(r"(?i)^(hạng mục|thông số|thông tin|đặc điểm|thuộc tính|chi tiết)")
# bảng DÀN Ý bài viết (Cấp heading | Nội dung → H2/H3) — không phải thông số
OUTLINE_HEAD = re.compile(r"(?i)^(cấp heading|heading|cấu trúc bài|dàn ý)")
OUTLINE_VAL = re.compile(r"(?i)^h[1-4]$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS product_spec_index (
    haravan_id      INTEGER PRIMARY KEY,
    handle          TEXT,
    title           TEXT,
    product_type    TEXT,
    vendor          TEXT,
    tags            TEXT,
    condition_kind  TEXT,
    published       INTEGER,
    spec_format     TEXT,
    pair_count      INTEGER,
    group_count     INTEGER,
    issue_count     INTEGER,
    issues_json     TEXT,
    spec_pairs_json TEXT,
    spec_groups_json TEXT,
    spec_block_html TEXT,
    has_bq_spec     INTEGER,
    has_table_spec  INTEGER,
    body_len        INTEGER,
    body_html       TEXT,
    image_src       TEXT,
    is_service      INTEGER DEFAULT 0,
    updated_at_haravan TEXT,
    scanned_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_psi_fmt ON product_spec_index(spec_format);
CREATE INDEX IF NOT EXISTS idx_psi_cond ON product_spec_index(condition_kind);
CREATE INDEX IF NOT EXISTS idx_psi_type ON product_spec_index(product_type);

CREATE TABLE IF NOT EXISTS spec_menu_collections (
    handle      TEXT,
    tag_filter  TEXT,
    title       TEXT,
    parent      TEXT,
    root        TEXT,
    sort_order  INTEGER,
    collection_id INTEGER,
    product_count INTEGER DEFAULT 0,
    new_count     INTEGER DEFAULT 0,
    ok_count      INTEGER DEFAULT 0,
    scanned_at  TEXT,
    PRIMARY KEY (handle, tag_filter)
);

CREATE TABLE IF NOT EXISTS spec_sync_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT,      -- product | collection
    actor       TEXT,      -- vo | nox
    haravan_id  INTEGER,
    handle      TEXT,
    tag_filter  TEXT DEFAULT '',
    title       TEXT,
    spec_format TEXT,
    pair_count  INTEGER,
    note        TEXT,
    created_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_log_actor ON spec_sync_log(actor, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_log_kind ON spec_sync_log(kind);

CREATE TABLE IF NOT EXISTS spec_research_source (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    haravan_id  INTEGER,
    url         TEXT,
    page_title  TEXT,
    n_rows      INTEGER,
    rows_json   TEXT,
    status      TEXT,      -- dung | bo_qua
    reason      TEXT,
    created_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_src_pid ON spec_research_source(haravan_id);

CREATE TABLE IF NOT EXISTS spec_group_products (
    handle      TEXT,
    tag_filter  TEXT,
    haravan_id  INTEGER,
    PRIMARY KEY (handle, tag_filter, haravan_id)
);
CREATE INDEX IF NOT EXISTS idx_sgp_pid ON spec_group_products(haravan_id);

-- View nhanh (23/7): bản spec đã gộp + vợ sửa tay, LƯU DB, KHÔNG tự đẩy lên web
-- ⚠️ KHÔNG đặt tên cột là `excluded`: đó là từ khoá của SQLite trong câu UPSERT
-- (`ON CONFLICT ... SET x = excluded.x`) → tự đá nhau. Dùng `skip_review`.
CREATE TABLE IF NOT EXISTS spec_quick_draft (
    haravan_id  INTEGER PRIMARY KEY,
    rows_json   TEXT,       -- [[nhãn, giá trị], ...] bản cuối vợ chốt
    skip_review INTEGER DEFAULT 0,   -- 1 = loại khỏi danh sách duyệt, KHÔNG sync
    note        TEXT,
    saved_at    TEXT
);

-- SP có thông số SAI trong mô tả (đối chiếu trang hãng bằng Chrome).
-- 1 dòng = 1 chỉ tiêu sai. Hiện ở tab đỏ "SP sai spec" trong nhật ký /spec.
CREATE TABLE IF NOT EXISTS spec_error_note (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    haravan_id  INTEGER,
    handle      TEXT,
    title       TEXT,
    label       TEXT,       -- tên chỉ tiêu sai (vd: Độ phân giải)
    wrong_value TEXT,       -- giá trị đang có trong body
    correct_value TEXT,     -- giá trị đúng theo hãng
    source      TEXT,       -- nguồn hãng đã đối chiếu
    note        TEXT,       -- ghi chú thêm
    status      TEXT DEFAULT 'open',   -- open | fixed
    created_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_errnote_pid ON spec_error_note(haravan_id);
"""


def init_schema():
    conn = db.get_conn()
    # bảng bản nháp 22/7 thiếu cột image_src → bỏ đi tạo lại (dữ liệu quét lại được)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(product_spec_index)")]
        if cols and "image_src" not in cols:
            conn.execute("DROP TABLE product_spec_index")
        elif cols and "is_service" not in cols:   # thêm cột, KHÔNG xoá dữ liệu đã quét
            conn.execute("ALTER TABLE product_spec_index ADD COLUMN is_service INTEGER DEFAULT 0")
        if cols and "skipped" not in cols:
            conn.execute("ALTER TABLE product_spec_index ADD COLUMN skipped INTEGER DEFAULT 0")
    except sqlite3.Error:
        pass
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


# ───────────────────────── tiện ích HTML ─────────────────────────

def strip_tags(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"[ \t ]+", " ", htmllib.unescape(s)).strip()


def parse_table_rows(fragment: str):
    rows = []
    for tr in TR.findall(fragment or ""):
        cells = [strip_tags(c) for c in CELL.findall(tr)]
        if cells:
            rows.append(cells)
    return rows


def table_kind(fragment: str) -> str:
    """Bảng này dùng để làm gì: spec | cauhinh | tuvan | sosanh | khac."""
    rows = parse_table_rows(fragment)
    if len(rows) < 2:
        return "khac"
    head = rows[0]
    if CONFIG_HEAD.search(head[0]):
        return "cauhinh"
    left_all = [r[0].strip() for r in rows if r and r[0].strip()]
    if OUTLINE_HEAD.search(head[0]) or \
            sum(bool(OUTLINE_VAL.match(k)) for k in left_all) >= max(2, len(left_all) * 0.4):
        return "danyy"
    if len(head) >= 3:
        return "sosanh"
    if ADVISORY_HEAD.search(head[0]) or ADVISORY_HEAD.search(head[-1]):
        return "tuvan"
    right = [r[1] for r in rows[1:] if len(r) >= 2]
    if right and sum(bool(ADVISORY_VAL.match(v)) for v in right) >= len(right) * 0.5:
        return "tuvan"
    # giá trị là CÂU VĂN dài (>45 ký tự) quá nửa bảng → bảng tư vấn/trải nghiệm, không phải spec
    if right and sum(1 for v in right if len(v) > 45) >= len(right) * 0.5:
        return "tuvan"
    if SPEC_HEAD.search(head[0]):
        return "spec"
    left = [r[0] for r in rows if len(r) >= 2]
    if left and sum(1 for k in left if len(k) <= 28) >= len(left) * 0.7:
        return "spec"
    return "khac"


def parse_pairs(fragment: str):
    """Bóc cặp Nhãn↔giá trị + tên nhóm từ khối spec (blockquote hoặc ul)."""
    pairs, bad = [], 0
    items = LI.findall(fragment or "")
    if not items:
        items = re.findall(r"(?is)<p[^>]*>(.*?)</p>", fragment or "")
    for it in items:
        t = strip_tags(it)
        if not t:
            continue
        m = re.match(r"^([^:：]{1,60})[:：]\s*(.*)$", t)
        if m:
            pairs.append([m.group(1).strip(" -•*"), m.group(2).strip()])
        else:
            bad += 1
    groups = [strip_tags(h) for h in HEAD.findall(fragment or "")]
    if not groups:
        groups = [strip_tags(s) for s in re.findall(
            r"(?is)<p[^>]*>\s*<strong[^>]*>(.*?)</strong>\s*</p>", fragment or "")]
    return pairs, [g for g in groups if g], bad


# ───────────────────── dựng lại khối spec ─────────────────────
LI_STYLE = "font-size: 16px; line-height: 1.6;"
P_STYLE = "font-size: 16px; line-height: 1.65;"
TB_STYLE = ("width:100%;border-collapse:collapse;font-size:14px;"
            "margin:12px 0;border:1px solid #e5e7eb")
TH_STYLE = ("padding:10px;background:#f3f4f6;text-align:left;font-weight:700;"
            "border:1px solid #e5e7eb")
TD_STYLE = "padding:10px;border:1px solid #e5e7eb;vertical-align:top"


def _esc(s):
    return htmllib.escape(s or "", quote=False)


def build_blockquote(groups: list) -> str:
    """groups = [{"name": "Thông tin hàng hóa", "rows": [[k, v], ...]}, ...] → blockquote."""
    out = ["<blockquote>"]
    for g in groups:
        rows = [r for r in g.get("rows", []) if (r[0] or "").strip()]
        if not rows:
            continue
        if (g.get("name") or "").strip():
            out.append(f'<p style="{P_STYLE}"><strong>{_esc(g["name"].strip())}</strong></p>')
        out.append("<ul>")
        for k, v in rows:
            out.append(f'<li style="{LI_STYLE}"><strong>{_esc(k.strip())}:</strong> {_esc(v.strip())}</li>')
        out.append("</ul>")
    out.append("</blockquote>")
    return "\n".join(out)


def build_table(groups: list) -> str:
    """Cùng dữ liệu nhưng dựng thành <table> 2 cột (nhóm = dòng gộp)."""
    out = [f'<table style="{TB_STYLE}"><tbody>']
    for g in groups:
        rows = [r for r in g.get("rows", []) if (r[0] or "").strip()]
        if not rows:
            continue
        if (g.get("name") or "").strip():
            out.append(f'<tr><th colspan="2" style="{TH_STYLE}">{_esc(g["name"].strip())}</th></tr>')
        for k, v in rows:
            out.append(f'<tr><td style="{TD_STYLE};width:32%;font-weight:600">{_esc(k.strip())}</td>'
                       f'<td style="{TD_STYLE}">{_esc(v.strip())}</td></tr>')
    out.append("</tbody></table>")
    return "\n".join(out)


def block_to_groups(fragment: str) -> list:
    """Bóc khối spec (blockquote hoặc table) → [{name, rows}] để đổ vào form sửa."""
    fragment = fragment or ""
    groups = []
    if re.search(r"(?i)<table", fragment):
        cur = {"name": "", "rows": []}
        for row in parse_table_rows(fragment):
            if len(row) == 1:
                if cur["rows"]:
                    groups.append(cur)
                cur = {"name": row[0], "rows": []}
            elif len(row) >= 2:
                if SPEC_HEAD.search(row[0]) and not cur["rows"] and not cur["name"]:
                    continue  # dòng tiêu đề "Hạng mục | Thông tin"
                cur["rows"].append([row[0], row[1]])
        if cur["rows"] or cur["name"]:
            groups.append(cur)
        return groups

    # blockquote / ul: nhóm = <p><strong> hoặc heading, dòng = <li>
    parts = re.split(r"(?is)(<p[^>]*>\s*<strong[^>]*>.*?</strong>\s*</p>|<h[2-5][^>]*>.*?</h[2-5]>)",
                     fragment)
    cur = {"name": "", "rows": []}
    for part in parts:
        if not part or not part.strip():
            continue
        if re.match(r"(?is)^\s*(<p[^>]*>\s*<strong|<h[2-5])", part):
            if cur["rows"]:
                groups.append(cur)
            cur = {"name": strip_tags(part), "rows": []}
        else:
            pr, _, _ = parse_pairs(part)
            cur["rows"].extend(pr)
    if cur["rows"] or cur["name"]:
        groups.append(cur)
    return [g for g in groups if g["rows"]]


def replace_spec_block(body_html: str, new_block: str, old_block: str = "") -> str:
    """Gỡ khối spec cũ rồi gắn khối mới vào ĐUÔI body.

    Phải gỡ được CẢ 3 kiểu khối cũ (blockquote / bảng thông số / <ul> danh sách),
    nếu không thì SP dạng danh sách sẽ bị lặp thông số ở 2 chỗ sau khi duyệt.
    """
    body = body_html or ""
    removed = False

    # 1) khớp đúng chuỗi khối cũ đã dò được lúc quét
    ob = (old_block or "").strip()
    if ob and ob in body:
        body = body.replace(ob, "", 1)
        removed = True
    elif ob:
        # HTML có thể lệch khoảng trắng → so bản đã nén khoảng trắng
        squash = re.compile(r"\s+")
        target = squash.sub(" ", ob)
        for m in list(BQ.finditer(body)) + list(TABLE.finditer(body)) + \
                list(re.finditer(r"(?is)<ul.*?</ul>", body)):
            if squash.sub(" ", m.group(0)) == target:
                body = body[:m.start()] + body[m.end():]
                removed = True
                break

    # 2) không có old_block (hoặc body đã bị sửa tay) → dò lại theo nội dung
    if not removed:
        for m in reversed(list(BQ.finditer(body))):
            if len(parse_pairs(m.group(0))[0]) >= 4:
                body = body[:m.start()] + body[m.end():]
                removed = True
                break
    if not removed:
        for m in reversed(list(TABLE.finditer(body))):
            if table_kind(m.group(0)) == "spec":
                body = body[:m.start()] + body[m.end():]
                removed = True
                break
    return body.rstrip() + "\n" + (new_block or "").strip()


# ───────────────────────── phân loại ─────────────────────────

COLS = ("haravan_id,handle,title,product_type,vendor,tags,condition_kind,published,spec_format,"
        "pair_count,group_count,issue_count,issues_json,spec_pairs_json,spec_groups_json,"
        "spec_block_html,has_bq_spec,has_table_spec,body_len,body_html,image_src,is_service,"
        "updated_at_haravan,scanned_at")
INSERT_SQL = (f"INSERT OR REPLACE INTO product_spec_index ({COLS}) VALUES ("
              + ",".join(["?"] * len(COLS.split(","))) + ")")


def mark_services(conn=None) -> int:
    """Gắn cờ SP dịch vụ/sửa chữa: theo collection dịch vụ HOẶC theo loại SP."""
    own = conn is None
    conn = conn or db.get_conn()
    q = ",".join("?" * len(SERVICE_COLLECTIONS))
    conn.execute(f"""UPDATE product_spec_index SET is_service = 1 WHERE haravan_id IN
        (SELECT haravan_id FROM spec_group_products WHERE handle IN ({q}))""", SERVICE_COLLECTIONS)
    conn.execute("""UPDATE product_spec_index SET is_service = 1
        WHERE product_type LIKE '%ửa chữa%' OR product_type LIKE '%ịch vụ%'
           OR product_type LIKE '%ệ sinh%' OR title LIKE 'Dịch vụ%' OR title LIKE 'Combo vệ sinh%'""")
    n = conn.execute("SELECT COUNT(*) FROM product_spec_index WHERE is_service=1").fetchone()[0]
    conn.commit()
    if own:
        conn.close()
    return n


def condition_of(p: dict) -> str:
    if (p.get("product_type") or "") == "ASSET_STORAGE" or KHO_ANH.search(p.get("title") or ""):
        return "kho_anh"
    f = [p.get("title") or "", p.get("product_type") or "", p.get("tags") or ""]
    if any(CU.search(x) for x in f):
        return "cu"
    if any(TRAY.search(x) for x in f):
        return "tray"
    if QSD.search(p.get("title") or ""):
        return "qsd"
    return "new"


def classify_body(p: dict) -> dict:
    body = p.get("body_html") or ""
    issues = []
    if not body.strip():
        return dict(fmt=FMT_F, block="", pairs=[], groups=[], issues=["body_html rỗng"],
                    has_bq=0, has_table=0)

    bqs = list(BQ.finditer(body))
    tables = TABLE.findall(body)
    kinds = [table_kind(t) for t in tables]
    spec_tables = [t for t, k in zip(tables, kinds) if k == "spec"]
    config_tables = [t for t, k in zip(tables, kinds) if k == "cauhinh"]

    best, best_pairs, best_groups, best_bad, best_m = "", [], [], 0, None
    for m in bqs:
        pr, gr, bad = parse_pairs(m.group(0))
        if len(pr) > len(best_pairs):
            best, best_pairs, best_groups, best_bad, best_m = m.group(0), pr, gr, bad, m

    has_bq_spec = len(best_pairs) >= 4
    has_table_spec = bool(spec_tables)

    if has_bq_spec:
        tail_gap = len(strip_tags(body[best_m.end():]))
        fmt = FMT_A if tail_gap == 0 else FMT_A_LAC
        block, pairs, groups = best, best_pairs, best_groups
        if fmt == FMT_A_LAC:
            issues.append(f"khối trích dẫn KHÔNG ở đuôi (còn {tail_gap} ký tự phía sau) "
                          f"→ theme không bốc vào khung Thông số")
        if best_bad >= 3:
            issues.append(f"{best_bad} dòng trong khối spec không tách được Nhãn: giá trị")
        if has_table_spec:
            issues.append("spec xuất hiện 2 chỗ (khối trích dẫn + bảng thông số)")
    elif spec_tables or config_tables:
        block = (spec_tables or config_tables)[0]
        rows = parse_table_rows(block)
        pairs = [r[:2] for r in rows if len(r) >= 2]
        groups = []
        fmt = FMT_B if spec_tables else FMT_B2
    elif re.search(r"(?is)<ul.*?</ul>", body) and SPEC_WORD.search(strip_tags(body)):
        fmt = FMT_C
        block = ""
        m = re.search(r"(?is)<h[1-5][^>]*>[^<]*thông số.*?</h[1-5]>(.*?)(<h[1-5]|$)", body)
        if m:
            m2 = re.search(r"(?is)<ul.*?</ul>", m.group(1))
            block = m2.group(0) if m2 else ""
        if not block:
            cands = re.findall(r"(?is)<ul.*?</ul>", body)
            block = max(cands, key=lambda u: len(parse_pairs(u)[0]), default="")
        pairs, groups, _ = parse_pairs(block)
    elif SPEC_WORD.search(strip_tags(body)):
        fmt, block, pairs, groups = FMT_D, "", [], []
    else:
        fmt, block, pairs, groups = FMT_E, "", [], []

    keys = [k.strip().lower() for k, _ in pairs]
    if fmt != FMT_B2:
        if any(WARRANTY.search(k) for k in keys):
            issues.append("khối spec còn dòng Bảo hành (đã bị cấm)")
        if any(CONDITION_ROW.search(k) for k in keys):
            issues.append("khối spec còn dòng Tình trạng (đã bị cấm)")
        if any(MONEY.search(v) for _, v in pairs) or any(PRICE_KEY.search(k) for k in keys):
            issues.append("khối spec có dấu hiệu chứa GIÁ")
        if any(not v.strip() for _, v in pairs):
            issues.append("có dòng spec bỏ trống giá trị")
    if fmt in (FMT_B, FMT_C, FMT_D, FMT_E):
        issues.append("spec không nằm trong khối trích dẫn ở đuôi → không lên khung Thông số")
    if fmt not in (FMT_D, FMT_E, FMT_F) and len(pairs) < 6:
        issues.append(f"khối spec chỉ có {len(pairs)} dòng (mỏng)")
    if len(body) < 2000:
        issues.append(f"mô tả ngắn ({len(body)} ký tự)")

    return dict(fmt=fmt, block=block, pairs=pairs, groups=groups, issues=issues,
                has_bq=int(has_bq_spec), has_table=int(has_table_spec))


# ───────────────────────── quét SP ─────────────────────────
FIELDS = ("id,handle,title,vendor,product_type,tags,body_html,published_at,"
          "updated_at,images")


def fetch_all_products(log=print) -> list:
    """Kéo toàn bộ SP live. Bẫy: API trả 50 SP/trang dù limit=250."""
    out, seen, page = [], set(), 1
    while page <= 200:
        for attempt in range(3):
            try:
                batch = hc.list_products(page=page, limit=250, fields=FIELDS)
                break
            except Exception as e:  # noqa: BLE001
                log(f"  trang {page} lỗi lần {attempt+1}: {e}")
                time.sleep(3)
        else:
            raise RuntimeError(f"Không kéo được trang {page}")
        if not batch:
            break
        new = 0
        for p in batch:
            if p["id"] not in seen:
                seen.add(p["id"])
                out.append(p)
                new += 1
        if new == 0:
            break
        page += 1
        time.sleep(0.2)
    return out


def scan_products(log=print) -> dict:
    init_schema()
    products = fetch_all_products(log)
    log(f"Đã kéo {len(products)} SP live")
    now = datetime.now().isoformat(timespec="seconds")
    rows = []
    for p in products:
        cond = condition_of(p)
        c = (classify_body(p) if cond == "new"
             else dict(fmt="", block="", pairs=[], groups=[], issues=[], has_bq=0, has_table=0))
        imgs = p.get("images") or []
        rows.append((
            p["id"], p.get("handle"), p.get("title"), p.get("product_type"), p.get("vendor"),
            p.get("tags"), cond, 1 if p.get("published_at") else 0,
            c["fmt"], len(c["pairs"]), len(c["groups"]), len(c["issues"]),
            json.dumps(c["issues"], ensure_ascii=False),
            json.dumps(c["pairs"], ensure_ascii=False),
            json.dumps(c["groups"], ensure_ascii=False),
            c["block"], c["has_bq"], c["has_table"],
            len(p.get("body_html") or ""), p.get("body_html") or "",
            (imgs[0].get("src") if imgs else None),
            1 if SERVICE_TYPE.search(p.get("product_type") or "") else 0,
            p.get("updated_at"), now,
        ))
    conn = db.get_conn()
    # INSERT OR REPLACE thay CẢ DÒNG → cột `skipped` (vợ chốt bỏ qua) sẽ về 0 nếu không giữ lại.
    keep_skip = [r[0] for r in conn.execute(
        "SELECT haravan_id FROM product_spec_index WHERE skipped=1").fetchall()]
    conn.executemany(INSERT_SQL, rows)
    if keep_skip:
        conn.executemany("UPDATE product_spec_index SET skipped=1 WHERE haravan_id=?",
                         [(i,) for i in keep_skip])
    conn.commit()
    mark_services(conn)
    conn.close()
    return {"total": len(rows),
            "new": sum(1 for r in rows if r[6] == "new"),
            "scanned_at": now}


# ─────────────────── quét menu collection LÁ ───────────────────
LI_BLOCK = re.compile(r"(?is)<li\b")


def _menu_html() -> str:
    r = requests.get(STORE_URL, timeout=30, headers=UA)
    r.raise_for_status()
    m = re.search(r'(?is)<nav class="header-nav-ver".*?</nav>', r.text)
    if not m:
        raise RuntimeError("Không tìm thấy menu dọc trên trang chủ")
    return m.group(0)


def parse_menu_leaves(menu_html: str) -> list:
    """Trả collection LÁ (nhánh sâu nhất). Bỏ collection mẹ, bỏ link không phải /collections/."""
    try:
        from bs4 import BeautifulSoup  # noqa: PLC0415
    except ImportError:
        raise RuntimeError("Thiếu thư viện beautifulsoup4")
    soup = BeautifulSoup(menu_html, "html.parser")
    leaves, order = [], 0
    for li in soup.find_all("li"):
        a = li.find("a", recursive=False)
        if not a or not a.get("href"):
            continue
        if li.find("ul"):        # còn cấp con → là collection MẸ, bỏ
            continue
        href = a["href"].split("?")[0].rstrip("/")
        if not href.startswith("/collections/"):
            continue
        parts = [x for x in href[len("/collections/"):].split("/") if x]
        if not parts:
            continue
        handle, tag = parts[0], (parts[1] if len(parts) > 1 else "")
        title = a.get("title") or a.get_text(" ", strip=True)
        title = re.sub(r"\s*Hot\s*$", "", title).strip()
        # cha + nhánh gốc để nhóm hiển thị
        parent, root = "", ""
        anc = [x for x in li.parents if x.name == "li"]
        if anc:
            pa = anc[0].find("a", recursive=False)
            if pa:
                parent = re.sub(r"\s*Hot\s*$", "", pa.get_text(" ", strip=True)).strip()
            ra = anc[-1].find("a", recursive=False)
            if ra:
                root = re.sub(r"\s*Hot\s*$", "", ra.get_text(" ", strip=True)).strip()
        order += 1
        leaves.append(dict(handle=handle, tag_filter=tag, title=title,
                           parent=parent or root, root=root or (parent or title),
                           sort_order=order))
    # bỏ trùng (giữ bản đầu)
    seen, out = set(), []
    for L in leaves:
        k = (L["handle"], L["tag_filter"])
        if k not in seen:
            seen.add(k)
            out.append(L)
    return out


def _collection_id(handle: str, cache: dict) -> int | None:
    if handle in cache:
        return cache[handle]
    cid = None
    # ⚠️ BẪY 27/7/2026: Haravan lọc `?handle=X` kiểu KHỚP TIỀN TỐ, và trả handle DÀI hơn
    # lên TRƯỚC. Lấy arr[0] => bốc NHẦM collection khác:
    #   ?handle=ban-phim-co -> [ban-phim-co-day(4 SP), ban-phim-co(92 SP)]  => lấy nhầm 4 SP
    #   ?handle=ghe         -> [ghe-van-phong(1 SP),   ghe(19 SP)]          => lấy nhầm 1 SP
    # => PHẢI lọc handle KHỚP CHÍNH XÁC, chỉ fallback arr[0] khi không có cái nào khớp.
    def _pick(arr):
        for c in arr:
            if (c.get("handle") or "") == handle:
                return c["id"]
        return None

    try:
        d = hc._request("GET", "/smart_collections.json",
                        params={"handle": handle, "fields": "id,handle"})
        cid = _pick(d.get("smart_collections") or [])
    except Exception:  # noqa: BLE001
        cid = None
    if cid is None:
        try:
            d = hc._request("GET", "/custom_collections.json",
                            params={"handle": handle, "fields": "id,handle"})
            cid = _pick(d.get("custom_collections") or [])
        except Exception:  # noqa: BLE001
            cid = None
    cache[handle] = cid
    return cid


def scan_menu(log=print) -> dict:
    """Bóc collection lá từ menu live → lấy SP từng nhóm → lưu DB."""
    init_schema()
    leaves = parse_menu_leaves(_menu_html())
    log(f"Menu live có {len(leaves)} collection lá")
    conn = db.get_conn()
    conn.execute("DELETE FROM spec_menu_collections")
    conn.execute("DELETE FROM spec_group_products")
    now = datetime.now().isoformat(timespec="seconds")
    id_cache, miss = {}, []
    known = {r[0] for r in conn.execute("SELECT haravan_id FROM product_spec_index").fetchall()}
    # SP dịch vụ/sửa chữa không nằm trong phạm vi → không tính vào new/đúng chuẩn
    # 23/7: thêm published — SP đã ẩn (web trả 301/404) cũng không tính. Trước đó
    # 97 SP đã ẩn vẫn nằm trong thống kê, làm mọi con số phồng lên.
    newset = {r[0] for r in conn.execute(
        "SELECT haravan_id FROM product_spec_index WHERE condition_kind='new' "
        "AND COALESCE(is_service,0)=0 AND COALESCE(skipped,0)=0 "
        "AND COALESCE(published,1)=1").fetchall()}
    okset = {r[0] for r in conn.execute(
        "SELECT haravan_id FROM product_spec_index WHERE spec_format=? "
        "AND COALESCE(is_service,0)=0", (FMT_A,)).fetchall()}

    for L in leaves:
        cid = _collection_id(L["handle"], id_cache)
        pids = []
        if cid:
            try:
                pids = [p["id"] for p in hc.list_products_in_collection(cid, fields="id")]
            except Exception as e:  # noqa: BLE001
                log(f"  ⚠ {L['handle']}: lỗi lấy SP ({e})")
        else:
            miss.append(L["handle"])
        if L["tag_filter"]:
            tag = L["tag_filter"].replace("_", " ").lower()
            keep = []
            for pid in pids:
                row = conn.execute("SELECT tags FROM product_spec_index WHERE haravan_id=?",
                                   (pid,)).fetchone()
                if row and tag in (row[0] or "").lower():
                    keep.append(pid)
            pids = keep
        pids = [p for p in pids if p in known]
        conn.executemany("INSERT OR REPLACE INTO spec_group_products VALUES (?,?,?)",
                         [(L["handle"], L["tag_filter"], pid) for pid in pids])
        conn.execute(
            "INSERT OR REPLACE INTO spec_menu_collections VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (L["handle"], L["tag_filter"], L["title"], L["parent"], L["root"], L["sort_order"],
             cid, len(pids), sum(1 for p in pids if p in newset),
             sum(1 for p in pids if p in okset), now))
        time.sleep(0.05)
    conn.commit()

    # ── 27/7/2026 (vợ chốt): SP không thuộc collection LÁ nào -> gom về NGĂN MẸ,
    # KHÔNG tạo collection con mới. Ngăn mẹ có thật trên Haravan, chỉ là không nằm
    # trong menu nên trước đây /thumbs bỏ qua -> SP bị dồn vào "SP chưa phân loại".
    # Thứ tự = CỤ THỂ TRƯỚC, TỔNG QUÁT SAU (mỗi SP chỉ vào ngăn mẹ đầu tiên khớp).
    PARENTS = ["cap-chuyen-doi", "luu-tru-va-box", "may-in", "may-tinh-bo",
               "ban-ghe-gaming", "phu-kien-linh-kien-laptop", "phu-kien-thiet-bi-mang-1",
               "gaming-gear", "man-hinh-may-tinh", "linh-kien-may-tinh"]
    leaf_ids = {r[0] for r in conn.execute("SELECT DISTINCT haravan_id FROM spec_group_products")}
    left = newset - leaf_ids
    log(f"SP chưa vào ngăn lá: {len(left)} -> gom về ngăn mẹ")
    order = len(leaves) + 1
    for ph in PARENTS:
        if not left:
            break
        pcid = _collection_id(ph, id_cache)
        if not pcid:
            log(f"  ⚠ không tìm thấy ngăn mẹ {ph}")
            continue
        try:
            pids = [p["id"] for p in hc.list_products_in_collection(pcid, fields="id")]
        except Exception as e:  # noqa: BLE001
            log(f"  ⚠ {ph}: {e}")
            continue
        take = [p for p in pids if p in left]
        if not take:
            continue
        left -= set(take)
        # lấy TÊN THẬT của collection cho dễ đọc (đừng hiện handle trần)
        ptitle = ph
        try:
            r = hc._request("GET", f"/smart_collections/{pcid}.json")
            ptitle = (r.get("smart_collection") or {}).get("title") or ph
        except Exception:  # noqa: BLE001
            pass
        conn.executemany("INSERT OR REPLACE INTO spec_group_products VALUES (?,?,?)",
                         [(ph, "", pid) for pid in take])
        conn.execute(
            "INSERT OR REPLACE INTO spec_menu_collections VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ph, "", ptitle, "gom từ ngăn mẹ", "📦 Ngăn mẹ (SP chưa có danh mục con)",
             order, pcid, len(take),
             sum(1 for p in take if p in newset), sum(1 for p in take if p in okset), now))
        order += 1
        log(f"  📦 {ph}: nhận {len(take)} SP")
    conn.commit()

    mark_services(conn)
    grouped = {r[0] for r in conn.execute("SELECT DISTINCT haravan_id FROM spec_group_products")}
    conn.close()
    if miss:
        log(f"⚠ {len(miss)} collection không resolve được id: {miss[:8]}")
    return {"leaves": len(leaves), "grouped": len(grouped),
            "ungrouped": len(known - grouped), "missing_id": miss, "scanned_at": now}


# ───────────────────────── truy vấn cho UI ─────────────────────────

def groups_overview(only_new: bool = True) -> dict:
    conn = db.get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM spec_menu_collections ORDER BY sort_order").fetchall()]
    grouped = {r[0] for r in conn.execute("SELECT DISTINCT haravan_id FROM spec_group_products")}
    q = "SELECT haravan_id FROM product_spec_index"
    if only_new:
        q += " WHERE condition_kind='new'"
    allp = {r[0] for r in conn.execute(q).fetchall()}
    stats = dict(conn.execute(
        "SELECT spec_format, COUNT(*) FROM product_spec_index WHERE condition_kind='new' "
        "AND COALESCE(is_service,0)=0 AND COALESCE(skipped,0)=0 "
        "AND COALESCE(published,1)=1 GROUP BY spec_format").fetchall())
    total = conn.execute("SELECT COUNT(*) FROM product_spec_index").fetchone()[0]
    service = conn.execute("SELECT COUNT(*) FROM product_spec_index WHERE is_service=1 "
                           "AND condition_kind='new'").fetchone()[0]
    scanned = conn.execute("SELECT MAX(scanned_at) FROM product_spec_index").fetchone()[0]
    conn.close()
    return {"groups": rows, "ungrouped": sorted(allp - grouped), "fmt_stats": stats,
            "total": total, "service": service, "scanned_at": scanned}


def products_of_group(handle: str, tag_filter: str = "", only_new: bool = True) -> list:
    conn = db.get_conn()
    if handle == "__ungrouped__":
        sql = ("SELECT p.haravan_id,p.handle,p.title,p.product_type,p.spec_format,p.pair_count,"
               "p.issue_count,p.published,p.image_src,p.condition_kind,"
               "COALESCE(p.is_service,0) AS is_service, COALESCE(p.skipped,0) AS skipped FROM product_spec_index p "
               "WHERE p.haravan_id NOT IN (SELECT haravan_id FROM spec_group_products)")
        args = []
    else:
        sql = ("SELECT p.haravan_id,p.handle,p.title,p.product_type,p.spec_format,p.pair_count,"
               "p.issue_count,p.published,p.image_src,p.condition_kind,"
               "COALESCE(p.is_service,0) AS is_service, COALESCE(p.skipped,0) AS skipped FROM product_spec_index p "
               "JOIN spec_group_products g ON g.haravan_id=p.haravan_id "
               "WHERE g.handle=? AND g.tag_filter=?")
        args = [handle, tag_filter]
    if only_new:
        sql += " AND p.condition_kind='new'"
    sql += " ORDER BY p.issue_count DESC, p.title"
    rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    # gắn kèm kết quả research: nguồn đã dùng + số nguồn đã soi
    if rows:
        ids = ",".join(str(r["haravan_id"]) for r in rows)
        used = {r[0]: (r[1], r[2], r[3]) for r in conn.execute(
            f"SELECT haravan_id, url, n_rows, reason FROM spec_research_source "
            f"WHERE haravan_id IN ({ids}) AND status='dung'").fetchall()}
        seen = dict(conn.execute(
            f"SELECT haravan_id, COUNT(*) FROM spec_research_source "
            f"WHERE haravan_id IN ({ids}) GROUP BY haravan_id").fetchall())
        for r in rows:
            u = used.get(r["haravan_id"])
            r["src_seen"] = seen.get(r["haravan_id"], 0)
            r["src_host"] = (u[0] or "").replace("https://", "").replace("http://",
                                                                        "").split("/")[0] if u else ""
            r["src_rows"] = u[1] if u else 0
            r["src_why"] = u[2] if u else ""
    conn.close()
    return rows


def get_product(pid: int) -> dict | None:
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM product_spec_index WHERE haravan_id=?", (pid,)).fetchone()
    conn.close()
    return dict(r) if r else None


def search_products(q: str, limit: int = 30) -> list:
    conn = db.get_conn()
    like = f"%{q.strip()}%"
    rows = [dict(r) for r in conn.execute(
        "SELECT haravan_id,handle,title,product_type,spec_format,pair_count,issue_count,"
        "published,image_src,condition_kind FROM product_spec_index "
        "WHERE title LIKE ? OR handle LIKE ? OR CAST(haravan_id AS TEXT)=? "
        "ORDER BY condition_kind='new' DESC, title LIMIT ?",
        (like, like, q.strip(), limit)).fetchall()]
    conn.close()
    return rows


def refresh_one(pid: int) -> dict:
    """Kéo lại 1 SP từ Haravan (live) → cập nhật bảng. Dùng sau khi sync."""
    init_schema()
    p = hc.get_product(pid)
    if not p:
        raise RuntimeError(f"Không tìm thấy SP {pid}")
    cond = condition_of(p)
    c = (classify_body(p) if cond == "new"
         else dict(fmt="", block="", pairs=[], groups=[], issues=[], has_bq=0, has_table=0))
    imgs = p.get("images") or []
    now = datetime.now().isoformat(timespec="seconds")
    conn = db.get_conn()
    was_service = conn.execute("SELECT is_service FROM product_spec_index WHERE haravan_id=?",
                               (pid,)).fetchone()
    conn.execute(INSERT_SQL,
                 (p["id"], p.get("handle"), p.get("title"), p.get("product_type"), p.get("vendor"),
                  p.get("tags"), cond, 1 if p.get("published_at") else 0,
                  c["fmt"], len(c["pairs"]), len(c["groups"]), len(c["issues"]),
                  json.dumps(c["issues"], ensure_ascii=False),
                  json.dumps(c["pairs"], ensure_ascii=False),
                  json.dumps(c["groups"], ensure_ascii=False),
                  c["block"], c["has_bq"], c["has_table"],
                  len(p.get("body_html") or ""), p.get("body_html") or "",
                  (imgs[0].get("src") if imgs else None),
                  (was_service[0] if was_service else 0)
                  or (1 if SERVICE_TYPE.search(p.get("product_type") or "") else 0),
                  p.get("updated_at"), now))
    conn.commit()
    conn.close()
    return get_product(pid)


def push_body(pid: int, body_html: str, actor: str = "nox", note: str = "") -> dict:
    """Đẩy mô tả mới lên Haravan rồi đọc lại để xác nhận (HTTP 200 ≠ đã lưu).

    actor: 'vo' = vợ tự bấm Duyệt trên tab · 'nox' = anh chạy script.
    """
    hc.update_product(pid, {"body_html": body_html})
    time.sleep(1.2)
    live = hc.get_product(pid)
    saved = (live.get("body_html") or "")
    ok = strip_tags(saved)[:400] == strip_tags(body_html)[:400]
    row = refresh_one(pid)
    log_event("product", actor, haravan_id=pid, handle=row["handle"], title=row["title"],
              spec_format=row["spec_format"], pair_count=row["pair_count"], note=note)
    return {"ok": ok, "spec_format": row["spec_format"], "body_len": row["body_len"]}


# ───────────────────── nhật ký sync + duyệt danh mục ─────────────────────

def log_event(kind: str, actor: str, haravan_id: int = None, handle: str = "",
              title: str = "", spec_format: str = "", pair_count: int = 0,
              note: str = "", tag_filter: str = "") -> None:
    init_schema()
    conn = db.get_conn()
    conn.execute("""INSERT INTO spec_sync_log
        (kind,actor,haravan_id,handle,tag_filter,title,spec_format,pair_count,note,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
                 (kind, actor, haravan_id, handle, tag_filter, title, spec_format,
                  pair_count, note, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()


def approve_collection(handle: str, tag_filter: str = "", actor: str = "vo") -> dict:
    conn = db.get_conn()
    r = conn.execute("SELECT title, new_count, ok_count FROM spec_menu_collections "
                     "WHERE handle=? AND tag_filter=?", (handle, tag_filter)).fetchone()
    conn.close()
    title = r["title"] if r else handle
    note = f"{r['ok_count']}/{r['new_count']} SP đúng chuẩn" if r else ""
    log_event("collection", actor, handle=handle, tag_filter=tag_filter, title=title, note=note)
    return {"ok": True, "title": title, "note": note}


def list_log(actor: str = None, page: int = 1, per: int = 10) -> dict:
    init_schema()
    conn = db.get_conn()
    where, args = "", []
    if actor:
        where = "WHERE actor = ?"
        args = [actor]
    total = conn.execute(f"SELECT COUNT(*) FROM spec_sync_log {where}", args).fetchone()[0]
    rows = [dict(r) for r in conn.execute(
        f"SELECT * FROM spec_sync_log {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        args + [per, max(0, (page - 1) * per)]).fetchall()]
    conn.close()
    return {"rows": rows, "total": total, "page": page,
            "pages": max(1, -(-total // per))}


def add_error_note(pid: int, label: str, wrong_value: str, correct_value: str,
                   source: str = "", note: str = "", handle: str = "",
                   title: str = "") -> int:
    """Ghi 1 chỉ tiêu SAI của SP (đã đối chiếu trang hãng). Nếu chưa có title/handle
    thì lấy từ product_spec_index. Trùng (pid+label) thì cập nhật đè, không nhân đôi."""
    init_schema()
    conn = db.get_conn()
    if not title or not handle:
        r = conn.execute("SELECT handle, title FROM product_spec_index WHERE haravan_id=?",
                         (pid,)).fetchone()
        if r:
            handle = handle or r["handle"]
            title = title or r["title"]
    old = conn.execute("SELECT id FROM spec_error_note WHERE haravan_id=? AND label=?",
                       (pid, label)).fetchone()
    now = datetime.now().isoformat(timespec="seconds")
    if old:
        conn.execute("""UPDATE spec_error_note SET wrong_value=?, correct_value=?,
            source=?, note=?, status='open', created_at=? WHERE id=?""",
            (wrong_value, correct_value, source, note, now, old["id"]))
        eid = old["id"]
    else:
        cur = conn.execute("""INSERT INTO spec_error_note
            (haravan_id,handle,title,label,wrong_value,correct_value,source,note,status,created_at)
            VALUES (?,?,?,?,?,?,?,?, 'open', ?)""",
            (pid, handle, title, label, wrong_value, correct_value, source, note, now))
        eid = cur.lastrowid
    conn.commit()
    conn.close()
    return eid


def list_error_notes(page: int = 1, per: int = 10, only_open: bool = False) -> dict:
    """Danh sách SP sai spec cho tab đỏ. Gom theo SP, mỗi SP kèm các chỉ tiêu sai."""
    init_schema()
    conn = db.get_conn()
    where = "WHERE status='open'" if only_open else ""
    rows = [dict(r) for r in conn.execute(
        f"SELECT * FROM spec_error_note {where} ORDER BY id DESC").fetchall()]
    conn.close()
    # gom theo haravan_id, giữ thứ tự xuất hiện
    order, grouped = [], {}
    for r in rows:
        pid = r["haravan_id"]
        if pid not in grouped:
            grouped[pid] = {"haravan_id": pid, "handle": r["handle"], "title": r["title"],
                            "created_at": r["created_at"], "items": []}
            order.append(pid)
        grouped[pid]["items"].append({
            "label": r["label"], "wrong": r["wrong_value"], "correct": r["correct_value"],
            "source": r["source"], "note": r["note"], "status": r["status"], "id": r["id"]})
    cards = [grouped[p] for p in order]
    total = len(cards)
    s = max(0, (page - 1) * per)
    return {"rows": cards[s:s + per], "total": total, "page": page,
            "pages": max(1, -(-total // per))}


def error_note_pids() -> set:
    """Tập haravan_id đang có lỗi spec (để chấm badge đỏ ở View nhanh / thẻ nhóm)."""
    init_schema()
    conn = db.get_conn()
    try:
        pids = {r[0] for r in conn.execute(
            "SELECT DISTINCT haravan_id FROM spec_error_note WHERE status='open'").fetchall()}
    except sqlite3.Error:
        pids = set()
    conn.close()
    return pids


def mark_skipped(pid: int, note: str = "", actor: str = "vo") -> dict:
    """Vợ chốt 'bỏ qua, xem như đã làm' → không tính vào nhóm cần sửa nữa."""
    init_schema()
    conn = db.get_conn()
    conn.execute("UPDATE product_spec_index SET skipped=1 WHERE haravan_id=?", (pid,))
    conn.commit()
    r = conn.execute("SELECT title, handle, spec_format, pair_count FROM product_spec_index "
                     "WHERE haravan_id=?", (pid,)).fetchone()
    conn.close()
    log_event("product", actor, haravan_id=pid, handle=r["handle"] if r else "",
              title=r["title"] if r else "", spec_format=r["spec_format"] if r else "",
              pair_count=r["pair_count"] if r else 0,
              note=note or "bỏ qua — xem như đã xử lý")
    return {"ok": True, "title": r["title"] if r else str(pid)}


def save_research_sources(pid: int, result: dict) -> int:
    """Lưu các trang nguồn đã soi khi research 1 SP (cả trang dùng lẫn trang bị loại)."""
    init_schema()
    now = datetime.now().isoformat(timespec="seconds")
    conn = db.get_conn()
    conn.execute("DELETE FROM spec_research_source WHERE haravan_id=?", (pid,))
    n = 0
    for c in result.get("candidates") or []:
        conn.execute("""INSERT INTO spec_research_source
            (haravan_id,url,page_title,n_rows,rows_json,status,reason,created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
                     (pid, c.get("url"), c.get("title") or "", len(c.get("rows") or []),
                      json.dumps(c.get("rows") or [], ensure_ascii=False),
                      "dung" if c.get("picked") else "bo_qua",
                      c.get("why") or "", now))
        n += 1
    for item in result.get("rejected") or []:
        url, why = item[0], item[1]
        ptitle = item[2] if len(item) > 2 else ""
        conn.execute("""INSERT INTO spec_research_source
            (haravan_id,url,page_title,n_rows,rows_json,status,reason,created_at)
            VALUES (?,?,?,?,?,?,?,?)""", (pid, url, ptitle, 0, "[]", "bo_qua", why, now))
        n += 1
    # SP bị chặn NGAY Ở CỔNG (không có mã model / nhóm không tự động) → vẫn phải ghi lý do,
    # không thì trên bảng hiện "chưa tra" trong khi thực tế đã xét và cố ý bỏ.
    if n == 0 and result.get("reason"):
        conn.execute("""INSERT INTO spec_research_source
            (haravan_id,url,page_title,n_rows,rows_json,status,reason,created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
                     (pid, "", "(không tra web)", 0, "[]", "bo_qua", result["reason"], now))
        n = 1
    conn.commit()
    conn.close()
    return n


def get_research_sources(pid: int) -> list:
    init_schema()
    conn = db.get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM spec_research_source WHERE haravan_id=? "
        "ORDER BY (status='dung') DESC, n_rows DESC", (pid,)).fetchall()]
    conn.close()
    for r in rows:
        r["rows"] = json.loads(r["rows_json"] or "[]")
        r.pop("rows_json", None)
    return rows


def approved_collections() -> dict:
    init_schema()
    conn = db.get_conn()
    rows = conn.execute("SELECT handle, MAX(created_at) FROM spec_sync_log "
                        "WHERE kind='collection' GROUP BY handle").fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


# ════════════════════ VIEW NHANH (23/7) ════════════════════
import unicodedata as _ud


def _qnorm(s: str) -> str:
    """Chuẩn hoá nhãn để so khớp.

    ⚠️ 'đ' KHÔNG tách được bằng NFD (là ký tự riêng, không phải d + dấu).
    Không thay trước thì "Độ phân giải" → " o phan giai" và mọi phép khớp
    nhãn có chữ đ đều trượt — lỗi đã trả giá 23/7.
    """
    s = str(s or "").lower().replace("đ", "d")
    s = _ud.normalize("NFD", s)
    s = "".join(c for c in s if _ud.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# dòng CẤM đưa vào bảng thông số (rule content của vợ)
_Q_BAN_LBL = re.compile(r"(?i)^\s*(giá|giá bán|giá niêm yết|đơn giá|bảo hành|tình trạng"
                        r"|kho hàng|còn hàng|tồn kho|khuyến mãi|mã sản phẩm cũ)\s*$")
_Q_BAN_VAL = re.compile(r"\d[\d.,]*\s*(₫|đ|vnđ|vnd|đồng)\b", re.I)


def _q_pairs_from_product(p: dict) -> list:
    """Bóc cặp [nhãn, giá trị] đang LIVE từ bản ghi SP."""
    out = []
    try:
        for x in json.loads(p.get("spec_pairs_json") or "[]"):
            if isinstance(x, dict):
                k = x.get("label") or x.get("k") or ""
                v = x.get("value") or x.get("v") or ""
            elif isinstance(x, (list, tuple)) and len(x) >= 2:
                k, v = x[0], x[1]
            else:
                continue
            if str(k).strip():
                out.append([str(k).strip(), str(v).strip()])
    except Exception:  # noqa: BLE001
        pass
    return out


def _q_rows_from_source(rj: str) -> list:
    out = []
    try:
        for x in json.loads(rj or "[]"):
            if isinstance(x, (list, tuple)) and len(x) >= 2 and str(x[0]).strip():
                out.append([str(x[0]).strip(), str(x[1]).strip()])
    except Exception:  # noqa: BLE001
        pass
    return out


# ── Nhãn ĐỒNG NGHĨA khác tên (23/7, vợ chỉ ra ca Lexar NM620) ────────────────
# Live ghi "Hãng sản xuất | Lexar", nguồn fetch ghi "Thương hiệu | LEXAR" → gộp thô
# ra 2 dòng cùng nghĩa. Nguồn còn tự trùng: "Tốc độ đọc tối đa" + "Tốc độ đọc".
# ⚠️ Khớp TRỌN VẸN nhãn, KHÔNG khớp chuỗi con — nếu không "Tốc độ đọc" sẽ nuốt
# luôn "Tốc độ đọc ngẫu nhiên" (chỉ số khác hẳn).
_SYN_GROUPS = {
    "hang":        ["hang san xuat", "thuong hieu", "hang", "brand", "nha san xuat",
                    "hang sx", "hang sx thuong hieu"],
    "dong_sp":     ["dong san pham", "dong", "series", "dong sp"],
    "ma_sp":       ["ma san pham", "ma part", "part number", "ma hang", "sku",
                    "ma san pham p n", "model", "ma model", "model number"],
    "form":        ["form factor", "chuan kich co", "kieu dang", "chuan kich thuoc"],
    "giao_tiep":   ["chuan giao tiep", "giao tiep", "interface", "chuan ket noi",
                    "giao thuc truyen dan", "giao dien dau ra", "chuan giao dien"],
    "bang_thong":  ["bang thong", "toc do truyen dan", "toc do truyen",
                    "toc do truyen tai", "bandwidth", "toc do toi da"],
    "chuan_ssd":   ["chuan ssd ho tro", "loai o cung tuong thich", "o cung ho tro",
                    "chuan o cung", "loai o cung ho tro"],
    "he_dieu_hanh": ["he dieu hanh ho tro", "he dieu hanh", "ho tro he dieu hanh",
                     "tuong thich he dieu hanh", "os ho tro"],
    "chip_nho":    ["bo nho flash", "loai chip nho", "chip nho", "loai bo nho",
                    "cong nghe nand"],
    "toc_doc":     ["toc do doc tuan tu", "toc do doc toi da", "toc do doc",
                    "toc do doc tuan tu toi da"],
    "toc_ghi":     ["toc do ghi tuan tu", "toc do ghi toi da", "toc do ghi",
                    "toc do ghi tuan tu toi da"],
    "dung_luong":  ["dung luong", "capacity", "dung luong luu tru"],
    "kich_thuoc":  ["kich thuoc", "dimensions", "kich thuoc san pham"],
    "trong_luong": ["trong luong", "can nang", "weight", "trong luong tinh"],
    "tam_nen":     ["tam nen", "panel", "loai tam nen", "cong nghe tam nen"],
    "tan_so":      ["tan so quet", "tan so lam tuoi", "refresh rate", "toc do lam moi"],
    "do_phan_giai": ["do phan giai", "resolution", "do phan giai man hinh"],
    "cong_suat":   ["cong suat", "cong suat toi da", "cong suat dinh muc"],
    "socket":      ["socket", "socket ho tro", "de cam", "socket cpu"],
    "cam_bien":    ["cam bien", "sensor", "mat doc", "cam bien quang"],
}
_LABEL_CANON = {lbl: key for key, lst in _SYN_GROUPS.items() for lbl in lst}
# Nhãn ĐỊNH DANH: là dữ liệu của MÌNH, không phải thông số kỹ thuật → khi trùng
# thì GIỮ giá trị live, không để nguồn ngoài đè. Nếu không, mã SP "LNM620X256G"
# của mình bị thay bằng "LNM620X256G-RNNNG" của shop khác.
_KEEP_LIVE = {"hang", "dong_sp", "ma_sp"}


def _canon(label: str) -> str:
    """Khoá gộp của một nhãn: nhãn đồng nghĩa cho ra cùng khoá."""
    n = _qnorm(label)
    return _LABEL_CANON.get(n, n)


def _same_value(a: str, b: str) -> bool:
    """Hai giá trị có coi là MỘT không? Dùng để quyết định có gộp 2 dòng đồng nghĩa.

    ⚠️ Không có phép này thì "Model: M2PF-C3-BK" và "Mã sản phẩm: LNM620X256G"
    (cùng nhóm ma_sp nhưng khác hẳn nội dung) sẽ bị nuốt mất một dòng.
    """
    na, nb = _qnorm(a), _qnorm(b)
    if not na or not nb:
        return True
    if na == nb:
        return True
    # ⚠️ "chứa nhau" thôi thì CHƯA đủ: "NM620" nằm trong "LNM620X256G" nhưng là
    # dòng SP vs mã SP, khác hẳn. Chỉ coi là một khi bên ngắn chiếm ≥60% bên dài
    # ("m2pf c3 bk" trong "orico m2pf c3 bk" = 62% → đúng là một).
    if na in nb or nb in na:
        short, long_ = (na, nb) if len(na) <= len(nb) else (nb, na)
        if len(short) / max(len(long_), 1) >= 0.6:
            return True
    # cùng bộ số + đơn vị (vd "Up to 3000 MBps" ⟷ "3000Mb/s") thì coi là một
    sa, sb = re.findall(r"\d+(?:[.,]\d+)?", na), re.findall(r"\d+(?:[.,]\d+)?", nb)
    return bool(sa) and sa == sb


def _dedupe_by_canon(rows: list) -> list:
    """Khử trùng trong CHÍNH một bảng (nguồn hay tự lặp: 'Tốc độ đọc tối đa' +
    'Tốc độ đọc'). Giữ dòng ĐẦU TIÊN vì thường đầy đủ hơn.

    Chỉ gộp khi GIÁ TRỊ tương thích — khác hẳn thì giữ cả hai, thà thừa còn hơn mất."""
    keep, out = {}, []
    for k, v in rows:
        c = _canon(k)
        if c in keep and _same_value(keep[c], v):
            continue
        if c not in keep:
            keep[c] = v
        out.append([k, v])
    return out


def merge_specs(live: list, web: list) -> list:
    """Mẫu 3 = gộp live + web, ưu tiên GIÁ TRỊ MỚI FETCH khi cùng nhãn.

    Trả [[nhãn, giá trị, trạng thái]] với trạng thái:
      giu  — chỉ live có, giữ nguyên
      doi  — cả hai có nhưng khác giá trị → lấy bản web
      trung— cả hai có và giống nhau
      moi  — chỉ web có → thêm mới
    """
    live = _dedupe_by_canon(live)
    web = _dedupe_by_canon(web)
    widx, worder = {}, []
    for k, v in web:
        n = _canon(k)
        if n and n not in widx:
            widx[n] = [k, v]
            worder.append(n)
    out, used = [], set()
    for k, v in live:
        if _Q_BAN_LBL.match(k) or _Q_BAN_VAL.search(v):
            continue
        n = _canon(k)
        if n in widx:
            used.add(n)
            wk, wv = widx[n]
            if _qnorm(v) == _qnorm(wv):
                out.append([k, v, "trung"])
            elif n in _KEEP_LIVE:
                out.append([k, v, "giu"])        # định danh: giữ bản của mình
            else:
                out.append([k, wv, "doi"])       # sửa theo spec mới fetch
        else:
            out.append([k, v, "giu"])
    for n in worder:
        if n in used:
            continue
        k, v = widx[n]
        if _Q_BAN_LBL.match(k) or _Q_BAN_VAL.search(v):
            continue
        out.append([k, v, "moi"])
    return out


def sort_web_like_live(live: list, web: list) -> list:
    """Mẫu 2: xếp lại spec fetch theo ĐÚNG thứ tự nhãn của bản live cho dễ soi,
    phần web có mà live không có thì dồn xuống cuối."""
    web = _dedupe_by_canon(web)
    order = {_canon(k): i for i, (k, _v) in enumerate(live)}
    keyed = [(order.get(_canon(k), 10_000 + i), k, v) for i, (k, v) in enumerate(web)]
    keyed.sort(key=lambda x: x[0])
    return [[k, v] for _i, k, v in keyed]


def align_live_web(live: list, web: list) -> list:
    """Xếp NGANG HÀNG bản live và bản fetch: cùng tên thông số thì cùng một dòng.

    Trả [[nhãn_live, giá_trị_live, nhãn_web, giá_trị_web, trạng_thái]] với
    trạng thái: trung (2 bên giống) · doi (2 bên khác) · chi_live · chi_web.
    """
    live = _dedupe_by_canon(live)
    web = _dedupe_by_canon(web)
    widx = {}
    for k, v in web:
        widx.setdefault(_canon(k), [k, v])
    out, used = [], set()
    for k, v in live:
        c = _canon(k)
        if c in widx:
            used.add(c)
            wk, wv = widx[c]
            st = "trung" if _qnorm(v) == _qnorm(wv) else "doi"
            out.append([k, v, wk, wv, st])
        else:
            out.append([k, v, "", "", "chi_live"])
    for k, v in web:                      # phần chỉ bản fetch có → dồn xuống cuối
        c = _canon(k)
        if c in used:
            continue
        used.add(c)
        out.append(["", "", k, v, "chi_web"])
    return out


def quick_rows(handle: str, tag_filter: str = "") -> list:
    """Dữ liệu cho trang View nhanh của 1 collection."""
    init_schema()
    base = products_of_group(handle, tag_filter, only_new=True)
    if not base:
        return []
    ids = ",".join(str(r["haravan_id"]) for r in base)
    conn = db.get_conn()
    src, src_url, src_title = {}, {}, {}
    for pid_, rj_, url_, pt_ in conn.execute(
            f"SELECT haravan_id, rows_json, url, page_title FROM spec_research_source "
            f"WHERE haravan_id IN ({ids}) AND status='dung'").fetchall():
        src[pid_] = rj_
        src_url[pid_] = url_ or ""
        src_title[pid_] = pt_ or ""
    full = {r[0]: dict(r) for r in conn.execute(
        f"SELECT haravan_id, spec_pairs_json FROM product_spec_index "
        f"WHERE haravan_id IN ({ids})").fetchall()}
    draft = {r[0]: dict(r) for r in conn.execute(
        f"SELECT haravan_id, rows_json, skip_review, saved_at FROM spec_quick_draft "
        f"WHERE haravan_id IN ({ids})").fetchall()}
    conn.close()

    out = []
    for r in base:
        pid = r["haravan_id"]
        live = _q_pairs_from_product(full.get(pid, {}))
        web = _q_rows_from_source(src.get(pid))
        merged = merge_specs(live, web)
        d = draft.get(pid) or {}
        saved = _q_rows_from_source(d.get("rows_json")) if d.get("rows_json") else None
        if saved:                       # vợ đã sửa tay → dùng bản đã lưu
            merged = [[k, v, "luu"] for k, v in saved]
        out.append({
            **r,
            "live": live, "web": sort_web_like_live(live, web), "merged": merged,
            "aligned": align_live_web(live, web),
            "n_live": len(live), "n_web": len(web), "n_merged": len(merged),
            "n_moi": sum(1 for x in merged if x[2] == "moi"),
            "n_doi": sum(1 for x in merged if x[2] == "doi"),
            "src_url": src_url.get(pid, ""),
            "src_title": src_title.get(pid, ""),
            "excluded": bool(d.get("skip_review")),
            "saved_at": (d.get("saved_at") or "").replace("T", " ")[:16],
            "img": r.get("image_src") or "",
        })
    return out


def quick_save(pid: int, rows: list) -> dict:
    """Lưu bản spec vợ chốt vào DB. KHÔNG đẩy lên Haravan."""
    init_schema()
    clean = [[str(a).strip(), str(b).strip()] for a, b in rows
             if str(a).strip() and not _Q_BAN_LBL.match(str(a).strip())]
    conn = db.get_conn()
    conn.execute("""INSERT INTO spec_quick_draft (haravan_id, rows_json, skip_review, saved_at)
        VALUES (?,?,COALESCE((SELECT skip_review FROM spec_quick_draft WHERE haravan_id=?),0),
                datetime('now','localtime'))
        ON CONFLICT(haravan_id) DO UPDATE SET rows_json=excluded.rows_json,
                saved_at=excluded.saved_at""",
                 (pid, json.dumps(clean, ensure_ascii=False), pid))
    conn.commit()
    conn.close()
    return {"ok": True, "n": len(clean)}


def quick_exclude(pid: int, on: bool = True) -> dict:
    """Loại SP khỏi danh sách duyệt (hàng quá cũ, không muốn đụng) → KHÔNG sync spec."""
    init_schema()
    conn = db.get_conn()
    conn.execute("""INSERT INTO spec_quick_draft (haravan_id, skip_review, saved_at)
        VALUES (?,?,datetime('now','localtime'))
        ON CONFLICT(haravan_id) DO UPDATE SET skip_review=excluded.skip_review,
                saved_at=excluded.saved_at""", (pid, 1 if on else 0))
    conn.commit()
    conn.close()
    return {"ok": True, "excluded": bool(on)}
