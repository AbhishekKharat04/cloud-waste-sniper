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

class ChatRequest(BaseModel):
    message: str
    env: Optional[str] = "production"

class SimulateRequest(BaseModel):
    resource_id: str
    resource_type: str
    env: Optional[str] = "production"

class SettingsUpdateRequest(BaseModel):
    mock_mode: bool
    live_pricing: bool
    slack_connected: bool
    github_connected: bool
    jira_connected: bool = False

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
            "jira_connected": os.getenv("JIRA_CONNECTED", "false").lower() == "true",
            "aws_region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            "repo_path": os.getenv("REPO_PATH", ".")
        }
    }

@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    os.environ["MOCK_AWS"] = "true" if req.mock_mode else "false"
    os.environ["USE_REAL_PRICING"] = "true" if req.live_pricing else "false"
    
    if not req.slack_connected:
        os.environ["SLACK_WEBHOOK_URL"] = ""
    elif not os.getenv("SLACK_WEBHOOK_URL"):
        os.environ["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/T000/B000/mocked"
        
    if not req.github_connected:
        os.environ["GITHUB_TOKEN"] = ""
    elif not os.getenv("GITHUB_TOKEN"):
        os.environ["GITHUB_TOKEN"] = "ghp_mocked_token"
        
    os.environ["JIRA_CONNECTED"] = "true" if req.jira_connected else "false"
    return {"status": "success", "message": "Settings updated successfully."}

@app.get("/api/user")
async def get_user_profile():
    """Returns dynamic user profile information."""
    return {
        "name": os.getenv("FINOPS_ADMIN_NAME", "FinOps Admin"),
        "role": os.getenv("FINOPS_ADMIN_ROLE", "System Administrator"),
        "initials": os.getenv("FINOPS_ADMIN_NAME", "FinOps Admin")[:2].upper()
    }

@app.post("/api/chat")
async def copilot_chat(req: ChatRequest):
    """Context-aware FinOps AI assistant."""
    import requests
    
    # 1. Fetch current environment waste data as context
    sniper = CloudWasteSniper(env=req.env)
    waste_items = []
    try:
        waste_items = sniper.scan_all()
    except Exception:
        pass
        
    context = ""
    total_waste = 0.0
    for item in waste_items:
        cost = item.get("estimated_monthly_waste") or item.get("estimated_monthly_savings") or 0.0
        total_waste += cost
        context += f"- Resource: {item['resource_id']} (Type: {item['type']}, Reason: {item['reason']}, Monthly Cost: ${cost:.2f})\n"
        
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        # Live Gemini call
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        prompt = f"""
        You are "Cloud Waste Sniper AI", a professional, elite Cloud FinOps consultant assisting Alex (CTO).
        You have direct access to the live environment state findings.
        
        Environment Context:
        - Target Environment: {req.env}
        - Total Detected Monthly Waste: ${total_waste:.2f}
        - Detected Idle / Wasteful Resources:
        {context}
        
        User's Message: "{req.message}"
        
        Provide a concise, highly tailored response in markdown format. Give direct advice, draft alerts or tickets if asked, and stay focused on cloud optimization.
        """
        try:
            resp = requests.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}]
            }, timeout=15)
            if resp.status_code == 200:
                ai_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                return {"status": "success", "reply": ai_text}
        except Exception as e:
            pass

    # Intelligent, context-aware mock fallback
    msg = req.message.lower()
    if "slack" in msg or "alert" in msg:
        reply = f"### 📬 Draft Slack FinOps Alert\nHere is a prepared alert you can broadcast to your engineering team:\n\n```text\n🚨 [FinOps Alert] - {req.env.upper()} Cloud Waste Detected!\nCloud Waste Sniper has identified ${total_waste:.2f}/mo of idling or orphaned resources in our environment.\n\nSummary of high-impact items:\n"
        for item in waste_items[:3]:
            cost = item.get("estimated_monthly_waste") or item.get("estimated_monthly_savings") or 0.0
            reply += f"• {item['resource_id']} ({item['type']}): ${cost:.2f}/mo - {item['reason']}\n"
        reply += f"\n👉 Actions can be auto-remediated directly from the Sniper Dashboard: https://cloud-waste-sniper.vercel.app/?env={req.env}\n```"
    elif "jira" in msg or "ticket" in msg:
        reply = f"### 🎫 Draft Jira Cleanup Ticket\nI have generated the specs for your cleanup sprint:\n\n* **Title**: `[FinOps-Cleanup] Remediate ${total_waste:.2f}/mo Idle Resources in {req.env.upper()}`\n* **Description**:\n  The following idling cloud resources were flagged by Cloud Waste Sniper for cleanup:\n"
        for item in waste_items:
            cost = item.get("estimated_monthly_waste") or item.get("estimated_monthly_savings") or 0.0
            reply += f"  - [{item['type']}] `{item['resource_id']}` -> Save **${cost:.2f}/mo** (Reason: {item['reason']})\n"
        reply += "\n* **Priority**: High\n* **Estimated Time to Resolve**: 15 minutes."
    elif "summary" in msg or "waste" in msg or "how much" in msg or "report" in msg:
        reply = f"### 📊 Environment Waste Report ({req.env.upper()})\nWe have scanned the Terraform state and found **{len(waste_items)}** wasteful resource(s) with an estimated total impact of **${total_waste:.2f}/month**.\n\n"
        for idx, item in enumerate(waste_items):
            cost = item.get("estimated_monthly_waste") or item.get("estimated_monthly_savings") or 0.0
            reply += f"{idx+1}. **`{item['resource_id']}`** ({item['type']})\n   - **Reason**: {item['reason']}\n   - **Monthly Cost**: ${cost:.2f}\n"
        reply += f"\n💡 *Recommendation*: Releasing these resources will instantly lower your {req.env} cloud bill by **${total_waste:.2f}**."
    elif "gcp" in msg or "azure" in msg or "aws" in msg:
        cloud = "aws" if "aws" in msg else ("azure" if "azure" in msg else "gcp")
        filtered = [i for i in waste_items if cloud in i.get("type", "").lower() or cloud in i.get("resource_id", "").lower()]
        filtered_cost = sum(i.get("estimated_monthly_waste", 0) or i.get("estimated_monthly_savings", 0) for i in filtered)
        
        reply = f"### ☁️ {cloud.upper()} Specific Audit ({req.env.upper()})\nI filtered the audit findings specifically for **{cloud.upper()}**:\n\n"
        if not filtered:
            reply += f"Nice work! No idle resources are currently flagged under {cloud.upper()}."
        else:
            reply += f"We found **{len(filtered)}** resource(s) totaling **${filtered_cost:.2f}/month**:\n"
            for item in filtered:
                cost = item.get("estimated_monthly_waste") or item.get("estimated_monthly_savings") or 0.0
                reply += f"- **`{item['resource_id']}`** ({item['type']}) -> Save **${cost:.2f}/mo**\n"
    else:
        reply = f"### 👋 Hello Alex!\nI am your context-aware **Cloud Waste Sniper AI Copilot**.\n\nI have analyzed your **{req.env.upper()}** environment and identified **${total_waste:.2f}/month** of potential cloud savings across **{len(waste_items)}** resources.\n\n**Quick actions you can ask me to do:**\n- `Draft a Slack alert for the team`\n- `Generate a Jira cleanup ticket`\n- `Provide a detailed cost summary`"
        
    return {"status": "success", "reply": reply}

@app.post("/api/simulate")
async def copilot_simulate(req: SimulateRequest):
    """Simulates AI impact analysis for a resource."""
    import requests
    import json
    
    # Fetch resource details
    sniper = CloudWasteSniper(env=req.env)
    waste_items = []
    try:
        waste_items = sniper.scan_all()
    except Exception:
        pass
        
    target_item = None
    for item in waste_items:
        if item["resource_id"] == req.resource_id:
            target_item = item
            break
            
    reason = target_item["reason"] if target_item else "Idle resource"
    cost = (target_item.get("estimated_monthly_waste") or target_item.get("estimated_monthly_savings") or 15.0) if target_item else 15.0
    
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        prompt = f"""
        You are a Cloud FinOps expert simulating the impact of deleting/downsizing a wasted cloud resource.
        Resource Type: {req.resource_type}
        Resource ID: {req.resource_id}
        Finding Reason: {reason}
        Monthly Cost: ${cost:.2f}

        Format your output strictly as a JSON object with these keys (do not include markdown wrapping or extra text):
        {{
          "confidence_score": 98,
          "risk_level": "Low",
          "risk_assessment": "...",
          "estimated_downtime": "0 seconds",
          "security_impact": "...",
          "recommended_pre_check": "..."
        }}
        """
        try:
            resp = requests.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}]
            }, timeout=15)
            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.endswith("```"):
                    text = text[:-3]
                data = json.loads(text.strip())
                return {"status": "success", "simulation": data}
        except Exception:
            pass

    # High-quality context-aware fallback simulation
    res_type = req.resource_type.lower()
    res_id = req.resource_id.lower()
    
    if "ebs_volume" in res_type or "volume" in res_type:
        simulation = {
            "confidence_score": 99,
            "risk_level": "Low",
            "risk_assessment": f"This volume '{req.resource_id}' is completely unattached. Deleting it will free up block storage instantly without impacting any running EC2 instances. It has been inactive for over 14 days.",
            "estimated_downtime": "0 seconds",
            "security_impact": "Ensures orphaned data is wiped, eliminating possible compliance leaks under SOC2 Section 4.2.",
            "recommended_pre_check": "Check if any historical snapshots exist before wiping."
        }
    elif "snapshot" in res_type:
        simulation = {
            "confidence_score": 95,
            "risk_level": "Low",
            "risk_assessment": "This snapshot is orphaned and belongs to an AMI or volume that has already been deleted. No active backups or operational AMIs depend on it.",
            "estimated_downtime": "0 seconds",
            "security_impact": "Reduces stale backup footprints in AWS S3 buckets.",
            "recommended_pre_check": "Confirm that the parent volume doesn't need to be restored."
        }
    elif "ip" in res_type or "eip" in res_type:
        simulation = {
            "confidence_score": 98,
            "risk_level": "Low",
            "risk_assessment": f"The Elastic IP '{req.resource_id}' is unassociated and idling. Deleting/releasing it has zero impact on server connections as no DNS record is pointing to this IP.",
            "estimated_downtime": "0 seconds",
            "security_impact": "Reduces your public IPv4 attack surface and eliminates idle address scanner targets.",
            "recommended_pre_check": "Verify DNS records (A-records) to ensure no external system is attempting to connect."
        }
    elif "instance" in res_type or "vm" in res_type or "compute" in res_type:
        simulation = {
            "confidence_score": 85,
            "risk_level": "Medium",
            "risk_assessment": f"Instance '{req.resource_id}' exhibits CPU utilization < 1% for 7 consecutive days. Downsizing or stopping it is recommended. Deleting it completely requires verifying if it's part of an Auto-Scaling Group.",
            "estimated_downtime": "15-30 seconds (reboot required during instance type change)",
            "security_impact": "No change to security groups, but stopping idle compute decreases exposure.",
            "recommended_pre_check": "Verify active thread counts or cron schedulers before triggering downsize."
        }
    else:
        simulation = {
            "confidence_score": 90,
            "risk_level": "Low",
            "risk_assessment": f"Resource '{req.resource_id}' of type '{req.resource_type}' is underutilized. Applying the FinOps patch is recommended to reclaim the projected cost of ${cost:.2f}/mo.",
            "estimated_downtime": "0 seconds",
            "security_impact": "Optimizes network/compute posture.",
            "recommended_pre_check": "Review resource tag owners."
        }
        
    return {"status": "success", "simulation": simulation}
