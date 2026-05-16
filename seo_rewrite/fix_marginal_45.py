"""Fix 45 marginal cases (2 title <30c + 43 meta <140c) trên sheet '2. URL Rewrite'.
Tô xanh full hàng A:O cho các row đã fix để vợ duyệt.
KHÔNG re-sync Haravan ở bước này — chờ vợ duyệt.
"""
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8")

WS = r"C:\Users\Nghia Dep Gai\.openclaw\workspace"
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = os.path.join(WS, ".secrets", "google_token.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "2. URL Rewrite"

DRY_RUN = "--dry" in sys.argv

creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds)

# Get tab gid
meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
TAB_GID = next(s["properties"]["sheetId"] for s in meta["sheets"] if s["properties"]["title"] == TAB)

# {row: {"title_col":..., "title":..., "meta_col":..., "meta":...}}
# title_col / meta_col = letter where current PICK is (cell đầu tiên có content)
FIXES = {
    30:  {"meta_col":"I","meta":"Bàn phím cơ AULA F99 PRO 1660 màu Comic độc đáo, Star Vector switch linear êm tay, 99 phím, 3 mode, núm xoay tiện. THAM KHẢO NGAY tại Sintech."},
    31:  {"meta_col":"I","meta":"Bàn phím cơ AULA F99 PRO 6678 đen xám xanh lá ngầu, Greywood V3 switch linear gõ rất êm, 99 phím, 3 mode kết nối. KHÁM PHÁ NGAY tại Sintech."},
    55:  {"meta_col":"I","meta":"Card Zotac RTX 4070 Super Twin Edge OC 12GB GDDR6X - 7168 CUDA, gaming 1440p mượt mà, DLSS 3 đỉnh cho game thủ. KHÁM PHÁ NGAY tại Sintech, voucher đậm."},
    56:  {"meta_col":"I","meta":"Chuột gaming AULA SC560 3 mode hồng cute, không dây nhỏ gọn vừa tay, hợp setup nữ tính, dễ mang đi học. CHỌN NGAY tại Sintech để săn deal hôm nay."},
    58:  {"meta_col":"I","meta":"Chuột gaming AULA SC518 2 mode trong suốt trắng - kết nối 2.4G + Bluetooth ổn định, LED RGB nhiều chế độ rực rỡ. XEM NGAY tại Sintech để săn deal!"},
    59:  {"meta_col":"J","meta":"Chuột AULA SC518 2 mode trong suốt đen - tone tối ngầu cá tính, công thái học, sạc Type-C tiện gọn. THAM KHẢO NGAY tại Sintech, voucher đậm."},
    62:  {"meta_col":"I","meta":"Chuột gaming AULA S12 PRO có dây đen, DPI 12800, LED RGB, 8 nút lập trình tiện, polling 1000Hz mượt. KHÁM PHÁ NGAY tại Sintech để săn deal hôm nay."},
    63:  {"meta_col":"K","meta":"Setup gaming chất lừ cùng chuột AULA S12 PRO có dây trắng xám, DPI cao 12800, 8 nút lập trình, hợp ngân sách học sinh. CHỌN NGAY tại Sintech!"},
    64:  {"meta_col":"J","meta":"Chuột AULA SC580X 3 mode đen - 6 mức DPI tùy chỉnh, sạc Type-C, nhẹ 81.9g flick nhanh cho gaming. THAM KHẢO NGAY tại Sintech để săn deal sớm!"},
    72:  {"meta_col":"I","meta":"Chuột không dây E-DRA EM605W đen, công thái học êm tay cả ngày, 3 mức DPI tiện, hợp văn phòng và học online. CHỌN NGAY tại Sintech, BH chính hãng."},
    103: {"meta_col":"K","meta":"Build PC mát rượi cùng fan Magic Snowman F-129 Xuôi ARGB - đèn rực rỡ sống động, êm chỉ 18.71 dBA. CHỌN NGAY tại Sintech để hoàn thiện setup."},
    104: {"meta_col":"K","meta":"Hoàn thiện build PC kính cùng fan Magic Snowman F-129 Reverse ARGB, đèn rực rỡ, êm gọn 18.71 dBA. KHÁM PHÁ NGAY tại Sintech, voucher hấp dẫn."},
    114: {"meta_col":"K","meta":"Nâng cấp PC dual channel cùng kit RAM ADATA XPG D10 16GB 2x8 Bus 3200MHz, hiệu năng cao đa nhiệm. CHỌN NGAY tại Sintech để săn ưu đãi đậm hôm nay."},
    124: {"meta_col":"K","meta":"Săn deal laptop văn phòng cùng HP 14s-dq5122TU i3 gen 12, RAM 8GB, SSD 256GB tốc độ tốt cho học online. CHỌN NGAY tại Sintech để nhận voucher!"},
    144: {"meta_col":"I","meta":"Mainboard Colorful H510M-K M.2 V20 DDR4, chipset H510, hỗ trợ Intel gen 10/11, hợp build văn phòng và gaming basic. KHÁM PHÁ NGAY tại Sintech."},
    145: {"meta_col":"K","meta":"Build PC văn phòng/gaming cơ bản cùng mainboard Colorful H510M-K M.2 V20 DDR4, ổn định, dễ lắp đặt cho người mới. CHỌN NGAY tại Sintech để được tư vấn!"},
    152: {"meta_col":"I","meta":"Màn hình gaming LG 24GS60F-B 24 inch IPS Full HD 180Hz 1ms, viền siêu mỏng, hợp setup gaming + văn phòng đa năng. KHÁM PHÁ NGAY tại Sintech!"},
    156: {"meta_col":"I","meta":"Nguồn máy tính DarkFlash PMT 750W GOLD trắng - ATX 3.1, PCIe 5.1, full modular, tụ Nhật cao cấp, BH 5 năm. KHÁM PHÁ NGAY tại Sintech để săn deal."},
    157: {"meta_col":"I","meta":"Nguồn máy tính DarkFlash PMT 750W GOLD ATX 3.1 - PCIe 5.1 đầy đủ, 80 Plus Gold tiết kiệm điện, full modular, tụ Nhật, BH 5 năm. THAM KHẢO NGAY tại Sintech."},
    158: {"meta_col":"I","meta":"Nguồn máy tính DarkFlash PMT 850W GOLD đen ATX 3.1 PCIe 5.1, full modular, tụ Nhật cao cấp, BH 5 năm an tâm. KHÁM PHÁ NGAY tại Sintech, BH chính hãng!"},
    159: {"meta_col":"K","meta":"Build PC gaming tone trắng cao cấp cùng nguồn DarkFlash PMT 850W GOLD ATX 3.1, PCIe 5.1 đầy đủ, BH 5 năm. CHỌN NGAY tại Sintech để săn deal."},
    200: {"meta_col":"I","meta":"Bàn phím cơ AULA F108 Pro Nimbus switch xám đen gradient mượt mà, 108 phím, 3 mode, Gasket mount êm tay. CHỌN NGAY tại Sintech để săn deal hôm nay!"},
    201: {"meta_col":"I","meta":"Bàn phím cơ AULA F108 Pro Reaper switch (đen xám vàng), 104 phím, 3 mode, núm xoay tiện, màn LCD 1.14 độc đáo. KHÁM PHÁ NGAY tại Sintech, deal có hạn!"},
    203: {"meta_col":"I","meta":"Bàn phím cơ Darmoshark TOP 98 Tri-mode RGB trắng, layout 98% gọn, Silver switch nhanh, 3 mode kết nối linh hoạt. CHỌN NGAY tại Sintech để săn deal hời!"},
    212: {"meta_col":"I","meta":"RAM ADATA XPG Spectrix D41 RGB 16GB DDR4 3200MHz xám, đèn RGB rực rỡ điểm tô setup, hỗ trợ Intel/AMD đa nền tảng. KHÁM PHÁ NGAY tại Sintech!"},
    213: {"meta_col":"J","meta":"RAM ADATA D50 RGB 16GB DDR4 3200MHz - PCB chất lượng, hỗ trợ Intel/AMD mới, hợp build PC gaming RGB. THAM KHẢO NGAY tại Sintech, voucher đậm."},
    235: {"meta_col":"I","meta":"RAM ADATA D50 RGB 16GB DDR4 3200MHz trắng - hợp setup tone trắng tinh khôi, PCB chất lượng, hỗ trợ Intel/AMD mới. THAM KHẢO NGAY tại Sintech!"},
    236: {"meta_col":"I","meta":"Build PC RGB tầm trung cùng RAM ADATA XPG Spectrix D41 8GB DDR4 3200MHz - đẹp + ổn định cho gamer. CHỌN NGAY tại Sintech để săn voucher đậm!"},
    243: {"meta_col":"I","meta":"RAM ADATA XPG GAMMIX D10 16GB DDR4 3200MHz - lựa chọn nâng cấp đáng tiền cho dàn PC tầm trung mượt mà. THAM KHẢO NGAY tại Sintech, deal hời."},
    253: {"meta_col":"I","meta":"Tai nghe gaming có dây E-DRA EH416PRO đen - củ loa lớn 50mm âm thanh sống động, mic đa hướng rõ, kết nối USB tiện. KHÁM PHÁ NGAY tại Sintech!"},
    254: {"meta_col":"K","meta":"Setup gaming nữ tính cùng tai nghe E-DRA EH416PRO hồng - củ loa lớn 50mm, mic rõ ràng, hợp gu Gen Z. CHỌN NGAY tại Sintech để săn ưu đãi đậm."},
    259: {"meta_col":"I","meta":"Tai nghe In-Ear Bamba B48 cổng jack 3.5 phổ thông, màng loa 13mm cho âm sống động, có mic + bộ điều khiển. XEM NGAY tại Sintech để săn deal!"},
    263: {"meta_col":"I","meta":"Tản nước AIO MSI MAG CORELIQUID 360R V2 - rad 360mm tản đỉnh, fan ARGB rực rỡ, lắp đặt dễ cho dàn PC gaming cao cấp. XEM NGAY tại Sintech để săn deal đậm!"},
    275: {"meta_col":"I","meta":"Tản nhiệt khí Deepcool AG500 Digital ARGB đen - thiết kế tower compact, ARGB sống động, hợp build PC tầm trung. KHÁM PHÁ NGAY tại Sintech, deal có hạn!"},
    299: {"meta_col":"I","meta":"Tản nước AIO Thermaltake LA240-S ARGB Sync - rad 240mm, fan ARGB Digital rực rỡ, làm mát CPU mượt cho PC gaming tầm trung. CHỌN NGAY tại Sintech!"},
    300: {"meta_col":"I","meta":"Tản nước AIO Thermaltake MAGFloe 360 Ultra ARGB - rad 360mm, màn TFT-LCD 3.95 inch tùy biến, hỗ trợ TDP 355W. KHÁM PHÁ NGAY tại Sintech, deal hời!"},
    316: {"meta_col":"I","meta":"Build PC tone trắng cao cấp cùng AIO Corsair H100i Elite RGB - rad 240mm, làm mát đỉnh cho CPU flagship, đèn RGB rực rỡ. CHỌN NGAY tại Sintech!"},
    328: {"meta_col":"I","meta":"Tay cầm gaming Machenike G5 Pro - kết nối có dây + 2.4G Wireless, RGB rực rỡ, pin 600mAh dùng lâu cho PC, Switch. KHÁM PHÁ NGAY tại Sintech!"},
    332: {
        "title_col":"F","title":"Vỏ Case 1STPLAYER RT7 đen ATX kính cường lực",
        "meta_col":"I","meta":"Case 1STPLAYER RT7 đen ATX - hợp build PC tone tối cao cấp, kính cường lực khoe linh kiện ngon. CHỌN NGAY tại Sintech, ưu đãi đậm tháng này!",
    },
    334: {"title_col":"F","title":"Vỏ Case Centaur Metal đen ATX khung kim loại"},
    364: {"meta_col":"I","meta":"Case MAGIC GM-02 Curved đen - kính cong nam tính độc đáo, compact tiết kiệm không gian, hỗ trợ 2 SSD + 1 HDD. THAM KHẢO NGAY tại Sintech, deal hời hôm nay!"},
    365: {"meta_col":"I","meta":"Case MAGIC GM-02 Curved trắng - kính cong cá tính tinh khôi, gọn nhẹ tiết kiệm không gian, hỗ trợ 2 SSD + 1 HDD. THAM KHẢO NGAY tại Sintech!"},
    459: {"meta_col":"I","meta":"Case Thermaltake View 270 TG V2 ARGB Snow - thẩm mỹ cao cấp tone trắng, ARGB sync rực rỡ, hợp build PC flagship. THAM KHẢO NGAY tại Sintech!"},
    480: {"meta_col":"I","meta":"Case Xigmatek Sky II 3F đen - thiết kế hiện đại nam tính, kèm 3 fan ngon trong tầm giá học sinh. KHÁM PHÁ NGAY tại Sintech để săn voucher đậm!"},
    481: {"meta_col":"I","meta":"Case Xigmatek Sky II 3F trắng - thiết kế hiện đại tinh tế, kèm 3 fan ngon ngay trong tầm giá học sinh. KHÁM PHÁ NGAY tại Sintech, deal hời tháng này!"},
}

# 1. Validate length theo rule
print("=== VALIDATE ===")
problems = 0
for row, fix in FIXES.items():
    if "title" in fix:
        ln = len(fix["title"])
        ok = 30 <= ln <= 61
        flag = "✓" if ok else f"✗ ({ln}c)"
        print(f"  [{row}] T {flag}: {fix['title']}")
        if not ok: problems += 1
    if "meta" in fix:
        ln = len(fix["meta"])
        ok = 140 <= ln <= 160
        flag = "✓" if ok else f"✗ ({ln}c)"
        if not ok:
            print(f"  [{row}] M {flag}: {fix['meta']}")
            problems += 1
print(f"Problems: {problems}")
if problems > 0:
    print("⚠️  Có problems — abort")
    sys.exit(1)

if DRY_RUN:
    print("DRY RUN done")
    sys.exit(0)

# 2. Apply value updates
updates = []
for row, fix in FIXES.items():
    if "title" in fix:
        updates.append({"range": f"'{TAB}'!{fix['title_col']}{row}", "values":[[fix["title"]]]})
    if "meta" in fix:
        updates.append({"range": f"'{TAB}'!{fix['meta_col']}{row}",  "values":[[fix["meta"]]]})

svc.spreadsheets().values().batchUpdate(
    spreadsheetId=SHEET_ID,
    body={"valueInputOption":"USER_ENTERED","data":updates},
).execute()
print(f"\n✅ Updated {len(updates)} cells")

# 3. Highlight full row A:O với màu xanh nhạt cho 45 row
GREEN = {"red": 0.78, "green": 0.92, "blue": 0.78}  # light green
fixed_rows = sorted(FIXES.keys())
fmt_requests = []
for row in fixed_rows:
    fmt_requests.append({
        "repeatCell": {
            "range": {
                "sheetId": TAB_GID,
                "startRowIndex": row - 1,
                "endRowIndex": row,
                "startColumnIndex": 0,
                "endColumnIndex": 15,  # A:O
            },
            "cell": {"userEnteredFormat": {"backgroundColor": GREEN}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

svc.spreadsheets().batchUpdate(
    spreadsheetId=SHEET_ID,
    body={"requests": fmt_requests},
).execute()
print(f"✅ Tô xanh {len(fmt_requests)} row")

# Summary
synced_in_fix = []
res = svc.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1:O", majorDimension="ROWS").execute()
all_rows = res.get("values", [])[1:]
for row in fixed_rows:
    r = all_rows[row - 2]
    if (r[12] if len(r) > 12 else "") == "TRUE":
        synced_in_fix.append(row)
print(f"\n--- TỔNG ---")
print(f"Tổng fix: {len(fixed_rows)}")
print(f"Trong đó đã sync (cần re-sync sau): {len(synced_in_fix)}")
print(f"Synced rows: {synced_in_fix}")
