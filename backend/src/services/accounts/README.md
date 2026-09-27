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
When crawlers or external feeds push raw scan data into the accounts service:

```mermaid
sequenceDiagram
    autonumber
    participant Client as Ingestion / Crawler Client
    participant API as FastAPI Router (api.py)
    participant Svc as AccountsService
    participant Tier as Tiering Engine (compute_priority_tier)
    participant Writer as AccountWriter
    participant DB as PostgreSQL Database

    Client->>API: Save Account Payload (JSON / DTO)
    API->>Svc: save_account(Account | InsertAccountCommand)
    Svc->>Tier: compute_priority_tier(account)
    Note over Tier: Evaluates Signals<br/>CRITICAL -> Tier 1<br/>HIGH (>=2) -> Tier 2<br/>HIGH/MED/LOW -> Tier 3<br/>None -> Tier 4
    Tier-->>Svc: PriorityTier Enum
    Svc->>Writer: insert_account(conn, account, tier)
    Writer->>DB: INSERT INTO accounts / assets / signals
    DB-->>Writer: Account DB Record ID
    Writer-->>Svc: account_id
    Svc->>DB: conn.commit()
    Svc-->>API: SaveAccountResponse(success=True, account_id, tier)
    API-->>Client: 200 OK (SaveAccountResponse)
```

### 2. Account Detail & AI Score Resolution Dataflow (`GET /api/accounts/{account_key}`)
When a user or frontend views an account's detail view:

```mermaid
sequenceDiagram
    autonumber
    participant UI as React Frontend / Client
    participant API as FastAPI Router (api.py)
    participant Svc as AccountsService
    participant Reader as AccountReader
    participant DB as PostgreSQL Database
    participant Scorer as Scorer Service (IScorerService)

    UI->>API: GET /api/accounts/{account_key}?version={v}
    API->>Svc: get_account(account_key, version)
    Svc->>Reader: load_account(conn, account_key, version)
    Reader->>DB: SELECT account, assets, signals, versions
    DB-->>Reader: Raw Account Record
    Reader-->>Svc: Hydrated Account Domain Model
    Svc-->>API: Account Model
    alt Account has no cached AI score
        API->>Scorer: get_latest_score_for_account(account_key)
        Scorer->>DB: SELECT latest AI score from scores table
        DB-->>Scorer: Score record
        Scorer-->>API: AccountScore
        API->>API: Attach latest_score to Account
    end
    API-->>UI: 200 OK (Account DTO with AI Score)
```

### 3. Prospecting Search & Filtered Listing Dataflow (`GET /api/accounts`, `GET /api/accounts/search`)

```mermaid
sequenceDiagram
    autonumber
    participant UI as Prospecting Dashboard UI
    participant API as FastAPI Router (api.py)
    participant Svc as AccountsService
    participant Reader as AccountReader
    participant DB as PostgreSQL Database

    alt Filtered Account List (/api/accounts)
        UI->>API: GET /api/accounts?priority_tier=tier_1_critical&skip=0&limit=25
        API->>Svc: list_accounts(ListAccountsQuery)
        Svc->>Reader: get_summary_stats(conn)
        Reader->>DB: SELECT tier counts & signal metrics
        DB-->>Reader: Summary Stats
        Svc->>Reader: get_accounts_by_tier(conn, tier, skip, limit)
        Reader->>DB: SELECT account keys by tier (Paginated)
        DB-->>Reader: Account Keys & Total Count
        Svc->>Reader: load_accounts_summary_batch(conn, keys)
        Reader->>DB: SELECT summary rows for keys
        DB-->>Reader: Batch Summaries
        Svc-->>API: AccountsPaginatedResponse(items, total, page, pages)
    else Prefix / Domain Search (/api/accounts/search)
        UI->>API: GET /api/accounts/search?q=acme&limit=10
        API->>Svc: search_accounts(query="acme", limit=10)
        Svc->>Reader: search_accounts_by_domain(conn, query, limit)
        Reader->>DB: SELECT keys matching domain prefix
        DB-->>Reader: Matching Keys
        Svc->>Reader: load_accounts_summary_batch(conn, keys)
        Reader->>DB: SELECT summary rows for keys
        DB-->>Reader: Batch Summaries
        Svc-->>API: AccountSearchResponse(query, total, results)
    end
    API-->>UI: 200 OK (JSON Response)
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
