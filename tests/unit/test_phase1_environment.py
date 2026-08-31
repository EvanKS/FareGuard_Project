"""
Phase 1 Tests - Environment and Project Structure

Tests to verify:
1. Project directory structure is correct
2. All required Python packages can be imported
3. Configuration module works
4. FastAPI app initializes
5. Docker Compose file is valid YAML
"""

import importlib
import os
import sys
from pathlib import Path

import pytest
import yaml

# Ensure project root is on sys.path
# tests/unit/test_phase1_environment.py -> parent = tests/unit -> parent = tests -> parent = project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestProjectStructure:
    """Verify the project directory structure exists."""

    REQUIRED_DIRS = [
        "data",
        "data/raw",
        "data/raw/gtfs",
        "data/raw/bmtc_statistics",
        "data/processed",
        "data/synthetic",
        "data/metadata",
        "ingestion",
        "graph",
        "simulation",
        "ml",
        "streaming",
        "risk",
        "database",
        "api",
        "dashboard",
        "dashboard/pages",
        "dashboard/components",
        "tests",
        "tests/unit",
        "tests/integration",
        "tests/api",
        "tests/ml",
        "tests/graph",
        "tests/streaming",
        "tests/end_to_end",
        "scripts",
        "docs",
        "models",
        "notebooks",
    ]

    REQUIRED_FILES = [
        "requirements.txt",
        "pyproject.toml",
        ".env.example",
        "docker-compose.yml",
        ".gitignore",
        "Dockerfile",
        "config.py",
        "api/main.py",
        "api/__init__.py",
        "ingestion/__init__.py",
        "graph/__init__.py",
        "simulation/__init__.py",
        "ml/__init__.py",
        "streaming/__init__.py",
        "risk/__init__.py",
        "database/__init__.py",
    ]

    def test_required_directories_exist(self):
        """All required directories must exist."""
        missing = []
        for dir_name in self.REQUIRED_DIRS:
            dir_path = PROJECT_ROOT / dir_name
            if not dir_path.is_dir():
                missing.append(dir_name)
        assert not missing, f"Missing directories: {missing}"

    def test_required_files_exist(self):
        """All required configuration and init files must exist."""
        missing = []
        for file_name in self.REQUIRED_FILES:
            file_path = PROJECT_ROOT / file_name
            if not file_path.is_file():
                missing.append(file_name)
        assert not missing, f"Missing files: {missing}"

    def test_requirements_txt_not_empty(self):
        """requirements.txt must contain dependencies."""
        req_file = PROJECT_ROOT / "requirements.txt"
        content = req_file.read_text()
        # Count non-empty, non-comment lines
        deps = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(deps) >= 10, f"Expected at least 10 dependencies, found {len(deps)}"

    def test_env_example_has_required_vars(self):
        """The .env.example must define all critical variables."""
        env_file = PROJECT_ROOT / ".env.example"
        content = env_file.read_text()
        required_vars = [
            "DATABASE_URL",
            "REDIS_URL",
            "API_HOST",
            "API_PORT",
            "STREAM_NAME",
            "RANDOM_SEED",
            "ANOMALY_RATE",
        ]
        missing = [var for var in required_vars if var not in content]
        assert not missing, f"Missing env vars in .env.example: {missing}"


class TestPythonImports:
    """Verify that core Python packages are importable."""

    CORE_PACKAGES = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "sqlalchemy",
        "pandas",
        "numpy",
        "sklearn",
        "networkx",
        "redis",
        "plotly",
        "requests",
        "httpx",
        "pytest",
        "dotenv",
    ]

    @pytest.mark.parametrize("package_name", CORE_PACKAGES)
    def test_import_package(self, package_name: str):
        """Each core package must be importable."""
        try:
            importlib.import_module(package_name)
        except ImportError as e:
            pytest.fail(f"Cannot import {package_name}: {e}")

    def test_import_xgboost(self):
        """XGBoost should be importable."""
        try:
            import xgboost
        except ImportError:
            pytest.skip("XGBoost not installed (optional)")


class TestProjectModuleImports:
    """Verify that project modules can be imported."""

    PROJECT_MODULES = [
        "config",
        "ingestion",
        "graph",
        "simulation",
        "ml",
        "streaming",
        "risk",
        "database",
        "api",
    ]

    @pytest.mark.parametrize("module_name", PROJECT_MODULES)
    def test_import_project_module(self, module_name: str):
        """Each project module must be importable."""
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            pytest.fail(f"Cannot import project module '{module_name}': {e}")


class TestConfiguration:
    """Verify the configuration module works correctly."""

    def test_settings_instance_exists(self):
        """Settings singleton must exist."""
        from config import settings
        assert settings is not None

    def test_settings_has_database_url(self):
        """Settings must have DATABASE_URL."""
        from config import settings
        assert settings.DATABASE_URL is not None
        assert "postgresql" in settings.DATABASE_URL

    def test_settings_has_redis_url(self):
        """Settings must have REDIS_URL."""
        from config import settings
        assert settings.REDIS_URL is not None
        assert "redis" in settings.REDIS_URL

    def test_settings_data_directories(self):
        """Settings must define data directory paths."""
        from config import settings
        assert settings.DATA_DIR is not None
        assert settings.RAW_DATA_DIR is not None
        assert settings.PROCESSED_DATA_DIR is not None
        assert settings.SYNTHETIC_DATA_DIR is not None
        assert settings.METADATA_DIR is not None
        assert settings.MODEL_DIR is not None

    def test_settings_ensure_directories(self):
        """ensure_directories() must create all data directories."""
        from config import settings
        settings.ensure_directories()
        assert settings.DATA_DIR.is_dir()
        assert settings.RAW_DATA_DIR.is_dir()
        assert settings.GTFS_DIR.is_dir()
        assert settings.PROCESSED_DATA_DIR.is_dir()
        assert settings.SYNTHETIC_DATA_DIR.is_dir()
        assert settings.METADATA_DIR.is_dir()
        assert settings.MODEL_DIR.is_dir()

    def test_settings_random_seed(self):
        """Random seed must be an integer."""
        from config import settings
        assert isinstance(settings.RANDOM_SEED, int)
        assert settings.RANDOM_SEED == 42  # default

    def test_settings_risk_thresholds(self):
        """Risk thresholds must be properly ordered."""
        from config import settings
        assert 0 < settings.RISK_THRESHOLD_NORMAL < settings.RISK_THRESHOLD_MONITOR
        assert settings.RISK_THRESHOLD_MONITOR < settings.RISK_THRESHOLD_SUSPICIOUS
        assert settings.RISK_THRESHOLD_SUSPICIOUS <= 1.0

    def test_severity_classification(self):
        """Severity classification must work correctly."""
        from config import settings
        assert settings.get_severity(0.0) == "NORMAL"
        assert settings.get_severity(0.15) == "NORMAL"
        assert settings.get_severity(0.35) == "MONITOR"
        assert settings.get_severity(0.65) == "SUSPICIOUS"
        assert settings.get_severity(0.85) == "HIGH_RISK"
        assert settings.get_severity(1.0) == "HIGH_RISK"


class TestFastAPIApp:
    """Verify the FastAPI application initializes correctly."""

    def test_app_creates(self):
        """FastAPI app object must be created."""
        from api.main import app
        assert app is not None
        assert app.title == "FareGuard API"

    def test_health_endpoint_exists(self):
        """Health endpoint must be registered."""
        from api.main import app
        routes = [route.path for route in app.routes if hasattr(route, "path")]
        assert "/health" in routes

    def test_health_endpoint_response(self):
        """Health endpoint must return valid response."""
        from fastapi.testclient import TestClient
        from api.main import app

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "FareGuard API"
        assert "version" in data

    def test_system_status_endpoint(self):
        """System status endpoint must return module statuses."""
        from fastapi.testclient import TestClient
        from api.main import app

        client = TestClient(app)
        response = client.get("/system/status")
        assert response.status_code == 200
        data = response.json()
        assert data["api"] == "running"
        assert "modules" in data

    def test_openapi_docs(self):
        """OpenAPI docs must be accessible."""
        from fastapi.testclient import TestClient
        from api.main import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "FareGuard API"


class TestDockerCompose:
    """Verify docker-compose.yml is valid."""

    def test_docker_compose_is_valid_yaml(self):
        """docker-compose.yml must be valid YAML."""
        dc_path = PROJECT_ROOT / "docker-compose.yml"
        with open(dc_path, "r") as f:
            config = yaml.safe_load(f)
        assert config is not None

    def test_docker_compose_has_services(self):
        """docker-compose.yml must define postgres, redis, api services."""
        dc_path = PROJECT_ROOT / "docker-compose.yml"
        with open(dc_path, "r") as f:
            config = yaml.safe_load(f)
        services = config.get("services", {})
        assert "postgres" in services, "Missing postgres service"
        assert "redis" in services, "Missing redis service"
        assert "api" in services, "Missing api service"

    def test_postgres_service_config(self):
        """PostgreSQL service must have correct configuration."""
        dc_path = PROJECT_ROOT / "docker-compose.yml"
        with open(dc_path, "r") as f:
            config = yaml.safe_load(f)
        pg = config["services"]["postgres"]
        assert "postgres" in pg["image"]
        assert "5432:5432" in pg["ports"]

    def test_redis_service_config(self):
        """Redis service must have correct configuration."""
        dc_path = PROJECT_ROOT / "docker-compose.yml"
        with open(dc_path, "r") as f:
            config = yaml.safe_load(f)
        redis_svc = config["services"]["redis"]
        assert "redis" in redis_svc["image"]
        assert "6379:6379" in redis_svc["ports"]
