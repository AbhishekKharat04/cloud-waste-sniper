# Cloud Waste Sniper - Product Requirements Document (PRD)

## App Name
Cloud Waste Sniper

## Tagline
Your AI-powered FinOps command center to detect cloud waste, compare multi-cloud pricing in real-time, and auto-remediate with Git-backed Infrastructure as Code patches.

## Problem
Organizations waste millions annually on idle, overprovisioned, and orphaned cloud resources. DevOps and FinOps teams struggle to identify these issues and bridge the gap between detection and remediation, often manually patching Terraform configurations. 

## Target User
DevOps Engineers, Cloud Architects, and FinOps Managers who need to reduce cloud spend quickly without breaking existing infrastructure.

## Core Features (Must Have)
- **Automated Scanning**: Detect unattached EBS volumes, idle EC2 instances, empty Load Balancers, etc.
- **Price Intelligence**: Real-time competitor pricing (AWS vs Azure vs GCP) via Bright Data SERP.
- **Auto-Remediation via GitOps**: Automatically modify `main.tf` and push Git commits/PRs instead of breaking infrastructure manually.
- **Dashboard & Analytics**: Real-time visualization of monthly waste and projected annual savings.
- **Audit Trails**: Complete historical logs of scans and remediations.

## Nice to Have (v2)
- Multi-cloud waste scanning (Azure, GCP natively)
- Slack/Teams integration for remediation approvals
- Advanced IAM role scanning for security waste

## Out of Scope (Current Version)
- Fully automated production apply (we only generate the PR, humans must approve and merge).
- Kubernetes pod-level metrics.

## User Stories
- As a **FinOps Manager**, I want to see a clear dashboard of wasted dollars so that I can report potential savings to the executive team.
- As a **DevOps Engineer**, I want the tool to automatically create a Terraform PR to remove waste so that I don't have to manually hunt through code.
- As a **Cloud Architect**, I want to compare instance pricing against Azure and GCP so that we can evaluate multi-cloud strategies.

## Success Metrics
- Average time from waste detection to PR creation < 5 seconds.
- Accurate identification of 100% of defined "idle" resources in the mock environment.
