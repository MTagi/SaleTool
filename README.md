# SaleTool

Công cụ: từ **1 input format mô tả mục tiêu tìm kiếm công ty**, tìm ra
**danh sách công ty phù hợp trên LinkedIn**, rồi lấy ra **danh sách liên hệ
(ưu tiên các cấp cao — C-level, VP, Director...)** của từng công ty đó.

## Cách tiếp cận dữ liệu

SaleTool **không** tự động hoá trình duyệt để scrape trực tiếp
`linkedin.com` — việc này vi phạm Terms of Service của LinkedIn và có rủi ro
pháp lý/khoá tài khoản. Thay vào đó, SaleTool gọi API của
[Apollo.io](https://apollo.io) — bên đã tổng hợp dữ liệu công ty/liên hệ (kèm
link LinkedIn) một cách hợp pháp. Bạn cần tài khoản Apollo và API key hợp lệ.

### Dùng Apollo.io cho hiệu quả

Bốn điều về API Apollo quyết định cách nhập tiêu chí — biết trước thì đỡ mất
credit và đỡ tưởng là mình nhập sai:

**1. Ô "Industries" thực chất chạy bằng từ khoá.** Apollo lọc ngành qua *tag ID*
nội bộ, không qua tên ngành. SaleTool tự đẩy tên ngành bạn gõ sang
`q_organization_keyword_tags` (khớp theo mô tả công ty) — sát hơn nhiều so với
taxonomy thô của Apollo. Gõ `payment gateway, e-wallet` cho kết quả tốt hơn
`Financial Services`. Ai đã tra được tag ID thật (chuỗi 24 ký tự hex) thì dán
vào chính ô đó, code tự nhận ra và dùng đúng bộ lọc.

**2. Search không trả email.** Apollo chỉ cho biết người đó *có* email hay
không; lấy email thật là một lượt gọi riêng và **đó mới là chỗ trừ credit**.
SaleTool chỉ tra cho những người Apollo đã báo là có email, gộp 10 người/lượt.
Bỏ tick **"Look up email addresses"** (hoặc `--no-reveal-emails` ở CLI) để khảo
sát xem bao nhiêu công ty/người khớp tiêu chí mà không tốn gì.

**3. Email cá nhân mặc định tắt.** Email công việc là thứ dùng cho B2B; email cá
nhân tốn thêm credit và Apollo không trả về với người ở vùng áp dụng GDPR.

**4. Quy mô là bộ lọc mạnh nhất.** Đặt cả min lẫn max — nó loại một lúc cả tập
đoàn (không tiếp cận được bằng cold outreach) lẫn công ty 5 người (không có ngân
sách). Kèm với đó: giữ **1–2 liên hệ/công ty** (số liệu Apollo: 1–2 người đạt
~7,8% tỉ lệ trả lời, từ 10 người trở lên tụt còn ~3,8%), và đừng tick hết 7 mức
seniority — công ty <200 người thì `c_suite`/`founder` trả lời tốt, công ty lớn
thì nhắm `head`/`director` đúng phòng ban.

Nếu gặp **403**: key chưa bật quyền API hoặc gói thuê bao không cho phép
endpoint đó. SaleTool dùng `mixed_people/api_search` (bản dành cho API) chứ
không dùng `mixed_people/search` — endpoint sau trả 403 trên gói Basic.

### Muốn dùng nguồn khác ngoài Apollo?

Hiện SaleTool **chỉ hỗ trợ Apollo**. Interface `CompanyContactProvider`
(`saletool/providers/base.py`) và factory `get_provider()` vẫn còn nguyên, nên
thêm nhà cung cấp khác (People Data Labs, Coresignal…) hoặc dựng lại luồng
import CSV thủ công từ Sales Navigator chỉ là viết thêm một lớp — không phải
sửa route hay pipeline. Hai provider `mock` và `csv_import` đã từng có, xem
lịch sử git nếu cần lấy lại.

## Cài đặt

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # điền APOLLO_API_KEY
```

Chạy trên Windows, hoặc muốn dựng luôn cả SearXNG để có web search miễn phí:
xem [docs/chay-local.md](docs/chay-local.md).

## Sử dụng

1. Mô tả mục tiêu tìm kiếm trong file YAML/JSON — xem mẫu tại
   `examples/search_criteria.example.yaml` (đầy đủ các trường xem
   `saletool/models.py::SearchCriteria`).

2. Chạy với Apollo:

   ```bash
   export APOLLO_API_KEY="..."

   python -m saletool.cli search \
     --config examples/search_criteria.example.yaml \
     --output output.csv
   ```

3. Muốn xem có bao nhiêu công ty/người khớp tiêu chí mà **không tốn credit**
   (bỏ qua bước tra email):

   ```bash
   python -m saletool.cli search \
     --config examples/search_criteria.example.yaml \
     --no-reveal-emails \
     --output output.csv
   ```

Kết quả xuất ra CSV (mặc định) hoặc JSON (`--output result.json`), mỗi dòng
là 1 cặp (công ty, liên hệ).

## Web UI — "ABIM Sales Assistant" (FastAPI API + React, có đăng nhập)

Giao diện web mang tên **ABIM Sales Assistant**, toàn bộ UI bằng tiếng Anh,
gồm 8 trang. Năm trang đầu là **một quy trình có thứ tự**, hiển thị thành thanh
5 bước ngay dưới thanh điều hướng, có đánh dấu bước nào đã xong:

> **1 Search** (tìm công ty) → **2 Enrich** (đọc website của họ) →
> **3 Catalog** (dịch vụ bạn bán) → **4 Match** (xếp hạng danh sách) →
> **5 Message** (viết cho từng contact)

Ba trang còn lại nằm ở thanh trên: **History** (lịch sử tìm kiếm), **Settings**
(cấu hình LLM + công cụ search + nguồn enrich + hồ sơ người gửi), **Account**
(tài khoản + đổi mật khẩu).

Hai nguyên tắc UI đáng nói:

- **Chặn trước, không báo lỗi sau.** Một lượt gọi `GET /api/status` cho biết đã
  có LLM key chưa, có hồ sơ người gửi chưa, catalog có dịch vụ nào chưa. Trang
  Matching/Messages hiện ngay đầu trang thứ còn thiếu kèm link tới đúng chỗ sửa,
  và khoá nút submit — thay vì để người dùng điền hết form rồi nhận lỗi 400.
- **Nối các bước lại.** Xong search có nút *Rank them →* mang sẵn `run_id` sang
  Matching; xong matching có nút *Write messages →* mang cả `run_id` lẫn
  `match_job_id` sang Messages. Không phải chọn lại thủ công ở từng trang.

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
`POST /api/search` (multipart, tự lưu vào lịch sử), `GET /api/search/runs` (danh sách lịch sử),
`GET /api/search/runs/{run_id}` (chi tiết 1 lần chạy), `GET
/api/download/{csv,json}?run_id=...` (mặc định lần gần nhất nếu không truyền
`run_id`), `GET|PUT /api/settings` + `POST /api/settings/test`,
`POST /api/enrich` + `GET /api/enrich/jobs[/{job_id}]`,
`GET|POST /api/catalog` + `PUT|DELETE /api/catalog/{service_id}`,
`GET /api/search/options` (danh sách seniority — frontend không giữ bản chép),
`GET /api/status` (trạng thái cấu hình + số liệu, dùng cho thanh 5 bước),
`POST /api/match` + `GET /api/match/jobs[/{job_id}]`,
`GET /api/messages/options`, `POST /api/messages` + `GET /api/messages/jobs[/{job_id}]`.
Xem `saletool/api/routes/`.

### Chạy frontend (React)

```bash
cd frontend
npm install
npm run dev
```

Mở `http://127.0.0.1:5173`. Vite dev server proxy sẵn `/api/*` sang
`http://127.0.0.1:8000` (xem `frontend/vite.config.js`) nên không cần cấu
hình CORS thủ công lúc phát triển. Đăng nhập, điền tiêu chí tìm kiếm ở trang
**Search**, điền Apollo API key, bấm **Search** —
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

### Catalog + Matching — xếp hạng công ty theo dịch vụ bạn bán

Hai trang này trả lời câu hỏi cuối cùng của quy trình: *trong danh sách vừa tìm
được, nên gọi ai trước?*

**Trang Catalog** quản lý danh mục dịch vụ của chính công ty bạn — tên, dịch vụ
làm gì, vì sao khách chọn bạn, ngành và quy mô khách hàng phù hợp, và **tín hiệu
mua hàng** (dấu hiệu cho thấy một công ty đang cần dịch vụ đó). Catalog dùng
chung cho cả đội, giống Settings.

> Chất lượng mô tả ở đây quyết định trực tiếp chất lượng xếp hạng — LLM chỉ đọc
> đúng những gì bạn ghi. Dịch vụ chỉ có mỗi cái tên sẽ được chấm dựa trên mỗi cái
> tên. Trang này gắn nhãn `Too thin` / `Usable` / `Detailed` cho từng dịch vụ để
> thấy ngay cái nào cần viết thêm.

**Trang Matching** chọn 1 lần search trong lịch sử + các dịch vụ muốn map, tuỳ
chọn thêm 1 câu mô tả tiêu chí ưu tiên (vd *"ưu tiên công ty đang mở rộng ở miền
Bắc"*), rồi chạy nền và trả về danh sách đã xếp hạng.

Cách chấm:

| Bước | Ai làm | Vì sao |
|---|---|---|
| Dựng hồ sơ công ty | code | Gộp kết quả search + **dữ liệu enrich đã có** (nếu công ty đó từng được enrich) |
| Chấm điểm từng cặp (công ty, dịch vụ) | LLM | 1 lượt gọi/công ty, thang điểm 0–100 mô tả sẵn trong prompt |
| Tính điểm tổng + xếp thứ tự | **code** | Để thứ hạng giải thích được và không đổi giữa 2 lần chạy |

Điểm tổng = điểm của **dịch vụ khớp nhất** — thực tế bán hàng chỉ cần một dịch vụ
đủ hợp là đã có lý do tiếp cận. Bằng điểm thì công ty hợp với nhiều dịch vụ hơn
đứng trước. Công ty chấm lỗi luôn nằm cuối, không lẫn với công ty điểm thấp thật.

Mỗi công ty hiển thị: điểm, dịch vụ khớp nhất kèm lý do, tóm tắt hành động,
**Signals** (dữ kiện ủng hộ), **Concerns** (điểm trừ, gồm cả "thiếu thông tin"),
và điểm chi tiết cho từng dịch vụ còn lại.

Hai điều đáng biết:

- **Enrich trước khi match thì điểm sát hơn hẳn.** Công ty chưa enrich được gắn
  nhãn *"Scored on search results only"*, và prompt yêu cầu model tự hạ trần điểm
  khi hồ sơ quá mỏng — thà chấm thấp còn hơn tự tin trên không có gì.
- **Kết quả chụp lại danh sách dịch vụ lúc chạy.** Sửa hoặc xoá dịch vụ trong
  catalog sau đó không làm sai lệch các bảng xếp hạng cũ.

Cần cấu hình LLM API key ở Settings trước khi dùng.

### Messages — sinh message gửi cho từng contact

Bước cuối: có contact rồi thì viết gì cho họ. Chọn 1 lần search, tick những
người muốn viết, chọn kênh + giọng văn + ngôn ngữ, chạy nền.

**Ngữ cảnh lấy từ chính các bước trước** — đó là lý do bước này nằm cuối chuỗi:

| Nguồn | Đóng góp vào message |
|---|---|
| Kết quả search | Tên, chức danh, công ty, email/LinkedIn của người nhận |
| Enrichment | Công ty làm gì, ngành, công nghệ đang dùng |
| **Matching** | **Dịch vụ khớp nhất + lý do khớp** — chính là câu mở đầu |
| Settings → Sender profile | Bạn là ai, công ty bạn làm gì, chữ ký |

Không có bước Matching thì vẫn viết được, nhưng message sẽ thiếu lý do cụ thể
để tiếp cận — trang này nói thẳng điều đó trước khi chạy.

#### Prompt tham khảo Apollo.io

Nguyên tắc lấy từ hướng dẫn công khai của Apollo (bên có số liệu trên hàng
triệu email thật), đưa thẳng vào prompt:

- **Situational awareness, không phải demographic awareness.** "Tôi thấy anh là
  CFO ngành sản xuất" là mail-merge. "Công ty anh đang chốt sổ thủ công qua ba
  nhà máy" mới là lý do người ta trả lời. Prompt bắt câu đầu tiên phải nói về
  *tình huống* của họ.
- **6–8 câu** cho email lạnh — khoảng Apollo đo được tỉ lệ trả lời cao nhất.
- **Một ý, một lời đề nghị.** CTA thứ hai làm giảm tỉ lệ trả lời.
- **1–2 người/công ty**, không rải cả phòng ban: Apollo đo 1–2 người đạt ~7,8%
  trả lời, từ 10 người trở lên tụt còn ~3,8%. Trang có sẵn nút *Pick 1/2 per
  company*, và cảnh báo nếu bạn chọn quá số này.
- **Không bịa.** Prompt ghi rõ: hồ sơ mỏng thì viết ngắn và thật, đừng viết dài
  và nghe có vẻ cụ thể.

#### Code kiểm lại, không chỉ tin prompt

Prompt ghi giới hạn ký tự thì model vẫn vượt, và vẫn để sót `[Tên công ty]`.
Với LinkedIn, vượt giới hạn **không phải lỗi thẩm mỹ — nền tảng từ chối gửi**.
Nên mọi ràng buộc đo được đều được backend kiểm lại sau khi model trả kết quả:

| Kênh | Giới hạn thật |
|---|---|
| Cold email | tiêu đề ≤ 60 ký tự, thân ≤ 125 từ |
| Follow-up email | tiêu đề ≤ 60 ký tự, thân ≤ 90 từ |
| LinkedIn connection note | ≤ **300** ký tự (tài khoản free: 200), không có tiêu đề |
| LinkedIn InMail | tiêu đề ≤ 200, thân ≤ 1900 ký tự |

Ngoài độ dài còn kiểm: placeholder còn sót (`[Name]`, `{{company}}`, `TBD`),
model tự nói về mình ("as an AI"), không gọi tên người nhận, và trường hợp model
tự khai là **không** cá nhân hoá được gì. Mọi vấn đề hiện ngay cạnh nội dung —
code **không tự sửa**, vì cắt ngang một câu còn tệ hơn để người dùng tự sửa.

Hỗ trợ **tiếng Anh và tiếng Việt**. Mỗi message có nút Copy, mở sẵn mail app,
và link tới profile LinkedIn của người nhận nếu có.

### Settings — cấu hình LLM và công cụ search

Cấu hình dùng chung cho cả hệ thống (không per-user). **API key được mã hoá
trước khi lưu và không bao giờ trả về trình duyệt** — UI chỉ thấy bản mask.

- **LLM**: mặc định OpenRouter (API tương thích OpenAI). Chọn model hỗ trợ
  structured output; trích xuất từ text đã sạch là việc dễ nên model nhỏ, rẻ là đủ.
- **Web search**: `none` (mặc định — chỉ đọc website công ty, hoàn toàn free),
  `searxng` (tự host, free, không cần key), `brave` / `tavily` / `serper` (trả phí).
- **Sender profile**: bạn là ai khi gửi message (tên, chức danh, công ty, mô tả
  công ty, link đặt lịch, chữ ký). Thiếu tên + công ty thì bước Messages bị chặn —
  message không có người gửi thì LLM buộc phải bịa ra một người.
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

## Lint

```bash
ruff check .          # cấu hình trong pyproject.toml
ruff check . --fix
```

Rule `BLE` (bắt Exception quá rộng) được bật có chủ đích: code có vài chỗ bắt
rộng **cố ý** — 1 công ty lỗi không được làm hỏng cả job — và đánh dấu
`# noqa: BLE001` kèm lý do. Bật rule thì những dòng đó có nghĩa, và chỗ bắt rộng
*không* chủ đích sẽ bị chặn.

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
    base.py            # interface CompanyContactProvider (điểm mở rộng)
    apollo.py           # provider duy nhất hiện tại
  seniority.py         # suy luận seniority từ title tự do
  pipeline.py          # điều phối: tìm công ty -> tìm liên hệ mỗi công ty
  output.py             # xuất CSV/JSON
  cli.py                 # CLI: saletool search / saletool web serve|create-user
  crypto.py             # mã hoá API key trước khi lưu DB
  db/
    base.py               # 5 interface + 1 JobRepository generic dùng chung cho
                          #   enrich/matching/message (3 loại job cùng vòng đời)
    sqlite_repo.py          # implementation SQLite (mặc định)
    mongo_repo.py            # implementation MongoDB (sẵn sàng, chưa bật mặc định)
    factory.py                # chọn implementation theo SALETOOL_DB_BACKEND
  enrichment/
    pipeline.py           # điều phối 4 tầng enrich
    discovery.py            # sitemap + crawl nông + tạo query search
    fetcher.py               # HTTP -> Playwright fallback, robots.txt, rate limit
    extractor.py              # HTML -> text sạch (trafilatura)
    structured.py              # tầng 0: JSON-LD, meta, mailto/tel, regex
    llm.py                      # prompt + schema trích xuất thông tin công ty
    search/                      # SearchProvider: none/searxng/brave/tavily/serper
  llm_api.py            # lớp gọi LLM dùng chung (json_schema -> json_object fallback)
  prompt_text.py        # cắt gọn text trước khi đưa vào prompt (dùng chung)
  matching/
    pipeline.py           # dựng hồ sơ công ty, gộp dữ liệu enrich, xếp hạng
    llm.py                  # prompt chấm điểm + map nhãn dịch vụ về id thật
  messaging/
    pipeline.py           # dựng brief người gửi/người nhận + KIỂM LẠI kết quả LLM
    llm.py                  # prompt viết message theo từng kênh gửi
  api/
    app.py               # FastAPI app: CORS, include routers
    auth.py                # cấp phát/xác minh JWT
    jobs.py                 # chạy job enrich/matching ở nền, ghi tiến độ xuống DB
    deps.py                 # dependency get_current_user
    routes/
      auth.py                 # /api/auth/login, /api/auth/me, /api/auth/change-password
      search.py                # /api/search, /api/search/runs[/{id}], /api/download/{fmt}
      settings.py               # /api/settings, /api/settings/test
      enrich.py                  # /api/enrich, /api/enrich/jobs[/{id}]
      catalog.py                  # /api/catalog[/{service_id}]
      match.py                     # /api/match, /api/match/jobs[/{id}]
      messages.py                   # /api/messages, /api/messages/jobs[/{id}]
      status.py                      # /api/status — cái gì đã cấu hình, cái gì đã có
frontend/               # React SPA (Vite) "ABIM Sales Assistant", tiếng Anh
                         # — Search, Enrichment, Catalog, Matching, Messages,
                         #   History, Settings, Account
docs/
  chay-local.md          # hướng dẫn chạy local (SaleTool + SearXNG) trên Windows
  research/              # khảo sát: các cách lấy dữ liệu công ty trên LinkedIn
examples/
  search_criteria.example.yaml
tests/
```
