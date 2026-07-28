"""B3 — viet 2 bai tru cot thay cho traffic crack da mat.

Boi canh: 224 bai "cai dat phan mem crack" da bi go + 301 (xem fix_redirects.py).
Traffic crack (~1.228 click/90 ngay) la traffic KHONG RA DON va keo ca site xuong.
=> Chuyen sang cum CO TIEN, nhu cau that (Google Autocomplete + GSC):
   1. "cau hinh chay autocad 2025/2026"  -> ban PC do hoa
   2. "cai win ban quyen bao nhieu tien / o dau" -> ban key + dich vu

Luat (SINTECH_CONTENT_RULES): khong H1 · khong nhac gia cu the · 3-6 internal link (deu 200)
· co FAQ (H2 "Cau hoi thuong gap" + H3 cau hoi -> theme tu sinh FAQPage schema)
· format BLOG: H2 17pt #e74c3c, H3 13pt, p Arial 12pt · xung "ban" · khong tu cam.

Chay:  py -3.12 _scripts/b3_write_posts.py --dual
"""
import argparse
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import ai_provider
import kw_suggest

LINKS = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\b3_internal_links.json")
PRODS = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\b3_product_links.json")
OUT = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\b3_posts")

POSTS = [
    {
        "key": "autocad",
        # Title ≤50 ky tu: theme Sintech TU THEM " – Sintech" (+10) -> 60+ la Google cat ngang
        # ⚠️ 2026 chu KHONG phai 2025: nay la thang 7/2026. GSC cho thay 2025 = 2 hien thi,
        # 2026 = 0, con 2021 = 4.535 (tu nhom bai crack da go). Bam 2025 = viet bai loi thoi ngay khi dang.
        # Da tra Autodesk: AutoCAD 2027 DA RA, 2026 la ban dang dung pho bien.
        "title": "Cấu hình AutoCAD 2026: chọn CPU, RAM, VGA chuẩn",
        "seeds": ["cấu hình chạy autocad", "cấu hình autocad 2026", "pc chạy autocad"],
        "intent": ("Người dùng AutoCAD (kiến trúc, xây dựng, cơ khí) muốn biết máy cần cấu hình gì "
                   "để chạy mượt, nên nâng cấp gì, và mua PC ở đâu. Ý định MUA rõ."),
        "angle": ("AutoCAD 2D ăn XUNG NHỊP CPU (đơn nhân) hơn là nhiều nhân; 3D/render mới cần VGA và nhiều nhân. "
                  "Rất nhiều người mua sai: dồn tiền vào VGA khủng trong khi bản vẽ 2D vẫn giật."),
        # ⚠️ Ban truoc TU MAU THUAN: than bai bao 2D khong can VGA manh, nhung bang lai goi y
        # PC Gaming co RTX 4060 cho dong "AutoCAD 2D". Bang PHAI khop luan diem cua bai.
        "extra": ("⚠️ PHIÊN BẢN: viết cho AutoCAD 2026 (bản đang dùng phổ biến, hôm nay là tháng 7/2026). "
                  "Nhắc được: AutoCAD 2027 đã ra và yêu cầu Windows 11; AutoCAD 2026 chạy trên Windows 10/11 "
                  "64-bit. Bài tham khảo được cho các bản lân cận (2024, 2025).\n"
                  "⚠️ KHÔNG trích 'thông số tối thiểu/đề nghị theo Autodesk' kèm con số cụ thể "
                  "(RAM bao nhiêu GB, CPU bao nhiêu GHz, VRAM bao nhiêu) — không xác minh được nguồn chính thức. "
                  "Nói theo NGUYÊN TẮC CHỌN MÁY và mức định tính (RAM đủ rộng, SSD NVMe, CPU xung cao...).\n"
                  "⚠️ BẢNG CHỌN MÁY PHẢI KHỚP LUẬN ĐIỂM CỦA BÀI, không được tự mâu thuẫn:\n"
                  "- Dòng 'AutoCAD 2D thuần': gợi ý máy CPU mạnh, KHÔNG cần VGA rời mạnh.\n"
                  "- Dòng '2D nặng / 3D nhẹ / dựng hình': mới gợi ý máy có VGA rời.\n"
                  "- Dòng '3D, render, đa nhiệm nặng': máy cấu hình cao nhất.\n"
                  "Thêm 1 câu đầu bài: yêu cầu thực tế còn tuỳ độ nặng file và phần mềm dùng kèm."),
        "links": ["/collections/pc-do-hoa", "/collections/cpu", "/collections/vga",
                  "/pages/xay-dung-cau-hinh", "/blogs/huong-dan/build-pc-do-hoa",
                  "/collections/man-hinh-do-hoa"],
    },
    {
        "key": "winbanquyen",
        # KHONG hua "gia bao nhieu" trong title: rule Sintech CAM neu gia trong bai (gia doi lien tuc,
        # khong co co che cap nhat) -> hua ma khong tra loi = khach that vong, tang thoat trang.
        "title": "Windows bản quyền: OEM, Retail và khác gì bản crack",
        "seeds": ["cài win bản quyền", "key windows 11", "win 11 bản quyền"],
        "intent": ("Người dùng muốn biết cài Windows bản quyền tốn bao nhiêu, mua key ở đâu, "
                   "có đáng so với dùng crack không, và có được hỗ trợ cài không. Ý định MUA rõ."),
        "angle": ("Khác biệt thật giữa bản quyền và crack không nằm ở 'chạy được hay không' mà ở: "
                  "cập nhật bảo mật, tính ổn định khi làm việc, rủi ro mất dữ liệu, và bản quyền theo máy "
                  "(OEM) vs theo người (Retail) — chỗ này người mua hay bị nhầm."),
        "extra": ("⚠️ GIÁ: KHÔNG viết con số. Thay vào đó có 1 mục trả lời 'giá phụ thuộc vào cái gì' "
                  "(Home hay Pro · OEM hay Retail · có kèm phí cài đặt không) và dẫn khách vào trang sản phẩm "
                  "để xem giá thật, luôn cập nhật.\n"
                  "⚠️ BẢNG CHÍNH chỉ nói về WINDOWS (Home vs Pro, OEM vs Retail, dịch vụ cài). "
                  "KHÔNG nhét Office, Kaspersky, Windows Server vào bảng chính — người đọc đang hỏi cài Win. "
                  "Office/Kaspersky để riêng một mục 'nên cài thêm gì sau khi có Windows'.\n"
                  "⚠️ KHÔNG nói chắc 'bản crack bị chặn cập nhật'. Viết đúng mức: công cụ kích hoạt không chính "
                  "thức có thể can thiệp dịch vụ hệ thống, chính sách bảo mật hoặc cơ chế cập nhật; một số bản "
                  "vẫn cập nhật được nhưng không có bảo đảm về tính toàn vẹn và hỗ trợ.\n"
                  "⚠️ Retail: nói đúng — giấy phép Retail thường chuyển được sang máy khác theo điều khoản, "
                  "chỉ kích hoạt trên một máy tại một thời điểm; liên kết tài khoản Microsoft giúp quản lý kích "
                  "hoạt chứ không thay thế điều khoản giấy phép.\n"
                  "⚠️ Mất dữ liệu: nói có điều kiện — chỉ nhập key kích hoạt thì KHÔNG mất dữ liệu; chỉ khi cài "
                  "lại sạch và format phân vùng hệ điều hành mới mất, nên phải sao lưu trước."),
        "links": ["/collections/cai-dat-windows-phan-mem", "/collections/phan-mem-ban-quyen",
                  "/blogs/huong-dan/office-2021-ban-quyen-khac-gi-office-crack-khi-dung-cho-cong-viec-hang-ngay"],
    },
]

H2 = ('font-size: 17pt; font-weight: 700; color: rgb(231, 76, 60); margin: 24px 0px 5px; '
      'line-height: 1.38; font-family: Arial, sans-serif;')
H3 = ('font-size: 13pt; font-weight: 700; color: rgb(0, 0, 0); margin: 18px 0px 4px; '
      'line-height: 1.4; font-family: Arial, sans-serif;')
P = ('font-family: Arial, sans-serif; font-size: 12pt; font-weight: 500; line-height: 1.65; '
     'margin: 10px 0px; color: rgb(0, 0, 0);')
TB = ('border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; font-size: 12pt; '
      'border: 2px solid #555; margin: 14px 0px;')
TH = 'border: 1px solid #999; background: #f4f4f4; padding: 8px; font-weight: 700; text-align: left;'
TD = 'border: 1px solid #999; padding: 8px;'

SYSTEM = f"""Bạn viết bài blog cho Sintech — cửa hàng linh kiện & PC tại TP.HCM (457 Trần Xuân Soạn, Phường Tân Hưng, Thành phố Hồ Chí Minh).

MỤC TIÊU: thay thế nhóm bài "hướng dẫn cài phần mềm crack" vừa bị gỡ. Bài mới phải phục vụ
người CÓ Ý ĐỊNH MUA, không phải người tìm phần mềm lậu.

LUẬT CỨNG:
- KHÔNG hướng dẫn tải/crack/bẻ khóa phần mềm. Không đưa link tải lậu. Nếu nhắc tới crack thì chỉ để
  nói rủi ro thật (mất cập nhật bảo mật, lỗi khi làm việc, rủi ro dữ liệu) — không phán xét đạo đức.
- KHÔNG nêu giá tiền cụ thể (giá đổi liên tục). Được nói "tầm giá phổ thông / trung cấp / cao cấp".
- KHÔNG bịa thông số. Không chắc thì nói định tính.
- Xưng "bạn". Không dùng từ: research, SERP, đối thủ, tại đây.
- KHÔNG H1. Không in đậm trong thân bài. Không dấu ';'. Không '---'.
- Heading ≤60 ký tự, không heading nào trùng nhau.

CẤU TRÚC (HTML thuần, dùng inline style ĐÚNG như đưa bên dưới):
- Mở bài 2-3 câu: nêu tình huống thật người đọc đang gặp. Có 1 internal link tự nhiên.
- 4-6 mục H2 theo chủ đề (bám cụm người thật gõ được cung cấp).
- ÍT NHẤT 1 bảng (so sánh/định hướng chọn) — có câu dẫn trước bảng.
- Mục H2 "Câu hỏi thường gặp" ở cuối: 4-5 câu hỏi, mỗi câu là H3, trả lời 2-3 câu ngay dưới.
  (Câu trả lời phải tự đứng độc lập — sẽ được trích ra làm dữ liệu có cấu trúc.)
- Kết bài không heading, mở bằng "Tóm lại," — có 1 internal link.
- Dùng 5-6 internal link, LẤY TỪ DANH SÁCH ĐƯỢC CUNG CẤP, anchor mô tả rõ (không "tại đây").
- ⚠️ BẮT BUỘC ít nhất 2 link tới SẢN PHẨM cụ thể (/products/...), không chỉ link danh mục.
- ⚠️ LINK SẢN PHẨM PHẢI NẰM TRONG BẢNG hoặc DANH SÁCH BULLET — người đọc quét mắt bảng/bullet,
  link chôn trong đoạn văn dài sẽ bị bỏ qua. Cách làm:
  · BẢNG "chọn máy theo nhu cầu": cột nhu cầu | cột cấu hình cần | cột MÁY GỢI Ý (chứa <a> tới sản phẩm)
  · hoặc <ul> gợi ý gói: mỗi <li> một lựa chọn, tên sản phẩm là link, kèm 1 câu vì sao hợp.
- KHÔNG lặp lại cùng một link 2 lần trong bài.

STYLE BẮT BUỘC (chép nguyên):
h2: style="{H2}"
h3: style="{H3}"
p:  style="{P}"
table: style="{TB}" | th: style="{TH}" | td: style="{TD}"
a: style="color: rgb(231, 76, 60); text-decoration: underline; font-weight: 700;"

Trả về DUY NHẤT 1 JSON object, không bọc markdown:
{{"title": "...", "meta": "<140-160 ký tự, có CTA>", "body_html": "<HTML thuần, bắt đầu bằng <p>>"}}"""


def gen(post, links_txt, provider=None):
    hints = []
    for s in post["seeds"]:
        try:
            hints += kw_suggest.suggest(s)
        except Exception:
            pass
    hints = list(dict.fromkeys(hints))[:14]

    msg = f"""BÀI CẦN VIẾT: {post['title']}

Ý ĐỊNH NGƯỜI TÌM: {post['intent']}

GÓC BÀI (phải bám, đây là thứ làm bài khác biệt):
{post['angle']}

YÊU CẦU RIÊNG CỦA BÀI NÀY (bắt buộc):
{post.get('extra', '(không có)')}

CỤM NGƯỜI THẬT GÕ GOOGLE (đặt heading bám các cụm này, diễn đạt tự nhiên):
{chr(10).join('- ' + h for h in hints)}

INTERNAL LINK ĐƯỢC PHÉP DÙNG (đã kiểm tra đều sống, dùng 3-6 cái):
{links_txt}

Viết bài. JSON thuần."""
    raw = (ai_provider.call_ai_single(provider, SYSTEM, msg, timeout=300) if provider
           else ai_provider.call_ai(SYSTEM, msg, timeout=300))
    raw = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError(f"AI không trả JSON: {raw[:120]}")
    return json.loads(m.group(0))


def qc(d, allowed):
    """Kiem luat truoc khi dua vo duyet — bao het loi, khong im lang."""
    b = d.get("body_html", "")
    errs = []
    if "<h1" in b.lower():
        errs.append("có H1 (cấm)")
    for w in ("crack ", "tải crack", "bẻ khóa", "google drive", "fshare"):
        if re.search(r"link\s+" + re.escape(w), b, re.I):
            errs.append(f"có vẻ dẫn link tải lậu ({w})")
    # ⚠️ Regex cu bat nham "Quận 7 để..." thanh "7 đ" -> bao gia gia. Phai co ranh gioi tu.
    if re.search(r"\d[\d.,]*\s?(?:đồng|vnđ|vnd|triệu\b|tr\b|k\b|₫)", b, re.I):
        errs.append("nhắc giá cụ thể (cấm)")
    all_used = re.findall(r'href="(/[^"]+)"', b)
    used = set(all_used)
    bad = [u for u in used if u not in allowed]
    if bad:
        errs.append(f"link không nằm trong danh sách cho phép: {bad[:3]}")
    if len(all_used) != len(used):
        errs.append("có link bị lặp 2 lần")
    if not (4 <= len(used) <= 7):
        errs.append(f"có {len(used)} internal link (cần 5-6)")
    n_prod = len([u for u in used if u.startswith("/products/")])
    if n_prod < 2:
        errs.append(f"chỉ {n_prod} link SẢN PHẨM (cần ≥2 — khách phải có đường vào SP thật)")

    # Link SP phai nam trong BANG hoac BULLET (vo chot: nguoi doc quet mat bang/bullet,
    # link chon trong doan van bi bo qua)
    blocks = re.findall(r"<table.*?</table>|<ul.*?</ul>", b, re.S | re.I)
    in_block = {u for blk in blocks for u in re.findall(r'href="(/products/[^"]+)"', blk)}
    if len([u for u in used if u.startswith("/products/")]) and not in_block:
        errs.append("link SẢN PHẨM nằm trong đoạn văn — phải đặt trong BẢNG hoặc BULLET")
    if "Câu hỏi thường gặp" not in b:
        errs.append("thiếu mục Câu hỏi thường gặp")
    if len(re.findall(r"<h3", b, re.I)) < 4:
        errs.append("FAQ dưới 4 câu")
    if not re.search(r"Tóm lại,", b):
        errs.append("kết bài không mở bằng 'Tóm lại,'")
    if "<table" not in b:
        errs.append("thiếu bảng")
    ml = len(d.get("meta", ""))
    if not (130 <= ml <= 170):
        errs.append(f"meta {ml} ký tự (cần 140-160)")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dual", action="store_true")
    a = ap.parse_args()

    all_links = json.loads(LINKS.read_text(encoding="utf-8"))
    by_url = {x["url"].replace("https://sintech.vn", ""): x for x in all_links}
    prods = json.loads(PRODS.read_text(encoding="utf-8"))   # SP THAT lay tu API danh muc
    OUT.mkdir(parents=True, exist_ok=True)

    lock, res = threading.Lock(), []

    def work(job):
        i, post = job
        prov = ["codex", "claude"][i % 2] if a.dual else None
        cats = [u for u in post["links"] if u in by_url]
        pl = prods.get(post["key"], [])[:5]
        allowed = cats + [x["url"] for x in pl]
        links_txt = (
            "DANH MỤC / BÀI LIÊN QUAN:\n"
            + "\n".join(f"- {u} — {by_url[u]['title'][:52]}" for u in cats)
            + "\n\nSẢN PHẨM CỤ THỂ (BẮT BUỘC dùng ít nhất 2 cái):\n"
            + "\n".join(f"- {x['url']} — {x['title']}" for x in pl))
        try:
            d = gen(post, links_txt, provider=prov)
        except Exception as e:
            print(f"  LỖI {type(e).__name__}: {str(e)[:70]} — {post['key']}", flush=True)
            return
        errs = qc(d, set(allowed))
        with lock:
            res.append({**post, **d, "errors": errs, "provider": prov or "auto"})
        print(f"  [{post['key']}] {len(d.get('body_html',''))} ký tự · AI={prov}", flush=True)
        if errs:
            print(f"      ⚠ QC: {' | '.join(errs)}", flush=True)
        else:
            print("      ✔ QC sạch", flush=True)

    if a.dual:
        with ThreadPoolExecutor(max_workers=2) as ex:
            list(ex.map(work, enumerate(POSTS)))
    else:
        for j in enumerate(POSTS):
            work(j)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    jf = OUT / f"b3_posts_{stamp}.json"
    jf.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    pv = ['<meta charset="utf-8"><title>2 bài B3 — chờ duyệt</title>',
          '<body style="max-width:900px;margin:24px auto;font-family:Arial">',
          "<h1 style='color:#e74c3c'>2 bài trụ cột B3 — CHƯA đẩy</h1>"]
    for r in res:
        pv.append(f"<hr><p style='background:#f4f4f4;padding:10px'><b>TITLE:</b> {r['title']}<br>"
                  f"<b>META ({len(r['meta'])} ký tự):</b> {r['meta']}<br>"
                  f"<b>QC:</b> {'✔ sạch' if not r['errors'] else '⚠ ' + ' | '.join(r['errors'])}</p>")
        pv.append(r["body_html"])
    (OUT / f"b3_posts_{stamp}.html").write_text("\n".join(pv) + "</body>", encoding="utf-8")

    print(f"\n[XONG] {len(res)} bài")
    print(f"  JSON    : {jf}")
    print(f"  PREVIEW : {OUT / f'b3_posts_{stamp}.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
