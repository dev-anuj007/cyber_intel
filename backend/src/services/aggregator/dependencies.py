from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel

from src.services.accounts.types import Account, SecuritySignal
from src.services.aggregator.internals.parsers import FeatureExtractor
from src.services.aggregator.internals.repositories.reader import JsonlReader
from src.services.aggregator.internals.resolvers import AccountKeyResolver
from src.services.aggregator.internals.signals import SignalDetector
from src.services.aggregator.protocols import IAggregatorService
from src.services.logger.logger_service import BaseLogger, get_logger

if TYPE_CHECKING:
    from src.services.aggregator.types import (
        AggregateRecordsQuery,
        LoadAccountsRequest,
        ProcessRecordQuery,
        RecordFeatures,
        RecordProcessingResult,
    )


@dataclass
class AggregatorServiceDependencyContext:
    feature_extractor: FeatureExtractor
    signal_detector: SignalDetector
    key_resolver: AccountKeyResolver
    reader: JsonlReader
    logger: BaseLogger


def get_aggregator_dependency_context(
    feature_extractor: Optional[FeatureExtractor] = None,
    signal_detector: Optional[SignalDetector] = None,
    key_resolver: Optional[AccountKeyResolver] = None,
    reader: Optional[JsonlReader] = None,
    logger: Optional[BaseLogger] = None,
) -> AggregatorServiceDependencyContext:
    return AggregatorServiceDependencyContext(
        feature_extractor=feature_extractor or FeatureExtractor(),
        signal_detector=signal_detector or SignalDetector(),
        key_resolver=key_resolver or AccountKeyResolver(),
        reader=reader or JsonlReader(),
        logger=logger or get_logger("services.aggregator"),
    )


def create_aggregator_service(
    context: Optional[AggregatorServiceDependencyContext] = None,
) -> IAggregatorService:
    from src.services.aggregator.aggregator_service import AggregatorService

    return AggregatorService(context=context or get_aggregator_dependency_context())


def get_aggregator_service() -> IAggregatorService:
    return create_aggregator_service()


class _LazyAggregatorServiceProxy(IAggregatorService):
    """Lazy Singleton Proxy for AggregatorService.

    Defers actual instantiation to first access to avoid import-time overhead and
    circular dependencies.
    """

    def __init__(self) -> None:
        self._instance: Optional[IAggregatorService] = None

    def _get_service(self) -> IAggregatorService:
        if self._instance is None:
            self._instance = get_aggregator_service()
        return self._instance

    def aggregate(
        self, records: Union[List[Dict[str, Any]], "AggregateRecordsQuery"]
    ) -> List[Account]:
        return self._get_service().aggregate(records)

    def build_accounts(self, records: List[Dict[str, Any]]) -> Dict[str, Account]:
        return self._get_service().build_accounts(records)

    def load_accounts_from_jsonl(
        self,
        request: Union["LoadAccountsRequest", str],
        limit: Optional[int] = None,
    ) -> Dict[str, Account]:
        return self._get_service().load_accounts_from_jsonl(request, limit=limit)

    def process_record(
        self, record: Union[Dict[str, Any], "ProcessRecordQuery"]
    ) -> "RecordProcessingResult":
        return self._get_service().process_record(record)

    def resolve_account_keys(
        self, record: Union[Dict[str, Any], BaseModel]
    ) -> List[str]:
        return self._get_service().resolve_account_keys(record)

    def detect_signals(
        self, features: Union["RecordFeatures", Dict[str, Any]]
    ) -> List[SecuritySignal]:
        return self._get_service().detect_signals(features)

    def extract_features(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return self._get_service().extract_features(record)

    def extract_vulnerability_features(
        self, vulns: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return self._get_service().extract_vulnerability_features(vulns)

    def get_asset_id(
        self, features: Union["RecordFeatures", Dict[str, Any]]
    ) -> Optional[Tuple[Optional[str], Optional[int], Optional[str]]]:
        return self._get_service().get_asset_id(features)


default_aggregator_service: IAggregatorService = _LazyAggregatorServiceProxy()
