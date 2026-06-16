# -*- coding: utf-8 -*-
"""Blog Rewrite — P5A APPLY PREVIEW (dry-run, KHÔNG upload/PUT).

Image rights audit + rehost dry-run plan + content-hash conflict check +
live payload backup design. TẤT CẢ read-only/local. Apply thật = P5B.
"""
import json, re, hashlib, time
from pathlib import Path
from urllib.parse import urlparse
import requests, urllib3
import db
import blog_rewrite_images as imgs

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_CFG = json.loads((Path(__file__).parent.parent / "state" / "haravan_token.json").read_text(encoding="utf-8"))

SINTECH_STORE_ID = "200000860097"  # store Sintech trên Haravan (cdn/product/file.hstatic.net/200000860097/)


def is_sintech_image(src):
    """hstatic.net là CDN dùng chung MỌI shop Haravan → phải check store ID trong path,
    KHÔNG coi mọi hstatic = của Sintech (GEARVN store 1000026716 cũng trên hstatic)."""
    h = (urlparse(src).hostname or "").lower()
    if "sintech.vn" in h or "myharavan" in h:
        return True
    if "hstatic.net" in h or "haravanstatic" in h:
        m = re.search(r"hstatic\.net/(\d{6,})/", src) or re.search(r"/(\d{9,})/", src)
        if m:
            return m.group(1) == SINTECH_STORE_ID
        return False  # không rõ store → coi như KHÔNG phải Sintech (an toàn)
    return False


_OWN = ("sintech.vn", "myharavan")  # giữ cho tương thích, ưu tiên is_sintech_image()
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
    _audit, gate = imgs.audit_body_images(d.get("draft_body_html") or "", check_availability=True)
    return {
        "ok": True, "phase": "P5A", "draft_id": draft_id, "article_id": c["article_id"],
        "conflict_status": conflict, "body_hash_original": orig_hash[:16], "body_hash_live": live_hash[:16],
        "fields_available": {"body_html": True, "title": True, "summary_html": True, "tags": True},
        "fields_default_selected": {"body_html": True, "title": False, "summary_html": False, "tags": False},
        "image_plan_status": "dry_run",
        "eligible_images": psum.get("eligible_upload", 0), "blocked_images": psum.get("blocked", 0),
        "manual_review_images": psum.get("manual_review", 0), "keep_existing_images": psum.get("keep_existing", 0),
        "image_gate": gate,  # P5D store-aware gate
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


# ═══════════════════════ P5B-1 — ARMED APPLY (feature flag OFF) ═══════════════════════
import blog_rewrite as _br

_FLAGS_PATH = Path(__file__).parent.parent / "state" / "blog_rewrite_flags.json"


def flags():
    try:
        return json.loads(_FLAGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def live_apply_enabled():
    return bool(flags().get("BLOG_REWRITE_LIVE_APPLY_ENABLED", False))


def live_rollback_enabled():
    return bool(flags().get("BLOG_REWRITE_LIVE_ROLLBACK_ENABLED", False))


def bulk_apply_enabled():
    return bool(flags().get("BLOG_REWRITE_BULK_APPLY_ENABLED", False))


def _migrate_apply_cols():
    conn = db.get_conn()
    for col in ("apply_nonce TEXT", "applied_draft_hash TEXT"):
        try:
            conn.execute(f"ALTER TABLE blog_rewrite_drafts ADD COLUMN {col}")
        except Exception:
            pass
    conn.commit(); conn.close()


_migrate_apply_cols()


def _get_live(blog_id, article_id):
    """GET live article (read-only). QA có thể monkeypatch."""
    return _fetch_live_article(blog_id, article_id)


def _fetch_public_page(url, attempts=3):
    """P7.2 — public page read-only fallback (CHỈ đọc, KHÔNG bao giờ PUT).
    Retry tối đa attempts + cache-bust để tránh CDN cache. QA monkeypatch-able."""
    if not url:
        return None
    for i in range(attempts):
        try:
            sep = "&" if "?" in url else "?"
            r = requests.get(f"{url}{sep}_rcncl={i}", verify=False, timeout=25,
                             headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache", "Pragma": "no-cache"})
            if r.status_code == 200 and r.text:
                return r.text
        except Exception:
            pass
        if i < attempts - 1:
            try:
                time.sleep(1.0)
            except Exception:
                pass
    return None


def _get_live_for_verify(blog_id, article_id, public_url=None):
    """P7.2 read-only ladder: ưu tiên Haravan admin GET, fallback public page.
    KHÔNG PUT. Trả {ok, source, body_html, public_text, http}.
    source ∈ HARAVAN_READ_API / PUBLIC_PAGE_FALLBACK / None."""
    try:
        code, art = _get_live(blog_id, article_id)
        if code == 200 and art:
            return {"ok": True, "source": "HARAVAN_READ_API", "body_html": art.get("body_html") or "",
                    "public_text": None, "http": code}
        admin_http = code
    except Exception as e:
        admin_http = f"exc:{str(e)[:40]}"
    page = _fetch_public_page(public_url, attempts=3)
    if page is not None:
        return {"ok": True, "source": "PUBLIC_PAGE_FALLBACK", "body_html": None,
                "public_text": page, "http": admin_http}
    return {"ok": False, "source": None, "body_html": None, "public_text": None, "http": admin_http}


def _put_article(blog_id, article_id, fields):
    """REAL Open API PUT body-only — CHỈ chạy khi flag ON (P5B-2). QA monkeypatch hàm này.
    Trả (status_code, dict)."""
    H = {"Authorization": f"Bearer {_CFG['blog_access_token']}",
         "Accept": "application/json", "Content-Type": "application/json"}
    r = requests.put(f"{_CFG['open_api_base']}/blogs/{blog_id}/articles/{article_id}.json",
                     headers=H, data=json.dumps({"article": fields}), verify=False, timeout=30)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {}


def _locked(phase="P5B-1"):
    return {"ok": False, "phase": phase, "locked": True,
            "error": "Live apply đang khóa. Không có thay đổi nào được gửi lên Haravan."}


def verify_live(draft_id):
    """GET live + so semantic signature với draft (read-only, KHÔNG PUT)."""
    import blog_rewrite_verify as _v
    d = _br.get_draft(int(draft_id))
    if not d:
        return {"ok": False, "error": "draft không tồn tại"}
    c = _br.get_candidate(d["candidate_id"])
    try:
        code, art = _get_live(c["blog_id"], c["article_id"])
    except Exception as e:
        return {"ok": True, "verify_status": "VERIFY_READ_FAILED", "error": str(e)[:80]}
    if code != 200:
        return {"ok": True, "verify_status": "VERIFY_READ_FAILED", "http": code}
    cmp = _v.compare_article_signatures(
        _v.build_article_verify_signature(d.get("draft_body_html") or ""),
        _v.build_article_verify_signature(art.get("body_html") or ""))
    conn = db.get_conn()
    conn.execute("UPDATE blog_rewrite_drafts SET apply_result_json=? WHERE id=?",
                 (json.dumps({"verify_live": cmp["status"], "reasons": cmp["reasons"]}, ensure_ascii=False), int(draft_id)))
    conn.commit(); conn.close()
    return {"ok": True, "draft_id": int(draft_id), "verify_status": cmp["status"], "reasons": cmp["reasons"],
            "live_images": _v.build_article_verify_signature(art.get("body_html") or "")["structure"]["img"]}


def verify_status(draft_id):
    d = _br.get_draft(int(draft_id))
    if not d:
        return {"ok": False, "error": "draft không tồn tại"}
    try:
        ar = json.loads(d.get("apply_result_json") or "{}")
    except Exception:
        ar = {}
    return {"ok": True, "draft_id": int(draft_id), "last_verify": ar.get("verify_live") or ar.get("verify"),
            "applied_at": d.get("applied_at")}


def apply_status(draft_id):
    d = _br.get_draft(int(draft_id))
    if not d:
        return {"ok": False, "error": "draft không tồn tại"}
    c = _br.get_candidate(d["candidate_id"])
    return {
        "ok": True, "phase": "P5B-1", "draft_id": d["id"], "candidate_id": d["candidate_id"],
        "article_id": (c or {}).get("article_id"), "version": d["version"],
        "approval_status": d["approval_status"], "rewrite_eligible": (c or {}).get("rewrite_eligible"),
        "reverse_copy": (c or {}).get("audit_reverse_copy"),
        "has_backup": bool(d.get("live_backup_payload_json")),
        "applied_draft_hash": d.get("applied_draft_hash"), "applied_at": d.get("applied_at"),
        "flags": {"live_apply": live_apply_enabled(), "live_rollback": live_rollback_enabled(),
                  "bulk_apply": bulk_apply_enabled()},
        "fields_body_only": True,
    }


def apply_draft_body_only(draft_id, confirm_phrase="", fields=None,
                          confirm_reviewed_draft=False, confirm_reviewed_images=False):
    """Armed apply body-only. Flag OFF → 423 (không PUT). Full guard + fresh conflict +
    backup + idempotency + post-PUT verify. QA monkeypatch _put_article/_get_live."""
    _br.record_event("apply_requested", draft_id=draft_id)
    if not live_apply_enabled():
        _br.record_event("apply_blocked_locked", draft_id=draft_id)
        return _locked(), 423
    d = _br.get_draft(int(draft_id))
    if not d:
        return {"ok": False, "error": "draft không tồn tại"}, 404
    cid = d["candidate_id"]
    c = _br.get_candidate(cid)
    article_id = (c or {}).get("article_id"); blog_id = (c or {}).get("blog_id")

    def reject(msg, ev="apply_failed"):
        _br.record_event(ev, candidate_id=cid, draft_id=draft_id, detail={"reason": msg[:120]})
        return {"ok": False, "phase": "P5B-1", "error": msg}, 400

    # ─── guards ───
    if (c or {}).get("audit_reverse_copy"):
        return reject("Bài reverse-copy (Sintech bị copy) — KHÔNG apply.")
    if not (c or {}).get("rewrite_eligible"):
        return reject("Candidate không rewrite_eligible.")
    latest = _br.latest_draft_for_candidate(cid)
    if not latest or latest["id"] != d["id"]:
        return reject("Draft cũ hơn latest version — chỉ apply latest.")
    if d["approval_status"] != "approved_local":
        return reject("Draft chưa approved_local.")
    if not (confirm_reviewed_draft and confirm_reviewed_images):
        return reject("Cần xác nhận đã review draft + ảnh.")
    fields = fields or {"body_html": True}
    if not fields.get("body_html"):
        return reject("fields.body_html phải = true.")
    if fields.get("title") or fields.get("summary_html") or fields.get("tags"):
        return reject("P5B-1 chỉ body-only — title/summary/tags chưa hỗ trợ.")
    if confirm_phrase.strip() != f"APPLY PILOT ARTICLE {article_id}":
        return reject("Confirm phrase sai.")

    draft_hash = _hash_body(d.get("draft_body_html") or "")
    # ─── idempotency ───
    if d.get("applied_draft_hash") == draft_hash and d.get("applied_at"):
        return {"ok": True, "phase": "P5B-1", "already_applied": True,
                "draft_id": d["id"], "verify_status": "VERIFIED"}, 200

    # ─── fresh conflict check NGAY TRƯỚC PUT ───
    code, art = _get_live(blog_id, article_id)
    if code != 200 or not art:
        return reject("Không đọc được live article (fresh).", "apply_blocked_conflict")
    live_hash_before = _hash_body(art.get("body_html") or "")
    orig_hash = _hash_body(d.get("original_body_html") or "")
    if live_hash_before != orig_hash:
        _br._set_candidate_status(cid, "conflict")
        _br.record_event("conflict_detected", candidate_id=cid, draft_id=draft_id,
                         detail={"live": live_hash_before[:16], "orig": orig_hash[:16]})
        return {"ok": False, "phase": "P5B-1", "conflict_status": "CONFLICT_LIVE_CHANGED",
                "error": "Bài live đã thay đổi từ lúc tạo draft — KHÔNG overwrite."}, 409

    # ─── IMAGE GATE (P5D): block nếu ảnh chết/đối thủ/unknown ───
    _audit, gate = imgs.audit_body_images(d.get("draft_body_html") or "", check_availability=True)
    if not gate["apply_allowed"]:
        _br.record_event("apply_blocked_image_gate", candidate_id=cid, draft_id=draft_id,
                         detail={"blocked": gate["blocked"], "dead": gate["dead"],
                                 "competitor": gate["competitor"], "unknown": gate["unknown"]})
        return {"ok": False, "phase": "P5B-1", "error": "Image gate BLOCK — ảnh chết/đối thủ/unknown chưa xử lý.",
                "image_gate": gate}, 409

    # ─── live backup TRƯỚC PUT (state BACKUP_SAVED) ───
    backup_preview(draft_id)
    _br.record_event("live_backup_saved", candidate_id=cid, draft_id=draft_id, detail={"state": "BACKUP_SAVED"})

    # ─── PUT body-only (state PUT_SENT) ───
    nonce = draft_hash[:12]
    _br.record_event("apply_started", candidate_id=cid, draft_id=draft_id, detail={"nonce": nonce, "state": "APPLY_REQUESTED"})
    put_fields = {"id": article_id, "body_html": d.get("draft_body_html")}
    put_exc = None
    try:
        status, _resp = _put_article(blog_id, article_id, put_fields)
    except Exception as e:
        # exception SAU khi đã gửi request (timeout/connection reset/parse) → request CÓ THỂ đã ăn
        status, _resp, put_exc = None, {}, str(e)[:160]
    # PUT request ĐÃ GỬI — từ đây TUYỆT ĐỐI KHÔNG PUT lại. Mọi kết quả → reconcile bằng GET.
    _br.record_event("put_sent", candidate_id=cid, draft_id=draft_id,
                     detail={"state": "PUT_SENT", "http": status, "nonce": nonce, "exception": put_exc})
    # P7.2 — 500-but-write: HTTP 5xx / timeout / exception / parse-fail SAU PUT_SENT = UNCERTAIN,
    # TUYỆT ĐỐI KHÔNG ghi FAILED ngay, KHÔNG re-PUT, KHÔNG rollback auto. Phải reconcile bằng GET.
    uncertain_after_put = (put_exc is not None) or (status not in (200, 201))
    if uncertain_after_put:
        _br.record_event("put_response_uncertain", candidate_id=cid, draft_id=draft_id,
                         detail={"http": status, "exception": put_exc})

    # ─── post-PUT verify + reconcile (LUÔN GET live read-only, KHÔNG re-PUT dù 500) ───
    try:
        rec = reconcile_post_put(draft_id, draft_hash, nonce, live_hash_before, http=status,
                                 uncertain=uncertain_after_put)
        applied_ok = rec["state"] in ("LIVE_VERIFIED", "APPLIED_RECONCILED")
        return {"ok": applied_ok, "phase": "P7.2", "draft_id": d["id"], "article_id": article_id,
                "verify_status": rec["verify"], "state": rec["state"], "http": status,
                "verify_source": rec.get("verify_source")}, 200
    except Exception as e:
        _br.record_event("post_put_reconcile_failed", candidate_id=cid, draft_id=draft_id, detail={"error": str(e)[:160]})
        return {"ok": False, "phase": "P7.2", "draft_id": d["id"], "article_id": article_id,
                "verify_status": "UNCERTAIN_POST_PUT", "state": "UNCERTAIN_POST_PUT", "http": status}, 200


def reconcile_post_put(draft_id, draft_hash=None, nonce=None, live_hash_before="", http=201, uncertain=False):
    """P7.2 — Post-PUT reconcile read-only theo ladder + 3 chiều. KHÔNG PUT. Idempotent.

    GET admin → fallback public page → semantic verify so với CẢ draft VÀ original:
      live khớp draft     → APPLIED_RECONCILED  (DB candidate=applied)
      live khớp original  → NOT_APPLIED_RETRYABLE (chưa lên live, để retry, KHÔNG auto)
      khác cả hai / không đọc được → UNCERTAIN_POST_PUT → circuit breaker OPEN
    Dùng trong apply flow + recovery sau crash. KHÔNG re-PUT, KHÔNG rollback auto."""
    import blog_rewrite_verify as _v
    d = _br.get_draft(int(draft_id))
    if not d:
        return {"ok": False, "error": "draft không tồn tại", "state": "UNCERTAIN_POST_PUT",
                "verify": "UNCERTAIN_POST_PUT", "verify_source": None}
    cid = d["candidate_id"]
    c = _br.get_candidate(cid) or {}
    draft_hash = draft_hash or _hash_body(d.get("draft_body_html") or "")
    nonce = nonce or draft_hash[:12]
    _br.record_event("post_put_verify_started", candidate_id=cid, draft_id=draft_id,
                     detail={"http": http, "uncertain": uncertain})

    fetched = _get_live_for_verify(c.get("blog_id"), c.get("article_id"), c.get("article_url"))
    source = fetched["source"]
    verdict, detail = "READ_FAILED", {}
    if fetched["ok"] and fetched.get("body_html") is not None:
        live_sig = _v.build_article_verify_signature(fetched["body_html"])
        cmp_d = _v.compare_article_signatures(_v.build_article_verify_signature(d.get("draft_body_html") or ""), live_sig)
        cmp_o = _v.compare_article_signatures(_v.build_article_verify_signature(d.get("original_body_html") or ""), live_sig)
        if cmp_d["status"].startswith("VERIFIED"):
            verdict = "DRAFT"
        elif cmp_o["status"].startswith("VERIFIED"):
            verdict = "ORIGINAL"
        else:
            verdict = "UNCERTAIN"
        detail = {"cmp_draft": cmp_d["status"], "cmp_original": cmp_o["status"]}
    elif fetched["ok"] and fetched.get("public_text") is not None:
        pc = _v.compare_public_page(fetched["public_text"], d.get("draft_body_html") or "", d.get("original_body_html") or "")
        verdict, detail = pc["verdict"], pc

    if verdict == "DRAFT":
        verify = "VERIFIED"
        state = "LIVE_VERIFIED" if (not uncertain and http in (200, 201) and source == "HARAVAN_READ_API") else "APPLIED_RECONCILED"
    elif verdict == "ORIGINAL":
        verify, state = "NOT_APPLIED_RETRYABLE", "NOT_APPLIED_RETRYABLE"
    elif verdict == "READ_FAILED":
        verify, state = "READ_AFTER_WRITE_FAILED", "UNCERTAIN_POST_PUT"
    else:
        verify, state = "UNCERTAIN_POST_PUT", "UNCERTAIN_POST_PUT"

    after_hash = _hash_body(fetched.get("body_html") or "") if fetched.get("body_html") else ""
    result = {"ok": True, "verify": verify, "state": state, "http": http, "verify_source": source,
              "verdict": verdict, "detail": detail, "live_hash_before": (live_hash_before or "")[:16],
              "after": after_hash[:16]}

    conn = db.get_conn()
    if state in ("LIVE_VERIFIED", "APPLIED_RECONCILED"):
        conn.execute("UPDATE blog_rewrite_drafts SET applied_at=COALESCE(applied_at, datetime('now')), "
                     "applied_draft_hash=?, apply_nonce=?, apply_result_json=? WHERE id=?",
                     (draft_hash, nonce, json.dumps(result, ensure_ascii=False), draft_id))
    else:
        conn.execute("UPDATE blog_rewrite_drafts SET apply_result_json=? WHERE id=?",
                     (json.dumps(result, ensure_ascii=False), draft_id))
    conn.commit(); conn.close()

    if state in ("LIVE_VERIFIED", "APPLIED_RECONCILED"):
        _br._set_candidate_status(cid, "applied")
        _br.record_event("post_put_reconciled_applied", candidate_id=cid, draft_id=draft_id,
                         detail={"state": state, "verify_source": source, "verdict": verdict})
    elif state == "NOT_APPLIED_RETRYABLE":
        _br._set_candidate_status(cid, "approved_local")  # chưa lên live → giữ retryable, KHÔNG auto retry
        _br.record_event("post_put_reconciled_not_applied", candidate_id=cid, draft_id=draft_id,
                         detail={"state": state, "verify_source": source})
    else:
        # UNCERTAIN thật / không đọc được sau write → halt an toàn, mở circuit breaker
        _br._set_candidate_status(cid, "uncertain")
        _br.record_event("post_put_reconcile_failed" if verdict == "READ_FAILED" else "uncertain_post_put",
                         candidate_id=cid, draft_id=draft_id, detail={"state": state, "verify_source": source})
        try:
            import blog_rewrite_autopilot as _auto
            _auto.cb_open(f"reconcile_{verdict.lower()}_post_put")
            _br.record_event("circuit_breaker_opened_uncertain", candidate_id=cid, draft_id=draft_id, detail={"verdict": verdict})
        except Exception:
            pass
    return result


def rollback_draft_apply(draft_id, confirm_phrase=""):
    """Rollback body-only từ live_backup. Flag OFF → 423. QA monkeypatch _put_article."""
    _br.record_event("rollback_requested", draft_id=draft_id)
    if not live_rollback_enabled():
        _br.record_event("rollback_blocked_locked", draft_id=draft_id)
        return _locked(), 423
    d = _br.get_draft(int(draft_id))
    if not d:
        return {"ok": False, "error": "draft không tồn tại"}, 404
    cid = d["candidate_id"]; c = _br.get_candidate(cid)
    article_id = (c or {}).get("article_id"); blog_id = (c or {}).get("blog_id")
    if confirm_phrase.strip() != f"ROLLBACK PILOT ARTICLE {article_id}":
        return {"ok": False, "error": "Confirm phrase sai."}, 400
    try:
        backup = json.loads(d.get("live_backup_payload_json") or "{}")
    except Exception:
        backup = {}
    if not backup.get("body_html"):
        return {"ok": False, "error": "Không có backup payload."}, 400
    _br.record_event("rollback_started", candidate_id=cid, draft_id=draft_id)
    status, _ = _put_article(blog_id, article_id, {"id": article_id, "body_html": backup["body_html"]})
    if status not in (200, 201):
        _br.record_event("rollback_failed", candidate_id=cid, draft_id=draft_id, detail={"http": status})
        return {"ok": False, "error": f"PUT HTTP {status}"}, 502
    code2, art2 = _get_live(blog_id, article_id)
    ok = _hash_body((art2 or {}).get("body_html") or "") == _hash_body(backup["body_html"])
    _br.record_event("rollback_completed" if ok else "rollback_verify_failed", candidate_id=cid, draft_id=draft_id)
    return {"ok": True, "phase": "P5B-1", "verify_status": "VERIFIED" if ok else "VERIFY_MISMATCH"}, 200
