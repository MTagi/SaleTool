# 01 — Đường chính thức: API và sản phẩm dữ liệu của LinkedIn

Phần này trả lời câu hỏi: *"LinkedIn có cho tôi lấy dữ liệu công ty một cách
chính thức không?"* — Câu trả lời ngắn: **gần như không, trừ khi bạn là đối tác
CRM lớn đã ký hợp đồng từ trước.**

---

## 1. Sales Navigator API (SNAP) — cửa đã đóng

**SNAP = Sales Navigator Application Platform.** Đây là API duy nhất của
LinkedIn thực sự liên quan đến dữ liệu Sales Navigator.

### Tình trạng hiện tại

Tài liệu chính thức của LinkedIn (trên Microsoft Learn) ghi:

> *"We are not currently accepting new partners for access to the LinkedIn
> Sales Navigator API."*

Cụ thể:
- ❌ Không có form đăng ký
- ❌ Không có danh sách chờ (waitlist)
- ❌ Không công bố timeline mở lại
- ✅ Đối tác cũ vẫn giữ quyền truy cập

### Ai đang có SNAP?

Chủ yếu là các nền tảng CRM/sales lớn đã tích hợp sẵn với Sales Navigator:
Salesforce, HubSpot, Microsoft Dynamics, Outreach, Salesloft… Đây là quan hệ
đối tác thương mại có ký kết, không phải thứ đăng ký tự phục vụ.

### SNAP gồm những dịch vụ gì

Theo tài liệu, SNAP có 3 nhóm dịch vụ:
- **Display Services** — nhúng profile Sales Navigator vào ứng dụng của đối tác
- **Analytics Services** — số liệu sử dụng
- **Sync Services** — đồng bộ dữ liệu CRM 2 chiều

Lưu ý: kể cả có SNAP, nó **không phải là API "search công ty tuỳ ý"**. Nó thiên
về đồng bộ và hiển thị trong ngữ cảnh CRM, không phải một cỗ máy truy vấn
firmographic.

### ⚠️ Hiểu lầm phổ biến cần xoá bỏ

> "Tôi trả tiền Sales Navigator rồi thì chắc có API dùng."

**Sai.** Thuê bao Sales Navigator (Core / Advanced / Advanced Plus) là quyền
truy cập **giao diện web cho một con người**. Nó không cấp:
- API key
- Client ID / Secret cho SNAP
- Bất kỳ endpoint lập trình nào

Hai thứ này hoàn toàn tách biệt về mặt thương mại.

---

## 2. LinkedIn Marketing Developer Platform (MDP)

Đây là chương trình API mở nhất của LinkedIn, nhưng **không phục vụ mục đích
tìm kiếm công ty**.

### Nó cho gì

| API | Phạm vi |
|---|---|
| `Organization Lookup` | Tra cứu thông tin 1 tổ chức khi **đã biết ID** |
| `Organization Search` | ⚠️ Chỉ mở cho **một số developer được chọn** |
| Analytics / Ads | Chỉ dữ liệu của **chính tài khoản quảng cáo của bạn** |
| Page management | Chỉ Page **bạn là quản trị viên** |

### Giới hạn sử dụng dữ liệu (quan trọng)

Điều khoản Marketing API của LinkedIn giới hạn rất chặt việc dùng lại dữ liệu:

> *Nếu bạn nhận được dữ liệu profile của tổ chức từ một Page — gồm logo, địa
> điểm, ngành, quy mô — bạn chỉ được sử dụng và hiển thị dữ liệu đó thông qua
> Marketing Application của bạn để phục vụ đúng Marketing Services mà dữ liệu
> đó được cấp cho.*

Nói cách khác: **không được dùng MDP để xây database công ty riêng.** Đó là
vi phạm điều khoản một cách trực diện.

### Rào cản phê duyệt

- Duyệt thủ công, không công bố tiêu chí
- Theo các nguồn cộng đồng: nhanh nhất ~4 tuần, trung bình ~4 tháng
- Rate limit cơ bản: khoảng 500 lượt tra cứu tổ chức/ngày (con số này từ nguồn
  thứ cấp, cần xác nhận lại)

### Kết luận về MDP

**Không dùng được cho use case của bạn.** MDP là công cụ cho các nền tảng
marketing quản lý quảng cáo/Page hộ khách hàng, không phải nguồn dữ liệu
prospecting.

---

## 3. LinkedIn Sales Insights (LSI) — ĐÃ KHAI TỬ

Đây là mất mát đáng tiếc nhất cho use case của bạn.

**LSI là gì:** sản phẩm Data-as-a-Service chính thức của LinkedIn, cho phép đội
Sales Ops truy cập dữ liệu công ty tổng hợp (headcount, tăng trưởng, phân bố
phòng ban…) dưới dạng bảng/export — tức là **đúng thứ bạn cần**, và hoàn toàn
hợp lệ.

**Tình trạng:** ngừng hoạt động từ **31/12/2024**.

Lý do LinkedIn đưa ra:

> *"…we have decided to discontinue services so that we can invest more in
> transforming the LinkedIn Sales Navigator experience to make it even more
> powerful."*

**Ý nghĩa:** LinkedIn đang chủ động thu hẹp mọi đường thoát dữ liệu dạng bảng,
dồn người dùng vào giao diện Sales Navigator — nơi dữ liệu chỉ được xem, không
được mang đi. Đây là xu hướng chiến lược, không phải sự cố tạm thời. **Đừng kỳ
vọng LinkedIn sẽ mở lại API trong tương lai gần.**

---

## 4. CRM Sync — đường thoát dữ liệu hợp lệ duy nhất

Đây là **cách duy nhất được LinkedIn chấp thuận** để đưa dữ liệu Sales Navigator
ra khỏi giao diện một cách tự động.

### Điều kiện

| Yêu cầu | Chi tiết |
|---|---|
| Gói thuê bao | **Advanced Plus** (giá theo hợp đồng riêng, LinkedIn không niêm yết) |
| CRM hỗ trợ | **Salesforce** hoặc **Microsoft Dynamics 365** — hết |
| Quản trị | Cần admin cấu hình ở cả 2 phía |
| Thời gian sync lần đầu | 24–48 giờ |

### Luồng dữ liệu

- **CRM → Sales Navigator:** import account/contact/lead vào SN
- **Sales Navigator → CRM:** ghi lại InMail, note, call log; đồng bộ lead/account

⚠️ Lưu ý về chiều dữ liệu: theo tài liệu, tính năng **Salesforce Import** chỉ
kéo dữ liệu *từ CRM vào SN*, không ghi ngược. Chiều "SN → CRM" chủ yếu là hoạt
động (activity) và bản ghi lead/account đã lưu — **không phải là "xuất toàn bộ
kết quả tìm kiếm"**.

### Đánh giá thực tế cho bạn

Đây **không** phải giải pháp thay thế cho "export kết quả search". Nó là công cụ
đồng bộ quy trình bán hàng. Nếu kỳ vọng của bạn là "chạy 1 search 2.500 công ty
rồi đổ hết sang hệ thống của tôi" → CRM Sync **không làm được việc đó**, kể cả
khi bạn nâng lên Advanced Plus.

Chi phí nâng cấp Advanced Plus + license Salesforce cho một mục tiêu mà nó không
thực sự đáp ứng → **thường không đáng**, trừ khi bạn vốn đã dùng Salesforce.

---

## 5. Data Licensing trực tiếp với LinkedIn

Về lý thuyết có tồn tại: LinkedIn ký thoả thuận cấp phép dữ liệu thương mại
theo từng trường hợp, đàm phán riêng qua kênh sales.

**Thực tế:** dành cho doanh nghiệp lớn, giá không niêm yết, quy trình dài. Không
phải lựa chọn khả thi cho một tool nội bộ quy mô nhóm nhỏ.

Điều đáng chú ý: điều khoản dịch vụ của LinkedIn nêu rõ khách hàng **không được
"trade, sell/re-sell or otherwise monetize"** dữ liệu LinkedIn nếu không có sự
đồng ý của LinkedIn. Nghĩa là nếu mô hình kinh doanh của bạn có bán lại dữ liệu
LinkedIn → bắt buộc phải có thoả thuận cấp phép, không có đường vòng.

---

## Tổng kết phần này

| Đường | Trạng thái | Dùng được cho bạn? |
|---|---|---|
| SNAP API | Đóng với đối tác mới | ❌ |
| Marketing Developer Platform | Mở nhưng cấm dùng để xây DB | ❌ |
| LinkedIn Sales Insights | Khai tử 31/12/2024 | ❌ |
| CRM Sync | Còn hoạt động, cần Advanced Plus + SF/Dynamics | ⚠️ Không giải quyết đúng nhu cầu |
| Data Licensing | Tồn tại, dành cho enterprise | ⚠️ Không thực tế |

➡️ **Kết luận: không có đường chính thức nào cho phép bạn lập trình lấy dữ liệu
công ty từ LinkedIn ở quy mô mong muốn.** Điều này định hình toàn bộ các phần
sau — mọi lựa chọn còn lại đều là *đánh đổi*, không có phương án "vừa tự động
vừa hoàn toàn hợp lệ với LinkedIn".
