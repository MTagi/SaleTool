# Backend SaleTool: FastAPI + Click CLI.
#
# Ảnh này phục vụ cả 2 vai trò, vì cùng một package:
#   - chạy API   : lệnh mặc định bên dưới
#   - chạy CLI   : docker compose run --rm backend python -m saletool.cli ...
#     (tạo tài khoản, chạy search không cần web UI)

FROM python:3.12-slim

# PYTHONIOENCODING: CLI in tiếng Việt ra stdout. Container Linux vốn đã UTF-8,
# đặt tường minh để log không phụ thuộc locale của base image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Cài dependency trước khi copy source: sửa code không làm mất cache lớp cài đặt.
# pymongo được cài sẵn dù mặc định chạy SQLite — đổi SALETOOL_DB_BACKEND=mongo
# lúc đó chỉ cần restart, không phải build lại ảnh.
COPY requirements.txt requirements-mongo.txt ./
RUN pip install -r requirements.txt -r requirements-mongo.txt

# Playwright chỉ là tầng dự phòng khi trang render bằng JS (extras `browser`).
# Mặc định TẮT vì chromium + thư viện hệ thống làm ảnh phồng thêm ~700MB. Thiếu
# nó pipeline enrich vẫn chạy: PlaywrightFetcher trả về lỗi và FallbackFetcher
# giữ nguyên kết quả HTTP.
ARG INSTALL_BROWSER=false
RUN if [ "$INSTALL_BROWSER" = "true" ]; then \
        pip install playwright && playwright install --with-deps chromium; \
    fi

# Không `pip install .` — WORKDIR đã nằm trong sys.path nên `python -m saletool.cli`
# chạy thẳng, và source được bind-mount lúc dev sẽ có hiệu lực ngay.
COPY saletool ./saletool
COPY examples ./examples

# File SQLite nằm ở /data (một volume), không nằm trong lớp ghi của container —
# nếu không, `docker compose down` là mất sạch tài khoản và lịch sử search.
RUN useradd --create-home --uid 10001 saletool \
    && mkdir -p /data \
    && chown saletool:saletool /data
ENV SALETOOL_DB_PATH=/data/saletool.db

USER saletool

EXPOSE 8000

# curl không có sẵn trong ảnh slim nên healthcheck dùng luôn Python.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health', timeout=5)"

CMD ["python", "-m", "saletool.cli", "web", "serve", "--host", "0.0.0.0", "--port", "8000"]
