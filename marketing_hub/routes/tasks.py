"""Routes: Task Center — /tasks + /api/tasks/*. Generate dedup + cooldown, lock 409."""
from flask import render_template, jsonify, request

from services import task_center_service as tc


def tasks_page():
    return render_template("tasks.html", counts=tc.counts())


def api_tasks():
    return jsonify({**tc.list_tasks(request.args), "counts": tc.counts(), "is_running": tc.is_running()})


def api_generate():
    res = tc.start_generate_async()
    if not res.get("started"):
        return jsonify({"ok": False, "status": "already_running"}), 409
    return jsonify({"ok": True, **res})


def api_resolve(tid):
    d = request.json or {}
    return jsonify(tc.set_status(tid, "resolved", d.get("snooze_days")))


def api_reopen(tid):
    return jsonify(tc.set_status(tid, "open"))


def api_snooze(tid):
    d = request.json or {}
    return jsonify(tc.set_status(tid, "snoozed", d.get("snooze_days", 7)))


def register(app):
    app.add_url_rule("/tasks", "tasks_page", tasks_page)
    app.add_url_rule("/api/tasks", "api_tasks", api_tasks)
    app.add_url_rule("/api/tasks/generate", "api_tasks_generate", api_generate, methods=["POST"])
    app.add_url_rule("/api/tasks/<int:tid>/resolve", "api_tasks_resolve", api_resolve, methods=["POST"])
    app.add_url_rule("/api/tasks/<int:tid>/reopen", "api_tasks_reopen", api_reopen, methods=["POST"])
    app.add_url_rule("/api/tasks/<int:tid>/snooze", "api_tasks_snooze", api_snooze, methods=["POST"])
