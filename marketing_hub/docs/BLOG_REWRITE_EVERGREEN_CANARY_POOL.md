# EVERGREEN CANARY POOL (10/6/2026)

Sau P5G-4: HOLD #55/#26 (facts), generate 2 evergreen #112+#110. **canary_ready evergreen: 1** · selected: [21].

## HOLD (facts chưa xử lý)
- **#55 RTX 3060** → HOLD_TIME_SENSITIVE_NEWS (Nvidia đưa 3060 lại — tin comeback chỉ là báo cáo chưa chính thức) → rewrite dạng 'theo báo cáo' hoặc skip.
- **#26 So sánh VGA** → HOLD_UNSUPPORTED_BENCHMARKS (bảng FPS AI tự tạo) → bỏ số FPS + review specs.

## READY_EVERGREEN (fact-safe)
| # | Candidate | Draft | Overlap | Img | Gate | Conflict | Facts |
|---|---|---|---|---|---|---|---|
| 1 | #21 DLSS 4 là gì? Cách bật DLSS  | 23 v1 | 10.0% | 8 | ALLOW | SAFE_TO_APPLY | 0 unsupported / 0 time-sensitive |

## Selected canary (2): [21]
- Bài khái niệm how-to (cảm biến chuột, tần số quét) — KHÔNG benchmark/giá/tin/driver → fact-safe, overlap ≤3%, gate ALLOW, ảnh ngoài đã gỡ (text sạch).
- An toàn hơn #55/#26 nhiều cho canary đầu tiên.

## Kết luận
- **2 canary evergreen READY** (fact-safe) — sẵn sàng vợ review nhẹ → approve_local → canary apply (P5B one-shot).
- Flags live VẪN KHÓA. KHÔNG apply lượt này.