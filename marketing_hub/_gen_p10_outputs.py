# -*- coding: utf-8 -*-
"""Sinh 6 output P10 (CSS-only theme patch preview). Read-only, KHÔNG PUT."""
import csv, json
from pathlib import Path

DOCS = Path(__file__).parent.parent / "docs"
TP = Path(__file__).parent.parent / "theme_patch_p10"
after = json.load(open(Path(__file__).parent / "state" / "_p0_retest_after.json", encoding="utf-8"))

PATCH_FILE = "assets/blog_article_style.scss.liquid"
FLAG = "blog_image_perf_patch_enabled"

# QA URL set
P0 = [
    (2, "1002794878", "ChatGPT", "https://sintech.vn/blogs/huong-dan/cach-tai-va-su-dung-chat-gpt-cho-may-tinh-windows-macos-cap-nhat-20", "5 img inline"),
    (3, "1002753568", "PC bị giật điện", "https://sintech.vn/blogs/huong-dan/pc-bi-giat-dien-co-sao-khong-nguyen-nhan-cach-khac-phuc-tai-nha", "hero 360KB + table"),
    (4, "1002398567", "Sửa PC Q7", "https://sintech.vn/blogs/news/trung-tam-sua-pc-uy-tin-lay-ngay-o-quan-7", "4 table, 0 img"),
    (6, "1002404456", "Thu mua máy cũ", "https://sintech.vn/blogs/news/thu-mua-may-tinh-cu-gia-cao-tan-noi-tai-tphcm", "7 table, 0 img"),
    (10, "1002792621", "Test VGA", "https://sintech.vn/blogs/huong-dan/top-phan-mem-test-vga-card-man-hinh-hieu-qua-2025-giup-kiem-tra-hi", "11 img inline"),
]
EXTRA_BLOG = [
    ("blog inline nhiều", "https://sintech.vn/blogs/news/tim-hieu-ve-ep-xung-phuong-phap-tang-toc-do-va-suc-manh-cua-pc-co-tha", "22 img"),
    ("blog inline nhiều", "https://sintech.vn/blogs/news/lich-phat-phim-chieu-rap-thang-6-2026-dang-chu-y", "20 img"),
    ("blog inline nhiều", "https://sintech.vn/blogs/news/ifa-2024-co-gi-tai-gian-trung-bay-cua-samsung-do-gi-cung-tich-hop-a", "19 img"),
    ("blog 0 ảnh", "https://sintech.vn/blogs/news/cau-hinh-choi-cs2-counter-strike-2-tren-pc-laptop", "0 img (CS2, 8clk)"),
    ("blog 0 ảnh", "https://sintech.vn/blogs/news/top-10-thuong-hieu-linh-kien-may-tinh-duoc-yeu-thich-nhat-tai-viet-nam", "0 img"),
]
NON_BLOG = [
    ("product", "https://sintech.vn/products/laptop-lenovo-v15-g5-irl-83hf00brva-15-6-inch-fhd-8-512gb", "KHÔNG được ảnh hưởng"),
    ("collection", "https://sintech.vn/collections/macbook-air", "KHÔNG được ảnh hưởng"),
    ("homepage", "https://sintech.vn", "KHÔNG được ảnh hưởng"),
]

# ── 1. urls.csv ──
with open(DOCS / "blog_theme_image_perf_patch_urls.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["group", "type", "url", "note", "patch_applies"])
    for rank, aid, t, url, note in P0:
        w.writerow(["P0_applied", "blog", url, "#%d %s · %s" % (rank, t, note), "YES (.article-content)"])
    for typ, url, note in EXTRA_BLOG:
        w.writerow(["QA_blog", "blog", url, note, "YES (.article-content)"])
    for typ, url, note in NON_BLOG:
        w.writerow(["QA_nonblog", typ, url, note, "NO (chỉ .article-content blog)"])

# ── 2. before_after.csv ──
with open(DOCS / "blog_theme_image_perf_before_after.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["url", "type", "perf_before", "lcp_before", "cls_before", "tbt_before",
                "perf_after", "lcp_after", "cls_after", "tbt_after", "after_status", "predicted"])
    for rank, aid, t, url, note in P0:
        a = after[str(rank)]
        w.writerow([url, "blog", a["performance_score"], a["lcp_ms"], a["cls_score"], a["tbt_ms"],
                    "", "", "", "", "PENDING_LIVE (patch chưa publish)", "CLS↓ (reserved space 16:9), LCP/TBT ~same"])
    for typ, url, note in EXTRA_BLOG:
        w.writerow([url, "blog", "see deep_audit", "", "", "", "", "", "", "", "PENDING_LIVE", "CLS↓ kỳ vọng"])
    for typ, url, note in NON_BLOG:
        w.writerow([url, typ, "n/a", "", "", "", "", "", "", "", "PENDING_LIVE", "KHÔNG đổi (patch không target)"])

# ── 3. changed_files.txt ──
(DOCS / "blog_theme_image_perf_changed_files.txt").write_text(
    "P10 BLOG IMAGE PERF PATCH — CHANGED FILES (local-only, CHƯA publish)\n\n"
    "THEME (Haravan theme id 1001489132 — KHÔNG PUT, chỉ patch local):\n"
    "  assets/blog_article_style.scss.liquid   [SỬA: +%d dòng patch CSS có flag]\n\n"
    "Local artifacts:\n"
    "  theme_patch_p10/backup/blog_article_style.scss.liquid   (bản GỐC tải về)\n"
    "  theme_patch_p10/backup/article.liquid                   (gốc, tham chiếu, KHÔNG sửa)\n"
    "  theme_patch_p10/patched/blog_article_style.scss.liquid  (bản ĐÃ PATCH)\n"
    "  theme_patch_p10/patch_block.scss.liquid                 (chỉ khối thêm)\n\n"
    "Số file theme đổi: 1 (chỉ CSS blog). article.liquid/blog.liquid/theme.liquid KHÔNG đụng.\n"
    "Settings cần thêm để BẬT: %s = true (mặc định không có = OFF an toàn).\n"
    % (50, FLAG), encoding="utf-8")

# ── 4. rollback.md ──
(DOCS / "blog_theme_image_perf_rollback.md").write_text(
    "# P10 — Rollback (CSS-only blog image patch)\n\n"
    "Patch CHƯA publish (local). Khi/ nếu đã publish, có 2 cách rollback:\n\n"
    "## Cách 1 — Tắt flag (nhanh, không revert file)\n"
    "- Set theme setting `%s = false` (hoặc xoá setting) → khối CSS bị Liquid loại bỏ, "
    "blog về hành vi cũ ngay. Không ảnh hưởng gì khác.\n\n"
    "## Cách 2 — Revert file backup\n"
    "- Ghi đè `assets/blog_article_style.scss.liquid` bằng bản gốc ở "
    "`theme_patch_p10/backup/blog_article_style.scss.liquid`.\n\n"
    "## An toàn\n"
    "- Patch chỉ thêm CSS dưới `.article-content` (blog body) → KHÔNG đụng product/collection/home.\n"
    "- Mặc định flag OFF: kể cả khi file đã lên theme, nếu chưa bật setting thì KHÔNG có hiệu lực.\n"
    "- KHÔNG xoá file, KHÔNG đổi JS/layout.\n" % FLAG, encoding="utf-8")

# ── 5. PLAN.md ──
patch_text = (TP / "patch_block.scss.liquid").read_text(encoding="utf-8")
(DOCS / "BLOG_THEME_IMAGE_PERFORMANCE_PATCH_PLAN.md").write_text(
    "# BLOG THEME IMAGE PERFORMANCE PATCH — PLAN (CSS-only, local preview)\n\n"
    "> P10 phạm vi **CSS-only** (vợ chốt). Sửa CLS/LCP blog ở tầng theme vì Haravan strip attr `<img>` "
    "trong body_html. **KHÔNG publish · KHÔNG PUT Haravan · KHÔNG deploy · KHÔNG commit.** Chỉ patch local + preview.\n\n"
    "## 1. Gốc vấn đề\n"
    "- Live `<img>` chỉ còn `src` (Haravan strip loading/fetchpriority/width/height/alt/class/style).\n"
    "- Body không có width/height → reflow khi ảnh tải → CLS cao (retest: CLS 5 bài không giảm).\n"
    "- `<div>/<table>` style + content cleanup thì SỐNG.\n\n"
    "## 2. File target (đã scan, KHÔNG giả định)\n"
    "- Wrapper body blog: `<div class=\"rte article-content\">{{ article.content }}</div>` (templates/article.liquid).\n"
    "- CSS blog: `assets/blog_article_style.scss.liquid` — **chưa có rule img nào cho .article-content** → đúng chỗ thêm.\n"
    "- Theme đã có lazyload riêng cho ảnh THUMBNAIL list (`class=lazyload data-src`) — KHÔNG đụng.\n\n"
    "## 3. Patch strategy (CSS-only)\n"
    "- `.article-content img`: max-width 100% + height auto + display block (responsive, không méo).\n"
    "- **Reserved space khử CLS**: `aspect-ratio:16/9` + `object-fit:contain` + nền nhạt. Ảnh blog Sintech chuẩn "
    "16:9 (600×338) nên vừa khít; ảnh lệch tỉ lệ chỉ letterbox, **KHÔNG méo**.\n"
    "- Ảnh ĐẦU TIÊN (hero/LCP) để `aspect-ratio:auto` — hiện đúng ngay, không letterbox hero.\n"
    "- Ổn định `.table-responsive`/`div[overflow-x]` + iframe 16:9.\n"
    "- **KHÔNG** JS, **KHÔNG** lazy-load (cần JS/attr — ngoài phạm vi CSS-only), **KHÔNG** đụng layout/global.\n\n"
    "## 4. Feature flag\n"
    f"- Khối CSS bọc trong Liquid `IF settings.{FLAG}`. Mặc định OFF (setting chưa có = false → CSS không xuất).\n"
    f"- Bật: thêm setting `{FLAG}=true` (settings_schema/config). Tắt/rollback: set false hoặc revert backup.\n\n"
    "## 5. Hạn chế trung thực (CSS-only)\n"
    "- CSS không set được width/height THẬT từng ảnh (Haravan strip) → dùng aspect-ratio 16:9 giả định. "
    "Ảnh không-16:9 sẽ có nền letterbox (không méo, nhưng có khoảng trắng).\n"
    "- Lazy-load + alt + fetchpriority-hero **không làm được bằng CSS** → vẫn cần JS/Liquid (gói riêng, ngoài P10 này).\n"
    "- **After-metrics đo thật cần publish** (Haravan API ghi thẳng theme live, không staging) → preview này chỉ dự đoán.\n\n"
    "## 6. QA (xem urls.csv): 5 bài P0 + 3 blog ảnh nhiều + 2 blog 0 ảnh + product/collection/home.\n"
    "Mục tiêu: blog CLS↓, ảnh không méo/không mất, product/collection/home KHÔNG đổi, không lỗi console, TBT không tăng.\n\n"
    "## 7. Exports\n- BLOG_THEME_IMAGE_PERFORMANCE_PATCH_PLAN.md\n- BLOG_THEME_IMAGE_PERFORMANCE_PATCH_PREVIEW.md\n"
    "- blog_theme_image_perf_patch_urls.csv\n- blog_theme_image_perf_before_after.csv\n"
    "- blog_theme_image_perf_changed_files.txt\n- blog_theme_image_perf_rollback.md\n\n"
    "## Safety\nno theme publish · no Haravan PUT · no upload · no commit/push/deploy · product/collection/home unaffected.\n",
    encoding="utf-8")

# ── 6. PREVIEW.md (kèm diff thật) ──
(DOCS / "BLOG_THEME_IMAGE_PERFORMANCE_PATCH_PREVIEW.md").write_text(
    "# BLOG THEME IMAGE PERFORMANCE PATCH — PREVIEW (diff thật, local)\n\n"
    "> Khối CSS sẽ THÊM vào cuối `assets/blog_article_style.scss.liquid`. Local-only, CHƯA publish.\n\n"
    "## File đổi: `assets/blog_article_style.scss.liquid` (+50 dòng)\n\n"
    "Bản gốc tải về: `theme_patch_p10/backup/...` · Bản patched: `theme_patch_p10/patched/...`\n\n"
    "## Khối CSS thêm (đã verify: Liquid if/endif cân, braces cân)\n\n"
    "```scss\n" + patch_text + "\n```\n\n"
    "## Cách bật để code team test\n"
    "1. Upload bản `patched/blog_article_style.scss.liquid` lên theme (hoặc copy khối CSS vào file thật).\n"
    f"2. Thêm setting `{FLAG} = true` (config/settings_data.json hoặc settings_schema).\n"
    "3. Mở 5 URL P0 + QA list → kiểm tra CLS giảm, ảnh không méo, product/collection/home nguyên.\n"
    "4. Đo CWV `/seo/cwv` đợt mới → so timeline `/seo/history`.\n\n"
    "## Predicted impact\n"
    "- **CLS**: ↓ rõ ở blog nhiều ảnh (reserved space). Đây là mục tiêu chính.\n"
    "- **LCP/TBT**: ~ không đổi (CSS thuần, không thêm JS).\n"
    "- **Rủi ro**: ảnh không-16:9 letterbox (khoảng trắng, không méo) — chấp nhận được, rollback dễ.\n\n"
    "## Safety\nno theme publish · no Haravan PUT · no upload · no commit/push/deploy.\n",
    encoding="utf-8")

print("WROTE 6 files:")
for n in ("BLOG_THEME_IMAGE_PERFORMANCE_PATCH_PLAN.md", "BLOG_THEME_IMAGE_PERFORMANCE_PATCH_PREVIEW.md",
          "blog_theme_image_perf_patch_urls.csv", "blog_theme_image_perf_before_after.csv",
          "blog_theme_image_perf_changed_files.txt", "blog_theme_image_perf_rollback.md"):
    print("  %6d B  %s" % ((DOCS / n).stat().st_size, n))
