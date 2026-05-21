"""NGUỒN CHÂN LÝ DUY NHẤT cho rule content Sintech — dùng chung 3 hệ gen
(SP / blog / collection / title-meta).

Đổi rule chung ở ĐÂY → mọi writer ăn theo (hết cảnh sửa 3 nơi, lệch nhau).
Đồng bộ seo_writing_rules.md (v2026-05-08).

Cách dùng trong writer:
    import sintech_rules
    _SYSTEM_PROMPT = ("...phần đầu type-specific...\\n"
                      + sintech_rules.common_rules_block(cta_note="...")
                      + "\\n...phần cấu trúc + OUTPUT JSON...")
"""

HOTLINE = "0911 713 000"
ADDRESS = "457 Trần Xuân Soạn, Q7, TP.HCM"
HOMEPAGE = "https://sintech.vn"

# CTA HOA chuẩn (cụm hành động viết HOA). KHÁM PHÁ NGAY = SP cao cấp/độc lạ.
CTA_POOL = [
    "XEM NGAY",
    "THAM KHẢO NGAY",
    "CHỌN NGAY mẫu phù hợp",
    "KHÁM PHÁ NGAY",
]

# Cụm filler vợ rate 0% — CẤM tuyệt đối trong title/meta/body
FORBIDDEN_FILLER = [
    "bền bỉ", "đẹp mắt", "Free ship", "Free ship nội thành",
    "đáng mua nhất", "tốt nhất 2026", "khôn nhất", "rẻ nhất",
]

SIGNATURE = f"Tư vấn cấu hình bởi team kỹ thuật Sintech — Hotline {HOTLINE} · {ADDRESS}."

TITLE_RULES = (
    "TITLE 45-61 ký tự (target 45-58, tối đa tuyệt đối 61). "
    "KHÔNG chứa 'Sintech' (Haravan tự thêm hậu tố ' - Sintech'). "
    "KHÔNG nhồi keyword / lặp từ / lan man."
)

META_RULES = (
    "META 140-160 ký tự, 1 câu mượt dễ đọc, có CTA HOA cuối câu "
    "(1 trong: " + " / ".join(CTA_POOL) + " — kèm 'tại Sintech'). "
    "Đủ: tên SP/chủ đề + lợi ích chính + ngữ cảnh dùng + CTA HOA."
)

SPEC_SAFETY = (
    "TUYỆT ĐỐI KHÔNG bịa thông số — CHỈ dùng spec số có sẵn trong TÊN SP / input. "
    "CẤM tự thêm nếu chưa xuất hiện: tần số quét (Hz), điện áp/dòng/công suất (V/A/W), "
    "dung lượng (GB/TB), kích thước (inch/mm), tốc độ (MHz/GHz/MB/s), "
    "số cổng/chân/nhân-luồng, bảo hành (tháng/năm)."
)

PRONOUN = (
    "Public xưng 'bạn', KHÔNG dùng 'anh'. Đa dạng câu mở "
    "(Hiện nay / Đối với / Trong khi / Nhờ đó / Bên cạnh đó / Tuy nhiên), "
    "KHÔNG lặp 'Bạn cần... Bạn nên...' liên tiếp."
)


def forbidden_block() -> str:
    return "CẤM filler (vợ rate 0%): " + ", ".join(f'"{x}"' for x in FORBIDDEN_FILLER) + "."


def common_rules_block(cta_note: str = "") -> str:
    """Khối RULE CHUNG để chèn vào mọi prompt content gen.

    cta_note: ghi chú CTA riêng theo loại (vd blog cho thêm 'TÌM HIỂU NGAY').
    """
    lines = [
        "=== RULE CHUNG SINTECH (nguồn: sintech_rules.py) ===",
        "- " + TITLE_RULES,
        "- " + META_RULES + ((" " + cta_note) if cta_note else ""),
        "- " + SPEC_SAFETY,
        "- " + forbidden_block(),
        "- " + PRONOUN,
        f'- CTA link intro + outro: <a href="{HOMEPAGE}"><strong>Sintech</strong></a>.',
        f"- Signature CỐ ĐỊNH cuối bài (in nghiêng): {SIGNATURE}",
    ]
    return "\n".join(lines)
