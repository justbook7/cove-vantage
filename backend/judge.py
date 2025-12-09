"""
Judge model evaluation for Cove.

Optional Stage 4: Independent evaluation of council responses.
Uses a separate model (e.g., o1) to assess quality and catch errors.

Features:
- Accuracy scoring
- Completeness evaluation
- Error detection
- Recommendations (approve/revise/escalate)
"""

from typing import Dict, Any, List, Optional
from .openrouter import query_model
from .config import FEATURE_FLAGS
import os


# Judge model configuration
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "openai/o1")


async def run_judge_evaluation(
    query: str,
    stage3_response: Dict[str, Any],
    stage1_responses: List[Dict[str, Any]],
    stage2_rankings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Run independent judge evaluation on council's final response.

    Args:
        query: Original user query
        stage3_response: Final synthesized response from chairman
        stage1_responses: Individual model responses
        stage2_rankings: Peer rankings

    Returns:
        Dict with evaluation scores and recommendation
    """
    if not FEATURE_FLAGS.get("judge_model", False):
        return {
            "enabled": False,
            "message": "Judge model evaluation is disabled"
        }

    # Build evaluation prompt
    eval_prompt = _build_evaluation_prompt(
        query,
        stage3_response,
        stage1_responses,
        stage2_rankings
    )

    # Query judge model
    messages = [{"role": "user", "content": eval_prompt}]

    try:
        response = await query_model(JUDGE_MODEL, messages, timeout=60.0)

        if not response or 'content' not in response:
            return {
                "enabled": True,
                "success": False,
                "error": "Judge model failed to respond"
            }

        # Parse evaluation
        evaluation = _parse_evaluation(response['content'])

        return {
            "enabled": True,
            "success": True,
            "judge_model": JUDGE_MODEL,
            **evaluation
        }

    except Exception as e:
        return {
            "enabled": True,
            "success": False,
            "error": f"Judge evaluation failed: {str(e)}"
        }


def _build_evaluation_prompt(
    query: str,
    stage3_response: Dict[str, Any],
    stage1_responses: List[Dict[str, Any]],
    stage2_rankings: List[Dict[str, Any]]
) -> str:
    """
    Build the evaluation prompt for the judge model.

    Args:
        query: Original user query
        stage3_response: Final response
        stage1_responses: Individual responses
        stage2_rankings: Peer rankings

    Returns:
        Evaluation prompt string
    """
    # Format stage 1 responses
    stage1_text = "\n\n".join([
        f"Model: {r['model']}\nResponse: {r['response']}"
        for r in stage1_responses
    ])

    # Extract final answer
    final_answer = stage3_response.get('response', '')

    prompt = f"""You are an independent judge evaluating the quality of a multi-LLM council's response.

**Original Question:**
{query}

**Individual Model Responses (Stage 1):**
{stage1_text}

**Council's Final Answer (Stage 3):**
{final_answer}

**Your Task:**
Evaluate the final answer for:
1. **Accuracy**: Is the information factually correct?
2. **Completeness**: Does it fully address all aspects of the question?
3. **Coherence**: Is it well-structured and easy to understand?
4. **Concerns**: Are there any errors, contradictions, or missing information?

Provide your evaluation in the following format:

ACCURACY SCORE: [0-10]
COMPLETENESS SCORE: [0-10]
COHERENCE SCORE: [0-10]

CONCERNS:
- [List any concerns, or write "None"]

RECOMMENDATION: [APPROVE | REVISE | ESCALATE]
REASONING: [Brief explanation of your recommendation]

Guidelines:
- APPROVE: Response is high quality and ready to send
- REVISE: Minor issues that should be addressed
- ESCALATE: Significant errors or inadequacies requiring major revision
"""

    return prompt


def _parse_evaluation(eval_text: str) -> Dict[str, Any]:
    """
    Parse structured evaluation from judge model response.

    Args:
        eval_text: Raw evaluation text

    Returns:
        Dict with parsed scores and recommendation
    """
    import re

    # Default values
    result = {
        "accuracy_score": 5.0,
        "completeness_score": 5.0,
        "coherence_score": 5.0,
        "concerns": [],
        "recommendation": "APPROVE",
        "reasoning": ""
    }

    # Extract scores
    accuracy_match = re.search(r'ACCURACY SCORE:\s*(\d+(?:\.\d+)?)', eval_text, re.IGNORECASE)
    if accuracy_match:
        result["accuracy_score"] = float(accuracy_match.group(1))

    completeness_match = re.search(r'COMPLETENESS SCORE:\s*(\d+(?:\.\d+)?)', eval_text, re.IGNORECASE)
    if completeness_match:
        result["completeness_score"] = float(completeness_match.group(1))

    coherence_match = re.search(r'COHERENCE SCORE:\s*(\d+(?:\.\d+)?)', eval_text, re.IGNORECASE)
    if coherence_match:
        result["coherence_score"] = float(coherence_match.group(1))

    # Extract concerns
    concerns_match = re.search(r'CONCERNS:\s*(.*?)(?=RECOMMENDATION:|$)', eval_text, re.DOTALL | re.IGNORECASE)
    if concerns_match:
        concerns_text = concerns_match.group(1).strip()
        # Parse bullet points
        concerns = [
            c.strip().lstrip('-•*').strip()
            for c in concerns_text.split('\n')
            if c.strip() and c.strip().lower() not in ['none', 'n/a', 'no concerns']
        ]
        result["concerns"] = concerns

    # Extract recommendation
    recommendation_match = re.search(r'RECOMMENDATION:\s*(\w+)', eval_text, re.IGNORECASE)
    if recommendation_match:
        result["recommendation"] = recommendation_match.group(1).upper()

    # Extract reasoning
    reasoning_match = re.search(r'REASONING:\s*(.*?)(?=\n\n|$)', eval_text, re.DOTALL | re.IGNORECASE)
    if reasoning_match:
        result["reasoning"] = reasoning_match.group(1).strip()

    # Calculate overall score (average of subscores)
    result["overall_score"] = round(
        (result["accuracy_score"] + result["completeness_score"] + result["coherence_score"]) / 3,
        1
    )

    return result


async def evaluate_response_quality(
    query: str,
    response: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Quick quality check for a single response.

    Lighter version of full judge evaluation.

    Args:
        query: User query
        response: Response to evaluate
        context: Optional context

    Returns:
        Dict with quality scores
    """
    prompt = f"""Evaluate this response for quality.

Question: {query}

Response: {response}

Rate on scale of 1-10:
ACCURACY: [score]
COMPLETENESS: [score]
COHERENCE: [score]

Be concise."""

    messages = [{"role": "user", "content": prompt}]

    try:
        result = await query_model(JUDGE_MODEL, messages, timeout=30.0)

        if result and 'content' in result:
            eval_data = _parse_evaluation(result['content'])
            return {
                "success": True,
                **eval_data
            }

    except Exception as e:
        pass

    # Return neutral scores on failure
    return {
        "success": False,
        "accuracy_score": 5.0,
        "completeness_score": 5.0,
        "coherence_score": 5.0,
        "overall_score": 5.0
    }
