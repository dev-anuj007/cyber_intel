import json
import os
from typing import Dict, Any, Optional
import pulumi
import pulumi_aws as aws

from .contracts import ServiceInfraContext, SharedInfraOutput

SERVICES = ["gateway", "database", "accounts", "auth", "scorer", "crawler", "eval", "jobs"]


def provision_shared_infra() -> SharedInfraOutput:
    """Provisions core shared infrastructure resources."""
    config = pulumi.Config()
    app_name = config.get("appName") or "sales-intel"
    environment = config.get("environment") or "dev"
    gemini_model = config.get("geminiModel") or "gemini-3.1-flash-lite"
    gemini_api_key = config.get_secret("geminiApiKey") or os.environ.get("GEMINI_API_KEY") or ""
    jwt_secret = config.get_secret("jwtSecret") or os.environ.get("JWT_SECRET") or "super-secret-sales-intel-jwt-key-2026"

    prefix = f"{app_name}-{environment}"
    current_region = aws.get_region()
    current_account = aws.get_caller_identity()

    # 1. Amazon S3 Database Bucket (Direct accounts.db storage)
    database_bucket = aws.s3.BucketV2(
        f"{prefix}-database-bucket",
        bucket=f"{prefix}-db-{current_region.name}-{current_account.account_id}",
        force_destroy=True,
        tags={"Environment": environment, "App": app_name, "Tier": "Database"},
    )

    aws.s3.BucketServerSideEncryptionConfigurationV2(
        f"{prefix}-db-sse",
        bucket=database_bucket.id,
        rules=[
            aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
                apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
                    sse_algorithm="AES256"
                )
            )
        ],
    )

    database_s3_uri = database_bucket.id.apply(lambda b: f"s3://{b}/accounts.db")

    # 2. Dedicated Amazon ECR Repositories per Microservice
    ecr_repo_urls: Dict[str, pulumi.Output[str]] = {}
    service_image_uris: Dict[str, pulumi.Output[str]] = {}

    for svc in SERVICES:
        repo_name = f"{prefix}-{svc}"
        try:
            existing_repo = aws.ecr.get_repository(name=repo_name)
            img_uri = f"{existing_repo.repository_url}:latest"
            ecr_repo_urls[svc] = pulumi.Output.from_input(existing_repo.repository_url)
            service_image_uris[svc] = pulumi.Output.from_input(img_uri)
        except Exception:
            repo = aws.ecr.Repository(
                f"{prefix}-{svc}-repo",
                name=repo_name,
                image_tag_mutability="MUTABLE",
                force_delete=True,
                image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
                    scan_on_push=False
                ),
                tags={"Environment": environment, "App": app_name, "Service": svc},
            )
            ecr_repo_urls[svc] = repo.repository_url
            service_image_uris[svc] = repo.repository_url.apply(lambda url: f"{url}:latest")

    # Fallback backend image URI (maps to gateway)
    backend_image_uri = service_image_uris.get("gateway", list(service_image_uris.values())[0])

    # 3. Amazon DynamoDB Tables (Hybrid Dynamic Layer)
    users_table = aws.dynamodb.Table(
        f"{prefix}-users",
        name=f"{prefix}-users",
        billing_mode="PAY_PER_REQUEST",
        hash_key="email",
        attributes=[
            aws.dynamodb.TableAttributeArgs(name="email", type="S"),
            aws.dynamodb.TableAttributeArgs(name="id", type="S"),
        ],
        global_secondary_indexes=[
            aws.dynamodb.TableGlobalSecondaryIndexArgs(
                name="UserIdIndex",
                hash_key="id",
                projection_type="ALL",
            )
        ],
    )

    scores_table = aws.dynamodb.Table(
        f"{prefix}-ai-scores",
        name=f"{prefix}-ai-scores",
        billing_mode="PAY_PER_REQUEST",
        hash_key="account_key",
        range_key="created_at",
        attributes=[
            aws.dynamodb.TableAttributeArgs(name="account_key", type="S"),
            aws.dynamodb.TableAttributeArgs(name="created_at", type="S"),
        ],
    )

    jobs_table = aws.dynamodb.Table(
        f"{prefix}-jobs",
        name=f"{prefix}-jobs",
        billing_mode="PAY_PER_REQUEST",
        hash_key="job_id",
        attributes=[
            aws.dynamodb.TableAttributeArgs(name="job_id", type="S"),
        ],
    )

    crawled_table = aws.dynamodb.Table(
        f"{prefix}-crawled-accounts",
        name=f"{prefix}-crawled-accounts",
        billing_mode="PAY_PER_REQUEST",
        hash_key="account_key",
        attributes=[
            aws.dynamodb.TableAttributeArgs(name="account_key", type="S"),
        ],
    )

    eval_runs_table = aws.dynamodb.Table(
        f"{prefix}-eval-runs",
        name=f"{prefix}-eval-runs",
        billing_mode="PAY_PER_REQUEST",
        hash_key="run_id",
        attributes=[
            aws.dynamodb.TableAttributeArgs(name="run_id", type="S"),
        ],
    )

    prompts_table = aws.dynamodb.Table(
        f"{prefix}-prompts",
        name=f"{prefix}-prompts",
        billing_mode="PAY_PER_REQUEST",
        hash_key="name",
        range_key="version",
        attributes=[
            aws.dynamodb.TableAttributeArgs(name="name", type="S"),
            aws.dynamodb.TableAttributeArgs(name="version", type="S"),
        ],
    )

    # 4. IAM Execution Role for Lambda Microservices
    lambda_role = aws.iam.Role(
        f"{prefix}-lambda-role",
        name=f"{prefix}-lambda-role",
        assume_role_policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }),
        managed_policy_arns=[
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        ],
        tags={"Environment": environment, "App": app_name},
    )

    # S3 & DynamoDB Access Policy for Database Bucket & Tables
    aws.iam.RolePolicy(
        f"{prefix}-lambda-storage-policy",
        role=lambda_role.id,
        policy=pulumi.Output.all(
            database_bucket.arn,
            users_table.arn,
            scores_table.arn,
            jobs_table.arn,
            crawled_table.arn,
            eval_runs_table.arn,
            prompts_table.arn,
        ).apply(
            lambda args: json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:ListBucket",
                            "s3:HeadObject"
                        ],
                        "Resource": [
                            args[0],
                            f"{args[0]}/*"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:GetItem",
                            "dynamodb:PutItem",
                            "dynamodb:UpdateItem",
                            "dynamodb:DeleteItem",
                            "dynamodb:Query",
                            "dynamodb:Scan",
                            "dynamodb:BatchGetItem",
                            "dynamodb:BatchWriteItem"
                        ],
                        "Resource": [
                            args[1],
                            f"{args[1]}/*",
                            args[2],
                            f"{args[2]}/*",
                            args[3],
                            f"{args[3]}/*",
                            args[4],
                            f"{args[4]}/*",
                            args[5],
                            f"{args[5]}/*",
                            args[6],
                            f"{args[6]}/*",
                        ]
                    }
                ]
            })
        ),
    )

    # 5. Central Amazon API Gateway HTTP API v2
    http_api = aws.apigatewayv2.Api(
        f"{prefix}-http-api",
        name=f"{prefix}-api",
        protocol_type="HTTP",
        cors_configuration=aws.apigatewayv2.ApiCorsConfigurationArgs(
            allow_origins=["*"],
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
            allow_headers=["*"],
            max_age=3600,
        ),
    )

    api_stage = aws.apigatewayv2.Stage(
        f"{prefix}-api-stage",
        api_id=http_api.id,
        name="$default",
        auto_deploy=True,
    )

    # 6. Common Environment Variables
    def _create_env_map(
        s3_uri: str,
        g_key: str,
        j_secret: str,
        u_tbl: str,
        s_tbl: str,
        j_tbl: str,
        c_tbl: str,
        e_tbl: str,
        p_tbl: str,
    ) -> Dict[str, str]:
        env_map = {
            "ENVIRONMENT": environment,
            "S3_DATABASE_URI": s3_uri,
            "GEMINI_MODEL": gemini_model,
            "JWT_SECRET": j_secret,
            "LOG_LEVEL": "INFO",
            "DYNAMODB_USERS_TABLE": u_tbl,
            "DYNAMODB_SCORES_TABLE": s_tbl,
            "DYNAMODB_JOBS_TABLE": j_tbl,
            "DYNAMODB_CRAWLED_TABLE": c_tbl,
            "DYNAMODB_EVAL_RUNS_TABLE": e_tbl,
            "DYNAMODB_PROMPTS_TABLE": p_tbl,
        }
        if g_key:
            env_map["GEMINI_API_KEY"] = g_key
        return env_map

    common_env_vars = pulumi.Output.all(
        database_s3_uri,
        gemini_api_key,
        jwt_secret,
        users_table.name,
        scores_table.name,
        jobs_table.name,
        crawled_table.name,
        eval_runs_table.name,
        prompts_table.name,
    ).apply(
        lambda args: _create_env_map(
            args[0], args[1], args[2], args[3], args[4], args[5], args[6], args[7], args[8]
        )
    )

    # Context passed to each microservice's dedicated infra provisioner
    service_context = ServiceInfraContext(
        prefix=prefix,
        environment=environment,
        app_name=app_name,
        lambda_role_arn=lambda_role.arn,
        backend_image_uri=backend_image_uri,
        http_api_id=http_api.id,
        http_api_execution_arn=http_api.execution_arn,
        common_env_vars=common_env_vars,
        service_image_uris=service_image_uris,
    )

    return SharedInfraOutput(
        prefix=prefix,
        environment=environment,
        app_name=app_name,
        database_bucket=database_bucket,
        database_s3_uri=database_s3_uri,
        ecr_repo_urls=ecr_repo_urls,
        service_image_uris=service_image_uris,
        backend_image_uri=backend_image_uri,
        lambda_role=lambda_role,
        http_api=http_api,
        api_stage=api_stage,
        service_context=service_context,
    )
