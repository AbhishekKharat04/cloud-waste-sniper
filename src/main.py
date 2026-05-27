import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv

# Load env variables — resolve .env from project root (parent of src/)
_project_root = Path(__file__).resolve().parent.parent
_env_path = _project_root / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

from src.scraper import CloudWasteSniper
from src.mapper import StateMapper, TFModifier
from src.git_engine import GitPRCreator
from src.reporter import FinOpsReporter
from src.price_intel import CloudPricingIntelligence
from src.history import ScanHistory

app = FastAPI(title="Cloud Waste Sniper API")

# Global scan history singleton for audit trail
scan_history = ScanHistory()

# Ensure templates directory exists
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(templates_dir, exist_ok=True)
templates = Jinja2Templates(directory=templates_dir)

from typing import Optional

class RemediateRequest(BaseModel):
    resource_id: str
    remediation_type: str  # e.g., "count_zero" or "downsize_instance"
    new_value: Optional[str] = None  # e.g., "t3.medium"
    env: Optional[str] = "production"

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the simple UI dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/scan")
async def scan_waste(env: str = "production"):
    """Triggers the AWS read-only scan (or returns mocked data)."""
    sniper = CloudWasteSniper(env=env)
    try:
        waste = sniper.scan_all()
        pricing_engine = "Bright Data Real-Time Scraped Engine" if sniper.live_pricing else "Default Estimates"
        scan_history.record_scan(waste, pricing_engine)
        return {
            "status": "success", 
            "data": waste,
            "pricing_engine": pricing_engine
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/report")
async def download_report(env: str = "production"):
    """Runs a scan and returns a downloadable Markdown executive report."""
    sniper = CloudWasteSniper(env=env)
    try:
        waste = sniper.scan_all()
        reporter = FinOpsReporter(waste)
        markdown = reporter.generate()
        return PlainTextResponse(
            content=markdown,
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=FinOps_Executive_Report.md"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/remediate")
async def remediate_waste(req: RemediateRequest):
    """Handles the core FinOps workflow: Maps state -> Modifies TF -> Generates PR."""
    repo_path = os.getenv("REPO_PATH", ".")
    env = req.env if req.env else "production"
    state_path = os.path.join(repo_path, "mock_infra", env, "terraform.tfstate")
    tf_path = os.path.join(repo_path, "mock_infra", env, "main.tf")
    
    try:
        # 1. Map AWS ID to local Terraform type & name
        mapper = StateMapper(state_path)
        tf_resource = mapper.find_resource_by_id(req.resource_id)
        
        if not tf_resource:
            raise HTTPException(status_code=404, detail=f"Could not map {req.resource_id} in {state_path}")
            
        tf_type = tf_resource["tf_type"]
        tf_name = tf_resource["tf_name"]
        
        # 2. Modify the .tf file safely
        modifier = TFModifier(tf_path)
        status = modifier.apply_remediation(tf_type, tf_name, req.remediation_type, req.new_value)
        
        if status == "error":
            raise HTTPException(status_code=500, detail=f"Failed to modify {tf_path}")
        elif status == "skipped":
            # Idempotent skip - do NOT create a PR (since git commit would fail)
            scan_history.record_remediation(tf_type, tf_name, req.remediation_type, "skipped")
            return {
                "status": "success",
                "message": f"Resource {tf_type}.{tf_name} is already fully optimized. No further Git commit necessary."
            }
            
        # 3. Commit and generate PR (Only run on "modified")
        git_engine = GitPRCreator()
        pr_success = git_engine.create_remediation_pr(tf_type, tf_name, branch_name=f"finops/{env}/optimize-resources")
        
        if not pr_success:
            scan_history.record_remediation(tf_type, tf_name, req.remediation_type, "partial")
            return {"status": "partial_success", "message": f"Terraform modified for {tf_type}.{tf_name}. Local Git commit may need manual push."}
        
        scan_history.record_remediation(tf_type, tf_name, req.remediation_type, "success")
        
        # 4. Send Slack notification if webhook exists
        slack_webhook = os.getenv("SLACK_WEBHOOK_URL", "").strip()
        if slack_webhook:
            import requests
            try:
                requests.post(slack_webhook, json={"text": f"✅ *FinOps Action*: Successfully remediated `{tf_type}.{tf_name}` via Cloud Waste Sniper. PR has been generated."}, timeout=5)
            except Exception as e:
                print(f"Failed to send Slack notification: {e}")

        return {"status": "success", "message": f"✓ Remediated {tf_type}.{tf_name} — Terraform patched & committed to branch finops/optimize-resources"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/price-intel")
async def get_price_intel():
    """Returns multi-cloud competitive pricing comparison."""
    intel = CloudPricingIntelligence()
    try:
        comparison = intel.fetch_comparison()
        return {"status": "success", "data": comparison}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history")
async def get_history():
    """Returns scan history audit trail."""
    return {
        "status": "success",
        "scans": scan_history.get_scans(),
        "stats": scan_history.get_stats()
    }

@app.get("/api/remediation-log")
async def get_remediation_log():
    """Returns remediation activity log."""
    return {
        "status": "success",
        "remediations": scan_history.get_remediations()
    }

@app.get("/api/settings")
async def get_settings():
    """Returns current system configuration status (never expose secrets)."""
    return {
        "status": "success",
        "settings": {
            "mock_mode": os.getenv("MOCK_AWS", "false").lower() == "true",
            "live_pricing": os.getenv("USE_REAL_PRICING", "false").lower() == "true",
            "brightdata_connected": bool(os.getenv("BRIGHTDATA_API_KEY", "").strip()),
            "github_connected": bool(os.getenv("GITHUB_TOKEN", "").strip()),
            "slack_connected": bool(os.getenv("SLACK_WEBHOOK_URL", "").strip()),
            "aws_region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            "repo_path": os.getenv("REPO_PATH", ".")
        }
    }

@app.get("/api/user")
async def get_user_profile():
    """Returns dynamic user profile information."""
    return {
        "name": os.getenv("FINOPS_ADMIN_NAME", "FinOps Admin"),
        "role": os.getenv("FINOPS_ADMIN_ROLE", "System Administrator"),
        "initials": os.getenv("FINOPS_ADMIN_NAME", "FinOps Admin")[:2].upper()
    }
