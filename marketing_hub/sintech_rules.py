"""NGUỒN CHÂN LÝ DUY NHẤT cho rule content Sintech — dùng chung 3 hệ gen
(SP / blog / collection / title-meta).

Đổi rule chung ở ĐÂY → mọi writer ăn theo (hết cảnh sửa 3 nơi, lệch nhau).
Đồng bộ **SINTECH_CONTENT_RULES.md** (v2026-07-15, PHẦN 1B) — file rules duy nhất cho người đọc.
File này là bản dịch sang prompt cho code. Sửa rules → sửa CẢ HAI.

Đầu ra vẫn phải qua `qc_content.py` trước khi sync (prompt có thể bị AI phớt lờ, QC thì không).

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

# ─────────── Luật vợ chốt 9/7/2026 (xem PHẦN 2 + PHẦN 7 SINTECH_CONTENT_RULES.md) ───────────

NO_PRICE = (
    "TUYỆT ĐỐI KHÔNG nhắc giá trong body: không số tiền (45.000 đồng / tầm 149k / 3tr390k), "
    "không 'giá rẻ', 'giá sốc', 'rẻ nhất'. Thay bằng 'phổ thông', 'đời cũ', 'cùng tầm'. "
    "Giá đổi liên tục, nêu vào là bài lỗi thời."
)

HEADING_RULES = (
    "HEADING: không H1, chỉ H2/H3. "
    "MỖI HEADING MỘT MỆNH ĐỀ, ≤55 ký tự — không nối 2 vế bằng ':' ',' hay '-'. "
    "HẠN CHẾ dấu '-' và ':' trong heading, chỉ dùng khi bất khả kháng (tên SP, tên riêng, mã model). "
    "Heading lấy NGUYÊN VĂN cách người ta gõ Google "
    "(đúng: 'LED Rainbow và LED RGB khác nhau như thế nào?' — "
    "sai: 'Phân biệt ba loại đèn quạt để không mua nhầm'). "
    "Không heading nào trùng nhau."
)

# Chỉ áp cho bài SẢN PHẨM (blog/collection không dùng)
H2_FIRST_PRODUCT = (
    "H2 ĐẦU TIÊN = tên SP + model + biến thể, KHÔNG dấu ':' "
    "(đúng: 'Fan case VSP SF-1225M12S Đen' — sai: 'Fan case VSP SF-1225M12S: 120mm, 1200rpm'). "
    "Ngay dưới H2 đầu: 1 câu dẫn + 5-6 bullet tóm spec."
)

BODY_STYLE = (
    "VĂN PHONG: đoạn 2-3 câu ngắn. Nhiều bullet, ít chữ đặc. "
    "KHÔNG dùng <strong> trong thân bài (chỉ dùng cho nhãn trong khối spec cuối bài). "
    "CẤM dấu ';' trong body. CẤM '---' separator. "
    "Trung thực: nói thẳng SP không hợp với ai, hãng không công bố gì."
)

INTERNAL_LINK = (
    "INTERNAL LINK: 3-6 link trong body, URL thật. Anchor là cụm danh từ mô tả ≤30 ký tự. "
    "CẤM anchor 'tại đây', 'xem thêm', 'click here'. "
    "Anchor IN ĐẬM: bọc <strong> trong <a> — <a href='...'><strong>tên đích</strong></a> (theme tự tô đỏ + đậm). "
    "Verify slug collection tồn tại trước khi chèn — hay bịa (usb / cap-sac / hub-argb là 404; "
    "đúng phải là usb-flash / cap-chuyen-doi)."
)

POLICY_SENTENCE = (
    "Sintech hiện công bố chính sách bán hàng, kiểm hàng, vận chuyển và trả góp 0% "
    "qua thẻ tín dụng đối với 1 số sản phẩm."
)

SPEC_BLOCKQUOTE = (
    "KHỐI SPEC = <blockquote> và là BLOCK CUỐI CÙNG TUYỆT ĐỐI (sau cả signature, "
    "không có gì đứng sau). Để TRẦN, KHÔNG inline style (nhồi style → đè CSS theme → "
    "không lên bảng). KHÔNG nhét <table> vào trong blockquote (không hiển thị trên trang SP). "
    "Cấu trúc: <p><strong>Tên nhóm</strong></p><ul><li><strong>Nhãn:</strong> giá trị</li></ul>. "
    "LOẠI BỎ 'Tình trạng' và 'Bảo hành' khỏi khối spec."
)

# ─────────── Bổ sung 15/7/2026 (PHẦN 1B SINTECH_CONTENT_RULES.md) ───────────

AI_EXTRACT = (
    "TRÍCH DẪN ĐƯỢC (cho AI Overview/ChatGPT): dưới MỖI heading dạng câu hỏi, đặt NGAY "
    "1 đoạn 40-55 từ trả lời TRỰC TIẾP — đủ nghĩa khi tách khỏi bài, có con số/kết luận "
    "cụ thể ngay câu đầu, đứng TRƯỚC mọi giải thích dài/bullet (trả lời trước, diễn giải sau). "
    "Mỗi đoạn thân bài ≤150 từ; đoạn 300-400 từ liền mạch phải cắt nhỏ."
)

EVIDENCE = (
    "BẰNG CHỨNG (E-E-A-T): thay câu định tính chung chung bằng số liệu cụ thể khi có "
    "('bền cao' → '~50 triệu lần bấm'; 'chạy mát' → 'hạ 8-12°C'; 'nhanh' → 'đọc ~5.000 MB/s'). "
    "Ưu tiên số THẬT đã test. Không có số thật → viết an toàn, KHÔNG bịa."
)

MONEY_PAGE_LINK = (
    "LINK VỀ MONEY PAGE (bài blog/guide BẮT BUỘC): trong các internal link phải có ≥2 link "
    "theo ngữ cảnh trỏ về đúng COLLECTION/PRODUCT phục vụ intent của bài "
    "(vd 'cấu hình chơi GTA 5' → /collections/vga, /collections/ram-may-tinh; "
    "'card đồ họa laptop là gì' → collection VGA/laptop). Đặt NGAY chỗ người đọc đang có "
    "nhu cầu mua, KHÔNG dồn cuối bài. Bài mồi KHÔNG được là ngõ cụt."
)


def forbidden_block() -> str:
    return "CẤM filler (vợ rate 0%): " + ", ".join(f'"{x}"' for x in FORBIDDEN_FILLER) + "."


def common_rules_block(cta_note: str = "", include_length: bool = True,
                       is_product: bool = True) -> str:
    """Khối RULE CHUNG để chèn vào mọi prompt content gen (body dài).

    cta_note: ghi chú CTA riêng theo loại (vd blog cho thêm 'TÌM HIỂU NGAY').
    include_length: True → kèm rule độ dài title/meta chung (45-61 / 140-160).
        Đặt False cho writer đã có rule length RIÊNG chặt hơn (vd collection 48-58,
        title-meta gen 45-58/145-158) để KHỎI mâu thuẫn.
    is_product: True → thêm luật riêng bài SP (H2 đầu = tên SP, blockquote spec cuối,
        câu chính sách). Đặt False cho blog.
    """
    lines = ["=== RULE CHUNG SINTECH (nguồn: sintech_rules.py) ==="]
    if include_length:
        lines.append("- " + TITLE_RULES)
        lines.append("- " + META_RULES + ((" " + cta_note) if cta_note else ""))
    elif cta_note:
        lines.append("- " + cta_note)
    lines += [
        "- " + SPEC_SAFETY,
        "- " + NO_PRICE,
        "- " + HEADING_RULES,
        "- " + AI_EXTRACT,
        "- " + EVIDENCE,
        "- " + BODY_STYLE,
        "- " + INTERNAL_LINK,
        "- " + forbidden_block(),
        "- " + PRONOUN,
        f'- CTA link intro + outro, anchor "Sintech" → <a href="{HOMEPAGE}">Sintech</a> '
        f"(thẻ <a> thường, KHÔNG bọc <strong>).",
        f"- Signature CỐ ĐỊNH cuối bài (in nghiêng, có dấu chấm cuối): {SIGNATURE}",
    ]
    if is_product:
        lines += [
            "- " + H2_FIRST_PRODUCT,
            f'- Section "Vì sao nên mua tại Sintech": 2 đoạn × 2 câu, đoạn 2 chèn NGUYÊN VĂN: '
            f'"{POLICY_SENTENCE}"',
            '- Có section "Những điểm cần kiểm tra trước khi mua" dạng checklist H3 nhãn NGẮN '
            "(6-21 ký tự): Cổng trên máy / Nhu cầu đèn / Vị trí lắp…",
            "- " + SPEC_BLOCKQUOTE,
        ]
    else:
        lines.append("- " + MONEY_PAGE_LINK)
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
