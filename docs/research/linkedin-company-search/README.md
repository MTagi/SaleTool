# Survey: Các cách lấy dữ liệu công ty trên LinkedIn

> **Ngày khảo sát:** 13/08/2026
> **Cập nhật:** 14/08/2026 — viết lại mục 2 của [`01-duong-chinh-thuc.md`](01-duong-chinh-thuc.md)
> (LinkedIn Marketing API Program / MDP) với dữ liệu đối chiếu lại tới 14/08/2026.
> **Bối cảnh:** Bạn đang có tài khoản LinkedIn Sales Navigator và muốn tìm ra
> mọi con đường khả thi để lấy dữ liệu công ty (và liên hệ cấp cao) phục vụ
> dự án SaleTool / ABIM Sales Assistant.

---

## Đọc gì trước

| File | Nội dung |
|---|---|
| [`01-duong-chinh-thuc.md`](01-duong-chinh-thuc.md) | API chính thức của LinkedIn: SNAP, **Marketing API Program / MDP (viết lại 14/08/2026)**, LSI (đã khai tử), CRM sync |
| [`02-sales-navigator.md`](02-sales-navigator.md) | **Quan trọng nhất với bạn** — khai thác tối đa tài khoản đang có: bộ lọc, giới hạn thật, sự thật về export |
| [`03-nha-cung-cap-ben-thu-ba.md`](03-nha-cung-cap-ben-thu-ba.md) | Mua dữ liệu: Apollo, PDL, Coresignal, Bright Data, ZoomInfo, Cognism |
| [`04-scraping-tu-dong-hoa.md`](04-scraping-tu-dong-hoa.md) | Công cụ export/scrape (Evaboot, Wiza, PhantomBuster…) và rủi ro thật |
| [`05-phap-ly-tuan-thu.md`](05-phap-ly-tuan-thu.md) | Án lệ, xử phạt, GDPR, và **Luật BVDLCN Việt Nam có hiệu lực 01/01/2026** |
| [`06-nguon-thay-the.md`](06-nguon-thay-the.md) | Nguồn ngoài LinkedIn, gồm registry doanh nghiệp Việt Nam |
| [`07-khuyen-nghi-lo-trinh.md`](07-khuyen-nghi-lo-trinh.md) | Khuyến nghị cụ thể + lộ trình cho SaleTool |
| [`nguon-tham-khao.md`](nguon-tham-khao.md) | Toàn bộ nguồn đã dùng |

---

## Tóm tắt điều hành (đọc cái này là đủ nắm 80%)

### 1. Cánh cửa API chính thức đã đóng

**Sales Navigator API (SNAP) không nhận đối tác mới.** Tài liệu chính thức của
LinkedIn ghi rõ *"We are not currently accepting new partners for access to the
LinkedIn Sales Navigator API."* Không có form đăng ký, không có hàng chờ,
không có timeline. Chỉ đối tác cũ (chủ yếu là CRM lớn: Salesforce, HubSpot,
MS Dynamics) còn giữ quyền.

Tài khoản Sales Navigator trả phí của bạn **không đi kèm API key nào cả** —
đây là hiểu lầm phổ biến nhất. Nó là quyền truy cập giao diện web, không phải
quyền truy cập dữ liệu có lập trình.

**LinkedIn Sales Insights (LSI)** — sản phẩm DaaS chính thức từng cho phép lấy
dữ liệu công ty dạng bảng — **đã bị khai tử ngày 31/12/2024**.

### 2. Sales Navigator không có nút export

Trang trợ giúp chính thức của LinkedIn: *"We currently don't offer the option
to export account and lead information from Sales Navigator into a CSV or XLS
file."*

Đường thoát dữ liệu **duy nhất được LinkedIn cho phép** là **CRM sync**, và nó
đòi hỏi:
- Gói **Advanced Plus** (giá theo hợp đồng riêng, không niêm yết), **và**
- CRM là **Salesforce hoặc Microsoft Dynamics**

Nếu bạn đang dùng gói Core hoặc Advanced → **không có đường thoát dữ liệu hợp
lệ nào ngoài việc con người tự đọc và tự gõ lại.**

### 3. Mọi công cụ export tự động đều vi phạm ToS — không có ngoại lệ

Evaboot, Wiza, PhantomBuster, Captain Data, Lobstr, Scrupp… tất cả đều hoạt
động bằng cách trích xuất dữ liệu tự động từ phiên đăng nhập của bạn. Việc này
vi phạm LinkedIn User Agreement **bất kể** công cụ chạy "chậm như người thật"
hay không.

⚠️ Các blog của chính nhà cung cấp quảng cáo "zero ban risk" / "100% safe" —
**đây là marketing, không phải sự thật kỹ thuật hay pháp lý.** Rủi ro thật:
khoá tài khoản Sales Navigator (mất luôn tiền thuê bao), và về lý thuyết là
kiện vi phạm hợp đồng.

### 4. Án lệ nói gì: "public data ≠ tội hình sự" nhưng "vẫn là vi phạm hợp đồng"

Đây là điểm bị hiểu sai nhiều nhất:

| Vụ | Kết quả | Ý nghĩa thật |
|---|---|---|
| **hiQ v. LinkedIn** (2022) | Toà phúc thẩm số 9: scrape dữ liệu công khai **không** vi phạm CFAA (luật hình sự về truy cập máy tính) | ✅ Không bị tội hình sự… |
| **hiQ v. LinkedIn** (kết cục) | Toà sơ thẩm: hiQ **đã vi phạm hợp đồng** (User Agreement). hiQ trả **500.000 USD**, chịu lệnh cấm vĩnh viễn, **phá sản đóng cửa** | ❌ …nhưng vẫn thua và chết vì vi phạm hợp đồng |
| **LinkedIn v. Proxycurl** (2025) | LinkedIn kiện 24/01/2025 (N.D. Cal, 3:25-cv-00828). Proxycurl — 10 triệu USD ARR — **dàn xếp và đóng cửa tháng 7/2025** | ❌ Nhà cung cấp dữ liệu LinkedIn lớn nhất bị xoá sổ |
| **Meta v. Bright Data** (2024) | Bright Data **thắng**: scrape dữ liệu công khai khi **đã đăng xuất** không bị ToS ràng buộc | ✅ Có vùng an toàn — nhưng chỉ khi *không đăng nhập* |

**Bài học cốt lõi:** ranh giới không nằm ở "dữ liệu công khai hay không", mà
nằm ở **"bạn có đăng nhập vào tài khoản đã ký ToS hay không"**. Dùng tài khoản
Sales Navigator của bạn để trích xuất tự động = vi phạm hợp đồng, đúng kịch bản
đã giết hiQ.

### 5. Rủi ro pháp lý ở Việt Nam đang **tăng**, không giảm

**Luật Bảo vệ dữ liệu cá nhân (PDPL) có hiệu lực 01/01/2026.** Khác GDPR ở chỗ
rất quan trọng: Việt Nam theo hướng **lấy sự đồng ý (consent-centric)**, và
khái niệm "lợi ích chính đáng" **hẹp hơn GDPR nhiều**.

Nghĩa là lập luận "tôi làm B2B nên được miễn" — vốn đã yếu ở EU — **còn yếu hơn
ở Việt Nam**. Tên + chức danh + email công việc của một cá nhân **vẫn là dữ liệu
cá nhân**.

Tiền lệ xử phạt thật: **CNIL (Pháp) phạt KASPR 240.000 EUR** ngày 05/12/2024 vì
thu thập thông tin liên hệ của người dùng LinkedIn — buộc xoá 160 triệu bản ghi.
Mô hình KASPR gần như *y hệt* mô hình "extension lấy contact từ LinkedIn".

---

## Bảng so sánh 6 nhóm phương án

| # | Cách làm | Chi phí | Kỹ thuật | Rủi ro ToS | Rủi ro pháp lý | Quy mô | Hợp với bạn? |
|---|---|---|---|---|---|---|---|
| A | **SNAP API chính thức** | — | — | Không | Không | Cao | ❌ Cửa đã đóng |
| B | **Sales Navigator thủ công** (người đọc, tự nhập) | Đã trả rồi | Thấp | Không | Thấp | ~50–200 cty/ngày | ✅ **Nền tảng** |
| C | **CRM Sync (Advanced Plus)** | $$$ + cần Salesforce/Dynamics | Trung bình | Không | Thấp | Cao | ⚠️ Nếu đủ ngân sách |
| D | **Công cụ export SN** (Evaboot/Wiza…) | $ | Thấp | **Cao** | Trung bình | Cao | ⚠️ Bạn tự quyết |
| E | **Mua từ nhà cung cấp** (Apollo/Coresignal/PDL) | $$–$$$ | Trung bình | Không (của bạn) | Thấp–TB | Rất cao | ✅ **Nên có** |
| F | **Nguồn ngoài LinkedIn** (registry, web, Crunchbase) | $–$$ | Cao | Không | Thấp | Cao | ✅ Bổ sung tốt |

---

## Khuyến nghị ngắn gọn

**Kiến trúc 3 tầng** (chi tiết ở [`07-khuyen-nghi-lo-trinh.md`](07-khuyen-nghi-lo-trinh.md)):

1. **Tầng khám phá (discovery)** — dùng Sales Navigator đúng mục đích: bộ lọc
   account search rất mạnh (headcount growth, department headcount, revenue,
   hiring signal) để *tìm ra công ty nào đáng theo đuổi*. Đây là thứ SN làm tốt
   nhất và bạn đã trả tiền cho nó.

2. **Tầng làm giàu (enrichment)** — lấy dữ liệu có cấu trúc + thông tin liên hệ
   từ **nhà cung cấp có giấy phép** (Apollo / Coresignal / PDL). Đây là nơi
   trách nhiệm pháp lý chuyển sang nhà cung cấp, và là nơi bạn *nên* đổ tiền
   thay vì đổ vào công cụ scrape.

3. **Tầng đối chiếu (verification)** — với thị trường Việt Nam, đối chiếu với
   **Cổng thông tin đăng ký doanh nghiệp quốc gia** (dangkykinhdoanh.gov.vn) để
   xác thực pháp nhân, mã số thuế, trạng thái hoạt động — thứ LinkedIn **không**
   có.

**Điều nên tránh:** đừng xây tự động hoá trình duyệt trên chính tài khoản
Sales Navigator của bạn. Rủi ro mất tài khoản là thật và chi phí thay thế cao
hơn nhiều so với tiền tiết kiệm được.

---

## Ghi chú về độ tin cậy của khảo sát này

- ✅ **Đã xác minh chéo:** các mốc pháp lý, án lệ, ngày tháng (tôi phát hiện
  nhiều blog SEO ghi sai năm vụ Proxycurl — bản này dùng số hiệu vụ án gốc).
- ⚠️ **Giới hạn kỹ thuật:** môi trường chạy khảo sát này **chặn truy cập
  `linkedin.com` và `learn.microsoft.com`**, nên các trích dẫn tài liệu chính
  thức của LinkedIn đến từ nguồn thứ cấp trích lại nguyên văn. Khuyến nghị bạn
  tự mở link trong [`nguon-tham-khao.md`](nguon-tham-khao.md) để xác nhận lần
  cuối trước khi ra quyết định có ràng buộc hợp đồng.
- ⚠️ **Giá và số liệu coverage** của các nhà cung cấp thay đổi liên tục và phần
  lớn đến từ trang marketing của chính họ — hãy coi là con số tham khảo, phải
  hỏi báo giá thật.
- ❗ **Đây không phải tư vấn pháp lý.** Phần pháp lý tổng hợp từ nguồn công khai.
  Nếu định vận hành thương mại ở quy mô lớn, hãy hỏi luật sư về PDPL Việt Nam.
