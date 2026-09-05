"""Blog topic taxonomy — constants + pure classifier.

Dùng chung bởi routes/system.py (Competitors page) và routes/haravan.py
(Haravan blogs page). Tách riêng để tránh circular import giữa các
module routes/* khi cần cùng 1 taxonomy.

Order matters: rule cụ thể trước, generic sau (vd "pirate" check trước "tutorial").
"""

BLOG_TOPICS = [
    ("pirate",   "⚠️ Crack / Pirate",    "rgba(239,68,68,0.15)",  ["full 100", "full crack", "active key", "kích hoạt key", "key bản quyền"]),
    ("service",  "🛠️ Dịch vụ Sintech",   "rgba(34,197,94,0.15)",  ["sửa chữa", "sua chua", "dịch vụ", "tphcm", "quận"]),
    ("review",   "📖 Review",            "rgba(168,85,247,0.15)", ["review", "đánh giá", "danh gia"]),
    ("compare",  "🆚 So sánh",           "rgba(236,72,153,0.15)", ["so sánh", "so sanh", " vs ", "vs."]),
    ("build_pc", "🧰 Build PC",          "rgba(245,158,11,0.15)", ["build pc", "cấu hình pc", "cau hinh pc", "build cấu hình"]),
    ("top",      "🏆 Top / List",        "rgba(251,146,60,0.15)", ["top ", "best ", "những "]),
    ("promo",    "💰 Khuyến mãi",        "rgba(34,197,94,0.15)",  ["khuyến mãi", "khuyen mai", "sale", "giảm giá", "ưu đãi"]),
    ("gaming",   "🎮 Gaming",            "rgba(99,102,241,0.15)", ["tựa game", "tua game", "fps", "moba", "esport", "gaming "]),
    ("tutorial", "📝 Hướng dẫn",         "rgba(59,130,246,0.15)", ["hướng dẫn", "huong dan", "cách ", "tutorial", "tips", "thủ thuật"]),
    ("news",     "📰 Tin tức",           "rgba(14,165,233,0.15)", ["tin tức", "tin tuc", "news", "ra mắt", "ra mat", "công bố"]),
    ("explain",  "💡 Giải thích",        "rgba(20,184,166,0.15)", [" là gì", "la gi", "có nên", "co nen", "khác gì", "khac gi"]),
]
BLOG_TOPIC_LABELS = {code: (label, color) for code, label, color, _ in BLOG_TOPICS}
BLOG_TOPIC_LABELS["other"] = ("❓ Khác", "rgba(120,120,140,0.15)")


def classify_blog_topic(title: str, url: str = "") -> str:
    """Detect chủ đề blog theo keyword trong TITLE. Tham số `url` bị BỎ QUA hoàn toàn.

    ⚠️ ĐÂY LÀ NGUỒN DUY NHẤT. Cả blog Sintech (routes/system.py) lẫn URL đối thủ
    (competitors.py) phải gọi hàm này — bảng "Topic gap" ở /competitors lấy hiệu của
    hai vế, nên hai vế BẮT BUỘC dùng chung một thước.

    4/9/2026: trước đây competitors.py giữ bản sao riêng `BLOG_TOPICS_RULES` — lệch cả
    thứ tự lẫn từ khoá (service nằm CUỐI thay vì thứ 2, thiếu "tphcm"/"quận",
    thiếu "build cấu hình", thiếu "khac gi"). Đo trên 266 blog Sintech: **11 bài (4,1%)
    ra 2 kết quả khác nhau**, dồn hết vào topic `service` — thước này đếm 14, thước kia
    đếm 3. Nghĩa là cột "Đối thủ có" và cột "Sintech có" đang đo bằng 2 cây thước khác
    nhau, gap của mảng dịch vụ sửa chữa bị âm giả. Đừng tách bản sao lần nữa.

    ⚠️ `url` CỐ Ý bị bỏ qua, chữ ký giữ lại chỉ cho tương thích caller cũ. Thử nhét url
    vào chuỗi phân loại một lần rồi phải gỡ: blog Sintech dùng handle **/news/**, trùng
    keyword của topic "news" → 113/268 bài bị gán nhầm thành Tin tức (trước chỉ 8).
    Đường dẫn còn nhiều từ trùng keyword khác nữa. Phân loại theo title, chấm hết.
    """
    t = (title or "").lower()
    for code, _label, _color, keywords in BLOG_TOPICS:
        if any(kw in t for kw in keywords):
            return code
    return "other"
