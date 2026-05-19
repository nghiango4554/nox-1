"""Chuẩn hóa case cho title trong tab '2. URL Rewrite':
- Chỉ viết hoa: chữ cái đầu câu + tên riêng (brand) + acronym kỹ thuật + model code
- Còn lại: viết thường
- BỎ QUA URL đã sync (M=TRUE) — không đụng
- BỎ QUA URL chưa có title (Status != 'Đã sinh')
"""
import os, sys, re
sys.stdout.reconfigure(encoding="utf-8")

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

WS = r"C:\Users\NGHIANGO\.openclaw\workspace"
TOKEN = os.path.join(WS, ".secrets", "google_token.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "2. URL Rewrite"

# Brand viết ALL UPPER (tên thương hiệu thường write all-caps)
BRANDS_UPPER = {
    "AULA","ASUS","MSI","HP","AMD","NVIDIA","AOC","AIWA","KTC","VSP","HKC",
    "EDRA","E-DRA","ROG","TUF","ASROCK","NZXT","EVGA","XPG","ADATA","MAGIC",
    "JONSBO","PANTUM","ECS","KFA2","ELSA","MERCUSYS","ID-COOLING","GAMDIAS",
    "PNY","GSKILL","G.SKILL","HKC","TRM","BAMBA","ZADAK","BIOSTAR","TPLINK","TP-LINK",
}
# Brand viết Title Case (giữ HOA chữ đầu)
BRANDS_TITLE = {
    "Apacer","Gigabyte","Colorful","Zotac","Intel","Logitech","Razer","Kingston",
    "Samsung","Seagate","Corsair","Deepcool","Thermalright","Thermaltake","Ocypus",
    "Segotep","Montech","Thonet","Vander","Lenovo","Dell","Acer","Apple","Microsoft",
    "Alienware","Sapphire","PowerColor","Manli","Palit","Gainward","Inno3D","Fujitsu",
    "Philips","Viewsonic","BenQ","Xiaomi","Rapoo","Redragon","HyperX","SteelSeries",
    "Havit","Sades","Bloody","Cherry","Ducky","Keychron","Akko","Glorious","Phanteks",
    "Fractal","SilverStone","Seasonic","Patriot","SanDisk","Transcend","Lexar","Sony",
    "Toshiba","Realtek","SuperFlower","CoolerMaster","WD","LG",
}
BRANDS = BRANDS_UPPER  # legacy alias

ACRONYMS = {
    "RGB","ARGB","AIO","RTX","GTX","RX","GDDR","DDR","DDR4","DDR5","DDR6",
    "GDDR6","GDDR6X","GDDR7","FHD","QHD","UHD","HDR","HDMI","DP","VGA","USB",
    "SSD","HDD","NVMe","NVME","PCIe","PCI-E","PWM","VESA","IPS","VA","TN","OLED",
    "LED","LCD","TFT","CPU","GPU","RAM","ROM","BIOS","SATA","MPRT","OS","PC",
    "ATX","mATX","ITX","SFX","EATX","FPS","AAA","BT","OC","EVO","PRO","MAX","ULTRA",
    "GEN","MOD","TDP","RPM","CFM","LGA","AM4","AM5","sRGB","NTSC","GHz","MHz","Hz",
    "TGP","TBP","SLI","CF","XMP","EXPO","TPM","HDR10","VRR","FREESYNC","HBM",
    "II","III","IV","V","VI","VII","VIII","IX","X","XI","XII","I/O","ECC","VR","AR",
    "AI","ML","DL","NPU","APU","SOC","BGA","PGA","UEFI","M.2","M2","DLSS","FSR","GAMING",
    "SUPER","WIFI","WI-FI","BLUETOOTH","TYPE-C","TYPE-A","V2","V3","V4","V5","KB","MB",
    "GB","TB","PB","KHz","TFTLCD","FREE","SYNC","HBM2","HBM3","ARGB","DLDSR",
}

# Lookup maps
BRAND_UPPER_LU = {b.upper() for b in BRANDS_UPPER}
BRAND_TITLE_LU = {b.upper(): b for b in BRANDS_TITLE}  # upper → title-case form
ACRONYM_LU = {a.upper() for a in ACRONYMS}

VN_DIACRITICS = "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
VN_CHARS = set(VN_DIACRITICS + VN_DIACRITICS.upper())

# Common Vietnamese words không có dấu (vẫn cần lowercase)
VN_PLAIN = {
    "cho","va","cua","tai","ve","co","la","khong","voi","trong","o","nay","do","len","xuong",
    "moi","do","dung","ban","cua","gia","re","la","cho","tao","hop","ly","san","bao","hanh",
}

def is_vn(word):
    return any(c in VN_CHARS for c in word) or word.lower() in VN_PLAIN

# Model code: chứa cả số và chữ
MODEL_RE = re.compile(r"^[A-Za-z][A-Za-z]*[\d][\w-]*$|^[A-Za-z]+-[\d][\w-]*$|^[\d]+[A-Za-z]+[\w-]*$|^[A-Z]+\d+[A-Za-z]*$|^[A-Z]+[\d]+[\w.-]*$")
# Number-with-unit: 360mm, 1080p, 144Hz, 8GB, 16:9, 27"
NUM_UNIT_RE = re.compile(r"^\d+[A-Za-z%/]+$|^\d+:\d+$|^\d+\.\d+[A-Za-z]+$|^\d+$")

# Common English words trong tech context cũng nên lowercase (tính từ phụ)
ENGLISH_LOWER = {"for","with","and","or","of","the","a","an","to","in","on","at"}


def fix_word(word, is_first):
    upper = word.upper()
    # Brand all-upper
    if upper in BRAND_UPPER_LU:
        return upper
    # Brand title-case
    if upper in BRAND_TITLE_LU:
        return BRAND_TITLE_LU[upper]
    # Acronym
    if upper in ACRONYM_LU:
        return upper
    # Number with unit (PHẢI check trước MODEL_RE để 420mm ko bị thành 420MM)
    if NUM_UNIT_RE.match(word):
        return word
    # Model code (e.g., G513IC, B860-A, RTX5050)
    if MODEL_RE.match(word):
        return word.upper()
    # Tiếng Việt → lowercase (capitalize nếu đầu câu)
    if is_vn(word):
        if is_first:
            return word[0].upper() + word[1:].lower() if word else word
        return word.lower()
    # English connector → lowercase
    if word.lower() in ENGLISH_LOWER:
        if is_first:
            return word[0].upper() + word[1:].lower()
        return word.lower()
    # English word khác (model line name như "Twin", "Edge", "Snow", "LightSync") → giữ Title Case
    if is_first or word[0].isupper():
        # Capitalize first letter, giữ rest of original case (preserve mixed case như LightSync, MAGFloe)
        return word[0].upper() + word[1:]
    return word.lower()


def fix_title(title):
    if not title.strip():
        return title
    # Tokenize giữ delimiters
    tokens = re.split(r"([\s\-/+()|,.:!?]+)", title.strip())
    out = []
    is_first = True
    for tok in tokens:
        if not tok:
            continue
        if re.match(r"^[\s\-/+()|,.:!?]+$", tok):
            out.append(tok)
            # Reset is_first sau dấu chấm/!?
            if any(c in tok for c in ".!?"):
                is_first = True
            continue
        out.append(fix_word(tok, is_first))
        is_first = False
    return "".join(out)


# Test với vài title trước
test = [
    "Tản Nước AIO Ocypus Delta L24 ARGB V2 Trắng",
    "AIO Thermaltake MAGFloe 420 Ultra ARGB Rad 420mm",
    "Bàn Phím Cơ AULA F75 MAX Xám Đen Gradient Reaper",
    "Card Màn Hình Zotac RTX 4070 Super Twin Edge OC 12G",
    "Chuột Logitech G102 LightSync Gen 2 Trắng Quốc Dân",
    "Loa Bluetooth Thonet Vander DUETT TM Đức Chính Hãng",
]
print("=== TEST ===")
for t in test:
    print(f"  IN : {t}")
    print(f"  OUT: {fix_title(t)}")
    print()

if "--apply" not in sys.argv:
    print("\nDùng `python fix_title_case.py --apply` để áp dụng vào sheet")
    sys.exit(0)

# Áp dụng vào sheet
print("\n=== APPLY TO SHEET ===")
creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds)

res = svc.spreadsheets().values().get(
    spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1:O", majorDimension="ROWS",
).execute()
rows = res.get("values", [])
header = rows[0]
data_rows = rows[1:]

def cell(r, idx):
    return r[idx] if idx < len(r) else ""

updates = []
fixed_cnt = 0
skipped_synced = 0
skipped_no_data = 0
for i, r in enumerate(data_rows, start=2):
    da_apply = cell(r, 12)  # cột M
    status = cell(r, 11)    # cột L
    if da_apply == "TRUE":
        skipped_synced += 1
        continue
    if status != "Đã sinh":
        skipped_no_data += 1
        continue
    # Fix 3 title (cột F, G, H — idx 5, 6, 7)
    new_titles = []
    changed = False
    for col_idx in (5, 6, 7):
        old = cell(r, col_idx)
        new = fix_title(old)
        new_titles.append(new)
        if new != old:
            changed = True
    if changed:
        updates.append({
            "range": f"'{TAB}'!F{i}:H{i}",
            "values": [new_titles],
        })
        fixed_cnt += 1

print(f"  Đã sync, bỏ qua: {skipped_synced}")
print(f"  Không có data, bỏ qua: {skipped_no_data}")
print(f"  Cần fix: {fixed_cnt} URL")

if updates:
    body = {"valueInputOption": "RAW", "data": updates}
    res = svc.spreadsheets().values().batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
    print(f"  ✓ Updated {res.get('totalUpdatedRows')} rows / {res.get('totalUpdatedCells')} cells")
