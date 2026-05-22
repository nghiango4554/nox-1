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
    "vượt trội", "đỉnh cao",
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


def common_rules_block(cta_note: str = "", include_length: bool = True) -> str:
    """Khối RULE CHUNG để chèn vào mọi prompt content gen (body dài).

    cta_note: ghi chú CTA riêng theo loại (vd blog cho thêm 'TÌM HIỂU NGAY').
    include_length: True → kèm rule độ dài title/meta chung (45-61 / 140-160).
        Đặt False cho writer đã có rule length RIÊNG chặt hơn (vd collection 48-58,
        title-meta gen 45-58/145-158) để KHỎI mâu thuẫn — vẫn giữ các rule chung
        còn lại (chống bịa spec, filler, xưng hô, CTA link, signature).
    """
    lines = ["=== RULE CHUNG SINTECH (nguồn: sintech_rules.py) ==="]
    if include_length:
        lines.append("- " + TITLE_RULES)
        lines.append("- " + META_RULES + ((" " + cta_note) if cta_note else ""))
    elif cta_note:
        lines.append("- " + cta_note)
    lines += [
        "- " + SPEC_SAFETY,
        "- " + forbidden_block(),
        "- " + PRONOUN,
        f'- CTA link intro + outro: <a href="{HOMEPAGE}"><strong>Sintech</strong></a>.',
        f"- Signature CỐ ĐỊNH cuối bài (in nghiêng): {SIGNATURE}",
    ]
    return "\n".join(lines)


def title_meta_rules_block() -> str:
    """Khối RULE CHUNG cho prompt gen TITLE/META (seo.py + collection).

    KHÔNG kèm độ dài & schema & angle — mỗi caller tự giữ riêng:
        seo.py        title 45-58 / meta 145-158, 3 title + 3 meta (M1/M2/M3)
        collection    title 48-58 / meta 140-160, 1 title + 1 meta
    Chỉ chứa các rule GIỐNG NHAU giữa 2 nơi: cấm 'Sintech' trong title, pool CTA HOA,
    chống bịa spec, cấm filler, cấm bịa giá. Đổi 1 lần ở đây → cả 2 nơi ăn theo.
    """
    cta_list = " / ".join(f'"{c} tại Sintech"' for c in CTA_POOL)
    return "\n".join([
        "=== RULE CHUNG TITLE/META (nguồn: sintech_rules.py) ===",
        '- TITLE KHÔNG chứa "Sintech" (Haravan tự thêm hậu tố " - Sintech"); '
        "KHÔNG nhồi keyword / lặp từ / lan man.",
        f"- META kết bằng CTA HOA (cụm hành động IN HOA, KHÔNG in hoa cả câu). "
        f'Pool: {cta_list}. "KHÁM PHÁ NGAY" chỉ dành SP cao cấp/độc lạ.',
        "- " + SPEC_SAFETY,
        "- " + forbidden_block(),
        "- KHÔNG bịa giá / mã giảm / % giảm nếu input không cung cấp.",
        '- TÍN HIỆU TIN CẬY: META nên cài 1 cụm "chính hãng" (và/hoặc 1 cam kết: '
        '"bảo hành chính hãng" / "hỗ trợ kỹ thuật") đặt TỰ NHIÊN, chữ thường — tăng CTR. '
        "KHÔNG nêu SỐ tháng/năm bảo hành nếu input không cung cấp; "
        "KHÔNG nhồi >2 cụm lợi ích trong 1 meta (tránh loãng/spammy).",
    ])
