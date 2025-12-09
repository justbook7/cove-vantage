"""
Style Guide Manager for Cove.

Enables workspace-specific voice, tone, and style control.
Applies style guides to responses via two-pass generation.

Features:
- Workspace-specific style guides
- Two-pass refinement (generate → refine)
- Style consistency enforcement
- Voice and tone customization
"""

from typing import Dict, Any, Optional
import os


# Predefined style guides for workspaces
WORKSPACE_STYLES = {
    "Wooster": {
        "name": "Wooster Style",
        "description": "Professional, witty, and sophisticated with British flair",
        "voice": "First-person, knowledgeable advisor",
        "tone": "Warm, humorous, erudite",
        "guidelines": [
            "Use sophisticated vocabulary with occasional wit",
            "Include literary or cultural references when appropriate",
            "Maintain professional demeanor with charm",
            "Use British English spelling (colour, analyse, etc.)",
            "Prefer longer, well-constructed sentences",
            "Add subtle humor without being flippant"
        ],
        "example": "I dare say the solution to your query lies in..."
    },
    "Bellcourt": {
        "name": "Bellcourt Style",
        "description": "Direct, analytical, and business-focused",
        "voice": "Third-person, objective analyst",
        "tone": "Professional, clear, action-oriented",
        "guidelines": [
            "Use clear, concise business language",
            "Focus on actionable insights",
            "Structure with bullet points and headings",
            "Emphasize data and evidence",
            "Avoid jargon unless necessary",
            "Provide executive summary upfront"
        ],
        "example": "The analysis reveals three key findings..."
    },
    "CFB 25": {
        "name": "CFB 25 Style",
        "description": "Enthusiastic, sports-focused, and data-driven",
        "voice": "First-person, passionate fan and analyst",
        "tone": "Energetic, knowledgeable, competitive",
        "guidelines": [
            "Use sports terminology and metaphors",
            "Reference stats and historical context",
            "Show enthusiasm for the game",
            "Break down complex strategies clearly",
            "Include betting/fantasy implications when relevant",
            "Use present tense for immediacy"
        ],
        "example": "Looking at the matchup, here's how it breaks down..."
    },
    "The Quant": {
        "name": "The Quant Style",
        "description": "Precise, mathematical, and rigorously analytical",
        "voice": "Third-person, technical expert",
        "tone": "Methodical, precise, objective",
        "guidelines": [
            "Use mathematical notation when appropriate",
            "Show calculations and formulas",
            "Emphasize statistical significance",
            "Structure proofs and derivations clearly",
            "Define technical terms precisely",
            "Include confidence intervals and error bounds"
        ],
        "example": "Given the parameters, we can derive..."
    },
    "General": {
        "name": "General Style",
        "description": "Balanced, clear, and accessible",
        "voice": "Second-person, helpful assistant",
        "tone": "Friendly, clear, informative",
        "guidelines": [
            "Use clear, accessible language",
            "Structure with paragraphs and lists",
            "Be helpful and direct",
            "Avoid unnecessary jargon",
            "Balance detail with clarity",
            "Address the user directly"
        ],
        "example": "Here's what you need to know..."
    }
}


class StyleGuideManager:
    """Manager for applying workspace-specific styles."""

    def __init__(self):
        """Initialize style guide manager."""
        self.styles = WORKSPACE_STYLES

    def get_style_guide(self, workspace: str) -> Dict[str, Any]:
        """
        Get style guide for a workspace.

        Args:
            workspace: Workspace name

        Returns:
            Style guide dict
        """
        return self.styles.get(workspace, self.styles["General"])

    async def apply_style(
        self,
        workspace: str,
        base_response: str,
        query: Optional[str] = None
    ) -> str:
        """
        Apply workspace style to a response via refinement.

        Two-pass approach:
        1. Generate base response (already done)
        2. Refine response to match style guide

        Args:
            workspace: Workspace name
            base_response: Original response to refine
            query: Original query (optional, for context)

        Returns:
            Refined response matching style guide
        """
        style_guide = self.get_style_guide(workspace)

        # If General workspace or style disabled, return as-is
        if workspace == "General" or not os.getenv("ENABLE_STYLE_GUIDES", "false").lower() == "true":
            return base_response

        # Build refinement prompt
        refinement_prompt = self._build_refinement_prompt(
            style_guide,
            base_response,
            query
        )

        # Use chairman model for refinement
        from ..openrouter import query_model
        from ..config import CHAIRMAN_MODEL

        try:
            messages = [{"role": "user", "content": refinement_prompt}]
            result = await query_model(CHAIRMAN_MODEL, messages, timeout=30.0)

            if result and 'content' in result:
                refined = result['content'].strip()
                return refined

        except Exception as e:
            # Fallback to original on error
            print(f"Style refinement failed: {e}")

        return base_response

    def _build_refinement_prompt(
        self,
        style_guide: Dict[str, Any],
        base_response: str,
        query: Optional[str] = None
    ) -> str:
        """
        Build refinement prompt for style application.

        Args:
            style_guide: Style guide dict
            base_response: Original response
            query: Original query

        Returns:
            Refinement prompt
        """
        guidelines_text = "\n".join([f"- {g}" for g in style_guide["guidelines"]])

        prompt = f"""Refine this response to match the following style guide.

**Style Guide: {style_guide['name']}**
Description: {style_guide['description']}
Voice: {style_guide['voice']}
Tone: {style_guide['tone']}

**Guidelines:**
{guidelines_text}

**Example opening:** {style_guide['example']}

**Original Response:**
{base_response}
"""

        if query:
            prompt += f"\n\n**Original Question:** {query}"

        prompt += """

**Your Task:**
Rewrite the response to match the style guide while preserving all factual content and key points. Do not add new information, only refine the presentation and tone.

**Refined Response:**"""

        return prompt

    def get_style_prompt_suffix(self, workspace: str) -> str:
        """
        Get style guidance to append to initial prompts.

        This lightweight approach adds style hints without full refinement.

        Args:
            workspace: Workspace name

        Returns:
            Style prompt suffix
        """
        style_guide = self.get_style_guide(workspace)

        if workspace == "General":
            return ""

        return f"""

**Style Note:** Please respond in the {style_guide['name']} ({style_guide['description']}).
{style_guide['voice']}, {style_guide['tone']}."""

    def list_available_styles(self) -> list:
        """
        List all available style guides.

        Returns:
            List of style guide names and descriptions
        """
        return [
            {
                "workspace": name,
                "style": guide["name"],
                "description": guide["description"]
            }
            for name, guide in self.styles.items()
        ]


# Global style guide manager instance
_style_manager: Optional[StyleGuideManager] = None


def get_style_manager() -> StyleGuideManager:
    """
    Get the global style guide manager.

    Returns:
        StyleGuideManager instance
    """
    global _style_manager
    if _style_manager is None:
        _style_manager = StyleGuideManager()
    return _style_manager


# Convenience functions
async def apply_workspace_style(workspace: str, response: str, query: Optional[str] = None) -> str:
    """Apply workspace style to response."""
    manager = get_style_manager()
    return await manager.apply_style(workspace, response, query)


def get_style_prompt_suffix(workspace: str) -> str:
    """Get style guidance suffix for prompts."""
    manager = get_style_manager()
    return manager.get_style_prompt_suffix(workspace)


def list_available_styles() -> list:
    """List all available style guides."""
    manager = get_style_manager()
    return manager.list_available_styles()
