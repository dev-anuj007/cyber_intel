# Aggregator Service

The **Aggregator Service** is a core telemetry processing and normalization engine in the Sales Intelligence Platform. It ingests raw network observations, port scans, and vulnerability feeds, extracts standardized security features, evaluates threat heuristics to detect actionable attack surface signals, and aggregates multi-asset telemetry into unified, deduplicated target account profiles.

---

## Architecture & Responsibilities

The service follows clean architecture and domain-driven design principles with strict dependency injection:

```mermaid
flowchart TD
    Ingest["Raw Telemetry / JSONL Feeds"] --> Svc["AggregatorService<br/><code>aggregator_service.py</code>"]
    Svc --> Ctx["Dependency Context<br/><code>dependencies.py</code>"]
    Ctx --> Logger["BaseLogger"]
    Ctx --> Extractor["FeatureExtractor<br/><code>internals/parsers.py</code>"]
    Ctx --> Resolver["AccountKeyResolver<br/><code>internals/resolvers.py</code>"]
    Ctx --> Detector["SignalDetector<br/><code>internals/signals.py</code>"]
    Ctx --> Reader["JsonlReader<br/><code>internals/repositories/reader.py</code>"]
    Svc --> Builder["AccountBuilder & _AccountBuffer<br/><code>internals/builder.py</code>"]
    Builder --> Output["Normalized Account Profiles<br/><code>Account (types.py)</code>"]
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
    Raw["Raw Shodan / Network Record<br/><i>(Dict / ProcessRecordQuery)</i>"] --> Parse["FeatureExtractor.extract_features()<br/><i>(internals/parsers.py)</i>"]
    Parse --> IP["Format IP Address<br/><i>(int to IPv4 string)</i>"]
    Parse --> HTTP["Extract HTTP status, server,<br/>cloud provider, and tags"]
    Parse --> Vuln["FeatureExtractor<br/>.extract_vulnerability_features()<br/><i>(internals/parsers.py)</i>"]
    Vuln --> Metrics["Compute vulnerability_count, max_cvss,<br/>max_epss, kev_count, ransomware_count"]
    Metrics --> Feat["RecordFeatures / Dict Output<br/><i>(Standardized Feature Map)</i>"]
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
    Feat["RecordFeatures / Dict<br/><i>(Standardized Feature Map)</i>"] --> SigDet["SignalDetector.detect_signals()<br/><i>(internals/signals.py)</i>"]
    SigDet --> Tech["Check tags (e.g. 'eol-product')<br/>&rarr; <b>HIGH: eol_product</b>"]
    SigDet --> KEV["Check kev_count > 0<br/>&rarr; <b>CRITICAL: kev_vulnerability</b>"]
    SigDet --> CVSS["Check max_cvss<br/>&ge; 9.0 CRITICAL | &ge; 7.0 HIGH<br/>&rarr; <b>high_severity_vulnerability</b>"]
    SigDet --> EPSS["Check max_epss &ge; 0.50<br/>&rarr; <b>HIGH: high_exploitation_probability</b>"]
    SigDet --> Ransom["Check ransomware_campaign != null<br/>&rarr; <b>CRITICAL: ransomware_associated_vulnerability</b>"]
    SigDet --> VulnCount["Check vulnerability_count &ge; 5<br/>&rarr; <b>MEDIUM: multiple_vulnerabilities</b>"]
    SigDet --> Ports["Check port not in (80, 443)<br/>&rarr; <b>LOW: non_standard_exposed_port</b>"]
    Tech --> Signals["List of SecuritySignal Entities<br/><i>(Name, Severity, Category, Evidence)</i>"]
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
    Record["Raw Record + Candidate Domains + Hostnames"] --> Res["AccountKeyResolver.resolve()<br/><i>(internals/resolvers.py)</i>"]
    Res --> Filter["Filter Transit & PTR Domains<br/><i>(internals/domain_utils.py)</i>"]
    Filter --> Match["extract_root_domain_match()<br/><i>(Match hostnames against root domains)</i>"]
    Match --> Keys["Resolved Account Keys<br/><i>(e.g., 'domain:acme.com')</i>"]
    Keys --> Builder["AccountBuilder.add_record()<br/><i>(internals/builder.py)</i>"]
    Builder --> Buffer["_AccountBuffer<br/><i>(Deduplicates IPs, Ports, Hostnames, Signals)</i>"]
    Buffer --> Build["AccountBuilder.build()<br/><i>(Converts buffers to Account instances)</i>"]
    Build --> Accounts["Dict[str, Account] Unified Targets<br/><i>(Or List[Account] via aggregate)</i>"]
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
