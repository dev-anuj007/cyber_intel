import json

import pulumi
import pulumi_aws as aws

from src.services.infra.types import FrontendInfraOutput


class FrontendInfraProvisioner:
    def provision_frontend(self, prefix: str, environment: str, app_name: str) -> FrontendInfraOutput:
        current_region = aws.get_region()
        current_account = aws.get_caller_identity()

        frontend_bucket = aws.s3.BucketV2(
            f"{prefix}-frontend-bucket",
            bucket=f"{prefix}-frontend-{current_region.name}-{current_account.account_id}",
            force_destroy=True,
            tags={"Environment": environment, "App": app_name, "Tier": "Frontend"},
            opts=pulumi.ResourceOptions(protect=False),
        )

        frontend_website = aws.s3.BucketWebsiteConfigurationV2(
            f"{prefix}-frontend-website",
            bucket=frontend_bucket.id,
            index_document=aws.s3.BucketWebsiteConfigurationV2IndexDocumentArgs(suffix="index.html"),
            error_document=aws.s3.BucketWebsiteConfigurationV2ErrorDocumentArgs(key="index.html"),
        )

        frontend_public_access = aws.s3.BucketPublicAccessBlock(
            f"{prefix}-frontend-public-access",
            bucket=frontend_bucket.id,
            block_public_acls=False,
            block_public_policy=False,
            ignore_public_acls=False,
            restrict_public_buckets=False,
        )

        bucket_policy = aws.s3.BucketPolicy(
            f"{prefix}-frontend-policy",
            bucket=frontend_bucket.id,
            policy=frontend_bucket.arn.apply(
                lambda arn: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "PublicReadGetObject",
                                "Effect": "Allow",
                                "Principal": "*",
                                "Action": "s3:GetObject",
                                "Resource": f"{arn}/*",
                            }
                        ],
                    }
                )
            ),
            opts=pulumi.ResourceOptions(depends_on=[frontend_public_access]),
        )

        cors = aws.s3.BucketCorsConfigurationV2(
            f"{prefix}-frontend-cors",
            bucket=frontend_bucket.id,
            cors_rules=[
                aws.s3.BucketCorsConfigurationV2CorsRuleArgs(
                    allowed_headers=["*"],
                    allowed_methods=["GET", "HEAD", "PUT", "POST", "DELETE"],
                    allowed_origins=["*"],
                    max_age_seconds=3600,
                )
            ],
        )

        website_url = frontend_website.website_endpoint.apply(lambda ep: f"http://{ep}")

        return FrontendInfraOutput(
            bucket=frontend_bucket,
            website=frontend_website,
            public_access=frontend_public_access,
            bucket_policy=bucket_policy,
            cors=cors,
            website_url=website_url,
        )



