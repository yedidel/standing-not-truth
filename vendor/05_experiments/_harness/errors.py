"""Provider-exhaustion errors.

A run must stop cleanly when a provider will not serve more calls, whether
that is an OpenRouter balance at zero or an Ollama weekly quota consumed.
Both cases share one requirement: halt at a unit boundary, never retry, and
leave the ledger in a state the next run can resume from.
"""

from __future__ import annotations


class ProviderExhausted(RuntimeError):
    """The provider will not serve more calls right now.

    Raised instead of a generic error so the runner can distinguish
    "stop and resume later" from "this unit failed, try the next one".
    """


class InsufficientBalance(ProviderExhausted):
    """Prepaid balance cannot cover further calls (OpenRouter)."""


class QuotaExhausted(ProviderExhausted):
    """A rate or period quota is spent (Ollama weekly limit)."""
