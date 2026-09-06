"""AI client abstraction supporting multiple providers."""

import asyncio
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from openai import AsyncAzureOpenAI, AsyncOpenAI
from anthropic import AsyncAnthropic
from google import genai
from google.genai import types


import logging

from ..models import AIConfig, AIProvider, AI_PROVIDER_DEFAULTS
from .tokens import record_usage

logger = logging.getLogger(__name__)


_ENV_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SECRET_PREFIXES = (
    "sk-",
    "sk_",
    "AIza",
    "xai-",
    "gsk_",
    "hf_",
)
_DEFAULT_API_KEY_ENVS = {
    AIProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
    AIProvider.OPENAI: "OPENAI_API_KEY",
    AIProvider.AZURE: "AZURE_OPENAI_API_KEY",
    AIProvider.ALI: "DASHSCOPE_API_KEY",
    AIProvider.GEMINI: "GOOGLE_API_KEY",
    AIProvider.DOUBAO: "DOUBAO_API_KEY",
    AIProvider.MINIMAX: "MINIMAX_API_KEY",
    AIProvider.DEEPSEEK: "DEEPSEEK_API_KEY",
}


def _resolve_api_key(config: AIConfig, *, fallback: Optional[str] = None) -> str:
    api_key = os.getenv(config.api_key_env)
    if api_key:
        return api_key
    if fallback is not None:
        return fallback
    raise ValueError(_missing_api_key_message(config))


def _missing_api_key_message(config: AIConfig) -> str:
    expected_env = _DEFAULT_API_KEY_ENVS.get(config.provider)
    if expected_env:
        setup_hint = (
            f"Set {expected_env}=your_api_key in .env or your shell, then set "
            f'ai.api_key_env to "{expected_env}" in data/config.json.'
        )
    else:
        setup_hint = (
            "Set the provider API key in .env or your shell, then set "
            "ai.api_key_env to that environment variable name in data/config.json."
        )

    if _looks_like_api_key_value(config.api_key_env):
        return (
            "Missing API key: ai.api_key_env must be an environment variable "
            f"name, not the API key value. {setup_hint}"
        )

    return (
        "Missing API key environment variable configured by ai.api_key_env. "
        "ai.api_key_env should contain the environment variable name, not the "
        f"key value. {setup_hint}"
    )


def _looks_like_api_key_value(value: str) -> bool:
    if value.startswith(_SECRET_PREFIXES):
        return True
    return not bool(_ENV_VAR_RE.fullmatch(value))


def _normalize_ollama_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if "://" not in normalized:
        normalized = f"http://{normalized}"
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


# Not every model accepts the modern request surface, and sending a parameter a
# model rejects fails the whole call. The gate batch of 2026-08-20 lost all 247
# items this way: `output_config.effort` is rejected on Haiku 4.5, so every entry
# errored, and the gate's keep-on-no-verdict fallback then made a total failure
# look like a permissive gate.
#
# Matched on prefix so dated snapshots (claude-haiku-4-5-20251001) resolve too.
_MODERN_PARAM_PREFIXES = (
    "claude-opus-5",
    "claude-opus-4-6",
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-sonnet-5",
    "claude-sonnet-4-6",
)


def supports_modern_params(model: str) -> bool:
    """Whether `output_config.effort` and `thinking: disabled` are accepted."""
    return str(model or "").startswith(_MODERN_PARAM_PREFIXES)


class AIClient(ABC):
    """Abstract base class for AI clients."""

    @abstractmethod
    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        *,
        model: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        effort: Optional[str] = None,
    ) -> str:
        """Generate completion from AI model.

        Args:
            system: System prompt
            user: User prompt
            temperature: Optional sampling temperature override
            max_tokens: Optional maximum tokens override
            model: Optional per-call model override, for per-stage model tiering
            schema: Optional JSON Schema constraining the response
            effort: Optional reasoning effort, one of low/medium/high/xhigh/max

        Returns:
            str: Generated completion text
        """
        pass


class AnthropicClient(AIClient):
    """Client for Anthropic-compatible models."""

    def __init__(self, config: AIConfig):
        """Initialize Anthropic client.

        Args:
            config: AI configuration
        """
        self.config = config

        api_key = _resolve_api_key(config)

        kwargs = {"api_key": api_key}
        if config.base_url:
            kwargs["base_url"] = config.base_url

        self.client = AsyncAnthropic(**kwargs)
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

    def build_params(
        self,
        system: str,
        user: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        effort: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build one request body, shared by the live and batch paths.

        Kept separate so the batch path cannot drift from the live one, and so
        request shaping is testable without a network call.
        """
        chosen_model = model or self.model
        modern = supports_modern_params(chosen_model)

        params: Dict[str, Any] = {
            "model": chosen_model,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
            "temperature": self.temperature if temperature is None else temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if modern:
            params["thinking"] = {"type": "disabled"}

        # `output_config` carries both the response format and the effort level,
        # so build it once rather than setting the key twice. Effort is dropped
        # for models that reject it rather than passed through and left to fail.
        output_config: Dict[str, Any] = {}
        if schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        if effort is not None:
            if modern:
                output_config["effort"] = effort
            else:
                logger.debug(
                    "Dropping effort=%s: unsupported on %s", effort, chosen_model
                )
        if output_config:
            params["output_config"] = output_config
        if tools:
            params["tools"] = tools

        return params

    def _record(self, message: Any) -> None:
        usage = getattr(message, "usage", None)
        if usage is not None:
            record_usage(
                self.config.provider.value,
                input_tokens=getattr(usage, "input_tokens", 0),
                output_tokens=getattr(usage, "output_tokens", 0),
                # The response says which model served it, so this is measured
                # rather than inferred from what we asked for.
                model=getattr(message, "model", None),
            )

    @staticmethod
    def _last_text(message: Any) -> str:
        """Return the final text block.

        With server-side tools the model narrates between tool calls, so the
        answer is the last text block rather than the first. Taking the first
        would return a preamble like "let me search for that".
        """
        texts = [
            block.text
            for block in message.content
            if getattr(block, "type", None) == "text"
        ]
        if not texts:
            raise ValueError("Response contained no text block")
        return texts[-1]

    @staticmethod
    def _first_text(message: Any) -> str:
        """Return the first text block, skipping any non-text blocks.

        Indexing content[0] blindly is what broke this client on Sonnet 5, whose
        first block was a ThinkingBlock. Thinking is disabled here, but a server
        tool result can also lead the list, so select by type rather than position.
        """
        for block in message.content:
            if getattr(block, "type", None) == "text":
                return block.text
        raise ValueError("Response contained no text block")

    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        *,
        model: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        effort: Optional[str] = None,
    ) -> str:
        """Generate completion using Claude."""
        message = await self.client.messages.create(
            **self.build_params(
                system,
                user,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
                schema=schema,
                effort=effort,
            )
        )
        self._record(message)
        return self._first_text(message)

    async def complete_with_tools(
        self,
        system: str,
        user: str,
        tools: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        effort: Optional[str] = None,
        max_tokens: Optional[int] = None,
        max_continuations: int = 4,
    ) -> str:
        """Run a completion with server-side tools, resuming if the turn pauses.

        Server tools run on Anthropic's side, so there is no execution loop here.
        There is still a continuation loop: a long tool-using turn can stop with
        `pause_turn`, and a caller that ignores that gets a silently truncated
        answer with no error raised.
        """
        params = self.build_params(
            system,
            user,
            max_tokens=max_tokens,
            model=model,
            schema=schema,
            effort=effort,
            tools=tools,
        )
        messages = list(params["messages"])

        for _ in range(max_continuations + 1):
            params["messages"] = messages
            message = await self.client.messages.create(**params)
            self._record(message)
            if getattr(message, "stop_reason", None) != "pause_turn":
                return self._last_text(message)
            # Re-send the paused turn so the server picks up where it stopped.
            messages = messages + [{"role": "assistant", "content": message.content}]

        logger.warning("Tool turn still paused after %d continuations", max_continuations)
        return self._last_text(message)

    async def complete_batch(
        self,
        requests: List["BatchRequest"],
        *,
        poll_seconds: float = 20.0,
        max_wait_seconds: float = 3600.0,
    ) -> Dict[str, str]:
        """Run many independent completions through the Batch API at half price.

        Suited to scheduled work with no latency requirement: the radar runs once
        a day and its per-item stages are mutually independent, so an hour of
        latency costs nothing and the discount is free.

        Returns a mapping of `custom_id` to text. Failed or expired entries are
        omitted rather than raising, so one bad item cannot lose a whole run; the
        caller compares the returned keys against what it submitted.
        """
        if not requests:
            return {}

        batch = await self.client.messages.batches.create(
            requests=[
                {
                    "custom_id": request.custom_id,
                    "params": self.build_params(
                        request.system,
                        request.user,
                        max_tokens=request.max_tokens,
                        model=request.model,
                        schema=request.schema,
                        effort=request.effort,
                    ),
                }
                for request in requests
            ]
        )

        waited = 0.0
        while True:
            current = await self.client.messages.batches.retrieve(batch.id)
            if current.processing_status == "ended":
                break
            if waited >= max_wait_seconds:
                raise BatchNotReady(
                    f"Batch {batch.id} still {current.processing_status} after "
                    f"{int(waited)}s"
                )
            await asyncio.sleep(poll_seconds)
            waited += poll_seconds

        # Results come back in arbitrary order, so key by custom_id. Collecting
        # by position is the classic way to silently mis-assign every result.
        collected: Dict[str, str] = {}
        async for entry in await self.client.messages.batches.results(batch.id):
            if entry.result.type != "succeeded":
                # Log the reason, not just the category. The 2026-08-20 gate
                # failure reported only "errored" seven times, which said
                # nothing about why and cost a log download to diagnose.
                error = getattr(entry.result, "error", None)
                detail = getattr(error, "message", None) or getattr(
                    error, "type", ""
                )
                logger.warning(
                    "Batch entry %s did not succeed: %s%s",
                    entry.custom_id,
                    entry.result.type,
                    f" ({detail})" if detail else "",
                )
                continue
            message = entry.result.message
            self._record(message)
            try:
                collected[entry.custom_id] = self._first_text(message)
            except ValueError:
                logger.warning("Batch entry %s returned no text", entry.custom_id)

        missing = {r.custom_id for r in requests} - set(collected)
        if missing:
            logger.warning(
                "Batch %s returned %d of %d results", batch.id, len(collected), len(requests)
            )
        return collected


@dataclass(frozen=True)
class BatchRequest:
    """One unit of work for the Batch API, addressed by `custom_id`."""

    custom_id: str
    system: str
    user: str
    schema: Optional[Dict[str, Any]] = None
    effort: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = None


class BatchNotReady(RuntimeError):
    """A batch did not finish inside the allotted wait."""


class OpenAIClient(AIClient):
    """Client for OpenAI-compatible APIs."""

    _BASE_URL_ENVS = {
        "ollama": (
            "HORIZON_OLLAMA_BASE_URL",
            "OLLAMA_BASE_URL",
            "OLLAMA_HOST",
        ),
    }

    # Providers that don't support response_format
    _NO_RESPONSE_FORMAT = {"minimax"}

    # Providers that need temperature clamped to (0, 1]
    _TEMP_CLAMP = {"minimax"}

    # Newer reasoning-series / GPT-5 family models reject legacy `max_tokens`
    # and require `max_completion_tokens` instead.
    _MODELS_REQUIRING_MAX_COMPLETION_TOKENS = ("o1", "o3", "o4", "gpt-5")

    def __init__(self, config: AIConfig):
        """Initialize OpenAI-compatible client.

        Args:
            config: AI configuration
        """
        self.config = config

        fallback = "no_key" if config.provider == AIProvider.OLLAMA else None
        api_key = _resolve_api_key(config, fallback=fallback)

        kwargs = {"api_key": api_key}
        base_url = self._resolve_base_url(config)
        if base_url:
            kwargs["base_url"] = base_url

        self.client = AsyncOpenAI(**kwargs)
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.provider = config.provider.value
        # Some newer models (e.g. Claude Opus 4.7 on Bedrock Converse) reject
        # `temperature`. We learn this on first 400 and stop sending it.
        self._supports_temperature = True
        self._use_max_completion_tokens = any(
            config.model.startswith(prefix)
            for prefix in self._MODELS_REQUIRING_MAX_COMPLETION_TOKENS
        )

    @classmethod
    def _resolve_base_url(cls, config: AIConfig) -> Optional[str]:
        base_url = (config.base_url or "").strip()
        if not base_url:
            for env_name in cls._BASE_URL_ENVS.get(config.provider.value, ()):
                base_url = os.getenv(env_name, "").strip()
                if base_url:
                    break
        if not base_url:
            base_url = AI_PROVIDER_DEFAULTS.get(config.provider, {}).get("base_url") or ""

        if config.provider == AIProvider.OLLAMA and base_url:
            return _normalize_ollama_base_url(base_url)
        return base_url or None

    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate completion using OpenAI-compatible API.

        Args:
            system: System prompt
            user: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            str: Generated text
        """
        temperature = self.temperature if temperature is None else temperature
        max_tokens = self.max_tokens if max_tokens is None else max_tokens

        # Clamp temperature for providers that require it
        if self.provider in self._TEMP_CLAMP and temperature <= 0:
            temperature = 0.01

        try:
            response = await self._do_request(
                system=system,
                user=user,
                temperature=temperature,
                max_tokens=max_tokens,
                include_temperature=self._supports_temperature,
                use_max_completion_tokens=self._use_max_completion_tokens,
            )
        except Exception as exc:
            if self._supports_temperature and self._is_temperature_unsupported(str(exc)):
                self._supports_temperature = False
                response = await self._do_request(
                    system=system,
                    user=user,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    include_temperature=False,
                    use_max_completion_tokens=self._use_max_completion_tokens,
                )
            elif not self._use_max_completion_tokens and self._is_max_tokens_unsupported(str(exc)):
                self._use_max_completion_tokens = True
                response = await self._do_request(
                    system=system,
                    user=user,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    include_temperature=self._supports_temperature,
                    use_max_completion_tokens=True,
                )
            else:
                raise
        usage = getattr(response, "usage", None)
        if usage is not None:
            record_usage(
                self.provider,
                input_tokens=getattr(usage, "prompt_tokens", 0),
                output_tokens=getattr(usage, "completion_tokens", 0),
            )
        return response.choices[0].message.content

    async def _do_request(
        self,
        *,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        include_temperature: bool,
        use_max_completion_tokens: bool,
    ):
        request_kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        token_param = "max_completion_tokens" if use_max_completion_tokens else "max_tokens"
        request_kwargs[token_param] = max_tokens
        if include_temperature:
            request_kwargs["temperature"] = temperature
        if self.provider not in self._NO_RESPONSE_FORMAT:
            request_kwargs["response_format"] = {"type": "json_object"}
        return await self.client.chat.completions.create(**request_kwargs)

    @staticmethod
    def _is_temperature_unsupported(message: str) -> bool:
        lowered = message.lower()
        return "temperature" in lowered and (
            "deprecated" in lowered
            or "not support" in lowered
            or "unsupported" in lowered
        )

    @staticmethod
    def _is_max_tokens_unsupported(message: str) -> bool:
        lowered = message.lower()
        return "max_tokens" in lowered and "max_completion_tokens" in lowered


class AzureOpenAIClient(AIClient):
    """Client for Azure OpenAI deployments.

    Uses the native AsyncAzureOpenAI client, which requires the deployment
    name (passed as `model`), azure_endpoint (resource base URL), and
    api_version. The deployment path is assembled internally by the SDK.
    """

    # Newer reasoning-series models reject legacy `max_tokens` and require
    # `max_completion_tokens` instead. Azure uses deployment names as `model`,
    # so a best-effort guess can be wrong for custom deployment aliases.
    _MODELS_REQUIRING_MAX_COMPLETION_TOKENS = ("o1", "o3", "o4", "gpt-5")

    def __init__(self, config: AIConfig):
        """Initialize Azure OpenAI client.

        Args:
            config: AI configuration
        """
        self.config = config

        api_key = _resolve_api_key(config)
        if not config.azure_endpoint_env:
            raise ValueError("azure_endpoint_env is required for azure provider")
        azure_endpoint = os.getenv(config.azure_endpoint_env)
        if not azure_endpoint:
            raise ValueError(f"Missing Azure endpoint: {config.azure_endpoint_env}")
        if not config.api_version:
            raise ValueError("api_version is required for azure provider")

        self.client = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=azure_endpoint,
            api_version=config.api_version,
        )
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self._use_max_completion_tokens = any(
            config.model.startswith(prefix)
            for prefix in self._MODELS_REQUIRING_MAX_COMPLETION_TOKENS
        )

    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate completion using Azure OpenAI.

        Args:
            system: System prompt
            user: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            str: Generated text
        """
        temperature = self.temperature if temperature is None else temperature
        max_tokens = self.max_tokens if max_tokens is None else max_tokens

        try:
            response = await self._create_completion(
                system=system,
                user=user,
                temperature=temperature,
                max_tokens=max_tokens,
                use_max_completion_tokens=self._use_max_completion_tokens,
            )
        except Exception as exc:
            fallback = self._token_fallback_mode(str(exc))
            if fallback is None:
                raise

            self._use_max_completion_tokens = fallback
            response = await self._create_completion(
                system=system,
                user=user,
                temperature=temperature,
                max_tokens=max_tokens,
                use_max_completion_tokens=fallback,
            )

        usage = getattr(response, "usage", None)
        if usage is not None:
            record_usage(
                "openai",
                input_tokens=getattr(usage, "prompt_tokens", 0),
                output_tokens=getattr(usage, "completion_tokens", 0),
            )
        return response.choices[0].message.content

    async def _create_completion(
        self,
        *,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        use_max_completion_tokens: bool,
    ):
        tokens_kwarg = (
            {"max_completion_tokens": max_tokens}
            if use_max_completion_tokens
            else {"max_tokens": max_tokens}
        )
        return await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
            **tokens_kwarg,
        )

    @staticmethod
    def _token_fallback_mode(message: str) -> Optional[bool]:
        lowered = message.lower()
        if "max_completion_tokens" in lowered and "max_tokens" in lowered:
            return True
        if "max_tokens" in lowered and "max_completion_tokens" not in lowered:
            return False
        return None


class GeminiClient(AIClient):
    """Client for Google Gemini models."""

    def __init__(self, config: AIConfig):
        """Initialize Gemini client.

        Args:
            config: AI configuration
        """
        self.config = config

        api_key = _resolve_api_key(config)

        self.client = genai.Client(api_key=api_key)
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate completion using Gemini.

        Args:
            system: System prompt
            user: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            str: Generated text
        """
        temperature = self.temperature if temperature is None else temperature
        max_tokens = self.max_tokens if max_tokens is None else max_tokens

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json"
            )
        )
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            total = getattr(usage, "total_token_count", 0) or 0
            prompt = getattr(usage, "prompt_token_count", 0) or 0
            completion = max(0, total - prompt)
            record_usage("gemini", input_tokens=prompt, output_tokens=completion)
        return response.text


def _uses_anthropic_compatible_api(config: AIConfig) -> bool:
    """Return whether MiniMax is configured for its Anthropic-compatible API."""
    base_url = (config.base_url or "").rstrip("/")
    return config.provider == AIProvider.MINIMAX and base_url.endswith("/anthropic")


def _create_single_client(config: AIConfig) -> AIClient:
    """Create a single AI client instance."""
    if (
        config.provider == AIProvider.ANTHROPIC
        or _uses_anthropic_compatible_api(config)
    ):
        return AnthropicClient(config)
    elif config.provider == AIProvider.AZURE:
        return AzureOpenAIClient(config)
    elif config.provider == AIProvider.GEMINI:
        return GeminiClient(config)
    elif config.provider in {
        AIProvider.OPENAI,
        AIProvider.ALI,
        AIProvider.DOUBAO,
        AIProvider.MINIMAX,
        AIProvider.DEEPSEEK,
        AIProvider.OLLAMA,
    }:
        return OpenAIClient(config)
    else:
        raise ValueError(f"Unsupported AI provider: {config.provider}")


class ChainedAIClient(AIClient):
    """Chain multiple AI clients with automatic fallback.

    When a provider fails with a retryable error (rate limit, auth/quota,
    service unavailable, or empty response), automatically falls back to
    the next provider in the chain.

    Clients are created lazily so that missing API keys for downstream
    providers do not block startup when the primary provider works.
    """

    def __init__(
        self,
        configs: List[AIConfig],
        clients: Optional[List[AIClient]] = None,
        client_factory: Optional[Any] = None,
    ):
        self.configs = configs
        self._client_factory = client_factory or _create_single_client
        self._client_cache: Dict[int, AIClient] = {}
        # Allow tests to inject pre-built clients directly
        if clients is not None:
            for idx, client in enumerate(clients):
                self._client_cache[idx] = client

    def _get_client(self, index: int) -> AIClient:
        if index not in self._client_cache:
            self._client_cache[index] = self._client_factory(self.configs[index])
        return self._client_cache[index]

    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        last_error: Optional[Exception] = None
        for i in range(len(self.configs)):
            try:
                client = self._get_client(i)
                result = await client.complete(system, user, temperature, max_tokens)
                if not result or not result.strip():
                    raise ValueError("Empty response from provider")
                return result
            except Exception as exc:
                if not self._should_fallback(exc):
                    raise
                last_error = exc
                if i < len(self.configs) - 1:
                    logger.warning(
                        "Provider %s failed (%s), falling back to %s...",
                        self.configs[i].provider.value, exc, self.configs[i + 1].provider.value,
                    )
        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    @staticmethod
    def _should_fallback(exc: Exception) -> bool:
        """Determine if an error warrants fallback to the next provider."""
        msg = str(exc).lower()
        if "429" in msg or "rate limit" in msg:
            return True
        if "401" in msg or "403" in msg or "quota" in msg or "exceeded" in msg:
            return True
        if "502" in msg or "503" in msg or "service unavailable" in msg:
            return True
        if "empty response" in msg:
            return True
        return False


def _create_chained_client(config: AIConfig) -> ChainedAIClient:
    """Build a ChainedAIClient from a comma-separated provider chain."""
    provider_chain = config.provider_chain or ""
    provider_names = [p.strip() for p in provider_chain.split(",") if p.strip()]
    if not provider_names:
        raise ValueError("provider_chain is empty")

    chain_configs: List[AIConfig] = []
    for name in provider_names:
        try:
            provider = AIProvider(name)
        except ValueError:
            raise ValueError(f"Unsupported AI provider in chain: {name}")

        defaults = AI_PROVIDER_DEFAULTS.get(provider, {})
        base_url = config.base_url if provider == config.provider else defaults.get("base_url")
        cfg = AIConfig(
            provider=provider,
            model=defaults.get("model", config.model),
            api_key_env=defaults.get("api_key_env", config.api_key_env),
            base_url=base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            throttle_sec=config.throttle_sec,
            analysis_concurrency=config.analysis_concurrency,
            enrichment_concurrency=config.enrichment_concurrency,
            languages=config.languages,
            azure_endpoint_env=(
                config.azure_endpoint_env or defaults.get("azure_endpoint_env")
                if provider == AIProvider.AZURE
                else None
            ),
            api_version=(
                config.api_version or defaults.get("api_version")
                if provider == AIProvider.AZURE
                else None
            ),
        )
        chain_configs.append(cfg)

    return ChainedAIClient(chain_configs)


def create_ai_client(config: AIConfig) -> AIClient:
    """Factory function to create appropriate AI client.

    Args:
        config: AI configuration

    Returns:
        AIClient: Initialized AI client

    Raises:
        ValueError: If provider is not supported
    """
    if config.provider_chain:
        return _create_chained_client(config)
    return _create_single_client(config)
