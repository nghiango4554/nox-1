# BLOG REWRITE AI — P5G-3 EDITORIAL FACT CHECK (10/6/2026)

> Fact-check + editorial 2 canary (#55 Nvidia RTX 3060, #26 So sánh 3 VGA). Read-only. **KHÔNG PUT/apply/upload/rehost · KHÔNG mở flag · KHÔNG commit/push/deploy.** Live flags KHÓA.

## 1. Audit 2 canary
| Candidate | Article | Draft | Ver | Images | Tables | Gate | Conflict | Overlap |
|---|---|---|---|---|---|---|---|---|
| #55 Nvidia RTX 3060 | 1002xxx | 24 | v1 | 2 (Sintech) | 0 | ALLOW | SAFE_TO_APPLY | 1.5% |
| #26 So sánh 3 VGA | 1002431x | 22 | v2 | 1 (Sintech) | 1 | ALLOW | SAFE_TO_APPLY | 9.2% |

## 2. Fact extraction — phát hiện chính
### 🔴 #55 RTX 3060 — FACT REVIEW **FAIL**
Claim cốt lõi **"Nvidia sắp ngừng sản xuất RTX 3060"** → **LỖI THỜI / NGƯỢC thực tế:**
- RTX 3060 discontinued 8/2024 NHƯNG **Nvidia ĐANG ĐƯA TRỞ LẠI**: resume sản xuất 6/2026, ra mắt 7/2026 với MSI/ASUS/Colorful/GALAX (do khủng hoảng thiếu RAM). Nguồn: WCCFtech, TechSpot, VideoCardz, Notebookcheck.
- Bài viết "sắp khai tử" mâu thuẫn thực tế hiện tại (10/6/2026) → **misinformation nếu publish**.
- → status REMOVE_UNSUPPORTED_CLAIM. **KHÔNG apply #55** — cần rewrite phản ánh 3060 quay lại, hoặc drop bài.
- (Claim stable đúng: 12GB VRAM, ra mắt 2/2021, RTX 4060 bus/VRAM thấp hơn.)

### 🟡 #26 So sánh 3 VGA — FACT REVIEW **REQUIRED**
- Spec ĐÚNG (VERIFIED_STABLE): RTX 3050/RX 6600 8GB · RTX 3060 12GB GDDR6 · DLSS/Reflex/NVENC · RX 6600 > RTX 3050 raster.
- **Bảng FPS toàn số AI tự tạo** (RTX 3050 LoL ~190, RX 6600 >220, RTX 3060 ~175 CS2...) → **UNSUPPORTED, không nguồn benchmark** → bỏ số cụ thể hoặc thay định tính.
- Giá "5-7 triệu" → time-sensitive MANUAL_REVIEW.
- → cần editor sửa/bỏ số FPS + giá trước approve.

## 3. Editorial scorecard
| Hạng mục | #55 | #26 |
|---|---|---|
| Originality | high (overlap 1.5%) | high (9.2%) |
| Coverage / Structure | ok | ok (nhiều heading + FAQ) |
| **Facts** | **FAIL (lỗi thời)** | **REVIEW (FPS unsupported)** |
| Images | PASS (2 Sintech, gate ALLOW) | PASS (1 Sintech) |
| Links | PASS (0 competitor href) | PASS (0 competitor) |
| HTML | PASS | PASS |
| **Overall** | **KHÔNG apply** | **review rồi mới approve** |

## 4. Image / Link / Fresh preflight
- #55: gate ALLOW · 2 ảnh Sintech · 0 dead/competitor/unknown · 0 external link · conflict SAFE_TO_APPLY · approved_local=False · apply_enabled=False (flag khóa).
- #26: gate ALLOW · 1 ảnh Sintech · 0 blocked · 0 competitor href · conflict SAFE_TO_APPLY · approved_local=False.

## 5. UI
Canary panel thêm "🔬 Fact review": badge FACT REVIEW FAIL / REQUIRED + counts (stable/manual/unsupported) + ready_manual_approve. Apply live disabled.

## 6. Export
`docs/BLOG_REWRITE_CANARY_FACT_CHECK.md` + `.csv` (claims table per category/status/note).

## 7. QA
- compileall OK · node --check N/A.
- 2 candidate đúng · fact extraction (web-verified claim Nvidia) · image gate ALLOW · link check 0 competitor · fresh preflight SAFE read-only.
- Smoke `/seo/blog-rewrite-ai` `/remediation/fact-check` `/remediation/canary-prep` 200.
- **PUT=0 · POST write=0 · DELETE=0 · upload=0** · live flags **OFF (khóa)** · broken-link config **nguyên (48/8/4/2s)** · secret sạch.

## 8. Kết luận
- **CẢ 2 CANARY CHƯA READY apply** sau fact-check: #55 facts lỗi thời (Nvidia đưa 3060 trở lại 2026), #26 cần bỏ số FPS AI tự tạo.
- **Bài học:** loại bài AN TOÀN nhất để rollout = **how-to/evergreen không số liệu time-sensitive** (như pilot #64 switch). Bài tin tức (#55) + benchmark (#26) rủi ro facts cao — AI dễ giữ thông tin lỗi thời hoặc bịa số.
- → Rollout nên ưu tiên bài how-to/khái niệm; bài tin/benchmark cần editor verify facts kỹ.

## 9. Files
- **NEW**: `docs/BLOG_REWRITE_CANARY_FACT_CHECK.md` + `.csv`, `state/_canary_fact_check.json`, doc này.
- **MOD**: `routes/blog_rewrite.py` (fact-check endpoint), `templates/blog_rewrite_ai.html` (fact-review UI).
- **Backup**: (no code logic change cần backup — chỉ thêm endpoint + UI; ghi rõ minimal change).

## OUTPUT
**BLOG REWRITE AI P5G-3 EDITORIAL FACT CHECK COMPLETED** · #55 FACT REVIEW **FAIL** (claim "RTX 3060 sắp khai tử" lỗi thời — Nvidia đưa trở lại 7/2026, web-verified) · #26 FACT REVIEW **REQUIRED** (bảng FPS unsupported AI tự tạo + giá time-sensitive; spec đúng) · cả 2 gate ALLOW/conflict SAFE/ảnh+link sạch nhưng **CHƯA ready apply do facts** · PUT=0 upload=0 flags OFF · broken-link untouched · no commit/push. **Khuyến nghị: rollout ưu tiên bài how-to/evergreen (như #64), bài tin/benchmark cần editor verify.**
