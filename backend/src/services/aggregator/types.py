"""Aggregator Service types, interfaces, and dataclasses."""

from typing import Protocol, List, Dict, Optional, Tuple
from src.services.accounts.types import Account, SecuritySignal


class IAggregatorService(Protocol):
    """Aggregator interface defining asset grouping and signal detection contracts."""

    def resolve_account_keys(self, record: dict) -> List[str]:
        ...

    def get_asset_id(self, features: dict) -> Optional[Tuple[str, Optional[int], Optional[str]]]:
        ...

    def extract_vulnerability_features(self, vulns: Optional[dict]) -> dict:
        ...

    def extract_features(self, record: dict) -> dict:
        ...

    def detect_signals(self, features: dict) -> List[SecuritySignal]:
        ...

    def build_accounts(self, records: List[dict]) -> Dict[str, Account]:
        ...

    def load_accounts_from_jsonl(self, jsonl_path: str, limit: Optional[int] = None) -> Dict[str, Account]:
        ...
