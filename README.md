# SaleTool

Công cụ: từ **1 input format mô tả mục tiêu tìm kiếm công ty**, tìm ra
**danh sách công ty phù hợp trên LinkedIn**, rồi lấy ra **danh sách liên hệ
(ưu tiên các cấp cao — C-level, VP, Director...)** của từng công ty đó.

## Cách tiếp cận dữ liệu

SaleTool **không** tự động hoá trình duyệt để scrape trực tiếp
`linkedin.com` — việc này vi phạm Terms of Service của LinkedIn và có rủi ro
pháp lý/khoá tài khoản. Thay vào đó, SaleTool gọi API của các **nhà cung cấp
dữ liệu bên thứ ba** đã tổng hợp dữ liệu công ty/liên hệ (kèm link LinkedIn)
một cách hợp pháp, ví dụ [Apollo.io](https://apollo.io). Bạn cần tài khoản
và API key hợp lệ của provider tương ứng.

Kiến trúc dùng interface `CompanyContactProvider` (`saletool/providers/base.py`)
nên có thể bổ sung thêm provider khác (People Data Labs, Proxycurl, Clearbit...)
mà không phải sửa pipeline.

### Đang dùng LinkedIn Sales Navigator?

Sales Navigator (kể cả gói trả phí) **không** tự cấp API key để gọi tự động —
LinkedIn chỉ cấp Sales Navigator API cho đối tác CRM được duyệt chính thức.
Vì vậy SaleTool có provider **`csv_import`** theo mô hình *human-in-the-loop*:
bạn tự tìm kiếm/duyệt trên Sales Navigator bằng trình duyệt của chính mình
(đúng ToS), tự export/copy kết quả ra CSV, rồi đưa cho SaleTool chuẩn hoá +
lọc theo seniority + xuất kết quả. Xem file mẫu
`examples/companies_export.example.csv` và `examples/contacts_export.example.csv`
— tên cột không cần khớp chính xác, provider tự nhận diện qua alias
(`saletool/providers/csv_import.py`). Nếu cột "seniority" không có sẵn,
SaleTool tự suy luận từ chức danh (`saletool/seniority.py`).

## Cài đặt

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # điền APOLLO_API_KEY nếu dùng provider apollo
```

Chạy trên Windows, hoặc muốn dựng luôn cả SearXNG để có web search miễn phí:
xem [docs/chay-local.md](docs/chay-local.md).

## Sử dụng

1. Mô tả mục tiêu tìm kiếm trong file YAML/JSON — xem mẫu tại
   `examples/search_criteria.example.yaml` (đầy đủ các trường xem
   `saletool/models.py::SearchCriteria`).

2. Chạy thử ngay không cần API key (dùng provider giả lập `mock`):

   ```bash
   python -m saletool.cli search \
     --config examples/search_criteria.example.yaml \
     --provider mock \
     --output output.csv
   ```

3. Chạy thật với Apollo.io:

   ```bash
   python -m saletool.cli search \
     --config examples/search_criteria.example.yaml \
     --provider apollo \
     --api-key "$APOLLO_API_KEY" \
     --output output.csv
   ```

4. Hoặc dùng dữ liệu bạn tự export thủ công từ Sales Navigator (CSV):

   ```bash
   python -m saletool.cli search \
     --config examples/search_criteria.example.yaml \
     --provider csv_import \
     --companies-csv examples/companies_export.example.csv \
     --contacts-csv examples/contacts_export.example.csv \
     --output output.csv
   ```

Kết quả xuất ra CSV (mặc định) hoặc JSON (`--output result.json`), mỗi dòng
là 1 cặp (công ty, liên hệ).

## Web UI — "ABIM Sales Assistant" (FastAPI API + React, có đăng nhập)

Giao diện web mang tên **ABIM Sales Assistant**, toàn bộ UI bằng tiếng Anh,
gồm 5 trang: **Search** (form tìm kiếm), **Enrichment** (bổ sung dữ liệu công
ty từ website), **History** (lịch sử tìm kiếm), **Settings** (cấu hình LLM +
công cụ search + nguồn enrich), **Account** (tài khoản + đổi mật khẩu).

Kiến trúc: **backend FastAPI** (JSON API thuần, JWT bearer auth) +
**frontend React** (SPA riêng, thư mục `frontend/`, gọi API qua fetch) +
**database qua lớp abstraction** (`saletool/db/`) — mặc định SQLite, đổi sang
MongoDB chỉ cần set biến môi trường, không phải sửa route/logic auth. Không
có tự đăng ký công khai — tài khoản do người vận hành tạo qua CLI, phù hợp
một tool dùng nội bộ trong nhóm nhỏ.

### Chạy backend

```bash
pip install -r requirements-dev.txt

# Đặt secret key để JWT không đổi khi restart server
export SALETOOL_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"

# Tạo tài khoản đăng nhập (dùng DB backend hiện tại, mặc định sqlite)
python -m saletool.cli web create-user --username demo

# Chạy API
python -m saletool.cli web serve --host 127.0.0.1 --port 8000
```

API chính: `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/change-password`,
`POST /api/search` (multipart — hỗ trợ upload CSV cho provider `csv_import`,
tự lưu vào lịch sử), `GET /api/search/runs` (danh sách lịch sử),
`GET /api/search/runs/{run_id}` (chi tiết 1 lần chạy), `GET
/api/download/{csv,json}?run_id=...` (mặc định lần gần nhất nếu không truyền
`run_id`), `GET|PUT /api/settings` + `POST /api/settings/test`,
`POST /api/enrich` + `GET /api/enrich/jobs[/{job_id}]`. Xem `saletool/api/routes/`.

### Chạy frontend (React)

```bash
cd frontend
npm install
npm run dev
```

Mở `http://127.0.0.1:5173`. Vite dev server proxy sẵn `/api/*` sang
`http://127.0.0.1:8000` (xem `frontend/vite.config.js`) nên không cần cấu
hình CORS thủ công lúc phát triển. Đăng nhập, điền tiêu chí tìm kiếm ở trang
**Search**, chọn provider (`mock` để demo, `apollo` với API key, hoặc
`csv_import` để tải lên CSV tự export từ Sales Navigator), bấm **Search** —
kết quả hiển thị dạng bảng theo từng công ty kèm liên hệ cấp cao, có nút tải
CSV/JSON. Mỗi lần tìm kiếm được lưu lại — trang **History** liệt kê các lần
chạy trước (tiêu chí, provider, số công ty/liên hệ, thời gian) và cho xem
lại/tải lại kết quả cũ. Trang **Account** hiển thị tài khoản đang đăng nhập
và cho đổi mật khẩu.

### Enrichment — bổ sung dữ liệu từ website công ty

Sau khi có danh sách công ty, bước enrich đọc **website của chính công ty** (và
tuỳ chọn các trang bên ngoài qua web search) để lấy mô tả, email, điện thoại,
địa chỉ, mã số thuế, mạng xã hội và ban lãnh đạo.

Ba lối vào:
- **Trang Enrichment** — dán danh sách `Tên công ty, domain.com`, mỗi dòng 1 công ty
- **Auto-enrich** — bật ở đầu trang Search, tự chạy cho toàn bộ kết quả sau khi search
- **Nút Enrich** — hiện trên từng công ty còn thiếu thông tin ở trang kết quả

Enrich **chạy nền** (mỗi công ty mất ~10–30 giây), UI poll tiến độ. Pipeline
chạy theo thứ tự **rẻ và chính xác trước**:

| Tầng | Việc | Chi phí |
|---|---|---|
| 0 | JSON-LD `schema.org/Organization`, thẻ meta, `mailto:`/`tel:`, regex | 0đ, chính xác hơn LLM |
| 1 | `sitemap.xml` + crawl nông website công ty | 0đ, không cần search API |
| 2 | Web search cho trang bên ngoài (tuỳ chọn) | tuỳ provider |
| 3 | LLM — **chỉ** cho trường mà tầng trên không lấy được | ~$0.0002/trang |

Thứ gì lấy được ở tầng sớm sẽ không bị tầng sau ghi đè. HTML được làm sạch bằng
`trafilatura` **trước khi** đưa vào LLM — bước này giảm khoảng 40 lần số token so
với ném HTML thô vào model.

Mọi bản ghi đều lưu **nguồn gốc (provenance)**: URL, thời điểm tải, tải bằng HTTP
hay browser, trích bằng parser hay LLM — xem nút "Show sources" trên từng kết quả.

**Giữ bước này ở mức rủi ro thấp:** mặc định tôn trọng `robots.txt`, nghỉ 1 giây
giữa 2 request tới cùng domain, và dùng User-Agent trung thực. Đừng tắt các mục
này trong Settings.

### Settings — cấu hình LLM và công cụ search

Cấu hình dùng chung cho cả hệ thống (không per-user). **API key được mã hoá
trước khi lưu và không bao giờ trả về trình duyệt** — UI chỉ thấy bản mask.

- **LLM**: mặc định OpenRouter (API tương thích OpenAI). Chọn model hỗ trợ
  structured output; trích xuất từ text đã sạch là việc dễ nên model nhỏ, rẻ là đủ.
- **Web search**: `none` (mặc định — chỉ đọc website công ty, hoàn toàn free),
  `searxng` (tự host, free, không cần key), `brave` / `tavily` / `serper` (trả phí).
- Nút **Test connection** gọi thật để kiểm tra cấu hình trước khi chạy enrich.

Build production: `npm run build` (ra `frontend/dist/`) — deploy tĩnh sau
1 reverse proxy trỏ `/api/*` về FastAPI, phần còn lại phục vụ file tĩnh.

### Đổi database sang MongoDB (sau này)

```bash
pip install -r requirements-mongo.txt   # thêm pymongo
export SALETOOL_DB_BACKEND=mongo
export SALETOOL_MONGO_URI="mongodb://localhost:27017"
export SALETOOL_MONGO_DB=saletool
```

`saletool/db/base.py` định nghĩa 4 interface — `UserRepository` (tài khoản),
`SearchRunRepository` (lịch sử tìm kiếm), `SettingsRepository` (cấu hình) và
`EnrichJobRepository` (job enrich chạy nền);
`sqlite_repo.py` và `mongo_repo.py` là 2 implementation cho cả bốn —
`saletool/db/factory.py` chọn theo `SALETOOL_DB_BACKEND`. Muốn thêm DB khác
chỉ cần viết thêm 1 implementation mới theo các interface này.

**Phạm vi bảo mật:** phù hợp dùng nội bộ sau HTTPS reverse proxy đáng tin cậy.
Chưa có: giới hạn số lần đăng nhập sai, refresh token/thu hồi token, khôi phục
mật khẩu — cần bổ sung thêm nếu triển khai ra ngoài internet công khai.

## Test

```bash
pytest              # backend (Python)
cd frontend && npm run build   # frontend (kiểm tra biên dịch)
```

## Cấu trúc dự án

```
saletool/
  models.py          # SearchCriteria, Company, Contact, CompanyResult
  config.py           # nạp input format YAML/JSON
  security.py          # băm/xác thực mật khẩu (PBKDF2, stdlib only)
  providers/
    base.py            # interface CompanyContactProvider
    apollo.py           # provider Apollo.io
    csv_import.py        # provider import CSV thủ công (vd: Sales Navigator)
    mock.py              # provider giả lập để demo/test
  seniority.py         # suy luận seniority từ title tự do
  pipeline.py          # điều phối: tìm công ty -> tìm liên hệ mỗi công ty
  output.py             # xuất CSV/JSON
  cli.py                 # CLI: saletool search / saletool web serve|create-user
  crypto.py             # mã hoá API key trước khi lưu DB
  db/
    base.py               # 4 interface: User/SearchRun/Settings/EnrichJob
    sqlite_repo.py          # implementation SQLite (mặc định)
    mongo_repo.py            # implementation MongoDB (sẵn sàng, chưa bật mặc định)
    factory.py                # chọn implementation theo SALETOOL_DB_BACKEND
  enrichment/
    pipeline.py           # điều phối 4 tầng enrich
    discovery.py            # sitemap + crawl nông + tạo query search
    fetcher.py               # HTTP -> Playwright fallback, robots.txt, rate limit
    extractor.py              # HTML -> text sạch (trafilatura)
    structured.py              # tầng 0: JSON-LD, meta, mailto/tel, regex
    llm.py                      # OpenRouter, structured output + validate lại
    search/                      # SearchProvider: none/searxng/brave/tavily/serper
  api/
    app.py               # FastAPI app: CORS, include routers
    auth.py                # cấp phát/xác minh JWT
    jobs.py                 # chạy job enrich ở nền, ghi tiến độ xuống DB
    deps.py                 # dependency get_current_user
    routes/
      auth.py                 # /api/auth/login, /api/auth/me, /api/auth/change-password
      search.py                # /api/search, /api/search/runs[/{id}], /api/download/{fmt}
      settings.py               # /api/settings, /api/settings/test
      enrich.py                  # /api/enrich, /api/enrich/jobs[/{id}]
frontend/               # React SPA (Vite) "ABIM Sales Assistant", tiếng Anh
                         # — Search, Enrichment, History, Settings, Account
docs/
  chay-local.md          # hướng dẫn chạy local (SaleTool + SearXNG) trên Windows
  research/              # khảo sát: các cách lấy dữ liệu công ty trên LinkedIn
examples/
  search_criteria.example.yaml
  companies_export.example.csv
  contacts_export.example.csv
tests/
```
