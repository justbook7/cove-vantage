"""Configuration for Project Cove."""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# API Keys
# ============================================================================

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Validate API key on import
if not OPENROUTER_API_KEY:
    import warnings
    warnings.warn(
        "OPENROUTER_API_KEY not set. API calls will fail. "
        "Set it in .env file or environment variable.",
        UserWarning
    )

# Council members - list of OpenRouter model identifiers
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

# ============================================================================
# Database Configuration
# ============================================================================

# Database URL (SQLite by default, can use PostgreSQL in production)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/cove.db")

# ============================================================================
# Model Costs (USD per 1 million tokens)
# ============================================================================

MODEL_COSTS = {
    "openai/gpt-5.1": {
        "input": 2.50,
        "output": 10.00,
    },
    "google/gemini-3-pro-preview": {
        "input": 1.25,
        "output": 5.00,
    },
    "anthropic/claude-sonnet-4.5": {
        "input": 3.00,
        "output": 15.00,
    },
    "x-ai/grok-4": {
        "input": 2.00,
        "output": 8.00,
    },
    "google/gemini-2.5-flash": {
        "input": 0.075,  # Very cheap for classification
        "output": 0.30,
    },
}

# ============================================================================
# Feature Flags
# ============================================================================

FEATURE_FLAGS = {
    "intent_classification": os.getenv("FEATURE_INTENT_CLASSIFICATION", "true").lower() == "true",
    "tools_enabled": os.getenv("FEATURE_TOOLS_ENABLED", "true").lower() == "true",
    "rag_enabled": os.getenv("FEATURE_RAG_ENABLED", "true").lower() == "true",
    "judge_model": os.getenv("FEATURE_JUDGE_MODEL", "false").lower() == "true",
    "cost_dashboard": os.getenv("FEATURE_COST_DASHBOARD", "true").lower() == "true",
}

# ============================================================================
# Cost Controls
# ============================================================================

# Daily cost limit (USD)
DAILY_COST_LIMIT = float(os.getenv("DAILY_COST_LIMIT", "100.0"))

# Single query cost limit (USD)
QUERY_COST_LIMIT = float(os.getenv("QUERY_COST_LIMIT", "5.0"))

# ============================================================================
# Model Selection for Special Tasks
# ============================================================================

# Intent classifier model (cheap and fast)
INTENT_CLASSIFIER_MODEL = os.getenv("INTENT_CLASSIFIER_MODEL", "google/gemini-2.5-flash")

# Embedding model for RAG
DEFAULT_EMBEDDING_MODEL = os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")

# ============================================================================
# Caching Configuration
# ============================================================================

# Redis URL (optional, for caching)
REDIS_URL = os.getenv("REDIS_URL", None)

# Cache TTL in seconds (default 1 hour)
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
