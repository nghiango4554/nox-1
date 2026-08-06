"""Routes: Thông số SP — tab quản lý khối thông số kỹ thuật trong mô tả sản phẩm.

Trang:
- /spec                     danh sách nhóm theo collection ĐANG HIỆN trên menu live (chỉ nhánh lá)
- /spec/g/<handle>          danh sách SP trong 1 nhóm (đọc DB, không gọi Haravan → load nhanh)
- /spec/p/<id>              sửa khối thông số + mô tả, đổi qua lại bảng ↔ khối trích dẫn, duyệt lên live

API:
- POST /spec/scan           quét lại SP + menu từ Haravan/live
- GET  /spec/api/search     tìm SP theo tên/handle/id
- POST /spec/p/<id>/convert đổi dạng khối spec (giữ nguyên dữ liệu)
- POST /spec/p/<id>/publish lưu + đẩy lên Haravan + đọc lại xác nhận
"""

import json
import threading
import traceback

from flask import jsonify, render_template, request

import spec_index as si

_SCAN = {"running": False, "log": [], "result": None, "error": None}


def _scan_worker(what: str):
    _SCAN.update(running=True, log=[], result=None, error=None)

    def log(msg):
        _SCAN["log"].append(str(msg))
        del _SCAN["log"][:-40]

    try:
        res = {}
        if what in ("all", "products"):
            log("Đang kéo sản phẩm live từ Haravan…")
            res["products"] = si.scan_products(log)
            log(f"Xong sản phẩm: {res['products']}")
        if what in ("all", "menu"):
            log("Đang bóc collection từ menu live sintech.vn…")
            res["menu"] = si.scan_menu(log)
            log(f"Xong menu: {res['menu']['leaves']} nhóm")
        _SCAN["result"] = res
    except Exception as e:  # noqa: BLE001
        _SCAN["error"] = f"{e}\n{traceback.format_exc()[-600:]}"
    finally:
        _SCAN["running"] = False


# ──────────────────────────── trang ────────────────────────────

def spec_index_page():
    si.init_schema()
    ov = si.groups_overview()
    roots, seen = [], {}
    for g in ov["groups"]:
        r = g["root"] or "Khác"
        if r not in seen:
            seen[r] = {"root": r, "groups": [], "product_count": 0, "new_count": 0, "ok_count": 0}
            roots.append(seen[r])
        seen[r]["groups"].append(g)
        seen[r]["product_count"] += g["product_count"]
        seen[r]["new_count"] += g["new_count"]
        seen[r]["ok_count"] += g["ok_count"]
    approvals = si.approved_collections()
    for g in ov["groups"]:
        g["approved_at"] = (approvals.get(g["handle"]) or "").replace("T", " ")[:16]
    ungrouped = si.products_of_group("__ungrouped__")
    fmt_rows = [{"code": k, "label": si.FMT_LABEL.get(k, (k, ""))[0],
                 "verdict": si.FMT_LABEL.get(k, (k, ""))[1], "count": v}
                for k, v in sorted(ov["fmt_stats"].items(), key=lambda x: -x[1]) if k]
    ok_total = ov["fmt_stats"].get(si.FMT_A, 0)
    new_total = sum(v for k, v in ov["fmt_stats"].items() if k)
    return render_template(
        "spec_index.html", roots=roots, ungrouped_count=len(ungrouped),
        fmt_rows=fmt_rows, ok_total=ok_total, new_total=new_total,
        total=ov["total"], service=ov.get("service", 0),
        scanned_at=ov["scanned_at"], scan=_SCAN)


def spec_group_page(handle):
    tag = request.args.get("tag", "")
    show_all = request.args.get("all") == "1"
    rows = si.products_of_group(handle, tag, only_new=not show_all)
    if handle == "__ungrouped__":
        title, parent = "SP chưa phân loại", "Không thuộc collection nào trên menu"
    else:
        import db
        conn = db.get_conn()
        r = conn.execute("SELECT title,parent,root FROM spec_menu_collections "
                         "WHERE handle=? AND tag_filter=?", (handle, tag)).fetchone()
        conn.close()
        title = r["title"] if r else handle
        parent = f"{r['root']} › {r['parent']}" if r else ""
    for x in rows:
        lab, verdict = si.FMT_LABEL.get(x["spec_format"], ("—", ""))
        if x.get("is_service"):          # trang dịch vụ/sửa chữa: ngoài phạm vi
            lab, verdict = "Trang dịch vụ / sửa chữa", "KHÔNG ÁP DỤNG"
        x["fmt_label"], x["verdict"] = lab, verdict
    return render_template("spec_group.html", rows=rows, title=title, parent=parent,
                           handle=handle, tag=tag, show_all=show_all)


# ⚡ 6/8/2026 — chia trang View nhanh.
# Đo trước khi sửa: `vga-nvidia` HTML **5.041 KB / 15.814 dòng bảng**, `case-gaming`
# 4.803 KB / 14.486 dòng — 35/175 nhóm vượt 500 KB. Server trả nhanh (0,7s), cái ì
# nằm ở chỗ trình duyệt phải dựng 15.000 dòng một lúc.
# Cắt theo SỐ DÒNG BẢNG chứ không theo số SP: mỗi SP nặng nhẹ rất khác nhau
# (SP ít spec 10 dòng, SP nhiều spec 120 dòng), cắt theo đầu SP thì trang vẫn phình.
# Luôn lấy ÍT NHẤT 1 SP mỗi trang để SP siêu nặng không làm trang rỗng.
DONG_MOI_TRANG = 1200


def _chia_theo_dong(rows, budget=DONG_MOI_TRANG):
    """Gom rows thành các trang sao cho mỗi trang ≲ budget dòng bảng.

    Trả list các (đầu, cuối) — cắt theo lát nên thứ tự SP giữ nguyên tuyệt đối.
    """
    trang, dau, dem = [], 0, 0
    for i, r in enumerate(rows):
        w = len(r.get("aligned") or []) + len(r.get("merged") or [])
        if dem and dem + w > budget:        # `dem and` = luôn nhận SP đầu tiên
            trang.append((dau, i))
            dau, dem = i, 0
        dem += w
    if dau < len(rows) or not trang:
        trang.append((dau, len(rows)))
    return trang


def spec_quick_page(handle):
    """View nhanh: 1 trang duyệt cả collection, mỗi SP 3 mẫu spec cạnh nhau."""
    tag = request.args.get("tag", "")
    rows = si.quick_rows(handle, tag)
    only = request.args.get("only", "")          # "" | doi | moi | chua
    if only == "doi":
        rows = [r for r in rows if r["n_doi"]]
    elif only == "moi":
        rows = [r for r in rows if r["n_moi"]]
    elif only == "chua":
        rows = [r for r in rows if not r["saved_at"] and not r["excluded"]]
    if handle == "__ungrouped__":
        title, parent = "SP chưa phân loại", ""
    else:
        import db
        conn = db.get_conn()
        r = conn.execute("SELECT title,parent,root FROM spec_menu_collections "
                         "WHERE handle=? AND tag_filter=?", (handle, tag)).fetchone()
        conn.close()
        title = r["title"] if r else handle
        parent = f"{r['root']} › {r['parent']}" if r else ""
    # Mọi con số ở thanh đầu trang vẫn tính trên TOÀN BỘ nhóm, không phải trang hiện tại.
    stat = {
        "n": len(rows),
        "co_web": sum(1 for r in rows if r["n_web"]),
        "doi": sum(1 for r in rows if r["n_doi"]),
        "moi": sum(1 for r in rows if r["n_moi"]),
        "saved": sum(1 for r in rows if r["saved_at"]),
        "excluded": sum(1 for r in rows if r["excluded"]),
    }

    xem_het = request.args.get("all") == "1"
    lat = _chia_theo_dong(rows)
    so_trang, trang = len(lat), 1
    if not xem_het and so_trang > 1:
        sp_can = request.args.get("sp") or ""
        if sp_can:      # từ link neo: nhảy thẳng tới trang chứa SP đó
            vt = next((i for i, r in enumerate(rows)
                       if str(r.get("haravan_id")) == sp_can or r.get("handle") == sp_can), -1)
            if vt >= 0:
                trang = next(k for k, (a, b) in enumerate(lat, 1) if a <= vt < b)
        else:
            try:
                trang = int(request.args.get("page") or 1)
            except (TypeError, ValueError):
                trang = 1
            trang = max(1, min(trang, so_trang))
        a, b = lat[trang - 1]
        rows = rows[a:b]

    return render_template("spec_quick.html", rows=rows, title=title, parent=parent,
                           handle=handle, tag=tag, stat=stat, only=only,
                           trang=trang, so_trang=so_trang, xem_het=xem_het,
                           n_sp_trang=len(rows))


def spec_quick_save(pid):
    data = request.get_json(silent=True) or {}
    rows = data.get("rows") or []
    if not isinstance(rows, list):
        return jsonify({"ok": False, "error": "rows phải là danh sách"}), 400
    pairs = []
    for x in rows:
        if isinstance(x, dict):
            pairs.append([x.get("k", ""), x.get("v", "")])
        elif isinstance(x, (list, tuple)) and len(x) >= 2:
            pairs.append([x[0], x[1]])
    return jsonify(si.quick_save(pid, pairs))


def spec_quick_exclude(pid):
    data = request.get_json(silent=True) or {}
    return jsonify(si.quick_exclude(pid, bool(data.get("on", True))))


def spec_product_page(pid):
    p = si.get_product(pid)
    if not p:
        return render_template("spec_edit.html", missing=True, pid=pid), 404
    groups = si.block_to_groups(p["spec_block_html"] or "")
    if not groups and p["spec_pairs_json"]:
        pairs = json.loads(p["spec_pairs_json"])
        if pairs:
            groups = [{"name": "Thông số kỹ thuật", "rows": pairs}]
    lab, verdict = si.FMT_LABEL.get(p["spec_format"], ("—", ""))
    return render_template(
        "spec_edit.html", p=p, groups=groups, missing=False,
        issues=json.loads(p["issues_json"] or "[]"),
        fmt_label=lab, verdict=verdict,
        block_bq=si.build_blockquote(groups), block_tb=si.build_table(groups))


# ──────────────────────────── API ────────────────────────────

def spec_scan():
    if _SCAN["running"]:
        return jsonify({"ok": False, "error": "Đang quét rồi"}), 409
    what = (request.json or {}).get("what", "all")
    threading.Thread(target=_scan_worker, args=(what,), daemon=True).start()
    return jsonify({"ok": True})


def spec_scan_status():
    return jsonify(_SCAN)


def spec_api_search():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"items": []})
    items = si.search_products(q)
    for x in items:
        x["fmt_label"], x["verdict"] = si.FMT_LABEL.get(x["spec_format"], ("—", ""))
    return jsonify({"items": items})


def spec_api_log():
    """Nhật ký sync, phân trang 10 dòng. actor=vo (vợ tự sync) | nox (anh sync)."""
    actor = request.args.get("actor") or "vo"
    page = max(1, int(request.args.get("page") or 1))
    d = si.list_log(actor=actor, page=page, per=10)
    for r in d["rows"]:
        r["when"] = (r["created_at"] or "").replace("T", " ")[:16]
        r["is_collection"] = r["kind"] == "collection"
    return jsonify(d)


def spec_api_errors():
    """Tab đỏ 'SP sai spec': danh sách SP có chỉ tiêu sai (đã đối chiếu trang hãng)."""
    page = max(1, int(request.args.get("page") or 1))
    d = si.list_error_notes(page=page, per=10)
    for r in d["rows"]:
        r["when"] = (r["created_at"] or "").replace("T", " ")[:16]
    return jsonify(d)


def spec_error_add(pid):
    """Thêm/ghi 1 chỉ tiêu sai cho SP (từ trang duyệt hoặc script nạp)."""
    d = request.get_json(silent=True) or {}
    eid = si.add_error_note(
        pid, d.get("label", ""), d.get("wrong", ""), d.get("correct", ""),
        source=d.get("source", ""), note=d.get("note", ""))
    return jsonify({"ok": True, "id": eid})


def spec_approve_collection(handle):
    # Bẫy: request.json ném 415 khi client không gửi Content-Type JSON → dùng silent
    tag = request.args.get("tag", "") or (request.get_json(silent=True) or {}).get("tag", "")
    res = si.approve_collection(handle, tag, actor="vo")
    return jsonify(res)


def spec_sources(pid):
    """Bảng đối chiếu: các trang đã lấy data spec (tên · link · spec lấy được)."""
    return jsonify({"rows": si.get_research_sources(pid)})


def spec_find_sources(pid):
    """Chạy research NGAY cho 1 SP để soi nguồn — KHÔNG ghi gì lên Haravan."""
    import spec_research as sr
    p = si.get_product(pid)
    if not p:
        return jsonify({"ok": False, "error": "không thấy SP"}), 404
    res = sr.research(p["title"], p["product_type"] or "")
    si.save_research_sources(pid, res)
    return jsonify({"ok": True, "found": len(res.get("candidates") or []),
                    "skipped": len(res.get("rejected") or []),
                    "reason": res.get("reason", ""),
                    "rows": si.get_research_sources(pid)})


def spec_convert(pid):
    """Đổi dạng khối spec mà KHÔNG mất dữ liệu: HTML khối → cặp → dựng lại dạng kia."""
    data = request.json or {}
    groups = si.block_to_groups(data.get("block_html") or "")
    target = data.get("to")
    if not groups:
        return jsonify({"ok": False, "error": "Không bóc được dòng thông số nào từ khối hiện tại"}), 400
    block = si.build_table(groups) if target == "table" else si.build_blockquote(groups)
    return jsonify({"ok": True, "block_html": block,
                    "rows": sum(len(g["rows"]) for g in groups), "groups": len(groups)})


def spec_publish(pid):
    data = request.json or {}
    block = (data.get("block_html") or "").strip()
    body = data.get("body_html")
    p = si.get_product(pid)
    if not p:
        return jsonify({"ok": False, "error": "Không thấy SP trong kho"}), 404
    base = body if body is not None else (p["body_html"] or "")
    if block:
        new_body = si.replace_spec_block(base, block, p["spec_block_html"] or "")
    else:
        new_body = base
    try:
        res = si.push_body(pid, new_body)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 500
    lab, verdict = si.FMT_LABEL.get(res["spec_format"], ("—", ""))
    return jsonify({"ok": res["ok"], "spec_format": res["spec_format"],
                    "fmt_label": lab, "verdict": verdict, "body_len": res["body_len"],
                    "url": f"https://sintech.vn/products/{p['handle']}"})


def register(app):
    app.add_url_rule("/spec", "spec_index_page", spec_index_page)
    app.add_url_rule("/spec/g/<handle>", "spec_group_page", spec_group_page)
    app.add_url_rule("/spec/g/<handle>/quick", "spec_quick_page", spec_quick_page)
    app.add_url_rule("/spec/q/<int:pid>/save", "spec_quick_save", spec_quick_save,
                     methods=["POST"])
    app.add_url_rule("/spec/q/<int:pid>/exclude", "spec_quick_exclude", spec_quick_exclude,
                     methods=["POST"])
    app.add_url_rule("/spec/p/<int:pid>", "spec_product_page", spec_product_page)
    app.add_url_rule("/spec/scan", "spec_scan", spec_scan, methods=["POST"])
    app.add_url_rule("/spec/scan-status", "spec_scan_status", spec_scan_status)
    app.add_url_rule("/spec/api/search", "spec_api_search", spec_api_search)
    app.add_url_rule("/spec/api/log", "spec_api_log", spec_api_log)
    app.add_url_rule("/spec/api/errors", "spec_api_errors", spec_api_errors)
    app.add_url_rule("/spec/p/<int:pid>/error", "spec_error_add", spec_error_add,
                     methods=["POST"])
    app.add_url_rule("/spec/g/<handle>/approve", "spec_approve_collection",
                     spec_approve_collection, methods=["POST"])
    app.add_url_rule("/spec/p/<int:pid>/sources", "spec_sources", spec_sources)
    app.add_url_rule("/spec/p/<int:pid>/find-sources", "spec_find_sources",
                     spec_find_sources, methods=["POST"])
    app.add_url_rule("/spec/p/<int:pid>/convert", "spec_convert", spec_convert, methods=["POST"])
    app.add_url_rule("/spec/p/<int:pid>/publish", "spec_publish", spec_publish, methods=["POST"])
