# Implementation Plan — Step-by-Step Build Sequence

## Phase 1: Setup and Architecture
- Initialize Python FastAPI project and directory structure (`src/`, `mock_infra/`).
- Setup `requirements.txt` (`fastapi`, `uvicorn`, `jinja2`, `PyGithub`, `python-dotenv`).
- Define `.env` template.
- Build the `index.html` UI shell with CSS tokens, navigation, and layout.

## Phase 2: Mock Infrastructure
- Create `mock_infra/main.tf` to simulate typical cloud waste (unattached EBS, idle EC2, etc.).
- Generate a `terraform.tfstate` file to act as the queryable source of truth.

## Phase 3: Core Scanning Engine
- Implement `scraper.py` to parse `terraform.tfstate` or `main.tf` and identify waste patterns.
- Hook up API route `/api/scan` to return JSON results.
- Implement the UI dashboard to visualize waste metrics and charts.

## Phase 4: Price Intelligence
- Integrate Bright Data SERP API in `price_intel.py`.
- Build the comparison engine to fetch AWS, Azure, and GCP pricing for compute and storage.
- Hook up `/api/price-intel` and render the comparison view.

## Phase 5: Auto-Remediation (GitOps)
- Implement `mapper.py` to map AWS Resource IDs to Terraform logical names.
- Implement `TFModifier` to safely parse and patch `main.tf` (downsizing instances or setting count = 0).
- Implement `GitPRCreator` in `git_engine.py` using `PyGithub` to stage, commit, and create a PR.
- Hook up `/api/remediate` and test the full round-trip from UI click to GitHub PR.

## Phase 6: Polish and Audit Trails
- Implement `history.py` to keep an in-memory audit log of scans and remediations.
- Build "Scan History" and "Remediation Log" pages.
- Add "Executive Report" markdown generation and download feature.
- Final UI polish (animations, empty states, Command Palette).

## Phase 7: Verification
- Verify all API endpoints handle errors gracefully.
- Test the full GitOps flow with a valid GitHub token.
- Test real-time feedback loop (dashboard metrics updating immediately after remediation).
