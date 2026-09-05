# -*- coding: utf-8 -*-
"""Kho THÔNG BÁO dùng chung cho toàn Hub.

Vợ chốt 12/8/2026. Ba mức, cùng một kho:
  · chuông có số  — mọi thông báo vào đây
  · bong bóng     — chỉ tin MỚI NHẤT chưa xem, 1 lần mỗi phiên
  · popup chặn    — CHỈ loại `can_xem`

Vì sao chỉ `can_xem` mới chặn màn hình: tin nào cũng chặn thì vài hôm là bấm
"đã xem xét" theo phản xạ, đúng lúc cần nhất lại thành vô dụng.

Ghi bằng khoá tệp thô sơ (ghi ra .tmp rồi đổi tên) — job chạy nền và web request
có thể ghi cùng lúc, không thì mất cả tệp.
"""
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock

WS = Path(__file__).resolve().parent.parent.parent            # …/workspace
FILE = WS / "nox-outputs" / "thong_bao.json"
LUU_TRU = WS / "nox-outputs"                                  # bản đầy đủ → tab /preview tự quét
_LOCK = Lock()
GIU = 200                                                     # giữ tối đa bao nhiêu tin

# loại → (nhãn, có chặn màn hình không)
LOAI = {
    "can_xem": ("cần xem", True),
    "sp_moi":  ("SP mới", False),
    "nhac":    ("nhắc", False),
    "xong":    ("xong", False),
    "loi":     ("lỗi", False),
}


def _doc():
    if not FILE.exists():
        return {"ds": [], "toast_phien": None}
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"ds": [], "toast_phien": None}


def _ghi(d):
    d["ds"] = d.get("ds", [])[:GIU]
    tmp = FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(str(tmp), str(FILE))


def them(loai, tieu_de, tom_tat="", viec="", link="", du_lieu=None, khoa=None):
    """Thêm 1 thông báo. Trả về id.

    `khoa` = khoá chống trùng: nếu đã có tin CHƯA ĐỌC cùng khoá thì cập nhật tin cũ
    thay vì đẻ thêm. Job chạy mỗi sáng mà không có cái này thì 10 hôm không mở Hub
    là có 10 dòng y hệt nhau.
    """
    if loai not in LOAI:
        loai = "nhac"
    with _LOCK:
        d = _doc()
        if khoa:
            for t in d["ds"]:
                if t.get("khoa") == khoa and not t.get("doc"):
                    t.update({"tieu_de": tieu_de, "tom_tat": tom_tat, "viec": viec,
                              "link": link, "du_lieu": du_lieu or t.get("du_lieu"),
                              "luc": datetime.now().strftime("%Y-%m-%d %H:%M")})
                    _ghi(d)
                    return t["id"]
        tin = {"id": uuid.uuid4().hex[:12], "loai": loai, "tieu_de": tieu_de,
               "tom_tat": tom_tat, "viec": viec, "link": link, "khoa": khoa,
               "du_lieu": du_lieu, "luc": datetime.now().strftime("%Y-%m-%d %H:%M"),
               "doc": None, "luu_tru": None}
        d["ds"].insert(0, tin)
        _ghi(d)
        return tin["id"]


def danh_sach(n=30):
    return _doc().get("ds", [])[:n]


def so_chua_doc():
    return sum(1 for t in _doc().get("ds", []) if not t.get("doc"))


def tin_chan():
    """Tin loại `can_xem` chưa đọc — cái duy nhất được phép chặn màn hình."""
    for t in _doc().get("ds", []):
        if t.get("loai") == "can_xem" and not t.get("doc"):
            return t
    return None


def tin_toast(phien):
    """Tin mới nhất chưa đọc, và chỉ trả 1 LẦN cho mỗi phiên trình duyệt."""
    d = _doc()
    if d.get("toast_phien") == phien:
        return None
    for t in d.get("ds", []):
        if not t.get("doc") and t.get("loai") != "can_xem":
            return t
    return None


def danh_dau_toast(phien):
    with _LOCK:
        d = _doc()
        d["toast_phien"] = phien
        _ghi(d)


def doc(tid):
    with _LOCK:
        d = _doc()
        for t in d["ds"]:
            if t["id"] == tid:
                t["doc"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                _ghi(d)
                return t
        return None


def doc_het():
    with _LOCK:
        d = _doc()
        gio = datetime.now().strftime("%Y-%m-%d %H:%M")
        n = 0
        for t in d["ds"]:
            if not t.get("doc"):
                t["doc"] = gio
                n += 1
        _ghi(d)
        return n


def ghi_luu_tru(tid, ten_file):
    with _LOCK:
        d = _doc()
        for t in d["ds"]:
            if t["id"] == tid:
                t["luu_tru"] = ten_file
                _ghi(d)
                return True
        return False
