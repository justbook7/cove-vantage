# Project Cove

![llmcouncil](header.jpg)

**Project Cove** is a full-featured AI orchestration platform that goes beyond simple LLM queries. Instead of asking a question to a single LLM provider, you can group multiple models into your "LLM Council" for collaborative deliberation, augmented with tools, RAG (Retrieval-Augmented Generation), and intelligent cost management.

## Core Deliberation Process

When you submit a query, here's what happens:

1. **Intent Classification**: The system analyzes your query and adaptively selects 1-5 models based on complexity (simple queries use 1 fast model, complex queries use full council).

2. **Tool Orchestration** (Optional): If your query would benefit from external data, the system can execute tools:
   - **Web Search**: Real-time information from the internet
   - **Calculator**: Safe mathematical computations
   - **Code Execution**: Sandboxed Python code execution
   - **RAG Search**: Semantic search over your workspace documents
   - **Sports Data**: Live scores, schedules, and odds for CFB, NFL, NBA, MLB

3. **Stage 1: First Opinions**: Selected LLMs respond to your query individually (with tool results if applicable). All responses shown in tab view for inspection.

4. **Stage 2: Anonymous Peer Review**: Each LLM ranks other responses without knowing their authors, preventing bias and favoritism.

5. **Stage 3: Synthesis**: The Chairman LLM synthesizes all responses and rankings into a comprehensive final answer.

6. **Stage 4: Judge Evaluation** (Optional): An independent judge model validates the final answer for accuracy and completeness.

## Key Features

### 🎯 Adaptive Intelligence
- **Intent Classification**: Automatically selects 1-5 models based on query complexity
- **Workflow Modes**: Quick (1 model), Dual Check (2 models), Deliberation (3+ models), Expert Panel (full council)
- **Cost Optimization**: 50-70% cost reduction on simple queries compared to full council

### 🛠️ Tool Integration
- **Calculator**: Safe mathematical expression evaluation (AST-based, no arbitrary code execution)
- **Web Search**: Tavily API integration with DuckDuckGo fallback
- **Code Execution**: Sandboxed Python environment with timeout protection
- **Sports Data**: ESPN API + The Odds API for scores, schedules, and betting lines
- **RAG Search**: Semantic search over workspace-specific document collections

### 📚 RAG (Retrieval-Augmented Generation)
- **Qdrant Vector Database**: Local vector storage with workspace isolation
- **Document Ingestion**: Upload text, markdown, PDF, or web pages
- **Smart Chunking**: Text splitting with overlap (1000 chars, 200 overlap)
- **OpenAI Embeddings**: text-embedding-3-small with LRU caching
- **Style Guides**: Workspace-specific voice/tone refinement (Wooster, Bellcourt, CFB 25, The Quant)

### 💰 Cost Management
- **Real-Time Tracking**: Token/cost/latency metrics for every model invocation
- **Cost Dashboard**: Visualize daily spend, cost by model, cost by workspace
- **Circuit Breaker**: Daily and per-query cost limits to prevent overruns
- **Caching**: Response caching with TTL to reduce redundant API calls
- **Rate Limiting**: Sliding window algorithm (10 req/min for messages, 30 for conversations)
- **Token Budgeting**: Minimal/standard/comprehensive synthesis modes

### 🎨 User Experience
- **Multi-Workspace Support**: Organize conversations by context (General, Wooster, Bellcourt, CFB 25, The Quant)
- **Enhanced Loading Indicators**: Stage-specific progress with icons and hints
- **Document Management**: Upload, view, and delete workspace documents
- **Cost Analytics**: Model performance tables, expensive query tracking
- **Tab-Based UI**: Inspect individual model responses, rankings, and synthesis

### 🔒 Security & Quality
- **Sandboxed Execution**: Code execution in restricted environment with module whitelist
- **Input Validation**: Pydantic models with length/pattern validation
- **Rate Limiting**: Per-IP tracking with X-Forwarded-For support
- **Judge Model**: Optional Stage 4 validation with accuracy/completeness scoring

## Vibe Code Alert

This project started as a 99% vibe coded Saturday hack to explore multiple LLMs side by side in the process of [reading books together with LLMs](https://x.com/karpathy/status/1990577951671509438). It has since evolved into a full production-ready orchestration platform with tools, RAG, cost management, and quality assurance. Code is ephemeral now and libraries are over, ask your LLM to change it in whatever way you like.

## Setup

### 1. Install Dependencies

The project uses [uv](https://docs.astral.sh/uv/) for project management.

**Backend:**
```bash
uv sync
```

**Frontend:**
```bash
cd frontend
npm install
cd ..
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Required
OPENROUTER_API_KEY=sk-or-v1-...

# Optional Features (default values shown)
FEATURE_INTENT_CLASSIFICATION=true
FEATURE_TOOLS_ENABLED=true
FEATURE_RAG_ENABLED=true
FEATURE_JUDGE_MODEL=false
FEATURE_COST_DASHBOARD=true

# Optional API Keys (only needed if features enabled)
TAVILY_API_KEY=tvly-...        # For web search
OPENAI_API_KEY=sk-...           # For embeddings (RAG)
ODDS_API_KEY=...                # For sports betting data

# Cost Controls (optional)
DAILY_COST_LIMIT=100.0          # Daily spending limit in USD
QUERY_COST_LIMIT=5.0            # Per-query limit in USD

# Rate Limiting (optional)
RATE_LIMIT_MESSAGE=10           # Requests per minute for /message endpoint
RATE_LIMIT_CONVERSATIONS=30     # Requests per minute for /conversations
RATE_LIMIT_DEFAULT=60           # Default requests per minute

# Caching (optional)
REDIS_URL=redis://localhost:6379  # Use Redis instead of in-memory cache
CACHE_TTL=3600                     # Cache time-to-live in seconds
```

Get your OpenRouter API key at [openrouter.ai](https://openrouter.ai/). Make sure to purchase the credits you need, or sign up for automatic top up.

### 3. Configure Models (Optional)

Edit `backend/config.py` to customize the council:

```python
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# Optional: Configure judge model for Stage 4 validation
JUDGE_MODEL = "openai/o1-preview"  # High-reasoning model for validation
```

## Running the Application

**Option 1: Use the start script**
```bash
./start.sh
```

**Option 2: Run manually**

Terminal 1 (Backend):
```bash
uv run python -m backend.main
```

Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

Then open http://localhost:5173 in your browser.

## Usage

### Basic Conversation
1. Select a workspace from the dropdown (General, Wooster, Bellcourt, CFB 25, The Quant)
2. Type your question in the input area
3. Watch as the system:
   - Classifies intent and selects appropriate models
   - Executes tools if needed (web search, calculator, etc.)
   - Collects individual responses (Stage 1)
   - Performs peer review (Stage 2)
   - Synthesizes final answer (Stage 3)
4. Review individual responses, rankings, and synthesis in separate tabs

### Document Management
1. Click "Workspace Settings" icon in the header
2. Upload documents (text, markdown, PDF)
3. Documents are automatically:
   - Chunked with overlap
   - Embedded using OpenAI
   - Stored in Qdrant vector database
4. RAG search automatically activates when relevant

### Cost Dashboard
1. Click "Cost Dashboard" in the navigation
2. View metrics:
   - Total cost and daily average
   - Cost breakdown by model
   - Cost breakdown by workspace
   - Model performance (latency, success rate)
   - Most expensive queries
3. Adjust date range for historical analysis

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.10+) with async/await
- **Database**: SQLite with SQLAlchemy 2.0 async ORM
- **Vector Store**: Qdrant (local) for semantic search
- **LLM Routing**: OpenRouter API (100+ models)
- **Embeddings**: OpenAI text-embedding-3-small
- **Tools**:
  - Web Search: Tavily API / DuckDuckGo
  - Calculator: AST-based safe evaluation
  - Code Execution: Sandboxed Python
  - Sports Data: ESPN API / The Odds API
- **Caching**: In-memory LRU cache or Redis
- **Rate Limiting**: Sliding window algorithm
- **Package Management**: uv

### Frontend
- **Framework**: React 18 + Vite
- **Rendering**: react-markdown for formatted responses
- **Styling**: Custom CSS with responsive design
- **Charts**: Custom bar charts for cost dashboard
- **State Management**: React hooks (useState, useEffect)
- **API Communication**: Fetch API with Server-Sent Events (SSE) for streaming

### Data Storage
- **Conversations**: SQLite database (`data/cove.db`)
- **Vectors**: Qdrant local storage (`data/qdrant/`)
- **Metrics**: SQLite tables for cost/latency tracking
- **Legacy**: JSON migration from `data/conversations/`

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Complete system architecture, design decisions, data flow diagrams
- **[API.md](API.md)**: Full API reference with request/response examples
- **[CLAUDE.md](CLAUDE.md)**: Technical implementation notes and development context

## Cost Optimization Tips

1. **Enable Intent Classification**: Automatically uses fewer models for simple queries (50-70% cost reduction)
2. **Use Token Budgeting**: Set synthesis budget to "minimal" or "standard" in workflows
3. **Enable Caching**: Reduces redundant API calls for similar queries
4. **Set Cost Limits**: Configure DAILY_COST_LIMIT and QUERY_COST_LIMIT to prevent overruns
5. **Monitor Dashboard**: Review cost dashboard regularly to identify expensive patterns
6. **Workspace-Specific Models**: Configure different model sets for different workspaces

## Performance Benchmarks

- **Simple Query (1 model)**: 1-2 seconds, ~$0.02
- **Moderate Query (2-3 models)**: 3-5 seconds, ~$0.08
- **Complex Query (4+ models)**: 6-8 seconds, ~$0.15
- **With Tools**: +1-3 seconds for tool execution
- **With RAG**: +0.5-1 second for semantic search

*Benchmarks based on GPT-4 class models. Actual costs vary by model selection and query length.*

## License

MIT License - feel free to use, modify, and distribute as you see fit.
