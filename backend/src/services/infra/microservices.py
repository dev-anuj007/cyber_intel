"""Microservices Infrastructure Orchestrator.

Responsible for:
1. Discovering and invoking dedicated infra provisioners from each microservice package:
   - Database Microservice (`src.services.database.infra.main`)
   - Accounts Microservice (`src.services.accounts.infra.main`)
   - Auth Microservice (`src.services.auth.infra.main`)
   - Scorer Microservice (`src.services.scorer.infra.main`)
   - Crawler Microservice (`src.services.crawler.infra.main`)
   - Eval Microservice (`src.services.eval.infra.main`)
   - Jobs Microservice (`src.services.jobs.infra.main`)
2. Deploying the Unified Gateway Fallback Lambda (`/health` & `$default` routes)
3. Registering all API Gateway integrations and invoke permissions
"""

import importlib
from typing import Dict

import pulumi
import pulumi_aws as aws

from .contracts import MicroservicesInfraOutput, ServiceInfraContext, ServiceInfraOutput

# Standard microservice order
KNOWN_MICROSERVICES = [
    "database",
    "accounts",
    "auth",
    "scorer",
    "crawler",
    "eval",
    "jobs",
    "prompts",
]


def provision_microservices_infra(ctx: ServiceInfraContext) -> MicroservicesInfraOutput:
    """Discovers and provisions all microservices Lambdas and API Gateway integrations."""
    services_output: Dict[str, ServiceInfraOutput] = {}

    # Discover and invoke each service's dedicated infra provisioner
    for service_name in KNOWN_MICROSERVICES:
        module_path = f"src.services.{service_name}.infra.main"
        try:
            module = importlib.import_module(module_path)
            if hasattr(module, "provision_service_infra"):
                output: ServiceInfraOutput = module.provision_service_infra(ctx)
                services_output[service_name] = output
        except ModuleNotFoundError as err:
            pulumi.log.warn(f"Could not load infra for service '{service_name}': {err}")

    # Unified Gateway Fallback Lambda
    name_prefix = f"{ctx.prefix}-gateway"
    gateway_fn = aws.lambda_.Function(
        f"{ctx.prefix}-lambda-gateway",
        name=name_prefix,
        role=ctx.lambda_role_arn,
        package_type="Image",
        image_uri=ctx.get_image_uri("gateway"),
        image_config=aws.lambda_.FunctionImageConfigArgs(commands=["src.lambda_handler.handler"]),
        memory_size=2048,
        timeout=60,
        ephemeral_storage=aws.lambda_.FunctionEphemeralStorageArgs(size=4096),
        environment=aws.lambda_.FunctionEnvironmentArgs(variables=ctx.common_env_vars),
        tags={"Environment": ctx.environment, "App": ctx.app_name, "Service": "gateway"},
    )

    gateway_integration = aws.apigatewayv2.Integration(
        f"{name_prefix}-integration",
        api_id=ctx.http_api_id,
        integration_type="AWS_PROXY",
        integration_uri=gateway_fn.arn,
        payload_format_version="2.0",
    )

    aws.lambda_.Permission(
        f"{name_prefix}-permission",
        action="lambda:InvokeFunction",
        function=gateway_fn.name,
        principal="apigateway.amazonaws.com",
        source_arn=pulumi.Output.all(ctx.http_api_execution_arn).apply(lambda args: f"{args[0]}/*/*"),
    )

    route_health = aws.apigatewayv2.Route(
        f"{name_prefix}-route-health",
        api_id=ctx.http_api_id,
        route_key="GET /health",
        target=gateway_integration.id.apply(lambda i_id: f"integrations/{i_id}"),
    )

    route_default = aws.apigatewayv2.Route(
        f"{name_prefix}-route-default",
        api_id=ctx.http_api_id,
        route_key="$default",
        target=gateway_integration.id.apply(lambda i_id: f"integrations/{i_id}"),
    )

    return MicroservicesInfraOutput(
        services=services_output,
        gateway_lambda=gateway_fn,
        gateway_integration=gateway_integration,
        routes=[route_health, route_default],
    )
