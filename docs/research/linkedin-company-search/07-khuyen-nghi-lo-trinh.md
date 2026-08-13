# 07 — Khuyến nghị và lộ trình cho SaleTool / ABIM Sales Assistant

Phần này chuyển kết quả khảo sát thành hành động cụ thể, gắn với codebase hiện
tại của bạn.

---

## 1. Kết luận chiến lược

> **Sales Navigator giỏi nhất ở việc TÌM RA công ty nào đáng theo đuổi.
> Nó tệ nhất (và không cho phép) ở việc MANG DỮ LIỆU ĐI.**
>
> Đừng chống lại điều đó. Hãy thiết kế hệ thống quanh nó.

Nói cách khác: dừng việc tìm cách "lấy dữ liệu ra khỏi LinkedIn" và chuyển sang
kiến trúc nơi LinkedIn đóng vai trò **nguồn tín hiệu**, còn dữ liệu có cấu trúc
đến từ nơi khác.

---

## 2. Kiến trúc 3 tầng khuyến nghị

```
┌──────────────────────────────────────────────────────────────────┐
│ TẦNG 1 — TÍN HIỆU (LinkedIn Sales Navigator)                     │
│                                                                   │
│  Con người dùng SN để trả lời: "Công ty nào đáng theo đuổi?"     │
│  Tận dụng: headcount growth, department headcount, hiring signal │
│  Đầu ra: danh sách TÊN + DOMAIN công ty (số lượng vừa phải)      │
│                                                                   │
│  ✅ Hoàn toàn hợp lệ — đây là đúng mục đích của sản phẩm         │
└────────────────────────────┬─────────────────────────────────────┘
                             │  CSV thủ công (provider csv_import)
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ TẦNG 2 — XÁC THỰC (Registry / Web công ty)                       │
│                                                                   │
│  Tự động: đối chiếu mã số DN, tình trạng hoạt động, domain       │
│  Nguồn: Cổng ĐKKD VN, CompanyData API, website chính thức        │
│                                                                   │
│  ✅ Tự động hoá thoải mái — không vướng ToS của ai              │
└────────────────────────────┬─────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ TẦNG 3 — LÀM GIÀU (Nhà cung cấp có giấy phép)                   │
│                                                                   │
│  Tự động: tìm liên hệ cấp cao + email                            │
│  Nguồn: Apollo (đã có) → thêm Coresignal / trang /team           │
│                                                                   │
│  ✅ Rủi ro chuyển sang nhà cung cấp                              │
└──────────────────────────────────────────────────────────────────┘
```

**Vì sao kiến trúc này đúng:**
- Mỗi tầng chỉ làm thứ nó được phép làm
- Nút thắt cổ chai (con người ở tầng 1) là **nhỏ nhất có thể** — bạn chỉ cần
  người nhập tên + domain, phần còn lại máy làm
- Không có điểm nào tự động hoá chạm vào LinkedIn

---

## 3. Việc cần làm với codebase hiện tại

### 🔴 Ưu tiên cao

#### 3.1. Mở rộng `SearchCriteria` cho đúng bộ lọc Sales Navigator

Hiện tại `saletool/models.py` có: `industries`, `keywords`, `locations`,
`company_size_min/max`, `target_titles`, `seniority_levels`.

**Thiếu các trường quan trọng nhất của Sales Navigator** — chính là những trường
tạo ra tín hiệu mua:

```python
# Đề xuất bổ sung vào SearchCriteria
headcount_growth_min: Optional[float]   # % tăng trưởng nhân sự tối thiểu
department: Optional[str]                # phòng ban quan tâm
department_headcount_min: Optional[int]  # số nhân sự phòng ban đó
technologies: list[str]                  # công nghệ đang dùng
hiring_signal: bool                      # đang tuyển dụng
revenue_min / revenue_max: Optional[int] # doanh thu
founded_year_min / max: Optional[int]    # năm thành lập
```

**Lý do:** khi bạn dùng SN để khám phá rồi nhập CSV vào SaleTool, tiêu chí đã
dùng ở SN nên được ghi lại — hiện lịch sử tìm kiếm của bạn lưu `SearchCriteria`,
nên các trường này sẽ tự động vào lịch sử, giúp tái lập lại search sau này.

#### 3.2. Thêm định danh pháp nhân vào `Company`

`Company` hiện có: `name`, `linkedin_url`, `domain`, `industry`, `location`,
`employee_count`, `provider_id`.

**Nên thêm:**

```python
tax_code: Optional[str]        # mã số thuế / mã số doanh nghiệp
registry_status: Optional[str] # đang hoạt động / tạm ngừng / giải thể
legal_name: Optional[str]      # tên pháp lý đầy đủ (khác tên thương mại)
founded_year: Optional[int]
```

**Lý do:** với thị trường Việt Nam, **mã số doanh nghiệp là khoá định danh duy
nhất đáng tin cậy**. Tên công ty có hàng chục biến thể viết. Đây cũng là điều
kiện tiên quyết để làm tầng 2 (xác thực).

#### 3.3. Ghi lại nguồn gốc dữ liệu (provenance)

Đây là yêu cầu **tuân thủ**, không phải tính năng phụ.

```python
# Thêm vào Company và Contact
source: str                    # "sales_navigator_manual" | "apollo" | "registry" | "company_website"
source_url: Optional[str]
collected_at: str              # ISO 8601
legal_basis: Optional[str]     # cơ sở pháp lý xử lý dữ liệu
```

**Lý do:** khi bị hỏi "dữ liệu này ở đâu ra?" — dù bởi cơ quan quản lý, khách
hàng, hay chính người trong danh sách — bạn phải trả lời được cho **từng bản
ghi**. Đây chính là một trong các điểm KASPR bị CNIL phạt.

Chi phí thêm: nhỏ. Lợi ích: rất lớn khi cần.

---

### 🟡 Ưu tiên trung bình

#### 3.4. Thêm provider `company_website`

Scrape trang `/team`, `/leadership`, `/about` của chính website công ty.

**Vì sao đáng làm sớm:**
- ✅ Rủi ro pháp lý **thấp nhất** trong mọi phương án (công ty tự công bố)
- ✅ Không vướng ToS của bên nào
- ✅ Coverage tốt cho SME Việt Nam — nơi LinkedIn yếu nhất
- ✅ Dữ liệu ban lãnh đạo thường chính xác hơn LinkedIn (được cập nhật chính thức)
- ⚠️ Cần tôn trọng `robots.txt` và rate limit lịch sự

#### 3.5. Thêm provider `vn_registry`

Tích hợp CompanyData API hoặc tương đương để xác thực pháp nhân Việt Nam.

**Giá trị:** biến SaleTool từ "danh sách công ty" thành "danh sách công ty **đã
xác thực**" — khác biệt lớn về chất lượng lead.

#### 3.6. Khử trùng (dedupe) đa nguồn

Khi có nhiều provider, cần hợp nhất bản ghi:
- Khoá ưu tiên 1: **mã số doanh nghiệp** (VN)
- Khoá ưu tiên 2: **domain** (đã chuẩn hoá: bỏ `www.`, bỏ protocol, lowercase)
- Khoá ưu tiên 3: tên đã chuẩn hoá + địa điểm

---

### 🟢 Ưu tiên thấp / cân nhắc sau

#### 3.7. Provider `coresignal`
Nếu nhu cầu firmographic quy mô lớn tăng lên. Chi phí ~$800/tháng nên chỉ làm
khi đã chứng minh được ROI.

#### 3.8. Suppression list (danh sách không liên hệ)
Bắt buộc nếu triển khai outreach thật. Cần trước khi gửi email đầu tiên, không
phải sau.

#### 3.9. Chính sách lưu trữ (retention policy)
Tự động xoá dữ liệu cá nhân sau N tháng. KASPR bị phạt một phần vì lưu quá lâu.
Với lịch sử tìm kiếm hiện đang lưu **toàn bộ kết quả** trong `search_runs`, nên
cân nhắc thời hạn lưu.

---

## 4. Điều KHÔNG nên làm

| ❌ Đừng làm | Lý do |
|---|---|
| Xây browser automation trên tài khoản Sales Navigator | Vi phạm ToS; mất tài khoản = mất cả mạng lưới; đúng kịch bản hiQ |
| Tích hợp PhantomBuster / Captain Data (giao cookie) | Rủi ro cao nhất; nền tảng có thể bị chặn hàng loạt |
| Tạo tài khoản LinkedIn phụ để "tăng hạn mức" | Biến vi phạm hợp đồng thành **gian lận** — đúng thứ giết Proxycurl |
| Phụ thuộc 1 nhà cung cấp dữ liệu duy nhất | Proxycurl biến mất qua đêm với 10 triệu USD ARR |
| Bán lại dữ liệu lấy từ LinkedIn | Vi phạm điều khoản trực diện; biến bạn thành mục tiêu kiện tụng |
| Thu thập contact của người đã giới hạn hiển thị | Chính xác điều KASPR bị phạt 240.000 EUR |

---

## 5. Lộ trình đề xuất

### Giai đoạn 1 — Củng cố nền tảng (1–2 tuần)
- [ ] Mở rộng `SearchCriteria` với các trường tín hiệu của Sales Navigator (3.1)
- [ ] Thêm `tax_code` / `registry_status` vào `Company` (3.2)
- [ ] Thêm trường provenance vào `Company` và `Contact` (3.3)
- [ ] Cập nhật mẫu CSV trong `examples/` cho khớp
- [ ] Viết tài liệu quy trình human-in-the-loop cho người dùng cuối

### Giai đoạn 2 — Mở rộng nguồn (2–4 tuần)
- [ ] Provider `company_website` (3.4) — **ROI cao nhất, rủi ro thấp nhất**
- [ ] Provider `vn_registry` (3.5)
- [ ] Logic khử trùng đa nguồn (3.6)

### Giai đoạn 3 — Quy mô & tuân thủ (khi cần)
- [ ] Đánh giá Coresignal, chạy thử với dữ liệu mẫu thật
- [ ] Suppression list + retention policy
- [ ] Rà soát pháp lý với luật sư về PDPL Việt Nam

---

## 6. Quyết định cần bạn đưa ra

Có 3 điểm khảo sát không thể tự quyết thay bạn:

### ❓ Quyết định 1: Có dùng công cụ export Sales Navigator không?

| | Có (Evaboot/Wiza) | Không (nhập tay) |
|---|---|---|
| Tốc độ | Nhanh gấp ~10–50 lần | ~50–200 công ty/ngày/người |
| Chi phí | +$39–699/tháng | Chi phí nhân công |
| Rủi ro tài khoản | **Có thật** | Không |
| Vi phạm ToS | **Có** | Không |

*Khuyến nghị của tôi:* không dùng. Nếu khối lượng vượt quá khả năng nhập tay,
tiền đó nên đổ vào nhà cung cấp dữ liệu — vừa nhanh hơn vừa không có rủi ro
tài khoản.

### ❓ Quyết định 2: Thị trường mục tiêu chính là đâu?

- **Việt Nam** → ưu tiên registry + website công ty; LinkedIn coverage yếu, PDPL
  siết chặt
- **Quốc tế / EU** → ưu tiên nhà cung cấp có tuân thủ GDPR (Cognism); cần cẩn
  trọng Điều 14
- **Mỹ** → Apollo/ZoomInfo coverage tốt nhất, môi trường pháp lý dễ thở hơn

Câu trả lời này thay đổi thứ tự ưu tiên ở Giai đoạn 2 khá nhiều.

### ❓ Quyết định 3: Có nâng lên Sales Navigator Advanced Plus không?

Chỉ đáng nếu bạn **đã** dùng Salesforce hoặc MS Dynamics. Nếu không, CRM Sync
cũng không giải quyết được nhu cầu "export kết quả search" của bạn — xem
[`01-duong-chinh-thuc.md`](01-duong-chinh-thuc.md) mục 4.

---

## 7. Một góc nhìn thẳng thắn để kết

Trong suốt khảo sát này có một mô-típ lặp đi lặp lại: **mọi công ty cố gắng tự
động hoá việc lấy dữ liệu LinkedIn ở quy mô lớn đều đã bị xử lý** — hiQ (phá
sản), Proxycurl (đóng cửa dù 10 triệu USD ARR), KASPR (phạt 240k EUR), ProAPIs
(đang bị kiện), Apollo và Seamless (bị gỡ Page).

Đây không phải là chuỗi trùng hợp. LinkedIn có nguồn lực của Microsoft và coi
dữ liệu này là tài sản cốt lõi. Xu hướng rõ ràng là **siết chặt dần**: khai tử
LSI, đóng SNAP, kiện liên tiếp.

Vì vậy, khuyến nghị cốt lõi không phải là "tìm cách lách khéo hơn", mà là:
**xây SaleTool sao cho giá trị của nó không phụ thuộc vào việc có lấy được dữ
liệu LinkedIn hay không.** Giá trị nằm ở việc *tổng hợp, xác thực, chấm điểm và
tổ chức* dữ liệu từ nhiều nguồn hợp lệ — đó là thứ không ai có thể kiện bạn, và
cũng là thứ khó sao chép hơn.
