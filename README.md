# Contact Form Filler — Automation Platform

A full-stack web application for discovering contact pages on authorized target websites, extracting and classifying HTML form fields, managing outreach campaigns, and automating form filling and submission with Playwright, FastAPI, MySQL, and a modern React + TypeScript dashboard.

---

## Main Features
- **Modern SaaS Web Application**: 11-page React + TypeScript + Tailwind CSS + Recharts interface.
- **Website Management & Inspection**: Single/bulk/CSV URL import with SSRF validation, CSV export, scan status filtering, and per-website field inspection with manual concept overrides.
- **Form Discovery & Semantic Mapping**: Playwright-powered contact page navigation, iframe-aware field extraction, CAPTCHA detection, and concept mapping (`full_name`, `email`, `phone`, `company`, `subject`, `message`, etc.).
- **Multi-Step Campaign Wizard**: 4-step workflow (Campaign Info -> Website Selection -> Field Strategies -> Review & Explicit Approval).
- **Live Campaign Monitoring**: Start, Pause, Resume, Restart, and Cancel controls with per-website status tracking and duplicate-run prevention.
- **Submissions Audit & Analytics**: Filterable submission history with HTTP request/response inspection, CSV export, and Recharts analytics.
- **Email Notifications & Runtime Settings**: Configurable SMTP notifications, recipient management, and Playwright timeout/concurrency settings.

---

## Architecture
- **Frontend (`frontend/`)**: React 18, TypeScript, Vite, Tailwind CSS, React Router, TanStack React Query, Recharts, Lucide React, Sonner.
- **Backend (`backend/app/`)**: FastAPI modular architecture (`api/routes`, `core`, `services`, `automation`, `database`, `schemas`), backed by `form_filler.py`, `auto_concept_mapper.py`, `cluster_raw_fields.py`, and `email_notifier.py`.
- **Database**: MySQL / MariaDB (`form_insights`) using pooled connections (`mysql-connector-python`).

---

## Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- MySQL 8.0+ or MariaDB 10.4+ (e.g., XAMPP or standalone MySQL Server)

---

## Quick Start

### 1. Database Setup
Start MySQL on `127.0.0.1:3306`, create the `form_insights` database, and import `form_insights (2).sql` if migrating existing data:
```sql
CREATE DATABASE IF NOT EXISTS form_insights CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. Environment Configuration
Copy `.env.example` to `backend/.env` (and `frontend/.env.example` to `frontend/.env`):
```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=form_insights
```

### 3. Backend Setup
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

Start the FastAPI backend:
```bash
# Windows:
python run_server_windows.py
# macOS/Linux:
# python run_server.py
```
API runs at `http://localhost:8000` (Docs: `http://localhost:8000/docs`, Health: `http://localhost:8000/health`).

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`.

---

## Running Tests
```bash
# Backend tests
backend\.venv\Scripts\pytest.exe backend\tests -v

# Frontend typecheck & production build
cd frontend && npm run build
```

---

## Project Structure
```text
├── backend/
│   ├── app/
│   │   ├── api/routes/      # health, websites, campaigns, submissions, analytics, fields, notifications, settings
│   │   ├── automation/      # playwright_manager.py
│   │   ├── core/            # config.py, logging.py, security.py
│   │   ├── database/        # connection.py (pooling), migrations.py
│   │   ├── schemas/         # Pydantic request/response models
│   │   ├── services/        # campaign_service.py
│   │   └── main.py          # FastAPI app assembly
│   ├── tests/               # pytest suite
│   ├── form_filler.py       # Playwright discovery & filling engine
│   ├── auto_concept_mapper.py
│   ├── cluster_raw_fields.py
│   ├── email_notifier.py
│   ├── fastapi_backend.py   # Backward-compatible ASGI export
│   ├── run_server_windows.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # Layout, StatusBadge, EmptyState, ErrorBoundary, ui/*
│   │   ├── lib/             # api.ts, utils.ts
│   │   ├── pages/           # 11 application pages
│   │   └── App.tsx
│   └── package.json
├── archive/                 # Archived legacy HTML/JS files
├── PROJECT_ANALYSIS.md
├── PROJECT_ISSUES.md
├── API_DOCUMENTATION.md
├── DATABASE_DOCUMENTATION.md
├── INSTALLATION_GUIDE.md
└── CHANGELOG.md
```
