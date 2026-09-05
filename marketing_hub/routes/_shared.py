"""Shared helpers across multiple route modules.

Đặt vào đây khi 1 helper được dùng bởi ≥2 module routes/*.py.
KHÔNG đặt code domain-specific — chỉ các utility nhỏ.
"""

from flask import request, jsonify


def save_seo_job_edits(update_fn, job_id):
    """Lưu edit title/meta/body từ form detail page (chung cho collection + blog).

    update_fn tự lo recompute quality/readability khi có edited_*
    (xem _collection_jobs_update / _blog_jobs_update).

    4/9/2026: CHỈ ghi field nào thực sự có trong payload. Trước đây luôn ghi cả ba,
    field thiếu thành chuỗi rỗng — một request gửi mỗi `body` là xoá sạch title+meta
    đã soạn. Frontend hiện tại (collection_content_detail / blog_content_detail) luôn
    gửi đủ ba nên chưa mất gì, nhưng đây là cửa mở sẵn: một lần gọi từ script, từ
    bản sửa JS sau này, hay lỗi DOM là mất nội dung mà không ai báo.
    Cùng nguyên tắc với db.seo_upsert_page — đừng ghi đè thứ caller không gửi.
    """
    payload = request.get_json(silent=True) or request.form
    fields = {}
    for khoa, cot in (("title", "edited_title"), ("meta", "edited_meta"),
                      ("body", "edited_body_html")):
        if khoa in payload:
            fields[cot] = (payload.get(khoa) or "").strip()
    if not fields:
        return jsonify({"ok": False, "error": "không có field nào để lưu"}), 400
    update_fn(job_id, **fields)
    return jsonify({"ok": True, "da_luu": sorted(fields)})
