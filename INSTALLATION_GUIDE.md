# Installation Guide

## 1. Prerequisites
- **Python 3.11+**
- **Node.js 18+** and **npm**
- **MySQL 8.0+** or **MariaDB 10.4+**

## 2. MySQL Setup
1. Start your MySQL/MariaDB server on `127.0.0.1:3306`.
2. Create the database:
   ```sql
   CREATE DATABASE IF NOT EXISTS form_insights CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
3. (Optional) Import existing data:
   ```bash
   mysql -u root form_insights < "form_insights (2).sql"
   ```

## 3. Backend Setup
```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Install dependencies:
pip install -r requirements.txt
# Install Chromium for Playwright:
playwright install chromium
```
Copy `.env.example` to `backend/.env` and configure `MYSQL_*` and `CORS_ORIGINS`.

Start the server:
```bash
# Windows:
python run_server_windows.py
# Linux/macOS:
python run_server.py
```

## 4. Frontend Setup
```bash
cd frontend
npm install
# Configure frontend/.env (VITE_API_URL=http://localhost:8000/api)
npm run dev
```
Open `http://localhost:5173` in your browser.
