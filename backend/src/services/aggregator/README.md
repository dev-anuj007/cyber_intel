# Aggregator Service

The **Aggregator Service** is a core telemetry processing and normalization engine in the Sales Intelligence Platform. It ingests raw network observations, port scans, and vulnerability feeds, extracts standardized security features, evaluates threat heuristics to detect actionable attack surface signals, and aggregates multi-asset telemetry into unified, deduplicated target account profiles.

---

## Architecture & Responsibilities

The service follows clean architecture and domain-driven design principles with strict dependency injection:

```mermaid
flowchart TD
    Ingest["Raw Network<br/>Telemetry"] --> Svc["Aggregator<br/>Service"]
    Svc --> Ctx["Dependency<br/>Context"]
    Ctx --> Logger["Logger<br/>Service"]
    Ctx --> Extractor["Feature<br/>Extractor"]
    Ctx --> Resolver["Account Key<br/>Resolver"]
    Ctx --> Detector["Signal<br/>Detector"]
    Ctx --> Reader["JSONL<br/>Reader"]
    Svc --> Builder["Account Builder<br/>& Buffer"]
    Builder --> Output["Target Account<br/>Profiles"]
```

### Module Breakdown

```text
aggregator/
├── __init__.py
├── aggregator_service.py       # Main domain service orchestrator
├── dependencies.py           # Dependency injection context & lazy singleton proxy
├── protocols.py              # Runtime checkable protocol interfaces (IAggregatorService)
├── README.md                 # Service documentation & architecture specs
├── types.py                  # Domain models, feature schemas & DTOs
├── internals/                # Specialized domain parsers, resolvers, and builders
│   ├── __init__.py
│   ├── builder.py            # Multi-record account aggregation buffer & builder
│   ├── constants.py          # Infrastructure and transit domain registries
│   ├── domain_utils.py       # Domain normalization, PTR detection, and root matching
│   ├── parsers.py            # IP formatting and vulnerability feature extraction
│   ├── resolvers.py          # Account key resolution and transit filtering
│   ├── signals.py            # Heuristic attack surface & threat signal detector
│   └── repositories/
│       ├── __init__.py
│       └── reader.py         # Streaming JSONL file reader
└── tests/                    # Pytest test suite for aggregator service
    ├── __init__.py
    └── test_aggregator_service.py
```

---

## Dataflow Diagrams (DFD) & Code Entry Points

### 1. Raw Telemetry Ingestion & Feature Extraction Flow

```mermaid
flowchart TD
    Raw["Raw Network<br/>Record"] --> Parse["Feature<br/>Extractor"]
    Parse --> IP["Format IPv4<br/>Address"]
    Parse --> HTTP["Extract Cloud<br/>& HTTP Headers"]
    Parse --> Vuln["Extract Vuln<br/>Metrics"]
    Vuln --> Metrics["Compute CVSS,<br/>EPSS & KEV"]
    Metrics --> Feat["Normalized<br/>Record Features"]
    IP --> Feat
    HTTP --> Feat
```

#### 🔍 Code Entry Points & Execution Trace
| Flow Step | Entry Function / Class | Source File | Description |
| :--- | :--- | :--- | :--- |
| **Service Entry Point** | `AggregatorService.extract_features(record)` | [`aggregator_service.py`](./aggregator_service.py) | Top-level service delegator for feature extraction. |
| **Feature Parser** | `FeatureExtractor.extract_features(record)` | [`internals/parsers.py`](./internals/parsers.py) | Parses network, port, product, OS, cloud, and HTTP headers. |
| **Vulnerability Aggregator** | `FeatureExtractor.extract_vulnerability_features(vulns)` | [`internals/parsers.py`](./internals/parsers.py) | Computes `max_cvss`, `max_epss`, `kev_count`, and `ransomware_count`. |
| **IP Normalizer** | `FeatureExtractor.format_ip(ip_val)` | [`internals/parsers.py`](./internals/parsers.py) | Converts integer IP or validates string IP into standard IPv4 format. |

---

### 2. Security Signal Detection & Attack Surface Heuristics Flow

```mermaid
flowchart TD
    Feat["Record<br/>Features"] --> SigDet["Signal<br/>Detector"]
    SigDet --> Tech["EOL Product<br/><b>HIGH</b>"]
    SigDet --> KEV["CISA KEV<br/><b>CRITICAL</b>"]
    SigDet --> CVSS["CVSS Score<br/><b>CRITICAL / HIGH</b>"]
    SigDet --> EPSS["High EPSS<br/><b>HIGH</b>"]
    SigDet --> Ransom["Ransomware<br/><b>CRITICAL</b>"]
    SigDet --> VulnCount["5+ Vulns<br/><b>MEDIUM</b>"]
    SigDet --> Ports["Non-Std Port<br/><b>LOW</b>"]
    Tech --> Signals["Security<br/>Signals List"]
    KEV --> Signals
    CVSS --> Signals
    EPSS --> Signals
    Ransom --> Signals
    VulnCount --> Signals
    Ports --> Signals
```

#### 🔍 Code Entry Points & Execution Trace
| Flow Step | Entry Function / Class | Source File | Description |
| :--- | :--- | :--- | :--- |
| **Service Entry Point** | `AggregatorService.detect_signals(features)` | [`aggregator_service.py`](./aggregator_service.py) | Accepts `RecordFeatures` or dictionary and delegates to detector. |
| **Signal Detector Hub** | `SignalDetector.detect_signals(features)` | [`internals/signals.py`](./internals/signals.py) | Coordinates technology, vulnerability, and port detection passes. |
| **Technology Risk Rule** | `SignalDetector._detect_technology_signals(features)` | [`internals/signals.py`](./internals/signals.py) | Flags end-of-life technologies and deprecated products. |
| **Vulnerability Risk Rules** | `SignalDetector._detect_vulnerability_signals(features)` | [`internals/signals.py`](./internals/signals.py) | Evaluates CISA KEV, EPSS exploitability, CVSS, and ransomware campaigns. |
| **Port Exposure Rule** | `SignalDetector._detect_port_signals(features)` | [`internals/signals.py`](./internals/signals.py) | Identifies non-standard exposed perimeter ports. |

---

### 3. Account Key Resolution & Multi-Asset Aggregation Flow

```mermaid
flowchart TD
    Record["Raw Record<br/>& Hostnames"] --> Res["Account Key<br/>Resolver"]
    Res --> Filter["Filter Transit<br/>& PTR Domains"]
    Filter --> Match["Match Hostnames<br/>to Root Domain"]
    Match --> Keys["Resolved<br/>Account Keys"]
    Keys --> Builder["Account<br/>Builder"]
    Builder --> Buffer["Account Buffer<br/><i>(Deduplicate)</i>"]
    Buffer --> Build["Build Account<br/>Entity"]
    Build --> Accounts["Unified Target<br/>Accounts"]
```

#### 🔍 Code Entry Points & Execution Trace
| Flow Step | Entry Function / Class | Source File | Description |
| :--- | :--- | :--- | :--- |
| **Batch Aggregation Entry** | `AggregatorService.aggregate(records)` | [`aggregator_service.py`](./aggregator_service.py) | Main entry point to convert a raw record batch into `List[Account]`. |
| **Account Dictionary Entry** | `AggregatorService.build_accounts(records)` | [`aggregator_service.py`](./aggregator_service.py) | Aggregates records and returns `Dict[account_key, Account]`. |
| **Single Record Processing** | `AggregatorService.process_record(record)` | [`aggregator_service.py`](./aggregator_service.py) | Evaluates one record returning keys, asset tuple, and signals. |
| **JSONL Ingestion Entry** | `AggregatorService.load_accounts_from_jsonl(request)` | [`aggregator_service.py`](./aggregator_service.py) | Streams a JSONL telemetry file from disk into unified accounts. |
| **Domain Key Resolver** | `AccountKeyResolver.resolve(record)` | [`internals/resolvers.py`](./internals/resolvers.py) | Resolves canonical target account domain keys. |
| **Domain Utilities & Transit Filter** | `internals/domain_utils.py` | [`internals/domain_utils.py`](./internals/domain_utils.py) | Normalizes domains, filters cloud/CDN transit domains and dynamic PTRs. |
| **Multi-Asset Buffer** | `AccountBuilder.add_record()` & `build()` | [`internals/builder.py`](./internals/builder.py) | Accumulates assets, deduplicates signals, and constructs `Account` objects. |
| **Streaming File Reader** | `JsonlReader.read(file_path, limit)` | [`internals/repositories/reader.py`](./internals/repositories/reader.py) | Line-by-line JSON reader with error handling. |

---

## Signal Heuristics & Rules Matrix

| Signal Name | Category | Severity | Detection Trigger Rule |
| :--- | :--- | :--- | :--- |
| `eol_product` | `technology_risk` | `HIGH` | Tag `eol-product` present in record tags |
| `kev_vulnerability` | `vulnerability` | `CRITICAL` | `kev_count > 0` (vulnerabilities present in CISA KEV catalog) |
| `high_severity_vulnerability` | `vulnerability` | `CRITICAL` / `HIGH` | `max_cvss >= 9.0` (CRITICAL), `max_cvss >= 7.0` (HIGH) |
| `high_exploitation_probability` | `vulnerability` | `HIGH` | `max_epss >= 0.50` (Exploit Prediction Scoring System) |
| `ransomware_associated_vulnerability` | `vulnerability` | `CRITICAL` | `ransomware_count > 0` (known association with active ransomware campaigns) |
| `multiple_vulnerabilities` | `vulnerability` | `MEDIUM` | `vulnerability_count >= 5` total CVEs on the asset |
| `non_standard_exposed_port` | `attack_surface` | `LOW` | Exposed port is not standard HTTP/S (`port not in {80, 443}`) |

---

## Domain Logic & Design Conventions

### 1. Pure Dependency Injection
The aggregator service accepts its dependency context directly:
```python
class AggregatorService(IAggregatorService):
    def __init__(
        self,
        context: Optional[AggregatorServiceDependencyContext] = None,
    ) -> None:
        self.context: AggregatorServiceDependencyContext = (
            context or get_aggregator_dependency_context()
        )
```

### 2. Method Ordering Standard
In every class across the service:
- **Public methods** are declared at the top of the class.
- **Private/internal helper methods** (`_` prefix) are grouped at the bottom under explicit section headers.

### 3. Lazy Singleton Proxy
To prevent import-time side effects and circular dependency chains, `dependencies.py` provides a thread-safe lazy proxy:
```python
from src.services.aggregator.dependencies import default_aggregator_service

# Instantiation is deferred until first method invocation
accounts = default_aggregator_service.aggregate(records)
```

### 4. DTO-First Contracts
All request and response payloads use Pydantic v2 schemas (`types.py`) with `model_config = ConfigDict(extra="ignore")`.

---

## Local Verification & Testing

To run the full suite of static analysis and unit tests:

```bash
# Type check the aggregator service
npx pyright src/services/aggregator

# Lint and verify PEP 8 compliance (max line length 88)
ruff check src/services/aggregator --line-length=88
ruff format --check src/services/aggregator --line-length=88

# Run automated tests
pytest src/services/aggregator/tests -v
```
