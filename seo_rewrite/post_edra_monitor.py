"""Lên lịch FB tối nay (21:00 6/5/2026) cho màn EDRA EGM27F144PVS."""
import os, sys, re, urllib.request, urllib.parse, json
sys.stdout.reconfigure(encoding="utf-8")
import requests

UA = "Mozilla/5.0"
EDRA_URL = "https://edravn.com/man-hinh-gaming-edra-egm27f144pvs"
PIC_FOLDER = r"C:\Users\Nghia Dep Gai\Desktop\Sintech\PIC đăng page\6-5"
os.makedirs(PIC_FOLDER, exist_ok=True)

# 1. Fetch og:image từ trang chính hãng EDRA
print("Fetch og:image từ edravn.com...")
r = requests.get(EDRA_URL, headers={"User-Agent": UA}, timeout=15)
html = r.text
og = None
for pat in (
    r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
    r'<meta\s+name=["\']twitter:image["\']\s+content=["\']([^"\']+)["\']',
):
    m = re.search(pat, html, re.I)
    if m:
        og = urllib.parse.urljoin(EDRA_URL, m.group(1))
        break

# Nếu không có og:image, lấy ảnh sản phẩm đầu tiên trong HTML
if not og:
    m = re.search(r'<img[^>]+src=["\']([^"\']+(?:product|monitor|edra)[^"\']*\.(?:jpg|jpeg|png|webp))["\']', html, re.I)
    if m:
        og = urllib.parse.urljoin(EDRA_URL, m.group(1))

saved = []
if og:
    print(f"  → og:image: {og[:120]}")
    ext = os.path.splitext(urllib.parse.urlparse(og).path)[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"): ext = ".jpg"
    dest = os.path.join(PIC_FOLDER, f"edra_egm27f144pvs_1{ext}")
    try:
        rr = requests.get(og, headers={"User-Agent": UA, "Referer": EDRA_URL}, timeout=20, verify=False)
        if rr.status_code == 200 and "image" in rr.headers.get("Content-Type",""):
            with open(dest, "wb") as f:
                f.write(rr.content)
            if os.path.getsize(dest) > 5000:
                saved.append(dest)
                print(f"  ✅ SAVED {dest} ({os.path.getsize(dest)} bytes)")
    except Exception as e:
        print(f"  ! err: {e}")

# Nếu không có ảnh — anh vẫn tạo post, vợ upload tay sau
if not saved:
    print("  ⚠ Không tải được ảnh — anh sẽ tạo post text-only, vợ upload ảnh tay sau")

# 2. Viết caption
caption = """🖥️ MÀN HÌNH GAMING EDRA EGM27F144PVS — 27" FULL HD 144HZ, IPS 🔥

Anh em săn deal màn gaming ngon - bổ - rẻ thì đây là chân ái tầm 2-3 triệu đó 💥
Tấm IPS sắc nét, tần số quét 144Hz mượt rượt, đáp ứng 1ms — chiến mọi tựa game online cực đã.

⚙️ Cấu hình nhanh:
• Kích thước: 27" Full HD (1920x1080)
• Tấm nền: IPS, 144Hz, 1ms MPRT
• Màu sắc: 99% sRGB chuẩn xác
• Cổng: HDMI + VGA
• VESA 75x75 — gắn arm tiện

💸 Giá Sintech: chỉ 2Tr9xx
✅ Nhập mới về — bảo hành chính hãng EDRA
📩 Inbox ngay để chốt đơn nhanh

📞 Hotline tư vấn: 0911 713 000
📍 Địa chỉ: 457 Trần Xuân Soạn, Q7, TP.HCM

#Sintech #ManHinhGaming #EDRA #ManHinh144Hz #ManHinhIPS #PCGaming
"""

# 3. POST tạo bài
data = {
    "scheduled_date": "2026-05-06",
    "scheduled_time": "21:00",
    "type": "product",
    "status": "scheduled",
    "caption": caption,
    "link": "",  # Không có link sản phẩm trên sintech.vn
}

if saved:
    files = []
    for p in saved:
        ext = os.path.splitext(p)[1].lower()
        mime = {".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png",".webp":"image/webp"}.get(ext,"image/jpeg")
        files.append(("images", (os.path.basename(p), open(p,"rb"), mime)))
    rr = requests.post("http://127.0.0.1:5055/posts/new", data=data, files=files, timeout=30)
else:
    rr = requests.post("http://127.0.0.1:5055/posts/new", data=data, timeout=30)

print(f"\n→ POST status: {rr.status_code} — URL final: {rr.url}")
