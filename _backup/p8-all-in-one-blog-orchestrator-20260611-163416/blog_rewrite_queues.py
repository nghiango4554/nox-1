# -*- coding: utf-8 -*-
"""Blog Rewrite — phân DEFER thành 3 queue + đòi evergreen về AUTO (title + BODY).

Queue:
  AUTO       — evergreen/how-to/concept text-first (đòi lại, đưa về pipeline AUTO_LANE)
  VISUAL     — phụ thuộc ảnh/tutorial/screenshot → remediation ảnh trước
  NEWS       — tin/launch/driver/giá/tồn kho time-sensitive → web-verify hoặc bỏ
  FPS_BENCH  — game-config/FPS/benchmark số liệu → bỏ số không nguồn / HOLD
  REVIEW     — vẫn mơ hồ sau khi đọc body → xử tay

Đọc body từ draft.original_body_html nếu có, không thì GET live Haravan (read-only).
Lưu kết quả vào cột blog_rewrite_candidates.blog_queue. KHÔNG PUT, KHÔNG sửa nội dung.
"""
import re
import db
import blog_rewrite as br
import blog_rewrite_apply as ap
import blog_rewrite_autopilot as auto
import blog_rewrite_full_auto as fa


def _migrate():
    conn = db.get_conn()
    try:
        conn.execute("ALTER TABLE blog_rewrite_candidates ADD COLUMN blog_queue TEXT")
    except Exception:
        pass
    conn.commit(); conn.close()


def classify_queue(title, body, decision=None):
    """Route 1 bài vào queue dựa title + body. Ưu tiên loại disqualifying trước, rồi đòi evergreen."""
    t = (title or "").lower()
    hit = lambda kws: any(k in t for k in kws)
    fg = auto.fact_gate(body or "")
    vis = auto.visual_dependency(body or "")
    # 1. NEWS — time-sensitive/news (title rõ hoặc body nhiều keyword)
    news_body = (len(fg["news_keywords"]) + len(fg["time_keywords"])) >= 2 or fg["price_claims"] >= 3
    if hit(fa._LANE_NEWS) or news_body:
        return "NEWS"
    # 2. FPS/BENCH — số benchmark/fps hoặc game-config
    if fg["benchmark_claims"] > 0 or fg["fps_total"] > 3 or hit(fa._LANE_GAMECFG) or hit(fa._LANE_BENCH):
        return "FPS_BENCH"
    # 3. VISUAL — phụ thuộc ảnh (đã block / body visual / title tutorial)
    if decision == "BLOCKED_IMAGE" or vis["depends_on_images"] or hit(fa._LANE_VISUAL):
        return "VISUAL"
    # 4. đòi lại evergreen → AUTO
    if auto._is_evergreen(t) or hit(fa._LANE_EVERGREEN):
        return "AUTO"
    # 5. evergreen ngầm: body có cấu trúc (nhiều H2) + không news/fps/visual → coi là AUTO reclaim
    if len(re.findall(r"<h2", body or "", re.I)) >= 3:
        return "AUTO"
    return "REVIEW"


def _get_body(cid, article_id, blog_id):
    """Body để phân tích: ưu tiên draft.original_body_html, fallback GET live Haravan."""
    d = br.latest_draft_for_candidate(cid)
    if d and (d.get("original_body_html") or "").strip():
        return d["original_body_html"], "draft"
    try:
        code, art = ap._fetch_live_article(blog_id, article_id)
        if code == 200 and art:
            return art.get("body_html") or "", "live"
    except Exception:
        pass
    return "", "none"


def classify_all(emit=print):
    """Phân loại toàn bộ candidate chưa applied/eligible/non-reverse. Lưu blog_queue. Read-only Haravan."""
    _migrate()
    conn = db.get_conn(); conn.row_factory = __import__("sqlite3").Row
    rows = conn.execute("SELECT id, article_id, blog_id, title FROM blog_rewrite_candidates "
                        "WHERE rewrite_eligible=1 AND audit_reverse_copy=0 AND status!='applied'").fetchall()
    # latest decision map
    lat = {}
    for r in conn.execute("SELECT candidate_id, decision FROM blog_rewrite_autopilot_items WHERE decision IS NOT NULL ORDER BY id"):
        lat[r["candidate_id"]] = r["decision"]
    conn.close()
    from collections import Counter
    cnt = Counter(); src_cnt = Counter()
    for i, r in enumerate(rows, 1):
        body, src = _get_body(r["id"], r["article_id"], r["blog_id"])
        src_cnt[src] += 1
        q = classify_queue(r["title"], body, lat.get(r["id"]))
        cnt[q] += 1
        c2 = db.get_conn()
        c2.execute("UPDATE blog_rewrite_candidates SET blog_queue=? WHERE id=?", (q, r["id"]))
        c2.commit(); c2.close()
        if i % 20 == 0:
            emit(f"  ...{i}/{len(rows)}")
    return {"total": len(rows), "queues": dict(cnt), "body_source": dict(src_cnt)}


def queue_summary():
    conn = db.get_conn(); conn.row_factory = __import__("sqlite3").Row
    rows = conn.execute("SELECT blog_queue, COUNT(*) n, "
                        "SUM(CASE WHEN COALESCE(gsc_clicks_28d,0)>0 OR COALESCE(ga4_organic_sessions_28d,0)>0 THEN 1 ELSE 0 END) traf "
                        "FROM blog_rewrite_candidates WHERE rewrite_eligible=1 AND audit_reverse_copy=0 AND status!='applied' "
                        "GROUP BY blog_queue").fetchall()
    conn.close()
    return {r["blog_queue"] or "UNCLASSIFIED": {"total": r["n"], "with_traffic": r["traf"]} for r in rows}


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print("Phân loại 3 queue (title+body)...")
    res = classify_all()
    print("Kết quả:", res["queues"], "| nguồn body:", res["body_source"])
    print("Summary:", queue_summary())
