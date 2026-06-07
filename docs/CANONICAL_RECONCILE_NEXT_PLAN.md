# Canonical Reconcile — Next Plan (KHÔNG thực thi)

> Tài liệu kế hoạch. **KHÔNG reset, KHÔNG rebase, KHÔNG switch, KHÔNG delete** trong mega-run này. Reconcile là task riêng cần vợ duyệt.

## Trạng thái hiện tại (cuối mega-run tracking release)
- Canonical HEAD: `de3e6d7` (= origin sau khi push 3 commit tracking/tasks/ops).
- origin/master: `6bd391c` (clean worktree replay; canonical commits đã lên GitHub qua cherry-pick).
- Clean worktree `Desktop\nox-clean-push` branch `cleanup/pre-push-history`: sạch, HEAD == origin/master.
- Auto Commit task: **Disabled**.
- Backup: `Desktop\tracking_release_backup_<ts>\` (tracked diff + git status + schema-only SQLite).

## WIP cũ trong canonical (KHÔNG đụng trong mega-run)
- **Modified tracked (~11 file):** `db.py` (WIP `hv_all_product_ids`/`hv_delete_products` — luôn loại khỏi staging qua cached patch), `alt_manager.py`, `cwv.py`, `haravan_sync.py`, `routes/alt.py`, `routes/haravan.py`, `seo.py`, `sync_collection_images.py`, … — thay đổi cũ chưa commit từ các phiên trước.
- **Untracked (~63 file):** scripts rời (`build_*.py`, `fetch_*.py`, `read_*.py`…), file data local (`*.xlsx`, `*.csv`), `token.pickle`, `blog_pkg/`, `gsc/`, `audit_bundle/`, ảnh `*.jpg`… — phần lớn là data/ad-hoc, KHÔNG nên commit bừa.
- **Data local:** `marketing_hub/data/posts.db` (DB chính, gitignored), config local (`state/*.json` trừ `*.example.json`), token (`.secrets/`).

## Nguyên tắc reconcile (khi làm task riêng)
1. **Phân loại từng nhóm** trước khi commit: code thật vs script ad-hoc vs data local vs rác.
2. Code thật (alt/cwv/haravan/seo…) → review diff, commit theo nhóm logic, push qua clean worktree.
3. `db.py` WIP `hv_*` → quyết định giữ/bỏ (feature Haravan bulk delete dở) — review riêng.
4. Script ad-hoc → cân nhắc `_scripts/` hoặc gitignore.
5. Data local (xlsx/csv/pickle/db) → gitignore, KHÔNG commit.
6. **KHÔNG** `git add .` / `git add -A`. Stage có chọn lọc.
7. Mọi push qua clean worktree fast-forward, KHÔNG push từ canonical, KHÔNG force.

## Đề xuất thứ tự (task riêng, chờ duyệt)
1. Gitignore data local còn sót (xlsx/csv/pickle/jpg ở root) → giảm nhiễu `git status`.
2. Review + commit code WIP theo nhóm (alt, cwv, haravan, seo) — từng commit nhỏ.
3. Quyết định số phận `hv_*` trong db.py.
4. Dọn script ad-hoc.

🚦 **KHÔNG thực thi tự động. Chờ vợ mở task reconcile riêng.**
