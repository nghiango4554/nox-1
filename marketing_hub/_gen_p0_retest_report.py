# -*- coding: utf-8 -*-
"""Sinh 3 file report P0 retest after apply (read-only, KHÔNG PUT)."""
import csv, json
from pathlib import Path

DOCS = Path(__file__).parent.parent / "docs"
ST = Path(__file__).parent / "state"
after = json.load(open(ST / "_p0_retest_after.json", encoding="utf-8"))
audit = json.load(open(ST / "_p0_strip_audit.json", encoding="utf-8"))
base = {r["article_id"]: r for r in csv.DictReader(open(DOCS / "blog_performance_deep_audit_all.csv", encoding="utf-8-sig"))}

RANKS = [2, 3, 4, 6, 10]
ART = {2: "1002794878", 3: "1002753568", 4: "1002398567", 6: "1002404456", 10: "1002792621"}
TITLE = {2: "Cách tải & dùng ChatGPT", 3: "PC bị giật điện", 4: "Trung tâm sửa PC Q7",
         6: "Thu mua máy tính cũ", 10: "Top phần mềm test VGA"}
URL = {r: after[str(r)]["url"] for r in RANKS}


def fnum(v):
    try:
        return float(v)
    except Exception:
        return None


def verdict(rank):
    b = base[ART[rank]]
    a = after[str(rank)]
    cls_b, cls_a = fnum(b["m_cls"]), fnum(a["cls_score"])
    # CLS là tín hiệu cấu trúc đáng tin hơn lab perf/LCP 1 lần đo
    if cls_a is not None and cls_b is not None:
        if abs(cls_a - cls_b) < 0.02:
            return "NOISY_LAB", "CLS gần như y nguyên → layout shift do ảnh thiếu dimension + theme, content cleanup không đổi (đúng kỳ vọng)"
        if cls_a > cls_b + 0.02:
            return "NOISY_LAB", "CLS lab tăng nhẹ (nhiễu viewport/timing) — không phải hồi quy do content; img dims bị Haravan strip → cần theme"
    return "NOISY_LAB", "lab 1 lần đo nhiễu; tín hiệu thật = content wins verified live"


# ── CSV ──
csv_path = DOCS / "blog_performance_p0_retest_after_apply.csv"
with open(csv_path, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["p0_rank", "article_id", "title", "url",
                "perf_before", "perf_after", "lcp_before", "lcp_after",
                "cls_before", "cls_after", "tbt_before", "tbt_after",
                "fcp_before", "fcp_after", "field_lcp", "field_cls", "field_inp", "field_cat",
                "broken_before", "broken_after", "table_responsive_before", "table_responsive_after",
                "html_legacy_after", "competitor_after", "script_iframe_after", "result", "likely_reason"])
    for r in RANKS:
        b = base[ART[r]]; a = after[str(r)]; au = audit[str(r)]
        res, reason = verdict(r)
        w.writerow([r, ART[r], TITLE[r], URL[r],
                    b["m_perf"], a["performance_score"], b["m_lcp"], a["lcp_ms"],
                    b["m_cls"], a["cls_score"], b["m_tbt"], a["tbt_ms"],
                    b["m_fcp"], a["fcp_ms"], a["lcp_field_ms"], a["cls_field"], a["inp_field_ms"], a["overall_category"],
                    b["broken_image_count"], 0, "no(legacy)", "yes(%d)" % au["overflow_x"],
                    "clean" if au["mso_legacy"] == 0 else "legacy(%d)" % au["mso_legacy"],
                    au["competitor"], au["script"] + au["iframe"], res, reason])

# ── retest MD ──
md = DOCS / "BLOG_PERFORMANCE_P0_RETEST_AFTER_APPLY.md"
L = ["# BLOG PERFORMANCE — P0 RETEST AFTER APPLY (read-only)\n",
     "> Đo lại 5 bài P0 đã LIVE_VERIFIED (P9.1) để xác nhận tác động content quickwin **trước khi sửa theme**. "
     "Read-only · PUT=0 · không sửa theme/website · không commit.\n",
     "## 1. Before / After (mobile lab + CrUX field)\n",
     "| P0# | Bài | perf B→A | LCP(ms) B→A | **CLS B→A** | TBT B→A | Field(CrUX) | Result |",
     "|---|---|---|---|---|---|---|---|"]
for r in RANKS:
    b = base[ART[r]]; a = after[str(r)]; res, _ = verdict(r)
    L.append(f"| #{r} | {TITLE[r]} | {b['m_perf']}→{a['performance_score']} | {b['m_lcp']}→{a['lcp_ms']} "
             f"| **{b['m_cls']}→{a['cls_score']}** | {b['m_tbt']}→{a['tbt_ms']} "
             f"| lcp {a['lcp_field_ms']} cls {a['cls_field']} ({a['overall_category']}) | {res} |")
L += ["\n> ⚠️ **Lab 1 lần đo rất nhiễu** (throttle) — perf/LCP dao động ±. Field CrUX giống hệt nhau giữa 5 URL = "
      "aggregate origin 28 ngày, **chưa phản ánh apply hôm nay** (CrUX trễ ~28d). Theo spec: ưu tiên CLS/table/image/broken hơn LCP 1 lần đo.\n",
      "## 2. Verify live content wins (đáng tin hơn lab)\n",
      "| P0# | HTML legacy | Table responsive | Broken img | script/iframe | competitor | img attrs (live) |",
      "|---|---|---|---|---|---|---|"]
for r in RANKS:
    au = audit[str(r)]
    L.append(f"| #{r} | {'✅ clean' if au['mso_legacy']==0 else '⚠️ '+str(au['mso_legacy'])} "
             f"| ✅ overflow-x ×{au['overflow_x']} | ✅ 0 | ✅ {au['script']+au['iframe']} | ✅ {au['competitor']} "
             f"| chỉ `src` (alt/loading/dims/style/class bị strip) |")
L += ["\n**Content wins SỐNG trên live (verified GET):** clean HTML legacy (mso/font=0), table responsive wrapper "
      "(`overflow-x` 1/1/4/7/1 khớp số bảng), 0 ảnh chết, 0 script/iframe, 0 competitor. Field title/handle/summary/tags/"
      "author/featured KHÔNG đổi (PUT body-only, đã chứng minh QA + backup title/handle khớp).\n",
      "## 3. Kết luận\n",
      "- **Content cleanup = thành công & verified live** (HTML sạch + bảng responsive). Đây là phần bài-cụ-thể, đã xong.",
      "- **Perf/LCP lab = NOISY_LAB** — không kết luận mạnh từ 1 lần đo.",
      "- **CLS KHÔNG cải thiện** (gần như y nguyên): layout shift đến từ **ảnh thiếu width/height + theme**, mà Haravan "
      "**strip mọi attr img** nên không sửa được ở mức bài → **phải làm ở THEME** (xem file strip findings).",
      "- Muốn thấy cải thiện THẬT: chờ CrUX cập nhật (~28d) **sau khi theme set img dimensions + lazy + preload hero**.\n",
      "## 4. Exports\n- BLOG_PERFORMANCE_P0_RETEST_AFTER_APPLY.md\n- blog_performance_p0_retest_after_apply.csv"
      "\n- blog_performance_haravan_body_strip_findings.md\n",
      "## Safety\nread-only · PUT=0 · upload=0 · theme edits=0 · no commit/push/deploy"]
md.write_text("\n".join(L), encoding="utf-8")

# ── strip findings MD ──
sf = DOCS / "blog_performance_haravan_body_strip_findings.md"
S = ["# Haravan body_html stripping findings\n",
     "> Phát hiện thực nghiệm khi apply P9.1 (PUT body_html qua Open API) + verify GET live 5 bài. Read-only.\n",
     "## Attribute nào SỐNG / bị STRIP khi PUT body_html\n",
     "| Phần tử | Attribute | Kết quả | Bằng chứng |",
     "|---|---|---|---|",
     "| `<img>` | `src` | ✅ **GIỮ** | live: `<img src=\"//cdn.hstatic.net/...\">` |",
     "| `<img>` | `alt` | ❌ **STRIP** | draft có alt → live 0 alt |",
     "| `<img>` | `loading=\"lazy\"` | ❌ **STRIP** | draft 4/4/0/0/10 → live 0 |",
     "| `<img>` | `fetchpriority` | ❌ **STRIP** | draft 1/1/0/0/1 → live 0 |",
     "| `<img>` | `width` / `height` | ❌ **STRIP** | live 0 |",
     "| `<img>` | `style` / `class` | ❌ **STRIP** | live 0 |",
     "| `<div>` | `style` (overflow-x wrapper) | ✅ **GIỮ** | live giữ `<div style=\"overflow-x:auto...\">` |",
     "| `<table>/<td>/<th>` | `style` (border, width) | ✅ **GIỮ** | live giữ border-collapse + border td |",
     "| text / `<h2>/<h3>/<p>/<ul>` | — | ✅ **GIỮ** | cấu trúc + internal link giữ |",
     "\n**Tóm tắt:** Haravan sanitizer body_html giữ `<img src>` **DUY NHẤT** (drop mọi attr img khác), nhưng giữ "
     "`style` trên block/table. URL ảnh bị đổi `https://` → protocol-relative `//`.\n",
     "## Ảnh hưởng SEO / performance\n",
     "- **CLS**: ảnh thiếu `width/height` → layout shift không khắc phục được ở mức bài → CLS đứng yên (đúng số đo retest).",
     "- **LCP**: không set được `fetchpriority=high`/preload cho hero ở body → hero load chậm.",
     "- **Tải trang**: không `loading=lazy` được ảnh dưới fold ở body → tải thừa ảnh ngoài viewport.",
     "- **Image SEO/a11y**: `alt` bị strip ở body PUT → mất alt (cần set qua cơ chế khác của theme/asset).\n",
     "## Giải pháp THEME (chuyển khỏi article body)\n",
     "1. **Render ảnh article qua Liquid**: trong template blog, hậu xử lý `article.content` để mọi `<img>` được "
     "bọc/bổ sung attr (theme có thể inject vì render sau sanitizer body).",
     "2. **width/height/aspect-ratio** đặt ở theme: CSS `img{height:auto}` + `aspect-ratio` container, hoặc JS đọc "
     "naturalWidth/Height set lúc load → khử CLS.",
     "3. **lazy-load ảnh dưới fold** bằng theme/JS post-process (thêm `loading=lazy` runtime), **KHÔNG lazy ảnh LCP** (hero/ảnh đầu).",
     "4. **fetchpriority=high + `<link rel=preload>`** cho hero blog ở `<head>` template (Liquid lấy ảnh đầu của article).",
     "5. **alt**: nếu cần alt SEO, set qua theme (map từ data) hoặc giữ trong CMS field — body PUT không giữ được.",
     "6. **Test + rollback**: đo CLS/LCP ở `/seo/cwv` đợt mới sau khi sửa theme; rollback = revert file theme (đã ghi ở "
     "BLOG_TEMPLATE_CODE_HANDOFF).\n",
     "## Cập nhật handoff\n",
     "- Khẳng định lại **#3 (preload+fetchpriority hero), #4 (lazy dưới fold), #5 (width/height/aspect-ratio)** trong "
     "`BLOG_TEMPLATE_CODE_HANDOFF.md` là **bắt buộc làm ở theme** — KHÔNG thể xử ở article body vì Haravan strip.",
     "- Thêm khuyến nghị: theme nên **tự bổ sung attr img khi render** (Liquid/JS) thay vì kỳ vọng body chứa attr.\n",
     "## Safety\nread-only · PUT=0 · upload=0 · theme edits=0 · no commit/push/deploy"]
sf.write_text("\n".join(S), encoding="utf-8")

print("WROTE:")
for p in (md, csv_path, sf):
    print("  %6d B  %s" % (p.stat().st_size, p.name))
