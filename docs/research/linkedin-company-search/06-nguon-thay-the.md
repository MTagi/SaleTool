# 06 — Nguồn dữ liệu công ty ngoài LinkedIn

LinkedIn không phải nguồn duy nhất, và với một số loại dữ liệu thì **nó còn là
nguồn tệ**. Phần này liệt kê các nguồn thay thế/bổ sung — đặc biệt quan trọng
cho thị trường Việt Nam, nơi LinkedIn có coverage yếu.

---

## 1. Điểm mù của LinkedIn

LinkedIn **không có** những dữ liệu này, dù chúng rất quan trọng cho B2B:

| Dữ liệu | LinkedIn | Nguồn đúng |
|---|---|---|
| Mã số thuế / mã doanh nghiệp | ❌ | Registry quốc gia |
| Tình trạng pháp lý (đang hoạt động / giải thể) | ❌ | Registry quốc gia |
| Vốn điều lệ | ❌ | Registry quốc gia |
| Người đại diện pháp luật | ❌ | Registry quốc gia |
| Báo cáo tài chính | ❌ | Registry / nhà cung cấp tài chính |
| Địa chỉ trụ sở chính thức | ⚠️ Tự khai, hay sai | Registry quốc gia |
| Cơ cấu sở hữu | ❌ | Registry / OpenCorporates |

**Và điểm mù lớn nhất:** ở Việt Nam, **rất nhiều doanh nghiệp SME không có
LinkedIn Company Page** hoặc có nhưng bỏ hoang. Nếu chỉ dựa vào LinkedIn, bạn
đang bỏ sót phần lớn thị trường nội địa.

---

## 2. 🇻🇳 Nguồn dữ liệu doanh nghiệp Việt Nam

### A. Cổng thông tin đăng ký doanh nghiệp quốc gia (nguồn gốc)

| | |
|---|---|
| **URL** | `dangkykinhdoanh.gov.vn` |
| **Cơ quan** | Bộ Kế hoạch & Đầu tư (nay thuộc Bộ Tài chính sau sáp nhập) |
| **Chi phí** | Tra cứu cơ bản **miễn phí**, không cần tài khoản |
| **API công khai** | ❌ **Không có** |
| **Giao diện** | Chỉ tiếng Việt |

**Đây là nguồn chân lý (source of truth)** cho pháp nhân Việt Nam: mã số doanh
nghiệp, tên chính thức, địa chỉ, người đại diện, ngành nghề đăng ký, tình trạng
hoạt động.

**Hạn chế cho tự động hoá:** không có API → muốn dùng ở quy mô phải qua nhà cung
cấp trung gian (mục B) hoặc tra cứu thủ công.

### B. Nhà cung cấp dữ liệu doanh nghiệp Việt Nam (có API)

| Nhà cung cấp | Mô tả | Ghi chú |
|---|---|---|
| **CompanyData.com** | ~1.83 triệu pháp nhân VN, API tra cứu theo mã DN/tên/địa chỉ, JSON 50+ trường, nguồn từ Sở KH&ĐT | Có API — phù hợp tích hợp |
| **InfobelPRO** | 1.8M+ công ty VN, lấy trực tiếp từ registry, giao qua API hoặc bulk | Có bulk delivery |
| **AsiaVerify** | Kết nối trực tiếp Cổng ĐKKD quốc gia + Tổng cục Thuế, real-time | Định vị KYB/thẩm định |
| **Companies House Vietnam** (`companieshouse.vn`) | Dữ liệu first-party từ registry VN | |

> ⚠️ Các con số coverage trên lấy từ trang marketing của chính nhà cung cấp. Hãy
> xin dữ liệu mẫu để kiểm chứng chất lượng thật.

### C. Nguồn Việt Nam khác

- **Tổng cục Thuế** — tra cứu mã số thuế, tình trạng hoạt động
- **Sàn chứng khoán HOSE/HNX** — báo cáo tài chính công ty niêm yết (chất lượng
  rất cao, miễn phí)
- **Cổng đấu thầu quốc gia** (`muasamcong.mpi.gov.vn`) — nếu bán cho khu vực công,
  đây là mỏ vàng: ai đang mua gì, ngân sách bao nhiêu
- **VietnamWorks / TopCV / ITviec** — tin tuyển dụng = tín hiệu tăng trưởng và
  tech stack (tương tự "hiring signal" của Sales Navigator nhưng phủ SME VN tốt hơn)

---

## 3. Nguồn quốc tế

### Registry và dữ liệu mở

| Nguồn | Phạm vi | Chi phí |
|---|---|---|
| **OpenCorporates** | Registry 140+ quốc gia, dữ liệu mở | Free tier + API trả phí |
| **GLEIF (LEI)** | Mã định danh pháp nhân toàn cầu | **Miễn phí hoàn toàn** |
| **EU Business Registers** | Registry các nước EU | Tuỳ nước |
| **SEC EDGAR** | Công ty niêm yết Mỹ, filing đầy đủ | **Miễn phí** |
| **UK Companies House** | Anh, có API tốt | **Miễn phí** |

### Dữ liệu startup / đầu tư

| Nguồn | Thế mạnh | Chi phí |
|---|---|---|
| **Crunchbase** | Vòng gọi vốn, nhà đầu tư, tin tức | API từ ~$49/tháng |
| **PitchBook** | Sâu về PE/VC | $$$ enterprise |
| **Tracxn** | Coverage châu Á tốt hơn Crunchbase | $$ |

> 💡 **Tín hiệu vàng:** công ty vừa gọi vốn = có ngân sách + đang mở rộng. Đây
> thường là tín hiệu mua mạnh hơn cả headcount growth.

### Dữ liệu công nghệ (technographic)

| Nguồn | Mô tả |
|---|---|
| **BuiltWith** | Công nghệ website đang dùng |
| **Wappalyzer** | Tương tự, có API |
| **HG Insights** | Technographic cấp doanh nghiệp |

Hữu ích nếu sản phẩm của bạn tích hợp/thay thế một công nghệ cụ thể.

### Trực tiếp từ web công ty

Thường bị đánh giá thấp nhưng rất hiệu quả và **rủi ro pháp lý thấp nhất**:

| Trang | Dữ liệu lấy được |
|---|---|
| `/about`, `/gioi-thieu` | Mô tả, quy mô, năm thành lập |
| `/team`, `/leadership` | **Ban lãnh đạo — chính thứ SaleTool cần**, và do công ty **chủ động công bố** |
| `/careers`, `/tuyen-dung` | Tín hiệu tăng trưởng, tech stack |
| `/contact` | Thông tin liên hệ **công ty** (không phải cá nhân → rủi ro thấp) |
| Footer | Mã số thuế, địa chỉ pháp lý |

> 🎯 **Điểm mạnh pháp lý:** thông tin ban lãnh đạo đăng trên website chính thức
> của công ty là dữ liệu **do chính tổ chức đó chủ động công bố** cho mục đích
> kinh doanh. Vị thế pháp lý tốt hơn hẳn so với scrape LinkedIn, và không vướng
> ToS của bên nào.

---

## 4. Chiến lược kết hợp đa nguồn

Không nguồn nào đủ một mình. Đây là cách ghép hợp lý:

```
┌─────────────────────────────────────────────────────────────┐
│ TẦNG 1 — KHÁM PHÁ: công ty nào đáng theo đuổi?              │
├─────────────────────────────────────────────────────────────┤
│  • Sales Navigator (headcount growth, department, ngành)    │
│  • Cổng ĐKKD VN (lọc theo ngành nghề, khu vực, năm TL)      │
│  • Crunchbase (vừa gọi vốn)                                 │
│  • Cổng đấu thầu (nếu bán cho khu vực công)                 │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ TẦNG 2 — XÁC THỰC: công ty này có thật và đang hoạt động?  │
├─────────────────────────────────────────────────────────────┤
│  • Registry VN (mã số DN, tình trạng, người đại diện)       │
│  • OpenCorporates / GLEIF (công ty nước ngoài)              │
│  • Website chính thức (còn sống không?)                     │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ TẦNG 3 — LÀM GIÀU: ai là người cần tiếp cận?               │
├─────────────────────────────────────────────────────────────┤
│  • Trang /team, /leadership của công ty  ← ưu tiên          │
│  • Apollo / Coresignal / PDL                                │
│  • Sales Navigator (xem thủ công)                           │
└─────────────────────────────────────────────────────────────┘
```

**Khoá kết nối giữa các nguồn:** dùng **domain website** làm khoá chính. Nó ổn
định hơn tên công ty rất nhiều (tên công ty có hàng chục biến thể viết:
"Công ty TNHH ABC", "ABC Co., Ltd", "ABC Vietnam"…).

Với thị trường Việt Nam, **mã số doanh nghiệp/mã số thuế** là khoá tốt nhất —
duy nhất tuyệt đối và do nhà nước cấp.

---

## 5. So sánh nhanh: LinkedIn vs nguồn thay thế

| Tiêu chí | LinkedIn / Sales Nav | Registry + Web + Provider |
|---|---|---|
| Tín hiệu tăng trưởng nhân sự | 🥇 **Không thay thế được** | ⚠️ Yếu (chỉ qua tin tuyển dụng) |
| Chức danh / cơ cấu tổ chức | 🥇 Tốt nhất | ⚠️ Chỉ có cấp lãnh đạo |
| Tính pháp lý của pháp nhân | ❌ Không có | 🥇 **Chính xác tuyệt đối** |
| Coverage SME Việt Nam | ⚠️ **Yếu** | 🥇 Đầy đủ |
| Rủi ro pháp lý khi thu thập | ⚠️ Cao | ✅ Thấp |
| Chi phí | Đã trả | Free → $$ |
| Tự động hoá được? | ❌ Không hợp lệ | ✅ Được |

➡️ **Kết luận:** Sales Navigator mạnh nhất ở **tín hiệu và con người**. Registry
+ web mạnh nhất ở **sự thật pháp lý và khả năng tự động hoá**. Dùng cả hai, mỗi
thứ đúng chỗ — đừng cố ép LinkedIn làm việc mà nó vừa không giỏi vừa không cho
phép.
