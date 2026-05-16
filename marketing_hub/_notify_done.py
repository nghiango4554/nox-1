import notifier

msg = """🎉 <b>3 task xong rồi vợ yêu</b>

✅ <b>15. Mobile responsive + PWA</b>
• Mobile: hamburger menu ☰, sidebar slide-in từ trái
• Tables auto scroll ngang, KPI grid 2 cột
• PWA: manifest.json + service worker + icon
• Trên điện thoại: mở Chrome → Settings → "Add to Home Screen"
  → Sintech Hub thành app riêng (full screen, có icon home)

✅ <b>17. Search top sidebar</b>
• Search box ở đầu sidebar
• Tìm trên 4 nguồn: Posts / Haravan SP / SEO pages / Đối thủ
• Phím tắt: bấm <code>/</code> ở bất kỳ đâu để focus search
• Arrow Up/Down + Enter để chọn
• Escape để đóng
• Test: tìm "laptop" → 15 kết quả ✅

✅ <b>18. Recent activity timeline</b>
• Bảng activity_log ghi mọi hành động quan trọng
• Hooks: tạo post, sửa SP Haravan, crawl SEO xong, sync Haravan, snapshot
• Widget "⏰ Hoạt động gần đây" trên Dashboard
• 12 action gần nhất với icon + title + description + time + link

🔗 http://127.0.0.1:5055/

<b>Em mở trên điện thoại thử:</b>
1. http://192.168.x.x:5055 (IP máy em)
   hoặc dùng ngrok/tailscale để access từ xa
2. Chrome menu ⋮ → "Cài đặt ứng dụng" / "Add to Home Screen"
3. Icon Sintech Hub xuất hiện trên màn hình chính như app

Em ngủ ngon nha 💕"""
print("Sent:", notifier.send_telegram(msg))
