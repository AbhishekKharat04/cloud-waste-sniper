# App Flow — Navigation & User Journey Map

## Pages List
- `/` (Home/Dashboard): Metrics, Charts, and Detected Waste Table
- `/price-intel`: Multi-cloud pricing comparisons (AWS, Azure, GCP)
- `/scan-history`: Audit trail of all previous AWS scans
- `/remediation-log`: Git-backed timeline of auto-remediated resources
- `/settings`: System configuration and API toggles

## Navigation Type
Left sidebar navigation with dynamic SPA (Single Page Application) view swapping. Top navbar for global actions (Run Scan, Download Report).

## Core User Journey 1: Waste Detection & Remediation
1. User lands on **Dashboard**. Sees empty state.
2. User clicks **"Run AWS Scan"**.
3. System scans infra, populates Dashboard metrics, charts, and findings table.
4. User locates an idle EC2 instance in the table and clicks **"Downsize"**.
5. System patches `main.tf`, commits via Git, opens a GitHub PR, and shows a success toast.
6. Dashboard re-renders dynamically with the resource removed.

## Core User Journey 2: Price Intelligence
1. User clicks **"Price Intelligence"** in the sidebar.
2. User clicks **"Fetch Prices"**.
3. System calls Bright Data SERP API, scrapes live competitor pricing.
4. User compares AWS costs against Azure/GCP and views the visual bar chart.

## Modals & Overlays
- **Welcome Onboarding**: Shown on first visit to explain the platform.
- **Resource Detail Modal**: Opened via "Review" button to explain *why* a resource is flagged and provide manual cleanup steps.
- **Command Palette (Ctrl+K)**: Quick navigation and actions overlay.
