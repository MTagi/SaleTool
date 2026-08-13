# 04 — Công cụ scraping / tự động hoá: cách hoạt động và rủi ro thật

> ⚠️ **Phần này mang tính khảo sát để bạn hiểu bức tranh đầy đủ và tự ra quyết
> định có thông tin. Tôi không khuyến nghị triển khai các cách trong file này
> trên tài khoản Sales Navigator của bạn** — lý do được giải thích cụ thể ở dưới.

---

## 1. Ba kiến trúc kỹ thuật khác nhau

Không phải "scraper" nào cũng giống nhau. Sự khác biệt về kiến trúc quyết định
loại rủi ro bạn gánh:

### A. Extension trình duyệt (Evaboot, Wiza, Scrupp, Clura…)

**Cách hoạt động:** cài extension Chrome, extension đọc DOM của trang Sales
Navigator **trong phiên đăng nhập của chính bạn**, trích xuất và xuất ra CSV.

| | |
|---|---|
| ✅ Ưu | Chạy ở tốc độ duyệt web bình thường → khó bị phát hiện hơn; dữ liệu đúng như bạn thấy |
| ❌ Nhược | **Vẫn vi phạm ToS**; rủi ro dồn vào **tài khoản cá nhân của bạn**; phải mở máy, mở trình duyệt |
| 💰 Giá | Evaboot ~$39–699/tháng + **bắt buộc có Sales Navigator ~$79–100/tháng** |

⚠️ **Bẫy chi phí Evaboot:** giá niêm yết không gồm 2 thứ — (1) thuê bao Sales
Navigator bắt buộc, (2) cơ chế tiêu **2 credit cho mỗi lead**, tức số lead thực
tế chỉ bằng **một nửa** con số credit quảng cáo.

### B. Cloud automation (PhantomBuster, Captain Data, TexAu…)

**Cách hoạt động:** bạn đưa **session cookie LinkedIn** của mình cho dịch vụ,
họ chạy automation từ server của họ.

| | |
|---|---|
| ✅ Ưu | Chạy 24/7, không cần mở máy; workflow phức tạp |
| ❌ Nhược | **Rủi ro cao nhất.** Giao cookie = giao quyền truy cập tài khoản. IP datacenter dễ bị nhận diện. **Rủi ro kép:** nếu LinkedIn chặn cả nền tảng đó, toàn bộ người dùng bị cắt cùng lúc |
| 💰 Giá | Từ ~$69/tháng |

⚠️ **Rủi ro nền tảng có tiền lệ thật:** đã có trường hợp LinkedIn thu hồi quyền
truy cập của cả một nền tảng automation, khiến toàn bộ khách hàng mất dịch vụ
ngay lập tức.

### C. Scraping ẩn danh, không đăng nhập (Bright Data…)

**Cách hoạt động:** truy cập trang công khai **mà không đăng nhập**, dùng proxy
dân cư.

| | |
|---|---|
| ✅ Ưu | **Vị thế pháp lý mạnh nhất** — đây chính là mô hình Bright Data đã thắng kiện Meta và X. Không có tài khoản nào để mất |
| ❌ Nhược | Dữ liệu **nghèo hơn nhiều** — không đăng nhập thì không thấy phần lớn nội dung Sales Navigator; hạ tầng proxy phức tạp/tốn kém |
| 💰 Giá | Theo dung lượng/bản ghi |

> 💡 **Điểm mấu chốt pháp lý:** khác biệt lớn nhất giữa C và A/B **không phải
> tốc độ**, mà là **có đăng nhập hay không**. Khi đăng nhập, bạn đang hành động
> dưới một hợp đồng (User Agreement) mà bạn đã chấp nhận → vi phạm hợp đồng.
> Khi không đăng nhập, toà (Meta v. Bright Data) đã phán rằng ToS không ràng
> buộc bạn. **Đây là ranh giới quan trọng nhất trong toàn bộ khảo sát này.**

---

## 2. Bảng công cụ phổ biến

| Công cụ | Loại | Cần Sales Nav? | Giá tham khảo | Ghi chú |
|---|---|---|---|---|
| **Evaboot** | Extension | ✅ Bắt buộc | $39–699/th + SN | Chuyên export Sales Nav, có làm sạch dữ liệu |
| **Wiza** | Extension | ✅ Bắt buộc | Từ $49/th | Export miễn phí, tính tiền theo email tìm được |
| **Scrupp** | Extension | ✅ | Rẻ hơn Evaboot | Định vị là "Evaboot alternative" |
| **PhantomBuster** | Cloud | ❌ | Từ ~$69/th | Nhiều workflow, **rủi ro cao** |
| **Captain Data** | Cloud | ❌ | $$$ | Thiên về enterprise workflow |
| **Clay** | Nền tảng enrich | ❌ | Từ ~$149/th | Điều phối nhiều nguồn, không tự scrape LinkedIn là chính |
| **Lobstr** | Cloud | ❌ | $ | Scraper chung |
| **Findymail / Prospeo / Dropcontact** | Tìm email | ❌ | $ | Chỉ enrich email, **không scrape LinkedIn** → an toàn hơn |

**Quan sát đáng chú ý:** chỉ **Evaboot và Wiza** bắt buộc phải có Sales
Navigator. Các công cụ còn lại (Apollo, Findymail, Lusha, Kaspr, Clay, Cognism,
PhantomBuster) hoạt động độc lập — nghĩa là **bạn không cần Sales Navigator để
dùng chúng**, và ngược lại, giá trị Sales Navigator của bạn nằm ở khâu *khám
phá*, không phải khâu *lấy dữ liệu*.

---

## 3. LinkedIn phát hiện tự động hoá bằng cách nào

Hiểu cơ chế này để đánh giá đúng rủi ro (chứ không phải để né tránh):

LinkedIn **không** chỉ đếm số hành động. Họ phân tích **mẫu hành vi**:

| Tín hiệu | Giải thích |
|---|---|
| **Thiếu hành vi phụ trợ** | Người thật có di chuột, cuộn trang, dừng đọc. Bot dán nội dung trong 0,01 giây mà không có các hành vi đó |
| **Thay đổi nhịp độ đột ngột** | Tài khoản đang dùng 20 lượt/ngày bỗng nhảy lên 500 |
| **Đều đặn phi tự nhiên** | Chính xác 45 giây/hành động, chạy 24/7 không nghỉ |
| **Bất thường về phiên** | Đăng nhập từ IP datacenter, nhiều địa điểm cùng lúc |
| **Dấu vân tay trình duyệt** | Headless browser, thiếu thuộc tính trình duyệt thật |

> ⚠️ **Điểm nhiều người bỏ qua:** ngay cả khi bạn tuân thủ "giới hạn an toàn"
> mà các blog khuyên, tài khoản vẫn có thể bị gắn cờ — vì thuật toán nhìn
> **hình dạng hành vi**, không phải chỉ con số tuyệt đối.

---

## 4. Đánh giá phê phán các tuyên bố của nhà cung cấp

Trong quá trình khảo sát, tôi gặp rất nhiều tuyên bố kiểu:

> *"Chrome extensions chạy ở tốc độ người thật (X, Y) mang **zero account ban
> risk** — LinkedIn chỉ thấy hành vi người dùng bình thường."*
>
> *"Công cụ Z có tỷ lệ block chỉ 12%."*

**Đánh giá của tôi — hãy hoài nghi:**

1. **Nguồn thiên vị.** Các con số "block rate" này gần như luôn đến từ blog của
   chính công ty bán công cụ, hoặc từ đối thủ so sánh. Không có bên thứ ba độc
   lập nào kiểm chứng.

2. **"Zero risk" là bất khả về mặt logic.** Không ai có thể đảm bảo LinkedIn
   không thay đổi thuật toán phát hiện vào ngày mai.

3. **Nhầm lẫn giữa "bị bắt" và "vi phạm".** Kể cả tỷ lệ bị phát hiện thật sự
   thấp, hành vi vẫn **vi phạm hợp đồng**. hiQ Labs không bị "ban tài khoản" —
   họ bị **kiện ra toà**, thua, trả 500.000 USD và đóng cửa công ty.

4. **Rủi ro không đối xứng.** Lợi ích: tiết kiệm vài giờ nhập liệu. Thiệt hại:
   mất tài khoản + mạng lưới + (trường hợp xấu) trách nhiệm pháp lý. Đây không
   phải phép đánh đổi cân bằng.

---

## 5. Nếu bạn vẫn quyết định dùng công cụ export

Đây là quyết định của bạn — tôi tôn trọng. Nếu chọn hướng này, đây là cách giảm
thiệt hại:

### Nguyên tắc giảm rủi ro

1. **Không bao giờ dùng tài khoản LinkedIn chính/cá nhân.** Nếu mất, bạn mất cả
   mạng lưới nghề nghiệp nhiều năm.
2. **Ưu tiên extension hơn cloud.** Không giao session cookie cho bên thứ ba.
3. **Tuyệt đối không tạo tài khoản giả.** Đây chính xác là hành vi khiến LinkedIn
   kiện Proxycurl và ProAPIs — chuyển từ "vi phạm hợp đồng" sang cáo buộc
   **gian lận (fraud)**, mức độ nghiêm trọng hoàn toàn khác.
4. **Giữ khối lượng thấp và không đều.** Tránh chạy 24/7.
5. **Dừng ngay khi có dấu hiệu cảnh báo** (xem [`02-sales-navigator.md`](02-sales-navigator.md) mục 7).
6. **Chỉ lấy trường dữ liệu thực sự cần.** Tên, chức danh, công ty. Không lấy
   toàn bộ profile — vừa giảm rủi ro, vừa đúng nguyên tắc *tối thiểu hoá dữ liệu*
   của GDPR/PDPL.
7. **Có kế hoạch B.** Giả định tài khoản sẽ mất vào một ngày nào đó.

### Điều tuyệt đối không nên làm

- ❌ Tạo/mua tài khoản LinkedIn giả
- ❌ Bán lại dữ liệu lấy từ LinkedIn (vi phạm điều khoản dịch vụ trực diện, và là
  thứ biến bạn thành mục tiêu kiện tụng thay vì chỉ bị khoá tài khoản)
- ❌ Thu thập dữ liệu của người đã **giới hạn hiển thị** — đây chính là điều
  khiến KASPR bị CNIL phạt 240.000 EUR
- ❌ Đưa cookie phiên cho dịch vụ không rõ ràng

---

## 6. Kết luận phần này

| Kiến trúc | Rủi ro tài khoản | Rủi ro pháp lý | Chất lượng dữ liệu | Khuyến nghị |
|---|---|---|---|---|
| Extension trên tài khoản của bạn | **Cao** | Trung bình | Cao | ⚠️ Cân nhắc kỹ |
| Cloud automation (giao cookie) | **Rất cao** | Trung bình | Cao | ❌ Không nên |
| Scrape ẩn danh không đăng nhập | Không có | **Thấp nhất** | Thấp | ✅ Nhưng dữ liệu nghèo |
| **Mua từ nhà cung cấp** | Không có | Thấp–TB | Cao | ✅ **Tốt nhất** |
| **Human-in-the-loop** | Không có | Thấp | Cao | ✅ **An toàn nhất** |

➡️ Khi so sánh trực diện: **tiền bỏ ra mua dữ liệu từ nhà cung cấp có giấy phép
gần như luôn rẻ hơn kỳ vọng thiệt hại từ việc mất tài khoản Sales Navigator + rủi
ro pháp lý.** Đó là lý do khuyến nghị của khảo sát này nghiêng về hướng mua dữ
liệu, không phải tự scrape.
