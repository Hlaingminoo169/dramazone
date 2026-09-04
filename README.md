# DramaZone VIP Bot System

A production-ready Telegram VIP content purchasing system with two bots:

- **@DramaZone_VIP_Bot** — Customer Bot (Myanmar UI)
- **@drama_zone_vip_admin_bot** — Admin Bot

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| Web Framework | FastAPI |
| Telegram SDK | python-telegram-bot 21.x |
| Database | MongoDB Atlas (Free M0) |
| DB Driver | PyMongo |
| Hosting | Render.com (Free tier) |
| Deployment | GitHub + Render auto-deploy |

## Project Structure

```
dramazone/
├── app/
│   ├── bots/           # Bot factories (customer + admin)
│   ├── database/       # MongoDB connection, indexes, seed
│   ├── handlers/
│   │   ├── customer/   # All customer flow handlers
│   │   └── admin/      # All admin handlers
│   ├── services/       # Business logic layer
│   ├── utils/          # Shared utilities
│   ├── config.py       # Centralized configuration
│   └── types.py        # Enums and type definitions
├── tests/
├── main.py             # FastAPI entrypoint + webhooks
├── render.yaml         # Render.com deployment config
├── requirements.txt
└── .env.example
```

## Setup

### 1. Clone and install dependencies

```bash
git clone <your-repo-url>
cd dramazone
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### 2. Configure environment

```bash
copy .env.example .env
# Edit .env with your values
```

### 3. Run locally (development)

```bash
uvicorn main:app --reload --port 8000
```

### 4. Run tests

```bash
pytest tests/
```

## Environment Variables

See [`.env.example`](.env.example) for all required variables.

**Never commit `.env` to Git.**

## Webhook Endpoints

| Endpoint | Bot |
|---|---|
| `POST /webhook/customer` | Customer Bot |
| `POST /webhook/admin` | Admin Bot |
| `GET /health` | Health check |

## Security Notes

- All secrets via environment variables — never hard-coded
- Webhook secret token validation on every request
- Admin authorization checked on every admin handler
- Atomic MongoDB operations prevent race conditions on approval/rejection
- Order ownership validated before any customer action
- Session state stored in MongoDB (not in-memory)

## Authorized Admins

Configured via `ADMIN_TELEGRAM_IDS` environment variable.

## ⚠️ Important

If any bot tokens were previously exposed, revoke them immediately in [@BotFather](https://t.me/BotFather) and generate new ones. Never paste tokens into chat.
