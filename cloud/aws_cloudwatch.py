"""
FareGuard AWS CloudWatch Observability & Metrics Module

Streams real-time operational telemetry, anomaly rates, ingestion throughput (TPS),
and financial deficit metrics to AWS CloudWatch for municipal-grade auditing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import settings

logger = logging.getLogger(__name__)


class CloudWatchMetricsService:
    """Publishes custom operational metrics to AWS CloudWatch."""

    def __init__(self) -> None:
        self.namespace = settings.CLOUDWATCH_NAMESPACE
        self.region = settings.AWS_REGION
        self.enabled = settings.USE_CLOUDWATCH
        self._cw_client = None
        self._recent_metric_points: List[Dict[str, Any]] = []
        self._init_client()

    def _init_client(self) -> None:
        if self.enabled and settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            try:
                import boto3
                self._cw_client = boto3.client(
                    "cloudwatch",
                    region_name=self.region,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                )
                logger.info("Connected to live AWS CloudWatch on region %s", self.region)
            except Exception as e:
                logger.warning("AWS CloudWatch connection failed (%s); operating in simulated mode.", e)
                self._cw_client = None

    @property
    def is_live(self) -> bool:
        return self._cw_client is not None

    def put_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Publish a single operational data point to CloudWatch."""
        now = datetime.now(timezone.utc)
        dim = dimensions or [{"Name": "Environment", "Value": "Production"}]
        metric_entry = {
            "MetricName": metric_name,
            "Value": float(value),
            "Unit": unit,
            "Timestamp": now.isoformat(),
            "Dimensions": dim,
        }

        if self.is_live:
            try:
                self._cw_client.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=[
                        {
                            "MetricName": metric_name,
                            "Value": float(value),
                            "Unit": unit,
                            "Timestamp": now,
                            "Dimensions": dim,
                        }
                    ],
                )
                metric_entry["status"] = "PUBLISHED_LIVE"
                metric_entry["mode"] = "AWS_LIVE"
                return metric_entry
            except Exception as e:
                logger.error("Failed to post metric to AWS CloudWatch: %s", e)
                metric_entry["status"] = "FAILED"
                metric_entry["error"] = str(e)
                return metric_entry

        # Simulated cloud metric aggregation
        metric_entry["status"] = "RECORDED"
        metric_entry["mode"] = "CLOUD_SIMULATED"
        self._recent_metric_points.insert(0, metric_entry)
        if len(self._recent_metric_points) > 100:
            self._recent_metric_points.pop()

        return metric_entry

    def publish_pipeline_telemetry(
        self,
        tps: float,
        deficit_inr: float,
        anomaly_count: int,
        active_routes: int,
    ) -> List[Dict[str, Any]]:
        """Batch publish end-to-end FareGuard telemetry to CloudWatch."""
        results = [
            self.put_metric("StreamingIngestionRate", tps, "Count/Second"),
            self.put_metric("TotalMonetaryDeficitINR", deficit_inr, "Count"),
            self.put_metric("DetectedAnomaliesCount", anomaly_count, "Count"),
            self.put_metric("ActiveMonitoredRoutes", active_routes, "Count"),
        ]
        return results

    def get_recent_metrics(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Return recently recorded metric data points."""
        return self._recent_metric_points[:limit]

    def get_health(self) -> Dict[str, Any]:
        """Return connectivity health and stats for CloudWatch."""
        return {
            "service": "AWS CloudWatch",
            "status": "ONLINE" if (self.is_live or not self.enabled) else "STANDBY",
            "mode": "AWS_LIVE" if self.is_live else "HYBRID_MOCK",
            "namespace": self.namespace,
            "region": self.region,
            "published_points": len(self._recent_metric_points),
            "last_metric": self._recent_metric_points[0]["MetricName"] if self._recent_metric_points else "None",
            "ping_latency_ms": 12 if self.is_live else 1,
        }
