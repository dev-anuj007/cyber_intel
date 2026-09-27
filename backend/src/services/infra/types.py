from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass
class ServiceInfraContext:
    prefix: str
    environment: str
    app_name: str
    lambda_role_arn: Any
    backend_image_uri: Any
    http_api_id: Any
    http_api_execution_arn: Any
    common_env_vars: Any
    service_image_uris: Mapping[str, Any] = field(default_factory=dict)

    def get_image_uri(self, service_name: str) -> Any:
        return self.service_image_uris.get(service_name, self.backend_image_uri)


@dataclass
class ServiceInfraOutput:
    service_name: str
    lambda_function: Any
    integration: Any
    routes: List[Any]
    permission: Any


@dataclass
class SharedInfraOutput:
    prefix: str
    environment: str
    app_name: str
    database_bucket: Any
    database_s3_uri: Any
    ecr_repo_urls: Dict[str, Any]
    service_image_uris: Dict[str, Any]
    backend_image_uri: Any
    lambda_role: Any
    http_api: Any
    api_stage: Any
    service_context: ServiceInfraContext
    database_url: Optional[Any] = None
    postgres_instance: Optional[Any] = None


@dataclass
class MicroservicesInfraOutput:
    services: Dict[str, ServiceInfraOutput]
    gateway_lambda: Any
    gateway_integration: Any
    routes: List[Any]


@dataclass
class FrontendInfraOutput:
    bucket: Any
    website: Any
    public_access: Any
    bucket_policy: Any
    cors: Any
    website_url: Any
