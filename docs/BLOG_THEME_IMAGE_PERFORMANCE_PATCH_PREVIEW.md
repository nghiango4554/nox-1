# BLOG THEME IMAGE PERFORMANCE PATCH — PREVIEW (diff thật, local)

> Khối CSS sẽ THÊM vào cuối `assets/blog_article_style.scss.liquid`. Local-only, CHƯA publish.

## File đổi: `assets/blog_article_style.scss.liquid` (+50 dòng)

Bản gốc tải về: `theme_patch_p10/backup/...` · Bản patched: `theme_patch_p10/patched/...`

## Khối CSS thêm (đã verify: Liquid if/endif cân, braces cân)

```scss

/* ════════════════════════════════════════════════════════════════════
   P10 — BLOG IMAGE PERFORMANCE PATCH (CSS-only) — CLS mitigation
   Lý do: Haravan strip mọi attr <img> trong body_html (chỉ giữ src) →
   ảnh inline không có width/height → reflow khi ảnh tải → CLS cao.
   Patch này KHÔNG đụng JS/layout, KHÔNG ảnh hưởng product/collection/home.
   FLAG: bọc trong Liquid IF settings.blog_image_perf_patch_enabled →
         mặc định OFF (setting chưa có = false). Bật = set setting true.
   Rollback: set flag false HOẶC revert file backup blog_article_style.scss.liquid.
   ════════════════════════════════════════════════════════════════════ */
{% if settings.blog_image_perf_patch_enabled %}
.article-content {
  /* (1) Ảnh inline responsive + KHÔNG méo + display block căn giữa */
  img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 12px auto;
    /* (2) Reserved space khử CLS — ảnh blog Sintech chuẩn 16:9 (600x338).
       object-fit: contain → ảnh lệch tỉ lệ chỉ letterbox, KHÔNG méo. */
    aspect-ratio: 16 / 9;
    object-fit: contain;
    background: #fafafa;
  }
  /* Ảnh đầu tiên (hero/LCP) — KHÔNG ép aspect để hiện đúng ngay, tránh letterbox hero */
  > p:first-of-type img:first-child,
  img:first-child {
    aspect-ratio: auto;
    background: transparent;
  }
  /* (3) Ổn định bảng responsive (wrapper overflow-x sống qua PUT) */
  .table-responsive,
  div[style*="overflow-x"] {
    max-width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  table {
    max-width: 100%;
  }
  /* (4) iframe (nếu có) giữ chỗ 16:9 tránh shift */
  iframe {
    max-width: 100%;
    aspect-ratio: 16 / 9;
  }
}
{% endif %}
/* ═══════════════ END P10 BLOG IMAGE PERFORMANCE PATCH ═══════════════ */

```

## Cách bật để code team test
1. Upload bản `patched/blog_article_style.scss.liquid` lên theme (hoặc copy khối CSS vào file thật).
2. Thêm setting `blog_image_perf_patch_enabled = true` (config/settings_data.json hoặc settings_schema).
3. Mở 5 URL P0 + QA list → kiểm tra CLS giảm, ảnh không méo, product/collection/home nguyên.
4. Đo CWV `/seo/cwv` đợt mới → so timeline `/seo/history`.

## Predicted impact
- **CLS**: ↓ rõ ở blog nhiều ảnh (reserved space). Đây là mục tiêu chính.
- **LCP/TBT**: ~ không đổi (CSS thuần, không thêm JS).
- **Rủi ro**: ảnh không-16:9 letterbox (khoảng trắng, không méo) — chấp nhận được, rollback dễ.

## Safety
no theme publish · no Haravan PUT · no upload · no commit/push/deploy.
