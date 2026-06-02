"""spec_block.py — Gom spec thô → khối <blockquote> thông số kỹ thuật cho theme Sintech.

Theme Sintech render <blockquote> chứa tiêu đề nhóm = <p><strong>…</strong></p> (TEXT THƯỜNG,
không dùng <h3> — vợ chốt 2/6) + <ul><li><strong>Nhãn:</strong> giá trị</li>. Hàm này tạo đúng markup đó.

Nguồn spec: list [{label, value}] (vd từ serper_search.fetch_product_specs) hoặc text.
AI chỉ làm việc GOM NHÓM + chuẩn hoá nhãn — KHÔNG bịa spec mới.
"""
from __future__ import annotations

import json
import re

import ai_provider


_GROUP_SYSTEM = """Bạn là chuyên viên chuẩn hoá thông số kỹ thuật cho Sintech.vn.
NHIỆM VỤ: gom danh sách spec THÔ của 1 sản phẩm thành các NHÓM có tiêu đề, để render bảng thông số trên web.

Quy tắc:
- Tự chọn 3-5 nhóm phù hợp loại SP. Tên nhóm gợi ý theo loại:
  • Chung: "Thông tin hàng hóa" (LUÔN ở đầu)
  • SSD/ổ cứng: "Hiệu năng lưu trữ", "Chuẩn kết nối", "Tương thích & ghi chú"
  • Laptop/PC: "Cấu hình", "Màn hình", "Kết nối và cổng", "Thiết kế và kích thước"
  • VGA: "Hiệu năng", "Bộ nhớ & bus", "Kết nối & nguồn"
  • Màn hình: "Tấm nền & hình ảnh", "Tần số & phản hồi", "Kết nối", "Thiết kế"
- Nhóm "Thông tin hàng hóa" gồm (nếu có): Thương hiệu, Dòng sản phẩm, Model, Loại sản phẩm, Dung lượng/Phiên bản.
- Mỗi item: label NGẮN GỌN tiếng Việt (vd "Tốc độ đọc tuần tự"), value GIỮ NGUYÊN số liệu + đơn vị.
- CHỈ dùng spec CÓ trong input. TUYỆT ĐỐI KHÔNG bịa spec/số mới.
- **TUYỆT ĐỐI KHÔNG đưa "Tình trạng" và "Bảo hành" vào bảng — BỎ HẲN 2 mục này** (kể cả khi input có).
- Value không thêm dấu chấm cuối dòng. Không lặp spec ở 2 nhóm.

Trả về DUY NHẤT 1 JSON, KHÔNG markdown fence:
{"groups":[{"title":"Thông tin hàng hóa","items":[{"label":"Thương hiệu","value":"SSTC"}]}]}"""


def _render_blockquote(groups: list) -> str:
    parts = ["<blockquote>"]
    for g in groups or []:
        title = (g.get("title") or "").strip()
        items = g.get("items") or []
        if not title or not items:
            continue
        rows = []
        for it in items:
            label = (it.get("label") or "").strip().rstrip(":").strip()
            val = (it.get("value") or "").strip()
            if not label or not val:
                continue
            # Bỏ hẳn Tình trạng / Bảo hành khỏi bảng spec (theo yêu cầu)
            _lc = label.lower()
            if "tình trạng" in _lc or "bảo hành" in _lc or "bao hanh" in _lc:
                continue
            rows.append(f"<li><strong>{label}:</strong> {val}</li>")
        if rows:
            # RULE (vợ chốt 2/6): tiêu đề nhóm trong khối trích dẫn = TEXT THƯỜNG (in đậm),
            # KHÔNG dùng <h3> nữa.
            parts.append(f"<p><strong>{title}</strong></p><ul>{''.join(rows)}</ul>")
    parts.append("</blockquote>")
    html = "".join(parts)
    return html if "<li>" in html else ""


def build_spec_blockquote(product_name: str, specs, brand: str = None,
                          known_info: str = None, reasoning_effort: str = "low") -> str:
    """specs: list[{label,value}] hoặc text. Trả HTML <blockquote> spec table (rỗng nếu fail/không spec).

    known_info: chuỗi dữ liệu XÁC MINH từ Haravan (vd "Tình trạng: Cũ đẹp\\nBảo hành: 12 tháng")
    — AI chỉ được ghi Tình trạng/Bảo hành theo đúng đây, không tự đoán.
    """
    if isinstance(specs, str):
        spec_text = specs.strip()
    else:
        spec_text = "\n".join(
            f"- {s.get('label')}: {s.get('value')}" for s in (specs or [])
            if s.get("label") and s.get("value")
        )
    if not spec_text:
        return ""
    user = (
        f"Sản phẩm: {product_name}\n"
        + (f"Thương hiệu: {brand}\n" if brand else "")
        + (f"\nDữ liệu XÁC MINH (chỉ dùng đúng cho Tình trạng/Bảo hành, KHÔNG đoán thêm):\n{known_info}\n" if known_info else "")
        + f"\nDanh sách spec thô:\n{spec_text}\n\nGom thành nhóm theo quy tắc, trả JSON."
    )
    try:
        raw = ai_provider.call_ai(_GROUP_SYSTEM, user, timeout=120,
                                  reasoning_effort=reasoning_effort)
    except Exception as e:
        print(f"[spec_block] AI lỗi: {e}")
        return ""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?|\n?```$", "", cleaned).strip()
    m = re.search(r"\{.*\}", cleaned, re.S)
    if m:
        cleaned = m.group(0)
    try:
        data = json.loads(cleaned)
    except Exception as e:
        print(f"[spec_block] parse JSON lỗi: {e} | tail: {cleaned[-200:]}")
        return ""
    return _render_blockquote(data.get("groups") or [])
