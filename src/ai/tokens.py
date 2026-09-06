"""Lightweight token usage tracker shared across AI clients.

This module keeps a simple in-memory counter of tokens used during a single
Horizon run, so the orchestrator can print a summary at the end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ProviderUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class TokenUsageSnapshot:
    total_input_tokens: int
    total_output_tokens: int
    per_provider: Dict[str, ProviderUsage] = field(default_factory=dict)
    # Keyed on the model the API says SERVED the request, which is the closest
    # thing to a per-stage cost this pipeline can get for free: the gate runs on
    # Haiku and everything else on Sonnet, so this splits the cheap filter from
    # the expensive comparison (NEWS-Radar N-045, partial). It does NOT separate
    # rank from defend from analysis, which share a model; that needs a stage
    # label threaded through the client and is the rest of N-045.
    per_model: Dict[str, ProviderUsage] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens


_provider_usage: Dict[str, ProviderUsage] = {}
_model_usage: Dict[str, ProviderUsage] = {}


def record_usage(provider: str, input_tokens: int = 0, output_tokens: int = 0,
                 model: str | None = None) -> None:
    """Accumulate token usage for a given provider.

    Args:
        provider: Provider identifier, e.g. "openai", "anthropic".
        input_tokens: Prompt / input tokens used.
        output_tokens: Completion / output tokens used.
        model: The model that served the request, when the response reports it.
            Optional, so every existing call site keeps working unchanged.
    """
    if input_tokens <= 0 and output_tokens <= 0:
        return

    usage = _provider_usage.setdefault(provider, ProviderUsage())
    usage.input_tokens += max(0, input_tokens)
    usage.output_tokens += max(0, output_tokens)

    if model:
        by_model = _model_usage.setdefault(model, ProviderUsage())
        by_model.input_tokens += max(0, input_tokens)
        by_model.output_tokens += max(0, output_tokens)


def get_usage_snapshot() -> TokenUsageSnapshot:
    """Return a snapshot of accumulated token usage."""
    total_in = sum(u.input_tokens for u in _provider_usage.values())
    total_out = sum(u.output_tokens for u in _provider_usage.values())
    return TokenUsageSnapshot(
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        per_provider=dict(_provider_usage),
        per_model=dict(_model_usage),
    )


def reset_usage() -> None:
    """Reset all accumulated usage (useful for tests)."""
    _provider_usage.clear()
    _model_usage.clear()
