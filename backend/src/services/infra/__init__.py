"""Dedicated Infrastructure Service for Sales Intelligence Platform.

Responsible for:
- Foundational shared cloud infrastructure (S3 Database, ECR, IAM, API Gateway)
- Discovering, configuring, and deploying all microservice Lambdas
- S3 Static Website Hosting for React frontend & documentation
"""

from .contracts import (
    ServiceInfraContext,
    ServiceInfraOutput,
    SharedInfraOutput,
    MicroservicesInfraOutput,
    FrontendInfraOutput,
)
from .shared import provision_shared_infra
from .microservices import provision_microservices_infra
from .frontend import provision_frontend_infra
from .main import provision_all_infra

__all__ = [
    "ServiceInfraContext",
    "ServiceInfraOutput",
    "SharedInfraOutput",
    "MicroservicesInfraOutput",
    "FrontendInfraOutput",
    "provision_shared_infra",
    "provision_microservices_infra",
    "provision_frontend_infra",
    "provision_all_infra",
]
