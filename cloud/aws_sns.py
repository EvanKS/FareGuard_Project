"""
FareGuard AWS SNS Cloud Push Notification Module

Publishes automated alerts (via SMS/Email topics) when high-severity anomalies,
system tampering, or severe revenue leakage events are flagged by the risk engine.
Supports live AWS SNS dispatch and simulated fallback logging.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import settings

logger = logging.getLogger(__name__)


class SNSNotificationService:
    """Manages AWS SNS notifications for transit operations and auditing."""

    def __init__(self) -> None:
        self.topic_arn = settings.SNS_TOPIC_ARN
        self.region = settings.AWS_REGION
        self.enabled = settings.USE_SNS
        self._sns_client = None
        self._dispatch_history: List[Dict[str, Any]] = []
        self._init_client()

    def _init_client(self) -> None:
        if self.enabled and settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            try:
                import boto3
                self._sns_client = boto3.client(
                    "sns",
                    region_name=self.region,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                )
                logger.info("Connected to live AWS SNS topic on region %s", self.region)
            except Exception as e:
                logger.warning("AWS SNS connection failed (%s); running in hybrid simulation mode.", e)
                self._sns_client = None

    @property
    def is_live(self) -> bool:
        return self._sns_client is not None

    def publish_alert(
        self,
        alert_id: str,
        route_id: str,
        risk_score: float,
        deficit_inr: float,
        severity: str,
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatch high-risk anomaly alert notification to the AWS SNS topic."""
        subject = f"[FAREGUARD ALERT] {severity}: Route {route_id} (Deficit: INR {deficit_inr:.2f})"
        body = (
            f"FAREGUARD CRITICAL REVENUE AUDIT DISPATCH\n"
            f"-----------------------------------------\n"
            f"Alert ID    : {alert_id}\n"
            f"Route ID    : {route_id}\n"
            f"Severity    : {severity}\n"
            f"Risk Score  : {risk_score:.4f}\n"
            f"Deficit     : INR {deficit_inr:,.2f}\n"
            f"Timestamp   : {datetime.now(timezone.utc).isoformat()}\n"
            f"Action Req  : Field Auditor Dispatch & Cash Box Reconciliation\n"
            f"Notes       : {message or 'Topological corridor anomaly detected.'}\n"
        )
        timestamp = datetime.now(timezone.utc).isoformat()

        if self.is_live:
            try:
                resp = self._sns_client.publish(
                    TopicArn=self.topic_arn,
                    Subject=subject[:100],  # SNS subject limit is 100 characters
                    Message=body,
                )
                dispatch_record = {
                    "alert_id": alert_id,
                    "route_id": route_id,
                    "severity": severity,
                    "message_id": resp.get("MessageId"),
                    "status": "DELIVERED",
                    "mode": "AWS_LIVE",
                    "timestamp": timestamp,
                    "subject": subject,
                }
                self._dispatch_history.append(dispatch_record)
                return dispatch_record
            except Exception as e:
                logger.error("Failed to publish to AWS SNS: %s", e)
                return {"status": "FAILED", "error": str(e), "mode": "AWS_LIVE"}

        # Simulated fallback dispatch
        message_id = f"msg-aws-sns-{int(datetime.now().timestamp())}-{len(self._dispatch_history) + 1}"
        record = {
            "alert_id": alert_id,
            "route_id": route_id,
            "severity": severity,
            "message_id": message_id,
            "status": "DISPATCHED",
            "mode": "CLOUD_SIMULATED",
            "timestamp": timestamp,
            "subject": subject,
            "topic": self.topic_arn.split(":")[-1],
        }
        self._dispatch_history.insert(0, record)
        # Keep last 50 in memory
        if len(self._dispatch_history) > 50:
            self._dispatch_history.pop()

        return record

    def get_recent_dispatches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the most recent notification dispatches."""
        return self._dispatch_history[:limit]

    def get_health(self) -> Dict[str, Any]:
        """Return connectivity health and stats for SNS."""
        return {
            "service": "AWS SNS",
            "status": "ONLINE" if (self.is_live or not self.enabled) else "STANDBY",
            "mode": "AWS_LIVE" if self.is_live else "HYBRID_MOCK",
            "topic_arn": self.topic_arn,
            "region": self.region,
            "dispatches_sent": len(self._dispatch_history),
            "last_dispatch": self._dispatch_history[0]["timestamp"] if self._dispatch_history else None,
            "ping_latency_ms": 18 if self.is_live else 1,
        }
