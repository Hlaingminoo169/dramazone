# DramaZone VIP Bot

A production-ready Telegram VIP content purchasing system built with **Python 3.12**, **FastAPI**, **python-telegram-bot**, and **MongoDB Atlas**.

---

## Project Overview

DramaZone VIP lets customers purchase access to exclusive Telegram drama channels via two bots:

| Bot | Username | Purpose |
|-----|----------|---------|
| Customer Bot | `@DramaZone_VIP_Bot` | Browse content, select packages, pay, receive access links |
| Admin Bot | `@drama_zone_vip_admin_bot` | Review orders, approve/reject payments, manage content |

Payments are manually verified by admins (KPay / Wave screenshot review).

---

## Architecture

```
Telegram
   │
   ├── Customer Bot (/webhook/customer)
   └── Admin Bot   (/webhook/admin)
           │
        FastAPI
           │
      MongoDB Atlas
```

---

## Local Setup

### 1. Prerequisites

- Python 3.12+
- Git

### 2. Clone the repository

```bash
git clone <your-repo-url>
cd dramazone-vip-bot
```

### 3. Create virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in the required values (see [Environment Variables](#environment-variables) below).

### 6. Run locally

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Verify:

```
GET http://localhost:8000/
GET http://localhost:8000/health
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in each value.

| Variable | Required | Description |
|----------|----------|-------------|
| `CUSTOMER_BOT_TOKEN` | ✅ | Telegram Bot token for the customer bot |
| `ADMIN_BOT_TOKEN` | ✅ | Telegram Bot token for the admin bot |
| `MONGODB_URI` | ✅ | MongoDB Atlas connection string |
| `MONGODB_DB_NAME` | ✅ | Database name (default: `dramazone_vip`) |
| `ADMIN_TELEGRAM_IDS` | ✅ | Comma-separated admin Telegram user IDs |
| `ADMIN_USERNAME` | ✅ | Admin's Telegram username (for contact link) |
| `KPAY_PHONE` | ✅ | KPay phone number |
| `KPAY_ACCOUNT_NAME` | ✅ | KPay account holder name |
| `WAVE_PHONE` | ✅ | Wave phone number |
| `WAVE_ACCOUNT_NAME` | ✅ | Wave account holder name |
| `CUSTOMER_WEBHOOK_SECRET` | ✅ (production) | Random secret to validate customer webhook |
| `ADMIN_WEBHOOK_SECRET` | ✅ (production) | Random secret to validate admin webhook |
| `WEBHOOK_BASE_URL` | ✅ (production) | Your HTTPS domain, e.g. `https://api.example.com` |
| `BOT_MODE` | ✅ | `polling` (local) or `webhook` (production) |
| `QR_KPAY_FILE_ID` | ❌ | Pre-uploaded KPay QR code Telegram file ID |
| `QR_WAVE_FILE_ID` | ❌ | Pre-uploaded Wave QR code Telegram file ID |

**⚠️ Never commit `.env` to Git.**

---

## MongoDB Setup

1. Create a free cluster at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2. Create a database user with read/write permissions.
3. Whitelist your IP (or `0.0.0.0/0` for cloud deployments).
4. Copy the connection string to `MONGODB_URI` in your `.env`.

Collections are created automatically on first startup. Indexes are also created automatically.

---

## Webhook Setup

After deploying to production, configure Telegram webhooks:

```bash
# Customer bot
curl -X POST "https://api.telegram.org/bot<CUSTOMER_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://YOUR-DOMAIN/webhook/customer",
    "secret_token": "<CUSTOMER_WEBHOOK_SECRET>"
  }'

# Admin bot
curl -X POST "https://api.telegram.org/bot<ADMIN_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://YOUR-DOMAIN/webhook/admin",
    "secret_token": "<ADMIN_WEBHOOK_SECRET>"
  }'
```

---

## FastAPI Cloud Deployment (Phase 1)

1. Push your code to GitHub (**without** `.env`).
2. Connect your GitHub repository to [FastAPI Cloud](https://fastapi.cloud).
3. Set all environment variables in the FastAPI Cloud dashboard.
4. Deploy.
5. Verify `GET /health` returns `{"status": "ok"}`.
6. Configure Telegram webhooks (see above).

**Important:** FastAPI Cloud injects the port via the `PORT` environment variable. The application reads this automatically — no code changes required.

---

## VPS Deployment (Phase 2)

### Prerequisites

- Ubuntu 22.04+ VPS
- Docker + Docker Compose
- Nginx
- Certbot (SSL)

### Steps

```bash
# 1. Pull from GitHub
git clone <your-repo-url>
cd dramazone-vip-bot

# 2. Create .env with production values
cp .env.example .env
nano .env  # fill in all values

# 3. Build Docker image
docker build -t dramazone-vip .

# 4. Run container
docker run -d \
  --name dramazone-vip \
  --env-file .env \
  -p 8000:8000 \
  --restart unless-stopped \
  dramazone-vip

# 5. Configure Nginx reverse proxy
# /etc/nginx/sites-available/dramazone
server {
    server_name api.yourdomain.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# 6. Enable SSL with Certbot
certbot --nginx -d api.yourdomain.com

# 7. Update Telegram webhooks to new domain
# (see Webhook Setup above)

# 8. Update container after code changes
git pull
docker build -t dramazone-vip .
docker stop dramazone-vip && docker rm dramazone-vip
docker run -d --name dramazone-vip --env-file .env -p 8000:8000 --restart unless-stopped dramazone-vip
```

### Architecture note

Business logic is **not** tied to any hosting platform. The same Docker image runs identically on FastAPI Cloud and a VPS — only environment variables change.

---

## Project Structure

```
dramazone-vip-bot/
├── app/
│   ├── bots/              # Bot initialisation (customer & admin)
│   ├── database/          # MongoDB connection & indexes
│   ├── handlers/          # Telegram update handlers
│   │   ├── customer/      # Customer bot handlers
│   │   └── admin/         # Admin bot handlers
│   ├── services/          # Business logic (orders, payments, etc.)
│   ├── utils/             # Shared utilities (numbers, pricing, etc.)
│   ├── config.py          # Centralised settings (pydantic-settings)
│   └── types.py           # Shared type definitions
├── main.py                # FastAPI entry point
├── requirements.txt
├── pyproject.toml
├── Dockerfile
├── .env.example
└── README.md
```

---

## Implementation Steps

| Step | Description | Status |
|------|-------------|--------|
| 1 | MongoDB Atlas Setup + Database Connection | ✅ Done |
| 2 | GitHub Project Structure | ✅ Done |
| 3 | FastAPI Application + Health Endpoint | ✅ Done |
| 4 | Telegram Webhook Architecture | 🔲 Pending |
| 5 | Database Schema | 🔲 Pending |
| 6 | Customer Bot Start | 🔲 Pending |
| 7 | Package Selection | 🔲 Pending |
| 8 | Myanmar/English Number Input | 🔲 Pending |
| 9 | Movie Selection | 🔲 Pending |
| 10 | Payment Method | 🔲 Pending |
| 11 | Order Creation + Screenshot | 🔲 Pending |
| 12 | Admin Bot | 🔲 Pending |
| 13 | Admin Payment Notification | 🔲 Pending |
| 14 | Approve Order | 🔲 Pending |
| 15 | Reject Order + Reason | 🔲 Pending |
| 16 | Order History | 🔲 Pending |
| 17 | Contact Admin | 🔲 Pending |
| 18 | Security | 🔲 Pending |
| 19 | Deployment | 🔲 Pending |

---

## License

Private — all rights reserved.
