"""OpenRouter client: balance checks and cost-reporting chat completions.

Two things this module exists for, both mandated by the run protocol in
``00_plan/MASTER_PLAN.md`` part C:

1. ``get_balance`` is called before every run, including every resume, so a
   run never starts that cannot finish.
2. ``chat`` asks OpenRouter to return the authoritative cost of each call
   (``usage.include``), so the ledger records what was actually charged
   rather than a price-list estimate.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

API_ROOT = "https://openrouter.ai/api/v1"
KEY_ENV = "OPENROUTER_API_KEY"


from .errors import InsufficientBalance, ProviderExhausted  # noqa: F401


def _key(explicit: str | None = None) -> str:
    key = explicit or os.environ.get(KEY_ENV)
    if not key:
        raise RuntimeError(
            f"No API key. Set {KEY_ENV} in the environment, or pass one "
            f"explicitly. The key is never written to disk or to the ledger."
        )
    return key


def _request(path: str, api_key: str, body: dict | None = None, timeout: int = 120):
    url = f"{API_ROOT}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST" if data else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        if exc.code in (402, 403) and "credit" in detail.lower():
            raise InsufficientBalance(f"HTTP {exc.code}: {detail}") from exc
        raise RuntimeError(f"HTTP {exc.code} on {path}: {detail}") from exc


@dataclass
class Balance:
    total: float
    used: float

    @property
    def remaining(self) -> float:
        return round(self.total - self.used, 6)

    def __str__(self) -> str:
        return (
            f"balance: ${self.remaining:.4f} remaining "
            f"(${self.used:.4f} used of ${self.total:.4f})"
        )


def get_balance(api_key: str | None = None) -> Balance:
    """Current key balance. Called before every run and after every run."""
    key = _key(api_key)
    payload = _request("/credits", key)
    data = payload.get("data", payload)
    return Balance(
        total=float(data.get("total_credits", 0.0)),
        used=float(data.get("total_usage", 0.0)),
    )


def chat(
    model: str,
    messages: list[dict[str, Any]],
    api_key: str | None = None,
    **params: Any,
) -> dict[str, Any]:
    """One chat completion, with authoritative cost accounting requested.

    Returns the raw OpenRouter response. No retry: a failed call is recorded
    as an error and retried on the next run, so a transient fault can never
    turn into a loop that drains the key.
    """
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "usage": {"include": True},
        **params,
    }
    return _request("/chat/completions", _key(api_key), body)


def extract_usage(response: dict[str, Any]) -> tuple[int, int, float]:
    """(tokens_in, tokens_out, cost_usd) from an OpenRouter response.

    ``usage.cost`` is what OpenRouter actually charged. If it is absent the
    cost is recorded as 0.0 and flagged by the caller rather than guessed,
    because a guessed number in the spend ledger is worse than a missing one.
    """
    usage = response.get("usage") or {}
    return (
        int(usage.get("prompt_tokens", 0) or 0),
        int(usage.get("completion_tokens", 0) or 0),
        float(usage.get("cost", 0.0) or 0.0),
    )
