"""job_sync.py — tầng CHUNG cho sync content job lên Haravan (Phase 2, Task #8).

Gom 2 mối nguy cross-cutting từng lặp ở 3 pipeline (content_jobs / collection / blog):
  1. Hợp đồng ghi SEO Haravan — theme Sintech đọc title/meta từ flat field
     `metafields_global_title_tag` / `metafields_global_description_tag`
     (verified 15/5/2026 — endpoint /metafields cũng nhận nhưng theme KHÔNG đọc từ đó).
     Đổi 1 lần ở ĐÂY → cả 3 nơi ăn theo.
  2. Map kết quả sync → status job (synced/failed + synced_at + error) — 1 nguồn để
     tránh tái diễn bug "sync fail mà status vẫn 'synced'".

KHÔNG đụng gen-engine hay logic riêng (ảnh lazy-upload + field flags của content_jobs,
2-phase worker, compress body) — những phần đó khác shape, giữ tại chỗ.
"""
from datetime import datetime

# Flat field theme Sintech đọc SEO title/meta (verified 15/5/2026).
SEO_TITLE_FIELD = "metafields_global_title_tag"
SEO_DESC_FIELD = "metafields_global_description_tag"


def seo_metafields(title=None, meta=None) -> dict:
    """Build dict flat field SEO cho payload Haravan.

    Truyền None cho field nào KHÔNG muốn ghi (vd content_jobs tick lẻ từng field).
    Truyền chuỗi (kể cả "") → field đó được set (đã .strip()).
    """
    out = {}
    if title is not None:
        out[SEO_TITLE_FIELD] = (title or "").strip()
    if meta is not None:
        out[SEO_DESC_FIELD] = (meta or "").strip()
    return out


def apply_sync_result(update_fn, job_id, result: dict, err_len: int = 500) -> bool:
    """Map kết quả sync → cập nhật status job. Trả True nếu OK.

    update_fn: hàm update job của pipeline (vd _collection_jobs_update / _blog_jobs_update).
    result: dict trả về từ writer sync ({"ok": bool, "error"?: str}).
    OK   → status='synced', synced_at=now, error=None.
    FAIL → status='failed', error=result['error'][:err_len] (KHÔNG giữ 'synced' cũ).
    """
    if result.get("ok"):
        update_fn(job_id, status="synced",
                  synced_at=datetime.now().isoformat(timespec="seconds"),
                  error=None)
        return True
    update_fn(job_id, status="failed",
              error=(result.get("error", "") or "")[:err_len])
    return False
