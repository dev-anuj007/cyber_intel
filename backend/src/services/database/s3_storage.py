import io
import os
import sqlite3
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

from src.core.config import ROOT_DIR, BACKEND_DIR, AWS_REGION, S3_DATABASE_URI
from src.services.logger import get_logger

logger = get_logger("services.database.s3_storage")


class S3DirectStorage:

    def __init__(self, s3_uri: Optional[str] = None, local_path: Optional[Path] = None):
        self.s3_uri = s3_uri or os.getenv("S3_DATABASE_URI") or S3_DATABASE_URI
        self.local_path = local_path or self._resolve_local_db_path()
        self._s3_client = None
        self._bucket_name: Optional[str] = None
        self._object_key: Optional[str] = None
        self._cached_file_size: int = 0
        self._parsed = False

        self._parse_s3_uri()

    @property
    def is_deployed_env(self) -> bool:
        """Determines dynamically if the runtime environment is deployed (non-local) or AWS Lambda."""
        is_lambda = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
        current_env = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "local")).lower()
        is_cloud_env = current_env not in {"local", "dev_local", "test"}
        effective_uri = self.s3_uri or os.getenv("S3_DATABASE_URI") or ""
        has_s3_uri = bool(effective_uri and effective_uri.startswith("s3://"))
        return is_lambda or (is_cloud_env and has_s3_uri) or has_s3_uri

    def _parse_s3_uri(self) -> None:
        effective_uri = self.s3_uri or os.getenv("S3_DATABASE_URI") or ""
        if effective_uri and effective_uri.startswith("s3://"):
            parsed = urlparse(effective_uri)
            self._bucket_name = parsed.netloc
            self._object_key = parsed.path.lstrip("/")
            self._parsed = True
        elif bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME")):
            uri = os.getenv("S3_DATABASE_URI") or os.getenv("S3_DB_URI") or ""
            if uri and uri.startswith("s3://"):
                parsed = urlparse(uri)
                self._bucket_name = parsed.netloc
                self._object_key = parsed.path.lstrip("/")
                self._parsed = True

    @property
    def s3_client(self):
        if self._s3_client is None:
            try:
                import boto3
                self._s3_client = boto3.client("s3", region_name=AWS_REGION)
            except ImportError:
                raise ImportError("boto3 is required for S3 database interactions. Run: pip install boto3")
        return self._s3_client

    def _resolve_local_db_path(self) -> Path:
        """Auto-resolve local accounts.db location across common project roots."""
        candidates = [
            ROOT_DIR / "accounts.db",
            BACKEND_DIR / "accounts.db",
            Path("accounts.db"),
            Path("/tmp/accounts.db"),
        ]
        valid = [c for c in candidates if c.exists() and c.is_file() and c.stat().st_size > 0]
        if valid:
            # Sort by file size descending to pick the full populated database
            valid.sort(key=lambda p: p.stat().st_size, reverse=True)
            return valid[0]
        return ROOT_DIR / "accounts.db"

    def get_effective_db_path(self) -> Path:
        """Returns the effective database path for SQLite connection based on environment."""
        self._parse_s3_uri()

        if self.is_deployed_env:
            target_tmp = Path("/tmp/accounts.db")
            if target_tmp.exists() and target_tmp.stat().st_size > 0:
                return target_tmp
            if self._bucket_name and self._object_key:
                try:
                    logger.info(
                        "Connecting to deployed database on S3",
                        bucket=self._bucket_name,
                        key=self._object_key,
                        target=str(target_tmp),
                    )
                    self.s3_client.download_file(self._bucket_name, self._object_key, str(target_tmp))
                    return target_tmp
                except Exception as e:
                    logger.error(f"S3 database connection error: {e}")
                    raise RuntimeError(f"Failed to access accounts.db from S3 (s3://{self._bucket_name}/{self._object_key}): {e}")
            return target_tmp

        if self.local_path and self.local_path.exists() and self.local_path.stat().st_size > 0:
            return self.local_path

        return self.local_path

    def get_storage_info(self) -> Tuple[str, int, bool]:
        """Returns (storage_location_description, size_bytes, is_s3_active)."""
        self._parse_s3_uri()

        if self.is_deployed_env:
            target_tmp = Path("/tmp/accounts.db")
            if target_tmp.exists():
                return (f"s3://{self._bucket_name}/{self._object_key} (cached in /tmp)", target_tmp.stat().st_size, True)
            if self._bucket_name and self._object_key:
                try:
                    resp = self.s3_client.head_object(Bucket=self._bucket_name, Key=self._object_key)
                    size = resp.get("ContentLength", 0)
                    return (f"s3://{self._bucket_name}/{self._object_key}", size, True)
                except Exception:
                    pass
            return (f"s3://{self._bucket_name}/{self._object_key}", 0, True)

        eff_path = self.get_effective_db_path()
        if eff_path and eff_path.exists():
            return (str(eff_path), eff_path.stat().st_size, False)

        return (str(self.local_path), 0, False)

    def sync_to_s3(self) -> bool:
        self._parse_s3_uri()
        if not self.is_deployed_env or not self._bucket_name or not self._object_key:
            return False

        target_tmp = Path("/tmp/accounts.db")
        if not target_tmp.exists() or target_tmp.stat().st_size == 0:
            return False

        try:
            self.s3_client.upload_file(str(target_tmp), self._bucket_name, self._object_key)
            logger.info("Successfully synced accounts.db to S3", bucket=self._bucket_name, key=self._object_key)
            return True
        except Exception as e:
            logger.error(f"Error syncing accounts.db to S3: {e}", bucket=self._bucket_name, key=self._object_key)
            return False
