"""
FareGuard Configuration Module

Centralized configuration using environment variables with sensible defaults.
All settings are loaded from .env file or environment variables.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file if it exists
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    # Try project root
    _project_root = Path(__file__).parent
    _env_file = _project_root / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)


class Settings:
    """Application settings loaded from environment variables."""

    # Project root
    PROJECT_ROOT: Path = Path(__file__).parent

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://fareguard:fareguard@localhost:5432/fareguard"
    )
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "fareguard")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "fareguard")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "fareguard")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))

    # API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # Streaming
    STREAM_NAME: str = os.getenv("STREAM_NAME", "fareguard:ticket_events")
    CONSUMER_GROUP: str = os.getenv("CONSUMER_GROUP", "fareguard_processors")
    CONSUMER_NAME: str = os.getenv("CONSUMER_NAME", "processor_1")

    # Data Directories
    DATA_DIR: Path = PROJECT_ROOT / os.getenv("DATA_DIR", "data")
    RAW_DATA_DIR: Path = PROJECT_ROOT / os.getenv("RAW_DATA_DIR", "data/raw")
    GTFS_DIR: Path = RAW_DATA_DIR / "gtfs"
    BMTC_STATS_DIR: Path = RAW_DATA_DIR / "bmtc_statistics"
    PROCESSED_DATA_DIR: Path = PROJECT_ROOT / os.getenv("PROCESSED_DATA_DIR", "data/processed")
    SYNTHETIC_DATA_DIR: Path = PROJECT_ROOT / os.getenv("SYNTHETIC_DATA_DIR", "data/synthetic")
    METADATA_DIR: Path = PROJECT_ROOT / os.getenv("METADATA_DIR", "data/metadata")
    MODEL_DIR: Path = PROJECT_ROOT / os.getenv("MODEL_DIR", "models")

    # Simulation
    SIMULATION_SPEED: float = float(os.getenv("SIMULATION_SPEED", "1.0"))
    RANDOM_SEED: int = int(os.getenv("RANDOM_SEED", "42"))
    ANOMALY_RATE: float = float(os.getenv("ANOMALY_RATE", "0.15"))

    # Demo Limits
    DEMO_ROUTE_LIMIT: int = int(os.getenv("DEMO_ROUTE_LIMIT", "10"))
    DEMO_TRIP_LIMIT: int = int(os.getenv("DEMO_TRIP_LIMIT", "50"))
    DEMO_EVENT_LIMIT: int = int(os.getenv("DEMO_EVENT_LIMIT", "1000"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Cloud Infrastructure & Services (AWS / Managed Serverless)
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-south-1")
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID", None)
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY", None)
    
    # S3 Object Storage (Models, GTFS, Auditor Snapshots)
    USE_S3: bool = os.getenv("USE_S3", "false").lower() in ("true", "1", "yes")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "fareguard-cloud-artifacts")
    
    # SNS Push Notifications (Auditor SMS/Email Dispatch)
    USE_SNS: bool = os.getenv("USE_SNS", "false").lower() in ("true", "1", "yes")
    SNS_TOPIC_ARN: str = os.getenv("SNS_TOPIC_ARN", "arn:aws:sns:ap-south-1:123456789012:fareguard-auditor-alerts")
    
    # SQS Dead Letter Queue (DLQ for Malformed Telemetry)
    USE_SQS: bool = os.getenv("USE_SQS", "false").lower() in ("true", "1", "yes")
    SQS_DLQ_URL: str = os.getenv("SQS_DLQ_URL", "https://sqs.ap-south-1.amazonaws.com/123456789012/fareguard-telemetry-dlq")
    
    # CloudWatch Metrics & Monitoring
    USE_CLOUDWATCH: bool = os.getenv("USE_CLOUDWATCH", "false").lower() in ("true", "1", "yes")
    CLOUDWATCH_NAMESPACE: str = os.getenv("CLOUDWATCH_NAMESPACE", "FareGuard/TransitIntelligence")

    # Cloud Provider Profile
    CLOUD_DEPLOYMENT_TARGET: str = os.getenv("CLOUD_DEPLOYMENT_TARGET", "AWS Cloud-Native (ap-south-1)")

    # Risk Thresholds (configurable)
    RISK_THRESHOLD_NORMAL: float = 0.30
    RISK_THRESHOLD_MONITOR: float = 0.60
    RISK_THRESHOLD_SUSPICIOUS: float = 0.80

    def ensure_directories(self) -> None:
        """Create all required data directories if they don't exist."""
        for dir_path in [
            self.DATA_DIR,
            self.RAW_DATA_DIR,
            self.GTFS_DIR,
            self.BMTC_STATS_DIR,
            self.PROCESSED_DATA_DIR,
            self.SYNTHETIC_DATA_DIR,
            self.METADATA_DIR,
            self.MODEL_DIR,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def get_severity(self, risk_score: float) -> str:
        """Get severity label from risk score."""
        if risk_score >= self.RISK_THRESHOLD_SUSPICIOUS:
            return "HIGH_RISK"
        elif risk_score >= self.RISK_THRESHOLD_MONITOR:
            return "SUSPICIOUS"
        elif risk_score >= self.RISK_THRESHOLD_NORMAL:
            return "MONITOR"
        else:
            return "NORMAL"


# Global settings instance
settings = Settings()
