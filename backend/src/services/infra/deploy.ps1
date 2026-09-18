# Sales Intelligence Platform - Unified Serverless Deployment Script
[CmdletBinding()]
param (
    [string]$Stack = "dev",
    [string]$AwsRegion = "ap-south-1"
)

$ErrorActionPreference = "Stop"
$env:PULUMI_SKIP_UPDATE_CHECK = "true"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Sales Intelligence Platform - Dedicated Microservices Deploy" -ForegroundColor Cyan
Write-Host " Stack: $Stack | Region: $AwsRegion" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Locate Workspace Roots
$infraDir = $PSScriptRoot
$backendDir = Resolve-Path (Join-Path $infraDir "..\..\..")
$rootDir = Resolve-Path (Join-Path $backendDir "..")
$frontendDir = Join-Path $rootDir "frontend"
$accountsDbFile = Join-Path $rootDir "accounts.db"

# Ensure Pulumi CLI is in PATH
$pulumiBin = "$env:USERPROFILE\.pulumi\bin"
if ((Test-Path $pulumiBin) -and ($env:PATH -notlike "*$pulumiBin*")) {
    $env:PATH = "$pulumiBin;$env:PATH"
}

# Load environment variables from backend/.env if present
$envFile = Join-Path $backendDir ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $name = $parts[0].Trim()
            $value = $parts[1].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

# 1. Setup Python Environment
Write-Host "`n[1/7] Verifying Python Dependencies..." -ForegroundColor Yellow
$venvDir = Join-Path $infraDir "venv"
if (-not (Test-Path $venvDir)) {
    python -m venv $venvDir
}
& (Join-Path $venvDir "Scripts\pip.exe") install -r (Join-Path $infraDir "requirements.txt") --quiet

# 2. Select or Initialize Pulumi Stack
Write-Host "`n[2/7] Configuring Pulumi Stack '$Stack'..." -ForegroundColor Yellow
if (-not $env:PULUMI_CONFIG_PASSPHRASE) {
    $env:PULUMI_CONFIG_PASSPHRASE = "b2b-sales-intel-secret"
}
if (-not $env:PULUMI_ACCESS_TOKEN) {
    & pulumi login --local
}

Push-Location $infraDir
try {
    & pulumi stack select $Stack --create
    & pulumi config set aws:region $AwsRegion
    if ($env:GEMINI_API_KEY) {
        & pulumi config set --secret geminiApiKey $env:GEMINI_API_KEY
    }
    if ($env:JWT_SECRET) {
        & pulumi config set --secret jwtSecret $env:JWT_SECRET
    }
} finally {
    Pop-Location
}

# 3. Build MkDocs Documentation
Write-Host "`n[3/7] Building MkDocs Technical Documentation..." -ForegroundColor Yellow
Push-Location $rootDir
try {
    python -m mkdocs build
} catch {
    Write-Host "Warning: MkDocs build skipped ($($_.Exception.Message))" -ForegroundColor DarkYellow
} finally {
    Pop-Location
}

# 4. Build and Push Dedicated Microservices Docker Images to AWS ECR
Write-Host "`n[4/7] Building & Pushing Dedicated Microservice Docker Images to AWS ECR..." -ForegroundColor Yellow
$awsAccountId = (aws sts get-caller-identity --query Account --output text).Trim()
$ecrBase = "$awsAccountId.dkr.ecr.$AwsRegion.amazonaws.com"

# Authenticate with AWS ECR
aws ecr get-login-password --region $AwsRegion | docker login --username AWS --password-stdin $ecrBase

$microservices = @(
    @{ Name = "gateway";   Dockerfile = "backend/Dockerfile" },
    @{ Name = "database";  Dockerfile = "backend/src/services/database/Dockerfile" },
    @{ Name = "accounts";  Dockerfile = "backend/src/services/accounts/Dockerfile" },
    @{ Name = "auth";      Dockerfile = "backend/src/services/auth/Dockerfile" },
    @{ Name = "scorer";    Dockerfile = "backend/src/services/scorer/Dockerfile" },
    @{ Name = "crawler";   Dockerfile = "backend/src/services/crawler/Dockerfile" },
    @{ Name = "eval";      Dockerfile = "backend/src/services/eval/Dockerfile" },
    @{ Name = "jobs";      Dockerfile = "backend/src/services/jobs/Dockerfile" }
)

Push-Location $rootDir
try {
    $env:BUILDX_NO_DEFAULT_ATTESTATIONS = "1"
    foreach ($svc in $microservices) {
        $repoName = "sales-intel-$Stack-$($svc.Name)"
        $imageUri = "$ecrBase/$repoName`:latest"

        Write-Host "  -> Ensuring ECR Repo: $repoName" -ForegroundColor Cyan
        try {
            aws ecr describe-repositories --repository-names $repoName --region $AwsRegion 2>$null | Out-Null
        } catch {
            aws ecr create-repository --repository-name $repoName --region $AwsRegion 2>$null | Out-Null
        }

        Write-Host "  -> Building and pushing: $($svc.Name) ($($svc.Dockerfile))" -ForegroundColor Cyan
        docker build --provenance=false -t $imageUri -f $svc.Dockerfile .
        docker push $imageUri
    }
} finally {
    Pop-Location
}

# 5. Run Pulumi Up
Write-Host "`n[5/7] Provisioning Cloud Infrastructure via Pulumi..." -ForegroundColor Yellow
Push-Location $infraDir
try {
    $origPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & pulumi cancel --yes 2>$null
    & pulumi refresh --yes --skip-preview
    & pulumi up --yes
    $lastCode = $LASTEXITCODE
    $ErrorActionPreference = $origPref
    if ($lastCode -ne 0) {
        throw "'pulumi up' execution failed."
    }

    $DatabaseBucket = (pulumi stack output database_bucket_name).Trim()
    $ApiGatewayUrl = (pulumi stack output api_gateway_url).Trim()
    $FrontendBucket = (pulumi stack output frontend_bucket_name).Trim()
    $FrontendUrl = (pulumi stack output frontend_website_url).Trim()
} finally {
    Pop-Location
}

# 6. Upload accounts.db to S3
Write-Host "`n[6/7] Uploading accounts.db Database to S3 Bucket..." -ForegroundColor Yellow
if (Test-Path $accountsDbFile) {
    Write-Host "Syncing $accountsDbFile -> s3://$DatabaseBucket/accounts.db" -ForegroundColor Cyan
    aws s3 cp $accountsDbFile "s3://$DatabaseBucket/accounts.db" --region $AwsRegion
}

# 7. Build and Deploy React Frontend & MkDocs Site
Write-Host "`n[7/7] Building & Deploying Frontend to S3..." -ForegroundColor Yellow
$env:VITE_API_URL = "$ApiGatewayUrl/api"

Push-Location $frontendDir
try {
    npm install
    npm run build
    aws s3 sync dist/ "s3://$FrontendBucket" --delete --region $AwsRegion
} finally {
    Pop-Location
}

# Build and Deploy MkDocs Site
try {
    Write-Host "Building MkDocs documentation site..." -ForegroundColor Cyan
    python -m mkdocs build
} catch {
    Write-Host "Warning: mkdocs build skipped or encountered an issue." -ForegroundColor Yellow
}

$siteDir = Join-Path $rootDir "site"
if (Test-Path $siteDir) {
    Write-Host "Deploying documentation to S3: s3://$FrontendBucket/documentation" -ForegroundColor Cyan
    aws s3 sync $siteDir "s3://$FrontendBucket/documentation" --region $AwsRegion
}

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host " DEDICATED MICROSERVICES DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host " API Gateway:     $ApiGatewayUrl" -ForegroundColor Green
Write-Host " Backend Health:  $ApiGatewayUrl/health" -ForegroundColor Green
Write-Host " Backend API:     $ApiGatewayUrl/api" -ForegroundColor Green
Write-Host " Database S3:     s3://$DatabaseBucket/accounts.db" -ForegroundColor Green
Write-Host " Frontend App:    $FrontendUrl" -ForegroundColor Green
Write-Host " Frontend Docs:   $FrontendUrl/documentation/" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
