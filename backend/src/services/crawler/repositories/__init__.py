"""Crawler Repositories Package."""

from src.services.crawler.repositories.reader import CrawlerReader
from src.services.crawler.repositories.writer import CrawlerWriter

__all__ = [
    "CrawlerReader",
    "CrawlerWriter",
]
