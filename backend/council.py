"""3-stage LLM Council orchestration with adaptive model selection."""

from typing import List, Dict, Any, Tuple, Optional
from .openrouter import query_models_parallel, query_model
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL, FEATURE_FLAGS
from .tool_orchestrator import run_with_tools


async def stage1_collect_responses(
    user_query: str,
    models: List[str],
    metadata: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from specified models.

    Args:
        user_query: The user's question
        models: List of model identifiers to query (1-5 models)
        metadata: Optional metadata for metrics tracking

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    messages = [{"role": "user", "content": user_query}]

    # Query selected models in parallel
    responses = await query_models_parallel(models, messages, metadata=metadata)

    # Format results
    stage1_results = []
    for model, response in responses.items():
        if response is not None:  # Only include successful responses
            stage1_results.append({
                "model": model,
                "response": response.get('content', '')
            })

    return stage1_results


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    models: List[str],
    metadata: Optional[Dict[str, Any]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1
        models: List of models to use for ranking
        metadata: Optional metadata for metrics tracking

    Returns:
        Tuple of (rankings list, label_to_model mapping)
    """
    # Safety check: cannot rank empty results
    if not stage1_results:
        return [], {}
    
    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from selected models in parallel
    responses = await query_models_parallel(models, messages, metadata=metadata)

    # Format results
    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    return stage2_results, label_to_model


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    budget: str = "standard"
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        budget: Token budget mode ("minimal", "standard", "comprehensive")

    Returns:
        Dict with 'model' and 'response' keys

    Token Budgeting:
    - minimal: Top 1 response only (~50% token reduction)
    - standard: Top 2 responses + summary (~30% reduction)
    - comprehensive: All responses (current behavior)
    """
    # Apply token budgeting by selecting top responses
    if budget == "minimal" and len(stage1_results) > 0:
        # Use only the top-ranked response
        if stage2_results:
            # Find the response with best average ranking
            response_scores = {}
            for result in stage2_results:
                parsed = result.get('parsed_ranking', [])
                for idx, label in enumerate(parsed):
                    score = len(parsed) - idx  # Higher score for higher rank
                    response_scores[label] = response_scores.get(label, 0) + score

            # Find the top-ranked response and use only that one
            if response_scores:
                # Sort by score (highest first) and get the top label
                top_label = max(response_scores.items(), key=lambda x: x[1])[0]
                # Find the index of the top response in stage1_results
                # Labels are "Response A", "Response B", etc., extract the letter
                label_letter = top_label.replace("Response ", "").strip()
                # Map label letters (A, B, C...) to indices (0, 1, 2...)
                if label_letter and len(label_letter) == 1:
                    label_index = ord(label_letter) - ord('A')
                    if 0 <= label_index < len(stage1_results):
                        stage1_results = [stage1_results[label_index]]
                    else:
                        # Index out of range, use first response
                        stage1_results = stage1_results[:1]
                else:
                    # Invalid label format, use first response
                    stage1_results = stage1_results[:1]
            else:
                # No rankings available, use first response
                stage1_results = stage1_results[:1]

    elif budget == "standard" and len(stage1_results) > 2:
        # Use top 2 responses
        stage1_results = stage1_results[:2]

    # Build context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ]) if budget != "minimal" else "(Rankings omitted for efficiency)"

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model
    response = await query_model(CHAIRMAN_MODEL, messages)

    if response is None:
        # Fallback if chairman fails
        return {
            "model": CHAIRMAN_MODEL,
            "response": "Error: Unable to generate final synthesis."
        }

    return {
        "model": CHAIRMAN_MODEL,
        "response": response.get('content', '')
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Response A")
            # This pattern looks for: number, period, optional space, "Response X"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                # Extract just the "Response X" part
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # Fallback: Extract all "Response X" patterns in order
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # Fallback: try to find any "Response X" patterns in order
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    from collections import defaultdict

    # Track positions for each model
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking['ranking']

        # Parse the ranking from the structured format
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    # Calculate average position for each model
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x['average_rank'])

    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Use gemini-2.5-flash for title generation (fast and cheap)
    response = await query_model("google/gemini-2.5-flash", messages, timeout=30.0)

    if response is None:
        # Fallback to a generic title
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_adaptive_council(
    user_query: str,
    workspace: str = "General",
    models: Optional[List[str]] = None,
    workflow: str = "deliberation",
    suggested_tools: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Tuple[List, List, Dict, Dict]:
    """
    Run adaptive council process with 1-5 models based on workflow type.

    Workflows:
    - "quick": 1 model, no ranking, no synthesis (fastest)
    - "dual_check": 2 models, simple comparison, optional synthesis
    - "deliberation": Full 3-stage process (3+ models)
    - "expert_panel": Full process with all council models

    Args:
        user_query: The user's question
        workspace: Workspace context (for metadata)
        models: List of models to use (defaults to COUNCIL_MODELS)
        workflow: Workflow type
        suggested_tools: List of tools to potentially use
        metadata: Optional metadata for tracking

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    # Default to all council models if not specified
    if models is None:
        models = COUNCIL_MODELS

    # Prepare metadata
    if metadata is None:
        metadata = {}
    metadata.update({"workspace": workspace, "workflow": workflow})

    # Tool orchestration (if enabled and tools suggested)
    tool_results = None
    query_for_council = user_query

    if FEATURE_FLAGS.get("tools_enabled", False) and suggested_tools:
        tool_results = await run_with_tools(
            user_query=user_query,
            workspace=workspace,
            suggested_tools=suggested_tools,
            context=metadata
        )

        # Use augmented query if tools were successful
        if tool_results.get("success") and tool_results.get("tools_used"):
            query_for_council = tool_results["augmented_query"]
            metadata["tools_used"] = tool_results["tools_used"]
            metadata["tool_results"] = tool_results["tool_results"]

    # Stage 1: Collect individual responses
    stage1_results = await stage1_collect_responses(query_for_council, models, metadata)

    # If no models responded successfully, return error
    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again."
        }, {}

    # Quick workflow: single model, return directly
    if workflow == "quick" and len(stage1_results) == 1:
        return stage1_results, [], stage1_results[0], {}

    # Dual check workflow: 2 models, optional simplified synthesis
    if workflow == "dual_check" and len(stage1_results) == 2:
        # Skip stage 2 rankings, go directly to synthesis
        stage3_result = await stage3_synthesize_final(user_query, stage1_results, [])
        return stage1_results, [], stage3_result, {}

    # Full deliberation workflow (3+ models)
    # Stage 2: Collect rankings
    stage2_results, label_to_model = await stage2_collect_rankings(
        user_query, stage1_results, models, metadata
    )

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results
    )

    # Prepare metadata
    result_metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings
    }

    return stage1_results, stage2_results, stage3_result, result_metadata


async def run_full_council(user_query: str) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process with all council models.

    DEPRECATED: Use run_adaptive_council() for better control.
    This function is kept for backwards compatibility.

    Args:
        user_query: The user's question

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    # Use adaptive council with all models and full deliberation
    return await run_adaptive_council(
        user_query,
        workspace="General",
        models=COUNCIL_MODELS,
        workflow="deliberation"
    )
