# -*- coding: utf-8 -*-
"""Runner nền cho Full Auto Run Once — chạy detached để UI poll realtime.

Usage (spawn bởi Flask):
  python _scripts/run_blog_rewrite_full_auto.py --dry-run
  python _scripts/run_blog_rewrite_full_auto.py --live --confirm "START FULL AUTO BLOG REWRITE SYNC"
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import blog_rewrite_full_auto as fa


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--live", action="store_true")
    p.add_argument("--confirm", default=None)
    p.add_argument("--max-articles", type=int, default=None)
    p.add_argument("--priority-cids", default=None, help="comma-separated candidate_id đẩy lên đầu queue")
    p.add_argument("--auto-only", action="store_true", help="CHỈ AUTO_LANE (bỏ DEFER_LANE)")
    p.add_argument("--skip-decided", action="store_true", help="loại bài đã có decision cuối (chỉ pending)")
    a = p.parse_args()
    pri = [int(x) for x in a.priority_cids.split(",") if x.strip()] if a.priority_cids else None
    res = fa.run_full_auto(confirm_phrase=a.confirm, dry_run=a.dry_run, max_articles=a.max_articles,
                           priority_cids=pri, auto_only=a.auto_only, skip_decided=a.skip_decided)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
