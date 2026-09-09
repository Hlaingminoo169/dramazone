# DramaZone VIP Telegram Bot

Backend for the DramaZone VIP Telegram Bot — handles order management, payment verification, and VIP content delivery.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Web Framework | FastAPI + Uvicorn |
| Database | MongoDB (Atlas or self-hosted) |
| DB Driver | Motor (async) |
| Config | pydantic-settings |
| Timezone | pytz |

---

## Project Structure

```
dramazone/
├── app/
│   ├── main.py              # FastAPI app, lifespan, routers
│   ├── config.py            # Centralised settings (env-driven)
│   ├── database/
│   │   ├── connection.py    # Motor async client
│   │   ├── indexes.py       # All MongoDB index definitions
│   │   └── collections.py  # Collection name constants
│   ├── models/
│   │   ├── user.py          # Customer profile
│   │   ├── movie.py         # VIP movie catalog
│   │   ├── order.py         # Purchase order + state machine
│   │   ├── session.py       # Conversation session (TTL)
│   │   ├── audit_log.py     # Admin action audit trail
│   │   └── rate_limit.py    # Rate limit TTL tracker
│   ├── routers/
│   │   └── health.py        # GET /health, GET /health/db
│   └── utils/
│       └── logger.py        # Structured JSON logging
├── .env.example             # Environment variable template
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Clone and enter the project

```bash
git clone <repo-url>
cd dramazone
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in at minimum:

```env
MONGODB_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/
MONGODB_DB_NAME=dramazone
```

### 5. Run the development server

```bash
uvicorn app.main:app --reload
```

### 6. Verify

```bash
# Liveness
curl http://localhost:8000/health

# Database connectivity
curl http://localhost:8000/health/db

# Swagger UI (development only)
open http://localhost:8000/docs
```

---

## Environment Variables

See [`.env.example`](.env.example) for the full list with descriptions.

### Required for Step 1

| Variable | Description |
|---|---|
| `MONGODB_URI` | MongoDB connection string |
| `MONGODB_DB_NAME` | Database name (default: `dramazone`) |

### Required for Telegram (future steps)

| Variable | Description |
|---|---|
| `CUSTOMER_BOT_TOKEN` | Customer-facing bot token |
| `ADMIN_BOT_TOKEN` | Admin-facing bot token |
| `WEBHOOK_SECRET` | Telegram webhook secret (min 32 chars) |
| `WEBHOOK_BASE_URL` | Public HTTPS URL of this service |

### Admin Access

```env
# Comma-separated Telegram numeric user IDs — NOT usernames
ADMIN_TELEGRAM_IDS=1673861706,1655754454
```

> ⚠️ Always use numeric Telegram user IDs for admin access. Usernames can change.

### Rate Limiting

```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_MAX_REQUESTS=30
ORDER_RATE_LIMIT=5
SCREENSHOT_RATE_LIMIT=3
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check — always 200 if process is running |
| `GET` | `/health/db` | MongoDB connectivity — 200 ok / 503 unreachable |
| `GET` | `/docs` | Swagger UI (development only) |

---

## MongoDB Collections

| Collection | Purpose |
|---|---|
| `users` | Customer Telegram profiles |
| `movies` | VIP movie catalog |
| `orders` | Purchase orders (central collection) |
| `sessions` | Active conversation state (TTL auto-expiry) |
| `rate_limits` | Rate limit windows (TTL auto-expiry) |
| `audit_logs` | Admin action audit trail (append-only) |
| `settings` | Runtime-configurable bot settings |

---

## Order Status Flow

```
PENDING_PAYMENT   → customer created order, no screenshot yet
        ↓
WAITING_APPROVAL  → screenshot submitted, pending admin review
        ↓
  APPROVED         → admin confirmed; VIP links sent to customer
  REJECTED         → admin rejected; customer notified with reason

(any state) → CANCELLED  → customer or system cancelled
```

---

## VPS Deployment

```bash
# Install production dependencies
pip install -r requirements.txt

# Set environment variables (or use a .env file)
export MONGODB_URI="..."
export APP_ENV=production

# Run with Uvicorn (single worker for Telegram webhooks)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1

# Or with Gunicorn + Uvicorn workers
gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 1
```

> **Note:** Use a single worker process (`--workers 1`) for Telegram webhook bots.
> Multiple workers would each need their own webhook registration.

---

## Development Notes

- **Docs UI** is only available in `APP_ENV=development`
- **Indexes** are created/verified automatically on every startup (idempotent)
- **Sessions and rate limits** auto-expire via MongoDB TTL indexes — no cleanup cron needed
- **Timestamps** are always stored in UTC; reports convert to `REPORT_TIMEZONE` (default: `Asia/Yangon`)

---

## Implementation Steps

- [x] **Step 1** — MongoDB foundation + FastAPI health check *(current)*
- [ ] **Step 2** — Customer bot: movie catalog + order creation
- [ ] **Step 3** — Customer bot: payment + screenshot submission
- [ ] **Step 4** — Admin bot: order review + approve/reject
- [ ] **Step 5** — Admin bot: dashboard + sales reporting
- [ ] **Step 6** — Rate limiting + security hardening
- [ ] **Step 7** — Session recovery + edge case handling
