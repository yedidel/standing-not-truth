"""Ollama Cloud provider: open-weight models, tool calling, no per-call charge.

Added so the model matrix can cover open-weight families without drawing on
the metered budget. Mistral, Qwen, DeepSeek, GLM, Kimi, Gemma and the
gpt-oss family are reachable here.

Two shape differences from OpenRouter matter to callers:

  * the reply is at ``message``, not ``choices[0].message``
  * ``tool_calls[].function.arguments`` is already a dict, not a JSON string

``normalize`` converts a response into the OpenAI shape so one judge can
score results from either provider without branching.
"""

from __future__ import annotations

import json
import os
import json as _json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import QuotaExhausted

API_ROOT = "https://ollama.com"
KEY_ENV = "OLLAMA_API_KEY"


def _key(explicit: str | None = None) -> str:
    key = explicit or os.environ.get(KEY_ENV)
    if not key:
        raise RuntimeError(f"No Ollama key. Set {KEY_ENV} in the environment.")
    return key


def list_models(api_key: str | None = None) -> list[str]:
    req = urllib.request.Request(
        f"{API_ROOT}/api/tags",
        headers={"Authorization": f"Bearer {_key(api_key)}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read())
    return [m.get("name") or m.get("model") for m in payload.get("models", [])]


def chat(
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict] | None = None,
    api_key: str | None = None,
    timeout: int = 300,
    **options: Any,
) -> dict[str, Any]:
    """One chat completion. No retry, matching the OpenRouter client."""
    body: dict[str, Any] = {"model": model, "messages": messages, "stream": False}
    if tools:
        body["tools"] = tools
    if options:
        body["options"] = options
    req = urllib.request.Request(
        f"{API_ROOT}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_key(api_key)}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        if _is_quota(exc.code, detail):
            raise QuotaExhausted(
                f"Ollama quota reached (HTTP {exc.code}): {detail}"
            ) from exc
        raise RuntimeError(f"HTTP {exc.code} on /api/chat: {detail}") from exc


def normalize(response: dict[str, Any]) -> dict[str, Any]:
    """Reshape an Ollama reply into the OpenAI response shape."""
    msg = dict(response.get("message") or {})
    calls = []
    for i, call in enumerate(msg.get("tool_calls") or []):
        fn = dict(call.get("function") or {})
        args = fn.get("arguments")
        if isinstance(args, dict):
            fn["arguments"] = json.dumps(args, ensure_ascii=False)
        calls.append({"id": call.get("id") or f"call_{i}", "function": fn})
    if calls:
        msg["tool_calls"] = calls
    out = dict(response)
    out["choices"] = [{"message": msg, "finish_reason": response.get("done_reason")}]
    return out


def denormalize_messages(messages: list[dict]) -> list[dict]:
    """Convert OpenAI-shaped history into what Ollama's /api/chat accepts.

    An assistant turn replaying a prior tool call carries
    ``function.arguments`` as a JSON string in the OpenAI schema. Ollama
    expects an object there and rejects the string with HTTP 400. This
    rewrites only that field and leaves every message otherwise intact.
    """
    out = []
    for m in messages:
        if not m.get("tool_calls"):
            out.append(m)
            continue
        m = dict(m)
        calls = []
        for c in m["tool_calls"]:
            c = dict(c)
            fn = dict(c.get("function") or {})
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    fn["arguments"] = json.loads(args or "{}")
                except json.JSONDecodeError:
                    fn["arguments"] = {}
            c["function"] = fn
            calls.append(c)
        m["tool_calls"] = calls
        out.append(m)
    return out


def extract_usage(response: dict[str, Any]) -> tuple[int, int, float]:
    """(tokens_in, tokens_out, cost_usd).

    Cost is recorded as 0.0 because the key is a flat-rate subscription and
    the API reports no per-call charge. That is a measured zero for this
    provider, not an unknown, and it is why Ollama runs do not consume the
    OpenRouter budget.
    """
    return (
        int(response.get("prompt_eval_count", 0) or 0),
        int(response.get("eval_count", 0) or 0),
        0.0,
    )


# --- quota handling -------------------------------------------------------

_QUOTA_WORDS = re.compile(
    r"quota|rate.?limit|too many requests|usage limit|weekly limit|exceeded",
    re.IGNORECASE,
)


def _is_quota(status: int, detail: str) -> bool:
    """True when the provider is refusing because a limit is spent.

    A 429 is unambiguous. Some providers return 402 or 403 with the reason
    only in the body, so the wording is checked as well. The consequence of
    a match is a clean stop rather than a retry, so a false positive costs a
    resumable pause and a false negative costs a wasted retry loop. We bias
    toward stopping.
    """
    return status == 429 or bool(_QUOTA_WORDS.search(detail))


def weekly_usage(experiments_dir: str | Path = None) -> dict[str, Any]:
    """Our own count of Ollama calls in the current ISO week.

    The API exposes no quota headers on a successful response, so the only
    way to know how much of a weekly allowance is gone is to count what we
    spent. This scans every experiment ledger for records tagged with this
    provider and buckets them by ISO week.
    """
    root = Path(experiments_dir or Path(__file__).resolve().parent.parent)
    now = datetime.now(timezone.utc).isocalendar()
    this_week = (now.year, now.week)
    calls = tokens_in = tokens_out = 0
    by_exp: dict[str, int] = {}
    for ledger in sorted(root.glob("*/ledger.jsonl")):
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = _json.loads(line)
            except _json.JSONDecodeError:
                continue
            if r.get("provider") != "ollama" or r.get("status") != "ok":
                continue
            ts = r.get("ts", "")
            try:
                d = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue
            iso = d.isocalendar()
            if (iso.year, iso.week) != this_week:
                continue
            calls += 1
            tokens_in += int(r.get("tokens_in", 0) or 0)
            tokens_out += int(r.get("tokens_out", 0) or 0)
            by_exp[r.get("exp", "?")] = by_exp.get(r.get("exp", "?"), 0) + 1
    return {
        "iso_week": f"{this_week[0]}-W{this_week[1]:02d}",
        "calls": calls,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "by_experiment": by_exp,
    }
