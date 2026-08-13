# Tổng kết: dựng hệ thống + khảo sát nguồn dữ liệu LinkedIn

> **Phiên làm việc:** 13–14/08/2026
> **Môi trường:** Windows 10, Python 3.14.4, Node 26.7.0
> **Nhánh:** `claude/linkedin-company-contact-search-aa80xb` · commit `e7cfeca` (đã push)

File này gộp 2 thứ: **Phần I** là toàn bộ việc đã làm trong phiên (dựng app,
dựng SearXNG, test enrich, sửa lỗi, dọn repo), **Phần II** là bản khảo sát
các cách lấy dữ liệu công ty trên LinkedIn.

Hướng dẫn chạy từng bước nằm ở [`chay-local.md`](chay-local.md); khảo sát bản
đầy đủ nằm ở [`research/linkedin-company-search/`](research/linkedin-company-search/).

---

# Phần I — Những gì đã làm

## 1. Dựng và chạy source

Ba service chạy song song:

| Service | Cổng | Lệnh |
|---|---|---|
| SearXNG | 8888 | `python -m searx.webapp` (venv riêng) |
| Backend FastAPI | 8000 | `python -m saletool.cli web serve` |
| Frontend Vite | 5173 | `npm run dev` |

Tài khoản đăng nhập đã tạo: **`demo` / `demo1234`** (SQLite `saletool.db`).

Hai biến môi trường bắt buộc, không đặt là hỏng ngầm chứ không báo lỗi rõ:

- **`SALETOOL_SECRET_KEY`** — phải cố định giữa các lần restart. Không đặt thì
  server sinh khoá tạm mới mỗi lần khởi động → JWT cũ hết hiệu lực và API key
  đã lưu ở Settings không giải mã được nữa (khoá suy ra từ biến này qua HKDF).
- **`PYTHONIOENCODING=utf-8`** — console Windows dùng cp1252, không encode được
  tiếng Việt. Lệnh `create-user` vẫn tạo tài khoản thành công nhưng ném
  `UnicodeEncodeError` lúc in thông báo.

Dự án **không** tự nạp file `.env` — biến phải set trực tiếp trong terminal.

## 2. Cài và chạy SearXNG

Máy không có Docker, WSL chưa cài distro nào → cài **native bằng Python** vào
`C:\Users\Admin\Documents\searxng`. Khả thi vì requirements của SearXNG không có
`uvloop` hay `setproctitle` (2 thứ hay chặn Windows). Ba chỗ vướng:

| Lỗi | Nguyên nhân | Cách xử lý |
|---|---|---|
| `invalid path 'utils/templates/.../searxng.conf:socket'` | 4 file template deploy có dấu `:` trong tên — Windows cấm | checkout loại trừ `utils/templates` (chỉ là template nginx/uwsgi) |
| `ModuleNotFoundError: No module named 'pwd'` | `searx/valkeydb.py` import module Unix-only ở top-level | bọc `try/except ImportError`; chỗ dùng duy nhất là 1 dòng log lỗi kết nối Valkey, cấu hình này không dùng Valkey nên không chạy tới |
| `ZoneInfoNotFoundError: 'Asia/Shanghai'` | Windows không có IANA timezone DB | `pip install tzdata` |

**Cấu hình quan trọng nhất** (`settings-local.yml`): bật `search.formats: [html, json]`.
Mặc định SearXNG **chỉ** cho `html`, mà SaleTool gọi `GET /search?q=...&format=json`
→ thiếu dòng này thì mọi request trả **403**. Chạy phải kèm `SEARXNG_SETTINGS_PATH`,
quên là nó dùng settings mặc định và cũng 403.

Đã verify: `curl "http://127.0.0.1:8888/search?q=abim+company&format=json"` trả
kết quả thật.

## 3. Nối SearXNG vào SaleTool

Settings đã đổi: search provider `none` → **`searxng`** (`http://127.0.0.1:8888`),
bật `use_web_search`. Nút **Test connection** trả `ok: true — "Connected. Got 3
result(s)"`, kết quả đầu là `https://vn.linkedin.com/company/vn-tech`.

⚠️ **LLM đang tắt.** Backend từ chối lưu settings (HTTP 400 *"LLM extraction is
enabled but no LLM API key is configured"*) vì chưa có OpenRouter key. Hệ quả:
enrichment chạy **tầng 0–2** (JSON-LD/meta/regex → sitemap + crawl website →
web search), **không có tầng 3 (LLM)**. Có key thì vào Settings nhập rồi bật
`use_llm` lại.

## 4. Test enrich thật

Input mẫu (dán vào trang Enrichment, mỗi dòng 1 công ty):

```
FPT Software, fptsoftware.com
Vinamilk, vinamilk.com.vn
```

Job chạy nền hết **62 giây** cho 2 công ty. Kết quả Vinamilk:

| Trường | Giá trị |
|---|---|
| description | "Công ty sữa Vinamilk không ngừng mở rộng nguồn nguyên liệu..." |
| emails | `vinamilk@vinamilk.com.vn` |
| phones | `1900 636 979` |
| addresses | `Số 10 Tân Trào, Phường Tân Mỹ, TP.HCM...` |
| social | facebook, instagram, linkedin, tiktok, youtube — đúng trang chính thức |
| **llm_calls** | **0** |

`llm_calls: 0` xác nhận toàn bộ dữ liệu trên lấy từ tầng 0–1, không tốn tiền LLM.
FPT Software ra kém hơn (chỉ có phone + social, `emails` rỗng) vì site đó không
gắn JSON-LD `Organization` đầy đủ.

## 5. Hai lỗi đã sửa

Cả hai đều lộ ra từ lần chạy thật ở trên, không phải từ đọc code.

**5.1. `discovery.py` — crawler tải cả CSS/JS**

Site dựng bằng Next.js/Nuxt nhét đường dẫn bundle ngay trong HTML trang chủ nên
crawl nông nhặt phải. Mỗi URL rác tốn 1 request + 1 nhịp nghỉ rate limit rồi mới
bị fetcher loại vì sai content-type. `_SKIP_RE` cũ thiếu `css|js`, lại neo `$`
vào cả URL nên trượt với query cache-busting (`/app.css?v=9f2a`).

→ Thay bằng `_should_skip()` khớp trên `urlparse(url).path`, thêm đuôi
`css/js/mjs/map/json/ico/woff...` và thư mục `/_next/static/`, `/_nuxt/`,
`/static/{js,css,media}/`, `/wp-content/`, `/cdn-cgi/`.

**5.2. `structured.py` — nút share bị nhận nhầm là trang công ty**

Gần như trang nào cũng có `facebook.com/sharer/sharer.php?u=...` hay
`twitter.com/intent/tweet`, và chúng nằm cao trong HTML nên **luôn thắng** link
thật. Ngoài ra href dính khoảng trắng ở cuối làm URL LinkedIn lưu xuống DB bấm
vào không mở được.

→ Thêm `social_profile()` dùng chung cho cả 2 đường vào (thẻ `<a href>` và
`sameAs` trong JSON-LD): `.strip()` URL, loại endpoint chia sẻ và link tới
video/bài viết lẻ.

**Kiểm chứng — chạy lại đúng 2 công ty đó:**

| | Trước | Sau |
|---|---|---|
| Vinamilk sources | 7, trong đó **2 `ok=False`** (css + webpack) | 7, **tất cả `ok=True`** — 2 slot phí thay bằng `/technology`, `/store-list` |
| FPT facebook | `facebook.com/sharer/sharer.php?u=...` | không còn |
| FPT linkedin | `".../fpt-software/ "` (thừa dấu cách) | `"https://www.linkedin.com/company/fpt-software/"` |

Lưu ý: facebook/youtube của FPT giờ **trống** thay vì có giá trị sai — trên site
đó chỉ tồn tại nút share và link video, không có link fanpage/kênh thật.

## 6. Một cảnh báo giả — không phải bug

Ban đầu tôi báo có lỗi encoding vì thấy `Tân Tr\ufffd\xa0o` trong địa chỉ Vinamilk.
Kiểm tra lại bằng probe đọc thẳng nguồn: header trả `charset=utf-8`, httpx decode
đúng, JSON-LD parse ra chuỗi sạch, và giá trị đọc ngược từ SQLite có **0 ký tự
hỏng**. Chuỗi hỏng đó là do **console Windows cp1252 render**, không phải dữ liệu.
Không sửa gì.

Ghi lại đây vì đây là cái bẫy sẽ lặp lại: **đừng đánh giá dữ liệu tiếng Việt qua
output terminal trên Windows** — hãy ghi ra file UTF-8 hoặc kiểm tra bằng
`ord()`/`repr()` rồi so.

## 7. Dọn repo

**Tài liệu** — gom vào `docs/`:

```
docs/
  tong-ket.md      (file này)
  chay-local.md    (từ CHAY-LOCAL.md ở root)
  research/linkedin-company-search/   (9 file, git nhận diện là rename nên giữ lịch sử)
```

`README.md` ở lại root theo thông lệ. Ba chỗ trỏ tới đường dẫn `research/` cũ đã
sửa: `fetcher.py`, `search/providers.py`, và cây thư mục trong README.

**Code** — quét bằng AST: **0 import thừa**. Quét symbol không ai tham chiếu ra
12 kết quả, 11 là dương tính giả (route handler FastAPI, command click, override
của `HTMLParser` — framework gọi chứ không gọi bằng tên). Ba thứ sửa thật:

| Chỗ | Vấn đề |
|---|---|
| `models.py` | `JOB_STATUSES` không ai dùng, còn liệt kê status `"cancelled"` mà hệ thống không bao giờ set → xoá |
| `pipeline.py` | `EnrichmentSource(...)` dựng inline 4 lần cùng bộ field → gom thành `_source()`, giảm 47 dòng |
| `discovery.py` | `_same_site()` viết lại phần bóc `www.` mà `normalize_domain()` đã làm, lại bỏ sót port → gọi thẳng `normalize_domain()` |

**Hai thứ cố ý giữ lại**, vì xoá hại hơn lợi:
- `api.listEnrichJobs()` trong `client.js` — chưa page nào gọi, nhưng endpoint
  `/api/enrich/jobs` có thật và có trong README. Xoá thì client lệch backend.
- `SENIORITY_LEVELS` trong `models.py` — Python không dùng, nhưng
  `frontend/src/constants.js` chép lại kèm comment "Must match saletool/models.py".
  Nó là nguồn chuẩn, không phải code chết.

**Kiểm chứng:** 121 test pass · `npm run build` OK · `npm run lint` sạch (1 warning
fast-refresh ở `AuthContext.jsx`, chỉ ảnh hưởng DX) · chạy lại enrich thật cho ra
kết quả **giống hệt** trước refactor → không đổi hành vi.

## 8. Commit và push

Commit `e7cfeca` trên `claude/linkedin-company-contact-search-aa80xb`, push
fast-forward `ecf4376..e7cfeca` lên https://github.com/MTagi/SaleTool.

Git identity đặt **repo-local** (`thang <thangdz2305@gmail.com>`) — không đụng
config global của máy. Muốn đổi email: `git config user.email "..."` rồi
`git commit --amend --reset-author`.

Nhánh này **chưa có PR**. Nhánh gốc để mở PR là `claude/readme-hello-content-mss0n6`.

## 9. Việc còn treo

- **Chưa có OpenRouter key** → tầng 3 (LLM) của enrichment chưa chạy được.
  Không có nó thì `industry`, `headquarters`, `executives`, `employee_count_text`
  gần như luôn rỗng vì mấy trường này hiếm khi có trong JSON-LD.
- **Bản vá `pwd` nằm trong repo searxng đã clone** — `git pull` searxng là mất,
  phải vá lại.
- **`user_agent` vẫn là giá trị mặc định** `SaleToolBot/1.0 (+contact: set-your-email@example.com)`.
  Nên đổi thành email thật trước khi crawl nhiều — đây là phần "trung thực" của
  chính sách crawl lịch sự.
- **Chưa mở PR.**

---

# Phần II — Khảo sát: các cách lấy dữ liệu công ty trên LinkedIn

> Ngày khảo sát 13/08/2026. Bản đầy đủ 9 file ở
> [`research/linkedin-company-search/`](research/linkedin-company-search/).
> **Đây không phải tư vấn pháp lý.**

## 1. Năm kết luận cốt lõi

**1.1. Cánh cửa API chính thức đã đóng.** Sales Navigator API (SNAP) không nhận
đối tác mới — không form đăng ký, không hàng chờ, không timeline. Chỉ đối tác CRM
cũ (Salesforce, HubSpot, MS Dynamics) còn quyền. **Tài khoản Sales Navigator trả
phí không đi kèm API key nào** — đây là hiểu lầm phổ biến nhất. LinkedIn Sales
Insights (LSI), sản phẩm DaaS chính thức, đã **khai tử 31/12/2024**.

**1.2. Sales Navigator không có nút export.** Đường thoát dữ liệu duy nhất được
LinkedIn cho phép là **CRM sync**, đòi hỏi gói **Advanced Plus** *và* CRM là
Salesforce hoặc Microsoft Dynamics. Dùng gói Core/Advanced → không có đường hợp
lệ nào ngoài con người tự đọc tự nhập.

**1.3. Mọi công cụ export tự động đều vi phạm ToS — không ngoại lệ.** Evaboot,
Wiza, PhantomBuster, Captain Data, Lobstr, Scrupp… đều trích xuất tự động từ
phiên đăng nhập của bạn, vi phạm User Agreement **bất kể** chạy "chậm như người
thật" hay không. Blog của chính nhà cung cấp quảng cáo "zero ban risk" là
**marketing, không phải sự thật kỹ thuật hay pháp lý**.

**1.4. Án lệ: "dữ liệu công khai ≠ tội hình sự" nhưng "vẫn là vi phạm hợp đồng".**

| Vụ | Kết quả | Ý nghĩa |
|---|---|---|
| **hiQ v. LinkedIn** (2022) | Toà phúc thẩm số 9: scrape dữ liệu công khai **không** vi phạm CFAA | ✅ Không bị tội hình sự… |
| **hiQ v. LinkedIn** (kết cục) | Toà sơ thẩm: hiQ **vi phạm hợp đồng**, trả **500.000 USD**, cấm vĩnh viễn, **phá sản** | ❌ …nhưng vẫn chết vì vi phạm hợp đồng |
| **LinkedIn v. Proxycurl** (2025) | Kiện 24/01/2025 (N.D. Cal, 3:25-cv-00828). Proxycurl — 10 triệu USD ARR — **dàn xếp và đóng cửa 7/2025** | ❌ Nhà cung cấp dữ liệu LinkedIn lớn nhất bị xoá sổ |
| **Meta v. Bright Data** (2024) | Bright Data **thắng**: scrape dữ liệu công khai khi **đã đăng xuất** không bị ToS ràng buộc | ✅ Có vùng an toàn — nhưng chỉ khi *không đăng nhập* |

> **Ranh giới không nằm ở "dữ liệu công khai hay không", mà ở "bạn có đăng nhập
> vào tài khoản đã ký ToS hay không".**

**1.5. Rủi ro pháp lý ở Việt Nam đang tăng.** Luật Bảo vệ dữ liệu cá nhân (PDPL)
**có hiệu lực 01/01/2026**, theo hướng **lấy sự đồng ý**, khái niệm "lợi ích chính
đáng" **hẹp hơn GDPR nhiều** → lập luận "làm B2B nên được miễn" còn yếu hơn ở EU.
Tên + chức danh + email công việc **vẫn là dữ liệu cá nhân**. Tiền lệ: **CNIL phạt
KASPR 240.000 EUR** (05/12/2024), buộc xoá 160 triệu bản ghi — mô hình KASPR gần
như y hệt "extension lấy contact từ LinkedIn".

## 2. So sánh 6 nhóm phương án

| # | Cách làm | Chi phí | Rủi ro ToS | Rủi ro pháp lý | Quy mô | Hợp không? |
|---|---|---|---|---|---|---|
| A | SNAP API chính thức | — | Không | Không | Cao | ❌ Cửa đã đóng |
| B | **Sales Navigator thủ công** | Đã trả rồi | Không | Thấp | ~50–200 cty/ngày | ✅ **Nền tảng** |
| C | CRM Sync (Advanced Plus) | $$$ + cần Salesforce/Dynamics | Không | Thấp | Cao | ⚠️ Nếu đủ ngân sách |
| D | Công cụ export SN (Evaboot/Wiza…) | $ | **Cao** | Trung bình | Cao | ⚠️ Bạn tự quyết |
| E | **Mua từ nhà cung cấp** (Apollo/Coresignal/PDL) | $$–$$$ | Không | Thấp–TB | Rất cao | ✅ **Nên có** |
| F | Nguồn ngoài LinkedIn (registry, web) | $–$$ | Không | Thấp | Cao | ✅ Bổ sung tốt |

## 3. Kiến trúc 3 tầng khuyến nghị

> **Sales Navigator giỏi nhất ở việc TÌM RA công ty nào đáng theo đuổi.
> Nó tệ nhất (và không cho phép) ở việc MANG DỮ LIỆU ĐI. Đừng chống lại điều đó —
> hãy thiết kế hệ thống quanh nó.**

| Tầng | Việc | Nguồn | Tự động hoá? |
|---|---|---|---|
| **1 — Tín hiệu** | Con người dùng SN trả lời "công ty nào đáng theo đuổi?" (headcount growth, department headcount, hiring signal). Đầu ra: tên + domain | Sales Navigator | ❌ Con người, đúng mục đích sản phẩm |
| **2 — Xác thực** | Đối chiếu mã số DN, tình trạng hoạt động, domain | Cổng ĐKKD VN, website công ty | ✅ Thoải mái, không vướng ToS ai |
| **3 — Làm giàu** | Tìm liên hệ cấp cao + email | Apollo (đã có) → thêm Coresignal | ✅ Rủi ro chuyển sang nhà cung cấp |

Nút thắt cổ chai (con người ở tầng 1) là **nhỏ nhất có thể** — chỉ cần nhập tên +
domain, phần còn lại máy làm. **Không điểm nào tự động hoá chạm vào LinkedIn.**

Kiến trúc hiện tại của SaleTool đã khớp: provider `csv_import` chính là cầu nối
tầng 1 → tầng 2, và pipeline enrichment (đã dựng trong phiên này) chính là tầng 2.

**Điều nên tránh:** đừng xây tự động hoá trình duyệt trên chính tài khoản Sales
Navigator của bạn. Rủi ro mất tài khoản là thật, chi phí thay thế cao hơn nhiều
tiền tiết kiệm được.

## 4. Việc khảo sát đề xuất cho codebase

Ưu tiên cao nhất: **mở rộng `SearchCriteria`** cho khớp bộ lọc Sales Navigator.
Hiện có `industries`, `keywords`, `locations`, `company_size_min/max`,
`target_titles`, `seniority_levels` — thiếu đúng những trường tạo ra *tín hiệu mua*:

```python
headcount_growth_min: Optional[float]   # % tăng trưởng nhân sự tối thiểu
department: Optional[str]                # phòng ban quan tâm
department_headcount_min: Optional[int]  # số nhân sự phòng ban đó
technologies: list[str]                  # công nghệ đang dùng
hiring_signal: bool                      # đang tuyển dụng
```

Chi tiết lộ trình: [`07-khuyen-nghi-lo-trinh.md`](research/linkedin-company-search/07-khuyen-nghi-lo-trinh.md).

## 5. Giới hạn của khảo sát

- ✅ **Đã xác minh chéo** các mốc pháp lý, án lệ, ngày tháng (nhiều blog SEO ghi
  sai năm vụ Proxycurl — bản này dùng số hiệu vụ án gốc).
- ⚠️ Môi trường chạy khảo sát **bị chặn `linkedin.com` và `learn.microsoft.com`**,
  nên trích dẫn tài liệu chính thức của LinkedIn đến từ nguồn thứ cấp trích lại
  nguyên văn. Nên tự mở link trong
  [`nguon-tham-khao.md`](research/linkedin-company-search/nguon-tham-khao.md)
  trước khi ra quyết định có ràng buộc hợp đồng.
- ⚠️ **Giá và số liệu coverage** của nhà cung cấp thay đổi liên tục, phần lớn từ
  trang marketing của chính họ — phải hỏi báo giá thật.
- ❗ **Không phải tư vấn pháp lý.** Vận hành thương mại quy mô lớn thì hỏi luật sư
  về PDPL Việt Nam.
