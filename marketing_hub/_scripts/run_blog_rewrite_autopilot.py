# -*- coding: utf-8 -*-
"""Runner CLI cho Blog Rewrite Autopilot (scheduler/manual). Mặc định KHÔNG apply.

Usage:
  python _scripts/run_blog_rewrite_autopilot.py --mode PREP_ONLY
  python _scripts/run_blog_rewrite_autopilot.py --dry-run
Scheduler mặc định OFF — script chỉ chạy 1 lượt khi được gọi tay/cron đã enable.
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import blog_rewrite_autopilot as autopilot


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", default=None, help="PREP_ONLY | SAFE_AUTO_APPLY")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm-apply", default=None, help="confirm phrase cho SAFE_AUTO_APPLY")
    args = p.parse_args()
    cfg = autopilot.load_config()
    # scheduler guard: chỉ chạy nếu enabled (manual gọi vẫn được qua --mode)
    res = autopilot.run(mode=args.mode, dry_run=args.dry_run, confirm_apply_phrase=args.confirm_apply)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
