# Dedicated Infrastructure Service (`src.services.infra`)

This service manages the complete Pulumi serverless cloud infrastructure for the **Sales Intelligence Platform**.

## Architecture Responsibilities

1. **Foundational Shared Resources (`shared.py`)**:
   - Amazon S3 Database Bucket (direct `accounts.db` hosting with SSE-S3 encryption).
   - Amazon ECR Repository for container images.
   - Amazon IAM Lambda Execution Role & S3 access policies.
   - Amazon API Gateway HTTP API (v2) with CORS and `$default` stage.
   - Common environment variable configuration.

2. **Microservices Deployment Orchestrator (`microservices.py`)**:
   - Automatically discovers and invokes each microservice's dedicated infrastructure provisioner (`src.services.<service>.infra.main`):
     - `database`
     - `accounts`
     - `auth`
     - `scorer`
     - `crawler`
     - `eval`
     - `jobs`
   - Unified Gateway Fallback Lambda (`/health` & `$default` routes).
   - Dedicated API Gateway integrations and invoke permissions.

3. **Frontend Infrastructure & Static Website (`frontend.py`)**:
   - Amazon S3 Static Website Hosting for React + Vite Frontend SPA and MkDocs interactive technical documentation.
   - S3 Bucket Public Access Block & Public Read Policy.
   - S3 CORS configuration.

## Quick Commands

### Deploy Everything (Infra + Docker + DB + Frontend)
From PowerShell:
```powershell
.\src\services\infra\deploy.ps1 -Stack dev -AwsRegion ap-south-1
```

From Bash:
```bash
./src/services/infra/deploy.sh dev ap-south-1
```

### Pulumi IaC Direct Execution
```bash
cd backend/src/services/infra
pulumi up
```
