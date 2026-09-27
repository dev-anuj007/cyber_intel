from typing import Any, Dict, Protocol, runtime_checkable

from src.services.infra.types import (
    FrontendInfraOutput,
    MicroservicesInfraOutput,
    ServiceInfraContext,
    ServiceInfraOutput,
    SharedInfraOutput,
)


@runtime_checkable
class IServiceInfraProvisioner(Protocol):
    def provision_service(self, ctx: ServiceInfraContext) -> ServiceInfraOutput:
        ...


@runtime_checkable
class ISharedInfraProvisioner(Protocol):
    def provision_shared(self) -> SharedInfraOutput:
        ...


@runtime_checkable
class IMicroservicesInfraProvisioner(Protocol):
    def provision_microservices(self, ctx: ServiceInfraContext) -> MicroservicesInfraOutput:
        ...


@runtime_checkable
class IFrontendInfraProvisioner(Protocol):
    def provision_frontend(
        self,
        prefix: str,
        environment: str,
        app_name: str,
    ) -> FrontendInfraOutput:
        ...


@runtime_checkable
class IInfraService(Protocol):
    def provision_all(self) -> Dict[str, Any]:
        ...
