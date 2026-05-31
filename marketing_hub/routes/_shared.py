"""Shared helpers across multiple route modules.

Đặt vào đây khi 1 helper được dùng bởi ≥2 module routes/*.py.
KHÔNG đặt code domain-specific — chỉ các utility nhỏ.
"""

from flask import request, jsonify


def save_seo_job_edits(update_fn, job_id):
    """Lưu edit title/meta/body từ form detail page (chung cho collection + blog).

    update_fn tự lo recompute quality/readability khi có edited_*
    (xem _collection_jobs_update / _blog_jobs_update).
    """
    payload = request.get_json(silent=True) or request.form
    update_fn(job_id,
              edited_title=(payload.get("title") or "").strip(),
              edited_meta=(payload.get("meta") or "").strip(),
              edited_body_html=(payload.get("body") or "").strip())
    return jsonify({"ok": True})
