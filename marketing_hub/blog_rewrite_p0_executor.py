# -*- coding: utf-8 -*-
"""P9 — BLOG P0 QUICKWIN EXECUTOR (preview-only, local).

Xử lý trọn 10 bài P0 từ BLOG_PERFORMANCE_P0_ACTION_PLAN:
- AUTO_SAFE_CONTENT: tự clean HTML legacy + table responsive + remove broken img
  + lazy-load (giữ ảnh LCP) qua draft version MỚI (không overwrite).
- IMAGE_TASK: xuất task ảnh chi tiết (KHÔNG upload/rehost).
- THEME_ONLY: tách cho code team (không sửa article).
- MANUAL_REVIEW: giữ tay.

TUYỆT ĐỐI: KHÔNG PUT Haravan, KHÔNG upload, KHÔNG sửa theme, KHÔNG commit.
Tái dùng helper P3-P5: gen.sanitize_html / quality_metrics, images.audit_body_images,
verify.compare_article_signatures. Draft lưu approval_status='p0_preview' (out-of-band,
KHÔNG lọt luồng apply plagiarism vốn dùng draft_ready/approved_local).
"""
import csv, json, re
from pathlib import Path
from bs4 import BeautifulSoup

import db
import blog_rewrite as br
import blog_rewrite_gen as gen
import blog_rewrite_images as images
import blog_rewrite_verify as verify

DOCS = Path(__file__).parent.parent / "docs"

# ── input files (đọc đúng 5 file P0) ──
F_PLAN_MD = DOCS / "BLOG_PERFORMANCE_P0_ACTION_PLAN.md"
F_PLAN_CSV = DOCS / "blog_performance_p0_action_plan.csv"
F_IMAGE_CSV = DOCS / "blog_performance_p0_image_tasks.csv"
F_CONTENT_CSV = DOCS / "blog_performance_p0_content_tasks.csv"
F_HANDOFF_MD = DOCS / "BLOG_TEMPLATE_CODE_HANDOFF.md"

# ── output files ──
O_PREVIEW_MD = DOCS / "BLOG_PERFORMANCE_P0_EXECUTOR_PREVIEW.md"
O_ITEMS_CSV = DOCS / "blog_performance_p0_executor_items.csv"
O_IMAGE_CSV = DOCS / "blog_performance_p0_image_execution_tasks.csv"
O_THEME_CSV = DOCS / "blog_performance_p0_theme_handoff.csv"
O_MANUAL_CSV = DOCS / "blog_performance_p0_manual_review.csv"

THIN_MIN_WORDS = 150
TEXT_PRESERVE_MIN = 0.92  # body sau clean phải giữ >=92% số từ gốc

GROUP_AUTO = "AUTO_SAFE_CONTENT"
GROUP_IMAGE = "IMAGE_TASK"
GROUP_THEME = "THEME_ONLY"
GROUP_MANUAL = "MANUAL_REVIEW"


# ═══════════════════════ load inputs ═══════════════════════
def _read_csv(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_p0():
    """Đọc 5 file P0 → list 10 bài (đã gộp content tasks + image tasks)."""
    plan = _read_csv(F_PLAN_CSV)
    content_rows = _read_csv(F_CONTENT_CSV)
    image_rows = _read_csv(F_IMAGE_CSV)

    content_by_aid = {}
    for r in content_rows:
        content_by_aid.setdefault(str(r["article_id"]), []).append(
            {"type": r["task_type"], "detail": r["detail"]})
    image_by_aid = {}
    for r in image_rows:
        image_by_aid.setdefault(str(r["article_id"]), []).append(r)

    out = []
    for r in plan:
        aid = str(r["article_id"])
        ctasks = content_by_aid.get(aid, [])
        out.append({
            "p0_rank": int(r["p0_rank"]),
            "article_id": int(aid),
            "title": r["title"],
            "url": r["url"],
            "traffic": r["traffic"],
            "mobile_perf": r["mobile_perf"],
            "lcp": r["lcp"],
            "cls": r["cls"],
            "hero_bytes": r["hero_bytes"],
            "broken_images": int(r["broken_images"] or 0),
            "heavy_images": int(r["heavy_images"] or 0),
            "primary_issue": r["primary_issue"],
            "secondary_issue": r["secondary_issue"],
            "owner": r["owner"],
            "effort": r["effort"],
            "expected_impact": r["expected_impact"],
            "quickwin_score": r["quickwin_score"],
            "content_tasks": ctasks,
            "image_tasks": image_by_aid.get(aid, []),
        })
    out.sort(key=lambda x: x["p0_rank"])
    return out


# ═══════════════════════ classify ═══════════════════════
def classify_group(bai, candidate, draft):
    """Phân 1 trong 4 nhóm theo spec (data-driven)."""
    # MANUAL_REVIEW: reverse_copy / không lấy được body / cần review tay
    if bai["primary_issue"] == "NEED_MANUAL_REVIEW":
        return GROUP_MANUAL
    if candidate and candidate.get("status") == "reverse_copy_defense":
        return GROUP_MANUAL
    has_body = bool(draft and (draft.get("original_body_html") or "").strip())
    if not has_body:
        return GROUP_MANUAL
    if any(t["type"] == "review tay" for t in bai["content_tasks"]):
        return GROUP_MANUAL
    # AUTO_SAFE_CONTENT: có content task tự xử lý được (clean/table/dom)
    auto_types = {"clean HTML legacy", "table responsive", "giảm DOM"}
    if any(t["type"] in auto_types for t in bai["content_tasks"]):
        return GROUP_AUTO
    # còn lại: owner THEME_CODE / lỗi global → THEME_ONLY
    return GROUP_THEME


# ═══════════════════════ auto-safe clean ═══════════════════════
def _norm_src(u):
    return (u or "").split("?")[0].strip().lower()


def _bytes_of(size_str):
    """'160KB' → 160000; 'CHẾT'/'' → None."""
    m = re.search(r"(\d+)\s*KB", size_str or "", re.I)
    if m:
        return int(m.group(1)) * 1000
    return None


def auto_safe_clean(base_body, broken_srcs):
    """Trả (cleaned_html, stats). Chỉ sửa MARKUP an toàn — KHÔNG đổi text."""
    broken_norm = {_norm_src(s) for s in broken_srcs if s}
    # 1. sanitize_html: clean legacy attr/tag, whitelist, table responsive+border, flag external
    cleaned, ext_links, ext_imgs = gen.sanitize_html(base_body)
    soup = BeautifulSoup(cleaned, "lxml")

    removed_broken = 0
    lazy_added = 0
    lcp_kept = 0
    imgs = soup.find_all("img")
    first = True
    for img in imgs:
        src = img.get("src", "")
        if _norm_src(src) in broken_norm:
            img.decompose()
            removed_broken += 1
            continue
        if first:
            # ảnh đầu = LCP → KHÔNG lazy + fetchpriority=high
            img["fetchpriority"] = "high"
            if img.has_attr("loading"):
                del img["loading"]
            lcp_kept += 1
            first = False
        else:
            img["loading"] = "lazy"
            lazy_added += 1

    tables = soup.find_all("table")
    body = soup.body
    out = "".join(str(c) for c in body.contents) if body else str(soup)
    out = out.strip()
    stats = {
        "removed_broken": removed_broken,
        "lazy_added": lazy_added,
        "lcp_kept": lcp_kept,
        "tables_wrapped": len(tables),
        "external_links": ext_links,
        "external_images": ext_imgs,
    }
    return out, stats


# ═══════════════════════ gates / acceptance ═══════════════════════
def _strip_noncontent(html):
    """Bỏ script/style/iframe để đo text HIỂN THỊ (legacy HTML hay có <style> chứa CSS)."""
    s = BeautifulSoup(html or "", "lxml")
    for bad in s(["script", "style", "iframe", "head"]):
        bad.decompose()
    return str(s)


def run_gates(base_body, cleaned_body, stats):
    """Chấm acceptance per bài. Trả dict gate + pass/blocked."""
    # so text HIỂN THỊ (đã bỏ script/style) — tránh phạt oan khi gỡ CSS/JS rác
    qm = gen.quality_metrics(_strip_noncontent(base_body), cleaned_body)
    wo, wd = qm["word_count_original"], qm["word_count_draft"]
    preserve = round(wd / wo, 4) if wo else 0.0

    # image gate: re-audit ảnh trong body đã clean (KHÔNG check availability → tránh flood host)
    audit, _gate_summary = images.audit_body_images(cleaned_body, check_availability=False)
    broken_after = sum(1 for a in audit if a.get("apply_gate_status") == "BLOCK_DEAD_IMAGE")
    external_imgs = sum(1 for a in audit if a.get("source_class") != "SINTECH_OWNED")
    blocked_img = sum(1 for a in audit if str(a.get("apply_gate_status", "")).startswith("BLOCK"))

    low = cleaned_body.lower()
    dangerous = ("<script" in low) or ("<iframe" in low)

    gate = {
        "html_safety": "PASS" if not dangerous else "FAIL",
        "semantic_preserved": preserve >= TEXT_PRESERVE_MIN,
        "text_preserve_ratio": preserve,
        "word_count_original": wo,
        "word_count_draft": wd,
        "broken_inline_after": broken_after,
        "tables_responsive": stats["tables_wrapped"],
        "competitor_href": _competitor_links(stats["external_links"]),
        "external_images_in_body": external_imgs,
        "blocked_image": blocked_img,
        "thin_content": wd < THIN_MIN_WORDS,
        "renders": bool(cleaned_body.strip()),
    }
    # acceptance: HTML safe + semantic giữ + no broken + not thin + render được + no competitor href
    accept = (
        gate["html_safety"] == "PASS"
        and gate["semantic_preserved"]
        and gate["broken_inline_after"] == 0
        and not gate["thin_content"]
        and gate["renders"]
        and not gate["competitor_href"]
    )
    gate["accept"] = accept
    # blocked-image: clean OK nhưng còn ảnh đối thủ/news/unknown cần xử lý tay
    gate["status"] = ("blocked_image" if (accept and blocked_img > 0)
                      else ("preview_ready" if accept else "blocked"))
    return gate


def _competitor_links(ext_links):
    bad = ("gearvn", "cellphones", "fptshop", "thegioididong", "hoanghamobile",
           "memoryzone", "phongvu", "anphat", "hanoicomputer", "tncstore", "gearvn")
    for u in ext_links or []:
        ul = (u or "").lower()
        if any(b in ul for b in bad):
            return True
    return False


# ═══════════════════════ save p0 draft (no overwrite) ═══════════════════════
def _existing_p0_draft(cid):
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT * FROM blog_rewrite_drafts WHERE candidate_id=? AND approval_status='p0_preview' "
        "ORDER BY version DESC LIMIT 1", (cid,)).fetchall()
    conn.close()
    return dict(rows[0]) if rows else None


def save_p0_draft(candidate, base_body, cleaned_body, meta):
    """Insert draft version MỚI (không overwrite). approval_status='p0_preview'."""
    cid = candidate["id"]
    conn = db.get_conn()
    try:
        ver = (conn.execute("SELECT COALESCE(MAX(version),0) FROM blog_rewrite_drafts WHERE candidate_id=?",
                            (cid,)).fetchone()[0] or 0) + 1
        qjson = json.dumps({"p0_executor": True, **meta}, ensure_ascii=False)
        cur = conn.execute(
            """INSERT INTO blog_rewrite_drafts
               (candidate_id, version, original_title, original_body_html, original_handle,
                original_content_hash, draft_title, draft_body_html, quality_json, approval_status)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (cid, ver, candidate.get("title"), base_body, candidate.get("handle"),
             candidate.get("content_hash"), candidate.get("title"), cleaned_body, qjson, "p0_preview"))
        did = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    br.record_event("p0_quickwin_draft", candidate_id=cid, draft_id=did,
                    detail={"version": ver, "group": meta.get("group")})
    return did, ver


# ═══════════════════════ orchestrate ═══════════════════════
def _candidate_by_article(aid):
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM blog_rewrite_candidates WHERE article_id=?", (aid,)).fetchone()
    conn.close()
    return dict(r) if r else None


def run_preview(force=False):
    """Chạy executor cho 10 bài P0. Tạo draft local cho nhóm AUTO_SAFE. KHÔNG PUT."""
    items = []
    for bai in load_p0():
        aid = bai["article_id"]
        cand = _candidate_by_article(aid)
        draft = br.latest_draft_for_candidate(cand["id"]) if cand else None
        group = classify_group(bai, cand, draft)

        rec = {
            **{k: bai[k] for k in ("p0_rank", "article_id", "title", "url", "traffic",
                                   "primary_issue", "secondary_issue", "owner", "effort",
                                   "expected_impact", "quickwin_score")},
            "candidate_id": cand["id"] if cand else None,
            "group": group,
            "body_source": None,
            "live_hash": cand.get("content_hash") if cand else None,
            "local_draft_id": None,
            "local_draft_hash": None,
            "image_count": len(bai["image_tasks"]),
            "image_tasks_actionable": _actionable_images(bai["image_tasks"]),
            "status": "",
            "gate": {},
            "auto_actions": [],
            "manual_actions": [],
        }

        if group == GROUP_AUTO:
            base = draft.get("original_body_html") or ""
            broken_srcs = [r["img_url"] for r in bai["image_tasks"] if r.get("status") == "broken"]
            # idempotent: reuse p0 draft trừ khi force
            existing = None if force else _existing_p0_draft(cand["id"])
            cleaned, stats = auto_safe_clean(base, broken_srcs)
            gate = run_gates(base, cleaned, stats)
            if existing and not force:
                did, ver = existing["id"], existing["version"]
            else:
                meta = {"group": group, "gate": gate, "stats": {
                    k: stats[k] for k in ("removed_broken", "lazy_added", "lcp_kept", "tables_wrapped")}}
                did, ver = save_p0_draft(cand, base, cleaned, meta)
            rec["body_source"] = "original_body_html (live gốc)"
            rec["local_draft_id"] = did
            rec["local_draft_hash"] = br._content_hash(cleaned)
            rec["status"] = gate["status"]
            rec["gate"] = gate
            rec["auto_actions"] = _auto_action_labels(bai, stats)
            rec["manual_actions"] = _manual_action_labels(bai, gate)
        elif group == GROUP_THEME:
            rec["status"] = "theme_only"
            rec["body_source"] = (draft.get("original_body_html") and "original (không sửa)") or "—"
            rec["manual_actions"] = ["→ THEME_CODE handoff (xem blog_performance_p0_theme_handoff.csv)"]
        elif group == GROUP_MANUAL:
            rec["status"] = "manual_review"
            rec["manual_actions"] = [t["detail"] for t in bai["content_tasks"]] or \
                ["Không lấy được body / reverse_copy — review tay trong editor"]
        items.append(rec)
    return items


def _actionable_images(image_tasks):
    n = 0
    for r in image_tasks:
        st = r.get("status", "")
        act = enum_image_action(r)
        if st in ("broken", "heavy") or act in ("RESIZE", "REMOVE_BROKEN", "MANUAL_REPLACE"):
            n += 1
    return n


def _auto_action_labels(bai, stats):
    out = []
    if stats["tables_wrapped"]:
        out.append(f"table responsive ×{stats['tables_wrapped']}")
    out.append("clean HTML legacy + sanitize")
    if stats["removed_broken"]:
        out.append(f"gỡ {stats['removed_broken']} ảnh chết")
    if stats["lazy_added"]:
        out.append(f"loading=lazy ×{stats['lazy_added']} (giữ LCP×{stats['lcp_kept']})")
    return out


def _manual_action_labels(bai, gate):
    out = []
    if gate.get("external_images_in_body"):
        out.append(f"{gate['external_images_in_body']} ảnh external/đối thủ → image task (re-host tay)")
    if bai["heavy_images"]:
        out.append(f"{bai['heavy_images']} ảnh nặng → resize (image task)")
    if "SET_DIMENSIONS" not in str(out):
        out.append("set width/height ảnh → image task (cần metadata)")
    return out


# ═══════════════════════ image action enum ═══════════════════════
def enum_image_action(r):
    """Map 1 image task row → action enum chuẩn spec."""
    st = r.get("status", "")
    role = r.get("role", "")
    src = r.get("img_url", "")
    bytes_ = _bytes_of(r.get("size", ""))
    is_external = not images.is_sintech_image(src)
    if st == "broken":
        return "REMOVE_BROKEN"
    if st == "heavy" or (bytes_ and bytes_ > 300000):
        return "RESIZE"
    if is_external:
        return "MANUAL_REPLACE"
    if role == "hero":
        return "KEEP_LCP_NO_LAZY"
    return "SET_LAZYLOAD"


def image_target(r):
    role = r.get("role", "")
    if role == "hero":
        return "1200×675 (hoặc 1200×628) · ưu tiên WebP · ≤180KB"
    return "WebP · cảnh báo >300KB · urgent >700KB"


# ═══════════════════════ summary / items for UI ═══════════════════════
def summary():
    items = run_preview(force=False)
    kpi = {
        "p0_total": len(items),
        "auto_safe": sum(1 for i in items if i["group"] == GROUP_AUTO),
        "image_tasks": sum(1 for i in items if i["image_tasks_actionable"] > 0),
        "theme_only": sum(1 for i in items if i["group"] == GROUP_THEME),
        "manual_review": sum(1 for i in items if i["group"] == GROUP_MANUAL),
        "preview_ready": sum(1 for i in items if i["status"] == "preview_ready"),
        "blocked_image": sum(1 for i in items if i["status"] == "blocked_image"),
    }
    return {"kpi": kpi, "items": items}


# ═══════════════════════ exports ═══════════════════════
def _w(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(header)
        wr.writerows(rows)
    return len(rows)


def export_all(items=None):
    if items is None:
        items = run_preview(force=False)
    p0 = load_p0()
    by_rank = {b["p0_rank"]: b for b in p0}
    counts = {}

    # 1. executor items
    h = ["p0_rank", "article_id", "title", "url", "owner", "group", "primary_issue",
         "secondary_issue", "body_source", "live_hash", "local_draft_id", "local_draft_hash",
         "image_count", "image_tasks_actionable", "auto_actions", "manual_actions",
         "html_safety", "semantic_preserved", "text_preserve", "broken_after",
         "tables_responsive", "blocked_image", "status"]
    rows = []
    for i in items:
        g = i.get("gate", {})
        rows.append([
            i["p0_rank"], i["article_id"], i["title"], i["url"], i["owner"], i["group"],
            i["primary_issue"], i["secondary_issue"], i["body_source"] or "", i["live_hash"] or "",
            i["local_draft_id"] or "", i["local_draft_hash"] or "", i["image_count"],
            i["image_tasks_actionable"], "; ".join(i["auto_actions"]), "; ".join(i["manual_actions"]),
            g.get("html_safety", ""), g.get("semantic_preserved", ""), g.get("text_preserve_ratio", ""),
            g.get("broken_inline_after", ""), g.get("tables_responsive", ""),
            g.get("blocked_image", ""), i["status"],
        ])
    counts["items"] = _w(O_ITEMS_CSV, h, rows)

    # 2. image execution tasks
    h = ["p0_rank", "article_id", "article_title", "article_url", "img_index", "role",
         "image_url", "is_external", "bytes", "width", "height", "issue", "action", "target"]
    rows = []
    for b in p0:
        for r in b["image_tasks"]:
            ext = "yes" if not images.is_sintech_image(r.get("img_url", "")) else "no"
            rows.append([
                b["p0_rank"], b["article_id"], b["title"], b["url"], r.get("img_index", ""),
                r.get("role", ""), r.get("img_url", ""), ext, r.get("size", ""), "", "",
                r.get("status", ""), enum_image_action(r), image_target(r),
            ])
    counts["image"] = _w(O_IMAGE_CSV, h, rows)

    # 3. theme handoff
    h = ["p0_rank", "article_id", "title", "url", "traffic", "global_issue", "evidence",
         "handoff_ref", "priority", "qa_after_fix"]
    rows = []
    for i in items:
        if i["group"] != GROUP_THEME:
            continue
        b = by_rank[i["p0_rank"]]
        rows.append([
            i["p0_rank"], i["article_id"], i["title"], i["url"], i["traffic"],
            f"{b['primary_issue']} / {b['secondary_issue']}".strip(" /"),
            f"mPerf {b['mobile_perf']} · LCP {int(b['lcp'])/1000:.1f}s · CLS {b['cls']}",
            "BLOG_TEMPLATE_CODE_HANDOFF #1 (unused JS), #2 (unused CSS), #5 (width/height/aspect-ratio)",
            "P0", "Đo lại CLS/Perf mobile ở /seo/cwv đợt quét mới (so wk hiện tại)",
        ])
    counts["theme"] = _w(O_THEME_CSV, h, rows)

    # 4. manual review
    h = ["p0_rank", "article_id", "title", "url", "reason", "suggested_manual_action"]
    rows = []
    for i in items:
        if i["group"] != GROUP_MANUAL:
            continue
        rows.append([
            i["p0_rank"], i["article_id"], i["title"], i["url"],
            "; ".join(i["manual_actions"]) or "reverse_copy / không lấy được body",
            "Mở editor Haravan kiểm tra trực tiếp; không sửa tự động (nguy cơ mất nội dung)",
        ])
    counts["manual"] = _w(O_MANUAL_CSV, h, rows)

    _write_preview_md(items, counts)
    counts["preview_md"] = 1
    return counts


def _write_preview_md(items, counts):
    k = summary()["kpi"]
    L = []
    L.append("# BLOG PERFORMANCE — P0 QUICKWIN EXECUTOR (PREVIEW, local-only)\n")
    L.append("> Nối tiếp `BLOG_PERFORMANCE_P0_ACTION_PLAN.md`. Preview LOCAL — **PUT=0, upload=0, "
             "theme edits=0, no commit/push/deploy**. Dừng sau preview để review.\n")
    L.append("## Coverage\n")
    L.append(f"- P0 total: **{k['p0_total']}** · auto-safe **{k['auto_safe']}** · image-task **{k['image_tasks']}** "
             f"· theme-only **{k['theme_only']}** · manual-review **{k['manual_review']}**")
    L.append(f"- preview-ready **{k['preview_ready']}** · blocked-image **{k['blocked_image']}**\n")
    L.append("## Bảng 10 bài P0\n")
    L.append("| P0# | Title | Group | Local draft | Auto fix | Image task | Status |")
    L.append("|---|---|---|---|---|---|---|")
    for i in items:
        L.append(f"| {i['p0_rank']} | {i['title'][:34]} | {i['group']} | "
                 f"{i['local_draft_id'] or '—'} | {'; '.join(i['auto_actions']) or '—'} | "
                 f"{i['image_tasks_actionable'] or '—'} | {i['status']} |")
    L.append("\n## Chi tiết nhóm AUTO_SAFE_CONTENT\n")
    for i in items:
        if i["group"] != GROUP_AUTO:
            continue
        g = i["gate"]
        L.append(f"### P0#{i['p0_rank']} — {i['title']}")
        L.append(f"- article `{i['article_id']}` · draft local #{i['local_draft_id']} · {i['url']}")
        L.append(f"- auto: {'; '.join(i['auto_actions'])}")
        L.append(f"- gate: HTML {g['html_safety']} · giữ text {g['text_preserve_ratio']*100:.1f}% "
                 f"({g['word_count_draft']}/{g['word_count_original']} từ) · broken sau {g['broken_inline_after']} "
                 f"· table responsive {g['tables_responsive']} · blocked-image {g['blocked_image']} → **{i['status']}**")
        if i["manual_actions"]:
            L.append(f"- còn lại (tay): {'; '.join(i['manual_actions'])}")
        L.append("")
    L.append("## Image tasks (tóm tắt) — xem `blog_performance_p0_image_execution_tasks.csv`\n")
    L.append("## Theme handoff — xem `blog_performance_p0_theme_handoff.csv`\n")
    L.append("## Manual review — xem `blog_performance_p0_manual_review.csv`\n")
    L.append("## Exports")
    for n in ("BLOG_PERFORMANCE_P0_EXECUTOR_PREVIEW.md", "blog_performance_p0_executor_items.csv",
              "blog_performance_p0_image_execution_tasks.csv", "blog_performance_p0_theme_handoff.csv",
              "blog_performance_p0_manual_review.csv"):
        L.append(f"- {n}")
    L.append("\n## Safety\npreview local only · PUT=0 · upload=0 · rehost=0 · theme edits=0 · no commit · no push · no deploy")
    O_PREVIEW_MD.write_text("\n".join(L), encoding="utf-8")
