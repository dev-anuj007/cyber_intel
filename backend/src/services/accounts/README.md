# Accounts Service

The **Accounts Service** is a core microservice in the Sales Intelligence Platform responsible for account inventory management, multi-version telemetry snapshots, attack-surface signal aggregation, automated priority tiering, and prospecting search.

---

## Architecture & Responsibilities

The service follows clean architecture and domain-driven design principles with strict dependency injection:

```mermaid
flowchart TD
    API["FastAPI Router - api.py"] --> Svc["AccountsService - accounts_service.py"]
    Lambda["AWS Lambda Handler - lambda_handler.py"] --> Svc
    Svc --> Ctx["AccountsServiceDependencyContext - dependencies.py"]
    Ctx --> Logger["Logger Service"]
    Ctx --> DB["Database Connection Pool"]
    Ctx --> Reader["AccountReader - internals/repositories/reader.py"]
    Ctx --> Writer["AccountWriter - internals/repositories/writer.py"]
```

### Module Breakdown

```text
accounts/
├── __init__.py
├── accounts_service.py       # Main domain service orchestrator
├── api.py                    # FastAPI route handlers & canonical routes
├── dependencies.py           # Dependency injection context & factory providers
├── Dockerfile                # AWS Lambda container definition
├── lambda_handler.py         # Serverless entry point for standalone execution
├── protocols.py              # Protocol interfaces (IAccountsService, IAccountReader, etc.)
├── README.md                 # Service documentation
├── types.py                  # Domain models, enums (PriorityTier, SignalSeverity) & DTOs
├── infra/                    # Declarative Pulumi infrastructure definition
│   └── main.py
├── internals/                # Low-level repository & SQL persistence layer
│   ├── __init__.py
│   └── repositories/
│       ├── __init__.py
│       ├── reader.py         # AccountReader database repository
│       ├── writer.py         # AccountWriter database repository
│       └── models/           # Relational SQL table entities
│           ├── __init__.py
│           └── account.py
└── tests/                    # Pytest test suite for service, repositories & API
    └── test_accounts_service.py
```

---

## Domain Logic & Design Conventions

### 1. Pure Dependency Injection
The service accepts a single required context object:
```python
class AccountsService(IAccountsService):
    def __init__(self, context: AccountsServiceDependencyContext):
        self.context = context
```
All external dependencies (`logger`, `reader`, `writer`, `get_connection()`) are managed and accessed via `self.context`.

### 2. DTO-First Contract
- Every service method accepts **at most 2 arguments** or a typed query DTO (e.g. `ListAccountsQuery`, `AccountsBySignalQuery`).
- Every service method returns a **typed response DTO** (e.g. `AccountsPaginatedResponse`, `AccountSearchResponse`, `SaveAccountResponse`, `SummaryStats`).

### 3. Automated Priority Tiering
The service automatically evaluates account telemetry to compute a `PriorityTier`:

- **`TIER_1_CRITICAL`** (`tier_1_critical`): Account has at least one signal with `SignalSeverity.CRITICAL`.
- **`TIER_2_HIGH`** (`tier_2_high`): Account has `SignalSeverity.HIGH` and $\ge 2$ total signals.
- **`TIER_3_MEDIUM`** (`tier_3_medium`): Account has `SignalSeverity.HIGH` with 1 signal OR any medium/low signals ($>0$ signals).
- **`TIER_4_LOW`** (`tier_4_low`): Account has 0 signals.

### 4. Multi-Version Snapshot Resolution
Accounts are keyed by domain (e.g. `domain:acme.corp`) and support immutable version snapshots (`v1`, `v2`, ...). 
- Querying by domain without a version returns the **latest snapshot** with score resolution.
- Querying with a specific version (`version="v1"`) returns that exact historical snapshot.

### 5. Lazy Singleton Proxy (`_LazyAccountsServiceProxy`)
The module exposes `default_accounts_service` backed by `_LazyAccountsServiceProxy`:
- **Zero Import-Time Side Effects**: Prevents eager database connections or logger initialization during module import.
- **Prevents Circular Imports**: Eliminates import deadlocks when other services (e.g. `scorer`, `crawler`) cross-reference accounts.
- **Test Isolation & Ergonomics**: Provides clean syntax for callers while allowing test fixtures to override dependencies before runtime execution.

---

## API Reference

All endpoints are mounted under `/api/accounts`:

| Method | Route | Description |
| :--- | :--- | :--- |
| `GET` | `/api/accounts/summary` | Aggregate statistics across priority tiers and critical signals. |
| `GET` | `/api/accounts/search` | Search accounts by domain prefix or keyword. |
| `GET` | `/api/accounts/signal/{signal_name}` | List accounts affected by a specific vulnerability or signal. |
| `GET` | `/api/accounts` | Paginated account list with tier and signal filters. |
| `GET` | `/api/accounts/{account_key}` | Get detailed account record with resolved latest AI score. |
| `GET` | `/api/accounts/{account_key}/versions` | List all historical scan versions for an account. |
| `GET` | `/api/accounts/{account_key}/score-history` | Retrieve historical AI score runs for an account. |
| `GET` | `/api/accounts/health` | Health check and total account count. |
| `DELETE` | `/api/accounts/{account_key}` | Delete an account and its associated entities. |

---

## End-to-End Dataflow Diagrams

### 1. Account Ingestion & Automated Priority Tiering Dataflow
Dataflow when raw security telemetry is ingested, classified, and persisted:

```mermaid
flowchart LR
    subgraph Input["1. Input Ingestion"]
        InPayload["Raw Ingestion Payload<br/>Account / InsertAccountCommand"]
    end

    subgraph Tiering["2. Automated Priority Classification"]
        SaveSvc["AccountsService.save_account()"]
        ComputeTier["compute_priority_tier()"]
        Eval{"Evaluate Signal Telemetry"}
        T1["Tier 1 (Critical)"]
        T2["Tier 2 (High)"]
        T3["Tier 3 (Medium)"]
        T4["Tier 4 (Low)"]
    end

    subgraph Persistence["3. Database Persistence"]
        Writer["AccountWriter.insert_account()"]
        DB[("PostgreSQL Database<br/>accounts / assets / signals")]
    end

    subgraph Output["4. Result Contract"]
        Resp["SaveAccountResponse<br/>(success=True, account_id, tier)"]
    end

    InPayload --> SaveSvc
    SaveSvc --> ComputeTier
    ComputeTier --> Eval
    Eval -->|"has critical signal"| T1
    Eval -->|"high severity + >= 2 signals"| T2
    Eval -->|"high / med / low signals"| T3
    Eval -->|"0 signals"| T4
    T1 & T2 & T3 & T4 --> Writer
    Writer --> DB
    DB --> Resp
```

### 2. Account Detail & AI Score Resolution Dataflow (`GET /api/accounts/{account_key}`)
Dataflow when querying an account and dynamically hydrating historical scan snapshots and AI scores:

```mermaid
flowchart LR
    subgraph ClientReq["1. HTTP Request"]
        Req["GET /api/accounts/{account_key}?version={v}"]
    end

    subgraph ServiceLayer["2. Service Orchestration"]
        Route["FastAPI Route Handler"]
        Svc["AccountsService.get_account()"]
        Reader["AccountReader.load_account()"]
    end

    subgraph DataStore["3. Data Stores & Services"]
        DB[("PostgreSQL Database")]
        Scorer["Scorer Service (IScorerService)"]
    end

    subgraph ClientResp["4. Hydrated Response"]
        AccountDTO["Hydrated Account DTO<br/>(Domains, Assets, Signals, AI Score)"]
    end

    Req --> Route
    Route --> Svc
    Svc --> Reader
    Reader --> DB
    DB -->|"Raw account snapshot"| Reader
    Reader -->|"Domain model"| Svc
    Svc --> Route
    Route -->|"Resolve missing AI score"| Scorer
    Scorer --> DB
    DB -->|"Score record"| Scorer
    Scorer -->|"Hydrate latest score"| AccountDTO
```

### 3. Prospecting Search & Filtered Listing Dataflow (`GET /api/accounts`, `GET /api/accounts/search`)
Dataflow for paginated priority tier filtering and domain search queries:

```mermaid
flowchart LR
    subgraph ClientReqs["1. Request Queries"]
        ReqList["GET /api/accounts<br/>(tier, has_critical, pagination)"]
        ReqSearch["GET /api/accounts/search<br/>(prefix / keyword query)"]
    end

    subgraph QueryExecution["2. Repository Execution"]
        ListSvc["list_accounts(ListAccountsQuery)"]
        SearchSvc["search_accounts(query, limit)"]
        Reader["AccountReader"]
    end

    subgraph DBQueries["3. PostgreSQL Index Queries"]
        StatsQuery[("Summary Stats & Metrics")]
        IndexScan[("Tier / Domain Prefix Index Scan")]
        BatchFetch[("Account Summary Batch Fetch")]
    end

    subgraph Responses["4. Response Models"]
        ListOut["AccountsPaginatedResponse<br/>(items, total, page, pages)"]
        SearchOut["AccountSearchResponse<br/>(query, total, results)"]
    end

    ReqList --> ListSvc
    ReqSearch --> SearchSvc
    ListSvc --> Reader
    SearchSvc --> Reader
    Reader --> StatsQuery
    Reader --> IndexScan
    IndexScan --> BatchFetch
    BatchFetch --> ListOut
    BatchFetch --> SearchOut
```

---

## Testing & Quality Assurance

### 1. Run Unit & Integration Tests
```powershell
pytest src/services/accounts/tests -v
```

### 2. Code Coverage Report
Measure branch and line coverage across the accounts service domain:
```powershell
pytest src/services/accounts/tests -v --cov=src.services.accounts --cov-report=term-missing --cov-report=html
```

### 3. Static Type Checking (Pyright)
Ensure 100% strict type safety across protocol interfaces, models, and service classes:
```powershell
npx pyright src/services/accounts
```

### 4. Code Formatting & Linting (Ruff - PEP 8)
Check and enforce PEP 8 style guidelines with a max line length of 88 characters:

```powershell
# Check for lint issues and import sorting
ruff check src/services/accounts --line-length=88

# Automatically fix lint issues
ruff check src/services/accounts --line-length=88 --fix

# Check formatting without modifying files
ruff format src/services/accounts --line-length=88 --check

# Format all code to PEP 8 standard
ruff format src/services/accounts --line-length=88
```

---

## Local Development & Microservice Execution

### Run as Standalone Microservice
You can run the accounts service independently using Uvicorn and its dedicated `lambda_handler.py`:

```powershell
uvicorn src.services.accounts.lambda_handler:app --reload --port 8001
```

### Health Check
```powershell
curl http://localhost:8001/health
```

---

## Containerization & Deployment

### 1. Build & Run with Docker
The accounts service includes a standalone AWS Lambda-compatible container definition (`Dockerfile`):

```powershell
# Build container image
docker build -f src/services/accounts/Dockerfile -t accounts-microservice:latest .

# Run container locally with RIE (Runtime Interface Emulator)
docker run -p 9000:8080 --env-file backend/.env accounts-microservice:latest
```

### 2. Infrastructure as Code & Service Deployment

#### Deploy ONLY the Accounts Microservice
To build, push to ECR, and deploy only the Accounts Lambda function without touching other services:

```powershell
# Windows PowerShell
.\src\services\infra\deploy.ps1 -Service accounts -Stack dev

# macOS / Linux
./src/services/infra/deploy.sh -s accounts --stack dev
```

#### Deploy Entire Stack (All Services + Database + Frontend)
To provision or update the complete infrastructure across all microservices:

```powershell
cd src/services/infra
pulumi up --stack dev
```
