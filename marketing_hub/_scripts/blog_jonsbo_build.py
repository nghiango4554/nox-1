"""Dung bai blog "Sam Jonsbo, sale bung no" theo dung khuon bai HSSV.

--thu   : chi sinh HTML ra file, KHONG dung toi Haravan
--tao   : tao bai o trang thai CHUA XUAT BAN (published=false) de vo duyet
--dang  : xuat ban bai da tao (can --id)
"""
import argparse
import base64
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import haravan_client as hc  # noqa: E402

OUT = Path(__file__).resolve().parent.parent.parent.parent / "nox-outputs"
BLOG_ID = 1000906526          # blog "news"
REF = "?ref=jonsbo-the-sp"
XANH = "#1b4fa0"              # xanh Jonsbo
XANH_NHAT = "#eaf1fb"
XAM = "#1f2a37"
LUC = "#157347"

TIEU_DE = "Sắm Jonsbo sale bùng nổ tại Sintech: tặng quà chính hãng 14/08 đến 14/09/2026"


def tien(n):
    return f"{n:,}".replace(",", ".") + "đ"


def the_sp(p):
    """Mot the san pham, dung khuon giong bai HSSV."""
    img = p["img"].replace(".webp", "_medium.webp") if "_medium" not in p["img"] else p["img"]
    return (
        f'<div style="display:inline-block;vertical-align:top;width:31%;min-width:168px;'
        f'margin:0 0.9% 12px;box-sizing:border-box;border:1px solid #e4e8ed;border-radius:8px;'
        f'padding:14px 10px;background:#ffffff;text-align:center;border-top:3px solid {XANH}">'
        f'<img alt="{p["title"]}" style="width:100%;height:auto;display:block;margin:0 auto 10px;'
        f'border-radius:6px" src="{img}">'
        f'<div style="font-family:Arial, Helvetica, sans-serif;font-size:10.5pt;font-weight:700;'
        f'color:{XAM};line-height:1.35;height:56px;overflow:hidden">{p["title"]}</div>'
        f'<div style="font-family:Arial, Helvetica, sans-serif;font-size:19pt;font-weight:700;'
        f'color:{XANH};background:{XANH_NHAT};border-radius:6px;padding:5px 4px;line-height:1.2">'
        f'{tien(p["price"])}</div>'
        f'<a style="display:inline-block;margin-top:12px;background:{LUC};color:#ffffff;'
        f'font-family:Arial, Helvetica, sans-serif;font-size:10pt;font-weight:700;'
        f'text-decoration:none;padding:8px 20px;border-radius:6px" '
        f'href="https://sintech.vn/products/{p["handle"]}{REF}">Xem sản phẩm</a></div>'
    )


def nut_xem_them(nhan, url):
    """Nut 'Xem them' cuoi moi nhom, tro toi trang tim kiem loc theo hang."""
    return (
        f'<div style="text-align:center;margin:6px 0 8px">'
        f'<a style="display:inline-block;background:#ffffff;color:{XANH};'
        f'font-family:Arial, Helvetica, sans-serif;font-size:11pt;font-weight:700;'
        f'text-decoration:none;padding:11px 30px;border:2px solid {XANH};border-radius:8px" '
        f'href="{url}">{nhan}</a></div>'
    )


def h2(txt):
    return (f'<h2 style="font-family:Arial, Helvetica, sans-serif;font-size:16pt;font-weight:700;'
            f'color:{XAM};border-left:5px solid {XANH};padding-left:12px;margin:34px 0 14px">{txt}</h2>')


def doan(txt):
    return (f'<p style="font-family:Arial, Helvetica, sans-serif;font-size:12pt;color:#3a434e;'
            f'line-height:1.7;margin:0 0 14px">{txt}</p>')


def muc_qua(so, dieu_kien, qua):
    return (
        f'<div style="display:inline-block;vertical-align:top;width:31%;min-width:180px;'
        f'margin:0 0.9% 12px;box-sizing:border-box;border:1px solid #cfdcef;border-radius:10px;'
        f'background:#ffffff;text-align:center;overflow:hidden">'
        f'<div style="background:{XANH};color:#ffffff;font-family:Arial, Helvetica, sans-serif;'
        f'font-size:20pt;font-weight:700;padding:10px 0">{so}</div>'
        f'<div style="padding:14px 12px 16px">'
        f'<div style="font-family:Arial, Helvetica, sans-serif;font-size:10.5pt;font-weight:700;'
        f'color:{XAM};line-height:1.4;min-height:52px">{dieu_kien}</div>'
        f'<div style="width:44px;height:3px;background:{XANH};border-radius:2px;margin:10px auto"></div>'
        f'<div style="font-family:Arial, Helvetica, sans-serif;font-size:11pt;font-weight:700;'
        f'color:{XANH};line-height:1.45">{qua}</div>'
        f'</div></div>'
    )


def dung_body(banner_url=""):
    sp = json.loads((OUT / "_jonsbo_sp.json").read_text(encoding="utf-8"))
    case = sorted([x for x in sp if x["loai"] == "case"], key=lambda z: z["price"])
    aio = sorted([x for x in sp if x["loai"] == "aio"], key=lambda z: z["price"])
    fan = sorted([x for x in sp if x["loai"] == "fan" and re.search(r"(240|360)", x["title"])],
                 key=lambda z: z["price"])

    h = []
    # --- hero
    h.append(
        f'<div style="text-align:center;margin:0 0 6px">'
        f'<div style="font-family:Arial, Helvetica, sans-serif;font-size:11pt;font-weight:700;'
        f'color:{XANH};letter-spacing:2px;margin-bottom:8px">SINTECH × JONSBO · 14/08 đến 14/09/2026</div>'
        f'<div style="font-family:Arial, Helvetica, sans-serif;font-size:27pt;font-weight:700;'
        f'color:{XANH};line-height:1.2;margin-bottom:10px">SẮM JONSBO, SALE BÙNG NỔ</div>'
        f'<div style="font-family:Arial, Helvetica, sans-serif;font-size:14pt;font-weight:700;'
        f'color:{XAM};line-height:1.45">Mua vỏ case, tản nhiệt AIO hay fan Jonsbo<br>'
        f'nhận quà chính hãng mang về</div>'
        f'<div style="width:90px;height:4px;background:{XANH};border-radius:3px;margin:16px auto 0">&nbsp;</div></div>'
    )
    if banner_url:
        # Anh banner vuong 1200x1200. Theme DA render anh dai dien o tren roi,
        # nen ban trong than bai chi de 480px cho do lap va do chiem cho.
        h.append(f'<p style="text-align:center;margin:20px 0"><img alt="Sắm Jonsbo sale bùng nổ tại Sintech" '
                 f'style="max-width:480px;width:100%;height:auto;display:block;margin:0 auto;'
                 f'border-radius:10px" src="{banner_url}"></p>')

    # --- chip
    def chip(nhan, gia_tri, mau):
        return (f'<div style="display:inline-block;border:2px solid {mau};border-radius:8px;'
                f'padding:11px 20px;margin:4px;background:#ffffff">'
                f'<div style="font-family:Arial, Helvetica, sans-serif;font-size:9.5pt;color:{mau};'
                f'font-weight:700">{nhan}</div>'
                f'<div style="font-family:Arial, Helvetica, sans-serif;font-size:13pt;font-weight:700;'
                f'color:{XAM}">{gia_tri}</div></div>')
    h.append('<div style="text-align:center;margin:16px 0 22px">'
             + chip("THỜI GIAN", "14/08 đến 14/09/2026", XANH)
             + chip("ĐIỀU KIỆN", "Fan và tản nhiệt từ 240mm", "#b4720a")
             + chip("ÁP DỤNG", "Trên một đơn hàng", "#c8202e")
             + '</div>')

    h.append(doan(
        "Jonsbo là hãng chuyên vỏ case và tản nhiệt được nhiều người chơi PC chọn nhờ thiết kế gọn "
        "và độ hoàn thiện tốt. Từ ngày 14/08 đến 14/09/2026, Sintech cùng Jonsbo triển khai chương "
        "trình tặng quà chính hãng cho khách mua vỏ case, tản nhiệt AIO và fan của hãng."))

    # --- 3 muc qua
    h.append(h2("Ba mức quà tặng"))
    h.append(doan("Mua càng nhiều món trong cùng một đơn hàng thì phần quà càng lớn."))
    h.append('<div style="text-align:center;margin:0 0 6px">'
             + muc_qua("01", "Mua vỏ case hoặc tản nhiệt AIO", "Tặng mũ bảo hiểm hoặc pad chuột Jonsbo")
             + muc_qua("02", "Mua vỏ case và tản nhiệt AIO", "Tặng quạt cầm tay hoặc áo chống nắng Jonsbo")
             + muc_qua("03", "Mua vỏ case, tản nhiệt AIO và fan", "Tặng mũ bảo hiểm và áo phông Jonsbo")
             + '</div>')

    # --- cac nhom SP
    nhom = [
        ("Vỏ case Jonsbo", case[:9],
         "Từ mini M-ATX gọn gàng cho góc bàn nhỏ tới mid tower ATX kính cong lắp được dàn tản nhiệt lớn.",
         "Xem tất cả vỏ case Jonsbo",
         "https://sintech.vn/search?q=case%20jonsbo&type=product"),
        ("Tản nhiệt nước AIO Jonsbo", aio,
         "Toàn bộ AIO Jonsbo tại Sintech đều là bản 240mm và 360mm, nằm trong nhóm được tính quà.",
         "Xem tất cả tản nhiệt nước Jonsbo",
         "https://sintech.vn/search?q=t%E1%BA%A3n%20n%C6%B0%E1%BB%9Bc%20jonsbo&type=product"),
        ("Fan case Jonsbo từ 240mm", fan,
         "Các bộ fan ARGB Infinity cỡ 240mm và 360mm, vừa đủ điều kiện nhận quà vừa hợp để đồng bộ màu với case.",
         "Xem tất cả fan Jonsbo",
         "https://sintech.vn/search?q=fan%20jonsbo&type=product"),
    ]
    for i, (ten, ds, mo_ta, nhan, url) in enumerate(nhom, 1):
        h.append(h2(f"{i}. {ten}"))
        h.append(doan(mo_ta))
        h.append('<div style="text-align:center;margin:0 0 6px">' + "".join(the_sp(p) for p in ds) + '</div>')
        h.append(nut_xem_them(nhan, url))

    # --- dieu kien
    h.append(h2("Điều kiện áp dụng"))
    for d in [
        "Chỉ áp dụng cho sản phẩm fan và tản nhiệt có kích thước từ 240mm trở lên.",
        "Chỉ tính trên một đơn hàng, không cộng dồn nhiều đơn hàng lại với nhau.",
        "Không áp dụng đồng thời với các chương trình khuyến mãi khác.",
        "Chương trình áp dụng từ ngày 14/08 đến hết ngày 14/09/2026.",
    ]:
        h.append(f'<p style="font-family:Arial, Helvetica, sans-serif;font-size:12pt;color:#3a434e;'
                 f'line-height:1.7;margin:0 0 10px;padding-left:18px;border-left:3px solid #e4e8ed">{d}</p>')

    # --- FAQ
    h.append(h2("Câu hỏi thường gặp"))
    faq = [
        ("Mua fan 120mm có được tặng quà không?",
         "Không. Chương trình chỉ tính cho fan và tản nhiệt từ 240mm trở lên."),
        ("Mua hai đơn riêng, một đơn case một đơn tản nhiệt, có được tính mức 02 không?",
         "Không. Chương trình chỉ tính trên một đơn hàng, không cộng dồn nhiều đơn."),
        ("Có được chọn quà không?",
         "Ở mức 01 và 02 khách được chọn một trong hai món ghi trên chương trình. Mức 03 nhận cả hai món."),
        ("Đang có khuyến mãi khác thì áp dụng chung được không?",
         "Không. Chương trình không áp dụng đồng thời với các khuyến mãi khác."),
    ]
    for q, a in faq:
        h.append(f'<div style="border:1px solid #e4e8ed;border-radius:8px;padding:14px 16px;margin:0 0 10px;'
                 f'background:#fafbfc"><div style="font-family:Arial, Helvetica, sans-serif;font-size:11.5pt;'
                 f'font-weight:700;color:{XAM};margin-bottom:6px">{q}</div>'
                 f'<div style="font-family:Arial, Helvetica, sans-serif;font-size:11.5pt;color:#3a434e;'
                 f'line-height:1.6">{a}</div></div>')

    # --- footer
    h.append(h2("Mua Jonsbo tại Sintech"))
    h.append(doan(
        "Sintech tư vấn chọn case và tản nhiệt theo đúng bo mạch, card và không gian bàn của khách, "
        "lắp ráp và đi dây tại chỗ. Cần chọn nhanh thì gọi hoặc nhắn tin, đội tư vấn trực từ 08:00 đến 21:00."))
    h.append(f'<div style="text-align:center;margin:22px 0 6px">'
             f'<div style="display:inline-block;border:2px solid {XANH};border-radius:10px;padding:16px 26px;'
             f'background:{XANH_NHAT}">'
             f'<div style="font-family:Arial, Helvetica, sans-serif;font-size:13pt;font-weight:700;color:{XAM}">'
             f'Hotline 0911 713 000</div>'
             f'<div style="font-family:Arial, Helvetica, sans-serif;font-size:11pt;color:#3a434e;margin-top:5px">'
             f'457 Trần Xuân Soạn, Phường Tân Hưng, Thành phố Hồ Chí Minh</div></div></div>')

    return "".join(h), len(case[:9]) + len(aio) + len(fan)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--thu", action="store_true")
    g.add_argument("--tao", action="store_true")
    a = ap.parse_args()

    body, so_sp = dung_body()
    print(f"Body: {len(body):,} ky tu · {so_sp} the san pham")
    kt = {
        "gach ngang dai": body.count("—") + body.count("–"),
        "dia chi dung mau": "457 Trần Xuân Soạn, Phường Tân Hưng, Thành phố Hồ Chí Minh" in body,
        "hotline": "0911 713 000" in body,
        "the <style>": body.count("<style"),
        "the <script>": body.count("<script"),
    }
    for k, v in kt.items():
        print(f"  {k:<20} {v}")
    assert kt["gach ngang dai"] == 0 and kt["the <style>"] == 0 and kt["the <script>"] == 0

    (OUT / "blog_jonsbo_preview.html").write_text(
        '<div style="max-width:920px;margin:0 auto;padding:24px;background:#fff">' + body + "</div>",
        encoding="utf-8")
    print(f"\nDa ghi {OUT / 'blog_jonsbo_preview.html'}")

    if a.thu:
        return

    img = Path(r"C:\Users\NGHIANGO\Downloads\10d61683-1180-401a-978e-2766b3e23cd0.png")
    from PIL import Image
    im = Image.open(img).convert("RGB")
    im.thumbnail((1200, 1200), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "WEBP", quality=86, method=6)
    b64 = base64.b64encode(buf.getvalue()).decode()

    # Gate chan tao bai blog moi la co y (chan script tu dong). Day la thao tac
    # vo yeu cau va da duyet noi dung tren trang preview, nen mo khoa co ly do.
    with hc.allow_blocked_operations("vo duyet 14/8: tao bai blog khuyen mai Jonsbo"):
        art = hc._request("POST", f"/blogs/{BLOG_ID}/articles.json", payload={"article": {
            "title": TIEU_DE,
            "body_html": body,
            "published": False,
            "image": {"attachment": b64,
                      "filename": "sn-bn-jonsbo-sale-sintechvn.webp"},
            "tags": "Jonsbo, khuyến mãi, vỏ case, tản nhiệt",
        }})["article"]
    print(f"\nDA TAO BAI (CHUA XUAT BAN)")
    print(f"  id     : {art['id']}")
    print(f"  handle : {art['handle']}")
    print(f"  anh    : {(art.get('image') or {}).get('src')}")
    (OUT / "_jonsbo_article.json").write_text(json.dumps(
        {"id": art["id"], "handle": art["handle"],
         "image": (art.get("image") or {}).get("src")}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
