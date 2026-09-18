from typing import Optional, Dict
from src.services.crawler.types import ICrawlerReader


class CrawlerReader(ICrawlerReader):

    def __init__(self):
        self._cache: Dict[str, dict] = {}

    def get_cached_scan(self, domain: str) -> Optional[dict]:
        return self._cache.get(domain.lower().strip())
