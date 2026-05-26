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
        return (
            f"## 📊 Executive Summary\n\n"
            f"This report provides an executive-level overview of detected cloud infrastructure waste and potential cost savings.\n\n"
            f"| Metric | Monthly Impact | Annual Impact (Projected) |\n"
            f"| :--- | :--- | :--- |\n"
            f"| **Total Stale Storage Waste** | ${sum(self._monthly_cost(i) for i in self.waste_items if i['type'] == 'ebs_volume'):,.2f} | ${sum(self._monthly_cost(i) for i in self.waste_items if i['type'] == 'ebs_volume') * 12:,.2f} |\n"
            f"| **Total Idle Compute Waste**  | ${sum(self._monthly_cost(i) for i in self.waste_items if i['type'] == 'ec2_instance'):,.2f} | ${sum(self._monthly_cost(i) for i in self.waste_items if i['type'] == 'ec2_instance') * 12:,.2f} |\n"
            f"| **Total Cloud Waste Saved**   | **${total_monthly:,.2f}** | **${total_annual:,.2f}** |"
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
            "2. **Over-provisioned EC2 Compute:** Staged instance downsizing (e.g. from `t3.2xlarge` to `t3.medium`) to cut active runtime cost while preserving essential performance capacity.\n\n"
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
