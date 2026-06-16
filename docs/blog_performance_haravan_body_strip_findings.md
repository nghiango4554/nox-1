# Haravan body_html stripping findings

> Phát hiện thực nghiệm khi apply P9.1 (PUT body_html qua Open API) + verify GET live 5 bài. Read-only.

## Attribute nào SỐNG / bị STRIP khi PUT body_html

| Phần tử | Attribute | Kết quả | Bằng chứng |
|---|---|---|---|
| `<img>` | `src` | ✅ **GIỮ** | live: `<img src="//cdn.hstatic.net/...">` |
| `<img>` | `alt` | ❌ **STRIP** | draft có alt → live 0 alt |
| `<img>` | `loading="lazy"` | ❌ **STRIP** | draft 4/4/0/0/10 → live 0 |
| `<img>` | `fetchpriority` | ❌ **STRIP** | draft 1/1/0/0/1 → live 0 |
| `<img>` | `width` / `height` | ❌ **STRIP** | live 0 |
| `<img>` | `style` / `class` | ❌ **STRIP** | live 0 |
| `<div>` | `style` (overflow-x wrapper) | ✅ **GIỮ** | live giữ `<div style="overflow-x:auto...">` |
| `<table>/<td>/<th>` | `style` (border, width) | ✅ **GIỮ** | live giữ border-collapse + border td |
| text / `<h2>/<h3>/<p>/<ul>` | — | ✅ **GIỮ** | cấu trúc + internal link giữ |

**Tóm tắt:** Haravan sanitizer body_html giữ `<img src>` **DUY NHẤT** (drop mọi attr img khác), nhưng giữ `style` trên block/table. URL ảnh bị đổi `https://` → protocol-relative `//`.

## Ảnh hưởng SEO / performance

- **CLS**: ảnh thiếu `width/height` → layout shift không khắc phục được ở mức bài → CLS đứng yên (đúng số đo retest).
- **LCP**: không set được `fetchpriority=high`/preload cho hero ở body → hero load chậm.
- **Tải trang**: không `loading=lazy` được ảnh dưới fold ở body → tải thừa ảnh ngoài viewport.
- **Image SEO/a11y**: `alt` bị strip ở body PUT → mất alt (cần set qua cơ chế khác của theme/asset).

## Giải pháp THEME (chuyển khỏi article body)

1. **Render ảnh article qua Liquid**: trong template blog, hậu xử lý `article.content` để mọi `<img>` được bọc/bổ sung attr (theme có thể inject vì render sau sanitizer body).
2. **width/height/aspect-ratio** đặt ở theme: CSS `img{height:auto}` + `aspect-ratio` container, hoặc JS đọc naturalWidth/Height set lúc load → khử CLS.
3. **lazy-load ảnh dưới fold** bằng theme/JS post-process (thêm `loading=lazy` runtime), **KHÔNG lazy ảnh LCP** (hero/ảnh đầu).
4. **fetchpriority=high + `<link rel=preload>`** cho hero blog ở `<head>` template (Liquid lấy ảnh đầu của article).
5. **alt**: nếu cần alt SEO, set qua theme (map từ data) hoặc giữ trong CMS field — body PUT không giữ được.
6. **Test + rollback**: đo CLS/LCP ở `/seo/cwv` đợt mới sau khi sửa theme; rollback = revert file theme (đã ghi ở BLOG_TEMPLATE_CODE_HANDOFF).

## Cập nhật handoff

- Khẳng định lại **#3 (preload+fetchpriority hero), #4 (lazy dưới fold), #5 (width/height/aspect-ratio)** trong `BLOG_TEMPLATE_CODE_HANDOFF.md` là **bắt buộc làm ở theme** — KHÔNG thể xử ở article body vì Haravan strip.
- Thêm khuyến nghị: theme nên **tự bổ sung attr img khi render** (Liquid/JS) thay vì kỳ vọng body chứa attr.

## Safety
read-only · PUT=0 · upload=0 · theme edits=0 · no commit/push/deploy