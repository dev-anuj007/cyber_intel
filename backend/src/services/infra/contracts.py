"""Common Type Definitions and Contracts for Infrastructure Provisioning."""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import pulumi
import pulumi_aws as aws


@dataclass
class ServiceInfraContext:
    """Context passed from the orchestrator to each dedicated microservice provisioner."""
    prefix: str
    environment: str
    app_name: str
    lambda_role_arn: pulumi.Input[str]
    backend_image_uri: pulumi.Input[str]
    http_api_id: pulumi.Input[str]
    http_api_execution_arn: pulumi.Input[str]
    common_env_vars: pulumi.Input[Dict[str, str]]
    service_image_uris: Dict[str, pulumi.Input[str]] = field(default_factory=dict)

    def get_image_uri(self, service_name: str) -> pulumi.Input[str]:
        """Retrieves dedicated ECR image URI for the specified microservice."""
        return self.service_image_uris.get(service_name, self.backend_image_uri)


@dataclass
class ServiceInfraOutput:
    """Output returned by each individual microservice provisioner."""
    service_name: str
    lambda_function: aws.lambda_.Function
    integration: aws.apigatewayv2.Integration
    routes: List[aws.apigatewayv2.Route]
    permission: aws.lambda_.Permission


@dataclass
class SharedInfraOutput:
    """Output containing foundational shared cloud resources."""
    prefix: str
    environment: str
    app_name: str
    database_bucket: aws.s3.BucketV2
    database_s3_uri: pulumi.Output[str]
    ecr_repo_urls: Dict[str, pulumi.Output[str]]
    service_image_uris: Dict[str, pulumi.Output[str]]
    backend_image_uri: pulumi.Output[str]
    lambda_role: aws.iam.Role
    http_api: aws.apigatewayv2.Api
    api_stage: aws.apigatewayv2.Stage
    service_context: ServiceInfraContext


@dataclass
class MicroservicesInfraOutput:
    """Output containing all deployed microservice resources."""
    services: Dict[str, ServiceInfraOutput]
    gateway_lambda: aws.lambda_.Function
    gateway_integration: aws.apigatewayv2.Integration
    routes: List[aws.apigatewayv2.Route]


@dataclass
class FrontendInfraOutput:
    """Output containing frontend static hosting resources."""
    bucket: aws.s3.BucketV2
    website: aws.s3.BucketWebsiteConfigurationV2
    public_access: aws.s3.BucketPublicAccessBlock
    bucket_policy: aws.s3.BucketPolicy
    cors: aws.s3.BucketCorsConfigurationV2
    website_url: pulumi.Output[str]
