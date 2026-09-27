import pulumi
import pulumi_aws as aws

from src.services.infra.types import ServiceInfraContext, ServiceInfraOutput


def provision_service_infra(ctx: ServiceInfraContext) -> ServiceInfraOutput:
    service_name = "prompts"
    name_prefix = f"{ctx.prefix}-{service_name}"

    prompts_lambda = aws.lambda_.Function(
        f"{name_prefix}-lambda",
        name=f"{ctx.prefix}-{service_name}",
        role=ctx.lambda_role_arn,
        package_type="Image",
        image_uri=ctx.get_image_uri(service_name),
        image_config=aws.lambda_.FunctionImageConfigArgs(commands=["src.services.prompts.lambda_handler.handler"]),
        memory_size=512,
        timeout=30,
        environment=aws.lambda_.FunctionEnvironmentArgs(variables=ctx.common_env_vars),
        tags={"Environment": ctx.environment, "App": ctx.app_name, "Service": service_name},
    )

    integration = aws.apigatewayv2.Integration(
        f"{name_prefix}-integration",
        api_id=ctx.http_api_id,
        integration_type="AWS_PROXY",
        integration_uri=prompts_lambda.arn,
        payload_format_version="2.0",
    )

    permission = aws.lambda_.Permission(
        f"{name_prefix}-permission",
        action="lambda:InvokeFunction",
        function=prompts_lambda.name,
        principal="apigateway.amazonaws.com",
        source_arn=pulumi.Output.all(ctx.http_api_execution_arn).apply(lambda args: f"{args[0]}/*/*"),
    )

    route_keys = [
        "ANY /api/prompts/{proxy+}",
        "GET /api/prompts",
        "POST /api/prompts",
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
        lambda_function=prompts_lambda,
        integration=integration,
        routes=routes,
        permission=permission,
    )
