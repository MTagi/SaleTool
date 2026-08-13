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
  cli.py                 # CLI: saletool search --config ... --provider ...
examples/
  search_criteria.example.yaml
  companies_export.example.csv
  contacts_export.example.csv
tests/
```
