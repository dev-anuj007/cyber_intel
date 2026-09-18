"""Eval Microservice Dedicated Pulumi Infrastructure Setup."""

from typing import List
import pulumi
import pulumi_aws as aws

from src.services.infra import ServiceInfraContext, ServiceInfraOutput


def provision_service_infra(ctx: ServiceInfraContext) -> ServiceInfraOutput:
    """Provisions dedicated AWS Lambda, API Gateway Integration, and Routes for the Eval microservice."""
    service_name = "eval"
    name_prefix = f"{ctx.prefix}-{service_name}"

    # 1. Dedicated Eval Lambda Function
    eval_lambda = aws.lambda_.Function(
        f"{name_prefix}-lambda",
        name=f"{ctx.prefix}-{service_name}",
        role=ctx.lambda_role_arn,
        package_type="Image",
        image_uri=ctx.get_image_uri(service_name),
        image_config=aws.lambda_.FunctionImageConfigArgs(
            commands=["src.services.eval.lambda_handler.handler"]
        ),
        memory_size=1024,
        timeout=60,
        ephemeral_storage=aws.lambda_.FunctionEphemeralStorageArgs(size=4096),
        environment=aws.lambda_.FunctionEnvironmentArgs(variables=ctx.common_env_vars),
        tags={"Environment": ctx.environment, "App": ctx.app_name, "Service": service_name},
    )

    # 2. Dedicated API Gateway Integration
    integration = aws.apigatewayv2.Integration(
        f"{name_prefix}-integration",
        api_id=ctx.http_api_id,
        integration_type="AWS_PROXY",
        integration_uri=eval_lambda.arn,
        payload_format_version="2.0",
    )

    # 3. Dedicated Lambda Invoke Permission
    permission = aws.lambda_.Permission(
        f"{name_prefix}-permission",
        action="lambda:InvokeFunction",
        function=eval_lambda.name,
        principal="apigateway.amazonaws.com",
        source_arn=pulumi.Output.all(ctx.http_api_execution_arn).apply(lambda args: f"{args[0]}/*/*"),
    )

    # 4. Dedicated Eval API Gateway Routes
    route_keys = [
        "ANY /api/eval/{proxy+}",
        "GET /api/eval/runs",
        "POST /api/eval/run",
    ]

    routes = []
    for idx, r_key in enumerate(route_keys):
        clean_key = r_key.replace(" ", "-").replace("/", "-").replace("{", "").replace("}", "").replace("+", "")
        route = aws.apigatewayv2.Route(
            f"{name_prefix}-route-{idx}-{clean_key}",
            api_id=ctx.http_api_id,
            route_key=r_key,
            target=integration.id.apply(lambda i_id: f"integrations/{i_id}"),
        )
        routes.append(route)

    return ServiceInfraOutput(
        service_name=service_name,
        lambda_function=eval_lambda,
        integration=integration,
        routes=routes,
        permission=permission,
    )
