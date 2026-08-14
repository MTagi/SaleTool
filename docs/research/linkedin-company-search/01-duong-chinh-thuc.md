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

## 2. LinkedIn Marketing API Program / Marketing Developer Platform (MDP)

*Viết lại và đối chiếu lại ngày **14/08/2026**. Xem ghi chú xác minh ở cuối mục.*

Đây là chương trình API mở nhất của LinkedIn — cũng là chương trình duy nhất mà
một công ty bình thường còn có thể xin vào được. Nhưng nó **không phải là nguồn
dữ liệu prospecting**, và điều đó được ghi thẳng trong điều khoản chứ không phải
là suy diễn.

Tài liệu chính thức nằm trên Microsoft Learn (`learn.microsoft.com/linkedin/marketing/`)
vì LinkedIn thuộc Microsoft; `developer.linkedin.com` chỉ còn là cổng đăng ký ứng
dụng và cổng nộp hồ sơ xin quyền.

### 2.1. Tình trạng phiên bản (tính đến 08/2026)

MDP đã chuyển sang API có phiên bản từ **tháng 6/2022**, endpoint gốc là
`https://api.linkedin.com/rest/`:

| Hạng mục | Trạng thái 08/2026 |
|---|---|
| Header bắt buộc | `Linkedin-Version: YYYYMM` (vd `202608`) |
| Không gửi header | **Lỗi** — LinkedIn *không* mặc định về bản mới nhất |
| Nhịp phát hành | Hàng tháng |
| Thời gian hỗ trợ | Tối thiểu **1 năm** kể từ ngày phát hành (Talent API là 2 năm) |
| Đã sunset | `202503`, `202506`, `202507` và các bản cũ hơn |
| Bản tài liệu mới nhất quan sát được | `li-lms-2026-07` |

Hệ quả thực tế: bất kỳ tích hợp nào cũng phải **được bảo trì liên tục**. Code
viết một lần rồi để đó sẽ chết trong vòng ~12 tháng khi phiên bản bị sunset. Với
một tool nội bộ, đây là chi phí định kỳ chứ không phải chi phí một lần.

### 2.2. Hai bậc truy cập và rào chắn đầu vào

| Bậc | Cách có được | Năng lực |
|---|---|---|
| **Development** | Mặc định khi app được duyệt vào một product | Hạn chế số lượt gọi, dùng để dựng và test; có ~12 tháng để nâng bậc |
| **Standard** | Nộp form riêng + **quay video màn hình ứng dụng** + cung cấp tài khoản test | Đầy đủ, không giới hạn tính năng |

Điều kiện tiên quyết trước cả hai bậc:

- Phải là **pháp nhân đã đăng ký**, không mở cho cá nhân developer
- Phải có **LinkedIn Page đã xác minh**, và **super admin của Page đó** phải xác
  minh chính ứng dụng của bạn — không có Page xác minh thì không có quyền
- LinkedIn thẩm định **công ty**, không chỉ thẩm định app

Các product mà developer được duyệt có thể xin: Advertising API, Community
Management API, Events Management API, Lead Sync API, Conversions API. **Không có
product nào tên kiểu "Company Data" hay "Firmographics".**

### 2.3. Organization API cho gì — và giấu gì

| API | Phạm vi thực tế |
|---|---|
| `Organization Lookup` | Tra cứu theo **id**, **vanityName**, hoặc **emailDomain**<br>vd: `GET /organizations?q=vanityName&vanityName=microsoft` |
| `Organization Search` | ⚠️ **Chỉ mở cho một số developer được chọn** — không xin tự phục vụ được |
| Analytics / Ads | Chỉ dữ liệu của **chính tài khoản quảng cáo của bạn** |
| Page management | Chỉ Page **bạn là quản trị viên** |

Điểm đắt giá nhất nằm ở đây. Khi bạn **không** có vai trò ADMINISTRATOR của tổ
chức đó, response chỉ trả về đúng các trường:

```
id, name, localizedName, localizedWebsite, vanityName, logoV2,
locations, primaryOrganizationType
```

Tức là **không có** `employee count`, **không có** ngành nghề, **không có** tăng
trưởng nhân sự — chính xác là ba trường mà tool này cần để lọc công ty mục tiêu.
Bạn nhận được tên, website và logo: những thứ mà việc scrape chính website công
ty (bước enrich trong tool) đã cho bạn rồi, còn rẻ hơn.

Ngoài ra `Organization Lookup` **không hỗ trợ ký tự đại diện và toán tử boolean**
(`*`, `?`, `AND`, `OR`). Nó là *lookup*, không phải *search* — bạn phải biết
trước công ty là ai thì mới tra được. Đúng thứ tự ngược với nhu cầu "tìm ra danh
sách công ty phù hợp".

### 2.4. Giới hạn thời gian lưu trữ — điều khoản giết chết use case

Đây là điều khoản quyết định, nặng hơn cả chuyện thiếu trường dữ liệu:

| Loại dữ liệu | Được lưu tối đa |
|---|---|
| Member profile data | **24 giờ** |
| Member social activity | **48 giờ** |
| Organization-level social activity | **6 tuần** |
| Organization-level social activity (tổ chức đó đã tự xác thực với app của bạn) | tối đa **6 tháng** |

Kèm theo:
- Khi nhiều mốc cùng áp dụng thì **mốc ngắn nhất thắng**
- Không còn nhu cầu dùng nữa thì phải **xoá trong vòng 10 ngày**
- Chấm dứt tham gia chương trình thì phải **xoá toàn bộ member data ngay lập tức**

Một tool prospecting về bản chất là *cơ sở dữ liệu bền*. Trần 24 giờ cho dữ liệu
người biến việc "lưu danh sách liên hệ cấp cao để đội sales dùng dần" thành vi
phạm ngay từ thiết kế — không phải vi phạm do dùng sai.

### 2.5. Restricted uses — cấm đích danh chính việc bạn đang làm

LinkedIn liệt kê riêng một trang "Restricted Uses of LinkedIn Marketing APIs and
Data". Nội dung, tóm tắt:

> Member data **không được** dùng cho mục đích quảng cáo, bán hàng hoặc tuyển
> dụng — *bao gồm việc nhận diện khách hàng tiềm năng (sales/marketing prospects),
> tạo lead, làm giàu dữ liệu khách hàng trong CRM hoặc marketing automation, xây
> danh sách audience, target quảng cáo, account-based marketing, hay gửi tin nhắn
> hàng loạt.*

Và:

> Member data **không được** kết hợp với dữ liệu của bạn, dữ liệu LinkedIn khác,
> hay dữ liệu bên thứ ba để *tạo, bổ sung, xác minh hoặc nối thêm vào* user
> profile, lead, hay bảng tham chiếu.

Thêm nữa: member data **không được xuất, phân phối hay chuyển ra khỏi ứng dụng
của bạn — kể cả cho chính khách hàng của bạn.**

Riêng với dữ liệu tổ chức, điều khoản Marketing API giới hạn:

> *Nếu bạn nhận được dữ liệu profile của tổ chức từ một Page — gồm logo, địa
> điểm, ngành, quy mô — bạn chỉ được sử dụng và hiển thị dữ liệu đó thông qua
> Marketing Application của bạn để phục vụ đúng Marketing Services mà dữ liệu
> đó được cấp cho.*

Nói cách khác: **không được dùng MDP để xây database công ty riêng.** Đây không
phải vùng xám — đoạn cấm ở trên mô tả gần như nguyên văn use case của tool này.

### 2.6. Rào cản phê duyệt và rate limit

⚠️ *Các con số trong mục này đến từ nguồn thứ cấp/cộng đồng, chưa xác minh được
với tài liệu gốc — hãy coi là ước lượng bậc độ lớn, không phải cam kết.*

- Duyệt thủ công, không công bố tiêu chí chấm
- Nhanh nhất ~4 tuần, trung bình ~4 tháng
- Rate limit cơ bản: khoảng **500 lượt tra cứu tổ chức/ngày**; app đã được duyệt
  đầy đủ có thể lên tới ~100.000 lượt gọi/ngày

Thay đổi gần đây đáng ghi nhận (không ảnh hưởng use case này nhưng cho thấy nhịp
thay đổi của nền tảng):
- **Từ 15/05/2026:** hỗ trợ developer chuyển hẳn sang Developer Support Request
  Form, không còn kênh cũ
- **07/2026:** `adCampaigns` — `creativeSelection` mặc định thành `OPTIMIZED` cho
  `SPONSORED_INMAILS` và `LEAD_GENERATION` (thuần quảng cáo)

### 2.7. Kết luận về MDP

**Không dùng được cho use case của bạn** — và lý do đã đổi so với cách hiểu phổ
biến. Vấn đề không phải "khó xin quyền". Kể cả khi bạn xin được Standard tier:

1. `Organization Search` vẫn không mở → không tìm được công ty theo tiêu chí
2. `Organization Lookup` không có wildcard/boolean → phải biết trước công ty
3. Không có ADMINISTRATOR role → không có employee count, ngành, tăng trưởng
4. Trần lưu trữ 24 giờ → không được giữ dữ liệu người
5. Restricted uses → cấm đích danh prospecting và làm giàu CRM

Ba rào đầu khiến MDP *không làm được việc*; hai rào cuối khiến nó *không được
phép làm việc đó* kể cả nếu làm được. MDP là công cụ cho các nền tảng marketing
quản lý quảng cáo/Page hộ khách hàng, không phải nguồn dữ liệu prospecting.

### ⚠️ Ghi chú xác minh (14/08/2026)

Môi trường soạn tài liệu này **bị proxy chặn truy cập trực tiếp** vào
`learn.microsoft.com` và `developer.linkedin.com` (`EGRESS_BLOCKED`), nên nội
dung trên được dựng lại từ **trích đoạn tài liệu gốc thu được qua công cụ tìm
kiếm** rồi đối chiếu chéo giữa nhiều nguồn. Mức tin cậy:

| Nội dung | Mức tin cậy |
|---|---|
| Versioning, header bắt buộc, cửa sổ hỗ trợ 1 năm | **Cao** — khớp trích đoạn trang `versioning` (`li-lms-2026-07`) |
| Bậc Development/Standard, yêu cầu screen recording + Page đã xác minh | **Cao** — khớp trích đoạn trang `marketing-tiers` (`li-lms-2026-06`) |
| Danh sách trường trả về khi không có ADMINISTRATOR role | **Cao** — khớp trích đoạn trang `organization-lookup-api` (`li-lms-2026-04`) |
| Mốc lưu trữ 24h / 48h / 6 tuần / 6 tháng | **Cao** — khớp trích đoạn trang `data-storage-requirements` (`li-lms-2026-04`) |
| Restricted uses (cấm prospecting, cấm append CRM) | **Cao** — khớp trích đoạn trang `restricted-use-cases` (`li-lms-2026-05`) |
| Danh sách phiên bản đã sunset | **Trung bình** — tổng hợp từ nhiều nguồn, chưa đọc được bảng sunset đầy đủ |
| Rate limit 500/ngày, timeline duyệt 4 tuần–4 tháng | **Thấp** — chỉ nguồn thứ cấp |

Trước khi ra quyết định thương mại dựa trên mục này, nên mở lại hai trang gốc từ
một máy không bị chặn:
`learn.microsoft.com/en-us/linkedin/marketing/restricted-use-cases` và
`learn.microsoft.com/en-us/linkedin/marketing/data-storage-requirements`.

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
| Marketing Developer Platform | Còn mở (08/2026), nhưng thiếu trường dữ liệu cần + cấm đích danh prospecting, trần lưu trữ 24h | ❌ |
| LinkedIn Sales Insights | Khai tử 31/12/2024 | ❌ |
| CRM Sync | Còn hoạt động, cần Advanced Plus + SF/Dynamics | ⚠️ Không giải quyết đúng nhu cầu |
| Data Licensing | Tồn tại, dành cho enterprise | ⚠️ Không thực tế |

➡️ **Kết luận: không có đường chính thức nào cho phép bạn lập trình lấy dữ liệu
công ty từ LinkedIn ở quy mô mong muốn.** Điều này định hình toàn bộ các phần
sau — mọi lựa chọn còn lại đều là *đánh đổi*, không có phương án "vừa tự động
vừa hoàn toàn hợp lệ với LinkedIn".
