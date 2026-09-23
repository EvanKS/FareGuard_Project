"""
FareGuard Cloud Services Package

Exposes AWS S3, SNS, SQS, CloudWatch services, and unified CloudServicesManager.
"""

from cloud.aws_s3 import S3StorageService
from cloud.aws_sns import SNSNotificationService
from cloud.aws_sqs import SQSDLQService
from cloud.aws_cloudwatch import CloudWatchMetricsService
from cloud.manager import CloudServicesManager, cloud_manager

__all__ = [
    "S3StorageService",
    "SNSNotificationService",
    "SQSDLQService",
    "CloudWatchMetricsService",
    "CloudServicesManager",
    "cloud_manager",
]
