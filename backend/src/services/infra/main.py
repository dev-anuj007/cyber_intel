"""Dedicated Infrastructure Orchestration Entrypoint.

Orchestrates:
1. Shared Infrastructure (S3 DB, ECR, IAM, API Gateway v2)
2. Microservices Deployment (pulls each service's infra details and deploys all Lambdas & Routes)
3. Frontend Infrastructure (S3 Static Website Hosting)
4. Stack Outputs
"""

import sys
from pathlib import Path
import pulumi

# Ensure backend root is in sys.path when running from Pulumi
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.services.infra.contracts import (
    ServiceInfraContext,
    ServiceInfraOutput,
    SharedInfraOutput,
    MicroservicesInfraOutput,
    FrontendInfraOutput,
)
from src.services.infra.shared import provision_shared_infra
from src.services.infra.microservices import provision_microservices_infra
from src.services.infra.frontend import provision_frontend_infra


def provision_all_infra():
    """Provisions all platform infrastructure and registers stack outputs."""
    # 1. Base Shared Infrastructure
    shared: SharedInfraOutput = provision_shared_infra()

    # 2. Dedicated Microservices (Auto-discovers & deploys all Lambda microservices)
    microservices: MicroservicesInfraOutput = provision_microservices_infra(shared.service_context)

    # 3. Dedicated Frontend Infrastructure (S3 Website Hosting & Policies)
    frontend: FrontendInfraOutput = provision_frontend_infra(
        prefix=shared.prefix,
        environment=shared.environment,
        app_name=shared.app_name,
    )

    # 4. Platform Stack Outputs
    api_endpoint = shared.http_api.api_endpoint
    pulumi.export("api_gateway_url", api_endpoint)
    pulumi.export("backend_api_url", api_endpoint.apply(lambda ep: f"{ep}/api"))
    pulumi.export("backend_health_url", api_endpoint.apply(lambda ep: f"{ep}/health"))
    pulumi.export("database_bucket_name", shared.database_bucket.id)
    pulumi.export("database_s3_uri", shared.database_s3_uri)
    pulumi.export("frontend_bucket_name", frontend.bucket.id)
    pulumi.export("frontend_website_url", frontend.website_url)

    return {
        "shared": shared,
        "microservices": microservices,
        "frontend": frontend,
    }


# Execute orchestration when run directly by Pulumi
if __name__ == "__main__" or __name__ == "__pulumi_main__":
    provision_all_infra()
