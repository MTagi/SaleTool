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

## Web UI (có đăng nhập)

Ngoài CLI, SaleTool có web UI chạy bằng FastAPI, bảo vệ bằng đăng nhập
(session cookie + mật khẩu băm PBKDF2, lưu tài khoản trong SQLite). Không có
tự đăng ký công khai — tài khoản do người vận hành tạo qua CLI, phù hợp một
tool dùng nội bộ trong nhóm nhỏ.

```bash
# 1. Đặt secret key để phiên đăng nhập không mất khi restart server
export SALETOOL_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"

# 2. Tạo tài khoản đăng nhập
python -m saletool.cli web create-user --username demo

# 3. Chạy server
python -m saletool.cli web serve --host 127.0.0.1 --port 8000
```

Mở `http://127.0.0.1:8000`, đăng nhập, điền tiêu chí tìm kiếm, chọn provider
(`mock` để demo, `apollo` với API key, hoặc `csv_import` để tải lên CSV bạn
tự export từ Sales Navigator), bấm **Tìm kiếm**. Kết quả hiển thị dạng bảng
theo từng công ty kèm liên hệ cấp cao, có nút tải về CSV/JSON.

**Phạm vi bảo mật:** phù hợp dùng nội bộ sau HTTPS reverse proxy đáng tin cậy.
Chưa có: giới hạn số lần đăng nhập sai, khôi phục mật khẩu, CSRF token riêng —
cần bổ sung thêm nếu triển khai ra ngoài internet công khai.

## Test

```bash
pytest
```

## Cấu trúc dự án

```
saletool/
  models.py          # SearchCriteria, Company, Contact, CompanyResult
  config.py           # nạp input format YAML/JSON
  providers/
    base.py            # interface CompanyContactProvider
    apollo.py           # provider Apollo.io
    csv_import.py        # provider import CSV thủ công (vd: Sales Navigator)
    mock.py              # provider giả lập để demo/test
  seniority.py         # suy luận seniority từ title tự do
  pipeline.py          # điều phối: tìm công ty -> tìm liên hệ mỗi công ty
  output.py             # xuất CSV/JSON
  cli.py                 # CLI: saletool search / saletool web serve|create-user
  web/
    app.py                # FastAPI app: login, dashboard, search, download
    auth.py                # băm/xác thực mật khẩu (PBKDF2, stdlib only)
    users_db.py             # lưu tài khoản (SQLite)
    templates/               # Jinja2: base, login, dashboard, results
    static/style.css          # giao diện
examples/
  search_criteria.example.yaml
  companies_export.example.csv
  contacts_export.example.csv
tests/
```
