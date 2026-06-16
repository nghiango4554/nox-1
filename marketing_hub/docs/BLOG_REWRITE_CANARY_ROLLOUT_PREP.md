# CANARY ROLLOUT PREP (10/6/2026)

## ⚠️ Phát hiện
- 6 SAFE_NOW (gate ALLOW image) nhưng **6/6 CHƯA có draft AI** (ids [21, 50, 55, 72, 71, 64]) → KHÔNG canary được (chưa có nội dung viết lại).
- Canary-ready (draft + gate ALLOW + chưa apply + non-reverse): **1 bài**. #136(#64) đã apply; #7/#8/#12 block ảnh đối thủ.

## Canary-ready
| # | Candidate | Draft | Gate | Conflict | Approval | Overlap | Img | Table | Risk |
|---|---|---|---|---|---|---|---|---|---|
| 1 | #26 So sánh 3 VGA tầm giá 5–7  | 12 v1 | ALLOW | SAFE_TO_APPLY | review_required | 18.9% | 1 | 1 | ⚠️ overlap 18.9% → review/regenerate trước |

## Kết luận
- **KHÔNG đủ 2 canary** như spec giả định: pool thật = 1 bài (#26), lại review_required (overlap 18.9%).
- Để rollout chuẩn cần: (a) generate draft AI cho vài bài SAFE_NOW sạch ảnh (DLSS/Microsoft/Nvidia/Valorant/Elden Ring/Dota2 — chỉ cần gen nội dung) → (b) preflight → chọn 2 bài approved_local; HOẶC review/regenerate #26.
- #64 vẫn là pilot live PASS. KHÔNG apply gì lượt này — flags khóa.