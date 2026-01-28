"""Usage tracker for LLM API calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class UsageTracker:
    """Tracks API calls and token usage for a run."""

    api_calls: int = 0
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0

    def record(self, tokens_in: Optional[int], tokens_out: Optional[int]) -> None:
        """Record one API call and its token usage (if available)."""
        self.api_calls += 1

        if tokens_in is None or tokens_out is None:
            self.input_tokens = None
            self.output_tokens = None
            return

        if self.input_tokens is None or self.output_tokens is None:
            return

        self.input_tokens += tokens_in
        self.output_tokens += tokens_out

    def snapshot(self) -> dict[str, Optional[int]]:
        """Return current usage totals."""
        return {
            "api_calls": self.api_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }
