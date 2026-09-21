# Dedicated Infrastructure Service (src.services.infra)

This package contains optional deployment and infrastructure automation for the platform. The app runtime itself is a local FastAPI + React + PostgreSQL stack, and the primary development workflow is to run the backend and frontend directly on a workstation or local environment.

## What this folder is for

- infrastructure provisioning helpers for environments that want to automate setup
- optional deployment scripts for custom hosting patterns
- compatibility with local automation and environment bootstrapping workflows

## What matters in practice

For normal day-to-day work, the key runtime flow is:

1. configure PostgreSQL in the backend environment
2. run the FastAPI app locally
3. run the React frontend locally
4. validate behavior through tests and service-level checks

The repo’s actual architecture is therefore best described as a modular local web application rather than a cloud-only deployment model.
