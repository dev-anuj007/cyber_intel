"""Pulumi entrypoint for Dedicated Infrastructure Service."""

import sys
from pathlib import Path

# Add backend directory to sys.path so 'src' packages can be imported
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.services.infra.main import provision_all_infra

if __name__ == "__main__" or __name__ == "__pulumi_main__":
    provision_all_infra()
