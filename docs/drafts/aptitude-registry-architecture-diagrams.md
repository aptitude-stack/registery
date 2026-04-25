# Aptitude Registry Architecture

> Status: draft/context document, not the canonical live contract.
> Use [`../architecture/system-overview.md`](../architecture/system-overview.md),
> [`../architecture/server-resolver-boundary.md`](../architecture/server-resolver-boundary.md),
> and [`../reference/api-contract.md`](../reference/api-contract.md) for the live baseline.

This diagram set shows the current `Aptitude Registry` shape and the planned
post-launch discovery extension from Plan 15.

## 1. Server System View

The interface is intentionally split into discovery, resolution, and fetch
instead of one generic read endpoint:

- Discovery is search-shaped load and should stay bound to compact ranking
  projections.
- Resolution is graph-shaped load and should read only authored selector edges.
- Fetch is payload-shaped load and can optimize for immutable metadata/content
  delivery and caching.

That separation keeps index-heavy candidate generation, lightweight dependency
reads, and heavier content retrieval from competing on the same path.

```mermaid
flowchart LR

    Publisher["Publisher Tooling<br/>metadata + .tar.zst bundle<br/>optional provenance"]
    Resolver["aptitude-resolver / MCP / CLI<br/>prompt interpretation<br/>reranking + final selection<br/>dependency solving + lock generation"]
    Ops["Ops / observability<br/>health probes<br/>metrics scrape<br/>logs + runbooks"]

    subgraph Server["Aptitude Registry"]
        direction TB

        Main["app/main.py<br/>composition root"]

        subgraph Interface["Interface Layer"]
            direction LR
            Health["GET /healthz<br/>GET /readyz<br/>GET /metrics"]
            Publish["POST /skills/{slug}<br/>PATCH lifecycle status"]
            Discovery["POST /discovery<br/>ordered slug candidates"]
            Resolution["GET /resolution/{slug}/{version}<br/>exact first-degree reads"]
            Fetch["GET /skills/{slug}<br/>GET /skills/{slug}/{version}<br/>GET /content"]
        end

        subgraph Core["Core Layer"]
            direction LR
            RegistrySvc["SkillRegistryService"]
            DiscoverySvc["SkillDiscoveryService"]
            ResolutionSvc["SkillResolutionService"]
            FetchSvc["SkillFetchService"]
            Governance["GovernancePolicy"]
            AuditEvents["Audit event builders"]
            Ports["Ports / contracts"]
        end

        subgraph Infra["Infrastructure Layer"]
            direction LR

            subgraph Persistence["Persistence"]
                direction TB
                Repo["SQLAlchemySkillRegistryRepository"]
                Models["ORM models<br/>skill<br/>skill_version<br/>skill_content<br/>skill_metadata<br/>skill_relationship_selector<br/>skill_search_document"]
            end

            subgraph Audit["Audit Adapter"]
                direction TB
                AuditRecorder["SQLAlchemyAuditRecorder"]
            end

            subgraph OptionalWorkers["Optional Post-Launch Workers"]
                direction TB
                EmbedIndexer["Embedding indexer<br/>(Plan 15)"]
                CoUsageRefresh["Co-usage refresh job<br/>(Plan 15)"]
            end
        end
    end

    subgraph Data["PostgreSQL"]
        direction TB
        Canonical[("Canonical registry tables<br/>versions, metadata, content,<br/>selectors, provenance")]
        Lexical[("Lexical discovery read model<br/>skill_search_documents")]
        AuditTable[("audit_events")]
        Semantic[("Semantic discovery read model<br/>skill_search_embeddings<br/>(Plan 15 optional)")]
        CoUsage[("Co-usage aggregates<br/>skill_co_usage_pairs<br/>(Plan 15 optional)")]
    end

    Publisher -->|"publish version"| Publish
    Resolver -->|"candidate retrieval"| Discovery
    Resolver -->|"exact relationship reads"| Resolution
    Resolver -->|"exact metadata/content fetch"| Fetch
    Ops <-->|"health / readiness / metrics"| Health

    Main --> Health
    Main --> Publish
    Main --> Discovery
    Main --> Resolution
    Main --> Fetch

    Publish --> RegistrySvc
    Discovery --> DiscoverySvc
    Resolution --> ResolutionSvc
    Fetch --> FetchSvc

    RegistrySvc --> Governance
    DiscoverySvc --> Governance
    ResolutionSvc --> Governance
    FetchSvc --> Governance

    RegistrySvc --> AuditEvents
    DiscoverySvc --> AuditEvents
    ResolutionSvc --> AuditEvents
    FetchSvc --> AuditEvents

    RegistrySvc --> Ports
    DiscoverySvc --> Ports
    ResolutionSvc --> Ports
    FetchSvc --> Ports

    Ports --> Repo
    Ports --> AuditRecorder

    Repo --> Models
    Repo --> Canonical
    Repo --> Lexical
    AuditRecorder --> AuditTable

    Publish -. "post-commit indexing" .-> EmbedIndexer
    EmbedIndexer -.-> Semantic
    Resolver -. "explicit outcome feed / lock facts" .-> CoUsageRefresh
    CoUsageRefresh -.-> CoUsage

    NoteServer["Server owns data-local work<br/>publish, discovery, exact fetch,<br/>governance, audit"]
    NoteResolver["Resolver owns decision-local work<br/>intent understanding, reranking,<br/>selection, solving, execution"]

    Server --- NoteServer
    Resolver --- NoteResolver

    classDef external fill:#f8f9fa,stroke:#6c757d,color:#1f2328;
    classDef entry fill:#e7f5ff,stroke:#1c7ed6,color:#1f2328;
    classDef core fill:#fff0f6,stroke:#c2255c,color:#1f2328;
    classDef infra fill:#fff4e6,stroke:#e67700,color:#1f2328;
    classDef data fill:#ebfbee,stroke:#2b8a3e,color:#1f2328;
    classDef future fill:#f1f3f5,stroke:#868e96,color:#495057,stroke-dasharray: 5 3;
    classDef note fill:#fff9db,stroke:#f08c00,color:#5f3b00;

    class Publisher,Resolver,Ops external;
    class Health,Publish,Discovery,Resolution,Fetch,Main entry;
    class RegistrySvc,DiscoverySvc,ResolutionSvc,FetchSvc,Governance,AuditEvents,Ports core;
    class Repo,Models,AuditRecorder infra;
    class Canonical,Lexical,AuditTable data;
    class EmbedIndexer,CoUsageRefresh,Semantic,CoUsage future;
    class NoteServer,NoteResolver note;
```

## 2. Discovery Internals

```mermaid
flowchart TB

    Request["POST /discovery<br/>name + optional description + tags"]
    Normalize["Normalize query text + tags"]
    Governance["Apply lifecycle / trust / filter policy"]

    subgraph Current["Current Baseline"]
        direction TB
        LexicalLookup["Lexical retrieval<br/>skill_search_documents<br/>tsvector + exact/substring"]
        LexicalRank["Deterministic lexical ranking<br/>exact slug/name<br/>ts_rank_cd<br/>tag overlap<br/>usage/freshness"]
    end

    subgraph Future["Plan 15 Optional Additive Layers"]
        direction TB
        QueryEmbed["Query embedding<br/>best effort + timeout"]
        SemanticLookup["Semantic retrieval<br/>skill_search_embeddings<br/>pgvector ANN"]
        CoUsageBoost["Bounded co-usage boost<br/>skill_co_usage_pairs<br/>only from explicit outcome signals"]
    end

    Union["Union eligible candidates"]
    Fusion["Deterministic fusion<br/>RRF + exact-match precedence"]
    Collapse["Keep best version per slug"]
    Response["Ordered slug candidates"]

    Request --> Normalize
    Normalize --> Governance
    Governance --> LexicalLookup
    LexicalLookup --> LexicalRank
    Governance -.-> QueryEmbed
    QueryEmbed -.-> SemanticLookup
    LexicalRank --> Union
    SemanticLookup -.-> Union
    Union --> Fusion
    CoUsageBoost -.-> Fusion
    Fusion --> Collapse
    Collapse --> Response

    NoteA["Lexical retrieval is mandatory"]
    NoteB["Semantic retrieval is best effort"]
    NoteC["Co-usage is advisory only<br/>not a dependency source"]
    NoteD["No new public route family"]

    Future --- NoteB
    Current --- NoteA
    CoUsageBoost --- NoteC
    Response --- NoteD

    classDef baseline fill:#e7f5ff,stroke:#1c7ed6,color:#1f2328;
    classDef future fill:#f1f3f5,stroke:#868e96,color:#495057,stroke-dasharray: 5 3;
    classDef neutral fill:#f8f9fa,stroke:#6c757d,color:#1f2328;
    classDef note fill:#fff9db,stroke:#f08c00,color:#5f3b00;

    class Request,Normalize,Governance,Union,Fusion,Collapse,Response neutral;
    class LexicalLookup,LexicalRank baseline;
    class QueryEmbed,SemanticLookup,CoUsageBoost future;
    class NoteA,NoteB,NoteC,NoteD note;
```
