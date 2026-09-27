from typing import Any, Dict, List, Optional, Tuple, Union

from src.services.accounts.types import Account, SecuritySignal
from src.services.aggregator.dependencies import (
    AggregatorServiceDependencyContext,
    get_aggregator_dependency_context,
)
from src.services.aggregator.internals.builder import AccountBuilder
from src.services.aggregator.internals.parsers import FeatureExtractor
from src.services.aggregator.internals.repositories.reader import JsonlReader
from src.services.aggregator.internals.resolvers import AccountKeyResolver
from src.services.aggregator.internals.signals import SignalDetector
from src.services.aggregator.protocols import IAggregatorService
from src.services.aggregator.types import (
    LoadAccountsRequest,
    RecordFeatures,
)
from src.services.logger.logger_service import BaseLogger


class AggregatorService(IAggregatorService):
    def __init__(self, context: Optional[AggregatorServiceDependencyContext] = None):
        ctx = context or get_aggregator_dependency_context()
        self._feature_extractor: FeatureExtractor = ctx.feature_extractor
        self._signal_detector: SignalDetector = ctx.signal_detector
        self._key_resolver: AccountKeyResolver = ctx.key_resolver
        self._reader: JsonlReader = ctx.reader
        self._logger: BaseLogger = ctx.logger

    @property
    def feature_extractor(self) -> FeatureExtractor:
        return self._feature_extractor

    @property
    def signal_detector(self) -> SignalDetector:
        return self._signal_detector

    @property
    def key_resolver(self) -> AccountKeyResolver:
        return self._key_resolver

    @property
    def reader(self) -> JsonlReader:
        return self._reader

    def resolve_account_keys(self, record: Union[Dict[str, Any], Any]) -> List[str]:
        if hasattr(record, "model_dump"):
            record_dict = record.model_dump()
        else:
            record_dict = dict(record) if isinstance(record, dict) else {}
        return self._key_resolver.resolve(record_dict)

    def get_asset_id(
        self, features: Union[RecordFeatures, Dict[str, Any]]
    ) -> Optional[Tuple[Optional[str], Optional[int], Optional[str]]]:
        if isinstance(features, RecordFeatures):
            ip = features.ip
            port = features.port
            hostname = features.hostname
        elif isinstance(features, dict):
            ip = features.get("ip")
            port = features.get("port")
            hostname = features.get("hostname")
        else:
            return None

        if not ip and not hostname:
            return None

        return (ip, port, hostname)

    def extract_vulnerability_features(self, vulns: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return self._feature_extractor.extract_vulnerability_features(vulns)

    def extract_features(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return self._feature_extractor.extract_features(record)

    def detect_signals(self, features: Union[RecordFeatures, Dict[str, Any]]) -> List[SecuritySignal]:
        feature_dict = features.model_dump() if isinstance(features, RecordFeatures) else features
        return self._signal_detector.detect_signals(feature_dict)

    def process_record(
        self, record: Dict[str, Any]
    ) -> Tuple[
        List[str],
        Optional[Tuple[Optional[str], Optional[int], Optional[str]]],
        List[SecuritySignal],
    ]:
        features = self.extract_features(record)
        signals = self.detect_signals(features)
        account_keys = self.resolve_account_keys(record)
        asset_id = self.get_asset_id(features)
        return account_keys, asset_id, signals

    def build_accounts(self, records: List[Dict[str, Any]]) -> Dict[str, Account]:
        with self._logger.span("aggregator.build_accounts", input_records=len(records)):
            builder = AccountBuilder()

            for record in records:
                features = self.extract_features(record)
                signals = self.detect_signals(features)
                account_keys = self.resolve_account_keys(record)

                if not account_keys:
                    continue

                asset_id = self.get_asset_id(features)

                for account_key in account_keys:
                    builder.add_record(
                        account_key=account_key,
                        asset_id=asset_id,
                        features=features,
                        signals=signals,
                    )

            return builder.build()

    def aggregate(self, records: List[Dict[str, Any]]) -> List[Account]:
        accounts_dict = self.build_accounts(records)
        return list(accounts_dict.values())

    def load_accounts_from_jsonl(
        self, request: Union[LoadAccountsRequest, str], limit: Optional[int] = None
    ) -> Dict[str, Account]:
        if isinstance(request, LoadAccountsRequest):
            jsonl_path = request.jsonl_path
            req_limit = request.limit
        else:
            jsonl_path = request
            req_limit = limit

        with self._logger.span("aggregator.load_jsonl", path=jsonl_path, limit=req_limit):
            records = self._reader.read(jsonl_path, limit=req_limit)
            return self.build_accounts(records)
