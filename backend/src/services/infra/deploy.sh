#!/usr/bin/env bash
# Sales Intelligence Platform - Unified Serverless Deployment Script
set -euo pipefail

STACK="${1:-dev}"
AWS_REGION="${2:-ap-south-1}"

echo "============================================================"
echo " Sales Intelligence Platform - Dedicated Microservices Deploy"
echo " Stack: ${STACK} | Region: ${AWS_REGION}"
echo "============================================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
ROOT_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"
ACCOUNTS_DB="${ROOT_DIR}/accounts.db"

# Load backend/.env if present
if [ -f "${BACKEND_DIR}/.env" ]; then
    export $(grep -v '^#' "${BACKEND_DIR}/.env" | xargs)
fi

# 1. Python venv setup
echo -e "\n[1/7] Setting up Python dependencies..."
VENV_DIR="${SCRIPT_DIR}/venv"
if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi
"${VENV_DIR}/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt" -q

# 2. Select Pulumi stack
echo -e "\n[2/7] Configuring Pulumi stack '${STACK}'..."
export PULUMI_CONFIG_PASSPHRASE="${PULUMI_CONFIG_PASSPHRASE:-b2b-sales-intel-secret}"
if [ -z "${PULUMI_ACCESS_TOKEN:-}" ]; then
    pulumi login --local
fi

cd "${SCRIPT_DIR}"
pulumi stack select "${STACK}" --create
pulumi config set aws:region "${AWS_REGION}"
if [ -n "${GEMINI_API_KEY:-}" ]; then
    pulumi config set --secret geminiApiKey "${GEMINI_API_KEY}"
fi
if [ -n "${JWT_SECRET:-}" ]; then
    pulumi config set --secret jwtSecret "${JWT_SECRET}"
fi
if [ -n "${LOGFIRE_TOKEN:-}" ]; then
    pulumi config set --secret logfireToken "${LOGFIRE_TOKEN}"
fi

# 3. Build MkDocs
echo -e "\n[3/7] Building MkDocs Technical Documentation..."
cd "${ROOT_DIR}"
python3 -m mkdocs build || echo "Warning: MkDocs build skipped"

# 4. Build and Push Dedicated Docker Images
echo -e "\n[4/7] Building and Pushing Dedicated Microservice Docker Images to ECR..."
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text | tr -d '[:space:]')"
ECR_BASE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_BASE}"

SERVICES=(
    "gateway:backend/Dockerfile"
    "database:backend/src/services/database/Dockerfile"
    "accounts:backend/src/services/accounts/Dockerfile"
    "auth:backend/src/services/auth/Dockerfile"
    "scorer:backend/src/services/scorer/Dockerfile"
    "crawler:backend/src/services/crawler/Dockerfile"
    "eval:backend/src/services/eval/Dockerfile"
    "jobs:backend/src/services/jobs/Dockerfile"
)

cd "${ROOT_DIR}"
for entry in "${SERVICES[@]}"; do
    SVC_NAME="${entry%%:*}"
    DOCKERFILE="${entry##*:}"
    REPO_NAME="sales-intel-${STACK}-${SVC_NAME}"
    IMAGE_URI="${ECR_BASE}/${REPO_NAME}:latest"

    echo "  -> Ensuring ECR Repo: ${REPO_NAME}"
    aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1 || \
    aws ecr create-repository --repository-name "${REPO_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1

    echo "  -> Building and pushing: ${SVC_NAME} (${DOCKERFILE})"
    export BUILDX_NO_DEFAULT_ATTESTATIONS=1
    docker build --provenance=false -t "${IMAGE_URI}" -f "${DOCKERFILE}" .
    docker push "${IMAGE_URI}"
done

# 5. Pulumi Up
echo -e "\n[5/7] Deploying Cloud Infrastructure..."
cd "${SCRIPT_DIR}"
pulumi cancel --yes 2>/dev/null || true
pulumi refresh --yes --skip-preview 2>/dev/null || true
pulumi up --yes

DB_BUCKET="$(pulumi stack output database_bucket_name | tr -d '[:space:]')"
API_URL="$(pulumi stack output api_gateway_url | tr -d '[:space:]')"
FRONTEND_BUCKET="$(pulumi stack output frontend_bucket_name | tr -d '[:space:]')"
FRONTEND_URL="$(pulumi stack output frontend_website_url | tr -d '[:space:]')"

echo "  -> Refreshing Lambda functions to latest container images..."
for svc in "${SERVICES[@]}"; do
    fn_name="sales-intel-${STACK}-${svc}"
    img_uri="${ECR_BASE}/sales-intel-${STACK}-${svc}:latest"
    aws lambda update-function-code --function-name "${fn_name}" --image-uri "${img_uri}" --region "${AWS_REGION}" --output json >/dev/null 2>&1 || true
done

# 6. Upload DB
echo -e "\n[6/7] Uploading accounts.db to S3..."
if [ -f "${ACCOUNTS_DB}" ]; then
    aws s3 cp "${ACCOUNTS_DB}" "s3://${DB_BUCKET}/accounts.db" --region "${AWS_REGION}"
fi

# 7. Frontend deploy
echo -e "\n[7/7] Deploying Frontend to S3..."
export VITE_API_URL="${API_URL}/api"
cd "${FRONTEND_DIR}"
npm install
npm run build
aws s3 sync dist/ "s3://${FRONTEND_BUCKET}" --delete --region "${AWS_REGION}"

if [ -d "${ROOT_DIR}/site" ]; then
    aws s3 sync "${ROOT_DIR}/site" "s3://${FRONTEND_BUCKET}/documentation" --region "${AWS_REGION}"
fi

echo -e "\n============================================================"
echo " DEDICATED MICROSERVICES DEPLOYMENT COMPLETE!"
echo " API Gateway:     ${API_URL}"
echo " Backend Health:  ${API_URL}/health"
echo " Backend API:     ${API_URL}/api"
echo " Database S3:     s3://${DB_BUCKET}/accounts.db"
echo " Frontend App:    ${FRONTEND_URL}"
echo " Frontend Docs:   ${FRONTEND_URL}/documentation/"
echo "============================================================"
