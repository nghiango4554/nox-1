"""Routes: nhận dữ liệu bài viết Facebook cào từ Meta Business Suite.

Trình duyệt đang mở Business Suite POST thẳng vào đây (CORS mở cho localhost),
khỏi phải bê JSON qua chat. Dữ liệu lưu ở `data/fb_posts_import.json`.

Dùng cho: đối chiếu chống trùng SP đã đăng + xem lại bài cũ trong hub.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from flask import request, jsonify, render_template

STORE = Path(__file__).resolve().parent.parent / "data" / "fb_posts_import.json"
THANG = {"tháng 1": 1, "tháng 2": 2, "tháng 3": 3, "tháng 4": 4, "tháng 5": 5, "tháng 6": 6,
         "tháng 7": 7, "tháng 8": 8, "tháng 9": 9, "tháng 10": 10, "tháng 11": 11, "tháng 12": 12}


def _doc() -> dict:
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {"cap_nhat": None, "items": []}


def _luu(d: dict):
    d["cap_nhat"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _ngay_iso(s: str, nam_mac_dinh: int = None) -> str:
    """'26 Tháng 7 18:00' -> '2026-07-26 18:00'. Không parse được thì trả nguyên."""
    s = (s or "").strip()
    m = re.match(r"(\d{1,2})\s+(Tháng\s+\d{1,2})\s*(\d{1,2}:\d{2})?", s, re.I)
    if not m:
        return s
    ngay = int(m.group(1))
    thang = THANG.get(m.group(2).lower().replace("  ", " "), 0)
    gio = m.group(3) or "00:00"
    nam = nam_mac_dinh or datetime.now().year
    if not thang:
        return s
    return f"{nam:04d}-{thang:02d}-{ngay:02d} {gio}"


def api_fb_import():
    """Nhận danh sách bài. Body: {items: [{caption, ngay, tiep_can, luot_xem, tuong_tac}]}"""
    d = request.get_json(silent=True) or {}
    items = d.get("items") or []
    if not isinstance(items, list):
        return jsonify({"ok": False, "error": "items phải là mảng"}), 400

    doc = _doc()
    cu = {(x.get("caption", "")[:80], x.get("ngay")) for x in doc["items"]}
    them = 0
    for it in items:
        cap = (it.get("caption") or "").strip()
        ngay = (it.get("ngay") or "").strip()
        if not cap or not ngay:
            continue
        if (cap[:80], ngay) in cu:
            continue
        doc["items"].append({
            "caption": cap,
            "ngay_goc": ngay,
            "ngay": _ngay_iso(ngay),
            "tiep_can": it.get("tiep_can", ""),
            "luot_xem": it.get("luot_xem", ""),
            "tuong_tac": it.get("tuong_tac", ""),
            "nguon": "meta_business_suite",
        })
        cu.add((cap[:80], ngay))
        them += 1

    doc["items"].sort(key=lambda x: x.get("ngay", ""), reverse=True)
    _luu(doc)
    r = jsonify({"ok": True, "them": them, "tong": len(doc["items"])})
    r.headers["Access-Control-Allow-Origin"] = "*"
    return r


def api_fb_import_options():
    r = jsonify({"ok": True})
    r.headers["Access-Control-Allow-Origin"] = "*"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type"
    r.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return r


def api_fb_import_list():
    doc = _doc()
    return jsonify({"ok": True, "cap_nhat": doc.get("cap_nhat"),
                    "tong": len(doc["items"]), "items": doc["items"]})


def _so(v):
    """'1.234' / '1,234' / '' → int. Dữ liệu cào về có nhiều kiểu ghi số."""
    if v is None:
        return 0
    s = str(v).strip().replace(".", "").replace(",", "").replace(" ", "")
    return int(s) if s.isdigit() else 0


def fb_posts_page():
    import os
    doc = _doc()
    items = []
    for i, x in enumerate(doc["items"], 1):
        cap = (x.get("caption") or "").strip()
        items.append({
            "stt": i,
            "ngay": x.get("ngay") or "",
            "caption": cap,
            "headline": cap.split("\n")[0][:120] if cap else "(không có nội dung)",
            "tiep_can": _so(x.get("tiep_can")),
            "luot_xem": _so(x.get("luot_xem")),
        })

    theo_thang = {}
    for x in items:
        k = (x["ngay"] or "")[:7]
        if k:
            theo_thang[k] = theo_thang.get(k, 0) + 1

    reach = [x["tiep_can"] for x in items if x["tiep_can"]]
    tb = round(sum(reach) / len(reach)) if reach else 0
    top = sorted(items, key=lambda x: -x["tiep_can"])[:3]
    top_ids = {x["stt"] for x in top if x["tiep_can"]}

    css = ""
    try:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "static", "css", "fb-module.css")
        css = str(int(os.path.getmtime(p)))
    except OSError:
        css = "0"

    return render_template("fb_posts_import.html", items=items,
                           cap_nhat=doc.get("cap_nhat"),
                           theo_thang=sorted(theo_thang.items(), reverse=True),
                           tb_reach=tb, top_ids=top_ids,
                           co_so_lieu=bool(reach), css_v=css)


def register(app):
    app.add_url_rule("/api/fb-import", "api_fb_import", api_fb_import, methods=["POST"])
    app.add_url_rule("/api/fb-import", "api_fb_import_options", api_fb_import_options,
                     methods=["OPTIONS"])
    app.add_url_rule("/api/fb-import/list", "api_fb_import_list", api_fb_import_list)
    app.add_url_rule("/facebook/bai-da-cao", "fb_posts_page", fb_posts_page)
