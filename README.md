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
    mock.py              # provider giả lập để demo/test
  pipeline.py          # điều phối: tìm công ty -> tìm liên hệ mỗi công ty
  output.py             # xuất CSV/JSON
  cli.py                 # CLI: saletool search --config ... --provider ...
examples/
  search_criteria.example.yaml
tests/
```
