# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A full-stack Quality Control (QC) inspection management system covering product inspections, defect tracking (NCMR), corrective actions (CAPA/8D), rework workflows, SPC studies, MSA (measurement system analysis), equipment calibration, pyrometry (CQI-9), and mechanical testing. The UI is primarily in Traditional Chinese.

**Stack:** Flask 3.1 (Python) + React 19 (TypeScript) + PostgreSQL 18 + Nginx + Docker

**Scale:** ~73 ORM models, ~80 service modules, ~180 API routes, ~180 React components.
Tests: 114 backend pytest files, 142 frontend vitest files — both suites are expected to stay green.

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

Schema changes are delivered as **hand-written, numbered SQL scripts** in `backend/migration/`
(`04_…` through `54_…`). They are **not** applied automatically — after adding one you must run it
against the target database yourself, or the app will fail at runtime against a stale schema.

```bash
psql -U postgres -d qa_database -f backend/migration/54_add_trgm_indexes_for_ncmr_complaint_equipment.sql
```

Tests build their schema from `models.py` via `create_all()`, so **a green test suite does not prove
the migration was applied.** Keep `models.py` and the SQL script in sync in the same change.

---

## Architecture

### Backend — Flask Blueprints + Service Layer

Each domain follows a three-layer pattern:

```
routes/<domain>.py        # HTTP request handling, input validation, auth checks
services/<domain>_service.py  # Business logic, DB queries via SQLAlchemy
models.py                 # SQLAlchemy ORM models (~74 models, all in one file)
```

Blueprint registration is in `backend/app.py`. Business logic must stay in services, not routes.

**Key backend files:**
- `backend/models.py` — All SQLAlchemy models. Tables use Chinese names as class docstrings. `ShippingData` measurements live in the `ShippingMeasurement` child table (the old flat `od1`–`od5` columns were dropped in migration 19), plus an `is_ng` computed flag.
- `backend/authentication.py` — JWT decode/validate; loads the current user and raises `AuthenticationError` carrying a stable `details.reason`.
- `backend/authorization.py` — Permission checks. `require_permissions(*perms, mode='all'|'any')` is the implementation; `require_permission(perm)` is the single-permission form. Permissions come from `Role.permissions`, not from a role name.
- `backend/utils.py` — `auth_required` (JWT decorator), HTML sanitization, CSRF tokens, `bounded_int` / `parse_optional_*` parameter helpers, audit logging.
- `backend/config.py` — Reads `.env` via python-dotenv; validates `SECRET_KEY`; configures SQLAlchemy pool (`pool_size=10`, `max_overflow=5`, `pool_recycle=3600`).
- `backend/errors.py` — Global error handlers for 400/401/403/404/500.
- `backend/services/spc_report.py` — SPC (Statistical Process Control) Excel report generation using pandas + openpyxl.
- `backend/services/msa_payload.py` — Shared MSA payload validation (text/int/decimal/JSON). Do not re-implement these per service.
- `backend/services/calibration_errors.py` — Calibration stable error contract plus the shared `require_object` payload guard.

### Frontend — React Router + React Query + Context

```
src_frontend/src/
├── pages/           # Full-page views (one per domain), lazy-loaded in App.tsx
├── components/      # Reusable UI components (charts, modals, tables)
├── hooks/           # React Query hooks, one file per domain
├── hooks/queryKeys.ts   # Central query key factory — see below
├── services/api.ts  # Single Axios instance; baseURL='/api'; attaches JWT from localStorage
├── utils/queryParams.ts # compactParams() — drops undefined/null/'' before axios `params`
├── utils/chartSetup.ts  # The ONLY Chart.js registration point; import it, never re-register
├── context/AuthContext.tsx  # Auth state (login/logout, current user)
├── types/index.ts   # All TypeScript interfaces
└── App.tsx          # Route definitions; ProtectedRoute / PermissionRoute wrap authenticated pages
```

Server state is managed with **TanStack React Query** (caching, refetching). Auth state uses React Context. All API calls go through `services/api.ts`.

**Frontend conventions worth following:**
- **Query keys** come from `hooks/queryKeys.ts` (or `msaKeys` / `msaStudyKeys` for MSA). Never inline a key literal — invalidation depends on both ends matching.
- **Query strings**: pass an object to axios's `params`, wrapping optional fields in `compactParams()`. Do not hand-build `URLSearchParams` for API calls (it is still correct for building router URLs).
- **Chart.js**: `import '../../utils/chartSetup';`. All components/elements/controllers are registered there.
- Every page route is `lazy()`-loaded; keep new pages that way so the initial bundle stays small.
- **Dense list tables** (roughly 8+ columns) take `className="dense-list-table"` and must sit inside a
  responsive wrapper (`<Table responsive>` or a `.table-responsive` div). The global `.table tbody td`
  padding and `.btn` padding otherwise squeeze every column into a multi-line mess. Free-text columns
  still need their own `text-truncate` + `maxWidth` + `title`. Do not use it on data-entry grids
  (calibration/pyrometry input tables) or on columns holding a wrapping badge list.

### Authentication & Authorization Flow

1. `POST /api/auth/login` returns a JWT (carrying `user_id` + `token_version`).
2. JWT stored in `localStorage` and sent as `Authorization: Bearer <token>` on every request.
3. `@auth_required` (`utils.py`) validates the token, re-loads the user from the DB (JWT claims are never trusted for authorization), and injects `current_user` as the view's first parameter.
4. `@require_permission('domain.action')` / `@require_permissions(..., mode='any')` (`authorization.py`) enforce fine-grained permissions. Always import these from `..authorization`.
5. Every 401 carries a stable `details.reason` (`missing_token`, `invalid_token`, `token_revoked`, `user_not_found`, `user_inactive`). The MSA and calibration adapters map those *reasons* — never the message text — onto their own error codes. If you add a new rejection path, give it a `reason` and register it in both adapters' `*_AUTH_CODE_BY_REASON` maps.

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
| CAPA / 8D | `routes/capa.py` | `services/capa_service.py` | Corrective actions, 8D reports (Excel/PDF export) |
| Complaint | `routes/complaint.py` | `services/complaint_service.py` | Customer complaints and statistics |
| Tolerance | `routes/tolerance.py` | `services/tolerance_service.py` | Vendor/spec tolerance standards |
| Extrusion Tolerance | `routes/extrusion_tolerance.py` | `services/extrusion_tolerance_service.py` | Extrusion-specific tolerance standards |
| SPC | `routes/spc_studies.py` | `services/spc_study_service.py` + `spc_*.py` | Studies, control limits, events, OCAP |
| MSA | `routes/msa.py` | `services/msa_*.py` | Gage R&R, bias/linearity, stability, attribute agreement |
| Measurement Equipment | `routes/measurement_equipment.py` | `services/measurement_equipment_service.py` | Gage master data and import |
| Calibration | `routes/calibrations.py`, `routes/calibration_templates.py` | `services/calibration_*.py` | Calibration templates, records, approval workflow |
| Pyrometry | `routes/pyrometry.py` | `services/pyrometry_*.py` | CQI-9 TUS / SAT, recorder & thermocouple calibration |
| Mechanical | `routes/mechanical.py` | `services/mechanical_*.py` | Tensile / hardness testing |
| Attachment | `routes/attachment.py` | `services/attachment_service.py` | File uploads via a pluggable storage backend |
| Task | `routes/task.py` | `services/task_service.py` | Cross-module task assignment and close gates |
| Vendor Performance | `routes/vendor_performance.py` | `services/vendor_performance_service.py` | Periodic vendor scoring |
| Quality Analytics | `routes/quality_analytics.py` | `services/quality_analytics_service.py` | Pareto, defect trends, repeat issues |
| Dashboard | `routes/admin.py` | `services/dashboard_service.py` | KPI stats, trend charts, todos |

Routes named `*_adapters.py` (`msa_adapters.py`, `calibration_adapters.py`) only translate shared
auth/permission failures into that module's stable error envelope — they hold no business logic.

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

The `.env` file is git-ignored (see `.gitignore`) and must be created locally — do not commit it. `SECRET_KEY` is required; the app refuses to start without it (see `config.py`).

---

## Key Conventions

- **Chinese field names:** Model columns and many variable names use Traditional Chinese (e.g., `廠商名稱`, `檢驗日期`). This is intentional — preserve them.
- **Measurement groups:** `ShippingData` measurements live in the `ShippingMeasurement` child table, keyed by measurement group (外徑/OD, 內徑/ID, 厚度, 同心度, 長度, 硬度, 圓度, …) and sample index. The `is_ng` boolean is computed at save time from tolerance comparisons.
- **Fuzzy search:** List filters use `ilike('%x%')`. Those columns are backed by **pg_trgm GIN** indexes (migration 53) — a plain btree index cannot serve a leading-wildcard `LIKE`. If you add a new fuzzy filter, add the matching trgm index.
- **List endpoints must be bounded.** Either paginate (`{data, total, total_pages}`, as in `ShippingService.get_list`) or take a required scoping id. Do not add an endpoint that returns a whole table.
- **Eager-load relations used by serializers** (`joinedload` / `selectinload` / `contains_eager`) rather than touching them inside a loop.
- **Don't wrap a function body in `try: ... except Exception as e: raise e`** — it changes nothing. Only catch where you actually `db.session.rollback()` or translate the error, and re-raise with a bare `raise`.
- **Excel import/export:** Several routes accept multipart form uploads (`.xlsx`) and return Excel files via `send_file`. openpyxl is used directly (not pandas) for formatting.
- **API docs:** Swagger UI available at `/apidocs` when running Flask.

後端是在venv環境中啟動
