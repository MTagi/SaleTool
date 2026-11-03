# ABIM Sales Assistant

A B2B sales research tool that finds companies and decision-makers, researches prospects, ranks them against your services, and drafts personalized outreach.

## Features

- **Search:** find companies and contacts through Apollo, with optional email lookup.
- **Enrich:** combine company websites, web search, structured extraction, and AI into sourced research reports.
- **Catalog:** manage the services you offer and their target customers.
- **Match:** score and rank prospects against selected services using search and enrichment evidence.
- **Messages:** draft emails and LinkedIn messages in English or Vietnamese. Review and send them yourself.
- **History:** revisit results and export search data as CSV or JSON.

## Run with Docker Compose

Requires Docker Engine with Docker Compose, or Docker Desktop. Run commands from the repository root.

### 1. Create the environment file

PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

Generate a secret, then paste the result into `SALETOOL_SECRET_KEY` in `.env`:

```bash
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_hex(32))"
```

Keep this secret unchanged across restarts. It signs login tokens and encrypts API keys stored in the database.

The example environment file selects MongoDB:

```dotenv
SALETOOL_SECRET_KEY=replace-with-your-generated-secret
SALETOOL_API_PORT=8000
COMPOSE_PROFILES=mongo
SALETOOL_DB_BACKEND=mongo
SALETOOL_MONGO_URI=mongodb://mongo:27017
SALETOOL_MONGO_DB=saletool
```

If port `8000` is occupied, change `SALETOOL_API_PORT`, for example to `18002`. The frontend defaults to port `8080`; set `SALETOOL_WEB_PORT` to change it.

### 2. Start the services

Start MongoDB and wait for it to become healthy, then build and start the application:

```bash
docker compose up -d --wait mongo
docker compose up -d --build --wait
```

| Service | Purpose | Host access |
|---|---|---|
| `frontend` | Nginx serves React and proxies `/api/*` to the backend | `http://localhost:8080` |
| `backend` | FastAPI and background enrichment, matching, and drafting jobs | Loopback only, `http://127.0.0.1:8000` by default |
| `mongo` | Accounts, Settings, catalog, search history, and job results | Internal Docker network only; port `27017` is not published |

This configuration runs **three containers**. MongoDB data persists in the `mongo-data` volume.

### 3. Create a login account

There is no default application account or public registration. On a new installation, run:

```bash
docker compose exec backend python -m saletool.cli web create-user --username admin
```

Enter and confirm a password when prompted. Open **http://localhost:8080** and sign in.

### 4. Configure integrations

Open **Settings**, save the configuration, and use **Test connection** for each integration:

| Setting | Configuration |
|---|---|
| Data source | Apollo API key for company and contact search |
| Web search | Select a provider such as Tavily and enter its API key; enable web search under Enrichment |
| Language model | Select OpenRouter, use `https://openrouter.ai/api/v1`, and enter your API key and model ID |
| Sender profile | Your name, company, and other details used to draft messages |

Set the model context window and output token budget to supported values. Leave room for input and the application's safety margin.

**Environment-file behavior:** Docker Compose reads `.env`, but the application does not load it directly. `APOLLO_API_KEY` is passed to the CLI. The web application reads integration credentials from database Settings. The `TAVILY_API_KEY`, `OPENROUTER_API_KEY`, and `OPENROUTER_MODEL` entries are local reference values and are not automatically imported into Settings.

API calls may incur provider charges. Disable **Look up email addresses** when you do not need Apollo email reveal.

## Operation

```bash
docker compose ps
docker compose logs -f backend
docker compose up -d --build --wait  # rebuild after source changes
docker compose stop                # stop services, keep containers and data
docker compose down                # remove containers, keep data volumes
```

Back up the database and retain `SALETOOL_SECRET_KEY`. **`docker compose down -v` deletes database volumes.** Switching between SQLite and MongoDB does not automatically migrate data.

For websites requiring JavaScript rendering, set `SALETOOL_INSTALL_BROWSER=true` in `.env` and rebuild the backend. This installs Playwright and Chromium; enable browser fallback in Settings as well.

For Internet access, place the frontend behind an HTTPS reverse proxy. Expose `443`, and `80` if required for redirects or certificates. Keep the backend and MongoDB private; bind the frontend host port to loopback when the proxy runs on the same host. HTTPS termination is not included in this Compose file.
