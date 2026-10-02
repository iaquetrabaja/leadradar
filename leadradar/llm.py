"""One structured-output call, three kinds of provider.

- anthropic          Claude (default) — official `anthropic` SDK.
- openai             ChatGPT models — official `openai` SDK.
- gemini             Google Gemini through its OpenAI-compatible endpoint.
- openai_compatible  Anything else that speaks the OpenAI API (OpenRouter, Groq,
                     Together, a local Ollama…): set `scoring.base_url`.

Every provider returns the same `Result`, so the scorer and the config generator
don't care which one is configured.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from pydantic import BaseModel

log = logging.getLogger("leadradar")

PROVIDERS = {
    "anthropic": {"key": "ANTHROPIC_API_KEY", "model": "claude-haiku-4-5", "base_url": None},
    "openai": {"key": "OPENAI_API_KEY", "model": "gpt-5-mini", "base_url": None},
    "gemini": {
        "key": "GEMINI_API_KEY",
        "model": "gemini-3.8-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    },
    "openai_compatible": {"key": "LLM_API_KEY", "model": None, "base_url": None},
}

# USD per million tokens (input, output, cached input) — only for the cost estimate in logs.
# Unknown models just log tokens; set `scoring.price: [input, output]` to get an estimate.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20),
    "claude-haiku-4-5": (1.0, 5.0, 0.10),
    "gpt-5-mini": (0.25, 2.0, 0.025),
    "gpt-5-nano": (0.05, 0.40, 0.005),
    "gpt-4o-mini": (0.15, 0.60, 0.075),
}


class RateLimited(Exception):
    pass


@dataclass
class Result:
    parsed: BaseModel | None
    stop: str  # ok | refusal | truncated | unusable
    detail: str = ""
    usage: dict = field(default_factory=dict)


def detect_provider() -> str:
    """For `init --describe`: use whichever key the user has set."""
    for name in ("anthropic", "openai", "gemini"):
        if os.environ.get(PROVIDERS[name]["key"], "").strip():
            return name
    return "anthropic"


class LLM:
    def __init__(self, scoring: dict):
        self.provider = scoring.get("provider") or "anthropic"
        if self.provider not in PROVIDERS:
            raise SystemExit(f"scoring.provider must be one of: {', '.join(PROVIDERS)}")
        spec = PROVIDERS[self.provider]
        self.model = scoring.get("model") or spec["model"]
        if not self.model:
            raise SystemExit("scoring.model is required for provider openai_compatible")
        self.effort = scoring.get("effort") or "low"
        price = scoring.get("price")
        self.price = (float(price[0]), float(price[1]), float(price[2]) if len(price) > 2 else 0.0) if price else PRICES.get(self.model)
        key = os.environ.get(spec["key"], "").strip()
        if not key:
            raise SystemExit(f"scoring.provider={self.provider} needs {spec['key']} in .env / GitHub secrets")

        if self.provider == "anthropic":
            import anthropic

            self.client = anthropic.Anthropic(api_key=key)
        else:
            from openai import OpenAI

            base_url = scoring.get("base_url") or spec["base_url"]
            if self.provider == "openai_compatible" and not base_url:
                raise SystemExit("scoring.base_url is required for provider openai_compatible")
            self.client = OpenAI(api_key=key, base_url=base_url)
            self._send_effort = True  # dropped automatically if the model rejects it

    def describe(self) -> str:
        return f"{self.provider}/{self.model}"

    def cost(self, usage: dict) -> float | None:
        if not self.price:
            return None
        pin, pout, pcache = self.price
        fresh = usage.get("input", 0) - usage.get("cache_read", 0) if self.provider != "anthropic" else usage.get("input", 0)
        return (
            (fresh + usage.get("cache_write", 0) * 1.25) * pin
            + usage.get("output", 0) * pout
            + usage.get("cache_read", 0) * pcache
        ) / 1e6

    def parse(self, system: str, user: str, schema: type[BaseModel], max_tokens: int = 16000) -> Result:
        if self.provider == "anthropic":
            return self._anthropic(system, user, schema, max_tokens)
        return self._openai(system, user, schema, max_tokens)

    # ── Claude ────────────────────────────────────────────────────────────
    def _anthropic(self, system, user, schema, max_tokens) -> Result:
        import anthropic

        options = {}
        if not self.model.startswith("claude-haiku"):
            # Effort and server-side fallback exist on the newer models only.
            options = {
                "output_config": {"effort": self.effort},
                "betas": ["server-side-fallback-2026-07-01"],
                "fallbacks": "default",
            }
        try:
            r = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=max_tokens,
                # Frozen system prompt -> cached across batches and runs.
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                **options,
            )
        except anthropic.RateLimitError as e:
            raise RateLimited(str(e)) from e
        usage = {
            "input": r.usage.input_tokens,
            "output": r.usage.output_tokens,
            "cache_read": r.usage.cache_read_input_tokens or 0,
            "cache_write": r.usage.cache_creation_input_tokens or 0,
        }
        if r.stop_reason == "refusal":
            return Result(None, "refusal", str(r.stop_details), usage)
        if r.stop_reason == "max_tokens":
            return Result(None, "truncated", "", usage)
        if r.parsed_output is None:
            return Result(None, "unusable", str(r.stop_reason), usage)
        return Result(r.parsed_output, "ok", "", usage)

    # ── OpenAI / Gemini / compatible ──────────────────────────────────────
    def _openai(self, system, user, schema, max_tokens) -> Result:
        import openai

        kwargs = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": schema,
        }
        # OpenAI's reasoning models only accept max_completion_tokens; others use max_tokens.
        kwargs["max_completion_tokens" if self.provider == "openai" else "max_tokens"] = max_tokens
        if self._send_effort:
            kwargs["reasoning_effort"] = self.effort  # less thinking = cheaper triage
        try:
            c = self.client.chat.completions.parse(**kwargs)
        except openai.BadRequestError as e:
            if self._send_effort and "reasoning" in str(e).lower():
                log.info("%s doesn't take reasoning_effort; retrying without it", self.model)
                self._send_effort = False
                return self._openai(system, user, schema, max_tokens)
            raise
        except openai.RateLimitError as e:
            raise RateLimited(str(e)) from e
        except openai.LengthFinishReasonError:
            return Result(None, "truncated")
        except openai.ContentFilterFinishReasonError:
            return Result(None, "refusal", "content_filter")
        u = c.usage
        details = getattr(u, "prompt_tokens_details", None) if u else None
        usage = {
            "input": u.prompt_tokens if u else 0,
            "output": u.completion_tokens if u else 0,
            "cache_read": (getattr(details, "cached_tokens", 0) or 0) if details else 0,
            "cache_write": 0,
        }
        msg = c.choices[0].message
        if getattr(msg, "refusal", None):
            return Result(None, "refusal", msg.refusal, usage)
        if msg.parsed is None:
            return Result(None, "unusable", c.choices[0].finish_reason or "", usage)
        return Result(msg.parsed, "ok", "", usage)
