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

## Web UI (FastAPI API + React, có đăng nhập)

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

API chính: `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/search`
(multipart — hỗ trợ upload CSV cho provider `csv_import`, tự lưu vào lịch sử),
`GET /api/search/runs` (danh sách lịch sử), `GET /api/search/runs/{run_id}`
(chi tiết 1 lần chạy), `GET /api/download/{csv,json}?run_id=...` (mặc định
lần gần nhất nếu không truyền `run_id`). Xem `saletool/api/routes/`.

### Chạy frontend (React)

```bash
cd frontend
npm install
npm run dev
```

Mở `http://127.0.0.1:5173`. Vite dev server proxy sẵn `/api/*` sang
`http://127.0.0.1:8000` (xem `frontend/vite.config.js`) nên không cần cấu
hình CORS thủ công lúc phát triển. Đăng nhập, điền tiêu chí tìm kiếm, chọn
provider (`mock` để demo, `apollo` với API key, hoặc `csv_import` để tải lên
CSV tự export từ Sales Navigator), bấm **Tìm kiếm** — kết quả hiển thị dạng
bảng theo từng công ty kèm liên hệ cấp cao, có nút tải CSV/JSON. Mỗi lần tìm
kiếm được lưu lại — trang **Lịch sử** liệt kê các lần chạy trước (tiêu chí,
provider, số công ty/liên hệ, thời gian) và cho xem lại/tải lại kết quả cũ.

Build production: `npm run build` (ra `frontend/dist/`) — deploy tĩnh sau
1 reverse proxy trỏ `/api/*` về FastAPI, phần còn lại phục vụ file tĩnh.

### Đổi database sang MongoDB (sau này)

```bash
pip install -r requirements-mongo.txt   # thêm pymongo
export SALETOOL_DB_BACKEND=mongo
export SALETOOL_MONGO_URI="mongodb://localhost:27017"
export SALETOOL_MONGO_DB=saletool
```

`saletool/db/base.py` định nghĩa 2 interface — `UserRepository` (tài khoản) và
`SearchRunRepository` (lịch sử tìm kiếm, mỗi lần chạy lưu tiêu chí + kết quả
đầy đủ); `sqlite_repo.py` và `mongo_repo.py` là 2 implementation cho cả hai —
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
  db/
    base.py               # interface UserRepository, SearchRunRepository
    sqlite_repo.py          # implementation SQLite (mặc định)
    mongo_repo.py            # implementation MongoDB (sẵn sàng, chưa bật mặc định)
    factory.py                # chọn implementation theo SALETOOL_DB_BACKEND
  api/
    app.py               # FastAPI app: CORS, include routers
    auth.py                # cấp phát/xác minh JWT
    deps.py                 # dependency get_current_user
    routes/
      auth.py                 # /api/auth/login, /api/auth/me
      search.py                # /api/search, /api/search/runs[/{id}], /api/download/{fmt}
frontend/               # React SPA (Vite) — login, dashboard, results, lịch sử
examples/
  search_criteria.example.yaml
  companies_export.example.csv
  contacts_export.example.csv
tests/
```
