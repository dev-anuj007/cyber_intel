# Infrastructure & Deployment Service (`src.services.infra`)

This package manages the Infrastructure as Code (IaC) and serverless deployment orchestration for the Sales Intelligence Platform using **Pulumi** and **AWS**.

---

## Architecture Overview

The deployed infrastructure provisions a highly scalable, serverless microservices architecture on AWS:

- **API Gateway (HTTP API v2)**: Centralized routing for microservice APIs and CORS management.
- **AWS Lambda (Container Images)**: Independent microservice handlers (`gateway`, `accounts`, `auth`, `database`, `scorer`, `crawler`, `eval`, `jobs`, `prompts`).
- **Amazon ECR**: Container registries for each microservice image.
- **Amazon S3**:
  - Encrypted database bucket for artifacts, crawler dumps, and backups.
  - Public static website hosting for the React + Vite frontend.
- **Pulumi Python IaC**: Orchestrated via `src.services.infra.infra_service`.

---

## Prerequisites

Before deploying, ensure you have the following installed and configured:

1. **AWS CLI** (v2.x) configured with administrative credentials:
   ```bash
   aws configure
   ```
2. **Pulumi CLI** (v3.x+):
   ```bash
   # Windows (via winget or choco)
   winget install Pulumi.Pulumi
   # macOS / Linux
   curl -fsSL https://get.pulumi.com | sh
   ```
3. **Docker Desktop / Docker Engine** running (for container image builds).
4. **Node.js (18+) & npm** (for frontend builds).
5. **Python 3.10+** with backend virtual environment active.

---

## Configuration & Secrets

Navigate to the infrastructure directory:
```bash
cd backend/src/services/infra
```

### Initialize or Select Stack
```bash
pulumi stack select dev --create
```

### Set Stack Configurations
```bash
# AWS Region
pulumi config set aws:region ap-south-1

# Application metadata
pulumi config set sales-intel-infra:appName sales-intel
pulumi config set sales-intel-infra:environment dev
pulumi config set sales-intel-infra:geminiModel gemini-3.1-flash-lite

# Sensitive Secrets (encrypted in Pulumi state)
pulumi config set --secret sales-intel-infra:geminiApiKey "YOUR_GEMINI_API_KEY"
pulumi config set --secret sales-intel-infra:jwtSecret "YOUR_JWT_SECRET"
pulumi config set --secret sales-intel-infra:logfireToken "YOUR_LOGFIRE_TOKEN"
pulumi config set --secret sales-intel-infra:dbPassword "YOUR_DB_PASSWORD"
```

---

## Deployment Workflows

### Option 1: Automated Script (Recommended)

The included deployment scripts automate the entire pipeline: authenticating ECR, building container images, running Pulumi provisioning, and syncing frontend static assets.

#### **Windows (PowerShell)**
```powershell
cd backend/src/services/infra

# Full deployment (Infrastructure + Containers + Frontend)
.\deploy.ps1 -Stack dev -AwsRegion ap-south-1

# Deploy only a specific microservice
.\deploy.ps1 -Service accounts -Stack dev

# Deploy only frontend
.\deploy.ps1 -Service frontend -Stack dev

# Skip infrastructure provisioning (deploy images only)
.\deploy.ps1 -SkipInfra
```

#### **macOS / Linux (Bash)**
```bash
cd backend/src/services/infra
chmod +x deploy.sh

# Full deployment
./deploy.sh --stack dev --region ap-south-1

# Deploy a specific microservice
./deploy.sh --service accounts --stack dev

# Skip frontend build
./deploy.sh --skip-frontend
```

---

### Option 2: Manual Step-by-Step Deployment

#### Step 1: Install Python Dependencies
```bash
cd backend
pip install -r requirements.txt
pip install -r src/services/infra/requirements.txt
```

#### Step 2: Authenticate Docker with ECR
```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
AWS_REGION="ap-south-1"

aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
```

#### Step 3: Build and Push Docker Images
Build the container images for your target services (e.g. gateway, accounts, etc.):
```bash
# Gateway / Backend API image
docker build -t "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/sales-intel-dev-gateway:latest" \
  -f backend/Dockerfile .
docker push "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/sales-intel-dev-gateway:latest"
```

#### Step 4: Preview & Apply Infrastructure with Pulumi
```bash
cd backend/src/services/infra

# Preview changes
pulumi preview

# Apply changes
pulumi up --yes
```

#### Step 5: Build and Upload Frontend Static Assets
```bash
cd frontend
npm install

# Inject API Gateway URL into Vite environment
FRONTEND_BUCKET=$(pulumi stack output frontend_bucket_name --cwd ../backend/src/services/infra)
VITE_API_URL=$(pulumi stack output backend_api_url --cwd ../backend/src/services/infra)

export VITE_API_URL=$VITE_API_URL
npm run build

# Sync build to S3
aws s3 sync dist/ "s3://$FRONTEND_BUCKET" --delete
```

---

## Verifying Deployment

Once deployed, review the exported endpoints:
```bash
pulumi stack output
```

Key outputs:
- **`api_gateway_url`**: Root API Gateway endpoint
- **`backend_api_url`**: Backend REST API base (`/api`)
- **`backend_health_url`**: Health check probe (`/health`)
- **`frontend_website_url`**: Public S3 website hosting URL
- **`database_url`**: Connection string for the PostgreSQL instance

### Health Check Verification
```bash
curl $(pulumi stack output backend_health_url)
# Response: {"status":"healthy","service":"sales-intel-gateway"}
```

---

## Teardown & Destruction

To destroy all cloud resources and avoid ongoing AWS charges:
```bash
cd backend/src/services/infra
pulumi destroy --yes
```
