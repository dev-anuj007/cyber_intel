from typing import Optional

from src.services.infra.internals.frontend import FrontendInfraProvisioner
from src.services.infra.internals.microservices import MicroservicesInfraProvisioner
from src.services.infra.internals.shared import SharedInfraProvisioner
from src.services.infra.protocols import (
    IFrontendInfraProvisioner,
    IInfraService,
    IMicroservicesInfraProvisioner,
    ISharedInfraProvisioner,
)


class InfraServiceDependencyContext:
    def __init__(
        self,
        shared_provisioner: Optional[ISharedInfraProvisioner] = None,
        microservices_provisioner: Optional[IMicroservicesInfraProvisioner] = None,
        frontend_provisioner: Optional[IFrontendInfraProvisioner] = None,
    ):
        self.shared_provisioner = shared_provisioner or SharedInfraProvisioner()
        self.microservices_provisioner = microservices_provisioner or MicroservicesInfraProvisioner()
        self.frontend_provisioner = frontend_provisioner or FrontendInfraProvisioner()


def get_infra_dependency_context(
    shared_provisioner: Optional[ISharedInfraProvisioner] = None,
    microservices_provisioner: Optional[IMicroservicesInfraProvisioner] = None,
    frontend_provisioner: Optional[IFrontendInfraProvisioner] = None,
) -> InfraServiceDependencyContext:
    return InfraServiceDependencyContext(
        shared_provisioner=shared_provisioner,
        microservices_provisioner=microservices_provisioner,
        frontend_provisioner=frontend_provisioner,
    )


def create_infra_service(context: Optional[InfraServiceDependencyContext] = None) -> IInfraService:
    from src.services.infra.infra_service import InfraService

    if context is None:
        context = get_infra_dependency_context()
    return InfraService(context=context)


default_infra_service = create_infra_service()


def get_infra_service() -> IInfraService:
    return default_infra_service
