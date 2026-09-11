"""Request shaping and Batch API handling for the Anthropic client."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ai.client import AnthropicClient, BatchNotReady, BatchRequest
from src.models import AIConfig, AIProvider


def _client(monkeypatch) -> AnthropicClient:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    config = AIConfig(
        provider=AIProvider.ANTHROPIC,
        model="claude-sonnet-5",
        api_key_env="ANTHROPIC_API_KEY",
        temperature=1.0,
        max_tokens=4096,
    )
    return AnthropicClient(config)


def _text(value: str):
    return SimpleNamespace(type="text", text=value)


# --------------------------------------------------------------- build_params


def test_params_omit_output_config_when_nothing_asks_for_it(monkeypatch) -> None:
    """An unmodified call must look exactly as it did before, or every existing
    caller changes behaviour silently."""
    params = _client(monkeypatch).build_params("sys", "usr")
    assert "output_config" not in params
    assert params["thinking"] == {"type": "disabled"}
    assert params["model"] == "claude-sonnet-5"


def test_schema_becomes_a_json_schema_output_format(monkeypatch) -> None:
    schema = {"type": "object", "properties": {"keep": {"type": "boolean"}}}
    params = _client(monkeypatch).build_params("sys", "usr", schema=schema)
    assert params["output_config"]["format"] == {
        "type": "json_schema",
        "schema": schema,
    }


def test_schema_and_effort_share_one_output_config(monkeypatch) -> None:
    """Both live under output_config; setting the key twice would drop one."""
    params = _client(monkeypatch).build_params(
        "sys", "usr", schema={"type": "object"}, effort="low"
    )
    assert set(params["output_config"]) == {"format", "effort"}


def test_model_override_enables_per_stage_tiering(monkeypatch) -> None:
    params = _client(monkeypatch).build_params("sys", "usr", model="claude-haiku-4-5")
    assert params["model"] == "claude-haiku-4-5"


# ------------------------------------------------------------------- complete


def test_complete_skips_non_text_leading_blocks(monkeypatch) -> None:
    """Indexing content[0] blindly is what broke this client on Sonnet 5."""
    client = _client(monkeypatch)
    message = SimpleNamespace(
        content=[SimpleNamespace(type="thinking"), _text("the answer")],
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
    )
    client.client = MagicMock(messages=MagicMock(create=AsyncMock(return_value=message)))
    assert asyncio.run(client.complete("sys", "usr")) == "the answer"


def test_complete_raises_when_there_is_no_text_at_all(monkeypatch) -> None:
    client = _client(monkeypatch)
    message = SimpleNamespace(content=[SimpleNamespace(type="thinking")], usage=None)
    client.client = MagicMock(messages=MagicMock(create=AsyncMock(return_value=message)))
    with pytest.raises(ValueError):
        asyncio.run(client.complete("sys", "usr"))


# ---------------------------------------------------------------------- batch


class _Results:
    """Mimics the SDK: `await results(id)` yields an async iterator."""

    def __init__(self, entries):
        self._entries = entries

    def __await__(self):
        async def _self():
            return self
        return _self().__await__()

    def __aiter__(self):
        async def gen():
            for entry in self._entries:
                yield entry
        return gen()


def _entry(custom_id: str, text: str, status: str = "succeeded"):
    return SimpleNamespace(
        custom_id=custom_id,
        result=SimpleNamespace(
            type=status,
            message=SimpleNamespace(
                content=[_text(text)],
                usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            ),
        ),
    )


def _batched(client, entries, statuses=("ended",)):
    batches = MagicMock()
    batches.create = AsyncMock(return_value=SimpleNamespace(id="batch_1"))
    batches.retrieve = AsyncMock(
        side_effect=[SimpleNamespace(processing_status=s) for s in statuses]
    )
    batches.results = MagicMock(return_value=_Results(entries))
    client.client = MagicMock(messages=MagicMock(batches=batches))
    return batches


def test_batch_results_are_keyed_not_positional(monkeypatch) -> None:
    """The API returns results in any order. Collecting by position would
    mis-assign every single one, silently."""
    client = _client(monkeypatch)
    _batched(client, [_entry("c", "third"), _entry("a", "first"), _entry("b", "second")])
    out = asyncio.run(
        client.complete_batch(
            [
                BatchRequest("a", "s", "u"),
                BatchRequest("b", "s", "u"),
                BatchRequest("c", "s", "u"),
            ],
            poll_seconds=0,
        )
    )
    assert out == {"a": "first", "b": "second", "c": "third"}


def test_batch_drops_failed_entries_without_losing_the_run(monkeypatch) -> None:
    client = _client(monkeypatch)
    _batched(client, [_entry("a", "ok"), _entry("b", "", status="errored")])
    out = asyncio.run(
        client.complete_batch(
            [BatchRequest("a", "s", "u"), BatchRequest("b", "s", "u")], poll_seconds=0
        )
    )
    assert out == {"a": "ok"}


def test_batch_polls_until_ended(monkeypatch) -> None:
    client = _client(monkeypatch)
    batches = _batched(
        client, [_entry("a", "ok")], statuses=("in_progress", "in_progress", "ended")
    )
    out = asyncio.run(
        client.complete_batch([BatchRequest("a", "s", "u")], poll_seconds=0)
    )
    assert out == {"a": "ok"}
    assert batches.retrieve.await_count == 3


def test_batch_gives_up_rather_than_polling_forever(monkeypatch) -> None:
    client = _client(monkeypatch)
    _batched(client, [], statuses=("in_progress",) * 10)
    with pytest.raises(BatchNotReady):
        asyncio.run(
            client.complete_batch(
                [BatchRequest("a", "s", "u")], poll_seconds=1, max_wait_seconds=2
            )
        )


def test_empty_batch_makes_no_api_call(monkeypatch) -> None:
    client = _client(monkeypatch)
    batches = _batched(client, [])
    assert asyncio.run(client.complete_batch([])) == {}
    batches.create.assert_not_awaited()


def test_batch_requests_carry_per_item_schema_and_model(monkeypatch) -> None:
    client = _client(monkeypatch)
    batches = _batched(client, [_entry("a", "ok")])
    asyncio.run(
        client.complete_batch(
            [
                BatchRequest(
                    "a", "s", "u", schema={"type": "object"},
                    effort="low", model="claude-sonnet-5",
                )
            ],
            poll_seconds=0,
        )
    )
    sent = batches.create.await_args.kwargs["requests"][0]
    assert sent["custom_id"] == "a"
    assert sent["params"]["model"] == "claude-sonnet-5"
    assert sent["params"]["output_config"]["effort"] == "low"


# ------------------------------------------- model capability gating


def test_effort_is_dropped_for_models_that_reject_it(monkeypatch) -> None:
    """The gate batch of 2026-08-20 lost all 247 items to this.

    `output_config.effort` is rejected on Haiku 4.5. Sending it failed every
    entry in the batch, and the gate's keep-on-no-verdict fallback then made a
    total failure look like a permissive gate that kept everything.
    """
    params = _client(monkeypatch).build_params(
        "sys", "usr", model="claude-haiku-4-5", effort="low"
    )
    assert "output_config" not in params or "effort" not in params["output_config"]
    assert "thinking" not in params


def test_schema_still_sent_to_older_models(monkeypatch) -> None:
    """Structured outputs are supported on Haiku 4.5; only effort is not."""
    params = _client(monkeypatch).build_params(
        "sys", "usr", model="claude-haiku-4-5", schema={"type": "object"}, effort="low"
    )
    assert params["output_config"]["format"]["type"] == "json_schema"
    assert "effort" not in params["output_config"]


def test_effort_and_thinking_kept_for_models_that_accept_them(monkeypatch) -> None:
    params = _client(monkeypatch).build_params(
        "sys", "usr", model="claude-sonnet-5", effort="high"
    )
    assert params["output_config"]["effort"] == "high"
    assert params["thinking"] == {"type": "disabled"}


def test_dated_snapshot_ids_resolve_by_prefix(monkeypatch) -> None:
    from src.ai.client import supports_modern_params

    assert supports_modern_params("claude-haiku-4-5-20251001") is False
    assert supports_modern_params("claude-sonnet-5") is True
    assert supports_modern_params("") is False


def test_batch_failure_logs_the_reason_not_just_the_category(monkeypatch, caplog) -> None:
    """"errored" seven times said nothing about why and cost a log download."""
    import logging
    from types import SimpleNamespace

    client = _client(monkeypatch)
    entry = SimpleNamespace(
        custom_id="gate-0",
        result=SimpleNamespace(
            type="errored",
            error=SimpleNamespace(type="invalid_request_error",
                                  message="effort not supported"),
        ),
    )
    _batched(client, [entry])
    with caplog.at_level(logging.WARNING):
        asyncio.run(
            client.complete_batch([BatchRequest("gate-0", "s", "u")], poll_seconds=0)
        )
    assert "effort not supported" in caplog.text


def test_batch_keeps_why_each_entry_stopped(monkeypatch, caplog) -> None:
    """NEWS-Radar N-267: a response cut at the ceiling still arrives as text, so
    the stop reason is the only evidence the batch was truncated."""
    client = _client(monkeypatch)
    cut = _entry("a", '{"verdicts": [')
    cut.result.message.stop_reason = "max_tokens"
    done = _entry("b", "{}")
    done.result.message.stop_reason = "end_turn"
    _batched(client, [cut, done])
    with caplog.at_level("WARNING"):
        out = asyncio.run(client.complete_batch(
            [BatchRequest("a", "s", "u"), BatchRequest("b", "s", "u")], poll_seconds=0
        ))
    assert set(out) == {"a", "b"}
    assert client.last_batch_stops == {"a": "max_tokens", "b": "end_turn"}
    assert "stopped at max_tokens" in caplog.text
