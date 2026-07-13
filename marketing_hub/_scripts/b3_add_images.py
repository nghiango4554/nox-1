"""Chen 5 anh vo lam vao bai AutoCAD 2026 (id 1003053880).

Chuan anh BLOG (SINTECH_CONTENT_RULES): rong 600px, border-radius 8px, canh giua.
Ten file SEO: <chu-de>-<mo-ta>-sintechvn.webp
Anh 1 = anh bia (dat sau doan mo bai) + set lam anh dai dien bai.
4 anh con lai = chen TRUOC dung H2 tuong ung.

⚠️ Bam Luu trong admin Haravan se ghi de body_html -> chen anh SAU CUNG.
"""
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from PIL import Image

import faq_schema
import haravan_blog as hb
import haravan_client as hc

DL = Path(r"C:\Users\NGHIANGO\Downloads")
BLOG, ART = 1000960873, 1003053881   # bai Windows ban quyen

# (file, ten SEO, alt, H2 dich — None = anh bia dat sau doan mo bai)
IMAGES = [
    ("1f4cc411-a101-4187-b7a2-243d2ad22899.png",
     "windows-ban-quyen-khac-gi-ban-crack-sintechvn.webp",
     "Windows bản quyền khác gì bản crack khi dùng hằng ngày", None),
    ("2e365747-c928-47f0-ba9b-812a804117a3.png",
     "windows-oem-gan-theo-may-retail-theo-nguoi-dung-sintechvn.webp",
     "Giấy phép Windows OEM gắn theo máy còn Retail gắn theo người dùng", "OEM gắn theo máy"),
    ("a2f9f818-5705-45b8-83ec-1c1454a7e161.png",
     "chon-ban-windows-home-pro-workstations-sintechvn.webp",
     "Chọn bản Windows Home, Pro hay Pro for Workstations cho máy tính", "Chọn bản Windows nào"),
    ("063668b8-0fd9-470b-be47-2285f4128365.png",
     "chi-phi-cai-win-ban-quyen-phu-thuoc-gi-sintechvn.webp",
     "Chi phí cài Windows bản quyền phụ thuộc bản Windows, giấy phép và dịch vụ", "bao nhiêu tiền phụ thuộc gì"),
    ("9d32587c-5b4b-41e3-9ef9-a4b48609f907.png",
     "cai-win-ban-quyen-online-tai-shop-hay-tan-noi-sintechvn.webp",
     "Cài Windows bản quyền online, tại cửa hàng Sintech hay hỗ trợ tận nơi", "ở đâu, tại nhà hay online"),
]

IMG_STYLE = "max-width: 600px; width: 100%; height: auto; border-radius: 8px; display: block; margin: 0 auto;"


def to_webp_600(p: Path) -> bytes:
    im = Image.open(p).convert("RGB")
    w = 600
    h = round(im.height * w / im.width)
    im = im.resize((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=88, method=6)
    return buf.getvalue()


def fig(url: str, alt: str) -> str:
    return (f'<p style="text-align: center; margin: 16px 0px;">'
            f'<img src="{url}" alt="{alt}" style="{IMG_STYLE}"></p>')


def main():
    art = hb.get_article(BLOG, ART)
    body = art["body_html"]
    print(f"body hiện tại: {len(body)} ký tự · ảnh đang có: {body.count('<img')}")
    if body.count("<img") > 0:
        print("⚠️ Bài đã có ảnh — dừng, tránh chèn trùng.")
        return 1

    hero_url = None
    for i, (f, name, alt, anchor) in enumerate(IMAGES):
        src = DL / f
        data = to_webp_600(src)
        url = hc.upload_to_asset_storage(data, name, alt=alt)
        print(f"  [{i+1}/5] {len(data)//1024}KB · {name}")
        print(f"        {url}")

        if anchor is None:      # anh bia: dat sau doan van dau tien
            m = re.search(r"</p>", body)
            body = body[:m.end()] + "\n" + fig(url, alt) + body[m.end():]
            hero_url = url
        else:                   # chen TRUOC H2 tuong ung
            m = re.search(r'<h2[^>]*>(?:(?!</h2>).)*' + re.escape(anchor), body, re.S | re.I)
            if not m:
                print(f"        ⚠ KHÔNG tìm thấy H2 chứa '{anchor}' — bỏ qua ảnh này")
                continue
            body = body[:m.start()] + fig(url, alt) + "\n" + body[m.start():]

    body, n = faq_schema.attach(body)   # dung lai comment FAQ (vi body doi)
    fields = {"body_html": body}
    if hero_url:
        fields["image"] = {"src": hero_url}   # anh dai dien bai
    try:
        hb.update_article(BLOG, ART, fields)
    except Exception as e:
        print(f"  API báo: {str(e)[:60]}")

    chk = hb.get_article(BLOG, ART)["body_html"]
    print(f"\n[XONG] ảnh trong bài: {chk.count('<img')} · FAQ schema: {len(faq_schema.extract_faq(chk))} câu")
    return 0


if __name__ == "__main__":
    sys.exit(main())
