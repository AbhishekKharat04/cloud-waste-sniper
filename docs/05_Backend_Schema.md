# Backend Schema — Data Model & Architecture

## Current State (In-Memory for MVP)
To ensure rapid iteration and zero-setup deployment for the hackathon, the backend uses an in-memory `ScanHistory` singleton object instead of a relational database.

### Scan History Model
- `id` (int): Auto-incrementing identifier.
- `timestamp` (ISO string): When the scan occurred.
- `resource_count` (int): Number of wasteful resources found.
- `total_waste` (float): Dollar amount of waste.
- `pricing_engine` (string): 'Bright Data' or 'Default'.
- `resources` (List of dicts): Snapshot of the resources.

### Remediation Log Model
- `id` (int): Auto-incrementing identifier.
- `timestamp` (ISO string): When the remediation occurred.
- `resource` (string): e.g., 'aws_instance.worker_node'.
- `action` (string): 'count_zero' or 'downsize_instance'.
- `status` (string): 'success', 'partial_success', or 'skipped'.
- `commit_hash` (string, optional): Git commit hash if available.

## Future State (PostgreSQL)
When transitioning to production, we will migrate to PostgreSQL with the following tables:

**Table: `scans`**
- `id` (uuid, PK)
- `account_id` (string, FK)
- `timestamp` (timestamp)
- `total_waste_usd` (decimal)

**Table: `resources`**
- `id` (uuid, PK)
- `scan_id` (uuid, FK)
- `resource_id` (string)
- `type` (string)
- `estimated_waste_usd` (decimal)
- `status` (string - 'active', 'remediated', 'acknowledged')

**Table: `remediations`**
- `id` (uuid, PK)
- `resource_id` (uuid, FK)
- `action_taken` (string)
- `pr_url` (string)
- `timestamp` (timestamp)
