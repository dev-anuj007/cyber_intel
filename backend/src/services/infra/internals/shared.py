import json
import os
from typing import Any, Dict

import pulumi
import pulumi_aws as aws

from src.services.infra.internals.ec2_postgres import provision_ec2_postgres
from src.services.infra.types import ServiceInfraContext, SharedInfraOutput

SERVICES = ["gateway", "database", "accounts", "auth", "scorer", "crawler", "eval", "jobs", "prompts"]


class SharedInfraProvisioner:
    def provision_shared(self) -> SharedInfraOutput:
        config = pulumi.Config()
        app_name = config.get("appName") or "sales-intel"
        environment = config.get("environment") or "dev"
        gemini_model = config.get("geminiModel") or "gemini-3.1-flash-lite"
        gemini_api_key = config.get_secret("geminiApiKey") or os.environ.get("GEMINI_API_KEY") or ""
        jwt_secret = (
            config.get_secret("jwtSecret") or os.environ.get("JWT_SECRET") or "super-secret-sales-intel-jwt-key-2026"
        )
        logfire_token = config.get_secret("logfireToken") or os.environ.get("LOGFIRE_TOKEN") or ""

        prefix = f"{app_name}-{environment}"
        current_region = aws.get_region()
        current_account = aws.get_caller_identity()

        database_bucket = aws.s3.BucketV2(
            f"{prefix}-database-bucket",
            bucket=f"{prefix}-db-{current_region.name}-{current_account.account_id}",
            force_destroy=True,
            tags={"Environment": environment, "App": app_name, "Tier": "Storage"},
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

        database_s3_uri = database_bucket.id.apply(lambda b: f"s3://{b}/artifacts")

        ecr_repo_urls: Dict[str, Any] = {}
        service_image_uris: Dict[str, Any] = {}

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
                    image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(scan_on_push=False),
                    tags={"Environment": environment, "App": app_name, "Service": svc},
                )
                ecr_repo_urls[svc] = repo.repository_url
                service_image_uris[svc] = repo.repository_url.apply(lambda url: f"{url}:latest")

        backend_image_uri = service_image_uris.get("gateway", list(service_image_uris.values())[0])

        lambda_role = aws.iam.Role(
            f"{prefix}-lambda-role",
            assume_role_policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Effect": "Allow",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                        }
                    ],
                }
            ),
            tags={"Environment": environment, "App": app_name},
        )

        aws.iam.RolePolicyAttachment(
            f"{prefix}-lambda-basic-exec",
            role=lambda_role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )

        aws.iam.RolePolicy(
            f"{prefix}-lambda-policy",
            role=lambda_role.id,
            policy=database_bucket.arn.apply(
                lambda bucket_arn: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "s3:GetObject",
                                    "s3:PutObject",
                                    "s3:ListBucket",
                                ],
                                "Resource": [bucket_arn, f"{bucket_arn}/*"],
                            },
                            {
                                "Effect": "Allow",
                                "Action": ["lambda:InvokeFunction"],
                                "Resource": ["arn:aws:lambda:*:*:function:sales-intel-*"],
                            },
                        ],
                    }
                )
            ),
        )

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

        enable_ec2_postgres = (
            config.get_bool("enableEc2Postgres") if config.get_bool("enableEc2Postgres") is not None else True
        )
        if enable_ec2_postgres:
            ec2_pg = provision_ec2_postgres(prefix=prefix, environment=environment)
            pg_db_url = ec2_pg.database_url
            pg_instance = ec2_pg.instance
        else:
            pg_db_url = pulumi.Output.from_input("")
            pg_instance = None

        def _create_env_map(
            s3_uri: str,
            g_key: str,
            j_secret: str,
            lf_token: str,
            db_url: str,
        ) -> Dict[str, str]:
            env_map = {
                "ENVIRONMENT": environment,
                "S3_DATABASE_URI": s3_uri,
                "GEMINI_MODEL": gemini_model,
                "JWT_SECRET": j_secret,
                "LOG_LEVEL": "INFO",
            }
            if db_url:
                env_map["DATABASE_URL"] = db_url
            if g_key:
                env_map["GEMINI_API_KEY"] = g_key
            if lf_token:
                env_map["LOGFIRE_TOKEN"] = lf_token
            return env_map

        common_env_vars = pulumi.Output.all(
            database_s3_uri,
            gemini_api_key,
            jwt_secret,
            logfire_token,
            pg_db_url,
        ).apply(lambda args: _create_env_map(args[0], args[1], args[2], args[3], args[4]))

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
            database_url=pg_db_url,
            postgres_instance=pg_instance,
        )



