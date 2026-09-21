#!/usr/bin/env bash
# Sales Intelligence Platform - Unified Serverless Deployment Script
set -euo pipefail

STACK="dev"
AWS_REGION="ap-south-1"
SERVICE="all"
SKIP_INFRA=false
SKIP_DOCS=false
SKIP_FRONTEND=false
UPLOAD_DB=false

# Parse named arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --stack|-s)
            STACK="$2"
            shift 2
            ;;
        --region|-r)
            AWS_REGION="$2"
            shift 2
            ;;
        --service)
            SERVICE="$2"
            shift 2
            ;;
        --skip-infra)
            SKIP_INFRA=true
            shift
            ;;
        --skip-docs)
            SKIP_DOCS=true
            shift
            ;;
        --skip-frontend)
            SKIP_FRONTEND=true
            shift
            ;;
        --upload-db)
            UPLOAD_DB=true
            shift
            ;;
        *)
            # Positional fallback: stack [region] [service]
            if [ -z "${STACK_SET:-}" ]; then
                STACK="$1"
                STACK_SET=1
            elif [ -z "${REGION_SET:-}" ]; then
                AWS_REGION="$1"
                REGION_SET=1
            elif [ -z "${SERVICE_SET:-}" ]; then
                SERVICE="$1"
                SERVICE_SET=1
            fi
            shift
            ;;
    esac
done

echo "============================================================"
echo " Sales Intelligence Platform - Serverless Deploy"
echo " Stack: ${STACK} | Region: ${AWS_REGION} | Service: ${SERVICE}"
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

ALL_SERVICES=(
    "gateway:backend/Dockerfile"
    "database:backend/src/services/database/Dockerfile"
    "accounts:backend/src/services/accounts/Dockerfile"
    "auth:backend/src/services/auth/Dockerfile"
    "scorer:backend/src/services/scorer/Dockerfile"
    "crawler:backend/src/services/crawler/Dockerfile"
    "eval:backend/src/services/eval/Dockerfile"
    "jobs:backend/src/services/jobs/Dockerfile"
)

TARGET_SERVICES=()
if [ "${SERVICE}" == "all" ]; then
    TARGET_SERVICES=("${ALL_SERVICES[@]}")
elif [ "${SERVICE}" == "frontend" ] || [ "${SERVICE}" == "docs" ]; then
    TARGET_SERVICES=()
else
    for entry in "${ALL_SERVICES[@]}"; do
        if [[ "${entry%%:*}" == "${SERVICE}" ]]; then
            TARGET_SERVICES+=("${entry}")
        fi
    done
fi

AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text | tr -d '[:space:]')"
ECR_BASE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# --- FAST PATH: Dedicated Microservice Single Deploy ---
if [ "${SERVICE}" != "all" ] && [ "${SERVICE}" != "frontend" ] && [ "${SERVICE}" != "docs" ] && [ "${SKIP_INFRA}" = true ]; then
    echo -e "\n[Fast Path] Deploying dedicated microservice: ${SERVICE}..."
    aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_BASE}"
    
    entry="${TARGET_SERVICES[0]}"
    svc_name="${entry%%:*}"
    dockerfile="${entry##*:}"
    repo_name="sales-intel-${STACK}-${svc_name}"
    image_uri="${ECR_BASE}/${repo_name}:latest"

    cd "${ROOT_DIR}"
    export BUILDX_NO_DEFAULT_ATTESTATIONS=1
    echo "  -> Building and pushing: ${svc_name} (${dockerfile})"
    docker build --provenance=false -t "${image_uri}" -f "${dockerfile}" .
    docker push "${image_uri}"

    fn_name="sales-intel-${STACK}-${svc_name}"
    echo "  -> Updating Lambda function ${fn_name}..."
    aws lambda update-function-code --function-name "${fn_name}" --image-uri "${image_uri}" --region "${AWS_REGION}" --output json >/dev/null 2>&1

    echo -e "\n============================================================"
    echo " Fast-deploy complete for ${SERVICE}!"
    echo "============================================================"
    exit 0
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
if ([ "${SERVICE}" == "all" ] || [ "${SERVICE}" == "docs" ]) && [ "${SKIP_DOCS}" = false ]; then
    echo -e "\n[3/7] Building MkDocs Technical Documentation..."
    cd "${ROOT_DIR}"
    python3 -m mkdocs build || echo "Warning: MkDocs build skipped"
fi

# 4. Build and Push Selected Microservices Docker Images to ECR
if [ ${#TARGET_SERVICES[@]} -gt 0 ]; then
    echo -e "\n[4/7] Building and Pushing Target Microservice Docker Images to ECR..."
    aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_BASE}"

    cd "${ROOT_DIR}"
    for entry in "${TARGET_SERVICES[@]}"; do
        svc_name="${entry%%:*}"
        dockerfile="${entry##*:}"
        repo_name="sales-intel-${STACK}-${svc_name}"
        image_uri="${ECR_BASE}/${repo_name}:latest"

        echo "  -> Ensuring ECR Repo: ${repo_name}"
        aws ecr describe-repositories --repository-names "${repo_name}" --region "${AWS_REGION}" >/dev/null 2>&1 || \
        aws ecr create-repository --repository-name "${repo_name}" --region "${AWS_REGION}" >/dev/null 2>&1

        echo "  -> Building and pushing: ${svc_name} (${dockerfile})"
        export BUILDX_NO_DEFAULT_ATTESTATIONS=1
        docker build --provenance=false -t "${image_uri}" -f "${dockerfile}" .
        docker push "${image_uri}"
    done
fi

# 5. Pulumi Up
if [ "${SKIP_INFRA}" = false ]; then
    echo -e "\n[5/7] Deploying Cloud Infrastructure..."
    cd "${SCRIPT_DIR}"
    pulumi cancel --yes 2>/dev/null || true
    pulumi refresh --yes --skip-preview 2>/dev/null || true
    pulumi up --yes
fi

cd "${SCRIPT_DIR}"
DB_BUCKET="$(pulumi stack output database_bucket_name 2>/dev/null | tr -d '[:space:]' || true)"
API_URL="$(pulumi stack output api_gateway_url 2>/dev/null | tr -d '[:space:]' || true)"
FRONTEND_BUCKET="$(pulumi stack output frontend_bucket_name 2>/dev/null | tr -d '[:space:]' || true)"
FRONTEND_URL="$(pulumi stack output frontend_website_url 2>/dev/null | tr -d '[:space:]' || true)"

if [ ${#TARGET_SERVICES[@]} -gt 0 ]; then
    echo "  -> Refreshing Lambda functions to latest container images..."
    for entry in "${TARGET_SERVICES[@]}"; do
        svc_name="${entry%%:*}"
        fn_name="sales-intel-${STACK}-${svc_name}"
        img_uri="${ECR_BASE}/sales-intel-${STACK}-${svc_name}:latest"
        aws lambda update-function-code --function-name "${fn_name}" --image-uri "${img_uri}" --region "${AWS_REGION}" --output json >/dev/null 2>&1 || true
    done
fi

# 6. Upload DB (Only if missing or --upload-db is given)
if [ -n "${DB_BUCKET:-}" ]; then
    db_exists=false
    if aws s3api head-object --bucket "${DB_BUCKET}" --key "accounts.db" --region "${AWS_REGION}" >/dev/null 2>&1; then
        db_exists=true
    fi

    if [ "${UPLOAD_DB}" = true ] || [ "${db_exists}" = false ]; then
        echo -e "\n[6/7] Uploading accounts.db to S3 (Initial Seed / Explicit)..."
        if [ -f "${ACCOUNTS_DB}" ]; then
            aws s3 cp "${ACCOUNTS_DB}" "s3://${DB_BUCKET}/accounts.db" --region "${AWS_REGION}"
        fi
    else
        echo -e "\n[6/7] Preserving existing accounts.db in S3 (Pass --upload-db to overwrite)..."
    fi
fi

# 7. Frontend deploy
if ([ "${SERVICE}" == "all" ] || [ "${SERVICE}" == "frontend" ]) && [ "${SKIP_FRONTEND}" = false ] && [ -n "${FRONTEND_BUCKET:-}" ]; then
    echo -e "\n[7/7] Deploying Frontend to S3..."
    export VITE_API_URL="${API_URL}/api"
    cd "${FRONTEND_DIR}"
    npm install
    npm run build
    aws s3 sync dist/ "s3://${FRONTEND_BUCKET}" --delete --region "${AWS_REGION}"
fi

if ([ "${SERVICE}" == "all" ] || [ "${SERVICE}" == "docs" ]) && [ "${SKIP_DOCS}" = false ] && [ -n "${FRONTEND_BUCKET:-}" ]; then
    if [ -d "${ROOT_DIR}/site" ]; then
        echo "Deploying documentation to S3: s3://${FRONTEND_BUCKET}/documentation"
        aws s3 sync "${ROOT_DIR}/site" "s3://${FRONTEND_BUCKET}/documentation" --region "${AWS_REGION}"
    fi
fi

echo -e "\n============================================================"
echo " DEPLOYMENT COMPLETE! (Target: ${SERVICE})"
if [ -n "${API_URL:-}" ]; then
    echo " API Gateway:     ${API_URL}"
    echo " Backend Health:  ${API_URL}/health"
    echo " Backend API:     ${API_URL}/api"
fi
if [ -n "${DB_BUCKET:-}" ]; then
    echo " Database S3:     s3://${DB_BUCKET}/accounts.db"
fi
if [ -n "${FRONTEND_URL:-}" ]; then
    echo " Frontend App:    ${FRONTEND_URL}"
    echo " Frontend Docs:   ${FRONTEND_URL}/documentation/"
fi
echo "============================================================"
