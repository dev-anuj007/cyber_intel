# Sales Intelligence Platform - Unified Serverless Deployment Script
[CmdletBinding()]
param (
    [string]$Stack = "dev",
    [string]$AwsRegion = "ap-south-1",
    [ValidateSet("all", "gateway", "database", "accounts", "auth", "scorer", "crawler", "eval", "jobs", "frontend", "docs")]
    [string]$Service = "all",
    [switch]$SkipInfra,
    [switch]$SkipDocs,
    [switch]$SkipFrontend,
    [switch]$UploadDb
)

$ErrorActionPreference = "Stop"
$env:PULUMI_SKIP_UPDATE_CHECK = "true"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Sales Intelligence Platform - Serverless Deploy" -ForegroundColor Cyan
Write-Host " Stack: $Stack | Region: $AwsRegion | Target Service: $Service" -ForegroundColor Cyan
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

# Microservices Map
$allMicroservices = @(
    @{ Name = "gateway";   Dockerfile = "backend/Dockerfile" },
    @{ Name = "database";  Dockerfile = "backend/src/services/database/Dockerfile" },
    @{ Name = "accounts";  Dockerfile = "backend/src/services/accounts/Dockerfile" },
    @{ Name = "auth";      Dockerfile = "backend/src/services/auth/Dockerfile" },
    @{ Name = "scorer";    Dockerfile = "backend/src/services/scorer/Dockerfile" },
    @{ Name = "crawler";   Dockerfile = "backend/src/services/crawler/Dockerfile" },
    @{ Name = "eval";      Dockerfile = "backend/src/services/eval/Dockerfile" },
    @{ Name = "jobs";      Dockerfile = "backend/src/services/jobs/Dockerfile" }
)

# Determine services to build/push
if ($Service -eq "all") {
    $targetMicroservices = $allMicroservices
} elseif ($Service -in @("frontend", "docs")) {
    $targetMicroservices = @()
} else {
    $targetMicroservices = @($allMicroservices | Where-Object { $_["Name"] -eq $Service -or $_.Name -eq $Service })
}

$awsAccountId = (aws sts get-caller-identity --query Account --output text).Trim()
$ecrBase = "$awsAccountId.dkr.ecr.$AwsRegion.amazonaws.com"

# --- FAST PATH: Dedicated Microservice Single Deploy ---
if ($Service -ne "all" -and $Service -notin @("frontend", "docs") -and $SkipInfra) {
    Write-Host "`n[Fast Path] Deploying dedicated microservice: $Service..." -ForegroundColor Yellow
    
    # 1. Authenticate with ECR
    aws ecr get-login-password --region $AwsRegion | docker login --username AWS --password-stdin $ecrBase
    
    # 2. Build & Push Target Service
    $svc = $targetMicroservices[0]
    $svcName = if ($svc.Name) { $svc.Name } else { $svc["Name"] }
    $svcDocker = if ($svc.Dockerfile) { $svc.Dockerfile } else { $svc["Dockerfile"] }
    $repoName = "sales-intel-$Stack-$svcName"
    $imageUri = "$ecrBase/$repoName`:latest"

    Push-Location $rootDir
    try {
        $env:BUILDX_NO_DEFAULT_ATTESTATIONS = "1"
        Write-Host "  -> Building and pushing: $svcName ($svcDocker)" -ForegroundColor Cyan
        docker build --provenance=false -t $imageUri -f $svcDocker .
        docker push $imageUri
    } finally {
        Pop-Location
    }

    # 3. Direct Lambda Code Update
    $fnName = "sales-intel-$Stack-$svcName"
    Write-Host "  -> Updating Lambda function $fnName..." -ForegroundColor Cyan
    aws lambda update-function-code --function-name $fnName --image-uri $imageUri --region $AwsRegion --output json | Out-Null
    
    Write-Host "`n============================================================" -ForegroundColor Cyan
    Write-Host " Fast-deploy complete for $Service!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Cyan
    return
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
    if ($env:LOGFIRE_TOKEN) {
        & pulumi config set --secret logfireToken $env:LOGFIRE_TOKEN
    }
} finally {
    Pop-Location
}

# 3. Build MkDocs Documentation (if needed)
if ($Service -in @("all", "docs") -and -not $SkipDocs) {
    Write-Host "`n[3/7] Building MkDocs Technical Documentation..." -ForegroundColor Yellow
    Push-Location $rootDir
    try {
        python -m mkdocs build
    } catch {
        Write-Host "Warning: MkDocs build skipped ($($_.Exception.Message))" -ForegroundColor DarkYellow
    } finally {
        Pop-Location
    }
}

# 4. Build and Push Selected Microservices Docker Images to AWS ECR
if ($targetMicroservices.Count -gt 0) {
    Write-Host "`n[4/7] Building & Pushing Selected Microservice Images to AWS ECR..." -ForegroundColor Yellow
    aws ecr get-login-password --region $AwsRegion | docker login --username AWS --password-stdin $ecrBase

    Push-Location $rootDir
    try {
        $env:BUILDX_NO_DEFAULT_ATTESTATIONS = "1"
        foreach ($svc in $targetMicroservices) {
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
}

# 5. Run Pulumi Up (if not skipped)
if (-not $SkipInfra) {
    Write-Host "`n[5/7] Provisioning Cloud Infrastructure via Pulumi..." -ForegroundColor Yellow
    Push-Location $infraDir
    try {
        $origPref = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & pulumi cancel --yes 2>$null
        & pulumi refresh --yes --skip-preview --clear-pending-creates
        & pulumi refresh --yes --skip-preview
        & pulumi up --yes
        $lastCode = $LASTEXITCODE
        $ErrorActionPreference = $origPref
        if ($lastCode -ne 0) {
            throw "'pulumi up' execution failed."
        }
    } finally {
        Pop-Location
    }
}

# Retrieve stack outputs
Push-Location $infraDir
try {
    $DatabaseBucket = (pulumi stack output database_bucket_name 2>$null | Out-String).Trim()
    $ApiGatewayUrl = (pulumi stack output api_gateway_url 2>$null | Out-String).Trim()
    $FrontendBucket = (pulumi stack output frontend_bucket_name 2>$null | Out-String).Trim()
    $FrontendUrl = (pulumi stack output frontend_website_url 2>$null | Out-String).Trim()
} finally {
    Pop-Location
}

# Update Lambda function code if target microservices were pushed
if ($targetMicroservices.Count -gt 0) {
    Write-Host "`n  -> Refreshing Lambda functions to use latest container images..." -ForegroundColor Cyan
    foreach ($svc in $targetMicroservices) {
        $fnName = "sales-intel-$Stack-$($svc.Name)"
        $imgUri = "$ecrBase/sales-intel-$Stack-$($svc.Name):latest"
        try {
            aws lambda update-function-code --function-name $fnName --image-uri $imgUri --region $AwsRegion --output json 2>$null | Out-Null
        } catch {
            Write-Host "    (Warning: Could not update $fnName code: $($_.Exception.Message))" -ForegroundColor DarkYellow
        }
    }
}

# 6. Upload accounts.db to S3 (Only if missing in S3 OR explicitly requested via -UploadDb)
if ($DatabaseBucket) {
    $dbExistsInS3 = $false
    try {
        aws s3api head-object --bucket $DatabaseBucket --key "accounts.db" --region $AwsRegion 2>$null | Out-Null
        $dbExistsInS3 = $true
    } catch {
        $dbExistsInS3 = $false
    }

    if ($UploadDb -or (-not $dbExistsInS3)) {
        Write-Host "`n[6/7] Uploading accounts.db Database to S3 Bucket (Initial Seed / Explicit)..." -ForegroundColor Yellow
        if (Test-Path $accountsDbFile) {
            Write-Host "Syncing $accountsDbFile -> s3://$DatabaseBucket/accounts.db" -ForegroundColor Cyan
            aws s3 cp $accountsDbFile "s3://$DatabaseBucket/accounts.db" --region $AwsRegion
        }
    } else {
        Write-Host "`n[6/7] Preserving existing accounts.db in S3 (Use -UploadDb to overwrite)..." -ForegroundColor DarkGray
    }
}

# 7. Build and Deploy Frontend / Docs
if ($Service -in @("all", "frontend") -and -not $SkipFrontend -and $FrontendBucket) {
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
}

if ($Service -in @("all", "docs") -and -not $SkipDocs -and $FrontendBucket) {
    Write-Host "`nBuilding & Deploying Technical Documentation..." -ForegroundColor Yellow
    $mkdocsConfig = Join-Path $rootDir "docs\mkdocs.yml"
    $pythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"
    if (Test-Path $mkdocsConfig) {
        if (Test-Path $pythonExe) {
            & $pythonExe -m mkdocs build -f $mkdocsConfig
        } elseif (Get-Command "mkdocs" -ErrorAction SilentlyContinue) {
            mkdocs build -f $mkdocsConfig
        }
    }
    $siteDir = Join-Path $rootDir "docs\site"
    if (Test-Path $siteDir) {
        Write-Host "Deploying documentation to S3: s3://$FrontendBucket/documentation" -ForegroundColor Cyan
        aws s3 sync $siteDir "s3://$FrontendBucket/documentation" --delete --region $AwsRegion
    }
}

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host " DEPLOYMENT COMPLETE! (Target: $Service)" -ForegroundColor Green
if ($ApiGatewayUrl) {
    Write-Host " API Gateway:     $ApiGatewayUrl" -ForegroundColor Green
    Write-Host " Backend Health:  $ApiGatewayUrl/health" -ForegroundColor Green
    Write-Host " Backend API:     $ApiGatewayUrl/api" -ForegroundColor Green
}
Write-Host " Database:        PostgreSQL on EC2 (sales_intel)" -ForegroundColor Green
if ($FrontendUrl) {
    Write-Host " Frontend App:    $FrontendUrl" -ForegroundColor Green
    Write-Host " Frontend Docs:   $FrontendUrl/documentation/" -ForegroundColor Green
}
Write-Host "============================================================" -ForegroundColor Cyan
