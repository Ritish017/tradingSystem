#!/usr/bin/env python
"""Quick start script to initialize and verify the trading platform."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

def print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def run_command(cmd: str, cwd: str | None = None) -> bool:
    """Run shell command and return success status."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"❌ Command failed: {cmd}")
            print(f"Error: {result.stderr}")
            return False
        return True
    except Exception as exc:
        print(f"❌ Exception running command: {exc}")
        return False

def check_prerequisites() -> bool:
    """Check if required tools are installed."""
    print_header("Checking Prerequisites")
    
    checks = {
        "Docker": "docker --version",
        "Docker Compose": "docker-compose --version",
        "Python 3.11+": "python --version",
        "Node.js": "node --version",
        "npm": "npm --version",
    }
    
    all_ok = True
    for name, cmd in checks.items():
        if run_command(cmd):
            print(f"✅ {name} installed")
        else:
            print(f"❌ {name} not found")
            all_ok = False
    
    return all_ok

def setup_environment() -> bool:
    """Setup .env file if not exists."""
    print_header("Setting Up Environment")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print("✅ .env file already exists")
        return True
    
    if not env_example.exists():
        print("❌ .env.example not found")
        return False
    
    # Copy example to .env
    env_file.write_text(env_example.read_text())
    print("✅ Created .env from .env.example")
    print("⚠️  IMPORTANT: Edit .env with your actual credentials before going live")
    return True

def start_infrastructure() -> bool:
    """Start Docker Compose services."""
    print_header("Starting Infrastructure")
    
    print("Starting Docker Compose services...")
    if not run_command("docker-compose up -d"):
        return False
    
    print("✅ Docker services started")
    print("Waiting 10 seconds for services to initialize...")
    time.sleep(10)
    
    # Check service status
    print("\nService Status:")
    run_command("docker-compose ps")
    
    return True

def install_backend_deps() -> bool:
    """Install backend Python dependencies."""
    print_header("Installing Backend Dependencies")
    
    backend_dir = Path("backend")
    if not backend_dir.exists():
        print("❌ backend/ directory not found")
        return False
    
    print("Installing Python packages...")
    if not run_command("pip install -e .", cwd=str(backend_dir)):
        return False
    
    print("✅ Backend dependencies installed")
    return True

def install_frontend_deps() -> bool:
    """Install frontend Node dependencies."""
    print_header("Installing Frontend Dependencies")
    
    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        print("❌ frontend/ directory not found")
        return False
    
    print("Installing npm packages...")
    if not run_command("npm install", cwd=str(frontend_dir)):
        return False
    
    print("✅ Frontend dependencies installed")
    return True

def run_migrations() -> bool:
    """Run database migrations."""
    print_header("Running Database Migrations")
    
    backend_dir = Path("backend")
    print("Running Alembic migrations...")
    if not run_command("alembic upgrade head", cwd=str(backend_dir)):
        print("⚠️  Migrations failed (may be expected if already run)")
    else:
        print("✅ Database migrations complete")
    
    return True

def verify_health() -> bool:
    """Verify backend health endpoint."""
    print_header("Verifying System Health")
    
    print("Checking backend health...")
    try:
        import requests
        response = requests.get("http://localhost:8000/healthz", timeout=5)
        if response.status_code == 200:
            print("✅ Backend health check passed")
            return True
        else:
            print(f"⚠️  Backend returned status {response.status_code}")
            return False
    except Exception as exc:
        print(f"⚠️  Backend not responding: {exc}")
        print("   (This is expected if backend not started yet)")
        return False

def print_next_steps() -> None:
    """Print instructions for next steps."""
    print_header("Setup Complete!")
    
    print("""
✅ Infrastructure is running!

Next Steps:

1. Start Backend (Terminal 1):
   cd backend
   uvicorn app.main:app --reload --port 8000

2. Start Frontend (Terminal 2):
   cd frontend
   npm run dev

3. Access the platform:
   - Dashboard: http://localhost:3000
   - API Docs: http://localhost:8000/docs
   - Grafana: http://localhost:3001 (admin/admin)
   - MLflow: http://localhost:5000

4. Seed historical data (optional):
   python scripts/seed_historical_data.py \\
     --symbols RELIANCE,TCS \\
     --start 2023-01-01 \\
     --end 2024-01-01

5. Run a backtest:
   python scripts/run_backtest.py \\
     --strategy supertrend_rsi \\
     --symbols RELIANCE \\
     --start 2023-01-01 \\
     --end 2023-12-31

⚠️  IMPORTANT REMINDERS:
- Edit .env with your actual API credentials
- Run 3 months of paper trading before going live
- Start live trading with minimum position sizes
- Review PRODUCTION.md before deploying to production
- Test the kill switch before going live

📚 Documentation:
- README.md - Complete platform guide
- PRODUCTION.md - Deployment & disaster recovery
- context.md - Build progress & architecture

Happy Trading! 🚀
(But remember: most retail algo traders lose money)
""")

def main() -> int:
    """Main setup flow."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║  Advanced India + Crypto Algorithmic Trading Platform       ║
║  Quick Start Setup                                           ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    steps = [
        ("Prerequisites", check_prerequisites),
        ("Environment", setup_environment),
        ("Infrastructure", start_infrastructure),
        ("Backend Dependencies", install_backend_deps),
        ("Frontend Dependencies", install_frontend_deps),
        ("Database Migrations", run_migrations),
    ]
    
    for step_name, step_func in steps:
        if not step_func():
            print(f"\n❌ Setup failed at: {step_name}")
            print("Please fix the errors above and try again.")
            return 1
    
    # Health check is optional
    verify_health()
    
    print_next_steps()
    return 0

if __name__ == "__main__":
    sys.exit(main())
