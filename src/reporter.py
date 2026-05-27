"""FinOps Executive Report Generator.

Compiles scan results into a professionally formatted Markdown report
suitable for executive review, Slack sharing, or archival.
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict

logger = logging.getLogger(__name__)


class FinOpsReporter:
    """Generates executive-grade Markdown reports from cloud waste scan data."""

    _RESOURCE_TYPE_LABELS = {
        "ebs_volume": "EBS Volume (Unattached)",
        "ec2_instance": "EC2 Instance (Idle / Over-provisioned)",
        "ebs_snapshot": "EBS Snapshot (Orphaned)",
        "elastic_ip": "Elastic IP (Unassociated)",
        "nat_gateway": "NAT Gateway (Idle)",
        "load_balancer": "Load Balancer (No Targets)",
    }

    def __init__(self, waste_items: List[Dict]):
        """Initializes the reporter with a list of detected waste items.

        Args:
            waste_items: The list returned by AWSSniper.scan_all(). Each dict
                         must contain 'resource_id', 'type', 'reason', and
                         one of 'estimated_monthly_waste' or 'estimated_monthly_savings'.
        """
        self.waste_items = waste_items
        self.generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _monthly_cost(self, item: Dict) -> float:
        """Extracts the monthly cost figure from a waste item dict."""
        return item.get("estimated_monthly_waste") or item.get("estimated_monthly_savings") or 0.0

    def _total_monthly(self) -> float:
        return sum(self._monthly_cost(i) for i in self.waste_items)

    def _type_label(self, raw_type: str) -> str:
        return self._RESOURCE_TYPE_LABELS.get(raw_type, raw_type)

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _build_header(self) -> str:
        return (
            f"# 🎯 Cloud Waste Sniper — Executive Report\n\n"
            f"**Generated at:** `{self.generated_at}` | **Scanner Version:** `v1.2.0` | **Flagged Items:** `{len(self.waste_items)}`"
        )

    def _build_exec_summary(self) -> str:
        total_monthly = self._total_monthly()
        total_annual = total_monthly * 12

        # Build per-category breakdown dynamically
        categories = {}
        for item in self.waste_items:
            t = item['type']
            categories[t] = categories.get(t, 0) + self._monthly_cost(item)

        category_rows = []
        for raw_type, monthly in sorted(categories.items(), key=lambda x: -x[1]):
            label = self._type_label(raw_type)
            category_rows.append(
                f"| **{label}** | ${monthly:,.2f} | ${monthly * 12:,.2f} |"
            )
        rows_str = "\n".join(category_rows)

        return (
            f"## 📊 Executive Summary\n\n"
            f"This report provides an executive-level overview of detected cloud infrastructure waste and potential cost savings.\n\n"
            f"| Category | Monthly Impact | Annual Impact (Projected) |\n"
            f"| :--- | :--- | :--- |\n"
            f"{rows_str}\n"
            f"| **TOTAL CLOUD WASTE** | **${total_monthly:,.2f}** | **${total_annual:,.2f}** |"
        )

    def _build_findings_table(self) -> str:
        rows = []
        for index, item in enumerate(self.waste_items):
            cost = self._monthly_cost(item)
            source = item.get("pricing_source", "default").upper()
            rows.append(
                f"| {index + 1} | `{item['resource_id']}` | {self._type_label(item['type'])} | {item['reason']} | ${cost:,.2f} ({source}) |"
            )
        
        table_content = "\n".join(rows)
        return (
            f"## 🔍 Detailed Findings Table\n\n"
            f"| # | Resource ID | Resource Type | Finding / Reason | Est. Monthly Cost (Source) |\n"
            f"| :--- | :--- | :--- | :--- | :--- |\n"
            f"{table_content}"
        )

    def _build_remediation_plan(self) -> str:
        return (
            "## 🛠️ Remediation Action Plan\n\n"
            "Automated infrastructure-as-code patches have been staged via localized Git branches to minimize waste safely:\n"
            "1. **Unattached EBS Volumes:** Staged code modifications to set `count = 0` on matching resource blocks inside your Terraform configurations.\n"
            "2. **Over-provisioned EC2 Compute:** Staged instance downsizing (e.g. from `t3.2xlarge` to `t3.medium`) to cut active runtime cost while preserving essential performance capacity.\n"
            "3. **Orphaned EBS Snapshots:** Identified snapshots whose parent volumes no longer exist — candidates for deletion.\n"
            "4. **Unassociated Elastic IPs:** IPs incurring hourly charges without an attached resource — release immediately.\n"
            "5. **Idle NAT Gateways:** Gateways processing zero traffic — evaluate for decommission.\n"
            "6. **Empty Load Balancers:** ALBs with no healthy targets — remove or reconfigure target groups.\n\n"
            "*Note: Real-time remediations are safely isolated on the branch `finops/optimize-resources` and will not mutate live resources until reviewed, approved, and merged.*"
        )

    def _build_next_steps(self) -> str:
        return (
            "## ⏭️ Recommended Next Steps\n\n"
            "1. **Review Git PRs:** Go to the staged branches or pull requests in GitHub (or inspect the local branch `finops/optimize-resources`).\n"
            "2. **Run Terraform Plan:** Execute `terraform plan` on the staged configurations to verify proposed infrastructure reduction changes.\n"
            "3. **Merge and Apply:** Merge the approved branch into `main` and execute `terraform apply` to physically remove or resize resources.\n"
            "4. **Re-run scan:** Perform a subsequent scan in Cloud Waste Sniper to confirm savings have been realized."
        )

    # ------------------------------------------------------------------
    # Main Generator
    # ------------------------------------------------------------------

    def generate(self) -> str:
        """Assembles all report components into a unified Markdown document."""
        if not self.waste_items:
            return (
                f"# 🎯 Cloud Waste Sniper — Executive Report\n\n"
                f"**Generated at:** `{self.generated_at}` | **Scanner Version:** `v1.2.0` | **Status:** `Optimized`\n\n"
                f"## ✅ No Cloud Waste Detected!\n\n"
                f"All infrastructure resources are currently optimized. No unattached storage or idle compute blocks were found. Keep up the great work!"
            )

        return "\n\n".join([
            self._build_header(),
            self._build_exec_summary(),
            self._build_findings_table(),
            self._build_remediation_plan(),
            self._build_next_steps(),
        ])
