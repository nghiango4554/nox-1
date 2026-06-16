# -*- coding: utf-8 -*-
"""Blog Rewrite — P5A APPLY PREVIEW (dry-run, KHÔNG upload/PUT).

Image rights audit + rehost dry-run plan + content-hash conflict check +
live payload backup design. TẤT CẢ read-only/local. Apply thật = P5B.
"""
import json, re, hashlib
from pathlib import Path
from urllib.parse import urlparse
import requests, urllib3
import db

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_CFG = json.loads((Path(__file__).parent.parent / "state" / "haravan_token.json").read_text(encoding="utf-8"))

_OWN = ("hstatic.net", "sintech.vn", "myharavan", "haravan")
_COMPETITOR = ("gearvn", "fptshop", "cellphones", "memoryzone", "tgdd", "thegioididong",
               "dienmayxanh", "hacom", "hoangha", "anphat", "phongvu", "didongviet",
               "phucanh", "maytinhcdc", "nguyenkim")
_NEWS = ("genk", "quantrimang", "tinhte", "vnexpress", "vnecdn", "thanhnien", "kenh14",
         "cafef", "sforum", "futurecdn", "wccftech", "pcworld", "pcmag", "techcrunch",
         "techradar", "notebookcheck", "makeuseof")
_OFFICIAL = ("intel.com", "asus.com", "nvidia.com", "amd.com", "msi.com", "gigabyte",
             "corsair", "logitech", "razer", "samsung.com", "kingston", "westerndigital",
             "seagate", "apple.com", "microsoft.com", "dell.com", "hp.com", "lenovo",
             "acer.com", "coolermaster", "noctua", "asrock")


def _classify_rights(src, alt):
    host = (urlparse(src).hostname or "").lower()
    fn = src.split("?")[0].rsplit("/", 1)[-1].lower()
    low = (src + " " + (alt or "")).lower()
    brand_fn = sorted(set(b for b in _COMPETITOR if b in fn))
    brand_alt = sorted(set(b for b in _COMPETITOR if b in (alt or "").lower()))
    brand_url = sorted(set(b for b in _COMPETITOR if b in src.lower()))
    is_own = any(o in host for o in _OWN)
    if is_own:
        if brand_fn or brand_alt:
            rights, action, eligible = "HARAVAN_EXISTING", "REHOST_ALLOWED_LATER", True  # ảnh mình, đổi tên bỏ brand
        else:
            rights, action, eligible = "HARAVAN_EXISTING", "KEEP_EXISTING", False
    elif any(b in low for b in _COMPETITOR):
        rights, action, eligible = "COMPETITOR_SOURCE", "REPLACE_WITH_OFFICIAL_IMAGE", False
    elif any(b in low for b in _NEWS):
        rights, action, eligible = "NEWS_MEDIA_SOURCE", "CREATE_ORIGINAL_IMAGE", False
    elif any(b in host for b in _OFFICIAL):
        rights, action, eligible = "OFFICIAL_MANUFACTURER", "REHOST_ALLOWED_LATER", True
    elif host:
        rights, action, eligible = "UNKNOWN_SOURCE", "MANUAL_REVIEW", False
    else:
        rights, action, eligible = "MANUAL_REVIEW", "MANUAL_REVIEW", False
    return {
        "hostname": host, "filename": fn, "alt": alt or "",
        "is_haravan": is_own, "is_external": bool(host) and not is_own,
        "brand_in_filename": brand_fn, "brand_in_alt": brand_alt, "brand_in_url": brand_url,
        "watermark_suspected": bool(brand_fn or brand_alt),
        "rights_status": rights, "recommended_action": action, "eligible_for_upload": eligible,
    }


def image_rights_audit(draft):
    body = draft.get("draft_body_html") or ""
    out = []
    for i, tag in enumerate(re.findall(r"<img[^>]+>", body, re.I)):
        sm = re.search(r'src="([^"]+)"', tag, re.I); am = re.search(r'alt="([^"]*)"', tag, re.I)
        if not sm:
            continue
        info = _classify_rights(sm.group(1), am.group(1) if am else "")
        info.update({"position": i, "original_src": sm.group(1)})
        out.append(info)
    return out


def build_image_rehost_plan(draft_id, refresh=True):
    """Dry-run rehost plan + rights. KHÔNG tải/upload. planned_new_url=null."""
    conn = db.get_conn()
    d = conn.execute("SELECT candidate_id, draft_body_html, image_mapping_json FROM blog_rewrite_drafts WHERE id=?", (draft_id,)).fetchone()
    if not d:
        conn.close(); return {"ok": False, "error": "draft không tồn tại"}
    d = dict(d)
    if d.get("image_mapping_json") and not refresh:
        conn.close(); return {"ok": True, "plan": json.loads(d["image_mapping_json"])}
    audit = image_rights_audit(d)
    plan = []
    for a in audit:
        planned_fn = a["filename"]
        for b in a["brand_in_filename"]:
            planned_fn = planned_fn.replace(b, "sintech")
        plan.append({
            "original_src": a["original_src"], "hostname": a["hostname"], "filename": a["filename"],
            "rights_status": a["rights_status"], "recommended_action": a["recommended_action"],
            "eligible_for_upload": a["eligible_for_upload"],
            "planned_filename": planned_fn if a["eligible_for_upload"] else None,
            "planned_alt": a["alt"], "planned_new_url": None, "status": "dry_run",
        })
    conn.execute("UPDATE blog_rewrite_drafts SET image_mapping_json=? WHERE id=?",
                 (json.dumps(plan, ensure_ascii=False), draft_id))
    conn.commit(); conn.close()
    return {"ok": True, "plan": plan,
            "summary": {"total": len(plan),
                        "eligible_upload": sum(1 for p in plan if p["eligible_for_upload"]),
                        "blocked": sum(1 for p in plan if not p["eligible_for_upload"] and p["recommended_action"] != "KEEP_EXISTING"),
                        "keep_existing": sum(1 for p in plan if p["recommended_action"] == "KEEP_EXISTING"),
                        "manual_review": sum(1 for p in plan if p["recommended_action"] == "MANUAL_REVIEW")}}


def _fetch_live_article(blog_id, article_id):
    H = {"Authorization": f"Bearer {_CFG['blog_access_token']}", "Accept": "application/json"}
    r = requests.get(f"{_CFG['open_api_base']}/blogs/{blog_id}/articles/{article_id}.json",
                     headers=H, verify=False, timeout=30)
    return r.status_code, (r.json().get("article", {}) if r.status_code == 200 else {})


def _hash_body(html):
    return hashlib.sha256(re.sub(r"\s+", " ", html or "").strip().encode("utf-8")).hexdigest()


def apply_preview(draft_id):
    """Conflict check + field availability. GET read-only. KHÔNG PUT. apply_enabled=False (P5A)."""
    conn = db.get_conn()
    d = conn.execute("SELECT * FROM blog_rewrite_drafts WHERE id=?", (draft_id,)).fetchone()
    if not d:
        conn.close(); return {"ok": False, "error": "draft không tồn tại"}
    d = dict(d)
    c = conn.execute("SELECT blog_id, article_id FROM blog_rewrite_candidates WHERE id=?", (d["candidate_id"],)).fetchone()
    conn.close()
    orig_hash = _hash_body(d.get("original_body_html") or "")
    try:
        code, art = _fetch_live_article(c["blog_id"], c["article_id"])
    except Exception as e:
        return {"ok": True, "phase": "P5A", "conflict_status": "READ_FAILED", "error": str(e)[:80], "apply_enabled": False}
    if code != 200 or not art:
        conflict = "MISSING_LIVE_ARTICLE"
        live_hash = ""
    else:
        live_hash = _hash_body(art.get("body_html") or "")
        conflict = "SAFE_TO_APPLY" if live_hash == orig_hash else "CONFLICT_LIVE_CHANGED"
    plan = build_image_rehost_plan(draft_id, refresh=True)
    psum = plan.get("summary", {})
    return {
        "ok": True, "phase": "P5A", "draft_id": draft_id, "article_id": c["article_id"],
        "conflict_status": conflict, "body_hash_original": orig_hash[:16], "body_hash_live": live_hash[:16],
        "fields_available": {"body_html": True, "title": True, "summary_html": True, "tags": True},
        "fields_default_selected": {"body_html": True, "title": False, "summary_html": False, "tags": False},
        "image_plan_status": "dry_run",
        "eligible_images": psum.get("eligible_upload", 0), "blocked_images": psum.get("blocked", 0),
        "manual_review_images": psum.get("manual_review", 0), "keep_existing_images": psum.get("keep_existing", 0),
        "apply_enabled": False,  # P5A: luôn False
    }


def backup_preview(draft_id):
    """Fetch live + build backup payload (KHÔNG PUT). Lưu live_backup_payload_json."""
    conn = db.get_conn()
    d = conn.execute("SELECT candidate_id FROM blog_rewrite_drafts WHERE id=?", (draft_id,)).fetchone()
    if not d:
        conn.close(); return {"ok": False, "error": "draft không tồn tại"}
    c = conn.execute("SELECT blog_id, article_id FROM blog_rewrite_candidates WHERE id=?", (d["candidate_id"],)).fetchone()
    try:
        code, art = _fetch_live_article(c["blog_id"], c["article_id"])
    except Exception as e:
        conn.close(); return {"ok": False, "error": f"fetch live fail: {str(e)[:60]}"}
    if code != 200:
        conn.close(); return {"ok": False, "error": f"live article HTTP {code}"}
    payload = {
        "article_id": art.get("id"), "blog_id": c["blog_id"], "title": art.get("title"),
        "body_html": art.get("body_html"), "summary_html": art.get("summary_html"),
        "tags": art.get("tags"), "handle": art.get("handle"), "published": art.get("published"),
        "published_at": art.get("published_at"), "image": art.get("image"),
        "updated_at": art.get("updated_at"), "hash": _hash_body(art.get("body_html") or ""),
        "backup_created_at": "preview",
    }
    conn.execute("UPDATE blog_rewrite_drafts SET live_backup_payload_json=? WHERE id=?",
                 (json.dumps(payload, ensure_ascii=False), draft_id))
    conn.commit(); conn.close()
    return {"ok": True, "phase": "P5A", "backup_status": "saved_local_preview",
            "article_id": payload["article_id"], "body_len": len(payload["body_html"] or ""),
            "hash": payload["hash"][:16]}
