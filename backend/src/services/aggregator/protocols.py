from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, Tuple, Union, runtime_checkable

from pydantic import BaseModel

from src.services.accounts.types import Account, SecuritySignal

if TYPE_CHECKING:
    from src.services.aggregator.types import LoadAccountsRequest, RecordFeatures


@runtime_checkable
class IAggregatorService(Protocol):
    def resolve_account_keys(self, record: Union[Dict[str, Any], BaseModel]) -> List[str]: ...

    def get_asset_id(
        self, features: Union[RecordFeatures, Dict[str, Any]]
    ) -> Optional[Tuple[Optional[str], Optional[int], Optional[str]]]: ...

    def extract_vulnerability_features(self, vulns: Optional[Dict[str, Any]]) -> Dict[str, Any]: ...

    def extract_features(self, record: Dict[str, Any]) -> Dict[str, Any]: ...

    def detect_signals(self, features: Union[RecordFeatures, Dict[str, Any]]) -> List[SecuritySignal]: ...

    def process_record(
        self, record: Dict[str, Any]
    ) -> Tuple[
        List[str],
        Optional[Tuple[Optional[str], Optional[int], Optional[str]]],
        List[SecuritySignal],
    ]: ...

    def aggregate(self, records: List[Dict[str, Any]]) -> List[Account]: ...

    def build_accounts(self, records: List[Dict[str, Any]]) -> Dict[str, Account]: ...

    def load_accounts_from_jsonl(
        self, request: Union[LoadAccountsRequest, str], limit: Optional[int] = None
    ) -> Dict[str, Account]: ...
