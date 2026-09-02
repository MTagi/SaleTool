# Chạy SaleTool bằng Docker Compose

Mặc định dựng 2 service: **backend** (FastAPI) và **frontend** (React build sẵn,
phục vụ qua nginx). Dữ liệu nằm trong SQLite trên một volume. MongoDB và SearXNG
là 2 profile tuỳ chọn, không bật thì không chạy.

| Service | Cổng trên host | Vai trò |
|---|---|---|
| `frontend` | 8080 | Giao diện "ABIM Sales Assistant" + proxy `/api/*` sang backend |
| `backend` | 127.0.0.1:8000 | API (chỉ mở loopback, dùng để curl/gỡ lỗi) |
| `mongo` | — | Chỉ với `--profile mongo` |
| `searxng` | 127.0.0.1:8888 | Chỉ với `--profile searxng` |

## 1. Chuẩn bị biến môi trường

```bash
cp .env.example .env
```

Rồi điền **`SALETOOL_SECRET_KEY`** trong `.env`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> **Khoá này phải cố định giữa các lần restart.** Nó vừa ký JWT vừa là gốc suy ra
> khoá mã hoá các API key lưu ở trang Settings (qua HKDF). Đổi khoá = mọi người
> phải đăng nhập lại **và** nhập lại API key. Chưa đặt thì `docker compose up`
> dừng ngay với thông báo, thay vì để server tự sinh khoá tạm rồi hỏng ngầm.

Bản thân ứng dụng **không** đọc file `.env` — đọc `.env` là việc của Docker
Compose, nó thay `${...}` trong `docker-compose.yml` rồi truyền vào container
thành biến môi trường thật.

## 2. Dựng và chạy

```bash
docker compose up -d --build
```

Tạo tài khoản đăng nhập (không có tự đăng ký công khai). Chạy một lần, dùng chung
ảnh backend:

```bash
docker compose run --rm backend python -m saletool.cli web create-user --username demo
```

Mở **http://localhost:8080** và đăng nhập.

Xem log / dừng:

```bash
docker compose logs -f backend
docker compose down          # giữ dữ liệu (volume vẫn còn)
docker compose down -v       # XOÁ luôn volume: mất tài khoản + lịch sử search
```

## 3. Chạy CLI trong container

Ảnh backend chứa cả CLI. Thư mục hiện tại mount vào `/work` để đọc file tiêu chí
và ghi kết quả ra ngay máy host:

```bash
docker compose run --rm -v "$PWD:/work" -w /work backend \
  python -m saletool.cli search \
  --config examples/search_criteria.example.yaml \
  --output output.csv
```

Khảo sát mà không tốn credit Apollo (bỏ bước tra email):

```bash
docker compose run --rm -v "$PWD:/work" -w /work backend \
  python -m saletool.cli search --config examples/search_criteria.example.yaml \
  --no-reveal-emails --output output.csv
```

CLI lấy Apollo key từ `APOLLO_API_KEY` trong `.env`. Web UI thì nhận key theo
từng request trong form, không cần biến này.

> **Trên Windows chạy bằng Git Bash**: thêm `MSYS_NO_PATHCONV=1` trước lệnh.
> Không có nó, Git Bash tự đổi `/work` thành đường dẫn Windows và Docker báo
> `the working directory 'C:/Program Files/Git/work' is invalid`. PowerShell và
> CMD không dính lỗi này.
>
> ```bash
> MSYS_NO_PATHCONV=1 docker compose run --rm -v "/d/AbimSaleTool:/work" -w /work backend \
>   python -m saletool.cli search --config examples/search_criteria.example.yaml --output output.csv
> ```

## 4. Profile tuỳ chọn

### MongoDB

```bash
# trong .env
SALETOOL_DB_BACKEND=mongo
```

```bash
docker compose --profile mongo up -d
```

`SALETOOL_MONGO_URI` mặc định đã là `mongodb://mongo:27017` (tên service trong
mạng compose). Đổi backend **không** chuyển dữ liệu cũ sang — tài khoản phải tạo
lại bằng `create-user`.

### SearXNG (web search miễn phí cho enrichment)

```bash
docker compose --profile searxng up -d
```

Vào trang **Settings** → Web search = `searxng`, instance URL =
**`http://searxng:8080`**. Đây là tên service trong mạng compose, **không phải**
`127.0.0.1:8888` — cổng đó chỉ để bạn mở bằng trình duyệt từ host.

Hai dòng log bình thường, không phải lỗi cấu hình: `ahmia`/`torch` không load
được (2 engine đó cần Tor proxy, mặc định vốn đã tắt), và DuckDuckGo thỉnh
thoảng trả CAPTCHA — SearXNG vẫn trả kết quả từ các engine còn lại.

Cấu hình nằm ở `docker/searxng/settings.yml`. Chỗ quan trọng nhất là
`search.formats` có `json`: SaleTool gọi `GET /search?q=...&format=json`, mặc
định SearXNG chỉ bật `html` và trả **403** cho mọi request JSON. Nhớ đổi
`server.secret_key` trước khi dùng ngoài máy local.

## 5. Playwright (tầng dự phòng render JS)

Mặc định **tắt** — chromium và thư viện hệ thống làm ảnh phồng thêm khoảng 700MB.
Thiếu nó pipeline enrich vẫn chạy bình thường: `PlaywrightFetcher` trả về lỗi và
`FallbackFetcher` giữ nguyên kết quả HTTP. Chỉ những site render hoàn toàn bằng
JS là lấy được ít dữ liệu hơn.

Muốn bật:

```bash
# trong .env
SALETOOL_INSTALL_BROWSER=true
```

```bash
docker compose build backend && docker compose up -d
```

## 6. Đưa ra production

Compose này dựng cho môi trường nội bộ. Trước khi mở ra ngoài internet:

- Đặt cả hệ thống sau **HTTPS reverse proxy**. Bản thân app chưa có giới hạn số
  lần đăng nhập sai, chưa có refresh/thu hồi token, chưa có khôi phục mật khẩu.
- Đổi `server.secret_key` của SearXNG và bật lại `limiter` nếu instance không
  còn chỉ nghe loopback.
- Đổi `enrichment.user_agent` trong Settings thành email thật — đó là phần
  "trung thực" của chính sách crawl lịch sự, cùng với `robots.txt` và nhịp nghỉ
  1 giây mỗi domain (đừng tắt hai thứ này).
- Cân nhắc bỏ dòng mở cổng `127.0.0.1:8000:8000` của backend.
