from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from src.services.aggregator.internals.parsers import FeatureExtractor
from src.services.aggregator.internals.repositories.reader import JsonlReader
from src.services.aggregator.internals.resolvers import AccountKeyResolver
from src.services.aggregator.internals.signals import SignalDetector
from src.services.aggregator.protocols import IAggregatorService
from src.services.logger.logger_service import BaseLogger, get_logger



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


def get_aggregator_service() -> IAggregatorService:
    from src.services.aggregator.aggregator_service import AggregatorService

    return AggregatorService(context=get_aggregator_dependency_context())


def create_aggregator_service(
    context: Optional[AggregatorServiceDependencyContext] = None,
) -> IAggregatorService:
    from src.services.aggregator.aggregator_service import AggregatorService

    return AggregatorService(context=context or get_aggregator_dependency_context())

