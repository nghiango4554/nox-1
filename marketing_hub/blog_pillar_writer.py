"""T4 — Sinh hệ thống nội dung Pillar–Cluster TỰ ĐỘNG cho Sintech (auto, không cần duyệt).

Tầng A: gen_pillars(ctx)            → 10-15 Pillar (JSON), bám data Sintech thật.
Tầng B: gen_clusters(pillar, ctx)   → 8-15 bài cluster/pillar (JSON).
Orchestrator: generate_plan()       → A → B từng pillar → seed blog_pillars + blog_jobs (status pending).

Context bám data THẬT: collections Sintech (data/haravan_collections.json) + top keyword GSC
(data/gsc_cache.json) → KHÔNG bắt AI "tự research web" (nó không browse được).

Bài cluster là net-new (chưa có URL thật) → blog_url = URL dự kiến
https://sintech.vn/blogs/<target_blog>/<slug>, source='ai_pillar'. Gen nội dung là bước batch riêng.
"""
import re
import json
import unicodedata
from pathlib import Path
from datetime import datetime

import db
import ai_provider

HERE = Path(__file__).parent
COLLECTIONS_PATH = HERE / "data" / "haravan_collections.json"
GSC_PATH = HERE / "data" / "gsc_cache.json"


# ──────────────────────────────── context ────────────────────────────────
def build_context(max_collections: int = 70, max_keywords: int = 90) -> dict:
    """Gom data Sintech thật → block text bơm vào prompt."""
    cols = []
    try:
        raw = json.loads(COLLECTIONS_PATH.read_text(encoding="utf-8"))
        seen = set()
        for c in raw:
            title = (c.get("title") or "").strip()
            handle = (c.get("handle") or "").strip()
            if not title or handle in seen:
                continue
            seen.add(handle)
            cols.append(f"{title} (/collections/{handle})")
            if len(cols) >= max_collections:
                break
    except Exception:
        pass

    kws = []
    try:
        gsc = json.loads(GSC_PATH.read_text(encoding="utf-8"))
        queries = gsc.get("performance", {}).get("queries", [])
        # đã sort theo click desc; lấy top, bỏ brand "sintech"
        for q in queries:
            term = (q.get("query") or "").strip()
            if not term or term.lower() == "sintech":
                continue
            kws.append(f"{term} (click {q.get('click', 0)}, pos {q.get('pos', 0)})")
            if len(kws) >= max_keywords:
                break
    except Exception:
        pass

    col_text = "\n".join(f"- {c}" for c in cols) or "(không có dữ liệu collection)"
    kw_text = "\n".join(f"- {k}" for k in kws) or "(không có dữ liệu GSC)"
    full = (
        f"### COLLECTIONS/CATEGORY SINTECH ĐANG BÁN ({len(cols)} nhóm) — kéo internal link về đây:\n"
        f"{col_text}\n\n"
        f"### TOP KEYWORD GOOGLE SEARCH CONSOLE SINTECH ĐANG CÓ ({len(kws)} từ, sort theo click):\n"
        f"{kw_text}"
    )
    short = (
        f"### CATEGORY SINTECH (để chọn internal link):\n{col_text}\n\n"
        f"### TOP KEYWORD GSC:\n" + "\n".join(f"- {k}" for k in kws[:40])
    )
    return {"text": full, "text_short": short, "n_collections": len(cols), "n_keywords": len(kws)}


# ──────────────────────────────── prompts ────────────────────────────────
_ROLE = (
    "Bạn là SEO Content Strategist cho Sintech.vn — website bán PC Gaming, PC văn phòng, "
    "laptop, linh kiện máy tính (CPU/Main/RAM/SSD/VGA/PSU/Case/tản nhiệt), màn hình, gaming gear, "
    "phần mềm bản quyền (Windows/Office/Autodesk) và dịch vụ kỹ thuật.\n"
    "Tư duy như các site công nghệ lớn (CellphoneS/Sforum, Thế Giới Di Động, Minh Tuấn Mobile): "
    "vừa bài sát sản phẩm, vừa bài ngoài lề CÓ KIỂM SOÁT (AI, Windows, phần mềm, gaming, setup góc làm việc, "
    "thủ thuật PC/laptop, xu hướng công nghệ) — vẫn liên quan tệp khách Sintech.\n\n"
    "3 LỚP NỘI DUNG: 'money' (sát SP, intent mua rõ) / 'support' (giải quyết vấn đề trước khi mua/nâng cấp) / "
    "'media' (ngoài lề kéo traffic rộng). Tỷ lệ ưu tiên 50% money / 30% support / 20% media.\n\n"
    "QUY TẮC BẮT BUỘC:\n"
    "- KHÔNG bịa search volume; chỉ đánh giá nhu cầu Cao/Trung bình/Thấp.\n"
    "- KHÔNG bịa thông số kỹ thuật. KHÔNG copy title/heading đối thủ. KHÔNG nhắc tên đối thủ.\n"
    "- KHÔNG đề xuất chung chung kiểu 'nên làm bài về laptop' — phải cụ thể, có góc riêng.\n"
    "- Ưu tiên chủ đề trend 2026: AI PC, laptop AI, NPU, Copilot+ PC, GPU RTX mới, CPU Intel/AMD đời mới, "
    "Windows 10 hết hỗ trợ → nâng Windows 11, phần mềm bản quyền, AI Agent, làm việc bằng AI, gaming 2026, bảo mật.\n"
    "- Internal link ưu tiên về collection/product/dịch vụ THẬT (lấy từ DATA cung cấp)."
)

_PILLAR_INSTR = (
    "\n\nNHIỆM VỤ: đề xuất {n} PILLAR content (chủ đề trụ) cho Sintech theo mô hình Pillar–Cluster.\n"
    "Mỗi Pillar phải đủ lớn để triển khai 8-15 bài cluster, hướng rõ ràng. "
    "Phải có CẢ Pillar sát sản phẩm LẪN Pillar ngoài lề có kiểm soát. Đa dạng 3 lớp money/support/media.\n\n"
    "{context}\n\n"
    "OUTPUT: CHỈ JSON THUẦN (KHÔNG markdown, KHÔNG ```), 1 mảng gồm {n} object:\n"
    '[{{"title":"...","intent":"...","content_group":"...","audience":"...","reason":"...",'
    '"priority":"Cao|Trung bình|Thấp","target_category":"tên/handle collection Sintech nên kéo link, hoặc \\"\\" nếu ngoài lề",'
    '"layer":"money|support|media"}}]'
)

_CLUSTER_INSTR = (
    "\n\nNHIỆM VỤ: cho PILLAR dưới đây, đề xuất {n} bài CLUSTER bao phủ nhiều góc "
    "(tư vấn mua, so sánh, lỗi thường gặp, hướng dẫn chọn, kiến thức nền, trend mới, case thực tế). "
    "Title tự nhiên, KHÔNG trùng intent nhau, KHÔNG giống nhau. Mỗi bài có góc viết unique.\n\n"
    "PILLAR: {pillar_title}\n"
    "- Intent pillar: {pillar_intent}\n- Lớp: {pillar_layer}\n- Category kéo link: {pillar_cat}\n\n"
    "{context}\n\n"
    "OUTPUT: CHỈ JSON THUẦN (KHÔNG markdown, KHÔNG ```), 1 mảng gồm {n} object:\n"
    '[{{"title":"...","keyword":"keyword chính","intent":"...","content_group":"...",'
    '"unique_angle":"góc viết riêng","internal_link":"collection/product Sintech nên chèn link",'
    '"priority":"Cao|Trung bình|Thấp","article_type":"Trend|Evergreen|How-to|So sánh|Giải thích",'
    '"layer":"money|support|media","is_external":true/false,"target_blog":"huong-dan|news"}}]'
)


# ──────────────────────────────── AI calls ────────────────────────────────
def _parse_json_array(raw: str) -> list:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\[[\s\S]*\]", text)
        if not m:
            raise ValueError(f"AI không trả JSON array. Đầu: {text[:200]}")
        data = json.loads(m.group(0))
    if not isinstance(data, list):
        raise ValueError("JSON không phải array.")
    return data


def gen_pillars(context_text: str, n: int = 12, timeout: int = 300) -> list:
    sys_p = _ROLE + _PILLAR_INSTR.format(n=n, context=context_text)
    raw = ai_provider.call_ai(
        sys_p, "Trả JSON array Pillar như mô tả. Tiếng Việt.",
        timeout=timeout, reasoning_effort="medium")
    pillars = _parse_json_array(raw)
    return [p for p in pillars if isinstance(p, dict) and p.get("title")]


def gen_clusters(pillar: dict, context_short: str, n: int = 10, timeout: int = 300) -> list:
    sys_p = _ROLE + _CLUSTER_INSTR.format(
        n=n, context=context_short,
        pillar_title=pillar.get("title", ""),
        pillar_intent=pillar.get("intent", ""),
        pillar_layer=pillar.get("layer", ""),
        pillar_cat=pillar.get("target_category", ""))
    raw = ai_provider.call_ai(
        sys_p, "Trả JSON array bài cluster như mô tả. Tiếng Việt.",
        timeout=timeout, reasoning_effort="medium")
    clusters = _parse_json_array(raw)
    return [c for c in clusters if isinstance(c, dict) and c.get("title")]


# ──────────────────────────────── slug + DB ────────────────────────────────
def slugify(text: str) -> str:
    t = unicodedata.normalize("NFD", text or "")
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = t.replace("đ", "d").replace("Đ", "D").lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:90] or "bai-viet"


def _insert_pillar(conn, p: dict) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """INSERT INTO blog_pillars
           (title, intent, content_group, audience, reason, priority, target_category, layer, cluster_count, created_at)
           VALUES (?,?,?,?,?,?,?,?,0,?)""",
        (p.get("title", "").strip(), p.get("intent", ""), p.get("content_group", ""),
         p.get("audience", ""), p.get("reason", ""), p.get("priority", ""),
         p.get("target_category", ""), p.get("layer", ""), now))
    return cur.lastrowid


def _unique_blog_url(conn, target_blog: str, slug: str) -> str:
    base = f"https://sintech.vn/blogs/{target_blog or 'news'}/{slug}"
    url = base
    i = 2
    while conn.execute("SELECT 1 FROM blog_jobs WHERE blog_url=?", (url,)).fetchone():
        url = f"{base}-{i}"
        i += 1
    return url


def _insert_cluster_job(conn, pillar_id: int, pillar: dict, c: dict):
    """Insert 1 cluster job. Trả job_id (lastrowid) hoặc None nếu thiếu title."""
    now = datetime.now().isoformat(timespec="seconds")
    title = (c.get("title") or "").strip()
    if not title:
        return None
    slug = slugify(title)
    target_blog = (c.get("target_blog") or "news").strip()
    if target_blog not in ("huong-dan", "news"):
        target_blog = "news"
    url = _unique_blog_url(conn, target_blog, slug)
    layer = (c.get("layer") or pillar.get("layer") or "").strip()
    is_ext = 1 if c.get("is_external") else 0
    cur = conn.execute(
        """INSERT INTO blog_jobs
           (blog_url, handle, article_title, status, created_at, updated_at,
            pillar_id, pillar, keyword, intent, content_layer, unique_angle,
            internal_link_hint, priority, article_type, is_external, source, target_blog)
           VALUES (?,?,?,'pending',?,?,?,?,?,?,?,?,?,?,?,?,'ai_pillar',?)""",
        (url, slug, title, now, now,
         pillar_id, pillar.get("title", ""), c.get("keyword", ""), c.get("intent", ""),
         layer, c.get("unique_angle", ""), c.get("internal_link", ""),
         c.get("priority", ""), c.get("article_type", ""), is_ext, target_blog))
    return cur.lastrowid


def generate_plan(n_pillars: int = 12, clusters_per_pillar: int = 10, progress=None) -> dict:
    """Chạy full: gen pillars → gen clusters từng pillar → seed DB. progress(dict) optional callback."""
    def _p(**kw):
        if progress:
            try:
                progress(kw)
            except Exception:
                pass

    ctx = build_context()
    _p(phase="pillars", msg=f"Gen {n_pillars} pillar (data: {ctx['n_collections']} cate, {ctx['n_keywords']} kw)...")
    pillars = gen_pillars(ctx["text"], n=n_pillars)
    _p(phase="pillars_done", n_pillars=len(pillars))

    result = {"n_pillars": len(pillars), "n_clusters": 0, "jobs_created": 0,
              "pillars": [], "job_ids": [], "errors": []}
    conn = db.get_conn()
    try:
        for i, p in enumerate(pillars, 1):
            pid = _insert_pillar(conn, p)
            conn.commit()
            _p(phase="clusters", pillar_idx=i, pillar_total=len(pillars),
               pillar_title=p.get("title", ""))
            try:
                clusters = gen_clusters(p, ctx["text_short"], n=clusters_per_pillar)
            except Exception as e:
                result["errors"].append(f"Pillar '{p.get('title','')[:40]}': {str(e)[:120]}")
                clusters = []
            created = 0
            for c in clusters:
                try:
                    jid = _insert_cluster_job(conn, pid, p, c)
                    if jid:
                        created += 1
                        result["job_ids"].append(jid)
                except Exception as e:
                    result["errors"].append(f"Cluster '{c.get('title','')[:40]}': {str(e)[:80]}")
            conn.execute("UPDATE blog_pillars SET cluster_count=? WHERE id=?", (created, pid))
            conn.commit()
            result["n_clusters"] += len(clusters)
            result["jobs_created"] += created
            result["pillars"].append({"id": pid, "title": p.get("title", ""),
                                      "layer": p.get("layer", ""), "clusters": created})
            _p(phase="pillar_done", pillar_idx=i, created=created)
    finally:
        conn.close()
    _p(phase="done", **{k: result[k] for k in ("n_pillars", "n_clusters", "jobs_created")})
    return result


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(HERE))
    ctx = build_context()
    print(f"Context: {ctx['n_collections']} collections, {ctx['n_keywords']} keywords")
    print("--- gen 3 pillars (smoke) ---")
    ps = gen_pillars(ctx["text"], n=3)
    print(f"Got {len(ps)} pillars:")
    for p in ps:
        print(f"  [{p.get('layer')}] {p.get('title')} -> {p.get('target_category')}")
    if ps:
        print("--- gen clusters for pillar[0] ---")
        cs = gen_clusters(ps[0], ctx["text_short"], n=5)
        print(f"Got {len(cs)} clusters:")
        for c in cs:
            print(f"  [{c.get('layer')}/{c.get('article_type')}] {c.get('title')}")
