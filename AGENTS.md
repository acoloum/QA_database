# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

A full-stack Quality Control (QC) inspection management system for managing product inspections, defect tracking (NCMR), corrective actions (CAR/8D), and rework workflows. The UI is primarily in Traditional Chinese.

**Stack:** Flask 3.1 (Python) + React 19 (TypeScript) + PostgreSQL 16 + Nginx + Docker

---

## Development Commands

### Backend (Flask)

```bash
# From the repo root — activate venv first if using one
cd backend
python app.py                          # Dev server on :5001
waitress-serve --listen=*:5001 app:app # Production WSGI server
```

### Frontend (React + Vite)

```bash
cd src_frontend
npm install        # Install dependencies
npm run dev        # Dev server on :5173 (proxies /api to :5001)
npm run build      # TypeScript check + Vite production build
npm run lint       # ESLint
npm run preview    # Preview production build
```

### Docker (Full Stack)

```bash
docker-compose up -d         # Build and start all services
docker-compose down          # Stop services
docker-compose logs -f app   # Follow app logs
```

Production is served at `http://localhost:8080` via Nginx.

### Database Migrations

```bash
cd backend
flask db migrate -m "description"   # Generate migration
flask db upgrade                    # Apply migrations

# Or apply raw SQL scripts manually:
psql -U postgres -d qa_database -f migration/04_create_all_tables.sql
```

---

## Architecture

### Backend — Flask Blueprints + Service Layer

Each domain follows a three-layer pattern:

```
routes/<domain>.py        # HTTP request handling, input validation, auth checks
services/<domain>_service.py  # Business logic, DB queries via SQLAlchemy
models.py                 # SQLAlchemy ORM models (all 14 tables in one file)
```

Blueprint registration is in `backend/app.py`. Business logic must stay in services, not routes.

**Key backend files:**
- `backend/models.py` — All SQLAlchemy models. Tables use Chinese names as class docstrings. `ShippingData` has 10 dynamic measurement groups (外徑/OD, 內徑/ID, 厚度, 同心度, 長度, 硬度, 圓度, etc.), each up to 5 samples, plus an `is_ng` computed flag.
- `backend/utils.py` — JWT auth (`token_required` decorator), role authorization (`require_role`), HTML sanitization, and CSRF token generation.
- `backend/config.py` — Reads `.env` via python-dotenv; validates `SECRET_KEY`; configures SQLAlchemy pool (`pool_size=10`, `max_overflow=5`, `pool_recycle=3600`).
- `backend/errors.py` — Global error handlers for 400/401/403/404/500.
- `backend/services/spc_report.py` — SPC (Statistical Process Control) Excel report generation using pandas + openpyxl.

### Frontend — React Router + React Query + Context

```
src_frontend/src/
├── pages/         # Full-page views (one per domain)
├── components/    # Reusable UI components (charts, modals, tables)
├── services/api.ts  # Single Axios instance; baseURL='/api'; attaches JWT from localStorage
├── context/AuthContext.tsx  # Auth state (login/logout, current user)
├── types/index.ts   # All TypeScript interfaces
└── App.tsx          # Route definitions; ProtectedRoute wraps authenticated pages
```

Server state is managed with **TanStack React Query** (caching, refetching). Auth state uses React Context. All API calls go through `services/api.ts`.

### Authentication Flow

1. `POST /api/auth/login` returns a JWT.
2. JWT stored in `localStorage` and sent as `Authorization: Bearer <token>` on every request.
3. `token_required` decorator in `utils.py` validates the token on protected routes.
4. Role-based access via `require_role` decorator.

### Nginx Reverse Proxy

In production (Docker), Nginx:
- Serves the React build from `/app/frontend/dist` for all non-API routes.
- Proxies `/api/*` to Flask on `:5001`.

---

## Domain Modules

| Domain | Routes | Service | Description |
|--------|--------|---------|-------------|
| Shipping | `routes/shipping.py` | `services/shipping_service.py` | Outgoing product QC inspections |
| Patrol | `routes/patrol.py` | `services/patrol_service.py` | In-process production patrol |
| NCMR | `routes/ncmr.py` | `services/ncmr_service.py` | Non-Conforming Material Reports |
| Rework | `routes/rework.py` | `services/rework_service.py` | Multi-step rework workflow |
| Tolerance | `routes/tolerance.py` | `services/tolerance_service.py` | Vendor/spec tolerance standards |
| Dashboard | `routes/admin.py` | — | KPI stats, trend charts |

---

## Environment Variables

Required in `.env` (development) or environment (Docker):

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=qa_database
DB_USER=postgres
DB_PASSWORD=<password>
SECRET_KEY=<jwt-secret>
```

The `.env` file is committed with development credentials — do not commit production secrets.

---

## Key Conventions

- **Chinese field names:** Model columns and many variable names use Traditional Chinese (e.g., `廠商名稱`, `檢驗日期`). This is intentional — preserve them.
- **Measurement groups:** `ShippingData` stores measurements as `od1`–`od5`, `id1`–`id5`, etc. The `is_ng` boolean is computed at save time based on tolerance comparisons.
- **Excel import/export:** Several routes accept multipart form uploads (`.xlsx`) and return Excel files via `send_file`. openpyxl is used directly (not pandas) for formatting.
- **API docs:** Swagger UI available at `/apidocs` when running Flask.

後端是在venv環境中啟動
