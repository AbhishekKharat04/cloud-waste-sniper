import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv

# Load env variables before importing modules
load_dotenv()

from src.scraper import AWSSniper
from src.mapper import StateMapper, TFModifier
from src.git_engine import GitPRCreator

app = FastAPI(title="Cloud Waste Sniper API")

# Ensure templates directory exists
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(templates_dir, exist_ok=True)
templates = Jinja2Templates(directory=templates_dir)

from typing import Optional

class RemediateRequest(BaseModel):
    resource_id: str
    remediation_type: str  # e.g., "count_zero" or "downsize_instance"
    new_value: Optional[str] = None  # e.g., "t3.medium"

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the simple UI dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/scan")
async def scan_waste():
    """Triggers the AWS read-only scan (or returns mocked data)."""
    sniper = AWSSniper()
    try:
        waste = sniper.scan_all()
        return {"status": "success", "data": waste}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/remediate")
async def remediate_waste(req: RemediateRequest):
    """Handles the core FinOps workflow: Maps state -> Modifies TF -> Generates PR."""
    repo_path = os.getenv("REPO_PATH", ".")
    state_path = os.path.join(repo_path, "mock_infra", "terraform.tfstate")
    tf_path = os.path.join(repo_path, "mock_infra", "main.tf")
    
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
        success = modifier.apply_remediation(tf_type, tf_name, req.remediation_type, req.new_value)
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to modify {tf_path}")
            
        # 3. Commit and generate PR
        git_engine = GitPRCreator()
        pr_success = git_engine.create_remediation_pr(tf_type, tf_name)
        
        if not pr_success:
            return {"status": "partial_success", "message": "File modified, but Git PR generation failed."}
            
        return {"status": "success", "message": f"Successfully processed {tf_type}.{tf_name} and committed/PR'd changes."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
