"""The ONLY MCP in this codebase that calls an LLM. Restricted, by design,
to drafting rationale TEXT from already-computed, human-supplied evidence.
It is never given the ability to output a score, and its output is never
written to any score/rank field - see agent.py, where the rationale it
returns only ever populates data.rationale, never interview_scores.*.
"""
from __future__ import annotations
import os
from .base import LLMRationaleMCP

SYSTEM_PROMPT = """You draft a short, evidence-based hiring rationale fromgit
numbers and notes a human has already produced and approved. Rules:
- Never invent a score, rating, or ranking - only reference the ones given.
- Never mention age, gender, caste, religion, marital status, nationality,
  disability, pregnancy, or health. If the input evidence contains any of
  these, omit them entirely rather than reference them.
- 2-4 sentences. Reference concrete evidence (scores, specific notes).
- Output plain text only, no JSON, no scores, no recommendation labels."""


class ClaudeLLMRationaleMCP(LLMRationaleMCP):
    def __init__(self, model: str = "claude-sonnet-5"):
        self.model = model
        self._client = None  # lazy init so importing this module doesn't require a key

    def _get_client(self):
        if self._client is None:
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError("ANTHROPIC_API_KEY not set - required for rationale drafting.")
            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def draft_rationale(self, evidence: dict) -> str:
        client = self._get_client()
        user_content = (
            f"Candidate final score: {evidence.get('final_score')}\n"
            f"Technical score: {evidence.get('technical_score')}\n"
            f"HR score: {evidence.get('hr_score')}\n"
            f"Cohort size: {evidence.get('cohort_size')}\n"
            f"Rank: {evidence.get('rank')}\n"
            f"HR interviewer notes: {evidence.get('overall_comments', '')}\n\n"
            "Write the rationale."
        )
        resp = client.messages.create(
            model=self.model,
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        return "".join(block.text for block in resp.content if block.type == "text").strip()


class StubLLMRationaleMCP(LLMRationaleMCP):
    """No API key needed - used by tests and the bundled example so the
    repo runs out of the box without network access or a key."""
    def draft_rationale(self, evidence: dict) -> str:
        return (
            f"Rank {evidence.get('rank')} in a cohort of {evidence.get('cohort_size')}. "
            f"Consolidated score {evidence.get('final_score')} "
            f"(technical {evidence.get('technical_score')}, HR {evidence.get('hr_score')}). "
            "[stub rationale - set ANTHROPIC_API_KEY and use ClaudeLLMRationaleMCP for a real draft]"
        )
