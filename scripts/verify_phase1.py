"""Phase 1 comprehensive verification script."""
import sys
import os

sys.path.insert(0, ".")

print("=" * 60)
print("PHASE 1 - COMPREHENSIVE VERIFICATION")
print("=" * 60)

# 1. Python environment
print(f"\n[1] Python version: {sys.version}")

# 2. All core imports
imports_ok = []
imports_fail = []
for pkg in [
    "fastapi", "uvicorn", "pydantic", "pydantic_settings", "dotenv",
    "sqlalchemy", "psycopg2", "alembic", "pandas", "numpy", "pyarrow",
    "sklearn", "xgboost", "joblib", "networkx", "redis", "streamlit",
    "plotly", "folium", "requests", "httpx", "pytest", "structlog",
    "click", "tqdm", "yaml",
]:
    try:
        __import__(pkg)
        imports_ok.append(pkg)
    except ImportError:
        imports_fail.append(pkg)
print(f"\n[2] Imports OK: {len(imports_ok)}/{len(imports_ok) + len(imports_fail)}")
if imports_fail:
    print(f"    FAILED: {imports_fail}")
else:
    print("    All packages importable")

# 3. Project modules
proj_ok = []
proj_fail = []
for mod in ["config", "ingestion", "graph", "simulation", "ml", "streaming", "risk", "database", "api"]:
    try:
        __import__(mod)
        proj_ok.append(mod)
    except ImportError as e:
        proj_fail.append((mod, str(e)))
print(f"\n[3] Project modules: {len(proj_ok)}/{len(proj_ok) + len(proj_fail)}")
if proj_fail:
    print(f"    FAILED: {proj_fail}")
else:
    print("    All project modules importable")

# 4. Config
from config import settings

print(f"\n[4] Configuration:")
print(f"    DATABASE_URL: {settings.DATABASE_URL[:40]}...")
print(f"    REDIS_URL: {settings.REDIS_URL}")
print(f"    RANDOM_SEED: {settings.RANDOM_SEED}")
print(f"    ANOMALY_RATE: {settings.ANOMALY_RATE}")
print(f"    Severity(0.1): {settings.get_severity(0.1)}")
print(f"    Severity(0.5): {settings.get_severity(0.5)}")
print(f"    Severity(0.7): {settings.get_severity(0.7)}")
print(f"    Severity(0.9): {settings.get_severity(0.9)}")

# 5. Directory structure
from pathlib import Path

root = Path(".")
required_dirs = [
    "data/raw/gtfs", "data/raw/bmtc_statistics", "data/processed",
    "data/synthetic", "data/metadata", "ingestion", "graph", "simulation",
    "ml", "streaming", "risk", "database", "api", "dashboard/pages",
    "dashboard/components", "tests/unit", "tests/integration", "tests/api",
    "tests/ml", "tests/graph", "tests/streaming", "tests/end_to_end",
    "scripts", "docs", "models", "notebooks",
]
missing_dirs = [d for d in required_dirs if not (root / d).is_dir()]
print(f"\n[5] Directories: {len(required_dirs) - len(missing_dirs)}/{len(required_dirs)}")
if missing_dirs:
    print(f"    MISSING: {missing_dirs}")
else:
    print("    All directories present")

# 6. Required files
required_files = [
    "requirements.txt", "pyproject.toml", ".env.example", "docker-compose.yml",
    ".gitignore", "Dockerfile", "config.py", "README.md", "LICENSE",
    "api/__init__.py", "api/main.py", "ingestion/__init__.py",
    "graph/__init__.py", "simulation/__init__.py", "ml/__init__.py",
    "streaming/__init__.py", "risk/__init__.py", "database/__init__.py",
    "tests/unit/test_phase1_environment.py",
]
missing_files = [f for f in required_files if not (root / f).is_file()]
print(f"\n[6] Files: {len(required_files) - len(missing_files)}/{len(required_files)}")
if missing_files:
    print(f"    MISSING: {missing_files}")
else:
    print("    All files present")

# 7. FastAPI app
from api.main import app

print(f"\n[7] FastAPI app: {app.title} v{app.version}")
route_paths = [r.path for r in app.routes if hasattr(r, "path")]
print(f"    Routes: {route_paths}")

# 8. FastAPI health check
from fastapi.testclient import TestClient

client = TestClient(app)
r = client.get("/health")
print(f"\n[8] GET /health: status={r.status_code}, body={r.json()}")
r2 = client.get("/system/status")
print(f"    GET /system/status: status={r2.status_code}, modules={list(r2.json().get('modules', {}).keys())}")

# 9. Docker compose
import yaml

with open("docker-compose.yml") as f:
    dc = yaml.safe_load(f)
services = list(dc.get("services", {}).keys())
print(f"\n[9] Docker Compose services: {services}")

# 10. .env.example
with open(".env.example") as f:
    env_content = f.read()
env_vars = [line.split("=")[0] for line in env_content.splitlines() if "=" in line and not line.startswith("#")]
print(f"\n[10] .env.example variables: {len(env_vars)} defined")
print(f"     Keys: {env_vars}")

print()
print("=" * 60)
print("PHASE 1 VERIFICATION COMPLETE")
print("=" * 60)
