"""OpenRouter API client for making LLM requests."""

import httpx
import time
from typing import List, Dict, Any, Optional
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL
from .metrics import metrics_collector


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API with automatic metrics tracking.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds
        metadata: Optional metadata to attach to metrics (conversation_id, workspace, etc.)

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    # Validate API key
    if not OPENROUTER_API_KEY:
        print(f"Error: OPENROUTER_API_KEY not configured. Cannot query model {model}")
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    # Start timing
    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            data = response.json()
            
            # Validate response structure
            if 'choices' not in data or len(data['choices']) == 0:
                raise ValueError("Invalid API response: no choices in response")
            
            message = data['choices'][0]['message']
            
            # Validate message content
            if 'content' not in message:
                raise ValueError("Invalid API response: no content in message")

            # Extract token usage from response
            usage = data.get('usage', {})
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)

            # Record metrics
            await metrics_collector.record_invocation(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                success=True,
                metadata=metadata or {}
            )

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details'),
                'usage': {
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': prompt_tokens + completion_tokens
                }
            }

    except Exception as e:
        # Calculate latency even for failed requests
        latency_ms = (time.time() - start_time) * 1000

        # Record failed invocation
        await metrics_collector.record_invocation(
            model=model,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=latency_ms,
            success=False,
            error_message=str(e),
            metadata=metadata or {}
        )

        print(f"Error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel with automatic metrics tracking.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model
        metadata: Optional metadata to attach to metrics (conversation_id, workspace, etc.)

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    # Create tasks for all models with metadata
    tasks = [query_model(model, messages, metadata=metadata) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}
