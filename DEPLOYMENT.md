# SmartChat production deployment

## Repository layout verified

- Vite frontend: `frontEnd/` (`frontEnd/package.json`, `frontEnd/vite.config.ts`)
- FastAPI service: `backend/main.py` (`main:app` from the `backend/` working directory)
- SQLAlchemy models: `backend/models.py`; `backend/main.py` calls `Base.metadata.create_all()` during application startup.
- There is no Alembic migration tree in the backend. `create_all()` creates absent tables but does not migrate existing table definitions. Apply schema changes with reviewed SQL/Alembic migrations before rollout; back up MySQL first.
- Main SQLAlchemy URL must use `mysql+pymysql://...`; PyMySQL is already present in `requirements.txt`.

## 1. Deploy the database

Create a managed MySQL 8 database (Railway MySQL, Aiven, or another managed MySQL provider), enable automated backups and TLS, and create a dedicated application database/user with least-privilege access. Copy its private connection details. Set `DATABASE_URL` on Railway as `mysql+pymysql://USER:PASSWORD@HOST:PORT/DATABASE?charset=utf8mb4` (URL-encode special characters in credentials). Keep the DB private to the backend network where possible. The current app creates missing tables on API startup; inspect the production schema and seed/transfer existing data separately. Do not deploy `backend/smartchat.db` or assume local SQLite data migrates itself.

## 2. Deploy FastAPI on Railway (recommended)

Railway suits this repository because it runs a persistent Python web process, accepts long-running request timeouts used by document/OCR and scraping workflows, and can host the Node WhatsApp service as a separate service. Connect the repository as a Railway project service and set **Root Directory** to `/backend`. The `backend/.python-version` file pins Python to 3.11.5. Install command: `pip install -r requirements.txt`. Start command (also in `backend/Procfile`):

```sh
gunicorn main:app --worker-class uvicorn.workers.UvicornWorker --workers 1 --bind 0.0.0.0:$PORT --timeout 300
```

Use one worker initially because Pinecone-ingest job progress and WhatsApp order/timer state are currently in process memory. Horizontal scaling requires external job/state storage. Set Railway health check path to `/health`.

Set these Railway variables (values are supplied by your providers):

| Variable | Required | Notes |
|---|---:|---|
| `DATABASE_URL` | Yes | Managed MySQL URL above |
| `SECRET_KEY` | Yes | Long random JWT signing secret; changing it invalidates current tokens |
| `ADMIN_SECRET` | Yes | Separate random admin secret |
| `ADMIN_EMAIL` | Yes | Production admin email |
| `ADMIN_PASSWORD` | Yes | Strong initial admin password; the frontend admin login sends credentials to `/admin/login` |
| `OPENAI_API_KEY` | For AI | Existing OpenAI chat, vision, and embeddings pipelines read this environment variable |
| `PINECONE_API_KEY` | For RAG | Existing Pinecone ingestion/query code reads this environment variable |
| `PINECONE_ENVIRONMENT` | If code requires it | Keep consistent with existing Pinecone setup |
| `CORS_ORIGINS` | Yes | Comma-separated exact origins, no trailing slash: `https://your-project.vercel.app,https://app.example.com` |
| `GMAIL_USER` | For email | SMTP sender account |
| `GMAIL_APP_PASSWORD` | For email | SMTP app password, stored as a secret |
| `UPLOAD_DIR` | Recommended | Writable mount path, e.g. `/data/uploads`; attach a persistent volume there for local-file compatibility |
| `WHATSAPP_SERVICE_URL` | For WhatsApp | Public/internal URL of separately deployed `whatsapp-service` |
| `BOT_SERVICE_URLS` | If WhatsApp bot calls enabled | JSON object mapping category service ports (`8001`–`8005`) to public/internal HTTPS base URLs, e.g. `{"8001":"https://uni.example.com","8002":"https://restaurant.example.com"}` |

The FastAPI service currently mounts `UPLOAD_DIR` at `/uploads`. A persistent volume prevents loss on restart but is local to one instance and is not shared across scaled instances. For robust production uploads, replace filesystem writes/static serving with S3-compatible object storage and store object URLs; Vercel itself cannot host these uploads. OCR fallback also needs native Tesseract/Poppler installed on the backend image in addition to Python packages; the current base requirements describe OCR as optional and do not provision those system binaries.

## 3. Deploy the frontend to Vercel

Import the same Git repository in Vercel. Set:

- **Root Directory:** `frontEnd`
- **Framework preset:** Vite
- **Build command:** `npm run build`
- **Output directory:** `dist`
- **Install command:** `npm install` (or use the committed lockfile with `npm ci` if available)

Set Vercel environment variables for Production and Preview as appropriate:

- `VITE_API_URL=https://<your-Railway-api-domain>` (public API origin, no trailing slash)
- `VITE_WIDGET_URL_TEMPLATE=https://<your-public-bot-service-domain>/{port}/{botId}` (replace with your reverse-proxy routing; `{port}` maps categories to 8001–8005 and `{botId}` is replaced with the selected chatbot ID)

`frontEnd/vercel.json` rewrites browser routes to `index.html`, so React Router routes survive refreshes. Vite env values are public build-time values; never put API keys, database URLs, or JWT secrets in `VITE_*` variables.

## 4. Domains, CORS, and integrations

Assign the API a stable Railway custom domain and HTTPS. Set that exact origin as `VITE_API_URL`, then redeploy the Vercel frontend. Set `CORS_ORIGINS` to every exact frontend origin in use (Vercel production domain, custom production domain, and optionally preview domains). Avoid `*` with credentials. Set the Vercel custom domain and add its origin to `CORS_ORIGINS` before testing browser API calls.

The Dashboard can build iframe links via `VITE_WIDGET_URL_TEMPLATE`; category model services currently use ports 8001–8005, so those services need publicly reachable HTTPS endpoints or a reverse proxy that routes them. Merely deploying `backend/main.py` does not deploy those separate model services. WhatsApp uses a separate Node service under `whatsapp-service/`; deploy it as a persistent Railway service, configure its callback/API URLs and persistent session storage, then set `WHATSAPP_SERVICE_URL` and `BOT_SERVICE_URLS` on FastAPI. The workspace contains WhatsApp session credentials; exclude them from source control and rotate/re-pair sessions if they were ever committed or shared.

## 5. Deployment order

1. Provision MySQL, take a backup/export of any data that must be retained, and configure the private DB URL.
2. Deploy FastAPI with secrets, API keys, upload storage, and CORS configured. Confirm `/health`, then inspect DB tables and API logs.
3. Deploy the public bot/model and WhatsApp services required by enabled integrations; set their service URLs.
4. Deploy Vercel with `VITE_API_URL` and `VITE_WIDGET_URL_TEMPLATE` set.
5. Add custom domains, update exact CORS origins, redeploy affected services, and smoke-test login, chatbot queries, PDF ingestion/progress, widget embeds, and integrations.

## 6. Local/production smoke commands

From repository root, build the frontend:

```sh
cd frontEnd
npm ci
npm run build
```

Run the backend from `backend/` after setting required values in an untracked `.env` copied from `.env.example`:

```sh
cd ../backend
python -m pip install -r requirements.txt
python -c "from main import app; print(app.title)"
gunicorn main:app --worker-class uvicorn.workers.UvicornWorker --workers 1 --bind 127.0.0.1:8000 --timeout 300
```

In another terminal, verify `curl http://127.0.0.1:8000/health` and `curl -I http://127.0.0.1:8000/docs`. For deployed services use `curl https://<api-domain>/health`; browser-test frontend auth, an AI chat response, an indexed-document retrieval, upload download URL, and iframe widget. Confirm no API secrets appear in Vite build output or backend logs.

## Common deployment failures

- **Vercel cannot find package/build output:** set Root Directory to `frontEnd`, build `npm run build`, output `dist`.
- **Refresh gives 404:** retain `frontEnd/vercel.json` rewrite and confirm the request is for a frontend route.
- **Browser CORS error:** add the exact scheme/host/port of the frontend to `CORS_ORIGINS` and redeploy the API.
- **DB connection or access denied:** confirm `mysql+pymysql`, URL-encoded credentials, MySQL network allowlist/TLS, and database grants.
- **Missing table:** inspect startup logs and DB permissions; `create_all()` only creates missing tables, it does not perform schema upgrades or data migrations.
- **AI/RAG unavailable:** check `OPENAI_API_KEY`, `PINECONE_API_KEY`, Pinecone index names/dimensions/namespaces, and provider connectivity in Railway logs.
- **Uploads vanish or return 404 after restart:** configure a Railway persistent volume at `UPLOAD_DIR` or implement object storage and migrate existing files.
- **Widget/WhatsApp works locally only:** the category model ports and WhatsApp Node service must each be deployed/reachable and their public HTTPS URLs configured; localhost is the API container itself.
- **OCR differs in production:** install Tesseract/Poppler system packages and enable the optional Python OCR dependencies in the backend image.
