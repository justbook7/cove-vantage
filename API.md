# Project Cove API Documentation

**Version**: 0.3.0
**Base URL**: `http://localhost:8001`
**Protocol**: HTTP/1.1 with Server-Sent Events (SSE) for streaming

---

## Table of Contents

1. [Authentication](#authentication)
2. [Response Format](#response-format)
3. [Error Handling](#error-handling)
4. [Rate Limiting](#rate-limiting)
5. [Endpoints](#endpoints)
   - [System](#system)
   - [Conversations](#conversations)
   - [Messages](#messages)
   - [Workspaces](#workspaces)
   - [Metrics](#metrics)
6. [Server-Sent Events](#server-sent-events)
7. [Examples](#examples)

---

## Authentication

Currently, the API does not require authentication for local development. All endpoints are publicly accessible on localhost.

**Future**: Production deployments should implement authentication via:
- API keys in `Authorization` header
- JWT tokens for user sessions
- OAuth2 for third-party integrations

---

## Response Format

### Success Response
```json
{
  "status": "ok",
  "data": { ... }
}
```

### Error Response
```json
{
  "detail": {
    "error": "Error message",
    "code": "ERROR_CODE",
    "context": { ... }
  }
}
```

---

## Error Handling

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Resource created |
| 400 | Bad request (validation error) |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
| 502 | External API error (OpenRouter, etc.) |

### Common Error Codes

- `VALIDATION_ERROR`: Request validation failed
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `DAILY_COST_LIMIT_EXCEEDED`: Daily cost limit reached
- `QUERY_COST_LIMIT_EXCEEDED`: Per-query cost limit reached
- `CONVERSATION_NOT_FOUND`: Conversation ID doesn't exist
- `MODEL_ERROR`: LLM API error
- `TOOL_ERROR`: Tool execution failed

---

## Rate Limiting

Rate limits are applied per IP address using a sliding window algorithm:

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/api/conversations/{id}/message` | 10 requests | 1 minute |
| `/api/conversations` (list/create) | 30 requests | 1 minute |
| Other endpoints | 60 requests | 1 minute |

### Rate Limit Headers

**Response Headers:**
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1640000000
Retry-After: 45
```

**429 Response:**
```json
{
  "detail": {
    "error": "Rate limit exceeded",
    "limit": 10,
    "window": "1 minute",
    "retry_after": 45
  }
}
```

---

## Endpoints

### System

#### GET `/`

**Description**: Health check and feature flags

**Response:**
```json
{
  "status": "ok",
  "service": "Project Cove API",
  "version": "0.3.0",
  "features": {
    "intent_classification": true,
    "tools_enabled": true,
    "rag_enabled": true,
    "judge_model": false,
    "cost_dashboard": true
  }
}
```

---

### Conversations

#### POST `/api/conversations`

**Description**: Create a new conversation

**Request Body:**
```json
{
  "workspace": "General"
}
```

**Parameters:**
- `workspace` (optional, default: "General"): Workspace name

**Response (201):**
```json
{
  "id": "conv_123abc",
  "workspace": "General",
  "title": "New Conversation",
  "created_at": "2025-12-09T10:30:00Z",
  "messages": []
}
```

---

#### GET `/api/conversations`

**Description**: List all conversations

**Query Parameters:**
- `workspace` (optional): Filter by workspace
- `limit` (optional, default: 100): Max number of conversations
- `offset` (optional, default: 0): Pagination offset

**Response:**
```json
{
  "conversations": [
    {
      "id": "conv_123abc",
      "workspace": "General",
      "title": "New Conversation",
      "created_at": "2025-12-09T10:30:00Z",
      "message_count": 5,
      "last_message_at": "2025-12-09T10:35:00Z"
    }
  ],
  "total": 42,
  "limit": 100,
  "offset": 0
}
```

---

#### GET `/api/conversations/{id}`

**Description**: Get a specific conversation with all messages

**Path Parameters:**
- `id` (required): Conversation ID

**Response:**
```json
{
  "id": "conv_123abc",
  "workspace": "General",
  "title": "Conversation Title",
  "created_at": "2025-12-09T10:30:00Z",
  "messages": [
    {
      "role": "user",
      "content": "What is the capital of France?",
      "timestamp": "2025-12-09T10:30:00Z"
    },
    {
      "role": "assistant",
      "timestamp": "2025-12-09T10:30:15Z",
      "stage1": [
        {
          "model": "openai/gpt-5.1",
          "response": "The capital of France is Paris..."
        }
      ],
      "stage2": [
        {
          "model": "openai/gpt-5.1",
          "ranking": "Response A is the most accurate...",
          "parsed_ranking": ["Response A", "Response B"]
        }
      ],
      "stage3": {
        "model": "google/gemini-3-pro-preview",
        "response": "Based on the council's deliberation, the capital of France is Paris..."
      },
      "metadata": {
        "intent": {
          "complexity": "simple",
          "workflow": "quick",
          "suggested_models": ["openai/gpt-5.1"]
        },
        "cost": 0.02,
        "latency_ms": 1850,
        "tools_used": []
      }
    }
  ]
}
```

**Error (404):**
```json
{
  "detail": "Conversation not found"
}
```

---

#### DELETE `/api/conversations/{id}`

**Description**: Delete a conversation

**Path Parameters:**
- `id` (required): Conversation ID

**Response (200):**
```json
{
  "status": "ok",
  "message": "Conversation deleted"
}
```

---

#### PUT `/api/conversations/{id}/title`

**Description**: Update conversation title

**Path Parameters:**
- `id` (required): Conversation ID

**Request Body:**
```json
{
  "title": "New Title"
}
```

**Response:**
```json
{
  "id": "conv_123abc",
  "title": "New Title"
}
```

---

### Messages

#### POST `/api/conversations/{id}/message`

**Description**: Send a message and receive streaming response via Server-Sent Events

**Path Parameters:**
- `id` (required): Conversation ID

**Request Body:**
```json
{
  "content": "What is the capital of France?",
  "workspace": "General"
}
```

**Parameters:**
- `content` (required): User message (1-10000 characters)
- `workspace` (optional): Override conversation workspace

**Response**: Server-Sent Events stream (see [Server-Sent Events](#server-sent-events) section)

**Error (429):**
```json
{
  "detail": {
    "error": "Rate limit exceeded",
    "limit": 10,
    "window": "1 minute",
    "retry_after": 45
  }
}
```

---

### Workspaces

#### POST `/api/workspaces/{workspace}/documents`

**Description**: Upload a document to workspace for RAG

**Path Parameters:**
- `workspace` (required): Workspace name

**Request Body:**
```json
{
  "title": "Document Title",
  "content": "Document content here...",
  "metadata": {
    "author": "John Doe",
    "source": "https://example.com",
    "tags": ["tag1", "tag2"]
  }
}
```

**Parameters:**
- `title` (required): Document title
- `content` (required): Document content (plain text or markdown)
- `metadata` (optional): Additional metadata

**Response (201):**
```json
{
  "id": "doc_456def",
  "workspace": "General",
  "title": "Document Title",
  "chunks": 12,
  "embedding_model": "text-embedding-3-small",
  "created_at": "2025-12-09T10:30:00Z"
}
```

---

#### GET `/api/workspaces/{workspace}/documents`

**Description**: List documents in workspace

**Path Parameters:**
- `workspace` (required): Workspace name

**Query Parameters:**
- `limit` (optional, default: 100): Max number of documents
- `offset` (optional, default: 0): Pagination offset

**Response:**
```json
{
  "workspace": "General",
  "documents": [
    {
      "id": "doc_456def",
      "title": "Document Title",
      "chunks": 12,
      "created_at": "2025-12-09T10:30:00Z",
      "metadata": {
        "author": "John Doe",
        "source": "https://example.com"
      }
    }
  ],
  "total": 25,
  "limit": 100,
  "offset": 0
}
```

---

#### DELETE `/api/workspaces/{workspace}/documents/{doc_id}`

**Description**: Delete a document from workspace

**Path Parameters:**
- `workspace` (required): Workspace name
- `doc_id` (required): Document ID

**Response:**
```json
{
  "status": "ok",
  "message": "Document deleted"
}
```

---

#### GET `/api/workspaces/{workspace}/stats`

**Description**: Get workspace statistics

**Path Parameters:**
- `workspace` (required): Workspace name

**Response:**
```json
{
  "name": "General",
  "document_count": 25,
  "total_chunks": 487,
  "vector_size": 1536,
  "storage_mb": 12.5,
  "last_updated": "2025-12-09T10:30:00Z"
}
```

---

### Metrics

#### GET `/api/metrics/daily`

**Description**: Get daily cost and usage metrics

**Query Parameters:**
- `date` (optional, default: today): Date in YYYY-MM-DD format
- `days` (optional, default: 7): Number of days to retrieve

**Response:**
```json
{
  "period": {
    "start_date": "2025-12-02",
    "end_date": "2025-12-09",
    "days": 7
  },
  "daily_metrics": [
    {
      "date": "2025-12-09",
      "total_cost": 12.45,
      "total_queries": 87,
      "successful_queries": 85,
      "failed_queries": 2,
      "total_tokens": {
        "prompt": 125000,
        "completion": 67000
      },
      "avg_latency_ms": 3250
    }
  ],
  "summary": {
    "total_cost": 87.30,
    "avg_daily_cost": 12.47,
    "total_queries": 612,
    "success_rate": 0.97
  }
}
```

---

#### GET `/api/metrics/models`

**Description**: Get per-model performance metrics

**Query Parameters:**
- `days` (optional, default: 30): Number of days to analyze
- `model` (optional): Filter by specific model

**Response:**
```json
{
  "period_days": 30,
  "models": [
    {
      "model": "openai/gpt-5.1",
      "total_invocations": 487,
      "successful_invocations": 485,
      "success_rate": 0.996,
      "total_cost": 34.56,
      "avg_cost_per_invocation": 0.071,
      "total_tokens": {
        "prompt": 487000,
        "completion": 234000
      },
      "avg_latency_ms": 2150,
      "p95_latency_ms": 4200,
      "p99_latency_ms": 6500
    }
  ]
}
```

---

#### GET `/api/metrics/dashboard`

**Description**: Get comprehensive dashboard data for visualization

**Query Parameters:**
- `start_date` (optional): Start date in YYYY-MM-DD format
- `end_date` (optional): End date in YYYY-MM-DD format

**Response:**
```json
{
  "summary": {
    "total_cost": 87.30,
    "avg_daily_cost": 12.47,
    "total_queries": 612,
    "success_rate": 0.97
  },
  "daily_costs": [
    {
      "date": "2025-12-09",
      "cost": 12.45
    }
  ],
  "model_costs": [
    {
      "model": "openai/gpt-5.1",
      "cost": 34.56,
      "percentage": 39.6,
      "invocations": 487
    }
  ],
  "workspace_costs": [
    {
      "workspace": "General",
      "cost": 45.20,
      "percentage": 51.8,
      "queries": 342
    }
  ],
  "expensive_queries": [
    {
      "conversation_id": "conv_123abc",
      "query": "Analyze this complex dataset...",
      "cost": 2.45,
      "timestamp": "2025-12-09T10:30:00Z",
      "models_used": 4,
      "tools_used": ["web_search", "code_execution"]
    }
  ],
  "model_performance": [
    {
      "model": "openai/gpt-5.1",
      "avg_latency_ms": 2150,
      "success_rate": 0.996,
      "total_cost": 34.56,
      "invocations": 487
    }
  ]
}
```

---

## Server-Sent Events

The `/api/conversations/{id}/message` endpoint streams responses using Server-Sent Events (SSE). The client should listen for multiple event types.

### Event Types

#### `intent_complete`
**Description**: Intent classification completed

**Data:**
```json
{
  "complexity": "moderate",
  "workflow": "deliberation",
  "suggested_models": [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5"
  ],
  "use_tools": ["web_search"],
  "reasoning": "Query requires current information and multiple perspectives"
}
```

---

#### `tools_complete`
**Description**: Tool execution completed

**Data:**
```json
{
  "tools_used": ["web_search", "calculator"],
  "tool_results": [
    {
      "tool": "web_search",
      "success": true,
      "data": {
        "results": [...]
      }
    }
  ],
  "augmented_query": "Original query with additional context from tools..."
}
```

---

#### `stage1_update`
**Description**: Individual model response received

**Data:**
```json
{
  "model": "openai/gpt-5.1",
  "response": "The capital of France is Paris...",
  "index": 0,
  "total": 3
}
```

---

#### `stage1_complete`
**Description**: All Stage 1 responses collected

**Data:**
```json
{
  "results": [
    {
      "model": "openai/gpt-5.1",
      "response": "..."
    }
  ]
}
```

---

#### `stage2_update`
**Description**: Individual ranking received

**Data:**
```json
{
  "model": "openai/gpt-5.1",
  "ranking": "Response A provides...",
  "parsed_ranking": ["Response A", "Response B", "Response C"],
  "index": 0,
  "total": 3
}
```

---

#### `stage2_complete`
**Description**: All Stage 2 rankings collected

**Data:**
```json
{
  "results": [
    {
      "model": "openai/gpt-5.1",
      "ranking": "...",
      "parsed_ranking": [...]
    }
  ],
  "aggregate_rankings": [
    {
      "model": "anthropic/claude-sonnet-4.5",
      "average_rank": 1.33,
      "rankings_count": 3
    }
  ]
}
```

---

#### `stage3_complete`
**Description**: Final synthesis completed

**Data:**
```json
{
  "model": "google/gemini-3-pro-preview",
  "response": "Based on the council's deliberation..."
}
```

---

#### `judge_complete`
**Description**: Judge evaluation completed (if enabled)

**Data:**
```json
{
  "enabled": true,
  "success": true,
  "judge_model": "openai/o1-preview",
  "accuracy_score": 0.95,
  "completeness_score": 0.90,
  "coherence_score": 0.92,
  "concerns": [],
  "recommendation": "approve",
  "feedback": "Response is accurate and comprehensive."
}
```

---

#### `metadata`
**Description**: Final metadata and costs

**Data:**
```json
{
  "cost": 0.15,
  "latency_ms": 5200,
  "models_used": 3,
  "tools_used": ["web_search"],
  "label_to_model": {
    "Response A": "openai/gpt-5.1",
    "Response B": "google/gemini-3-pro-preview",
    "Response C": "anthropic/claude-sonnet-4.5"
  }
}
```

---

#### `error`
**Description**: Error occurred during processing

**Data:**
```json
{
  "error": "Model API error",
  "code": "MODEL_ERROR",
  "details": {
    "model": "openai/gpt-5.1",
    "message": "API timeout"
  }
}
```

---

#### `done`
**Description**: Stream completed successfully

**Data:**
```json
{
  "status": "completed"
}
```

---

## Examples

### Creating a Conversation and Sending a Message

**Python Example:**
```python
import requests
import json

BASE_URL = "http://localhost:8001"

# 1. Create conversation
response = requests.post(
    f"{BASE_URL}/api/conversations",
    json={"workspace": "General"}
)
conversation = response.json()
conv_id = conversation["id"]

# 2. Send message with SSE streaming
response = requests.post(
    f"{BASE_URL}/api/conversations/{conv_id}/message",
    json={"content": "What is the capital of France?"},
    stream=True
)

for line in response.iter_lines():
    if line:
        line = line.decode('utf-8')
        if line.startswith('data: '):
            data = json.loads(line[6:])
            event_type = data.get('type')

            if event_type == 'stage1_update':
                print(f"Model: {data['model']}")
                print(f"Response: {data['response'][:100]}...")

            elif event_type == 'stage3_complete':
                print(f"\nFinal Answer: {data['response']}")

            elif event_type == 'metadata':
                print(f"\nCost: ${data['cost']:.3f}")
                print(f"Latency: {data['latency_ms']}ms")
```

---

**JavaScript/TypeScript Example:**
```typescript
const BASE_URL = 'http://localhost:8001';

// 1. Create conversation
const conversation = await fetch(`${BASE_URL}/api/conversations`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ workspace: 'General' })
}).then(r => r.json());

const convId = conversation.id;

// 2. Send message with SSE
const eventSource = new EventSource(
  `${BASE_URL}/api/conversations/${convId}/message?` +
  new URLSearchParams({ content: 'What is the capital of France?' })
);

eventSource.addEventListener('stage1_update', (event) => {
  const data = JSON.parse(event.data);
  console.log(`Model: ${data.model}`);
  console.log(`Response: ${data.response.substring(0, 100)}...`);
});

eventSource.addEventListener('stage3_complete', (event) => {
  const data = JSON.parse(event.data);
  console.log('\nFinal Answer:', data.response);
});

eventSource.addEventListener('metadata', (event) => {
  const data = JSON.parse(event.data);
  console.log(`\nCost: $${data.cost.toFixed(3)}`);
  console.log(`Latency: ${data.latency_ms}ms`);
});

eventSource.addEventListener('done', () => {
  eventSource.close();
});

eventSource.addEventListener('error', (event) => {
  console.error('SSE Error:', event);
  eventSource.close();
});
```

---

### Uploading Documents for RAG

**Python Example:**
```python
import requests

BASE_URL = "http://localhost:8001"

# Upload document
response = requests.post(
    f"{BASE_URL}/api/workspaces/General/documents",
    json={
        "title": "Company Style Guide",
        "content": """
        Our company voice is professional yet approachable...
        We prefer active voice over passive voice...
        """,
        "metadata": {
            "author": "Marketing Team",
            "version": "2.1"
        }
    }
)

document = response.json()
print(f"Document uploaded: {document['id']}")
print(f"Chunks created: {document['chunks']}")

# List documents
response = requests.get(f"{BASE_URL}/api/workspaces/General/documents")
documents = response.json()
print(f"Total documents: {documents['total']}")
```

---

### Fetching Cost Dashboard Data

**Python Example:**
```python
import requests
from datetime import date, timedelta

BASE_URL = "http://localhost:8001"

# Get last 7 days of data
end_date = date.today()
start_date = end_date - timedelta(days=7)

response = requests.get(
    f"{BASE_URL}/api/metrics/dashboard",
    params={
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }
)

dashboard = response.json()

print(f"Total Cost: ${dashboard['summary']['total_cost']:.2f}")
print(f"Avg Daily Cost: ${dashboard['summary']['avg_daily_cost']:.2f}")
print(f"Success Rate: {dashboard['summary']['success_rate']:.1%}")

print("\nTop 3 Models by Cost:")
for model in dashboard['model_costs'][:3]:
    print(f"  {model['model']}: ${model['cost']:.2f} ({model['percentage']:.1f}%)")

print("\nMost Expensive Queries:")
for query in dashboard['expensive_queries'][:5]:
    print(f"  ${query['cost']:.2f} - {query['query'][:60]}...")
```

---

## Additional Notes

### CORS Configuration

The API is configured to allow CORS requests from:
- `http://localhost:5173` (Vite default)
- `http://localhost:3000` (Alternative dev port)

For production, update the CORS middleware in `backend/main.py`.

### Database Migrations

The system automatically creates SQLite tables on first run. No manual migration is required.

Legacy JSON conversations in `data/conversations/` are migrated automatically on first access.

### Feature Flags

All features can be toggled via environment variables. Check the root endpoint (`GET /`) to see current feature status.

### Performance Tips

1. **Use intent classification**: Reduces cost by 50-70% for simple queries
2. **Enable caching**: Set `REDIS_URL` for distributed caching
3. **Monitor rate limits**: Check response headers to avoid throttling
4. **Batch document uploads**: Upload multiple small documents in parallel
5. **Use websockets** (future): For lower latency than SSE

### Security Considerations

1. **Production Authentication**: Implement API key or OAuth2 before deployment
2. **HTTPS Only**: Always use HTTPS in production
3. **Input Validation**: All inputs are validated via Pydantic models
4. **Rate Limiting**: Already implemented, but adjust limits per your needs
5. **Cost Limits**: Set `DAILY_COST_LIMIT` and `QUERY_COST_LIMIT` in production

---

## API Versioning

**Current Version**: 0.3.0

The API follows semantic versioning. Breaking changes will increment the major version.

**Deprecation Policy**: Deprecated endpoints will be supported for at least 2 minor versions before removal.

---

## Support

For issues, feature requests, or contributions:
- **GitHub**: [github.com/yourusername/cove-vantage](https://github.com/yourusername/cove-vantage)
- **Documentation**: See [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- **License**: MIT
