# Project Cove - Architecture Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [Technology Stack](#technology-stack)
6. [Design Decisions](#design-decisions)

---

## System Overview

Project Cove is a **multi-model AI orchestration platform** that intelligently routes queries to appropriate AI models, executes tools, retrieves context from knowledge bases, and synthesizes high-quality responses through a deliberative council process.

### Key Capabilities

- **Adaptive Model Routing**: 1-5 models selected based on query complexity (50-70% cost savings)
- **Tool Orchestration**: Web search, calculator, code execution, sports data, RAG search
- **3-Stage Deliberation**: Individual responses → Peer rankings → Chairman synthesis
- **RAG (Retrieval-Augmented Generation)**: Workspace-specific knowledge bases with semantic search
- **Cost Management**: Real-time tracking, circuit breakers, caching, rate limiting
- **Quality Assurance**: Optional judge model for response evaluation

---

## Architecture Diagram

```
┌─────────────┐
│   User/UI   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│           FastAPI Backend (Port 8001)       │
│  ┌──────────────────────────────────────┐  │
│  │  Intent Classifier                   │  │
│  │  ├─ Rule-based patterns             │  │
│  │  └─ LLM classification (gemini-flash)│  │
│  └──────────────────────────────────────┘  │
│                    │                        │
│                    ▼                        │
│  ┌──────────────────────────────────────┐  │
│  │  Tool Orchestrator                   │  │
│  │  ├─ Calculator                       │  │
│  │  ├─ Web Search (Tavily/DuckDuckGo)  │  │
│  │  ├─ Code Execution (Sandboxed)      │  │
│  │  ├─ Sports Data (ESPN/Odds API)     │  │
│  │  └─ RAG Search (Qdrant + Embeddings)│  │
│  └──────────────────────────────────────┘  │
│                    │                        │
│                    ▼                        │
│  ┌──────────────────────────────────────┐  │
│  │  3-Stage Council                     │  │
│  │  ┌────────────────────────────────┐  │  │
│  │  │  Stage 1: Collect Responses    │  │  │
│  │  │  ├─ Query 1-5 models in parallel│ │  │
│  │  │  └─ Return individual responses │  │  │
│  │  └────────────────────────────────┘  │  │
│  │  ┌────────────────────────────────┐  │  │
│  │  │  Stage 2: Peer Rankings        │  │  │
│  │  │  ├─ Anonymize responses         │  │  │
│  │  │  ├─ Models rank each other     │  │  │
│  │  │  └─ Calculate aggregate scores  │  │  │
│  │  └────────────────────────────────┘  │  │
│  │  ┌────────────────────────────────┐  │  │
│  │  │  Stage 3: Chairman Synthesis   │  │  │
│  │  │  ├─ Apply token budgeting       │  │  │
│  │  │  ├─ Synthesize final response   │  │  │
│  │  │  └─ Optional: Apply style guide │  │  │
│  │  └────────────────────────────────┘  │  │
│  └──────────────────────────────────────┘  │
│                    │                        │
│                    ▼                        │
│  ┌──────────────────────────────────────┐  │
│  │  Optional: Judge Model               │  │
│  │  ├─ Accuracy evaluation              │  │
│  │  ├─ Completeness check               │  │
│  │  └─ Recommendation (approve/revise)  │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │  Cross-Cutting Concerns              │  │
│  │  ├─ Response Caching (In-memory/Redis)│ │
│  │  ├─ Circuit Breaker (Cost limits)   │  │
│  │  ├─ Rate Limiting (Per IP/Endpoint)  │  │
│  │  ├─ Metrics Collection (SQLite)     │  │
│  │  └─ Error Handling & Logging        │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│  External Services                          │
│  ├─ OpenRouter API (LLM models)            │
│  ├─ OpenAI API (Embeddings)                │
│  ├─ Tavily/DuckDuckGo (Web search)         │
│  └─ ESPN/The Odds API (Sports data)        │
└─────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│  Data Storage                               │
│  ├─ SQLite (Conversations, Metrics)        │
│  ├─ Qdrant (Vector DB for RAG)             │
│  └─ In-memory Cache (LRU with TTL)         │
└─────────────────────────────────────────────┘
```

---

## Core Components

### 1. Intent Classifier (`backend/intent_classifier.py`)

**Purpose**: Analyze queries to determine complexity and route appropriately

**Classification Levels**:
- **Simple** (1 model): Greetings, basic facts
- **Moderate** (2-3 models): Standard questions, calculations
- **Complex** (3-4 models): Multi-faceted analysis, comparisons
- **Expert** (4-5 models): High-stakes content, deep analysis

**Workflow Types**:
- `quick`: Single model, no deliberation
- `dual_check`: Two models, simple comparison
- `deliberation`: Full 3-stage process
- `expert_panel`: Full process + tools

**Implementation**:
```python
async def classify_intent(query: str, workspace: str) -> Dict:
    # 1. Try rule-based classification (fast, free)
    # 2. Fallback to gemini-2.5-flash (~$0.001)
    return {
        "complexity": "moderate",
        "suggested_models": ["claude-sonnet-4.5", "gpt-5.1"],
        "use_tools": ["calculator", "web_search"],
        "workflow": "deliberation",
        "estimated_cost": 0.01
    }
```

### 2. Tool Orchestrator (`backend/tool_orchestrator.py`)

**Purpose**: Execute tools and augment queries with results

**Available Tools**:
1. **Calculator** (`tools/calculator.py`)
   - AST-based safe evaluation
   - Supports: +, -, *, /, **, sqrt, sin, cos, log, etc.

2. **Web Search** (`tools/web_search.py`)
   - Primary: Tavily API
   - Fallback: DuckDuckGo Instant Answer API
   - Returns: Title, snippet, URL

3. **Code Execution** (`tools/code_execution.py`)
   - Sandboxed Python execution
   - Restricted builtins and modules
   - Timeout protection

4. **Sports Data** (`tools/sports_data.py`)
   - ESPN API (scores, schedules)
   - The Odds API (betting lines)
   - Mock data fallback

5. **RAG Search** (`tools/rag_search.py`)
   - Semantic search over workspace documents
   - Relevance scoring
   - Configurable result count

**Flow**:
```python
1. Intent classifier suggests tools: ["web_search", "calculator"]
2. Tool orchestrator prepares parameters
3. Tools execute in parallel
4. Results formatted and prepended to query
5. Council receives augmented query with context
```

### 3. Council Process (`backend/council.py`)

**Stage 1: Individual Responses**
- Query selected models in parallel (1-5 models)
- Each model responds independently
- No awareness of other responses

**Stage 2: Peer Rankings**
- Responses anonymized (Response A, B, C...)
- Each model evaluates and ranks ALL responses
- Parsing extracts "FINAL RANKING:" section
- Aggregate rankings calculated

**Stage 3: Chairman Synthesis**
- Token budgeting applied:
  - `minimal`: Top 1 response (~50% token reduction)
  - `standard`: Top 2 responses (~30% reduction)
  - `comprehensive`: All responses
- Chairman synthesizes final answer
- Optional: Style guide applied based on workspace

### 4. RAG System (`backend/rag/`)

**Components**:
- **Vector Store** (`vector_store.py`): Qdrant integration, workspace-specific collections
- **Embeddings** (`embeddings.py`): OpenAI embeddings with LRU caching
- **Ingestor** (`ingestor.py`): Document chunking, batch processing
- **Style Guide** (`style_guide.py`): Workspace-specific voice/tone

**Document Flow**:
```
1. User uploads document (text/PDF)
2. Ingestor chunks text (1000 chars, 200 overlap)
3. Batch embedding generation
4. Store in Qdrant with metadata
5. Semantic search during queries
```

### 5. Cost Management

**Circuit Breaker** (`backend/circuit_breaker.py`):
- Daily cost limit (default: $100)
- Per-query limit (default: $5)
- Real-time cost tracking via database
- Raises CircuitBreakerError if exceeded

**Caching** (`backend/cache.py`):
- Cache key: hash(model + messages)
- TTL: 1 hour (configurable)
- LRU eviction when full
- Optional Redis backend

**Rate Limiting** (`backend/rate_limiter.py`):
- Sliding window algorithm
- Per-endpoint limits (messages: 10/min, default: 60/min)
- IP-based tracking
- Returns 429 with Retry-After header

### 6. Metrics & Analytics (`backend/metrics.py`)

**Tracked Metrics**:
- Model invocations (tokens, latency, success rate)
- Daily/monthly costs
- Per-workspace costs
- Model performance statistics

**Database Schema**:
```sql
CREATE TABLE model_invocations (
    id INTEGER PRIMARY KEY,
    conversation_id TEXT,
    model_name TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    latency_ms REAL,
    success BOOLEAN,
    created_at TIMESTAMP
);
```

---

## Data Flow

### Query Processing Flow

```
1. User submits query + workspace
   ↓
2. Check rate limit (10 req/min for messages)
   ↓
3. Check circuit breaker (daily/query cost limits)
   ↓
4. Intent classification
   ├─ Determine complexity
   ├─ Select models (1-5)
   ├─ Suggest tools
   └─ Choose workflow
   ↓
5. Tool orchestration (if tools suggested)
   ├─ Execute tools in parallel
   ├─ Format results
   └─ Augment query with context
   ↓
6. Stage 1: Collect responses
   ├─ Check cache for each model
   ├─ Query models in parallel
   ├─ Record metrics
   └─ Return responses
   ↓
7. Stage 2: Peer rankings (if workflow requires)
   ├─ Anonymize responses
   ├─ Query models for rankings
   ├─ Parse rankings
   └─ Calculate aggregates
   ↓
8. Stage 3: Chairman synthesis
   ├─ Apply token budgeting
   ├─ Synthesize final answer
   └─ Optional: Apply style guide
   ↓
9. Optional: Judge evaluation
   ├─ Evaluate accuracy/completeness
   └─ Recommend approve/revise
   ↓
10. Store conversation in database
   ↓
11. Return response to user
```

### Database Interactions

**Write Path**:
```
Query → Council → Metrics Collector → SQLite
                → Storage → SQLite (conversations)
```

**Read Path**:
```
GET /api/conversations → Storage → SQLite → JSON response
GET /api/metrics/daily → Metrics → SQLite → Aggregated stats
```

### RAG Data Flow

**Ingestion**:
```
Document Upload → Ingestor → Chunking → Embeddings API → Qdrant
                                                        ↓
                                                   Vector Store
```

**Search**:
```
Query → Generate embedding → Qdrant search → Ranked results
                          ↓
                    Relevance filtering
```

---

## Technology Stack

### Backend
- **Framework**: FastAPI 0.115+
- **Language**: Python 3.10+
- **Database**: SQLite (PostgreSQL-ready)
- **Vector DB**: Qdrant (local, persistent)
- **Async**: asyncio, aiosqlite
- **HTTP Client**: httpx

### Frontend
- **Framework**: React 18
- **Build Tool**: Vite
- **Styling**: CSS Modules
- **State**: React Hooks (useState, useEffect)
- **API**: Fetch API with SSE support

### External Services
- **LLM Routing**: OpenRouter
- **Embeddings**: OpenAI API (text-embedding-3-small)
- **Web Search**: Tavily / DuckDuckGo
- **Sports Data**: ESPN API / The Odds API

### Infrastructure
- **Caching**: In-memory LRU (Redis optional)
- **Rate Limiting**: Sliding window (in-memory)
- **Monitoring**: SQLite-based metrics

---

## Design Decisions

### 1. Why OpenRouter?

**Decision**: Use OpenRouter for LLM routing instead of direct provider APIs

**Rationale**:
- Single API for 100+ models
- Built-in fallbacks and load balancing
- Unified billing
- Model availability transparency

**Trade-offs**:
- Additional hop (minimal latency)
- Dependency on third party
- Cost markup (~10-20%)

### 2. Why SQLite?

**Decision**: Use SQLite for conversations and metrics

**Rationale**:
- Zero configuration
- Local file storage
- Fast for read-heavy workloads
- Easy backup (just copy file)
- PostgreSQL migration path

**Trade-offs**:
- Limited concurrency (write locks)
- Not ideal for distributed systems
- Size limits (~281 TB, practically unlimited)

### 3. Why Qdrant?

**Decision**: Use Qdrant for vector storage

**Rationale**:
- Open source
- Local deployment
- High performance
- Rich filtering capabilities
- Collection-based isolation

**Alternatives Considered**:
- Pinecone: Cloud-only, paid
- Weaviate: More complex setup
- FAISS: No built-in persistence

### 4. Why 3-Stage Deliberation?

**Decision**: Multi-stage process instead of single synthesis

**Rationale**:
- Peer review improves quality
- Anonymization prevents bias
- Deliberation surfaces best ideas
- Transparency for users

**Trade-offs**:
- Higher latency (6-10s vs 2-3s)
- Higher cost (3-5x model calls)
- Complexity in implementation

**Mitigation**:
- Adaptive routing (1-5 models)
- Token budgeting
- Caching
- Quick workflow for simple queries

### 5. Why Intent Classification?

**Decision**: Pre-classify queries before routing

**Rationale**:
- Cost savings (50-70%)
- Latency reduction
- Better user experience
- Resource optimization

**Implementation**:
- Hybrid: Rule-based + cheap model ($0.001)
- Fast for obvious patterns
- Accurate for ambiguous cases

### 6. Why Tool Orchestration?

**Decision**: Pre-fetch data before LLM queries

**Rationale**:
- Real-time data accuracy
- Reduced hallucination
- Factual grounding
- Computational offloading

**Trade-offs**:
- Added latency (tool execution)
- Additional API costs
- Complexity in error handling

### 7. Why Workspace Isolation?

**Decision**: Separate knowledge bases per workspace

**Rationale**:
- Data privacy
- Context relevance
- Custom styles
- Multi-tenancy ready

**Implementation**:
- Qdrant collections per workspace
- Style guides per workspace
- Workspace metadata in all queries

---

## Scalability Considerations

### Current Limits
- **Concurrent Requests**: ~100 (FastAPI default)
- **Database**: Single SQLite file (write locks)
- **Caching**: In-memory (process-local)
- **Vector DB**: Local Qdrant (single instance)

### Scaling Path
1. **Horizontal Scaling** (1K-10K users):
   - Multiple backend instances behind load balancer
   - PostgreSQL for conversations/metrics
   - Redis for distributed caching
   - Cloud Qdrant or separate instance

2. **Optimization** (10K-100K users):
   - CDN for static assets
   - Database read replicas
   - Message queue for async processing
   - Separate services (RAG, tools, council)

3. **Enterprise** (100K+ users):
   - Kubernetes orchestration
   - Microservices architecture
   - Distributed vector store
   - Multi-region deployment

---

## Security Considerations

### Authentication & Authorization
- Currently: None (local development)
- Production: Add API keys, JWT tokens, OAuth

### Input Validation
- Pydantic models for request validation
- Max query length (10K chars)
- Content filtering (XSS, injection prevention)

### Tool Security
- Code execution: Sandboxed, restricted imports
- Calculator: AST-based, no eval/exec
- File uploads: Size limits, type validation

### Rate Limiting
- Per-IP limits to prevent abuse
- Per-user limits (when auth added)
- Endpoint-specific limits

### Data Privacy
- Workspace isolation in vector store
- Conversation metadata per workspace
- Optional data encryption at rest

---

## Performance Benchmarks

### Typical Query Latencies
- Simple query (1 model, no tools): 1-2s
- Moderate (2 models, 1 tool): 3-5s
- Complex (3 models, full deliberation): 6-8s
- Expert (4 models, tools, judge): 10-15s

### Cost Estimates (per query)
- Simple: $0.01-0.02
- Moderate: $0.05-0.10
- Complex: $0.15-0.25
- Expert: $0.30-0.50

### Throughput
- Single instance: ~10 queries/sec
- With caching: ~50 queries/sec (80% hit rate)
- Database writes: ~100/sec

---

## Monitoring & Observability

### Metrics Collected
- Request rate (per endpoint)
- Response latency (p50, p95, p99)
- Model success rate
- Cost per query/day
- Cache hit rate
- Error rate

### Logging
- FastAPI access logs
- Application logs (errors, warnings)
- Model API errors
- Tool execution failures

### Alerting (Future)
- Daily cost exceeds threshold
- Error rate spike
- Model availability issues
- Database size approaching limits

---

## Future Enhancements

### Short Term
- [ ] Add authentication (API keys)
- [ ] Implement conversation export
- [ ] Add conversation search
- [ ] Enhanced error messages
- [ ] Keyboard shortcuts

### Medium Term
- [ ] Real-time streaming (token-by-token)
- [ ] Conversation branching
- [ ] Model comparison mode
- [ ] Custom model selection UI
- [ ] Batch processing API

### Long Term
- [ ] Multi-user support with teams
- [ ] Plugin system for custom tools
- [ ] Self-hosted embeddings
- [ ] Fine-tuned intent classifier
- [ ] Mobile apps (iOS, Android)

---

## References

- **FastAPI**: https://fastapi.tiangolo.com
- **OpenRouter**: https://openrouter.ai
- **Qdrant**: https://qdrant.tech
- **OpenAI Embeddings**: https://platform.openai.com/docs/guides/embeddings
- **React**: https://react.dev

---

**Last Updated**: December 2025
**Version**: 0.3.0
