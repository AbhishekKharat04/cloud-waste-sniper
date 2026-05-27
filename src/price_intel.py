"""Multi-Cloud Competitive Pricing Intelligence via Bright Data.

Scrapes real-time compute and storage pricing from AWS, Azure, and GCP
using Bright Data's SERP API, enabling side-by-side cost comparisons.
"""
import os
import re
import logging
import requests
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Fallback pricing data (realistic as of 2024)
_FALLBACK_PRICING = {
    "compute": {
        "aws": {"instance": "t3.2xlarge", "vcpus": 8, "ram_gb": 32, "hourly": 0.3328, "monthly": 239.62, "currency": "USD"},
        "azure": {"instance": "Standard_D8s_v5", "vcpus": 8, "ram_gb": 32, "hourly": 0.384, "monthly": 276.48, "currency": "USD"},
        "gcp": {"instance": "n2-standard-8", "vcpus": 8, "ram_gb": 32, "hourly": 0.3886, "monthly": 279.79, "currency": "USD"}
    },
    "storage": {
        "aws": {"type": "gp3 SSD", "price_per_gb": 0.08, "currency": "USD"},
        "azure": {"type": "Premium SSD v2", "price_per_gb": 0.095, "currency": "USD"},
        "gcp": {"type": "pd-ssd", "price_per_gb": 0.085, "currency": "USD"}
    },
    "database": {
        "aws": {"type": "RDS PostgreSQL (db.m5.large)", "hourly": 0.276, "monthly": 198.72, "currency": "USD"},
        "azure": {"type": "Azure DB for PostgreSQL (2 vCore)", "hourly": 0.258, "monthly": 185.76, "currency": "USD"},
        "gcp": {"type": "Cloud SQL PostgreSQL (db-custom-2-8192)", "hourly": 0.228, "monthly": 164.16, "currency": "USD"}
    }
}

class CloudPricingIntelligence:
    """Fetches and compares cloud pricing across AWS, Azure, and GCP."""
    
    _SERP_API_URL = "https://api.brightdata.com/serp/req"
    
    def __init__(self):
        self.api_key = os.getenv("BRIGHTDATA_API_KEY", "").strip()
        self.use_live = os.getenv("USE_REAL_PRICING", "false").lower() == "true"
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            })
    
    def _serp_query(self, query: str) -> Optional[dict]:
        if not self.api_key:
            return None
        try:
            resp = self.session.post(self._SERP_API_URL, json={
                "query": query, "search_engine": "google",
                "country": "us", "language": "en"
            }, timeout=25)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"[PriceIntel] SERP query failed: {e}")
            return None
    
    def _extract_price_from_serp(self, serp_data: dict, min_val: float = 0.01, max_val: float = 10.0) -> Optional[float]:
        if not serp_data:
            return None
        for result in serp_data.get("organic", []):
            text = result.get("snippet", "") + " " + result.get("description", "")
            matches = re.findall(r'\$(\d+(?:\.\d+)?)', text)
            for m in matches:
                val = float(m)
                if min_val <= val <= max_val:
                    return val
        return None

    def fetch_comparison(self) -> Dict:
        """Returns multi-cloud pricing comparison data."""
        source = "fallback"
        data = {
            "compute": dict(_FALLBACK_PRICING["compute"]),
            "storage": dict(_FALLBACK_PRICING["storage"]),
            "database": dict(_FALLBACK_PRICING["database"]),
        }
        
        if self.use_live and self.api_key:
            logger.info("[PriceIntel] Attempting live pricing via Bright Data SERP...")
            # Try to fetch live AWS compute pricing
            aws_compute = self._serp_query("AWS EC2 t3.2xlarge on-demand price per hour us-east-1")
            price = self._extract_price_from_serp(aws_compute, 0.10, 2.00)
            if price:
                data["compute"]["aws"]["hourly"] = price
                data["compute"]["aws"]["monthly"] = round(price * 24 * 30, 2)
                source = "brightdata"
            
            # Try Azure
            azure_compute = self._serp_query("Azure Standard D8s v5 on-demand price per hour")
            price = self._extract_price_from_serp(azure_compute, 0.10, 2.00)
            if price:
                data["compute"]["azure"]["hourly"] = price
                data["compute"]["azure"]["monthly"] = round(price * 24 * 30, 2)
                source = "brightdata"
            
            # Try GCP
            gcp_compute = self._serp_query("GCP n2-standard-8 on-demand price per hour")
            price = self._extract_price_from_serp(gcp_compute, 0.10, 2.00)
            if price:
                data["compute"]["gcp"]["hourly"] = price
                data["compute"]["gcp"]["monthly"] = round(price * 24 * 30, 2)
                source = "brightdata"
            
            # Try storage prices
            aws_storage = self._serp_query("AWS EBS gp3 price per GB month us-east-1")
            price = self._extract_price_from_serp(aws_storage, 0.01, 1.00)
            if price:
                data["storage"]["aws"]["price_per_gb"] = price
                source = "brightdata"
            
            # Try database prices
            aws_db = self._serp_query("AWS RDS PostgreSQL db.m5.large on-demand price per hour us-east-1")
            price = self._extract_price_from_serp(aws_db, 0.05, 3.00)
            if price:
                data["database"]["aws"]["hourly"] = price
                data["database"]["aws"]["monthly"] = round(price * 24 * 30, 2)
                source = "brightdata"

            azure_db = self._serp_query("Azure Database for PostgreSQL Flexible Server 2 vCore price per hour")
            price = self._extract_price_from_serp(azure_db, 0.05, 3.00)
            if price:
                data["database"]["azure"]["hourly"] = price
                data["database"]["azure"]["monthly"] = round(price * 24 * 30, 2)
                source = "brightdata"

            gcp_db = self._serp_query("GCP Cloud SQL PostgreSQL 2 vCPU 8GB RAM price per hour")
            price = self._extract_price_from_serp(gcp_db, 0.05, 3.00)
            if price:
                data["database"]["gcp"]["hourly"] = price
                data["database"]["gcp"]["monthly"] = round(price * 24 * 30, 2)
                source = "brightdata"
            
            if source == "fallback":
                logger.warning("[PriceIntel] All live queries failed. Using fallback data.")
        
        return {
            "source": source,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "compute": data["compute"],
            "storage": data["storage"],
            "database": data["database"],
            "cheapest_compute": min(data["compute"].items(), key=lambda x: x[1]["monthly"])[0],
            "cheapest_storage": min(data["storage"].items(), key=lambda x: x[1]["price_per_gb"])[0],
            "cheapest_database": min(data["database"].items(), key=lambda x: x[1]["monthly"])[0],
        }
