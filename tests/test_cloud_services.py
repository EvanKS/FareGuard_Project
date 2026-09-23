"""
Unit tests for FareGuard Cloud Services Suite

Validates AWS S3, AWS SNS, AWS SQS, AWS CloudWatch, and CloudServicesManager
in both simulated cloud mode and live configuration.
"""

import pytest
from cloud.aws_s3 import S3StorageService
from cloud.aws_sns import SNSNotificationService
from cloud.aws_sqs import SQSDLQService
from cloud.aws_cloudwatch import CloudWatchMetricsService
from cloud.manager import CloudServicesManager


def test_s3_storage_service():
    s3 = S3StorageService()
    health = s3.get_health()
    assert health["service"] == "AWS S3"
    assert health["status"] in ("ONLINE", "STANDBY")
    assert health["object_count"] >= 0

    # Test simulated upload
    upload_res = s3.upload_file("config.py", "configs/config.py")
    assert upload_res["status"] in ("STORED", "UPLOADED")
    assert upload_res["key"] == "configs/config.py"

    # Test audit snapshot archive
    snapshot_res = s3.save_audit_snapshot("ALT-TEST-99", {"route_id": "500D", "deficit": 250.0})
    assert snapshot_res["status"] == "ARCHIVED"


def test_sns_notification_service():
    sns = SNSNotificationService()
    health = sns.get_health()
    assert health["service"] == "AWS SNS"
    assert health["status"] in ("ONLINE", "STANDBY")

    # Publish alert
    alert = sns.publish_alert(
        alert_id="ALT-UNIT-1",
        route_id="335E",
        risk_score=0.88,
        deficit_inr=920.0,
        severity="HIGH_RISK",
        message="Unit test notification",
    )
    assert alert["status"] in ("DISPATCHED", "DELIVERED")
    assert alert["severity"] == "HIGH_RISK"
    assert len(sns.get_recent_dispatches()) > 0


def test_sqs_dlq_service():
    sqs = SQSDLQService()
    health = sqs.get_health()
    assert health["service"] == "AWS SQS (DLQ)"

    # Push malformed event
    res = sqs.push_malformed_event({"bad_field": None}, "Missing required schema fields")
    assert res["status"] in ("BUFFERED_IN_CLOUD_DLQ", "QUEUED_AWS_SQS")
    assert sqs.get_queue_depth() >= 1


def test_cloudwatch_metrics_service():
    cw = CloudWatchMetricsService()
    health = cw.get_health()
    assert health["service"] == "AWS CloudWatch"

    # Put single metric
    metric_res = cw.put_metric("UnitTestingMetric", 42.0, "Count")
    assert metric_res["status"] in ("RECORDED", "PUBLISHED_LIVE")

    # Batch publish
    telemetry = cw.publish_pipeline_telemetry(tps=125.0, deficit_inr=4500.0, anomaly_count=3, active_routes=12)
    assert len(telemetry) == 4


def test_cloud_services_manager():
    mgr = CloudServicesManager()
    status = mgr.get_full_cloud_status()
    assert "deployment_target" in status
    assert len(status["services"]) >= 4

    # Test end-to-end dispatch
    dispatch_test = mgr.trigger_test_dispatch()
    assert dispatch_test["status"] == "SUCCESS"
    assert "sns" in dispatch_test
    assert "s3" in dispatch_test
    assert "cloudwatch" in dispatch_test
