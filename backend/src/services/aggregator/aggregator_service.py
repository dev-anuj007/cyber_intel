from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel

from src.services.accounts.types import Account, SecuritySignal
from src.services.aggregator.dependencies import (
    AggregatorServiceDependencyContext,
    get_aggregator_dependency_context,
)
from src.services.aggregator.internals.builder import AccountBuilder
from src.services.aggregator.protocols import IAggregatorService
from src.services.aggregator.types import (
    AggregateRecordsQuery,
    LoadAccountsRequest,
    ProcessRecordQuery,
    RecordFeatures,
    RecordProcessingResult,
)


class AggregatorService(IAggregatorService):
    def __init__(
        self,
        context: Optional[AggregatorServiceDependencyContext] = None,
    ) -> None:
        self.context: AggregatorServiceDependencyContext = (
            context or get_aggregator_dependency_context()
        )

    def aggregate(
        self, records: Union[List[Dict[str, Any]], AggregateRecordsQuery]
    ) -> List[Account]:
        raw_records = (
            records.records if isinstance(records, AggregateRecordsQuery) else records
        )
        accounts_dict = self.build_accounts(raw_records)
        return list(accounts_dict.values())

    def build_accounts(self, records: List[Dict[str, Any]]) -> Dict[str, Account]:
        with self.context.logger.span(
            "aggregator.build_accounts", input_records=len(records)
        ):
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

    def load_accounts_from_jsonl(
        self, request: Union[LoadAccountsRequest, str], limit: Optional[int] = None
    ) -> Dict[str, Account]:
        if isinstance(request, LoadAccountsRequest):
            jsonl_path = request.jsonl_path
            req_limit = request.limit
        else:
            jsonl_path = request
            req_limit = limit

        with self.context.logger.span(
            "aggregator.load_jsonl", path=jsonl_path, limit=req_limit
        ):
            records = self.context.reader.read(jsonl_path, limit=req_limit)
            return self.build_accounts(records)

    def process_record(
        self, record: Union[Dict[str, Any], ProcessRecordQuery]
    ) -> RecordProcessingResult:
        raw_record = record.record if isinstance(record, ProcessRecordQuery) else record
        features = self.extract_features(raw_record)
        signals = self.detect_signals(features)
        account_keys = self.resolve_account_keys(raw_record)
        asset_id = self.get_asset_id(features)
        return RecordProcessingResult(
            account_keys=account_keys,
            asset_id=asset_id,
            signals=signals,
        )

    def resolve_account_keys(
        self, record: Union[Dict[str, Any], BaseModel]
    ) -> List[str]:
        if isinstance(record, BaseModel):
            record_dict = record.model_dump()
        elif isinstance(record, dict):
            record_dict = dict(record)
        else:
            record_dict = {}
        return self.context.key_resolver.resolve(record_dict)

    def detect_signals(
        self, features: Union[RecordFeatures, Dict[str, Any]]
    ) -> List[SecuritySignal]:
        if isinstance(features, RecordFeatures):
            feature_dict = features.model_dump()
        else:
            feature_dict = features
        return self.context.signal_detector.detect_signals(feature_dict)

    def extract_features(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return self.context.feature_extractor.extract_features(record)

    def extract_vulnerability_features(
        self, vulns: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return self.context.feature_extractor.extract_vulnerability_features(vulns)

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
