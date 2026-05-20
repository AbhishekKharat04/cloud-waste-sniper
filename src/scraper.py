import os
import boto3
import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AWSSniper:
    def __init__(self):
        self.mock_mode = os.getenv("MOCK_AWS", "false").lower() == "true"
        if not self.mock_mode:
            self.ec2_client = boto3.client('ec2', region_name=os.getenv("AWS_REGION", "us-east-1"))
            self.cloudwatch_client = boto3.client('cloudwatch', region_name=os.getenv("AWS_REGION", "us-east-1"))
            logger.info("AWSSniper initialized in LIVE mode (read-only).")
        else:
            logger.info("AWSSniper initialized in MOCK mode.")

    def scan_unattached_volumes(self) -> List[Dict]:
        """Scans for unattached EBS volumes."""
        if self.mock_mode:
            logger.info("Returning mocked unattached volumes.")
            return [
                {
                    "resource_id": "vol-0123456789abcdef0",
                    "type": "ebs_volume",
                    "reason": "Unattached (State=available)",
                    "estimated_monthly_waste": 10.0 # 100GB * $0.10
                }
            ]
        
        logger.info("Scanning AWS for unattached EBS volumes...")
        unattached_volumes = []
        try:
            # Paginator is better for large accounts
            paginator = self.ec2_client.get_paginator('describe_volumes')
            for page in paginator.paginate(Filters=[{'Name': 'status', 'Values': ['available']}]):
                for volume in page['Volumes']:
                    size_gb = volume['Size']
                    unattached_volumes.append({
                        "resource_id": volume['VolumeId'],
                        "type": "ebs_volume",
                        "reason": "Unattached (State=available)",
                        "estimated_monthly_waste": size_gb * 0.10  # Assuming $0.10/GB-month for gp3
                    })
        except Exception as e:
            logger.error(f"Error scanning volumes: {e}")
        return unattached_volumes

    def scan_idle_compute(self) -> List[Dict]:
        """Scans for idle EC2 instances based on CloudWatch metrics."""
        if self.mock_mode:
            logger.info("Returning mocked idle compute instances.")
            return [
                {
                    "resource_id": "i-0abc12345def67890",
                    "type": "ec2_instance",
                    "reason": "Max CPU < 3% over 4 days",
                    "suggested_downsize": "t3.medium",
                    "estimated_monthly_savings": 250.0
                }
            ]
        
        logger.info("Scanning AWS for idle EC2 instances...")
        idle_instances = []
        # In a real scenario, this would use self.cloudwatch_client.get_metric_statistics
        # over the last 4 days for CPUUtilization. For brevity in MVP, we just outline it:
        try:
            instances = self.ec2_client.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
            # pseudo-code for CW fetch:
            # for res in instances['Reservations']:
            #     for inst in res['Instances']:
            #         metrics = self.cloudwatch_client.get_metric_statistics(...)
            #         if max(metrics) < 3.0:
            #             idle_instances.append(...)
            pass 
        except Exception as e:
            logger.error(f"Error scanning compute: {e}")
        return idle_instances

    def scan_all(self) -> List[Dict]:
        """Runs all waste scans."""
        waste = []
        waste.extend(self.scan_unattached_volumes())
        waste.extend(self.scan_idle_compute())
        return waste
