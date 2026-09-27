from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

from src.services.accounts.types import Account, SecuritySignal

AssetIdTuple = Tuple[Optional[str], Optional[int], Optional[str]]


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


class ProcessRecordQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    record: Dict[str, Any] = Field(default_factory=dict)


class RecordProcessingResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    account_keys: List[str] = Field(default_factory=list)
    asset_id: Optional[AssetIdTuple] = None
    signals: List[SecuritySignal] = Field(default_factory=list)

    def to_tuple(
        self,
    ) -> Tuple[
        List[str],
        Optional[AssetIdTuple],
        List[SecuritySignal],
    ]:
        return (self.account_keys, self.asset_id, self.signals)


class AddRecordCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")

    account_key: str
    asset_id: Optional[AssetIdTuple] = None
    features: Union[RecordFeatures, Dict[str, Any]] = Field(default_factory=dict)
    signals: List[SecuritySignal] = Field(default_factory=list)


class AggregateRecordsQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    records: List[Dict[str, Any]] = Field(default_factory=list)


class AggregatedAccountsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    accounts: List[Account] = Field(default_factory=list)
    total_count: int = 0


class LoadAccountsRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    jsonl_path: str
    limit: Optional[int] = None
