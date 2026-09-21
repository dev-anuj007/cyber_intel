from typing import Dict

from src.services.crawler.types import ICrawlerWriter


class CrawlerWriter(ICrawlerWriter):
    def __init__(self):
        self._cache: Dict[str, dict] = {}

    def cache_scan(self, domain: str, scan_data: dict) -> None:
        self._cache[domain.lower().strip()] = scan_data
