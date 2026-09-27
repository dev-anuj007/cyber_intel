from typing import Any, Dict, List, Optional, Protocol, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

from src.services.accounts.types import Account, SecuritySignal


class VulnerabilityFeatures(BaseModel):
    model_config = ConfigDict(extra="ignore")

    vulnerability_count: int = 0
    max_cvss: Optional[float] = None
    max_epss: Optional[float] = None
    kev_count: int = 0
    ransomware_count: int = 0


class RecordFeatures(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ip: Optional[str] = None
    port: Optional[int] = None
    hostname: Optional[str] = None
    domain: Optional[str] = None
    product: Optional[str] = None
    version: Optional[str] = None
    os: Optional[str] = None
    asn: Optional[Any] = None
    http_status: Optional[int] = None
    http_server: Optional[str] = None
    cloud_provider: Optional[str] = None
    cloud_region: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    vulnerability_count: int = 0
    max_cvss: Optional[float] = None
    max_epss: Optional[float] = None
    kev_count: int = 0
    ransomware_count: int = 0


class RecordProcessingResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    account_keys: List[str] = Field(default_factory=list)
    asset_id: Optional[Tuple[Optional[str], Optional[int], Optional[str]]] = None
    signals: List[SecuritySignal] = Field(default_factory=list)


class AddRecordCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    account_key: str
    asset_id: Optional[Tuple[Optional[str], Optional[int], Optional[str]]] = None
    features: Union[RecordFeatures, Dict[str, Any]] = Field(default_factory=dict)
    signals: List[SecuritySignal] = Field(default_factory=list)


class LoadAccountsRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    jsonl_path: str
    limit: Optional[int] = None


from src.services.aggregator.protocols import IAggregatorService

