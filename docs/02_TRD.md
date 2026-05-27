# Technical Requirements Document (TRD)

## Frontend
- **Framework**: Vanilla JS, HTML5, CSS3 (No build step required for rapid iteration)
- **Styling**: Custom CSS tokens with variables for easy theming (Dark mode first)
- **Icons**: Google Material Icons (Round)
- **Charts**: Chart.js (CDN) for Dashboard analytics

## Backend
- **Framework**: FastAPI (Python 3.9+)
- **Templating**: Jinja2 for rendering the SPA view container
- **Server**: Uvicorn

## Database
- **Current**: In-memory SQLite / Python Dicts (Mocking state for rapid MVP)
- **Future State**: PostgreSQL for persistent FinOps state and RBAC

## Integrations & APIs
- **AWS**: `boto3` for infrastructure scanning (mocked locally for the hackathon).
- **Price Intelligence**: Bright Data SERP API for real-time multi-cloud price scraping.
- **GitOps**: `PyGithub` to auto-generate PRs based on Terraform modifications.
- **IaC**: Local `mock_infra/main.tf` for simulated remediation.

## Environment Variables
- `MOCK_AWS` (bool)
- `BRIGHTDATA_API_KEY` (string)
- `USE_REAL_PRICING` (bool)
- `GITHUB_TOKEN` (string)
- `REPO_PATH` (string)
- `REPO_NAME` (string)
- `AWS_REGION` (string)
