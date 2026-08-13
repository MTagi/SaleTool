# 02 — Khai thác tối đa tài khoản Sales Navigator bạn đang có

Đây là phần quan trọng nhất, vì bạn **đã trả tiền cho công cụ này rồi**. Mục
tiêu: hiểu chính xác nó cho gì, cấm gì, và giới hạn ở đâu — để không kỳ vọng sai
và không tự đưa mình vào rủi ro không cần thiết.

---

## 1. Điểm mạnh thật sự: Account Search (tìm công ty)

Nhiều người dùng Sales Navigator chỉ để tìm *người*. Nhưng với nhu cầu của bạn
("tìm công ty phù hợp"), **Account Search mới là thứ đáng tiền** — và đây là chỗ
LinkedIn thực sự có dữ liệu độc quyền mà không nhà cung cấp nào sao chép được
đầy đủ.

### Các bộ lọc công ty đáng giá nhất

| Bộ lọc | Vì sao quan trọng |
|---|---|
| **Company headcount growth** | Lọc công ty đang tăng trưởng theo % — tín hiệu có ngân sách, đang mở rộng. **Không nguồn public nào khác có được số này theo thời gian thực.** |
| **Department headcount** | Số nhân sự theo *phòng ban cụ thể* (VD: công ty có ≥ 5 người phòng Sales). Cực mạnh nếu sản phẩm của bạn bán cho 1 phòng ban nhất định. |
| **Department headcount growth** | Phòng ban nào đang phình ra → nơi đó đang có nhu cầu/ngân sách. |
| **Annual revenue** | Lọc theo doanh thu (nhiều loại tiền tệ). |
| **Company headcount** | Quy mô tổng. |
| **Industry / Location** | Cơ bản. |
| **Technologies used** | Công nghệ đang dùng — hữu ích để bán sản phẩm tích hợp/thay thế. |
| **Hiring signal** | Công ty đang tuyển → tín hiệu tăng trưởng. |
| **Company connections** | Ai trong mạng lưới của bạn đang làm ở đó → đường vào ấm. |

> Sales Navigator có tổng cộng **30+ bộ lọc** ở cấp account và lead.

### Chiến thuật kết hợp đáng dùng

Công thức được nhiều nguồn khuyến nghị:

```
Industry + Location + Headcount range + Headcount GROWTH > X%
```

Lý do: `headcount growth` biến một danh sách tĩnh thành **danh sách có tín hiệu
mua**. Đây là điểm khác biệt cốt lõi giữa Sales Navigator và một database
firmographic mua ngoài (vốn thường chỉ có snapshot tĩnh, cập nhật hàng tháng).

### 💡 Hàm ý cho SaleTool

`SearchCriteria` hiện tại của bạn có `company_size_min/max` nhưng **chưa có
trường tăng trưởng nhân sự**. Nếu quy trình của bạn là human-in-the-loop qua
Sales Navigator, nên bổ sung các trường phản ánh đúng bộ lọc SN:
`headcount_growth_min`, `department`, `department_headcount_min`,
`technologies`, `hiring_signal`. Xem chi tiết ở [`07-khuyen-nghi-lo-trinh.md`](07-khuyen-nghi-lo-trinh.md).

---

## 2. Sự thật về export: KHÔNG có nút export

Trang trợ giúp chính thức của LinkedIn nói thẳng:

> *"We currently don't offer the option to export account and lead information
> from Sales Navigator into a CSV or XLS file."*

Cụ thể là:
- ❌ Không có nút "Export to CSV" ở bất kỳ đâu
- ❌ Không có API cho lead list ở gói Core và Advanced
- ❌ Không có cách chọn 1 search rồi tải hàng loạt
- ✅ Chỉ có CRM Sync (Advanced Plus + Salesforce/Dynamics) — xem [`01-duong-chinh-thuc.md`](01-duong-chinh-thuc.md)

> ⚠️ **Ghi chú nguồn:** một số blog ghi mốc "as of July 1, 2026" cho việc này.
> Tôi không xác minh được mốc đó (môi trường khảo sát bị chặn truy cập
> `linkedin.com`). Nhiều khả năng đó là ngày cập nhật trang trợ giúp, không phải
> ngày LinkedIn "gỡ bỏ" tính năng — vì thực tế Sales Navigator chưa từng có nút
> export CSV chính thức. Bạn nên tự mở trang trợ giúp để xác nhận.

---

## 3. Giới hạn định lượng cần biết

Đây là các con số quyết định việc thiết kế quy trình của bạn:

| Giới hạn | Con số | Ảnh hưởng |
|---|---|---|
| **Kết quả tối đa / 1 search** | **2.500** (100 trang × 25) | Thị trường lớn hơn 2.500 → **bắt buộc chia nhỏ** search bằng filter phụ |
| Saved searches | 50 lead + 50 account | Đủ dùng cho hầu hết trường hợp |
| Saved leads | 2.500 | Cần dọn dẹp định kỳ nếu làm quy mô lớn |
| Mỗi custom list | 1.000 | Chia list theo segment |
| Search người (people) | Không giới hạn số lượt | Khác hẳn tài khoản free |
| Alert từ saved search | Hàng ngày / hàng tuần | **Tính năng bị đánh giá thấp** — xem mục 4 |

### Chiến thuật vượt giới hạn 2.500 (hợp lệ)

Không phải "hack", chỉ là chia nhỏ tập kết quả:
- Chia theo **địa lý** (tỉnh/thành, quốc gia)
- Chia theo **khoảng headcount** (1–10, 11–50, 51–200…)
- Chia theo **ngành con**
- Chia theo **khoảng doanh thu**

Mỗi lát cắt là một search riêng < 2.500 kết quả. Đây là cách làm chuẩn, không
vi phạm gì.

### So sánh với tài khoản free (để thấy giá trị bạn đang có)

| | Free | Sales Navigator |
|---|---|---|
| Commercial Use Limit | ~300 search/tháng, sau đó bị chặn | **Không bị giới hạn này** |
| Kết quả/search | 1.000 | 2.500 |
| Bộ lọc account nâng cao | Không | **Có (30+)** |

---

## 4. Tính năng bị đánh giá thấp: Saved Search + Alerts

Đây là thứ biến Sales Navigator từ "công cụ tra cứu" thành **"hệ thống theo dõi
tín hiệu"** — và nó hoàn toàn hợp lệ.

**Cách dùng:**
1. Tạo search account với tiêu chí lý tưởng (ICP) của bạn
2. Lưu lại (saved search)
3. LinkedIn tự động gửi alert khi có **công ty mới khớp tiêu chí**

**Vì sao đáng giá:** thay vì bạn phải quét lại toàn bộ thị trường mỗi tháng,
LinkedIn chủ động báo cho bạn phần *thay đổi* (delta). Với 50 saved search, bạn
có thể phủ 50 phân khúc ICP khác nhau và nhận tín hiệu liên tục.

**Các loại alert khác đáng theo dõi:**
- Thay đổi nhân sự cấp cao (job change) — tín hiệu mua rất mạnh
- Công ty được nhắc tin tức
- Tăng trưởng nhân sự bất thường

---

## 5. Các tính năng khác

| Tính năng | Mô tả | Đánh giá |
|---|---|---|
| **Lead Recommendations** | LinkedIn gợi ý người liên quan trong account đã lưu | Hữu ích, tiết kiệm thời gian tìm đúng người |
| **InMail** | Nhắn tin ngoài mạng lưới | Có credit hàng tháng, tuỳ gói |
| **TeamLink** | Xem đồng nghiệp có kết nối gì | Chỉ có ở gói team |
| **Buyer Intent** | Tín hiệu quan tâm | Có ở Advanced |
| **Notes & Tags** | Ghi chú trong SN | Dữ liệu này *không* export được |

---

## 6. Ranh giới: cái gì được và không được làm

Đây là phần cần đọc kỹ nhất.

### ✅ Được phép (an toàn hoàn toàn)

- Search, lọc, xem kết quả bằng mắt trong giao diện
- Lưu lead/account vào list
- Tạo saved search, nhận alert
- **Con người tự đọc và tự gõ lại** thông tin sang hệ thống khác
- Copy/paste thủ công từng bản ghi
- CRM Sync (nếu có Advanced Plus + Salesforce/Dynamics)

### ❌ Vi phạm LinkedIn User Agreement

- Dùng extension/script/bot để **trích xuất tự động** kết quả
- Chạy trình duyệt tự động (Selenium/Playwright/Puppeteer) trên tài khoản
- Xuất hàng loạt bằng bất kỳ công cụ bên thứ ba nào
- Tạo tài khoản giả để tăng hạn mức
- Chia sẻ cookie phiên đăng nhập cho dịch vụ cloud

### ⚠️ Vùng xám mà nhiều người hiểu sai

> *"Extension chạy chậm như người thật thì không sao."*

**Không đúng về mặt hợp đồng.** Tốc độ ảnh hưởng đến **khả năng bị phát hiện**,
không ảnh hưởng đến **tính vi phạm**. LinkedIn User Agreement cấm việc trích
xuất dữ liệu tự động, không cấm "trích xuất nhanh". Vụ hiQ cho thấy toà xử
**vi phạm hợp đồng** ngay cả khi CFAA không áp dụng.

Các blog của nhà cung cấp công cụ ghi "zero ban risk" — đó là tuyên bố về xác
suất bị bắt, không phải về tính hợp lệ. Hai chuyện khác nhau.

---

## 7. Dấu hiệu cảnh báo tài khoản đang bị soi

Nếu bạn (hoặc ai trong nhóm) có dùng công cụ tự động, các dấu hiệu này xuất hiện
**trước** khi bị khoá:

1. Bị đăng xuất đột ngột, lặp lại
2. Cookie phiên hết hạn bất thường
3. Bị yêu cầu xác thực lại liên tục
4. CAPTCHA xuất hiện nhiều bất thường
5. Kết quả search bị cắt/rỗng bất thường

➡️ Gặp các dấu hiệu này = **dừng ngay mọi tự động hoá**. Bước tiếp theo của
LinkedIn thường là hạn chế tài khoản, rồi khoá vĩnh viễn.

**Chi phí nếu mất tài khoản:** không chỉ mất tiền thuê bao. Mất luôn saved
searches, lead lists, lịch sử InMail, và mạng lưới kết nối gắn với tài khoản cá
nhân đó.

---

## 8. Quy trình human-in-the-loop khuyến nghị

Đây là quy trình an toàn nhất tận dụng được tài khoản của bạn — và đúng thứ
provider `csv_import` trong SaleTool đang phục vụ:

```
1. [Sales Navigator - thủ công]
   Tạo account search với ICP  →  chia nhỏ để mỗi search < 2.500
   ↓
2. [Sales Navigator - thủ công]
   Lưu vào Account List, đặt tên theo segment
   ↓
3. [Con người]
   Rà soát bằng mắt, loại bỏ công ty không phù hợp
   (bước này AI/scraper không làm thay được tốt)
   ↓
4. [Chuyển dữ liệu]
   Nhập tay / copy sang CSV theo mẫu của SaleTool
   ↓
5. [SaleTool - tự động]
   csv_import → chuẩn hoá, lọc seniority, lưu lịch sử
   ↓
6. [Nhà cung cấp bên thứ ba - tự động]
   Enrich thêm email/điện thoại/liên hệ cấp cao
   (KHÔNG lấy từ LinkedIn — xem file 03)
```

**Điểm mấu chốt:** bước 1–4 do **con người** thao tác trên trình duyệt của chính
họ. Bước 5–6 là tự động nhưng **không chạm vào LinkedIn**. Ranh giới này giữ bạn
ở phía an toàn.

**Nút thắt cổ chai:** bước 4 (nhập tay). Đây là chi phí thật của việc tuân thủ.
Ước tính thực tế: một người làm được khoảng 50–200 công ty/ngày tuỳ mức độ chi
tiết. Nếu nhu cầu của bạn lớn hơn nhiều lần con số đó → nên mua dữ liệu từ nhà
cung cấp (file 03) thay vì tìm cách tự động hoá LinkedIn.
