"""In-memory scan history and audit trail."""
from datetime import datetime
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class ScanHistory:
    """Stores scan results in memory for audit trail."""
    
    _instance = None
    _scans: List[Dict] = []
    _remediations: List[Dict] = []
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._scans = []
            cls._remediations = []
        return cls._instance
    
    def record_scan(self, results: List[Dict], pricing_engine: str) -> Dict:
        total_waste = sum(
            r.get("estimated_monthly_waste", 0) + r.get("estimated_monthly_savings", 0)
            for r in results
        )
        entry = {
            "id": len(self._scans) + 1,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "resource_count": len(results),
            "total_waste": round(total_waste, 2),
            "pricing_engine": pricing_engine,
            "resources": results,
        }
        self._scans.append(entry)
        logger.info(f"[History] Scan #{entry['id']} recorded: {len(results)} resources, ${total_waste:.2f} waste")
        return entry
    
    def record_remediation(self, resource_type: str, resource_name: str, action: str, status: str, commit_hash: str = None) -> Dict:
        entry = {
            "id": len(self._remediations) + 1,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "resource": f"{resource_type}.{resource_name}",
            "action": action,
            "status": status,
            "commit_hash": commit_hash,
        }
        self._remediations.append(entry)
        return entry
    
    def get_scans(self) -> List[Dict]:
        return list(reversed(self._scans))
    
    def get_remediations(self) -> List[Dict]:
        return list(reversed(self._remediations))
    
    def get_stats(self) -> Dict:
        total_scans = len(self._scans)
        total_remediations = len(self._remediations)
        total_waste_found = sum(s["total_waste"] for s in self._scans)
        return {
            "total_scans": total_scans,
            "total_remediations": total_remediations,
            "total_waste_found": round(total_waste_found, 2),
        }
