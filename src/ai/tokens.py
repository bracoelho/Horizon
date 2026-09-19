"""Lightweight token usage tracker shared across AI clients.

This module keeps a simple in-memory counter of tokens used during a single
Horizon run, so the orchestrator can print a summary at the end.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional


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


# ---------------------------------------------------------------------------
# The per-call cost record (NEWS-Radar, TOKENOMICS v2 clause 1, 2026-09-19).
#
# `record_usage` above keeps the run's TOTALS, which is what the log line
# `Token usage this run` prints and what every cost claim in the record has
# rested on. Clause 1 wants attribution PER CALL: the stage that asked, why,
# which provider and which KEY served it, which model the API says answered,
# tokens in and out, and the two cache counts and the batch flag that clause 7
# calls techniques. Nothing reads this ledger inside the run; it is written
# beside the fixture at the end and reconciled against the totals (clause 3),
# so a call the ledger missed shows up as a difference rather than as silence.
#
# The stage arrives through a context variable set at each stage boundary,
# never threaded through the client's signature, so every existing call site
# keeps working and a call made outside any stage records `unattributed`,
# which is itself a number the morning reads.
# ---------------------------------------------------------------------------

UNATTRIBUTED = "unattributed"
_stage: contextvars.ContextVar = contextvars.ContextVar("cost_stage", default=None)


@dataclass
class CallRecord:
    stage: str
    purpose: str
    provider: str
    key_id: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    batch: bool = False
    stop_reason: str = ""


_calls: List[CallRecord] = []


def key_identifier(env_name: str, key_value: Optional[str]) -> str:
    """The identifier of the key a call ACTUALLY used, resolved from its value.

    A config names an environment variable and a keychain item names a
    purpose, and on 2026-09-19 the two were found to disagree (OS N-533: the
    item named for experiments held the production key). So the record carries
    a fingerprint of the VALUE, sha256 truncated to eight hex characters,
    beside the env name it was read from. Eight hex characters of a hash reveal
    nothing about the key and are enough to tell two keys apart.
    """
    if not key_value:
        return f"{env_name}:none"
    digest = hashlib.sha256(key_value.encode("utf-8")).hexdigest()[:8]
    return f"{env_name}:{digest}"


@contextmanager
def stage(name: str, purpose: str = "") -> Iterator[None]:
    """Attribute every call made inside the block to `name`."""
    token = _stage.set((name, purpose))
    try:
        yield
    finally:
        _stage.reset(token)


def current_stage() -> tuple[str, str]:
    value = _stage.get()
    return value if value else (UNATTRIBUTED, "")


def record_call(provider: str, model: Optional[str], key_id: str, *,
                input_tokens: int = 0, output_tokens: int = 0,
                cache_read_tokens: int = 0, cache_write_tokens: int = 0,
                batch: bool = False, stop_reason: str = "") -> None:
    """Append one call to the ledger, attributed to the current stage."""
    name, purpose = current_stage()
    _calls.append(CallRecord(
        stage=name, purpose=purpose, provider=provider, key_id=key_id,
        model=str(model or ""), input_tokens=max(0, int(input_tokens or 0)),
        output_tokens=max(0, int(output_tokens or 0)),
        cache_read_tokens=max(0, int(cache_read_tokens or 0)),
        cache_write_tokens=max(0, int(cache_write_tokens or 0)),
        batch=bool(batch), stop_reason=str(stop_reason or ""),
    ))


def get_calls() -> List[CallRecord]:
    return list(_calls)


def stage_summary(calls: Optional[List[CallRecord]] = None) -> Dict[str, dict]:
    """Per-stage totals: calls, tokens in and out, the cache counts, batch calls."""
    out: Dict[str, dict] = {}
    for c in (_calls if calls is None else calls):
        row = out.setdefault(c.stage, {
            "calls": 0, "batch_calls": 0, "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_write_tokens": 0, "models": {}, "keys": {},
        })
        row["calls"] += 1
        row["batch_calls"] += int(c.batch)
        row["input_tokens"] += c.input_tokens
        row["output_tokens"] += c.output_tokens
        row["cache_read_tokens"] += c.cache_read_tokens
        row["cache_write_tokens"] += c.cache_write_tokens
        row["models"][c.model] = row["models"].get(c.model, 0) + 1
        row["keys"][c.key_id] = row["keys"].get(c.key_id, 0) + 1
    return out


def reconcile() -> dict:
    """Clause 3: the ledger's sums against the totals `record_usage` kept.

    Equal means every recorded call was attributed; a difference is the size
    of what the ledger missed, printed rather than hidden.
    """
    snap = get_usage_snapshot()
    ledger_in = sum(c.input_tokens for c in _calls)
    ledger_out = sum(c.output_tokens for c in _calls)
    return {
        "ledger_input": ledger_in, "ledger_output": ledger_out,
        "totals_input": snap.total_input_tokens, "totals_output": snap.total_output_tokens,
        "agree": ledger_in == snap.total_input_tokens and ledger_out == snap.total_output_tokens,
        "calls": len(_calls),
        "unattributed": sum(1 for c in _calls if c.stage == UNATTRIBUTED),
    }


def write_ledger(path: Path) -> int:
    """Write the ledger as JSONL, one call a line; returns the line count."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for c in _calls:
            fh.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
    return len(_calls)


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
    _calls.clear()
