import json
import os
import threading
from typing import Callable, Dict, Optional

from src.services.database.dependencies import is_deployed
from src.services.jobs.protocols import IJobDispatcher
from src.services.logger.logger_service import BaseLogger, get_logger


class ThreadPoolJobDispatcher(IJobDispatcher):
    def __init__(self, executor_fn: Callable[[str], None], logger: Optional[BaseLogger] = None):
        self._executor_fn = executor_fn
        self._logger = logger or get_logger("services.jobs.dispatcher.thread")

    def dispatch(self, job_id: str, job_type: str) -> None:
        thread = threading.Thread(
            target=self._executor_fn,
            args=(job_id,),
            daemon=True,
            name=f"Worker-{job_id}",
        )
        thread.start()
        self._logger.info("Dispatched job to background thread", job_id=job_id, job_type=job_type)


class LambdaJobDispatcher(IJobDispatcher):
    def __init__(
        self,
        fallback_dispatcher: Optional[IJobDispatcher] = None,
        logger: Optional[BaseLogger] = None,
        region: Optional[str] = None,
        app_name: Optional[str] = None,
        environment: Optional[str] = None,
        routes: Optional[Dict[str, str]] = None,
    ):
        self._fallback = fallback_dispatcher
        self._logger = logger or get_logger("services.jobs.dispatcher.lambda")
        self._region = region or os.environ.get("AWS_REGION", "ap-south-1")
        self._app_name = app_name or os.environ.get("APP_NAME", "sales-intel")
        self._env = environment or os.environ.get("ENVIRONMENT", "dev")
        self._routes = routes or {
            "eval": "eval",
            "crawler": "crawler",
            "scorer": "scorer",
            "batch_score": "scorer",
        }

    def _resolve_function_name(self, job_type: str) -> str:
        for prefix, target in self._routes.items():
            if job_type.startswith(prefix):
                return f"{self._app_name}-{self._env}-{target}"
        return f"{self._app_name}-{self._env}-jobs"

    def dispatch(self, job_id: str, job_type: str) -> None:
        function_name = self._resolve_function_name(job_type)
        try:
            import boto3

            client = boto3.client("lambda", region_name=self._region)
            client.invoke(
                FunctionName=function_name,
                InvocationType="Event",
                Payload=json.dumps({"job_id": job_id, "action": "execute_job"}),
            )
            self._logger.info(
                "Dispatched job to AWS Lambda",
                job_id=job_id,
                function_name=function_name,
            )
        except Exception as exc:
            self._logger.warning(
                f"Lambda dispatch failed ({exc}), activating fallback",
                job_id=job_id,
                error=str(exc),
            )
            if self._fallback:
                self._fallback.dispatch(job_id, job_type)
            else:
                raise


def create_default_dispatcher(
    executor_fn: Callable[[str], None],
    logger: Optional[BaseLogger] = None,
) -> IJobDispatcher:
    thread_dispatcher = ThreadPoolJobDispatcher(executor_fn=executor_fn, logger=logger)
    if is_deployed():
        return LambdaJobDispatcher(
            fallback_dispatcher=thread_dispatcher,
            logger=logger,
        )
    return thread_dispatcher
