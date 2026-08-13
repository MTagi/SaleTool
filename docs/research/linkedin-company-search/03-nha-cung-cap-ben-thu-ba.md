# 03 — Mua dữ liệu từ nhà cung cấp bên thứ ba

Đây là con đường **thực tế nhất** để có dữ liệu công ty + liên hệ ở quy mô lớn
mà không tự đặt mình vào rủi ro với LinkedIn.

**Nguyên tắc cốt lõi:** khi bạn mua dữ liệu, bạn chuyển phần lớn rủi ro thu thập
sang nhà cung cấp. Nhưng **không phải toàn bộ** — bạn vẫn chịu trách nhiệm về
cách *sử dụng* dữ liệu (xem [`05-phap-ly-tuan-thu.md`](05-phap-ly-tuan-thu.md)).

---

## ⚠️ Bài học Proxycurl: vì sao phải chọn nhà cung cấp cẩn thận

Trước tháng 7/2025, câu trả lời mặc định cho "API lấy dữ liệu LinkedIn" là
**Proxycurl**. Giờ thì không còn.

**Diễn biến:**
- **24/01/2025** — LinkedIn kiện Nubela Pte. Ltd. (công ty mẹ Proxycurl) tại Toà
  liên bang Bắc California, **vụ án số 3:25-cv-00828**
- Cáo buộc: tạo **hàng trăm nghìn tài khoản giả** để scrape hàng triệu profile,
  gồm cả **dữ liệu không công khai**, rồi bán lại qua API
- 6 nhóm khiếu kiện: vi phạm hợp đồng, lừa dối, vi phạm CFAA, luật cạnh tranh
  không lành mạnh California, Lanham Act, chiếm dụng
- **Giữa 2025** — dàn xếp
- **Tháng 7/2025** — Proxycurl đóng cửa hoàn toàn, dữ liệu bị xoá

**Quy mô mất mát:** Proxycurl có ~10 triệu USD doanh thu định kỳ hằng năm (ARR).
Không phải công ty nhỏ.

> 💡 **Bài học cho bạn:** nếu bạn xây SaleTool phụ thuộc vào một API dữ liệu
> LinkedIn duy nhất, bạn đang gánh **rủi ro nhà cung cấp biến mất qua đêm**.
> Kiến trúc provider-interface hiện tại của SaleTool (`CompanyContactProvider`)
> chính là biện pháp phòng vệ đúng đắn — hãy giữ nó.

**Tín hiệu leo thang khác trong 2025:**
- LinkedIn kiện **ProAPIs** (bị cáo buộc vận hành mạng lưới hàng triệu tài khoản
  giả, bán dữ liệu tới 15.000 USD/tháng)
- **Apollo.io và Seamless.ai bị gỡ LinkedIn Company Page** — dấu hiệu LinkedIn
  hành động đơn phương trước cả khi có vụ kiện công khai

---

## Bảng so sánh nhà cung cấp

| Nhà cung cấp | Thế mạnh | Giá tham khảo | Có API | Phù hợp |
|---|---|---|---|---|
| **Apollo.io** | Contact + sequencing + dialer, self-serve, giá minh bạch | Có gói free; trả phí từ ~$49/user/tháng | ✅ | Startup, đội nhỏ, muốn all-in-one |
| **Coresignal** | **Dữ liệu công ty & việc làm**, refresh hằng ngày–quý, bulk dataset | Pro từ ~$800/tháng | ✅ | **Dữ liệu firmographic quy mô lớn** |
| **People Data Labs** | DB người lớn nhất, enrichment | Pro từ ~$98/tháng | ✅ | Enrich profile người |
| **Bright Data** | Dataset LinkedIn mua sẵn, thắng kiện Meta & X | Theo bản ghi/GB | ✅ | Bulk dataset, quy mô rất lớn |
| **ZoomInfo** | Firmographic sâu, intent data, org chart | Hợp đồng năm, tối thiểu cao | ✅ | Doanh nghiệp lớn |
| **Cognism** | **Tuân thủ GDPR mạnh**, số di động EMEA, DNC screening | ~$15.000+/năm | ✅ | Thị trường EU, ưu tiên tuân thủ |
| **Explorium** | 150M+ công ty, 800M+ người | Liên hệ | ✅ | Enterprise |
| **Lusha / Kaspr** | Contact nhanh, extension | Rẻ | ✅ | ⚠️ Kaspr **đã bị CNIL phạt** |

> ⚠️ **Cảnh báo về số liệu:** giá và con số coverage ở trên phần lớn lấy từ
> trang marketing của chính nhà cung cấp hoặc blog so sánh (nhiều blog do đối thủ
> viết, có thiên vị rõ rệt — VD ZoomInfo viết bài so sánh Apollo vs Cognism).
> **Bắt buộc phải xin báo giá và bản dữ liệu mẫu thật** trước khi quyết định.

---

## Phân tích theo nhu cầu cụ thể của bạn

### Nếu ưu tiên = tìm CÔNG TY (firmographic)

**Coresignal** là lựa chọn phù hợp nhất về mặt định vị:
- Chuyên về company intelligence + job postings
- Refresh hằng ngày đến hàng quý (tuỳ dataset)
- Cung cấp cả API lẫn **bulk dataset** — nếu bạn muốn tự lưu về DB và query
  linh hoạt thì bulk dataset hợp lý hơn gọi API từng lần
- Giá khởi điểm ~$800/tháng — cao hơn Apollo nhưng đúng chuyên môn

**Bright Data** nếu cần quy mô rất lớn:
- Bán dataset công ty/profile đã thu thập sẵn, lọc theo địa lý/ngành/chức danh
- Giao dưới dạng JSON/CSV
- Điểm mạnh pháp lý: **đã thắng kiện Meta (01/2024) và X (05/2024)** — công ty
  scraping đầu tiên được toà Mỹ soi kỹ và thắng
- ⚠️ Lưu ý: chiến thắng đó dựa trên việc scrape **khi đã đăng xuất**, dữ liệu
  công khai. Việc họ tự nhận "fully GDPR/CCPA compliant" là **tuyên bố marketing
  của chính họ**, không phải phán quyết của toà.

### Nếu ưu tiên = tìm LIÊN HỆ CẤP CAO (đúng mục tiêu SaleTool)

**Apollo.io** — vẫn là lựa chọn thực dụng nhất cho đội nhỏ:
- Đã tích hợp sẵn trong SaleTool (`saletool/providers/apollo.py`)
- ~30M công ty, ~210M contact (theo số liệu công bố)
- Lọc theo `person_seniorities` — đúng thứ SaleTool cần
- Self-serve, có gói free để thử, giá minh bạch
- ⚠️ Rủi ro cần biết: Apollo bị gỡ LinkedIn Company Page năm 2025 → cho thấy
  quan hệ với LinkedIn căng thẳng. Không có nghĩa Apollo sắp sập, nhưng củng cố
  luận điểm **không nên phụ thuộc vào một nhà cung cấp duy nhất**.

**Cognism** — nếu bạn nhắm thị trường châu Âu:
- Xây sẵn tính năng tuân thủ GDPR: DNC screening (lọc danh sách không gọi),
  consent tracking
- Đây là điểm quan trọng nếu tệp khách hàng có người ở EU
- Giá cao (~$15.000+/năm) → chỉ hợp lý khi doanh thu tương xứng

### Nếu ưu tiên = thị trường Việt Nam

**Không nhà cung cấp quốc tế nào ở trên có coverage tốt cho Việt Nam.** Đây là
điểm mù lớn. Xem [`06-nguon-thay-the.md`](06-nguon-thay-the.md) để biết nguồn
dữ liệu doanh nghiệp Việt Nam đúng nghĩa.

---

## Câu hỏi bắt buộc phải hỏi nhà cung cấp

Trước khi ký hợp đồng, hỏi thẳng những câu này. Cách họ trả lời sẽ cho bạn biết
nhiều hơn cả tài liệu marketing:

### Về nguồn gốc dữ liệu
1. **Dữ liệu này lấy từ đâu?** (Yêu cầu cụ thể, không chấp nhận "public web")
2. Có scrape LinkedIn không? Nếu có, **có đăng nhập hay không đăng nhập?**
3. Có dùng tài khoản LinkedIn giả không? *(Đây chính là điều giết Proxycurl)*
4. Có thoả thuận cấp phép nào với LinkedIn không?

### Về pháp lý
5. Có **điều khoản bồi thường (indemnification)** nếu tôi bị kiện vì dùng dữ liệu
   của các bạn không? — ⚠️ **Đây là câu quan trọng nhất.** Nhà cung cấp tự tin về
   nguồn gốc dữ liệu sẽ sẵn sàng bồi thường. Ai né câu này là tín hiệu xấu.
6. Cơ sở pháp lý xử lý dữ liệu cá nhân là gì? (GDPR Art. 6)
7. Có cơ chế xử lý yêu cầu xoá dữ liệu (DSAR) không?
8. Có DNC/suppression list không?

### Về vận hành
9. Dữ liệu refresh bao lâu một lần?
10. Coverage thực tế ở **thị trường mục tiêu của tôi** là bao nhiêu? (Xin mẫu thật)
11. Chính sách nếu dữ liệu sai/lỗi thời?
12. Nếu các bạn ngừng hoạt động, tôi có được giữ dữ liệu đã tải không?

---

## Chiến lược đa nhà cung cấp (khuyến nghị)

Kiến trúc `CompanyContactProvider` của SaleTool đã cho phép điều này. Nên tận
dụng:

```
                    ┌─────────────────────┐
                    │  SearchCriteria     │
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
    ┌───────────────┐  ┌──────────────┐  ┌───────────────┐
    │ csv_import    │  │  apollo      │  │ coresignal    │
    │ (Sales Nav    │  │  (contact)   │  │ (firmographic)│
    │  thủ công)    │  │              │  │   — cần viết  │
    └───────┬───────┘  └──────┬───────┘  └───────┬───────┘
            └──────────────────┼──────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │  Hợp nhất + khử     │
                    │  trùng + chấm điểm  │
                    └─────────────────────┘
```

**Lợi ích:**
- Không nhà cung cấp nào sập được toàn bộ hệ thống của bạn
- Đối chiếu chéo → phát hiện dữ liệu sai
- Tối ưu chi phí: dùng nguồn rẻ trước, nguồn đắt chỉ để enrich phần thiếu

**Chi phí:** phức tạp hơn về khử trùng (dedupe) — cần khoá định danh chung
(domain công ty là khoá tốt nhất, tốt hơn tên công ty nhiều).
