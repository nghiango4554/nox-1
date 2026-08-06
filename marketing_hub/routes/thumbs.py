"""Routes: Chuẩn hóa ảnh Thumbnail — xem preview (contact sheet + before/after).

Trang:
  /thumbs            — tổng quan theo wave/collection (đã gen preview chưa, bao nhiêu SP)
  /thumbs/c/<handle> — chi tiết 1 collection: contact sheet lưới + before/after từng SP
  /thumbs/img/<kind>/<name> — phục vụ file ảnh từ Desktop\\Sintech-img\\thumb_chuan

AN TOÀN: read-only, KHÔNG up Haravan (chỉ GET list SP + đọc ảnh local).
Ảnh do scripts workspace (standardize_all.py) gen ra, KHÔNG sinh trong web.
"""
import base64
import csv
import io
import json
import re
import threading
import time
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path

from flask import (render_template, send_from_directory, abort, request, jsonify,
                   make_response, has_request_context, g)
from PIL import Image, ImageChops

import haravan_client as hc

WS = Path(r"C:\Users\NGHIANGO\.openclaw\workspace")
NOXOUT = WS / "nox-outputs"
THUMB_ROOT = Path(r"C:\Users\NGHIANGO\Desktop\Sintech-img\thumb_chuan")
KINDS = {"std", "_contact", "_preview"}
# _preview = bản nhỏ 280px CHỈ để nhìn trên trang này (ảnh gốc 1000px hiện ở khung
# 140px là thừa gấp 7 lần → case-gaming phải tải 112 MB). Bản nhỏ chỉ ~10 KB/ảnh.
# Ảnh gốc trong std KHÔNG bị đụng: phóng to, đẩy Haravan, đếm, sắp thứ tự đều dùng std.
PREVIEW_KIND = "_preview"
STATUS_FILE = NOXOUT / "thumb_status.json"   # {handle: {status: da_duyet|da_sync, at: ...}}
DOWNLOADS = Path.home() / "Downloads"
ADDED_ARCHIVE = Path(r"C:\Users\NGHIANGO\Desktop\Sintech-img\anh_them_da_dung")
SYNCED_FILE = NOXOUT / "thumb_synced_products.json"   # list handle SP đã sync (dedup chống up trùng)
BACKUP_ORIG = THUMB_ROOT / "_backup_orig"

# tiến độ sync (chạy nền)
SYNC_STATE = {"running": False, "finished": False, "total": 0, "done": 0,
              "ok": 0, "fail": 0, "current": "", "msg": "", "relech": []}
SYNC_LOCK = threading.Lock()


def _load_synced():
    if SYNCED_FILE.exists():
        try:
            return set(json.loads(SYNCED_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def _save_synced(s):
    SYNCED_FILE.write_text(json.dumps(sorted(s), ensure_ascii=False), encoding="utf-8")


def _load_status():
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_status(d):
    STATUS_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ───────────── nhớ tạm kết quả hàm phụ ─────────────
# Đo 6/8/2026: vẽ 1 trang collection gọi lại _menu_groups() 3 lần, _product_types()
# 4 lần, _old_cond_handles() 4 lần — lần nào cũng quét lại DB từ đầu (~170ms phí).
# Hai tầng nhớ:
#   · trong 1 request  — luôn đúng tuyệt đối, chỉ bỏ phần gọi lặp
#   · giữa các request — TTL giây; nguồn là bảng spec_* + product_spec_index,
#                        chỉ đổi khi quét lại menu ở tab /spec nên giữ được lâu
# ⚠️ MỌI thao tác ghi (thêm/xoá ảnh, làm lại, duyệt, sync) PHẢI gọi _memo_clear(),
#    không thì đẩy ảnh theo bản đồ cũ — đúng bẫy thumb_collection_map.json (14/7/2026).
_MEMO = {}
_MEMO_LOCK = threading.Lock()
_MEMO_TTL = 120


def _memo(key, fn, ttl=_MEMO_TTL):
    box = None
    if has_request_context():
        box = getattr(g, "_thumb_memo", None)
        if box is None:
            box = {}
            g._thumb_memo = box
        if key in box:
            return box[key]
    hit = _MEMO.get(key)
    now = time.time()
    if hit and now - hit[0] < ttl:
        val = hit[1]
    else:
        val = fn()
        with _MEMO_LOCK:
            _MEMO[key] = (now, val)
    if box is not None:
        box[key] = val
    return val


def _memo_clear():
    """Xoá sạch cache hàm phụ. Gọi sau mọi thao tác ghi và trước khi sync."""
    with _MEMO_LOCK:
        _MEMO.clear()
    if has_request_context():
        g._thumb_memo = {}

TARGET = 1000
FILL = 0.85
PAD = int(TARGET * (1 - FILL) / 2)
INNER = TARGET - 2 * PAD


def _flatten_white(img):
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def _trim_white(img, thresh=12):
    bg = Image.new("RGB", img.size, (255, 255, 255))
    mask = ImageChops.difference(img, bg).convert("L").point(lambda p: 255 if p > thresh else 0)
    bbox = mask.getbbox()
    if not bbox:
        return img
    l, t, r, b = bbox
    return img.crop((max(0, l - 4), max(0, t - 4),
                     min(img.width, r + 4), min(img.height, b + 4)))


def _standardize_no_rembg(img):
    """Chuẩn hóa 1000² nền trắng, fill 85%, căn giữa — KHÔNG xóa nền (chỉ cắt mép trắng)."""
    img = _trim_white(_flatten_white(img))
    s = min(INNER / img.width, INNER / img.height)
    nw, nh = max(1, round(img.width * s)), max(1, round(img.height * s))
    r = img.resize((nw, nh), Image.LANCZOS)
    cv = Image.new("RGB", (TARGET, TARGET), (255, 255, 255))
    cv.paste(r, ((TARGET - nw) // 2, (TARGET - nh) // 2))
    return cv

_COL_CACHE = {}   # handle -> collection_id (nạp 1 lần)


def _collections():
    if not _COL_CACHE:
        for c in (hc.list_smart_collections(limit=250) + hc.list_custom_collections(limit=250)):
            if c.get("handle"):
                _COL_CACHE[c["handle"]] = c["id"]
    return _COL_CACHE


def _warm_collections():
    """Nạp sẵn bản đồ collection lúc server khởi động (~2,5s).

    Không có nó thì lần đầu mở /thumbs/c/... phải chờ đủ 2,5s đó, dù các lần sau
    đã nhanh. Chạy nền, lỗi thì thôi — lần gọi thật sẽ tự nạp lại.
    """
    try:
        _collections()
    except Exception:  # noqa: BLE001
        pass


threading.Thread(target=_warm_collections, daemon=True).start()


_PROD_CACHE = {}      # cid -> (thoi_diem, [products])
# Đo 5/8/2026 trên case-gaming: có cache 190ms · hết cache 2.282ms (chênh 13 lần).
# TTL 90s quá ngắn — vợ rời trang 2 phút quay lại là phải chờ lại từ đầu, cả ngày.
# Danh sách SP trong collection gần như không đổi trong ngày nên nới rộng an toàn.
_PROD_TTL = 900       # 15 phút — coi là còn tươi, trả thẳng
_PROD_MAX = 21600     # 6 giờ — quá hạn này thì phải lấy mới, không trả bản cũ nữa
_PROD_FILE = NOXOUT / "_thumbs_prod_cache.json"   # giữ qua lần restart
_PROD_LOCK = threading.Lock()
_PROD_REFRESHING = set()   # cid đang được làm mới ngầm, tránh gọi chồng
_PROD_FIELDS = "id,handle,title,images,published_at"   # thiếu published_at -> mọi SP coi như ẨN


def _one_page(cid, page):
    return hc._request("GET", "/products.json",
                       params={"collection_id": cid, "limit": 50, "page": page,
                               "fields": _PROD_FIELDS}).get("products", [])


def _fetch_products_in(cid):
    """Kéo toàn bộ SP của collection.

    Haravan cap CỨNG 50 SP/trang — đo 4/8/2026: xin limit=100 hay 250 đều chỉ trả 50.
    Nên collection 279 SP = 6 lượt gọi. Trước đây gọi TUẦN TỰ nên mất ~3,1s.
    Giờ gọi song song từng lô 4 trang, dừng khi gặp trang < 50. Lỗi thì lùi về tuần tự.
    """
    from concurrent.futures import ThreadPoolExecutor
    BATCH = 4
    # Trang 1 gọi TRƯỚC một mình: đa số collection chỉ có 1 trang, bắn 4 request là phí
    # (đo được chuot-gaming 45 SP còn CHẬM hơn cách cũ vì 3 request thừa).
    first = _one_page(cid, 1)
    if len(first) < 50:
        return first
    out, page = list(first), 2
    try:
        while page <= 200:
            pages = list(range(page, page + BATCH))
            with ThreadPoolExecutor(max_workers=BATCH) as ex:
                res = list(ex.map(lambda p: _one_page(cid, p), pages))
            for b in res:
                out.extend(b)
            if any(len(b) < 50 for b in res):
                return out
            page += BATCH
        return out
    except Exception:  # noqa: BLE001 — mạng lỗi/throttle: lùi về cách cũ cho chắc
        out, page = [], 1
        while page <= 200:
            b = _one_page(cid, page)
            out.extend(b)
            if len(b) < 50:
                break
            page += 1
        return out


def _cid_key(cid):
    """JSON chỉ có key kiểu chữ, còn trong code cid là SỐ.
    Không chuẩn hoá thì nạp lại từ đĩa tra không bao giờ khớp — cache thành vô dụng."""
    return str(cid)


def _prod_cache_load():
    """Nạp cache từ đĩa lúc khởi động — restart không phải chờ lại từ đầu."""
    try:
        raw = json.loads(_PROD_FILE.read_text(encoding="utf-8"))
        now = time.time()
        n = 0
        for cid, (t, items) in raw.items():
            if now - t < _PROD_MAX:
                _PROD_CACHE[_cid_key(cid)] = (t, items)
                n += 1
        if n:
            print(f"[thumbs] nạp lại cache {n} collection từ đĩa")
    except Exception:
        pass


def _prod_cache_save():
    try:
        _PROD_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _PROD_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_PROD_CACHE, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_PROD_FILE)
    except Exception:
        pass


def _prod_refresh_bg(cid):
    """Lấy dữ liệu mới ở luồng nền, không bắt người dùng chờ."""
    try:
        out = _fetch_products_in(cid)
        with _PROD_LOCK:
            _PROD_CACHE[_cid_key(cid)] = (time.time(), out)
        _prod_cache_save()
    except Exception:
        pass
    finally:
        _PROD_REFRESHING.discard(_cid_key(cid))


def _products_in(cid, use_cache=False):
    """SP của collection. `use_cache=True` CHỈ dùng khi vẽ trang.

    ⚠️ Luồng SYNC phải để use_cache=False (mặc định): dữ liệu cũ đủ làm sync bỏ sót
    SP mới thêm — đúng bẫy `thumb_collection_map.json` stale đã gặp 14/7/2026.

    Đường vẽ trang dùng kiểu "trả bản cũ trước, làm mới sau":
      · còn tươi (<15 phút)  → trả ngay
      · quá hạn nhưng <6 giờ → VẪN trả ngay bản cũ, đồng thời lấy bản mới ở luồng nền
      · quá 6 giờ / chưa có  → đành lấy mới rồi mới trả
    Nhờ vậy người dùng gần như không bao giờ phải chờ 2,3 giây nữa.
    """
    if use_cache:
        hit = _PROD_CACHE.get(_cid_key(cid))
        if hit:
            tuoi = time.time() - hit[0]
            if tuoi < _PROD_TTL:
                return hit[1]
            if tuoi < _PROD_MAX:
                if _cid_key(cid) not in _PROD_REFRESHING:
                    _PROD_REFRESHING.add(_cid_key(cid))
                    threading.Thread(target=_prod_refresh_bg, args=(cid,), daemon=True).start()
                return hit[1]
    out = _fetch_products_in(cid)
    with _PROD_LOCK:
        _PROD_CACHE[_cid_key(cid)] = (time.time(), out)
    if use_cache:
        _prod_cache_save()
    return out


_prod_cache_load()


def _read_tracking():
    p = NOXOUT / "thumb_tracking.csv"
    if not p.exists():
        return []
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def _preview_log():
    """handle -> dict(...) từ log gen preview. Chịu được thiếu header / dòng rách
    (file bị ghi đồng thời lúc đang gen)."""
    p = NOXOUT / "thumb_preview_log.csv"
    cols = ["wave", "handle", "so_sp", "so_anh", "noimg", "rembg", "loi"]
    out = {}
    if not p.exists():
        return out
    try:
        with open(p, encoding="utf-8-sig", newline="") as f:
            for row in csv.reader(f):
                if not row or row[0] == "wave":   # bỏ header nếu có
                    continue
                d = dict(zip(cols, row))
                h = d.get("handle")
                if h:
                    out[h] = d
    except Exception:
        pass
    return out


UNGROUPED = "__ungrouped__"

# Trần mỗi trang ở trang chi tiết collection. Thêm ?all=1 để xem hết trong 1 trang.
# ⚠️ 6/8/2026 — SỬA LẠI CÁCH ĐẾM. Bản đầu chỉ chặn theo SỐ SP (60), mà thứ làm
# trình duyệt ì là SỐ THẺ <img>, không phải số SP. Đo ra 18 collection dưới 60 SP
# nhưng mỗi SP nhiều ảnh vẫn ra 200-315 ảnh/trang và KHÔNG được chia gì cả
# (man-hinh-gaming 315 · man-hinh-22-25-inch 294 · laptop-asus 288...).
# Nay chặn theo CẢ HAI, cái nào chạm trước thì cắt.
SP_MOI_TRANG = 60
ANH_MOI_TRANG = 200


def _chia_lat(items, sp_max=SP_MOI_TRANG, anh_max=ANH_MOI_TRANG):
    """Cắt items thành các lát (đầu, cuối) — chạm trần SP hoặc trần ảnh thì sang trang.

    Luôn nhận ÍT NHẤT 1 SP mỗi trang, để 1 SP có hơn 200 ảnh không đẻ ra trang rỗng.
    """
    lat, dau, n_sp, n_anh = [], 0, 0, 0
    for i, it in enumerate(items):
        w = len(it.get("imgs") or [])
        if n_sp and (n_sp + 1 > sp_max or n_anh + w > anh_max):
            lat.append((dau, i))
            dau, n_sp, n_anh = i, 0, 0
        n_sp += 1
        n_anh += w
    if dau < len(items) or not lat:
        lat.append((dau, len(items)))
    return lat

# Vợ chốt 22/7/2026: nhánh PC build sẵn + combo PC HIỆN KHÔNG LÀM ảnh chuẩn.
# Vẫn hiện trên trang (gập lại, để cuối) nhưng KHÔNG tính vào tiến độ / việc cần làm.
OUT_OF_SCOPE_ROOTS = {"PC Gaming – Đồ Họa – AI", "PC Văn Phòng – Máy Bộ",
                      "Dịch Vụ & Sửa Chữa"}


def _menu_groups():
    return _memo("menu_groups", _menu_groups_raw)


def _menu_groups_raw():
    """Phân tầng theo MENU LIVE (giống tab /spec): chỉ collection LÁ, gom theo nhánh gốc.

    Thay cho `thumb_tracking.csv` (4 wave, thứ tự cũ) + `thumb_collection_map.json`
    (file tĩnh, 22/7/2026 đo được **4.791/8.221 cặp là rác** vì gom cả collection MẸ).
    Nguồn: bảng `spec_menu_collections` + `spec_group_products` do tab /spec quét từ menu live.
    Trả list [{handle, title, root, parent, sp: [handle SP]}] + nhóm "SP chưa phân loại".
    """
    import db as _db
    conn = _db.get_conn()
    try:
        colls = conn.execute("SELECT handle, title, root, parent, sort_order "
                             "FROM spec_menu_collections ORDER BY sort_order").fetchall()
        gp = {}
        for h, pid in conn.execute("SELECT handle, haravan_id FROM spec_group_products"):
            gp.setdefault(h, []).append(pid)
        # 27/7/2026: LỌC SP ĐÃ ẨN. Trước đó /thumbs gom cả SP `published=0` (đo được 156 con,
        # web trả 301 về collection hoặc 404) => tốn công căn ảnh cho SP không còn bán.
        prods = {r[0]: dict(handle=r[1], title=r[2], cond=r[3], svc=r[4])
                 for r in conn.execute("SELECT haravan_id, handle, title, condition_kind, "
                                       "COALESCE(is_service,0) FROM product_spec_index "
                                       "WHERE COALESCE(published,1)=1")}
    except Exception:
        conn.close()
        return []
    conn.close()
    # 🔧 27/7/2026 (vợ bắt được ở vga-nvidia): THẺ NGOÀI và TRANG TRONG phải đếm
    # CÙNG MỘT BỘ LỌC. Trước đây _menu_groups() lấy hết SP trong nhóm, còn
    # _collection_items() lại bỏ hàng cũ + combo PC + SP sai loại → vga-nvidia
    # thẻ ngoài ghi "249 SP · 72 đã sync" mà bấm vào chỉ có 163 SP, 0 đã sync
    # (rule smart collection vơ nhầm 55 laptop có chữ 'RTX' trong tên).
    _old = _old_cond_handles()
    _ptypes = _product_types()

    def _keep(ph, coll):
        if ph in _old:
            return False                       # hàng cũ / qua sử dụng
        t = _ptypes.get(ph)
        if t in HIDE_PRODUCT_TYPES:
            return False                       # combo PC — không chuẩn hoá
        allow = COLLECTION_TYPE_FILTER.get(coll)
        return not (allow and t and t not in allow)

    out, seen = [], set()
    for c in colls:
        sp = [prods[i]["handle"] for i in gp.get(c["handle"], []) if i in prods]
        sp = [ph for ph in sp if _keep(ph, c["handle"])]
        seen |= set(sp)
        root = c["root"] or "Khác"
        out.append({"handle": c["handle"], "title": c["title"], "root": root,
                    "parent": c["parent"] or "", "sp": sp,
                    "in_scope": root not in OUT_OF_SCOPE_ROOTS})
    # "SP chưa phân loại" cũng phải theo cùng bộ lọc, không thì SP vừa bị loại khỏi
    # nhóm (laptop lẫn trong vga, combo PC…) lại rơi hết vào đây.
    rest = [p["handle"] for p in prods.values()
            if p["cond"] == "new" and not p["svc"] and p["handle"] not in seen
            and p["handle"] not in _old
            and _ptypes.get(p["handle"]) not in HIDE_PRODUCT_TYPES]
    if rest:
        out.append({"handle": UNGROUPED, "title": "SP chưa phân loại",
                    "root": "⚠️ Chưa phân loại", "parent": "", "sp": rest,
                    "in_scope": True})
    return out


def _collection_map():
    """handle collection -> [handle SP]. Lấy từ menu live; hụt thì lùi về file cũ."""
    groups = _menu_groups()
    if groups:
        return {g["handle"]: g["sp"] for g in groups}
    p = NOXOUT / "thumb_collection_map.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


# Collection TỔNG/CHA (catch-all) — KHÔNG cho làm 'collection chính' của SP, để trang
# tổng được dọn gọn còn SP lấy collection CỤ THỂ làm nhà. Sửa/bổ sung tự do.
AGGREGATE_HANDLES = {
    "linh-kien-may-tinh", "phu-kien-may-tinh", "gaming-gear", "man-hinh-may-tinh",
    "man-hinh-may-tinh-pc", "laptop", "hang-cu", "thiet-bi-mang", "may-tinh-bo",
    "pc-gaming-do-hoa-ai", "pc-van-phong", "camera-giam-sat",
}


def _primary_map():
    return _memo("primary_map", _primary_map_raw)


def _primary_map_raw():
    """handle SP -> collection 'CHÍNH' (nơi SP hiện đầy đủ 1 lần, chỗ khác đánh dấu 'đã xem').

    Từ 22/7/2026 chỉ còn collection LÁ nên không cần né collection mẹ nữa:
    lấy nhóm ĐẦU TIÊN theo thứ tự menu live làm nhà.
    """
    primary = {}
    for g in _menu_groups():
        for ph in g["sp"]:
            primary.setdefault(ph, g["handle"])
    return primary


def _std_done():
    """Tập handle SP đã có ảnh chuẩn (mỗi SP = 1 thư mục std/<handle>/)."""
    d = THUMB_ROOT / "std"
    return {p.name for p in d.iterdir() if p.is_dir()} if d.exists() else set()


def _manifest(handle):
    p = THUMB_ROOT / "std" / handle / "manifest.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _img_ver(handle, idx) -> int:
    """Giờ sửa của ảnh gốc — gắn vào ?v= trong đường dẫn.
    Ảnh đổi thì đường dẫn đổi, trình duyệt buộc tải bản mới thay vì bám ảnh cũ."""
    try:
        return int((THUMB_ROOT / "std" / handle / f"{idx}.jpg").stat().st_mtime)
    except OSError:
        return 0


def _sp_state(handle):
    """Bộ ảnh hiện tại của 1 SP, kèm giờ sửa từng ảnh.

    Để trang vẽ lại ĐÚNG dải ảnh của SP đó thay vì tải lại cả trang (6/8/2026).
    Trang collection lớn nặng ~980 KB / 976 thẻ ảnh — xoá 1 ảnh mà tải lại hết
    thì mỗi thao tác phải chờ vài giây.
    `vers` = ?v= chống trình duyệt bám ảnh cũ, đúng như template vẫn làm.
    """
    idxs = _sp_images(handle)
    return {"handle": handle, "imgs": idxs, "n": len(idxs),
            "vers": {str(i): _img_ver(handle, i) for i in idxs}}


def _sp_images(handle, kind="std"):
    """idx ảnh chuẩn của 1 SP, theo THỨ TỰ trong manifest (đã kéo-thả). Fallback: theo số."""
    d = THUMB_ROOT / kind / handle
    if not d.exists():
        return []
    files = {int(p.stem) for p in d.glob("*.jpg") if p.stem.isdigit()}
    man = _manifest(handle)
    if man:
        order = [e["idx"] for e in man if isinstance(e, dict) and e.get("idx") in files]
        order += [i for i in sorted(files) if i not in order]
        return order
    return sorted(files)


# ───────────── pages ─────────────

def thumbs_page():
    # Phân tầng theo MENU LIVE (đổi 22/7/2026, vợ chốt: bỏ hẳn 4 wave + collection mẹ)
    groups = _menu_groups()
    log = _preview_log()
    primary = _primary_map()          # SP -> collection 'nhà'
    done_set = _std_done()
    synced_set = _load_synced()
    status = _load_status()
    waves, waves_off = {}, {}
    tot = {"sp": 0, "col_done": 0, "approved": 0, "synced": 0, "to_sync": 0,
           "off_col": 0, "off_sp": 0,
           # 27/7/2026: số liệu cho thanh "việc cần làm" + bộ lọc
           "relech": 0, "pending_sp": 0, "nogen": 0, "gen": 0, "todo": [],
           "todo_push": [], "todo_hand": [], "push_sp_set": set(), "push_sp": 0}
    for r in groups:
        h = r["handle"]
        lg = log.get(h)
        sp_handles = r["sp"]
        total = len(sp_handles)
        gen = sum(1 for ph in sp_handles if ph in done_set)
        pct = round(gen * 100 / total) if total else 0

        def _int(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return 0
        rembg = _int(lg.get("rembg")) if lg else 0
        noimg = _int(lg.get("noimg")) if lg else 0
        gstatus = "done" if (total and gen >= total) else ("partial" if gen else "pending")
        review = (status.get(h) or {}).get("status", "")   # '' | da_duyet | da_sync
        # 'nhà' của bao nhiêu SP nằm ở chính nhóm này. own==0 mà vẫn có SP
        # => toàn bộ SP đã có nhà ở nhóm khác -> làm MỜ card (không xóa/ẩn).
        own = sum(1 for ph in sp_handles if primary.get(ph) == h)
        all_seen = bool(sp_handles) and own == 0
        # Bẫy 22/7/2026: cờ 'da_sync' đóng từ lần trước KHÔNG tự mở khi có SP/ảnh mới
        # → thẻ hiện xanh "đã sync" trong khi còn SP chưa đẩy (vợ bắt được 2 con laptop).
        pending = sum(1 for ph in sp_handles
                      if (THUMB_ROOT / "std" / ph).exists() and ph not in synced_set)
        if review == "da_sync" and pending:
            review = "sync_lech"
        bucket = waves if r.get("in_scope", True) else waves_off
        w = bucket.setdefault(r["root"], {"nhom": r["root"], "cols": [], "gen": 0, "total": 0})
        # nhãn lọc: mỗi thẻ thuộc đúng 1 nhóm việc -> bộ lọc phía trên dùng cái này
        if review == "sync_lech":
            flt = "relech"
        elif not gen:
            flt = "nogen"
        elif gstatus != "done":
            flt = "dang"
        elif review == "da_sync":
            flt = "xong"
        else:
            flt = "chosync"
        w["cols"].append({
            "handle": h, "title": r["title"], "parent": r["parent"],
            "so_sp": total, "gen": gen, "pct": pct,
            "synced": sum(1 for ph in sp_handles if ph in synced_set), "pending": pending,
            "rembg": rembg, "noimg": noimg, "status": gstatus, "review": review,
            "own": own, "all_seen": all_seen, "flt": flt,
        })
        w["gen"] += gen
        w["total"] += total
        if not r.get("in_scope", True):        # ngoài phạm vi: không tính vào tiến độ
            tot["off_col"] += 1
            tot["off_sp"] += total
            continue
        tot["sp"] += total
        tot["gen"] += gen
        if gstatus == "done":
            tot["col_done"] += 1
        if review == "da_duyet":
            tot["approved"] += 1
            tot["to_sync"] += 1
        elif review == "da_sync":
            tot["synced"] += 1
        elif review == "sync_lech":
            tot["relech"] += 1
            tot["pending_sp"] += pending
            tot["to_sync"] += 1
        # danh mục RỖNG (0 SP) không phải "chưa gen" — đừng tính vào việc cần làm
        if not gen and not all_seen and total:
            tot["nogen"] += 1
        if review in ("sync_lech", "da_duyet") or (not gen and not all_seen and total):
            kind = ("relech" if review == "sync_lech"
                    else "duyet" if review == "da_duyet" else "nogen")
            row = {"handle": h, "title": r["title"], "root": r["root"],
                   "pending": pending, "so_sp": total, "gen": gen, "kind": kind}
            tot["todo"].append(row)
            # Tách 2 loại việc KHÁC HẲN NHAU (vợ hỏi 27/7):
            #  · bấm-1-nút  = đã có ảnh chuẩn, chỉ chờ đẩy live
            #  · làm-tay    = chưa gen ảnh, phải ngồi làm
            if kind in ("relech", "duyet"):
                tot["todo_push"].append(row)
                tot["push_sp_set"].update(
                    ph for ph in sp_handles
                    if (THUMB_ROOT / "std" / ph).exists() and ph not in synced_set)
            else:
                tot["todo_hand"].append(row)
    tot["todo"].sort(key=lambda x: (-x["pending"], -x["so_sp"]))
    tot["todo_push"].sort(key=lambda x: -x["pending"])
    tot["todo_hand"].sort(key=lambda x: -x["so_sp"])
    # ĐẾM SP DUY NHẤT — cộng 'pending' từng danh mục sẽ tính trùng SP nằm nhiều danh mục
    tot["push_sp"] = len(tot["push_sp_set"])
    # ⚠️ tot['sp']/tot['gen'] là số LƯỢT (1 SP ở nhiều danh mục bị cộng nhiều lần).
    # KPI phải hiện SỐ SP DUY NHẤT, không thì vợ tưởng shop có 3.533 SP.
    uniq = {ph for r in groups if r.get("in_scope", True) for ph in r["sp"]}
    tot["sp_uniq"] = len(uniq)
    tot["gen_uniq"] = sum(1 for ph in uniq if ph in done_set)
    tot["pct"] = round(tot["gen_uniq"] * 100 / tot["sp_uniq"]) if tot["sp_uniq"] else 0
    # thẻ CẦN XỬ LÝ nổi lên đầu mỗi nhóm, thẻ 'đã xem ở nơi khác' xuống cuối
    _rank = {"relech": 0, "nogen": 1, "dang": 2, "chosync": 3, "xong": 4}
    for w in list(waves.values()) + list(waves_off.values()):
        w["pct"] = round(w["gen"] * 100 / w["total"]) if w["total"] else 0
        w["cols"].sort(key=lambda c: (c["all_seen"], _rank.get(c["flt"], 9), -c["so_sp"]))
        w["need"] = sum(1 for c in w["cols"] if c["flt"] in ("relech", "nogen"))
    n_std = len(done_set)
    n_in = sum(1 for g in groups if g.get("in_scope", True))
    resp = make_response(render_template("thumbs.html", active="thumbs", waves=waves,
                                         waves_off=waves_off, tot=tot, n_std=n_std,
                                         n_col=n_in))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


# Chia SP trong 1 collection thành các nhóm con cho dễ duyệt.
# Rule khớp theo THỨ TỰ (con đầu tiên khớp thì lấy) -> đặt nhóm hẹp lên trước.
# Collection không có rule ở đây thì trang render phẳng như cũ.
GROUP_RULES = {
    "tan-nhiet": [
        ("Tản zin (stock CPU)", r"\bstock\b|\bzin\b"),
        ("Tản nước AIO",        r"\baio\b|nước|nuoc"),
        ("Tản khí",             r"khí|\bkhi\b"),
    ],
}


def _group_items(col_handle, items, gstatus=None):
    """[{name, slug, items, n_sp, n_img, status, at}] theo thứ tự rule; None nếu chưa có rule."""
    rules = GROUP_RULES.get(col_handle)
    if not rules:
        return None
    gstatus = gstatus or {}
    buckets = {name: [] for name, _ in rules}
    buckets["Khác"] = []
    for it in items:
        text = (it.get("title") or it.get("handle") or "")
        for name, pat in rules:
            if re.search(pat, text, re.IGNORECASE):
                buckets[name].append(it)
                break
        else:
            buckets["Khác"].append(it)
    out = []
    for name in [n for n, _ in rules] + ["Khác"]:
        grp = buckets[name]
        if not grp:
            continue
        slug = _group_slug(name)
        g = gstatus.get(slug) or {}
        out.append({"name": name, "slug": slug, "items": grp,
                    "n_sp": len(grp),
                    "n_img": sum(len(x["imgs"]) for x in grp),
                    "status": g.get("status", ""), "at": g.get("at", "")})
    return out


def _group_slug(name):
    return re.sub(r"[^a-z0-9]+", "-", _strip_accents(name).lower()).strip("-")


def _strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _old_cond_handles():
    return _memo("old_cond", _old_cond_handles_raw)


def _old_cond_handles_raw():
    """Handle SP hàng CŨ / qua-sử-dụng (condition_kind cu/qsd) — ẩn khỏi /thumbs."""
    try:
        import db as _db
        conn = _db.get_conn()
        rows = conn.execute(
            "SELECT handle FROM product_spec_index WHERE condition_kind IN ('cu','qsd')"
        ).fetchall()
        conn.close()
        return {r["handle"] for r in rows if r["handle"]}
    except Exception:  # noqa: BLE001
        return set()


def _product_types():
    return _memo("product_types", _product_types_raw)


def _product_types_raw():
    """handle -> product_type (từ DB) để lọc collection theo loại SP."""
    try:
        import db as _db
        conn = _db.get_conn()
        rows = conn.execute("SELECT handle, product_type FROM product_spec_index").fetchall()
        conn.close()
        return {r["handle"]: r["product_type"] for r in rows if r["handle"]}
    except Exception:  # noqa: BLE001
        return {}


# Collection chỉ hiện đúng loại SP (bỏ SP smart-rule vơ nhầm: laptop/PC lẫn trong vga…).
COLLECTION_TYPE_FILTER = {"vga-nvidia": {"VGA"}}

# Loại SP ẨN toàn cục khỏi /thumbs (không chuẩn hoá) — combo PC dựng sẵn, mình không chỉnh.
HIDE_PRODUCT_TYPES = {"COMBO PC"}


def _collection_items(handle):
    """(items, missing, n_img) — SP trong collection theo thứ tự collection, kèm ảnh chuẩn local.

    Bỏ hàng CŨ (condition_kind cu/qsd) khỏi lưới — chỉ chuẩn hoá hàng đang bán mới."""
    items, missing = [], []
    n_img = 0
    old_cond = _old_cond_handles()
    allow_types = COLLECTION_TYPE_FILTER.get(handle)
    ptypes = _product_types()          # luôn nạp: cần cho lọc combo PC toàn cục
    primary = _primary_map()           # SP -> collection chính
    synced_set = _load_synced()        # SP đã đẩy ảnh lên live
    if handle == UNGROUPED:
        # nhóm SP không thuộc collection nào trên menu live → lấy thẳng từ kho SP
        import db as _db
        conn = _db.get_conn()
        rows = conn.execute("""SELECT handle, title, published, haravan_id FROM product_spec_index
            WHERE condition_kind='new' AND COALESCE(is_service,0)=0 AND published=1
              AND product_type != 'COMBO PC'
              AND haravan_id NOT IN (SELECT haravan_id FROM spec_group_products)
            ORDER BY title""").fetchall()
        conn.close()
        for r in rows:
            ph = r["handle"]
            idxs = _sp_images(ph, "std")
            if idxs or (THUMB_ROOT / "std" / ph).exists():
                items.append({"handle": ph, "title": r["title"], "imgs": idxs, "seen_at": None,
                              "live": [], "n_live": 0, "pub": bool(r["published"]),
                              "pid": r["haravan_id"], "synced": ph in synced_set})
                n_img += len(idxs)
            else:
                missing.append({"handle": ph, "title": r["title"]})
        return items, missing, n_img
    # 📦 NGĂN MẸ chỉ chứa SP KHÔNG thuộc ngăn con nào (gán ở scan_menu). Trang chi tiết
    # phải hiện đúng bấy nhiêu, không thì thẻ ngoài ghi 28 SP mà bấm vào ra 297 SP.
    _only = None
    _g = next((x for x in _menu_groups() if x["handle"] == handle), None)
    if _g and str(_g.get("root", "")).startswith("📦"):
        _only = set(_g["sp"])

    cid = _collections().get(handle)
    if cid:
        # vẽ trang -> được phép dùng cache 90s (sync vẫn lấy tươi, xem _products_in)
        for p in _products_in(cid, use_cache=True):
            ph = p.get("handle")
            if _only is not None and ph not in _only:
                continue               # ngăn mẹ: chỉ SP được gán cho nó
            if ph in old_cond:
                continue               # ẩn hàng cũ khỏi /thumbs
            if p.get("published_at") is None:
                continue               # ẩn SP unpublished (đã ẩn khỏi cửa hàng)
            t = ptypes.get(ph)
            if t in HIDE_PRODUCT_TYPES:
                continue               # ẩn combo PC toàn cục (mình không chỉnh PC)
            if allow_types and t and t not in allow_types:
                continue               # collection này chỉ hiện đúng loại (bỏ laptop/PC lẫn)
            # SP có collection chính KHÁC collection đang xem -> đánh dấu 'đã xem ở đó'
            prim = primary.get(ph)
            seen_at = prim if (prim and prim != handle) else None
            idxs = _sp_images(ph, "std")
            live_src = [im.get("src") for im in (p.get("images") or []) if im.get("src")]
            # 🔧 27/7/2026 (vợ báo): thỉnh thoảng SP MỚI hiện 0 ảnh dù Haravan CÓ ảnh.
            # /products.json?collection_id=... đôi lúc trả images rỗng cho SP vừa thêm
            # (index collection chưa kịp gắn ảnh). Không có ảnh chuẩn + không có ảnh live
            # => SP bị đẩy sang danh sách "thiếu ảnh" và biến mất khỏi lưới.
            # → Hỏi lại TỪNG SP đó cho chắc, chỉ tốn 1 request cho ca hiếm.
            if not idxs and not live_src and p.get("id"):
                try:
                    _full = hc.get_product(p["id"])
                    live_src = [im.get("src") for im in (_full.get("images") or [])
                                if im.get("src")]
                except Exception:  # noqa: BLE001
                    pass
            # SP đang ẨN → trang bán hàng trả 404, phải mở bằng link ADMIN (bẫy 22/7)
            base = {"handle": ph, "title": p.get("title"), "seen_at": seen_at,
                    "live": live_src, "n_live": len(live_src),
                    "pub": bool(p.get("published_at")), "pid": p.get("id"),
                    # 27/7/2026 (vợ chốt): SP đã đẩy live rồi -> mặc định ẨN cho gọn,
                    # để chỉ còn SP MỚI / chưa đẩy trước mắt.
                    "synced": ph in synced_set,
                    # ⚠️ SP CÒN VIỆC (có ảnh chuẩn mà chưa đẩy) thì KHÔNG BAO GIỜ ẩn,
                    # kể cả khi 'nhà' của nó ở collection khác — nếu không thì thẻ ngoài
                    # báo "còn 1 SP chưa sync" mà bấm vào lại không thấy con nào (vợ báo 27/7).
                    "pending": (ph not in synced_set) and (THUMB_ROOT / "std" / ph).exists()}
            if idxs:
                items.append({**base, "imgs": idxs})
                n_img += len(idxs)
            elif live_src or (THUMB_ROOT / "std" / ph).exists():
                # CHƯA chuẩn hoá (hoặc vợ đã xoá hết ảnh chuẩn) — vẫn có ảnh trên live.
                # Bẫy 22/7: trước đây chỉ ghi "0 ảnh" làm tưởng SP không có ảnh nào.
                items.append({**base, "imgs": []})
            else:
                missing.append({"handle": ph, "title": p.get("title")})
    return items, missing, n_img


def thumbs_collection(handle):
    g = next((x for x in _menu_groups() if x["handle"] == handle), None)
    row = ({"handle": handle, "nhom": g["root"], "so_sp": len(g["sp"]),
            "title": g["title"], "parent": g["parent"]} if g else None)
    wave = g["root"] if g else ""
    # contact sheet đặt tên theo wave CŨ (W1__handle__p1.jpg) → tìm theo handle, bỏ tiền tố
    cdir = THUMB_ROOT / "_contact"
    sheets = sorted(p.name for p in cdir.glob(f"*__{handle}__p*.jpg")) if cdir.exists() else []
    items, missing, n_img = _collection_items(handle)
    # SP còn việc (chưa đẩy) luôn hiện -> không tính vào 2 nhóm bị ẩn
    n_seen = sum(1 for it in items if it.get("seen_at") and not it.get("pending"))
    # SP đã đẩy live (và KHÔNG phải loại "đã xem ở nơi khác" — cái đó đã có ô riêng)
    n_synced = sum(1 for it in items if it.get("synced") and not it.get("seen_at"))
    n_moi = sum(1 for it in items if not it.get("synced"))
    # Chỉ ẩn-mặc-định SP đã đẩy khi còn ít nhất 1 SP để xem. Không thì trang trống trơn
    # (vd man-hinh-22-25-inch: 50 SP 'đã xem nơi khác' + 4 SP 'đã đẩy' = 0 SP hiện).
    hide_synced = n_moi > 0
    strow = _load_status().get(handle) or {}
    review = strow.get("status", "")
    groups = _group_items(handle, items, strow.get("groups"))
    n_grp_done = sum(1 for g in groups if g["status"]) if groups else 0

    # ── Chia trang ──
    # Đo 6/8/2026: case-gaming = 274 SP · 976 ảnh · HTML 989 KB. Trình duyệt phải
    # dựng gần 1.000 thẻ <img> một lúc, trang cao 63.000 px nên thao tác gì cũng ì.
    # Collection có NHÓM (tản nhiệt) giữ nguyên 1 trang: nút "Duyệt nhóm" tính theo
    # cả nhóm, cắt ngang trang sẽ làm phạm vi duyệt hiểu sai.
    # Mọi con số ở đầu trang (SP / ảnh / đã đẩy) vẫn tính trên TOÀN collection.
    n_sp_all = len(items)
    xem_het = request.args.get("all") == "1"
    so_trang, trang = 1, 1
    lat = _chia_lat(items)
    if not groups and not xem_het and len(lat) > 1:
        so_trang = len(lat)
        sp_can = request.args.get("sp") or ""
        if sp_can:   # từ ô tìm kiếm: nhảy thẳng tới trang chứa SP đó
            vt = next((i for i, it in enumerate(items) if it["handle"] == sp_can), -1)
            if vt >= 0:
                trang = next(k for k, (a, b) in enumerate(lat, 1) if a <= vt < b)
        else:
            try:
                trang = int(request.args.get("page") or 1)
            except (TypeError, ValueError):
                trang = 1
            trang = max(1, min(trang, so_trang))
        a, b = lat[trang - 1]
        items = items[a:b]
        sp_tu, sp_den = a + 1, b
    else:
        sp_tu, sp_den = (1, n_sp_all) if n_sp_all else (0, 0)

    try:
        shop = hc.load_config().get("shop_domain", "")
    except Exception:  # noqa: BLE001
        shop = ""
    return render_template("thumbs_collection.html", active="thumbs", shop=shop,
                           handle=handle, wave=wave,
                           sheets=sheets, items=items, missing=missing, groups=groups,
                           n_grp_done=n_grp_done,
                           n_img=n_img, n_seen=n_seen, n_synced=n_synced, n_moi=n_moi,
                           hide_synced=hide_synced, row=row, review=review,
                           img_ver=_img_ver,
                           n_sp_all=n_sp_all, trang=trang, so_trang=so_trang,
                           xem_het=xem_het, sp_moi_trang=SP_MOI_TRANG,
                           # dải SP thật của trang này — KHÔNG suy ra từ số SP/trang
                           # được nữa, vì mỗi lát to nhỏ khác nhau (cắt theo số ảnh).
                           sp_tu=sp_tu, sp_den=sp_den,
                           # ở chế độ ?all=1 thì so_trang vẫn = 1, nên cần cờ riêng
                           # để trang biết có nút "quay lại chia trang" hay không
                           co_the_chia=(len(lat) > 1 and not groups),
                           n_anh_trang=sum(len(it.get("imgs") or []) for it in items))


def _lam_ban_nho(goc: Path, dich: Path) -> bool:
    """Sinh bản nhỏ 280px từ ảnh gốc. Trả True nếu tạo được."""
    try:
        from PIL import Image
        dich.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(goc) as im:
            im = im.convert("RGB")
            im.thumbnail((280, 280), Image.LANCZOS)
            tmp = dich.with_suffix(".tmp")
            im.save(tmp, "JPEG", quality=82, optimize=True, progressive=True)
            tmp.replace(dich)
        return True
    except Exception:
        return False


def thumbs_img(kind, name):
    if kind not in KINDS:
        abort(404)
    d = THUMB_ROOT / kind

    if kind == PREVIEW_KIND:
        goc = THUMB_ROOT / "std" / name
        nho = d / name
        if not goc.exists():
            abort(404)
        # ⚠️ Bẫy 5/8/2026: vợ sửa ảnh sau khi đã tạo bản nhỏ → ảnh gốc đổi mà bản nhỏ
        # vẫn đứng yên, trang hiện ảnh CŨ trong khi phóng to ra ảnh MỚI.
        # Nên: bản nhỏ thiếu HOẶC cũ hơn ảnh gốc thì tạo lại; không tạo được thì
        # trả thẳng ảnh gốc — thà nặng còn hơn hiện sai ảnh.
        can_lam = (not nho.exists()) or (nho.stat().st_mtime < goc.stat().st_mtime)
        if can_lam and not _lam_ban_nho(goc, nho):
            d = THUMB_ROOT / "std"
    elif not (d / name).exists():
        abort(404)

    resp = send_from_directory(str(d), name)
    # Đường dẫn có kèm ?v=<giờ sửa> (xem template) nên ảnh đổi là đường dẫn đổi
    # → giữ lâu vẫn an toàn, không còn cảnh trình duyệt bám ảnh cũ.
    resp.headers["Cache-Control"] = "public, max-age=604800"
    return resp


def thumbs_reorder():
    """Lưu thứ tự ảnh mới (kéo-thả) vào manifest. body: {handle, order:[idx,...]}."""
    data = request.get_json(force=True, silent=True) or {}
    handle = data.get("handle", "")
    order = data.get("order")
    d = THUMB_ROOT / "std" / handle
    if not d.exists() or not isinstance(order, list):
        return jsonify(ok=False, error="tham số sai"), 400
    files = {int(p.stem) for p in d.glob("*.jpg") if p.stem.isdigit()}
    order = [int(i) for i in order if int(i) in files]
    man = _manifest(handle) or [{"idx": i} for i in sorted(files)]
    by_idx = {e.get("idx"): e for e in man if isinstance(e, dict)}
    new_man = [by_idx.get(i, {"idx": i}) for i in order]
    new_man += [by_idx[i] for i in by_idx if i not in order and i in files]  # giữ sót
    (d / "manifest.json").write_text(json.dumps(new_man, ensure_ascii=False), encoding="utf-8")
    return jsonify(ok=True, order=[e["idx"] for e in new_man])


def thumbs_redo():
    """Làm lại CHỈ các ảnh ĐANG HIỂN THỊ của 1 SP — KHÔNG xóa nền (cắt mép + căn giữa).
    Giữ nguyên bộ ảnh hiện tại (gồm ảnh đã thêm), thứ tự, ảnh đã xóa. body: {handle}.
    - Ảnh gốc từ Haravan: chuẩn hóa lại từ nguồn gốc (theo image_id).
    - Ảnh tự thêm / không có nguồn: chuẩn hóa lại tại chỗ từ ảnh hiện có."""
    data = request.get_json(force=True, silent=True) or {}
    handle = data.get("handle", "")
    d = THUMB_ROOT / "std" / handle
    if not d.exists():
        return jsonify(ok=False, error="SP chưa có ảnh chuẩn"), 404
    order = _sp_images(handle)   # idx đang hiển thị, theo thứ tự
    man = _manifest(handle) or []
    id_by_idx = {e["idx"]: e.get("image_id") for e in man
                 if isinstance(e, dict) and "idx" in e}
    # map image_id -> src từ Haravan (best-effort, để làm lại từ ảnh gốc)
    src_map = {}
    try:
        prods = hc._request("GET", "/products.json",
                            params={"handle": handle, "limit": 1}).get("products", [])
        if prods:
            for im in prods[0].get("images") or []:
                src_map[im["id"]] = im["src"]
    except Exception:
        pass
    n = 0
    for idx in order:
        fp = d / f"{idx}.jpg"
        iid = id_by_idx.get(idx)
        try:
            if iid and iid in src_map:                       # làm lại từ ảnh gốc Haravan
                raw = urllib.request.urlopen(src_map[iid], timeout=25).read()
                src_img = Image.open(io.BytesIO(raw))
            elif fp.exists():                                # ảnh thêm / không có nguồn -> tại chỗ
                src_img = Image.open(io.BytesIO(fp.read_bytes()))
            else:
                continue
            _standardize_no_rembg(src_img).save(fp, quality=92)
            n += 1
        except Exception:
            continue
    return jsonify(ok=True, n=n, sp=_sp_state(handle))


def thumbs_gen_from_live():
    """TẠO ảnh chuẩn LẦN ĐẦU cho 1 SP từ ảnh đang có trên Haravan. body: {handle}.

    Vì sao cần (vợ hỏi 27/7/2026): /thumbs hiển thị ảnh CHUẨN LOCAL ở `std/<handle>/`,
    không phải ảnh live. SP MỚI tạo (Samsung S32GF, Ryzen 5500GT, RTX 3060…) có ảnh
    trên Haravan nhưng chưa qua bước chuẩn hoá nên `std/` rỗng -> /thumbs báo "chưa gen".
    Trước đây chỉ có script chạy hàng loạt, KHÔNG có cách gen cho 1 SP lẻ trên web.
    """
    data = request.get_json(force=True, silent=True) or {}
    handle = (data.get("handle") or "").strip()
    if not handle:
        return jsonify(ok=False, error="thiếu handle"), 400
    d = THUMB_ROOT / "std" / handle
    if d.exists() and any(d.glob("*.jpg")):
        return jsonify(ok=False, error="SP đã có ảnh chuẩn — dùng nút Làm lại"), 400
    try:
        prods = hc._request("GET", "/products.json",
                            params={"handle": handle, "limit": 1}).get("products", [])
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, error=f"lỗi gọi Haravan: {e}"), 500
    if not prods:
        return jsonify(ok=False, error="không tìm thấy SP trên Haravan"), 404
    imgs = sorted(prods[0].get("images") or [], key=lambda x: x.get("position") or 0)
    if not imgs:
        return jsonify(ok=False, error="SP không có ảnh nào trên Haravan"), 400
    d.mkdir(parents=True, exist_ok=True)
    man, n, errs = [], 0, 0
    for im in imgs:
        try:
            raw = urllib.request.urlopen(im["src"], timeout=30).read()
            _standardize_no_rembg(Image.open(io.BytesIO(raw))).save(d / f"{n}.jpg", quality=92)
            man.append({"idx": n, "image_id": im.get("id"),
                        "position": im.get("position"), "note": "gen-from-live"})
            n += 1
        except Exception:  # noqa: BLE001
            errs += 1
    if not n:
        return jsonify(ok=False, error="tải/chuẩn hoá thất bại toàn bộ"), 500
    (d / "manifest.json").write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")
    return jsonify(ok=True, n=n, errors=errs, sp=_sp_state(handle))


def thumbs_add_image():
    """Chèn NHIỀU ảnh từ máy (Downloads…) vào cuối bộ ảnh 1 SP — chuẩn hóa 1000² không xóa nền.
    multipart: handle + file (1 hoặc nhiều)."""
    handle = request.form.get("handle", "")
    files = request.files.getlist("file")
    if not handle or not files:
        return jsonify(ok=False, error="thiếu handle/ảnh"), 400
    d = THUMB_ROOT / "std" / handle
    d.mkdir(parents=True, exist_ok=True)
    existing = [int(p.stem) for p in d.glob("*.jpg") if p.stem.isdigit()]
    man = _manifest(handle) or [{"idx": i} for i in sorted(existing)]
    nidx = (max(existing) + 1) if existing else 0
    added, errs = [], 0
    for f in files:
        if not f or not f.filename:
            continue
        try:
            std = _standardize_no_rembg(Image.open(io.BytesIO(f.read())))
        except Exception:
            errs += 1
            continue
        std.save(d / f"{nidx}.jpg", quality=92)
        man.append({"idx": nidx, "image_id": None, "position": None,
                    "note": "added-local", "src_name": (f.filename or "")})
        added.append(nidx)
        nidx += 1
    (d / "manifest.json").write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")
    if not added:
        return jsonify(ok=False, error="không ảnh nào hợp lệ"), 400
    return jsonify(ok=True, added=len(added), idxs=added, errors=errs,
                   sp=_sp_state(handle))


def thumbs_paste_front():
    """Dán 1 ảnh từ clipboard (base64) -> chuẩn hoá căn giữa 1000² -> chèn vào ĐẦU SP
    (thành ảnh đại diện). body JSON: {handle, image: 'data:image/...;base64,...'}."""
    data = request.get_json(force=True, silent=True) or {}
    handle = (data.get("handle") or "").strip()
    img_data = data.get("image") or ""
    if not handle or not img_data:
        return jsonify(ok=False, error="thiếu handle hoặc ảnh"), 400
    try:
        if "," in img_data:
            img_data = img_data.split(",", 1)[1]
        raw = base64.b64decode(img_data)
        std = _standardize_no_rembg(Image.open(io.BytesIO(raw)))
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, error="ảnh không đọc được: " + str(e)[:60]), 400
    d = THUMB_ROOT / "std" / handle
    d.mkdir(parents=True, exist_ok=True)
    existing = [int(p.stem) for p in d.glob("*.jpg") if p.stem.isdigit()]
    nidx = (max(existing) + 1) if existing else 0
    std.save(d / f"{nidx}.jpg", quality=92)
    # manifest: chèn entry mới lên ĐẦU -> thành ảnh đại diện (pos 1)
    man = _manifest(handle) or [{"idx": i} for i in sorted(existing)]
    man.insert(0, {"idx": nidx, "image_id": None, "position": None, "note": "pasted-front"})
    (d / "manifest.json").write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")
    return jsonify(ok=True, idx=nidx, n=len(man), sp=_sp_state(handle))


def thumbs_delete_image():
    """Xóa 1 ảnh khỏi bộ ảnh chuẩn của 1 SP. body: {handle, idx}."""
    data = request.get_json(force=True, silent=True) or {}
    handle = data.get("handle", "")
    idx = data.get("idx")
    d = THUMB_ROOT / "std" / handle
    if not d.exists() or idx is None:
        return jsonify(ok=False, error="tham số sai"), 400
    idx = int(idx)
    fp = d / f"{idx}.jpg"
    if fp.exists():
        fp.unlink()
    # Dọn luôn bản nhỏ — trước đây bỏ lại làm rác dần trong _preview/ (bắt được 6/8/2026).
    try:
        (THUMB_ROOT / PREVIEW_KIND / handle / f"{idx}.jpg").unlink(missing_ok=True)
    except OSError:
        pass
    man = _manifest(handle)
    if man is not None:
        man = [e for e in man if not (isinstance(e, dict) and e.get("idx") == idx)]
        (d / "manifest.json").write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")
    return jsonify(ok=True, sp=_sp_state(handle))


def _cleanup_added_from_downloads(collection_handle):
    """Gom file ảnh gốc (vợ thêm từ Downloads) của collection ra khỏi Downloads.
    Tìm theo tên file đã lưu lúc add. Trả số file đã chuyển. KHÔNG đụng std/ (web+sync giữ nguyên)."""
    prod_handles = _collection_map().get(collection_handle) or []
    moved = 0
    for ph in prod_handles:
        man = _manifest(ph)
        if not man:
            continue
        for e in man:
            if not (isinstance(e, dict) and e.get("note") == "added-local"):
                continue
            name = e.get("src_name")
            if not name:
                continue
            src = DOWNLOADS / name
            if not src.exists():
                continue
            dest_dir = ADDED_ARCHIVE / ph
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / name
            try:
                if dest.exists():
                    dest = dest_dir / f"{src.stem}_{e.get('idx')}{src.suffix}"
                src.replace(dest)
                moved += 1
            except Exception:
                pass
    return moved


def thumbs_approve():
    """Duyệt 1 collection (sau khi vợ xem hết SP). body: {handle, value: true/false}.
    Khi duyệt: gom ảnh gốc đã thêm (từ Downloads) sang folder gom."""
    data = request.get_json(force=True, silent=True) or {}
    handle = data.get("handle", "")
    value = data.get("value", True)
    if not handle:
        return jsonify(ok=False, error="thiếu handle"), 400
    st = _load_status()
    moved = 0
    row = st.get(handle) or {}
    groups = row.get("groups")          # trạng thái duyệt từng nhóm — giữ lại khi bỏ duyệt collection
    if value:
        st[handle] = {"status": "da_duyet", "at": _now()}
        moved = _cleanup_added_from_downloads(handle)
    else:
        st.pop(handle, None)
    if groups:
        st.setdefault(handle, {})["groups"] = groups
    _save_status(st)
    return jsonify(ok=True, status=(st.get(handle) or {}).get("status", ""), moved=moved)


def thumbs_approve_group():
    """Duyệt 1 NHÓM con trong collection. body: {handle, slug, value}.
    Duyệt hết các nhóm -> tự duyệt luôn collection (nếu chưa sync)."""
    data = request.get_json(force=True, silent=True) or {}
    handle, slug = data.get("handle", ""), data.get("slug", "")
    value = data.get("value", True)
    if not handle or not slug:
        return jsonify(ok=False, error="thiếu handle/slug"), 400
    rules = GROUP_RULES.get(handle)
    if not rules:
        return jsonify(ok=False, error="collection không chia nhóm"), 400
    valid = {_group_slug(n) for n, _ in rules} | {_group_slug("Khác")}
    if slug not in valid:
        return jsonify(ok=False, error="nhóm không tồn tại"), 400

    st = _load_status()
    row = st.setdefault(handle, {})
    gs = row.setdefault("groups", {})
    if value:
        gs[slug] = {"status": "da_duyet", "at": _now()}
    else:
        gs.pop(slug, None)
    if not gs:
        row.pop("groups", None)

    # đủ nhóm -> duyệt cả collection (không đè trạng thái đã sync)
    auto, moved = False, 0
    items, _, _ = _collection_items(handle)
    n_real = len(_group_items(handle, items) or [])
    if value and n_real and len(gs) >= n_real and row.get("status") not in ("da_duyet", "da_sync"):
        row["status"], row["at"] = "da_duyet", _now()
        moved = _cleanup_added_from_downloads(handle)
        auto = True
    if not value and row.get("status") == "da_duyet":
        row.pop("status", None); row.pop("at", None)     # bỏ 1 nhóm -> collection không còn "duyệt đủ"
    if not row:
        st.pop(handle, None)
    _save_status(st)
    return jsonify(ok=True, slug=slug, status=(gs.get(slug) or {}).get("status", ""),
                   n_done=len(gs), n_groups=n_real, col_status=row.get("status", ""),
                   auto_approved=auto, moved=moved)


def _sync_one_product(handle):
    """Thay ảnh 1 SP trên Haravan bằng bộ ảnh chuẩn local — GIỮ ảnh local (chỉ đọc).
    Backup ảnh gốc -> up ảnh chuẩn -> xóa ảnh gốc -> set vị trí 1..n."""
    d = THUMB_ROOT / "std" / handle
    order = _sp_images(handle)
    if not order:
        return {"ok": False, "error": "không có ảnh chuẩn local"}
    prods = hc._request("GET", "/products.json",
                        params={"handle": handle, "limit": 1}).get("products", [])
    if not prods:
        return {"ok": False, "error": "không tìm thấy SP"}
    pid = prods[0]["id"]
    imgs = sorted(prods[0].get("images") or [], key=lambda x: x.get("position") or 0)
    # backup ảnh gốc (local)
    bdir = BACKUP_ORIG / handle
    bdir.mkdir(parents=True, exist_ok=True)
    meta = []
    for im in imgs:
        try:
            raw = urllib.request.urlopen(im["src"], timeout=30).read()
            fn = f"{im.get('position') or 0}_{im['id']}.jpg"
            (bdir / fn).write_bytes(raw)
            meta.append({"id": im["id"], "position": im.get("position"),
                         "src": im["src"], "file": fn})
        except Exception:
            pass
    (bdir / "orig_manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    # up ảnh chuẩn (đọc local, KHÔNG xóa local) — có retry, đảm bảo đủ bộ
    new_ids = []
    for i, idx in enumerate(order):
        iid = None
        for attempt in range(3):
            try:
                b64 = base64.b64encode((d / f"{idx}.jpg").read_bytes()).decode()
                img = hc.add_product_image(pid, b64, filename=f"{handle}-{i + 1}.jpg")
                if img.get("id"):
                    iid = img["id"]
                    break
            except Exception:
                pass
            time.sleep(1.0)
        new_ids.append(iid)
        time.sleep(0.25)
    # GATE: chỉ xóa ảnh gốc khi up ĐỦ bộ (up trước, xóa sau) — tránh mất ảnh mà vẫn báo synced
    if not all(new_ids):
        # dọn ảnh mới up dở để không để lại rác
        for iid in new_ids:
            if iid:
                try:
                    hc._request("DELETE", f"/products/{pid}/images/{iid}.json")
                except Exception:
                    pass
        return {"ok": False, "error": "up thiếu ảnh %d/%d (giữ nguyên ảnh gốc)"
                % (sum(1 for x in new_ids if x), len(order))}
    # xóa ảnh gốc
    for im in imgs:
        try:
            hc._request("DELETE", f"/products/{pid}/images/{im['id']}.json")
            time.sleep(0.2)
        except Exception:
            pass
    # set vị trí 1..n
    for i, iid in enumerate(new_ids):
        if iid:
            try:
                hc._request("PUT", f"/products/{pid}/images/{iid}.json",
                            payload={"image": {"id": iid, "position": i + 1}})
                time.sleep(0.15)
            except Exception:
                pass
    return {"ok": True, "n": len(new_ids)}


def _n_live(handle):
    """Số ảnh SP trên Haravan. -1 = không đọc được (coi như cần sync)."""
    try:
        prods = hc._request("GET", "/products.json",
                            params={"handle": handle, "limit": 1}).get("products", [])
        if not prods:
            return -1
        return len(prods[0].get("images") or [])
    except Exception:
        return -1


def _sp_list_of(coll_handle, cmap):
    """Danh sách SP của 1 collection, lấy từ HARAVAN (nguồn thật) hợp với bản đồ local.

    Bản đồ local `thumb_collection_map.json` là file tĩnh nên hay STALE: SP mới thêm trên
    Haravan không có trong đó => sync bỏ sót ÂM THẦM mà vẫn báo "x/x OK" (bẫy 14/7/2026,
    sót đúng con fan-case-vsp poster). Trả về (danh sách SP, danh sách SP local thiếu).
    """
    local = list(cmap.get(coll_handle, []))
    try:
        cid = _collections().get(coll_handle)
        live = [p["handle"] for p in _products_in(cid)] if cid else []
    except Exception:
        live = []          # mạng lỗi -> lùi về bản đồ local, KHÔNG chặn sync
    if not live:
        return local, []
    missing = [h for h in live if h not in set(local)]
    return local + missing, missing


def _sync_worker(coll_list):
    cmap = _collection_map()
    synced = _load_synced()
    # gom SP (dedup). SP đã synced chỉ được bỏ qua khi local == live: nếu vợ chèn thêm
    # ảnh ở /thumbs sau lần sync trước thì ảnh đó không bao giờ lên live mà collection
    # vẫn bị đánh dấu da_sync (bẫy dedup 6/7/2026).
    prod_order, seen, relech, missing_all = [], set(), [], []
    for c in coll_list:
        sp_list, missing = _sp_list_of(c, cmap)
        missing_all += [{"collection": c, "handle": h} for h in missing]
        for ph in sp_list:
            if ph in seen:
                continue
            seen.add(ph)
            if not (THUMB_ROOT / "std" / ph).exists():
                continue          # chưa có ảnh chuẩn local -> không có gì để đẩy
            if ph in synced:
                nl, nv = len(_sp_images(ph)), _n_live(ph)
                if nl == nv:
                    continue
                relech.append((ph, nl, nv))
            prod_order.append(ph)
    failed = set()
    msgs = []
    if relech:
        msgs.append(f"⚠️ {len(relech)} SP đã synced nhưng lệch local vs live → sync lại")
    if missing_all:
        msgs.append(f"⚠️ {len(missing_all)} SP có trên Haravan nhưng THIẾU trong bản đồ local "
                    f"(đã tự thêm vào lượt sync này) → chạy lại build_collection_map.py")
    SYNC_STATE.update(running=True, finished=False, total=len(prod_order),
                      done=0, ok=0, fail=0, current="",
                      msg=" · ".join(msgs),
                      relech=[{"handle": p, "local": nl, "live": nv} for p, nl, nv in relech],
                      missing_local=missing_all)
    for ph in prod_order:
        SYNC_STATE["current"] = ph
        try:
            r = _sync_one_product(ph)
            if r.get("ok"):
                SYNC_STATE["ok"] += 1
                synced.add(ph)
                _save_synced(synced)
            else:
                SYNC_STATE["fail"] += 1
                failed.add(ph)
        except Exception:
            SYNC_STATE["fail"] += 1
            failed.add(ph)
        SYNC_STATE["done"] += 1
    # đánh dấu collection da_sync nếu KHÔNG có SP nào của nó lỗi
    # (xét theo danh sách SP THẬT trên Haravan, không theo bản đồ local stale)
    st = _load_status()
    for c in coll_list:
        phs, _ = _sp_list_of(c, cmap)
        if any(p in failed for p in phs):
            continue
        if (st.get(c) or {}).get("status") in ("da_duyet", "da_sync"):
            st[c] = {"status": "da_sync", "at": _now()}
    _save_status(st)
    tail = ""
    if SYNC_STATE.get("missing_local"):
        tail = (f" · ⚠️ {len(SYNC_STATE['missing_local'])} SP thiếu trong bản đồ local "
                f"(đã sync bù) → chạy lại build_collection_map.py")
    # sync vừa đổi ảnh trên Haravan -> bỏ cache để trang vẽ lại bằng dữ liệu mới
    # (xoá cả bản trên đĩa, không thì restart lại nạp về dữ liệu cũ)
    _PROD_CACHE.clear()
    _PROD_REFRESHING.clear()
    try:
        _PROD_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    SYNC_STATE.update(running=False, finished=True, current="",
                      msg=f"Xong: {SYNC_STATE['ok']} SP ok, {SYNC_STATE['fail']} lỗi{tail}")


def thumbs_sync():
    """Sync TẤT CẢ collection đã duyệt lên live (chạy nền). Dedup theo SP, giữ ảnh local."""
    with SYNC_LOCK:
        if SYNC_STATE["running"]:
            return jsonify(ok=False, error="Đang sync, đợi xong đã"), 409
        # Sync KHÔNG được chạy trên bản đồ nhớ tạm — SP vừa thêm vào collection
        # 2 phút trước sẽ bị bỏ sót (bẫy thumb_collection_map.json 14/7/2026).
        _memo_clear()
        st = _load_status()
        coll = [h for h, v in st.items() if (v or {}).get("status") == "da_duyet"]
        # Thêm nhóm đã đóng cờ 'da_sync' nhưng SAU ĐÓ có SP/ảnh mới chưa đẩy —
        # trước đây những nhóm này bị bỏ quên vĩnh viễn (bẫy 22/7/2026).
        synced = _load_synced()
        cmap = _collection_map()
        for h, v in st.items():
            if (v or {}).get("status") != "da_sync":
                continue
            if any((THUMB_ROOT / "std" / ph).exists() and ph not in synced
                   for ph in cmap.get(h, [])):
                coll.append(h)
        if not coll:
            return jsonify(ok=False, error="Chưa có collection nào đã duyệt"), 400
        t = threading.Thread(target=_sync_worker, args=(coll,), daemon=True)
        t.start()
    return jsonify(ok=True, started=True, collections=len(coll))


def thumbs_sync_status():
    return jsonify(SYNC_STATE)


def _norm(s):
    """Bỏ dấu tiếng Việt + thường hóa + coi '-' như khoảng trắng (để tìm gần đúng)."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower().replace("-", " ").replace("đ", "d")


def _titles():
    p = NOXOUT / "thumb_product_titles.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def thumbs_search():
    """Tìm SP theo tên. SP ở nhiều collection -> mỗi collection 1 dòng kết quả."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify(results=[])
    toks = [t for t in _norm(q).split() if t]
    titles = _titles()
    cmap = _collection_map()
    done = _std_done()
    coll_by_prod = {}
    for c, phs in cmap.items():
        for ph in phs:
            coll_by_prod.setdefault(ph, []).append(c)
    res = []
    for h, title in titles.items():
        if h not in done:
            continue
        hay = _norm(title) + " " + _norm(h)
        if all(t in hay for t in toks):
            for c in sorted(coll_by_prod.get(h, [])):
                res.append({"title": title, "handle": h, "collection": c})
        if len(res) > 300:
            break
    res.sort(key=lambda r: (r["title"], r["collection"]))
    return jsonify(results=res[:80])


def register(app):
    app.add_url_rule("/thumbs/sync", "thumbs_sync", thumbs_sync, methods=["POST"])
    app.add_url_rule("/thumbs/sync-status", "thumbs_sync_status", thumbs_sync_status)
    app.add_url_rule("/thumbs/search", "thumbs_search", thumbs_search)
    app.add_url_rule("/thumbs", "thumbs_page", thumbs_page)
    app.add_url_rule("/thumbs/c/<handle>", "thumbs_collection", thumbs_collection)
    app.add_url_rule("/thumbs/img/<kind>/<path:name>", "thumbs_img", thumbs_img)
    app.add_url_rule("/thumbs/reorder", "thumbs_reorder", thumbs_reorder, methods=["POST"])
    app.add_url_rule("/thumbs/redo", "thumbs_redo", thumbs_redo, methods=["POST"])
    app.add_url_rule("/thumbs/approve", "thumbs_approve", thumbs_approve, methods=["POST"])
    app.add_url_rule("/thumbs/approve-group", "thumbs_approve_group", thumbs_approve_group,
                     methods=["POST"])
    app.add_url_rule("/thumbs/gen-from-live", "thumbs_gen_from_live", thumbs_gen_from_live,
                     methods=["POST"])
    app.add_url_rule("/thumbs/add-image", "thumbs_add_image", thumbs_add_image, methods=["POST"])
    app.add_url_rule("/thumbs/paste", "thumbs_paste_front", thumbs_paste_front, methods=["POST"])
    app.add_url_rule("/thumbs/delete-image", "thumbs_delete_image", thumbs_delete_image, methods=["POST"])
