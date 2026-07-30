"""Routes: 👁️ Preview — nơi xem mọi file HTML preview do các task sinh ra.

Vấn đề trước đây: mỗi task lại đẻ 1 file .html rơi rớt trong nox-outputs/ hoặc Downloads,
vợ phải tự đi tìm mà mở. Tab này gom hết về một chỗ, xem ngay trong hub.

Nguồn quét (chỉ ĐỌC):
  · workspace/nox-outputs/            — file kết quả chuẩn của mọi script
  · Downloads/                        — preview tạm, ảnh local kèm theo
  · marketing_hub/data/_preview/      — preview do chính hub sinh

An toàn: chỉ phục vụ file nằm TRONG các thư mục gốc kể trên (chặn path traversal),
chỉ mở .html/.htm và các loại ảnh. Không ghi, không xoá trừ khi bấm nút xoá.
"""

import mimetypes
import time
from pathlib import Path

from flask import render_template, request, jsonify, send_file, abort

WS = Path(__file__).resolve().parent.parent.parent.parent      # …/workspace
ROOTS = {
    "outputs": WS / "nox-outputs",
    "downloads": Path.home() / "Downloads",
    "hub": Path(__file__).resolve().parent.parent / "data" / "_preview",
}
HTML_EXT = {".html", ".htm"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}


def _safe(root_key: str, rel: str) -> Path:
    """Ghép đường dẫn và CHẶN đi ra ngoài thư mục gốc."""
    root = ROOTS.get(root_key)
    if not root:
        abort(404)
    p = (root / rel).resolve()
    if not str(p).startswith(str(root.resolve())):
        abort(403)
    return p


def _bo_qua(p: Path, root: Path) -> bool:
    """Loại file KHÔNG phải bản xem thử: backup body, snapshot, thư mục rác.

    Quy ước trong repo: thư mục/file bắt đầu bằng '_' hoặc có chữ 'backup' là bản lưu,
    mở ra chỉ thấy HTML thô của 1 sản phẩm chứ không xem được gì.
    """
    parts = p.relative_to(root).parts
    for seg in parts:
        low = seg.lower()
        if seg.startswith("_") or "backup" in low or low in ("node_modules", ".git"):
            return True
    return False


def _scan(limit_per_root: int = 200) -> list:
    out = []
    for key, root in ROOTS.items():
        if not root.exists():
            continue
        try:
            files = [p for p in root.rglob("*")
                     if p.suffix.lower() in HTML_EXT and p.is_file() and not _bo_qua(p, root)]
        except Exception:
            continue
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for p in files[:limit_per_root]:
            st = p.stat()
            out.append({
                "root": key,
                "rel": str(p.relative_to(root)).replace("\\", "/"),
                "name": p.name,
                "size_kb": round(st.st_size / 1024, 1),
                "mtime": st.st_mtime,
                "when": time.strftime("%d/%m %H:%M", time.localtime(st.st_mtime)),
            })
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out


# ─────────────────────────── PAGES ───────────────────────────

def preview_page():
    items = _scan()
    return render_template("preview.html", items=items,
                           roots={k: str(v) for k, v in ROOTS.items()})


def api_preview_list():
    return jsonify({"ok": True, "items": _scan()})


def preview_file(root_key, rel):
    """Trả nội dung file preview (html/ảnh) để nhúng iframe hoặc mở tab mới."""
    p = _safe(root_key, rel)
    if not p.exists() or not p.is_file():
        abort(404)
    ext = p.suffix.lower()
    if ext not in HTML_EXT | IMG_EXT:
        abort(415)
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    if ext in HTML_EXT:
        mime = "text/html; charset=utf-8"
    return send_file(str(p), mimetype=mime, conditional=True)


def api_preview_delete():
    """Xoá 1 file preview (.html hoặc ẢNH, chỉ trong thư mục gốc đã khai báo).

    2026-07-29: mở thêm cho ảnh — vợ lọc ảnh ứng viên ngay trên trang preview,
    bấm ✕ là xoá luôn file để lượt đẩy sau không lấy nhầm ảnh đã loại.
    """
    d = request.get_json(silent=True) or {}
    p = _safe(d.get("root", ""), d.get("rel", ""))
    if p.suffix.lower() not in (HTML_EXT | IMG_EXT):
        return jsonify({"ok": False, "error": "chỉ xoá được file .html hoặc ảnh"}), 400
    if not p.exists():
        return jsonify({"ok": False, "error": "file không còn"}), 404
    p.unlink()
    return jsonify({"ok": True})


def register(app):
    app.add_url_rule("/preview", "preview_page", preview_page)
    app.add_url_rule("/api/preview/list", "api_preview_list", api_preview_list)
    app.add_url_rule("/preview/file/<root_key>/<path:rel>", "preview_file", preview_file)
    app.add_url_rule("/api/preview/delete", "api_preview_delete",
                     api_preview_delete, methods=["POST"])
