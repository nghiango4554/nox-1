# -*- coding: utf-8 -*-
"""Routes: 🔔 Thông báo dùng chung — chuông ở mọi tab.

  GET  /thong-bao                json danh sách + số chưa đọc
  POST /thong-bao/doc            đánh dấu 1 tin đã đọc
  POST /thong-bao/doc-het        đánh dấu tất cả
  POST /thong-bao/toast-da-hien  ghi nhận bong bóng đã bung trong phiên này
  POST /thong-bao/da-xem-xet     tin `can_xem`: đóng popup + SINH BẢN LƯU TRỮ có ảnh

Bản lưu trữ ghi vào `nox-outputs/` nên tab /preview (routes/preview.py) tự quét thấy,
không phải làm trang mới.
"""
import html as _html
import io
import base64
import urllib.request
from datetime import datetime

from flask import jsonify, request

import notify

MAU = {"them": ("#16a34a", "#d7f2e1", "#186b3a"),
       "bot": ("#e11d48", "#fde4de", "#a3301c"),
       "thay": ("#d97706", "#fff3d6", "#8a5a00"),
       "thutu": ("#2563eb", "#dbeafe", "#12386e"),
       "an": ("#94a3b8", "#eef1f6", "#5b647a")}


def _phien():
    """Mã phiên trình duyệt do JS gửi lên — để bong bóng chỉ bung 1 lần mỗi phiên."""
    return (request.args.get("phien") or (request.get_json(silent=True) or {}).get("phien")
            or "")


def thong_bao_json():
    return jsonify({
        "so": notify.so_chua_doc(),
        "ds": notify.danh_sach(30),
        "chan": notify.tin_chan(),
        "toast": notify.tin_toast(_phien()),
    })


def thong_bao_doc():
    tid = (request.get_json(silent=True) or {}).get("id") or ""
    t = notify.doc(tid)
    return jsonify({"ok": bool(t), "so": notify.so_chua_doc()})


def thong_bao_doc_het():
    return jsonify({"ok": True, "n": notify.doc_het(), "so": notify.so_chua_doc()})


def thong_bao_toast_da_hien():
    notify.danh_dau_toast(_phien())
    return jsonify({"ok": True})


# ───────────────────────── bản lưu trữ có ảnh ─────────────────────────

def _thu_nho(src, s=104):
    """Tải ảnh và nhúng thẳng vào file ở cỡ nhỏ (~6KB).

    Cố ý KHÔNG trỏ link Haravan: một năm sau mở lại bản lưu trữ vẫn còn ảnh, kể cả
    khi ảnh gốc đã bị thay hoặc xoá — mà đó chính là lúc cần xem lại nhất.
    """
    from PIL import Image
    try:
        raw = urllib.request.urlopen(src, timeout=25).read()
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        c = Image.new("RGB", (s, s), "white")
        im.thumbnail((s, s), Image.LANCZOS)
        c.paste(im, ((s - im.width) // 2, (s - im.height) // 2))
        b = io.BytesIO()
        c.save(b, "JPEG", quality=78)
        return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
    except Exception:
        return ""


def _khoi_sp(x):
    """Một khối HTML cho 1 SP trong bản lưu trữ: dải ảnh + giải thích hậu quả."""
    import haravan_client as hc
    vien, nen, chu = MAU.get(x.get("loai"), MAU["thay"])
    h = x.get("handle", "")
    anh = []
    try:
        p = hc._request("GET", "/products.json", params={"handle": h, "limit": 1})["products"][0]
        ims = sorted(p.get("images") or [], key=lambda i: i.get("position") or 0)
        moi = max(0, (x.get("so_moi") or 0) - (x.get("so_cu") or 0))
        for i, im in enumerate(ims):
            la_moi = x.get("loai") == "them" and i >= len(ims) - moi
            d = _thu_nho(im["src"])
            if d:
                anh.append(
                    '<figure style="margin:0"><img src="%s" style="width:104px;height:104px;'
                    'object-fit:contain;background:#fff;border:%s;border-radius:7px;display:block">'
                    '<figcaption style="font-size:10.5px;text-align:center;color:%s;margin-top:2px">'
                    '#%d%s</figcaption></figure>'
                    % (d, ("3px solid " + vien) if la_moi else "1px solid #dde3ec",
                       vien if la_moi else "#8a93a6", i + 1, " MỚI" if la_moi else ""))
    except Exception:
        pass

    if x.get("loai") == "them":
        vi_sao = ("Kho ảnh chuẩn của SP này vẫn đang có <b>%d tấm</b>, nên nếu đẩy từ /thumbs "
                  "thì <b>%d tấm mới sẽ bị xoá</b>. Muốn giữ thì kéo chúng về kho trước, "
                  "hoặc bỏ qua SP này khi đẩy cả cụm."
                  % (x.get("so_cu") or 0, (x.get("so_moi") or 0) - (x.get("so_cu") or 0)))
    elif x.get("loai") == "bot":
        vi_sao = ("Ảnh trên web <b>ít đi</b> so với lần chụp trước. Nếu không ai cố ý xoá thì "
                  "nên kiểm lại — có thể một lượt đẩy nào đó đã ghi đè.")
    elif x.get("loai") == "thutu":
        vi_sao = ("Số lượng ảnh không đổi nhưng <b>thứ tự đã khác</b>. Ảnh đại diện ngoài lưới "
                  "danh mục có thể đã đổi sang tấm khác.")
    elif x.get("loai") == "an":
        vi_sao = "SP không còn trong danh sách đang bán — đã ẩn hoặc xoá."
    else:
        vi_sao = ("Có tấm bị bỏ và tấm được thêm. Kho và web giờ lệch nhau, nên đối chiếu "
                  "trước khi đẩy.")

    return ("""<div style="border:1px solid #e3e8f0;border-radius:11px;padding:15px 16px;
      background:#fcfdff;margin-bottom:14px">
      <div style="font-size:16px;font-weight:700;margin-bottom:5px">%s</div>
      <div><span style="display:inline-block;font-size:11.5px;font-weight:700;padding:2px 9px;
        border-radius:999px;background:%s;color:%s;margin-right:8px">%s</span>
        <span style="font-size:13px;color:#5b647a">%d → %d ảnh · <code>%s</code></span></div>
      <div style="display:flex;gap:9px;flex-wrap:wrap;margin:11px 0">%s</div>
      <div style="font-size:13px;color:#5b647a;border-top:1px dashed #e3e8f0;padding-top:10px">
        <b>Nghĩa là gì:</b> %s</div>
      <div style="margin-top:9px"><a href="https://sintech.vn/products/%s" target="_blank"
        rel="noopener" style="font-size:12.5px;color:#1457b8;text-decoration:none">xem trên web ↗</a></div>
    </div>""" % (_html.escape(x.get("title") or h), nen, chu,
                 _html.escape(x.get("chi_tiet") or ""), x.get("so_cu") or 0,
                 x.get("so_moi") or 0, _html.escape(h),
                 "".join(anh) or '<i style="color:#8a93a6;font-size:13px">không tải được ảnh</i>',
                 vi_sao, _html.escape(h)))


def _sinh_luu_tru(tin):
    """Dựng file HTML đầy đủ (có ảnh) rồi ghi vào nox-outputs → hiện ở tab /preview."""
    ds = (tin.get("du_lieu") or {}).get("thay_doi") or []
    gio = datetime.now()
    ten = "thongbao_%s_%s.html" % (gio.strftime("%Y%m%d_%H%M"), tin["id"][:6])
    than = "".join(_khoi_sp(x) for x in ds)
    doc_html = """<!doctype html><meta charset="utf-8">
<title>%s — %s</title>
<style>body{font:15px/1.6 system-ui,Segoe UI,Arial;background:#eef1f6;color:#1d2430;margin:0;padding:24px}
.w{max-width:940px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}
.meta{color:#5b647a;font-size:13.5px;margin:0 0 20px}
code{background:#f2f5f9;padding:1px 6px;border-radius:5px;font-size:12.5px}</style>
<div class="w"><h1>%s</h1>
<p class="meta">Phát hiện lúc <b>%s</b> · đã xem xét lúc <b>%s</b> · %d sản phẩm.<br>
Đây là thay đổi làm <b>bên ngoài</b> trang /thumbs (trực tiếp trên Haravan).
Ảnh nhúng sẵn trong tệp này nên về sau vẫn xem lại được dù ảnh gốc có đổi.</p>
%s</div>""" % (_html.escape(tin.get("tieu_de", "Thông báo")), gio.strftime("%d/%m/%Y"),
               _html.escape(tin.get("tieu_de", "Thông báo")), tin.get("luc", ""),
               gio.strftime("%Y-%m-%d %H:%M"), len(ds), than)
    (notify.LUU_TRU / ten).write_text(doc_html, encoding="utf-8")
    return ten


def thong_bao_da_xem_xet():
    tid = (request.get_json(silent=True) or {}).get("id") or ""
    tin = None
    for t in notify.danh_sach(200):
        if t["id"] == tid:
            tin = t
            break
    if not tin:
        return jsonify({"ok": False, "loi": "không thấy thông báo"}), 404
    notify.doc(tid)
    try:
        ten = _sinh_luu_tru(tin)
        notify.ghi_luu_tru(tid, ten)
    except Exception as e:                                   # lưu trữ hỏng thì vẫn cho qua
        return jsonify({"ok": True, "luu_tru": None, "loi_luu": str(e)[:120]})
    return jsonify({"ok": True, "luu_tru": ten,
                    "link": "/preview?f=outputs/" + ten})


def register(app):
    app.add_url_rule("/thong-bao", "thong_bao_json", thong_bao_json)
    app.add_url_rule("/thong-bao/doc", "thong_bao_doc", thong_bao_doc, methods=["POST"])
    app.add_url_rule("/thong-bao/doc-het", "thong_bao_doc_het", thong_bao_doc_het,
                     methods=["POST"])
    app.add_url_rule("/thong-bao/toast-da-hien", "thong_bao_toast_da_hien",
                     thong_bao_toast_da_hien, methods=["POST"])
    app.add_url_rule("/thong-bao/da-xem-xet", "thong_bao_da_xem_xet",
                     thong_bao_da_xem_xet, methods=["POST"])
