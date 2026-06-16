# -*- coding: utf-8 -*-
"""QA P8 ALL-IN-ONE — classifier + label mapping + ordering + integration dry-run (PUT=0)."""
import sys, io, json
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DIR = Path(__file__).parent.parent
sys.path.insert(0, str(DIR))
import blog_rewrite_queues as q
import blog_rewrite_all_in_one as aio
import blog_rewrite_full_auto as fa
import blog_rewrite_apply as ap, blog_rewrite_autopilot as auto

res = []
def chk(n, c, x=""):
    res.append((n, bool(c))); print(("  PASS " if c else "  FAIL ") + n + (("  " + x) if x else ""))

# ── classifier routing (title+body) ──
CASES = [
    ("Keo tản nhiệt kim loại lỏng là gì? Có nên dùng?", "<h2>a</h2><p>giải thích khái niệm tản nhiệt</p>", None, q.Q_AUTO),
    ("Hướng dẫn xóa watermark bằng Photoshop từng bước", "<p>bước 1 mở ảnh, như hình bên dưới</p>", None, q.Q_VISUAL),
    ("RTX 5090 chính thức ra mắt giá khủng", "<p>nvidia vừa công bố ra mắt</p>", None, q.Q_NEWS),
    ("Microsoft kết thúc hỗ trợ Windows 11 22H2", "<p>end of support deadline</p>", None, q.Q_NEWS),
    ("Cấu hình chơi Cyberpunk đạt 120 fps", "<p>rtx 4070 đạt 120 fps benchmark</p>", None, q.Q_FPS),
    ("Tổng hợp kiến thức về CPU", "<h2>1</h2><h2>2</h2><h2>3</h2><p>x</p>", None, q.Q_AUTO),
    ("Bài mơ hồ abc xyz", "<p>ngắn</p>", None, q.Q_REVIEW),
    ("VRAM là gì", "<p>như hình dưới minh hoạ</p>", "BLOCKED_IMAGE", q.Q_VISUAL),
]
for title, body, dec, want in CASES:
    qq, reason, conf = q.classify_queue(title, body, dec)
    chk(f"classify '{title[:26]}' → {want}", qq == want, f"got {qq}")

# ── _spec_label mapping ──
chk("label APPLIED+AUTO → applied", aio._spec_label(q.Q_AUTO, "APPLIED") == "applied")
chk("label APPLIED+VISUAL → visual_fixed", aio._spec_label(q.Q_VISUAL, "APPLIED") == "visual_fixed")
chk("label APPLIED_RECONCILED", aio._spec_label(q.Q_AUTO, "APPLIED_RECONCILED") == "applied_reconciled")
chk("label BLOCKED_IMAGE → blocked_image", aio._spec_label(q.Q_VISUAL, "BLOCKED_IMAGE") == "blocked_image")
chk("label HOLD_TIME_SENSITIVE → hold_news", aio._spec_label(q.Q_NEWS, "HOLD_TIME_SENSITIVE") == "hold_news")
chk("label BLOCKED_FACT+FPS → hold_benchmark", aio._spec_label(q.Q_FPS, "BLOCKED_FACT") == "hold_benchmark")
chk("label MANUAL_REVIEW → manual_complex", aio._spec_label(q.Q_REVIEW, "MANUAL_REVIEW") == "manual_complex")

# ── ordering: AUTO trước, REVIEW sau ──
ordered, qmap, per = aio.build_ordered(reclassify=False)
stages_present = [s for s in aio.STAGE_ORDER if per.get(s)]
# vị trí đầu mỗi stage phải tăng dần theo STAGE_ORDER
idx = []
pos = 0
ok_order = True
for s in aio.STAGE_ORDER:
    n = len(per.get(s, []))
    if n and ordered[pos:pos + n] != per[s]:
        ok_order = False
    pos += n
chk("ordering = stage order (AUTO→VISUAL→NEWS→FPS→REVIEW)", ok_order and pos == len(ordered), f"total={len(ordered)}")
chk("mọi bài có queue (không thiếu)", all(qmap.get(cid) for cid in ordered))

# ── integration dry-run (PUT=0, no generate) ──
cb_snap = auto.cb_state()
put_calls = {"n": 0}
orig_put = ap._put_article
ap._put_article = lambda *a, **k: (put_calls.__setitem__("n", put_calls["n"] + 1) or (201, {}))
try:
    r = aio.run_all_in_one(dry_run=True, reclassify=False, max_articles=6)
    chk("dry-run all-in-one ok", r.get("ok"), f"err={r.get('error')}")
    chk("dry-run PUT = 0", put_calls["n"] == 0, f"puts={put_calls['n']}")
    cp = fa.load_checkpoint()
    chk("dry-run processed = 6", cp and cp.get("processed") == 6, f"processed={cp.get('processed') if cp else None}")
    chk("dry-run mode ALL_IN_ONE", True)
finally:
    ap._put_article = orig_put

npass = sum(1 for _, c in res if c)
print(f"\n=== QA P8: {npass}/{len(res)} PASS ===")
print("CB open:", auto.cb_state().get("open"), "| flags:", ap.flags() or "OFF")
sys.exit(0 if npass == len(res) else 1)
