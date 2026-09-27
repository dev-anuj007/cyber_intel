from typing import Dict, List, Optional, Set, Tuple

from src.services.accounts.types import Account, Asset, SecuritySignal


class _AccountBuffer:
    def __init__(self, account_key: str):
        self.account_key = account_key
        self.domain = account_key.replace("domain:", "")
        self.domains: List[str] = [self.domain] if self.domain else []
        self.assets: List[Asset] = []
        self._asset_keys: Set[Tuple[Optional[str], Optional[int], Optional[str]]] = set()
        self.ips: List[str] = []
        self._ip_set: Set[str] = set()
        self.hostnames: List[str] = []
        self._hostname_set: Set[str] = set()
        self.ports: List[int] = []
        self._port_set: Set[int] = set()
        self.products: List[str] = []
        self._product_set: Set[str] = set()
        self.cloud_providers: List[str] = []
        self._cloud_set: Set[str] = set()
        self.signals: List[SecuritySignal] = []
        self._signal_keys: Set[Tuple[str, str, str, str]] = set()

    def add_asset(self, asset_id: Optional[Tuple[Optional[str], Optional[int], Optional[str]]]) -> None:
        if not asset_id:
            return
        ip, port, asset_host = asset_id
        if not asset_host or asset_host == self.domain or asset_host.endswith("." + self.domain):
            key = (ip, port, asset_host)
            if key not in self._asset_keys:
                self._asset_keys.add(key)
                self.assets.append(Asset(ip=ip, port=port, hostname=asset_host))

    def add_features(self, features: dict) -> None:
        ip = features.get("ip")
        if ip and ip not in self._ip_set:
            self._ip_set.add(ip)
            self.ips.append(ip)

        hostname = features.get("hostname")
        if hostname and (hostname == self.domain or hostname.endswith("." + self.domain)):
            if hostname not in self._hostname_set:
                self._hostname_set.add(hostname)
                self.hostnames.append(hostname)

        port = features.get("port")
        if port is not None and port not in self._port_set:
            self._port_set.add(port)
            self.ports.append(port)

        product = features.get("product")
        if product and product not in self._product_set:
            self._product_set.add(product)
            self.products.append(product)

        cloud_provider = features.get("cloud_provider")
        if cloud_provider and cloud_provider not in self._cloud_set:
            self._cloud_set.add(cloud_provider)
            self.cloud_providers.append(cloud_provider)

    def add_signals(self, signals: List[SecuritySignal]) -> None:
        for s in signals:
            s_sev = s.severity if isinstance(s.severity, str) else s.severity.value
            s_key = (s.name, s_sev, s.category, s.evidence)
            if s_key not in self._signal_keys:
                self._signal_keys.add(s_key)
                self.signals.append(s)

    def to_account(self) -> Account:
        return Account(
            account_key=self.account_key,
            domains=list(self.domains),
            assets=list(self.assets),
            ips=list(self.ips),
            hostnames=list(self.hostnames),
            ports=list(self.ports),
            products=list(self.products),
            cloud_providers=list(self.cloud_providers),
            signals=list(self.signals),
        )


class AccountBuilder:
    def __init__(self) -> None:
        self._buffers: Dict[str, _AccountBuffer] = {}

    def get_or_create(self, account_key: str) -> _AccountBuffer:
        if account_key not in self._buffers:
            self._buffers[account_key] = _AccountBuffer(account_key)
        return self._buffers[account_key]

    def add_record(
        self,
        account_key: str,
        asset_id: Optional[Tuple[Optional[str], Optional[int], Optional[str]]],
        features: dict,
        signals: List[SecuritySignal],
    ) -> None:
        buffer = self.get_or_create(account_key)
        buffer.add_asset(asset_id)
        buffer.add_features(features)
        buffer.add_signals(signals)

    def build(self) -> Dict[str, Account]:
        return {key: buffer.to_account() for key, buffer in self._buffers.items()}
