# Chạy SaleTool + SearXNG trên máy local (Windows)

Tài liệu này ghi lại quy trình đã chạy thật trên Windows 10, Python 3.14.4,
Node 26.7.0. Ba service chạy song song, mỗi cái 1 terminal riêng:

| Service | Cổng | Vai trò |
|---|---|---|
| SearXNG | 8888 | meta-search tự host, cấp web search cho bước enrich |
| Backend FastAPI | 8000 | API: auth, search, enrich, settings |
| Frontend Vite (React) | 5173 | giao diện "ABIM Sales Assistant" |

Thứ tự khởi động không quan trọng, nhưng SearXNG nên chạy trước khi bấm
**Test connection** ở trang Settings.

---

## 1. Backend (FastAPI)

```bash
cd C:/Users/Admin/Documents/SaleTool

python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Tạo tài khoản đăng nhập (không có tự đăng ký công khai — tài khoản do người
vận hành tạo bằng CLI):

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m saletool.cli web create-user \
  --username demo --password demo1234
```

> **Cần `PYTHONIOENCODING=utf-8`.** Thiếu biến này, lệnh vẫn tạo tài khoản
> thành công nhưng ném `UnicodeEncodeError` lúc in thông báo tiếng Việt ra
> console Windows (codepage cp1252 không encode được chữ "Đ").
> Kiểm tra tài khoản đã có chưa:
>
> ```bash
> .venv/Scripts/python.exe -c "from saletool.db.factory import get_user_repository; print(bool(get_user_repository().get_password_hash('demo')))"
> ```

Chạy API:

```bash
PYTHONIOENCODING=utf-8 \
SALETOOL_SECRET_KEY=dev-local-secret-key-0123456789abcdef \
.venv/Scripts/python.exe -m saletool.cli web serve --host 127.0.0.1 --port 8000
```

> **`SALETOOL_SECRET_KEY` phải cố định giữa các lần restart.** Không đặt thì
> mỗi lần khởi động lại server sinh khoá tạm mới → mọi JWT cũ hết hiệu lực
> (phải đăng nhập lại), và các API key đã lưu ở trang Settings **không giải mã
> được nữa** (khoá mã hoá suy ra từ chính biến này qua HKDF).
> Giá trị ở trên chỉ dùng cho máy local. Deploy thật thì sinh khoá ngẫu nhiên:
> `python -c "import secrets; print(secrets.token_hex(32))"`.
>
> Lưu ý: dự án **không** tự nạp file `.env` — biến môi trường phải set trực
> tiếp trong terminal chạy lệnh.

Dữ liệu lưu ở SQLite `saletool.db` ngay trong thư mục dự án (mặc định
`SALETOOL_DB_BACKEND=sqlite`).

## 2. Frontend (React + Vite)

```bash
cd C:/Users/Admin/Documents/SaleTool/frontend
npm install
npm run dev
```

Mở **http://localhost:5173**, đăng nhập `demo` / `demo1234`.

Vite đã proxy sẵn `/api/*` sang `http://127.0.0.1:8000` (xem
`frontend/vite.config.js`) nên lúc dev không phải cấu hình CORS.

---

## 3. SearXNG

Máy này không có Docker và WSL chưa cài distro nào, nên SearXNG được cài
**native bằng Python** vào thư mục riêng `C:\Users\Admin\Documents\searxng`
(ngoài repo SaleTool). Requirements của SearXNG không có `uvloop` hay
`setproctitle` nên chạy được trên Windows, chỉ vướng 3 chỗ ghi ở dưới.

### 3.1. Clone — loại trừ file có tên không hợp lệ

```bash
cd C:/Users/Admin/Documents
git clone --depth 1 https://github.com/searxng/searxng.git searxng
cd searxng
git restore --source=HEAD -- ':/' ':(exclude)utils/templates'
```

Lệnh `git clone` sẽ báo checkout thất bại với 4 file:

```
error: invalid path 'utils/templates/etc/nginx/default.apps-available/searxng.conf:socket'
...
```

Tên file chứa dấu `:` — Windows cấm ký tự này. Lệnh `git restore` ở trên
checkout lại toàn bộ **trừ** `utils/templates` (chỉ là template deploy
nginx/uwsgi/httpd, không cần để chạy). Static assets của giao diện đã được
build sẵn và commit trong repo nên không cần Node để build theme.

### 3.2. Cài dependencies

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pip install tzdata
```

> **`tzdata` là bắt buộc trên Windows.** Windows không có sẵn IANA timezone
> database, thiếu nó một số engine chết lúc load:
> `ZoneInfoNotFoundError: 'No time zone found with key Asia/Shanghai'`.

### 3.3. Vá `pwd` (module chỉ có trên Unix)

`searx/valkeydb.py` import `pwd` ở top-level → trên Windows chết ngay khi
`searx.webapp` import `limiter`:

```
ModuleNotFoundError: No module named 'pwd'
```

Sửa `searx/valkeydb.py` — đổi phần import:

```python
import os

try:
    import pwd  # not available on Windows
except ImportError:
    pwd = None

import logging
```

và chỗ dùng nó trong `initialize()`:

```python
        _CLIENT = None
        if pwd is not None:
            _pw = pwd.getpwuid(os.getuid())
            logger.exception("[%s (%s)] can't connect valkey DB ...", _pw.pw_name, _pw.pw_uid)
        else:
            logger.exception("can't connect valkey DB ...")
```

Đây là nhánh log lỗi khi kết nối Valkey thất bại. Cấu hình dưới đây không dùng
Valkey nên nhánh này không bao giờ chạy tới.

### 3.4. File cấu hình

Tạo `C:\Users\Admin\Documents\searxng\settings-local.yml`:

```yaml
use_default_settings: true

general:
  instance_name: "SaleTool SearXNG"
  enable_metrics: true

server:
  bind_address: "127.0.0.1"
  port: 8888
  secret_key: "saletool-local-searxng-dev-secret-0123456789abcdef"
  limiter: false
  public_instance: false
  image_proxy: false

search:
  formats:
    - html
    - json
  safe_search: 0
  autocomplete: ""

ui:
  static_use_hash: true

outgoing:
  request_timeout: 10.0
  max_request_timeout: 15.0
  pool_connections: 100
  pool_maxsize: 20
```

> **`search.formats` phải có `json`.** Mặc định SearXNG chỉ bật `html`, trong
> khi SaleTool gọi `GET /search?q=...&format=json`
> (`saletool/enrichment/search/providers.py::SearxngSearchProvider`). Thiếu
> dòng này thì mọi request JSON trả **403**.
>
> `limiter: false` chấp nhận được vì instance chỉ nghe trên loopback. Nếu mở
> ra ngoài mạng thì phải bật lại.

### 3.5. Chạy

```bash
cd C:/Users/Admin/Documents/searxng
PYTHONIOENCODING=utf-8 \
SEARXNG_SETTINGS_PATH="C:/Users/Admin/Documents/searxng/settings-local.yml" \
.venv/Scripts/python.exe -m searx.webapp
```

> **Không được quên `SEARXNG_SETTINGS_PATH`** — thiếu nó SearXNG dùng settings
> mặc định (không có `json` trong formats) và API trả 403.

Kiểm tra:

```bash
curl -s "http://127.0.0.1:8888/search?q=abim+company&format=json" | head -c 300
```

---

## 4. Nối SearXNG vào SaleTool

Vào **http://localhost:5173** → trang **Settings**:

- **Web search**: chọn `searxng`, instance URL = `http://127.0.0.1:8888`
- Bật **use web search** ở phần Enrichment
- Bấm **Test connection** → mong đợi `Connected. Got N result(s).`

Hoặc làm bằng API:

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo1234"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -X PUT http://127.0.0.1:8000/api/settings \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{
  "llm": {"enabled": false, "provider": "openrouter", "base_url": "https://openrouter.ai/api/v1", "model": "google/gemini-2.0-flash-001"},
  "search": {"provider": "searxng", "searxng_url": "http://127.0.0.1:8888", "max_results": 5},
  "enrichment": {"use_web_search": true, "use_llm": false}
}'

curl -s -X POST http://127.0.0.1:8000/api/settings/test \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"target":"search"}'
```

### Về LLM

Cấu hình hiện tại đang **tắt LLM** (`llm.enabled: false`) vì chưa có API key
OpenRouter. Backend từ chối lưu settings với HTTP 400 *"LLM extraction is
enabled but no LLM API key is configured"* nếu bật LLM mà không có key.

Hệ quả: enrichment chạy tầng 0–2 (JSON-LD/meta/regex → sitemap + crawl website
→ web search qua SearXNG), **không có tầng 3 (LLM)**. Có key rồi thì vào trang
Settings nhập key, bật LLM và `use_llm` lại.

---

## 5. Kiểm tra nhanh cả hệ thống

```bash
curl -s -o /dev/null -w "searxng  HTTP %{http_code}\n" "http://127.0.0.1:8888/search?q=test&format=json"
curl -s -o /dev/null -w "backend  HTTP %{http_code}\n" http://127.0.0.1:8000/api/settings   # 401 = sống (thiếu token)
curl -s -o /dev/null -w "frontend HTTP %{http_code}\n" http://localhost:5173/
```

Thử luồng search (Apollo API key lấy từ Settings, không truyền qua form nữa —
nhập key ở trang Settings trước khi chạy lệnh này):

```bash
curl -s -X POST http://127.0.0.1:8000/api/search \
  -H "Authorization: Bearer $TOKEN" \
  -F "config=@examples/search_criteria.example.yaml"
```

---

## 6. Lỗi thường gặp

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| `UnicodeEncodeError: 'charmap' codec can't encode '\u0110'` | console Windows cp1252 in tiếng Việt | `PYTHONIOENCODING=utf-8` (lệnh vẫn chạy đúng, chỉ lỗi lúc in) |
| SearXNG trả **403** cho `format=json` | thiếu `json` trong `search.formats`, hoặc chạy mà quên `SEARXNG_SETTINGS_PATH` | xem 3.4 / 3.5 |
| `ModuleNotFoundError: No module named 'pwd'` | `valkeydb.py` import module Unix-only | vá theo 3.3 |
| `ZoneInfoNotFoundError` lúc load engine | Windows thiếu IANA tz database | `pip install tzdata` |
| `git clone` báo `invalid path ...conf:socket` | tên file chứa `:` | checkout loại trừ `utils/templates`, xem 3.1 |
| PUT `/api/settings` trả 400 về LLM key | bật LLM nhưng chưa nhập key | nhập key, hoặc đặt `llm.enabled: false` |
| Đăng nhập lại sau mỗi lần restart backend | `SALETOOL_SECRET_KEY` không cố định | set biến này, xem mục 1 |
| Engine `ahmia` / `torch` không load | 2 engine này cần Tor proxy | bỏ qua — mặc định vốn đã tắt |
| `wikidata: engine init was not successful` (getaddrinfo) | DNS lỗi lúc khởi động | bỏ qua nếu search vẫn trả kết quả |
