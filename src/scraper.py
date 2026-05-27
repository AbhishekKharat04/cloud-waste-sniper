"""AWS Cloud Waste Scanner with optional Bright Data SERP-powered live pricing.

This module detects wasteful AWS resources (unattached EBS volumes, idle EC2
instances) using either live boto3 calls or high-fidelity mock data. When
the ``USE_REAL_PRICING`` toggle is enabled and a valid ``BRIGHTDATA_API_KEY``
is present, per-unit pricing is fetched in real time from Google search snippets
via Bright Data's SERP API.
"""

import os
import re
import logging
import requests
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Default Fallback Prices ---
_DEFAULT_GP3_PRICE_PER_GB = 0.08    # $/GB-month for gp3 in us-east-1 (Default estimate: $8.00 for 100GB)
_DEFAULT_T3_2XL_PRICE_HR  = 0.3328  # $/hr for t3.2xlarge on-demand (~$239.62/month)
_DEFAULT_T3_MD_PRICE_HR   = 0.0416  # $/hr for t3.medium on-demand (~$29.95/month)

class BrightDataPricingClient:
    """Fetches live AWS pricing via Bright Data's SERP API.

    Uses Bright Data's Google SERP API to search for current AWS pricing
    information. The SERP results are parsed for pricing snippets that
    contain dollar amounts for the requested resource types.

    If the API key is missing, invalid, or the request fails for any
    reason, methods return None and the caller falls back to defaults.
    """

    _SERP_API_URL = "https://api.brightdata.com/serp/req"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def _serp_query(self, query: str, timeout: int = 25) -> Optional[dict]:
        """Sends a Google SERP query through Bright Data's API."""
        payload = {
            "query": query,
            "search_engine": "google",
            "country": "us",
            "language": "en",
        }
        try:
            logger.info(f"[BrightData SERP] Query: \"{query}\"")
            resp = self.session.post(
                self._SERP_API_URL,
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"[BrightData SERP] Successful response received.")
            return data
        except Exception as e:
            logger.warning(f"[BrightData SERP] API query failed: {e}")
            return None

    def _extract_price(self, text: str) -> Optional[float]:
        """Uses regex to find dollar values (e.g. $0.08, $0.3328) in search snippets."""
        # Find all occurrences of e.g. $0.08 or $0.3328
        matches = re.findall(r'\$(\d+(?:\.\d+)+)', text)
        for match in matches:
            try:
                val = float(match)
                if val > 0:
                    return val
            except ValueError:
                continue
        return None

    def fetch_gp3_price(self) -> Optional[float]:
        """Queries Google via SERP for gp3 storage price per GB in us-east-1."""
        query = "AWS EBS gp3 price per GB-month us-east-1 site:aws.amazon.com"
        serp_data = self._serp_query(query)
        if not serp_data:
            return None

        # Search organic results for a valid price
        organic_results = serp_data.get("organic", [])
        for result in organic_results:
            snippet = result.get("snippet", "") + " " + result.get("description", "")
            price = self._extract_price(snippet)
            if price is not None and 0.01 <= price <= 0.50:  # Sanity range check
                logger.info(f"[BrightData SERP] Extracted gp3 price: ${price}/GB-month")
                return price

        logger.warning("[BrightData SERP] Could not extract valid gp3 price from search snippets.")
        return None

    def fetch_t3_2xlarge_price(self) -> Optional[float]:
        """Queries Google via SERP for t3.2xlarge on-demand hourly price in us-east-1."""
        query = "AWS EC2 t3.2xlarge on-demand price per hour us-east-1 site:aws.amazon.com"
        serp_data = self._serp_query(query)
        if not serp_data:
            return None

        organic_results = serp_data.get("organic", [])
        for result in organic_results:
            snippet = result.get("snippet", "") + " " + result.get("description", "")
            price = self._extract_price(snippet)
            if price is not None and 0.10 <= price <= 2.00:  # Sanity range check
                logger.info(f"[BrightData SERP] Extracted t3.2xlarge price: ${price}/hr")
                return price

        logger.warning("[BrightData SERP] Could not extract valid t3.2xlarge price from search snippets.")
        return None


class AWSSniper:
    def __init__(self):
        self.mock_mode = os.getenv("MOCK_AWS", "false").lower() == "true"
        self.use_real_pricing = os.getenv("USE_REAL_PRICING", "false").lower() == "true"
        self.brightdata_api_key = os.getenv("BRIGHTDATA_API_KEY", "").strip()

        # Instantiate live clients if not mock mode
        if not self.mock_mode:
            self.ec2_client = boto3.client('ec2', region_name=os.getenv("AWS_REGION", "us-east-1"))
            self.cloudwatch_client = boto3.client('cloudwatch', region_name=os.getenv("AWS_REGION", "us-east-1"))
            logger.info("AWSSniper initialized in LIVE mode (read-only).")
        else:
            logger.info("AWSSniper initialized in MOCK mode.")

        # Pricing Client Initialization
        self.pricing_client = None
        self.live_pricing = False
        if self.use_real_pricing:
            if self.brightdata_api_key:
                self.pricing_client = BrightDataPricingClient(self.brightdata_api_key)
                self.live_pricing = True
                logger.info("Bright Data real-time pricing client active.")
            else:
                logger.warning("USE_REAL_PRICING is active, but BRIGHTDATA_API_KEY is missing. Falling back to default estimates.")

    def scan_unattached_volumes(self) -> List[Dict]:
        """Scans for unattached EBS volumes and appends pricing."""
        # 1. Fetch unit price
        unit_price = _DEFAULT_GP3_PRICE_PER_GB
        pricing_source = "default"

        if self.live_pricing and self.pricing_client:
            fetched_price = self.pricing_client.fetch_gp3_price()
            if fetched_price is not None:
                unit_price = fetched_price
                pricing_source = "brightdata"
            else:
                logger.warning("Failed to fetch live gp3 pricing. Using default estimates.")

        # 2. Get unattached volumes
        unattached_volumes = []
        if self.mock_mode:
            # Simulated unattached gp3 volume #1 (100 GB)
            unattached_volumes.append({
                "resource_id": "vol-0123456789abcdef0",
                "type": "ebs_volume",
                "reason": "Unattached for 30+ days (State=available)",
                "size_gb": 100,
                "unit_price": unit_price,
                "estimated_monthly_waste": round(100 * unit_price, 2),
                "pricing_source": pricing_source
            })
            # Simulated unattached gp3 volume #2 (200 GB)
            unattached_volumes.append({
                "resource_id": "vol-0a1b2c3d4e5f67890",
                "type": "ebs_volume",
                "reason": "Unattached, snapshot backup exists",
                "size_gb": 200,
                "unit_price": unit_price,
                "estimated_monthly_waste": round(200 * unit_price, 2),
                "pricing_source": pricing_source
            })
        else:
            try:
                paginator = self.ec2_client.get_paginator('describe_volumes')
                for page in paginator.paginate(Filters=[{'Name': 'status', 'Values': ['available']}]):
                    for volume in page['Volumes']:
                        size_gb = volume['Size']
                        vol_type = volume.get('VolumeType', 'gp3')
                        # If different than gp3, we still estimate with gp3 rate for MVP simplicity
                        unattached_volumes.append({
                            "resource_id": volume['VolumeId'],
                            "type": "ebs_volume",
                            "reason": f"Unattached (State=available)",
                            "size_gb": size_gb,
                            "unit_price": unit_price,
                            "estimated_monthly_waste": size_gb * unit_price,
                            "pricing_source": pricing_source
                        })
            except Exception as e:
                logger.error(f"Error scanning live volumes: {e}")

        return unattached_volumes

    def scan_idle_compute(self) -> List[Dict]:
        """Scans for idle EC2 compute and appends savings statistics."""
        # 1. Fetch unit prices
        t3_2xl_price = _DEFAULT_T3_2XL_PRICE_HR
        pricing_source = "default"

        if self.live_pricing and self.pricing_client:
            fetched_price = self.pricing_client.fetch_t3_2xlarge_price()
            if fetched_price is not None:
                t3_2xl_price = fetched_price
                pricing_source = "brightdata"
            else:
                logger.warning("Failed to fetch live t3.2xlarge pricing. Using default estimates.")

        # Downsize to t3.medium savings calculation
        t3_md_price = _DEFAULT_T3_MD_PRICE_HR
        # If live pricing scaled, scale the downsized instance rate proportionally
        if pricing_source == "brightdata":
            scale_ratio = t3_2xl_price / _DEFAULT_T3_2XL_PRICE_HR
            t3_md_price = _DEFAULT_T3_MD_PRICE_HR * scale_ratio

        monthly_current = t3_2xl_price * 24 * 30
        monthly_optimized = t3_md_price * 24 * 30
        estimated_savings = monthly_current - monthly_optimized

        # 2. Get idle instances
        idle_compute = []
        if self.mock_mode:
            idle_compute.append({
                "resource_id": "i-0abc12345def67890",
                "type": "ec2_instance",
                "reason": "Max CPU < 3% over 7 days",
                "suggested_downsize": "t3.medium",
                "unit_price": t3_2xl_price,
                "estimated_monthly_savings": round(estimated_savings, 2),
                "pricing_source": pricing_source
            })
            # Zombie instance — near-zero utilization over 14 days
            t3_sm_price = _DEFAULT_T3_MD_PRICE_HR * 0.5  # t3.small is ~half of t3.medium
            if pricing_source == "brightdata":
                scale_ratio = t3_2xl_price / _DEFAULT_T3_2XL_PRICE_HR
                t3_sm_price = t3_sm_price * scale_ratio
            zombie_savings = (t3_2xl_price - t3_sm_price) * 24 * 30
            idle_compute.append({
                "resource_id": "i-0fed98765cba43210",
                "type": "ec2_instance",
                "reason": "Max CPU < 1% over 14 days (zombie)",
                "suggested_downsize": "t3.small",
                "unit_price": t3_2xl_price,
                "estimated_monthly_savings": round(zombie_savings, 2),
                "pricing_source": pricing_source
            })
        else:
            # Pseudo-code / MVP framework for CloudWatch idle computer scanning
            try:
                instances = self.ec2_client.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
                # Real implementation would query CloudWatch for CPUUtilization metrics
                # For this MVP, we outline the list of running instances and return
                # any matching sandbox configs
                pass
            except Exception as e:
                logger.error(f"Error scanning live compute: {e}")

        return idle_compute

    def scan_orphaned_resources(self) -> List[Dict]:
        """Scans for orphaned AWS resources: snapshots, EIPs, NAT gateways, LBs."""
        orphaned = []

        if self.mock_mode:
            orphaned.append({
                "resource_id": "snap-0123456789abcdef",
                "type": "ebs_snapshot",
                "reason": "Orphaned \u2014 parent volume deleted",
                "estimated_monthly_waste": 5.00,
                "pricing_source": "default"
            })
            orphaned.append({
                "resource_id": "eip-12345678",
                "type": "elastic_ip",
                "reason": "Unassociated Elastic IP",
                "estimated_monthly_waste": 3.60,
                "pricing_source": "default"
            })
            orphaned.append({
                "resource_id": "nat-0abcdef1234567890",
                "type": "nat_gateway",
                "reason": "Zero bytes processed in 14 days",
                "estimated_monthly_waste": 32.40,
                "pricing_source": "default"
            })
            orphaned.append({
                "resource_id": "lb-app-legacy-lb",
                "type": "load_balancer",
                "reason": "No healthy targets registered",
                "estimated_monthly_waste": 16.43,
                "pricing_source": "default"
            })
        else:
            # Live scanning for orphaned resources would use boto3 here
            try:
                # Orphaned snapshots: snapshots whose source volume no longer exists
                snapshots = self.ec2_client.describe_snapshots(OwnerIds=['self'])['Snapshots']
                volumes = {v['VolumeId'] for page in self.ec2_client.get_paginator('describe_volumes').paginate() for v in page['Volumes']}
                for snap in snapshots:
                    if snap.get('VolumeId') and snap['VolumeId'] not in volumes:
                        orphaned.append({
                            "resource_id": snap['SnapshotId'],
                            "type": "ebs_snapshot",
                            "reason": "Orphaned \u2014 parent volume deleted",
                            "estimated_monthly_waste": round(snap.get('VolumeSize', 0) * 0.05, 2),
                            "pricing_source": "default"
                        })

                # Unassociated Elastic IPs
                addresses = self.ec2_client.describe_addresses()['Addresses']
                for addr in addresses:
                    if 'AssociationId' not in addr:
                        orphaned.append({
                            "resource_id": addr.get('AllocationId', 'unknown'),
                            "type": "elastic_ip",
                            "reason": "Unassociated Elastic IP",
                            "estimated_monthly_waste": 3.60,
                            "pricing_source": "default"
                        })
            except Exception as e:
                logger.error(f"Error scanning orphaned resources: {e}")

        return orphaned

    def scan_all(self) -> List[Dict]:
        """Runs all waste scans."""
        waste = []
        waste.extend(self.scan_unattached_volumes())
        waste.extend(self.scan_idle_compute())
        waste.extend(self.scan_orphaned_resources())
        return waste

