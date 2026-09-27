import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pulumi

from src.services.infra.dependencies import (
    InfraServiceDependencyContext,
    get_infra_dependency_context,
)
from src.services.infra.protocols import (
    IFrontendInfraProvisioner,
    IInfraService,
    IMicroservicesInfraProvisioner,
    ISharedInfraProvisioner,
)
from src.services.infra.types import (
    FrontendInfraOutput,
    MicroservicesInfraOutput,
    SharedInfraOutput,
)


class InfraService(IInfraService):
    def __init__(self, context: Optional[InfraServiceDependencyContext] = None):
        self._context = context or get_infra_dependency_context()
        self._shared_provisioner: ISharedInfraProvisioner = self._context.shared_provisioner
        self._microservices_provisioner: IMicroservicesInfraProvisioner = self._context.microservices_provisioner
        self._frontend_provisioner: IFrontendInfraProvisioner = self._context.frontend_provisioner

    def provision_all(self) -> Dict[str, Any]:
        shared: SharedInfraOutput = self._shared_provisioner.provision_shared()
        microservices: MicroservicesInfraOutput = self._microservices_provisioner.provision_microservices(
            shared.service_context
        )
        frontend: FrontendInfraOutput = self._frontend_provisioner.provision_frontend(
            prefix=shared.prefix,
            environment=shared.environment,
            app_name=shared.app_name,
        )

        api_endpoint = shared.http_api.api_endpoint
        pulumi.export("api_gateway_url", api_endpoint)
        pulumi.export("backend_api_url", api_endpoint.apply(lambda ep: f"{ep}/api"))
        pulumi.export("backend_health_url", api_endpoint.apply(lambda ep: f"{ep}/health"))
        pulumi.export("database_bucket_name", shared.database_bucket.id)
        pulumi.export("database_s3_uri", shared.database_s3_uri)
        if shared.database_url is not None:
            pulumi.export("database_url", shared.database_url)
        pulumi.export("frontend_bucket_name", frontend.bucket.id)
        pulumi.export("frontend_website_url", frontend.website_url)

        return {
            "shared": shared,
            "microservices": microservices,
            "frontend": frontend,
        }


default_infra_service = InfraService()


def provision_all_infra() -> Dict[str, Any]:
    return default_infra_service.provision_all()


if __name__ == "__main__" or __name__ == "__pulumi_main__":
    BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    provision_all_infra()
