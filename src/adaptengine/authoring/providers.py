"""LLM provider interface for the agentic layer (W8 K.1, D56). Disabled by default.

Every provider implements complete(prompt, *, task, payload) -> str (the model's text reply).
`task` and `payload` let the offline StubProvider answer deterministically without a model;
network providers ignore them and send only the prompt.

- StubProvider: deterministic templates for tests, CI and the demo (no network).
- AnthropicProvider: Claude via the official `anthropic` SDK (optional `[agents]` extra; reads
  credentials from the environment). Current Claude models reject sampling parameters such as
  temperature, so reproducibility comes from CachedProvider, not temperature 0 (deviation, notes).
- OllamaProvider: a local model through Ollama's HTTP API (temperature 0, JSON format).
- CachedProvider: wraps any provider; caches replies by prompt hash on disk so evaluations and the
  demo replay offline and deterministically; replay_only=True never calls the wrapped provider.

Only adaptengine.authoring, adaptengine.agents, the CLI and the demo API import this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Protocol


class ProviderError(RuntimeError):
    """A provider could not produce a reply (unavailable, refused, timed out, cache miss)."""


class Provider(Protocol):
    name: str
    model: str

    def complete(self, prompt: str, *, task: str, payload: Optional[dict] = None) -> str: ...


def prompt_hash(provider_name: str, model: str, task: str, prompt: str) -> str:
    key = "\x1f".join((provider_name, model, task, prompt))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------ stub


class StubProvider:
    """Deterministic, offline. `responders` maps task -> fn(payload) -> reply text to override."""

    name = "stub"
    model = "template-stub-1"

    def __init__(self, responders: Optional[dict[str, Callable[[dict], str]]] = None):
        self.responders = dict(responders or {})
        self.calls = 0

    def complete(self, prompt: str, *, task: str, payload: Optional[dict] = None) -> str:
        self.calls += 1
        payload = payload or {}
        if task in self.responders:
            return self.responders[task](payload)
        if task == "rank":
            return json.dumps(
                {
                    "ranking": list(payload.get("candidates", [])),
                    "rationale": "Stub: keeps the engine's deterministic order.",
                }
            )
        if task == "propose_plan":
            ref = payload.get("reference_days", [])
            return json.dumps({"days": ref, "rationale": "Stub: repeats the engine's plan."})
        if task == "orchestrate":
            opts = payload.get("options", [])
            return json.dumps(
                {
                    "option": opts[0]["id"] if opts else "continue",
                    "rationale": "Stub: follows the engine's default tier order.",
                }
            )
        if task == "draft":
            from .draft import template_draft  # local import: draft imports this module

            return json.dumps(template_draft(payload))
        raise ProviderError(f"stub has no template for task {task!r}")


# ------------------------------------------------------------------------- anthropic


class AnthropicProvider:
    """Claude through the official SDK. Needs `pip install -e ".[agents]"` and credentials
    (ANTHROPIC_API_KEY, or an `ant auth login` profile)."""

    name = "anthropic"

    def __init__(
        self,
        model: str = "claude-opus-5-5",
        *,
        timeout: float = 60.0,
        effort: str = "medium",
        max_tokens: int = 16000,
        system: str = "You answer with a single JSON object and nothing else.",
    ):
        try:
            import anthropic
        except ImportError as e:  # optional extra
            raise ProviderError("anthropic SDK not installed: pip install -e '.[agents]'") from e
        self._anthropic = anthropic
        self.model, self.effort, self.max_tokens, self.system = model, effort, max_tokens, system
        self.client = anthropic.Anthropic(timeout=timeout, max_retries=2)

    def complete(self, prompt: str, *, task: str, payload: Optional[dict] = None) -> str:
        a = self._anthropic
        try:
            # Server-side refusal fallback is on by default for current Opus models.
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system,
                output_config={"effort": self.effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[{"role": "user", "content": prompt}],
            )
        except a.APITimeoutError as e:
            raise ProviderError(f"timeout: {e}") from e
        except (a.APIStatusError, a.APIConnectionError) as e:
            raise ProviderError(f"{type(e).__name__}: {e}") from e
        if response.stop_reason == "refusal":
            raise ProviderError(f"model refused: {response.stop_details}")
        return "".join(b.text for b in response.content if b.type == "text").strip()


# ---------------------------------------------------------------------------- ollama


class OllamaProvider:
    """A local model via Ollama (offline once the model is pulled)."""

    name = "ollama"

    def __init__(
        self,
        model: str = "llama3.1:8b",
        host: str = "http://localhost:11434",
        timeout: float = 120.0,
    ):
        self.model, self.host, self.timeout = model, host.rstrip("/"), timeout

    def complete(self, prompt: str, *, task: str, payload: Optional[dict] = None) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0, "seed": 0},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/generate", data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))["response"]
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
            raise ProviderError(f"ollama: {e}") from e


# ----------------------------------------------------------------------------- cache


class CachedProvider:
    """Disk cache by prompt hash (L.2). Records model, prompt hash, latency and timestamp."""

    def __init__(self, inner: Any, cache_dir: str, replay_only: bool = False):
        self.inner, self.cache_dir, self.replay_only = inner, cache_dir, replay_only
        self.name, self.model = inner.name, inner.model
        self.hits = self.misses = 0
        os.makedirs(cache_dir, exist_ok=True)

    def _path(self, h: str) -> str:
        return os.path.join(self.cache_dir, f"{h}.json")

    def complete(self, prompt: str, *, task: str, payload: Optional[dict] = None) -> str:
        h = prompt_hash(self.inner.name, self.inner.model, task, prompt)
        path = self._path(h)
        if os.path.exists(path):
            self.hits += 1
            with open(path, encoding="utf-8") as f:
                return json.load(f)["response"]
        self.misses += 1
        if self.replay_only:
            raise ProviderError(f"cache miss in replay-only mode ({h[:12]})")
        t0 = time.perf_counter()
        text = self.inner.complete(prompt, task=task, payload=payload)
        rec = {
            "prompt_hash": h,
            "provider": self.inner.name,
            "model": self.inner.model,
            "task": task,
            "latency_s": round(time.perf_counter() - t0, 3),
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "prompt": prompt,
            "response": text,
        }
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=1)
        os.replace(tmp, path)
        return text


def make_provider(spec: str, cache_dir: Optional[str] = None, replay_only: bool = False):
    """'stub' | 'anthropic[:model]' | 'ollama[:model]', optionally wrapped in the disk cache."""
    kind, _, model = spec.partition(":")
    if kind == "stub":
        p: Any = StubProvider()
    elif kind == "anthropic":
        p = AnthropicProvider(model or "claude-opus-5-5")
    elif kind == "ollama":
        p = OllamaProvider(model or "llama3.1:8b")
    else:
        raise ValueError(f"unknown provider {spec!r}")
    return CachedProvider(p, cache_dir, replay_only) if cache_dir else p
