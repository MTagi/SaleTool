# 05 — Pháp lý và tuân thủ

> ❗ **Miễn trừ:** đây là tổng hợp từ nguồn công khai để bạn nắm bức tranh, **không
> phải tư vấn pháp lý**. Nếu triển khai thương mại quy mô lớn, đặc biệt là có xử
> lý dữ liệu cá nhân người Việt Nam, hãy tham vấn luật sư.

---

## 1. Hai tầng rủi ro hoàn toàn khác nhau

Rất nhiều người gộp chung 2 thứ này, dẫn đến kết luận sai:

| | **Tầng 1: Quan hệ với LinkedIn** | **Tầng 2: Luật bảo vệ dữ liệu** |
|---|---|---|
| Nguồn ràng buộc | Hợp đồng (User Agreement) | Luật (GDPR, PDPL…) |
| Ai xử lý bạn | LinkedIn (khoá tài khoản, kiện dân sự) | Cơ quan nhà nước (phạt hành chính) |
| Mua dữ liệu từ bên thứ ba có thoát không? | ✅ **Có** — bạn không ký ToS nào | ❌ **Không** — bạn vẫn là bên xử lý dữ liệu |

➡️ **Điểm mấu chốt:** mua dữ liệu từ nhà cung cấp giải quyết **tầng 1** nhưng
**không giải quyết tầng 2**. Bạn vẫn phải tuân thủ luật bảo vệ dữ liệu cá nhân
khi *sử dụng* dữ liệu đó.

---

## 2. Án lệ then chốt

### hiQ Labs v. LinkedIn — vụ bị trích dẫn sai nhiều nhất

Đây là vụ mọi người hay viện dẫn để nói "scraping là hợp pháp". Sự thật phức tạp
hơn nhiều:

**Giai đoạn 1 (2022) — hiQ thắng về CFAA:**
Toà Phúc thẩm Liên bang Khu vực 9 phán quyết rằng scrape **dữ liệu công khai**
không vi phạm **CFAA** (Computer Fraud and Abuse Act — luật về truy cập máy tính
trái phép). Lý do: dữ liệu công khai thì không có "rào cản truy cập" để mà vượt.

✅ Đây là chiến thắng thật, và vẫn còn giá trị: **scraping dữ liệu công khai
không phải tội hình sự ở Mỹ.**

**Giai đoạn 2 (11–12/2022) — hiQ thua và chết:**
Toà sơ thẩm phán quyết hiQ **đã vi phạm User Agreement của LinkedIn**, vốn cấm
rõ ràng việc scrape profile và tạo danh tính giả. Kết cục:
- hiQ trả **500.000 USD** tiền bồi thường
- Chịu **lệnh cấm vĩnh viễn**: ngừng scraping, **xoá toàn bộ** mã nguồn, dữ liệu,
  thuật toán đã thu được
- **Công ty đóng cửa**

> 🎯 **Bài học chính xác từ hiQ:** "Không phạm tội hình sự" ≠ "được phép làm".
> Vi phạm hợp đồng đủ để giết một công ty. Và điều kiện tiên quyết của vi phạm
> hợp đồng là **bạn đã chấp nhận hợp đồng đó** — tức là **đã đăng nhập**.

### Meta v. Bright Data (01/2024) — vùng an toàn được xác lập

- **23/01/2024** — Thẩm phán Edward Chen ra phán quyết rút gọn **có lợi cho
  Bright Data**
- Nội dung then chốt: *"The Facebook and Instagram Terms do not bar **logged-off**
  scraping of public data; perforce it does not prohibit the sale of such public
  data."*
- **23/02/2024** — Meta rút đơn kiện

**X (Twitter) v. Bright Data (05/2024):** cũng bị bác. Toà cho rằng X không lập
luận được về việc truy cập trang công khai, và yêu cầu về sao chép dữ liệu công
khai bị luật bản quyền loại trừ (preempted).

> 🎯 **Ý nghĩa:** đây là **vùng an toàn duy nhất được toà Mỹ xác nhận rõ ràng** —
> scrape dữ liệu công khai **khi đã đăng xuất**. Từ khoá quyết định là
> ***logged-off***. Đăng nhập vào là bạn quay lại kịch bản hiQ.

### LinkedIn v. Proxycurl (2025) — LinkedIn phản công

- **24/01/2025** — kiện tại Toà liên bang Bắc California, **vụ 3:25-cv-00828**
- Cáo buộc: tạo **hàng trăm nghìn tài khoản giả**, scrape hàng triệu profile gồm
  **cả dữ liệu không công khai**, bán lại qua API
- 6 nhóm khiếu kiện, gồm **lừa dối (fraud)** — nghiêm trọng hơn hẳn vi phạm hợp
  đồng đơn thuần
- Dàn xếp giữa 2025; **tháng 7/2025 Proxycurl đóng cửa** (dù có ~10 triệu USD ARR)

> 🎯 **Yếu tố quyết định:** không phải "scraping" mà là **tài khoản giả** và **dữ
> liệu không công khai**. Hai thứ này đưa vụ việc từ tranh chấp hợp đồng sang cáo
> buộc gian lận.

### Tổng hợp: ranh giới thật nằm ở đâu

```
        AN TOÀN HƠN  ←─────────────────────────────→  NGUY HIỂM HƠN

   Mua dữ liệu     Scrape công khai      Extension trên      Tài khoản giả +
   có giấy phép    khi ĐÃ ĐĂNG XUẤT      tài khoản thật      dữ liệu không
                   (Bright Data ✅)      (hiQ ❌)            công khai
                                                             (Proxycurl ❌❌)
   ────────────────────────────────────────────────────────────────────────
   Không ToS       ToS không ràng buộc   Vi phạm hợp đồng    Gian lận + CFAA
```

---

## 3. Xử phạt hành chính: vụ KASPR

Đây là tiền lệ quan trọng nhất cho mô hình "extension lấy contact từ LinkedIn".

| | |
|---|---|
| **Ngày** | 05/12/2024 |
| **Cơ quan** | CNIL (Pháp) |
| **Mức phạt** | **240.000 EUR** |
| **Mô hình KASPR** | Extension Chrome trả phí, cho khách lấy thông tin liên hệ của người mà họ xem profile trên LinkedIn |
| **Quy mô DB** | ~160 triệu contact |

**Các vi phạm bị kết luận:**
1. Thu thập thông tin liên hệ của người dùng **kể cả khi họ đã giới hạn hiển thị**
2. Lưu trữ dữ liệu **quá thời hạn cần thiết**
3. **Không thông báo** kịp thời và minh bạch cho cá nhân
4. Xử lý **yêu cầu truy cập dữ liệu (DSAR) không đầy đủ**

**Chế tài kèm theo:** buộc ngừng thu thập dữ liệu của người đã giới hạn hiển thị,
và **xoá dữ liệu đã thu**. Hạn tuân thủ: 18/06/2025.

> 🎯 **Vì sao vụ này rất liên quan đến bạn:** nếu SaleTool (hoặc bất kỳ công cụ
> nào bạn dùng) thu thập contact từ LinkedIn theo cách tương tự, đây chính xác là
> mô hình đã bị phạt. Điểm số 1 đặc biệt quan trọng: **tôn trọng cài đặt hiển thị
> của người dùng** không phải tuỳ chọn.

---

## 4. GDPR — nếu bạn chạm đến dữ liệu người EU

### Dữ liệu B2B **vẫn là** dữ liệu cá nhân

Hiểu lầm phổ biến: *"Tôi làm B2B nên GDPR không áp dụng."* **Sai.** Tên, chức
danh, email công việc của một cá nhân xác định được → là dữ liệu cá nhân theo
GDPR.

### Cơ sở pháp lý: Lợi ích chính đáng (Art. 6(1)(f))

Với outreach lạnh, đây gần như luôn là cơ sở duy nhất khả dĩ. Phải vượt qua
**bài test 3 phần**:

| Test | Yêu cầu | Ứng dụng thực tế |
|---|---|---|
| **Purpose** (mục đích) | Có lý do kinh doanh chính đáng | Bán sản phẩm B2B liên quan cho đúng người ra quyết định — thường **đạt** |
| **Necessity** (cần thiết) | Xử lý phải cần thiết cho mục đích đó | ⚠️ Scrape **toàn bộ profile** sẽ **trượt**. Bạn chỉ cần: tên, chức danh, công ty, email công việc |
| **Balancing** (cân bằng) | Quyền lợi cá nhân không lấn át | Phụ thuộc mức độ xâm phạm; số điện thoại di động cá nhân rủi ro cao hơn nhiều |

### Nghĩa vụ Điều 14 — thường bị bỏ qua

Khi thu thập dữ liệu **từ nguồn không phải chính người đó** (tức là mọi trường
hợp mua/scrape dữ liệu), GDPR Điều 14 yêu cầu bạn **thông báo cho cá nhân rằng
bạn đang giữ dữ liệu của họ**, thường trong vòng **1 tháng**.

Thực tế: **hầu như không ai làm điều này.** Đây là lỗ hổng tuân thủ lớn nhất và
phổ biến nhất trong toàn ngành sales intelligence.

---

## 5. 🇻🇳 Việt Nam: Luật BVDLCN có hiệu lực 01/01/2026

**Đây là phần quan trọng nhất nếu bạn xử lý dữ liệu người Việt Nam** — và nhiều
người chưa cập nhật.

### Mốc pháp lý

| Mốc | Nội dung |
|---|---|
| 2023 | Nghị định 13/2023/NĐ-CP (PDPD) về bảo vệ dữ liệu cá nhân |
| **26/06/2025** | Quốc hội thông qua **Luật Bảo vệ dữ liệu cá nhân (PDPL)** |
| **01/01/2026** | **Luật có hiệu lực** |

### Khác biệt then chốt so với GDPR

> ⚠️ **Việt Nam theo hướng lấy sự đồng ý (consent-centric).** Sự đồng ý trước của
> chủ thể dữ liệu là cơ sở pháp lý chính, chỉ có một số ít trường hợp miễn trừ
> theo luật định.

**Nghị định 13 (PDPD) không công nhận cơ sở "lợi ích chính đáng"** như GDPR.

**Luật PDPL mới có dùng thuật ngữ "lợi ích chính đáng", nhưng phạm vi hẹp hơn
GDPR đáng kể** — theo phân tích của các hãng luật, nó chỉ áp dụng khi việc xử lý
dữ liệu là cần thiết để **ngăn chặn hành vi xâm phạm từ bên thứ ba**.

### Hệ quả thực tế cho bạn

| Kịch bản | GDPR (EU) | PDPL (Việt Nam) |
|---|---|---|
| Cold outreach B2B dựa trên "lợi ích chính đáng" | ⚠️ Khả thi nếu qua được 3-part test | ❌ **Rủi ro cao hơn nhiều** — cơ sở này gần như không dùng được cho marketing |
| Mua danh sách contact rồi gửi email lạnh | ⚠️ Vùng xám | ❌ **Rủi ro cao** nếu không có sự đồng ý |

➡️ **Kết luận thẳng thắn:** lập luận "làm B2B nên được miễn" vốn đã yếu ở EU,
**còn yếu hơn nhiều ở Việt Nam**. Nếu tệp khách hàng mục tiêu của bạn là doanh
nghiệp Việt Nam, đây là rủi ro cần đưa vào tính toán ngay từ đầu, không phải xử
lý sau.

**Hàm ý thiết kế cho SaleTool:**
- Nên tách bạch rõ giữa **dữ liệu công ty** (pháp nhân — rủi ro thấp hơn nhiều)
  và **dữ liệu liên hệ cá nhân** (rủi ro cao)
- Cân nhắc: dùng LinkedIn/Sales Navigator để tìm **công ty**, còn thông tin liên
  hệ thì lấy qua kênh có cơ sở pháp lý rõ ràng hơn (form đăng ký, danh bạ doanh
  nghiệp công bố công khai, hoặc nhà cung cấp có cam kết tuân thủ)

---

## 6. Checklist tuân thủ tối thiểu

Nếu bạn vận hành SaleTool có xử lý dữ liệu cá nhân:

### Thu thập
- [ ] Chỉ thu thập trường **thực sự cần** (tên, chức danh, công ty, email công việc)
- [ ] **Không** thu thập dữ liệu của người đã giới hạn hiển thị *(bài học KASPR)*
- [ ] Ghi lại **nguồn gốc** từng bản ghi (provenance) — cần khi bị hỏi
- [ ] Ghi lại **cơ sở pháp lý** cho từng loại xử lý

### Lưu trữ
- [ ] Đặt **thời hạn lưu trữ** và tự động xoá khi hết hạn *(KASPR bị phạt vì điều này)*
- [ ] Mã hoá dữ liệu nhạy cảm
- [ ] Kiểm soát truy cập theo vai trò

### Sử dụng
- [ ] Có cơ chế **opt-out / hủy đăng ký** trong mọi email outreach
- [ ] Duy trì **suppression list** (danh sách không liên hệ) và kiểm tra trước khi gửi
- [ ] Có quy trình xử lý **yêu cầu xoá dữ liệu** trong thời hạn luật định

### Minh bạch
- [ ] Có privacy notice mô tả nguồn dữ liệu
- [ ] Cân nhắc nghĩa vụ thông báo theo GDPR Điều 14
- [ ] Với dữ liệu người Việt Nam: rà soát lại cơ sở pháp lý theo PDPL

### Nhà cung cấp
- [ ] Có **điều khoản bồi thường (indemnification)** trong hợp đồng
- [ ] Có DPA (Data Processing Agreement)
- [ ] Đã hỏi rõ nguồn gốc dữ liệu bằng văn bản

---

## 7. Tóm tắt: 5 điều cần nhớ

1. **"Dữ liệu công khai" không phải lá chắn vạn năng.** Ranh giới thật là
   **đăng nhập hay không đăng nhập**.
2. **Vi phạm hợp đồng đủ để giết công ty** — hiQ là bằng chứng, không phải giả
   thuyết.
3. **Tài khoản giả biến vi phạm hợp đồng thành gian lận** — đây là thứ giết
   Proxycurl.
4. **Mua dữ liệu không miễn trừ nghĩa vụ bảo vệ dữ liệu cá nhân.**
5. **Việt Nam đang siết chặt, không nới lỏng.** PDPL hiệu lực 01/01/2026, hẹp
   hơn GDPR về "lợi ích chính đáng".
