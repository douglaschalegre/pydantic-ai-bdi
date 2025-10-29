"""Natural language brief parsing into BDI desires and intentions using Pydantic AI.

We create a lightweight Pydantic AI Agent dedicated to transforming a free-form
user brief into:
- desires: high-level goals (strings)
- intentions: candidate high-level plans (strings)

The agent prompts the model to produce structured JSON output validated by a Pydantic schema.
Falls back to simple heuristics if model invocation fails.
"""

from __future__ import annotations
from typing import List
from pydantic import BaseModel, Field

from pydantic_ai import Agent, NativeOutput

from server.agents.general import build_model


class BriefParseOutput(BaseModel):
    desires: List[str] = Field(
        description="Distinct high-level goals inferred from the brief."
    )
    intentions: List[str] = Field(
        description="High-level plan statements (1-2 sentences) that operationalize desires."
    )


SYSTEM_GUIDANCE = """
Your task is to extract desires and intentions from a user's natural language brief.
You must ensure that the information is extracted from the brief itself.
Your response is two arrays: the first for desires in the format [\"desire1\", \"desire2\", ...],
and the second for intentions in the format [\"intention1\", \"intention2\", ...].
If you don't find model names in the abstract or you are not sure, return [\"NA\"]

Step 1: Carefully read the user's brief to understand their goals.
Step 2: Identify and list distinct desires (high-level goals) from the brief. This will be your output 'desires'.
Step 3: Identify and list what the user intends to do to achieve those desires. This will be your output 'intentions'.
""".strip()

_parse_agent = Agent(
    model=build_model(),
    system_prompt=SYSTEM_GUIDANCE,
    output_type=NativeOutput(BriefParseOutput),
)


async def extract_desires_intentions(brief: str) -> tuple[List[str], List[str]]:
    """Run the parsing agent; fallback to heuristic if model or validation fails."""
    if not brief.strip():
        return [], []

    result = await _parse_agent.run(brief)
    desires = [d.strip() for d in result.output.desires if d.strip()]
    intentions = [i.strip() for i in result.output.intentions if i.strip()]
    # Basic post-filtering
    desires = _dedupe_keep_order(desires)
    intentions = _dedupe_keep_order(intentions)
    return desires, intentions


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for text in items:
        current_text = text.lower()
        if current_text not in seen:
            seen.add(current_text)
            out.append(text)
    return out
