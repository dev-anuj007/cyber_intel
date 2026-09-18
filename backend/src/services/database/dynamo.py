import os
from decimal import Decimal
from typing import Any, Dict, Optional

from src.core.config import AWS_REGION
from src.services.logger import get_logger

logger = get_logger("services.database.dynamo")

_DYNAMO_RESOURCE = None
_DYNAMO_CLIENT = None


def is_deployed() -> bool:
    is_lambda = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
    current_env = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "local")).lower()
    is_cloud_env = current_env not in {"local", "dev_local", "test"}
    has_ddb_env = bool(os.getenv("DYNAMODB_USERS_TABLE") or os.getenv("AWS_EXECUTION_ENV"))
    return is_lambda or is_cloud_env or has_ddb_env


def get_dynamo_resource():
    global _DYNAMO_RESOURCE
    if _DYNAMO_RESOURCE is None:
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 is required for DynamoDB operations. Run: pip install boto3")
        region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", AWS_REGION))
        _DYNAMO_RESOURCE = boto3.resource("dynamodb", region_name=region)
    return _DYNAMO_RESOURCE


def get_dynamo_client():
    global _DYNAMO_CLIENT
    if _DYNAMO_CLIENT is None:
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 is required for DynamoDB operations. Run: pip install boto3")
        region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", AWS_REGION))
        _DYNAMO_CLIENT = boto3.client("dynamodb", region_name=region)
    return _DYNAMO_CLIENT


def get_table_name(entity: str) -> str:
    env_var_map = {
        "users": "DYNAMODB_USERS_TABLE",
        "scores": "DYNAMODB_SCORES_TABLE",
        "jobs": "DYNAMODB_JOBS_TABLE",
        "crawled": "DYNAMODB_CRAWLED_TABLE",
        "eval_runs": "DYNAMODB_EVAL_RUNS_TABLE",
        "prompts": "DYNAMODB_PROMPTS_TABLE",
    }
    env_name = env_var_map.get(entity)
    if env_name and os.getenv(env_name):
        return os.getenv(env_name)

    app_name = os.getenv("APP_NAME", "sales-intel")
    env = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "dev"))
    return f"{app_name}-{env}-{entity}"


def float_to_decimal(val: Any) -> Any:
    if isinstance(val, float):
        return Decimal(str(round(val, 6)))
    elif isinstance(val, dict):
        return {k: float_to_decimal(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [float_to_decimal(v) for v in val]
    return val


def decimal_to_python(val: Any) -> Any:
    if isinstance(val, Decimal):
        if val % 1 == 0:
            return int(val)
        return float(val)
    elif isinstance(val, dict):
        return {k: decimal_to_python(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [decimal_to_python(v) for v in val]
    return val
