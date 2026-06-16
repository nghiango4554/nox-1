# -*- coding: utf-8 -*-
"""Runner nền P8 ALL-IN-ONE — chạy detached để UI poll realtime (reuse full_auto checkpoint).

  python _scripts/run_blog_rewrite_all_in_one.py --live --confirm "START ALL IN ONE BLOG REWRITE SYNC"
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import blog_rewrite_all_in_one as aio


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--live", action="store_true")
    p.add_argument("--confirm", default=None)
    p.add_argument("--max-articles", type=int, default=None)
    p.add_argument("--no-reclassify", action="store_true")
    p.add_argument("--skip-decided", action="store_true", help="retry chỉ FAILED + chưa xử (bỏ bài đã chốt)")
    a = p.parse_args()
    res = aio.run_all_in_one(confirm_phrase=a.confirm, dry_run=a.dry_run,
                             max_articles=a.max_articles, reclassify=not a.no_reclassify,
                             skip_decided=a.skip_decided)
    try:
        aio.export_csvs()
    except Exception:
        pass
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
