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
    app.add_url_rule("/spec/p/<int:pid>", "spec_product_page", spec_product_page)
    app.add_url_rule("/spec/scan", "spec_scan", spec_scan, methods=["POST"])
    app.add_url_rule("/spec/scan-status", "spec_scan_status", spec_scan_status)
    app.add_url_rule("/spec/api/search", "spec_api_search", spec_api_search)
    app.add_url_rule("/spec/api/log", "spec_api_log", spec_api_log)
    app.add_url_rule("/spec/g/<handle>/approve", "spec_approve_collection",
                     spec_approve_collection, methods=["POST"])
    app.add_url_rule("/spec/p/<int:pid>/sources", "spec_sources", spec_sources)
    app.add_url_rule("/spec/p/<int:pid>/find-sources", "spec_find_sources",
                     spec_find_sources, methods=["POST"])
    app.add_url_rule("/spec/p/<int:pid>/convert", "spec_convert", spec_convert, methods=["POST"])
    app.add_url_rule("/spec/p/<int:pid>/publish", "spec_publish", spec_publish, methods=["POST"])
