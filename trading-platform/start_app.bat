@echo off
echo ========================================
echo Starting Trading Platform
echo ========================================
echo.

echo [1/6] Checking Docker Desktop...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker Desktop is not running. Please start Docker Desktop and try again.
    echo You can start it from: "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    pause
    exit /b 1
)
echo Docker is running!
echo.

echo [2/6] Installing frontend dependencies...
cd frontend
if not exist node_modules (
    echo Installing npm packages...
    call npm install
    if %errorlevel% neq 0 (
        echo Failed to install npm packages
        cd ..
        pause
        exit /b 1
    )
) else (
    echo Node modules already installed
)
cd ..
echo.

echo [3/6] Starting Docker services...
docker-compose up -d
if %errorlevel% neq 0 (
    echo Failed to start Docker services
    pause
    exit /b 1
)
echo Docker services started!
echo.

echo [4/6] Waiting for services to be ready (30 seconds)...
timeout /t 30 /nobreak >nul
echo.

echo [5/6] Starting Backend (FastAPI)...
start "Trading Platform - Backend" cmd /k "cd /d %~dp0backend && ..\\.venv312\\Scripts\\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo Backend starting in new window...
echo.

echo [6/6] Starting Frontend (Next.js)...
timeout /t 5 /nobreak >nul
start "Trading Platform - Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
echo Frontend starting in new window...
echo.

echo ========================================
echo Trading Platform Started!
echo ========================================
echo.
echo Services:
echo   - Dashboard:  http://localhost:3000
echo   - API Docs:   http://localhost:8000/docs
echo   - Grafana:    http://localhost:3001 (admin/admin)
echo   - MLflow:     http://localhost:5000
echo.
echo Press any key to view Docker logs...
pause >nul
docker-compose logs -f
