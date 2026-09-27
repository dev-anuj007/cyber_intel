from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    Union,
    runtime_checkable,
)

from pydantic import BaseModel

from src.services.accounts.types import Account, SecuritySignal

if TYPE_CHECKING:
    from src.services.aggregator.types import (
        AggregateRecordsQuery,
        AssetIdTuple,
        LoadAccountsRequest,
        ProcessRecordQuery,
        RecordFeatures,
        RecordProcessingResult,
        VulnerabilityFeatures,
    )


@runtime_checkable
class IAggregatorService(Protocol):
    def aggregate(
        self, records: Union[List[Dict[str, Any]], AggregateRecordsQuery]
    ) -> List[Account]: ...

    def build_accounts(self, records: List[Dict[str, Any]]) -> Dict[str, Account]: ...

    def load_accounts_from_jsonl(
        self,
        request: Union[LoadAccountsRequest, str],
        limit: Optional[int] = None,
    ) -> Dict[str, Account]: ...

    def process_record(
        self, record: Union[Dict[str, Any], ProcessRecordQuery]
    ) -> RecordProcessingResult: ...

    def resolve_account_keys(
        self, record: Union[Dict[str, Any], BaseModel]
    ) -> List[str]: ...

    def detect_signals(
        self, features: Union[RecordFeatures, Dict[str, Any]]
    ) -> List[SecuritySignal]: ...

    def extract_features(self, record: Dict[str, Any]) -> Dict[str, Any]: ...

    def extract_record_features(self, record: Dict[str, Any]) -> RecordFeatures: ...

    def extract_vulnerability_features(
        self, vulns: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]: ...

    def extract_typed_vulnerability_features(
        self, vulns: Optional[Dict[str, Any]]
    ) -> VulnerabilityFeatures: ...

    def get_asset_id(
        self, features: Union[RecordFeatures, Dict[str, Any]]
    ) -> Optional[AssetIdTuple]: ...
