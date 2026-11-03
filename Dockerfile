# Backend SaleTool: FastAPI + Click CLI.
#
# This image serves two roles because both use the same package:
#   - run the API: the default command below
#   - run the CLI: docker compose run --rm backend python -m saletool.cli ...
#     (create accounts or search without the web UI)

FROM python:3.12-slim

# PYTHONIOENCODING: the CLI may print non-ASCII text to stdout. Linux containers
# already use UTF-8; set this explicitly so logs do not depend on the base image locale.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies before copying source so code changes do not invalidate
# the dependency layer cache. pymongo is installed even though SQLite is the
# default; switching SALETOOL_DB_BACKEND=mongo only requires a restart, not a rebuild.
COPY requirements.txt requirements-mongo.txt ./
RUN pip install -r requirements.txt -r requirements-mongo.txt

# Playwright is only a fallback for JavaScript-rendered pages (the `browser` extra).
# Disabled by default because Chromium and system libraries add ~700 MB. Without
# it, enrichment still runs: PlaywrightFetcher returns an error and FallbackFetcher
# preserves the HTTP result.
ARG INSTALL_BROWSER=false
RUN if [ "$INSTALL_BROWSER" = "true" ]; then \
        pip install playwright && playwright install --with-deps chromium; \
    fi

# Do not `pip install .`: WORKDIR is already on sys.path, so `python -m saletool.cli`
# runs directly, and source bind-mounted during development takes effect immediately.
COPY saletool ./saletool
COPY examples ./examples

# The SQLite file is in /data (a volume), not in the container's writable layer;
# otherwise `docker compose down` would remove all accounts and search history.
RUN useradd --create-home --uid 10001 saletool \
    && mkdir -p /data \
    && chown saletool:saletool /data
ENV SALETOOL_DB_PATH=/data/saletool.db

USER saletool

EXPOSE 8000

# curl is not available in the slim image, so the healthcheck uses Python.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health', timeout=5)"

CMD ["python", "-m", "saletool.cli", "web", "serve", "--host", "0.0.0.0", "--port", "8000"]
