# Kết quả Audit Thủ công (Người chấm: Lê Anh Sơn — Tác giả)

> Lưu ý thiên lệch: Người chấm là tác giả bài làm; đã cố định 10 vị trí coherence (trang 1–10) trước khi xem điểm và dùng cùng bộ tiêu chí cho cả 3 chiến lược.

## 1. Chunk Coherence (10 vị trí cố định: trang 1–10)
Thang điểm: `0` = cắt giữa ý/thiếu chủ thể không hiểu; `1` = hiểu một phần/thiếu ngữ cảnh; `2` = tự hiểu được, trọn ý.

| Trang | Chiến lược A (`fixed_size`) | Lý do (A) | Chiến lược B & C (`by_paragraph`) | Lý do (B & C) |
|---:|---:|---|---:|---|
| 1 | 1 | Giữ phần đầu Quốc hiệu/tên Luật nhưng cắt giữa câu `"Căn cứ Hiến pháp nước Cộng..."` | 2 | Trọn phần Quốc hiệu, tên Luật và căn cứ ban hành |
| 2 | 1 | Đủ khoản 9–10 nhưng cắt giữa khoản 12 | 2 | Trọn vẹn khoản 9, 10, 11 không đứt câu |
| 3 | 1 | Đủ khoản 7 nhưng cắt giữa Điều 4 khoản 1 | 2 | Trọn khoản 7 và Điều 4 khoản 1 |
| 4 | 1 | Đủ khoản 1–3 nhưng cắt giữa khoản 4 | 2 | Trọn vẹn khoản 1, 2, 3 của Điều 6 |
| 5 | 0 | Bắt đầu từ điểm `d)` (thiếu tên Điều 7 ở trang 4) và cắt giữa khoản 2 | 1 | Trọn các điểm `d)..k)` nhưng vẫn thiếu tiêu đề Điều 7 ở trang trước |
| 6 | 0 | Bắt đầu từ `1.` (thiếu tiêu đề Điều 9) và cắt giữa câu | 1 | Trọn các khoản 1..4 nhưng thiếu tiêu đề Điều 9 ở trang trước |
| 7 | 0 | Bắt đầu từ `16.` (thiếu tiêu đề Điều 9) và cắt giữa câu | 1 | Trọn các khoản 16..18 nhưng thiếu tiêu đề Điều 9 ở trang trước |
| 8 | 1 | Có tiêu đề Chương II, Điều 10 nhưng cắt giữa khoản 3 | 2 | Trọn Chương II, Điều 10 khoản 1 và 2 |
| 9 | 0 | Bắt đầu từ `a)` (thiếu câu dẫn Điều 11) và cắt giữa `b)` | 1 | Trọn điểm `a)` và phần đầu `b)`, vẫn thiếu câu dẫn Điều 11 ở trang 8 |
| 10 | 1 | Đọc được ý chính khoản 3 nhưng cắt giữa điểm `e)` | 2 | Trọn khoản 3 (điểm `a..e`), tự hiểu đầy đủ |
| **TB / 2** | **0.60** (6/20) | 4 mức 0, 6 mức 1, 0 mức 2 | **1.60** (16/20) | 0 mức 0, 4 mức 1, 6 mức 2 |

## 2. Metadata Usefulness (6 câu test × top-3 = 18 bản ghi/chiến lược)
- **Đủ và đúng (`source`, `page`, `chapter`)**:
  - **A**: `18/18` bản ghi khớp chính xác số trang và chương của tài liệu gốc.
  - **B**: `18/18` bản ghi khớp chính xác số trang và chương.
  - **C**: `18/18` bản ghi khớp chính xác số trang và chương.
- **Tuân thủ filter**:
  - **A / B**: `N/A` (không bật cơ chế lọc SQL trong truy xuất).
  - **C**: `2/2` câu test có filter (`q18` lọc `Chương II`, `q19` lọc `Chương IV`) có 100% top-3 tuân thủ đúng chương. (Trên tập dev cũng đạt `3/3`).

## 3. Grounding Quality (6 câu test, thang 0–2)
| Câu | Gold Page | Filter | A (điểm & lý do) | B (điểm & lý do) | C (điểm & lý do) |
|---|---|---|---|---|---|
| `q17` | 8 | - | **2**: Rank 1 đủ Điều 10 khoản 2 | **2**: Rank 1 trọn Điều 10 | **2**: Rank 1 trọn Điều 10 |
| `q18` | 14 | `Chương II` | **2**: Rank 2 đủ khoản 7 Điều 18 | **2**: Rank 1 trọn khoản 7 Điều 18 | **2**: Rank 1 trọn khoản 7 Điều 18 |
| `q19` | 41 | `Chương IV` | **1**: Rank 1 cắt mất chữ đầu `"Giấy..."` và cắt phần cuối khoản 3 | **2**: Rank 1 trọn khoản 3 Điều 62 | **2**: Rank 1 trọn khoản 3 Điều 62 |
| `q20` | 56 | - | **1**: Rank 1 cắt giữa khoản 5 Điều 82, thiếu hành động của Công an | **2**: Rank 1 trọn khoản 5 Điều 82 | **2**: Rank 1 trọn khoản 5 Điều 82 |
| `q21` | 53 | - | **2**: Rank 1 đủ khoản 1 Điều 77 | **2**: Rank 1 trọn khoản 1 Điều 77 | **2**: Rank 1 trọn khoản 1 Điều 77 |
| `q22` | 60 | - | **2**: Rank 2 đủ điểm a khoản 2 Điều 89 | **2**: Rank 2 trọn điểm a khoản 2 Điều 89 | **2**: Rank 2 trọn điểm a khoản 2 Điều 89 |
| **Tổng hợp** | | | **0/2/4** (0 mức 0, 2 mức 1, 4 mức 2) — TB **1.67/2** | **0/0/6** (6 mức 2) — TB **2.00/2** | **0/0/6** (6 mức 2) — TB **2.00/2** |

