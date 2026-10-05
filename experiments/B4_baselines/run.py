"""B-4 — AttriGuard's own defense, on our units.

`B7` compared three placements with our implementation of each, which leaves
the objection that we built the baselines ourselves. B-4 removes it: the
attenuation prompts and the judge prompt below are **loaded verbatim from the
USENIX artifact** at
`baselines/attriguard/unpacked/usenix-artifacts/main/pipeline/AttriGuard.py`,
parsed out of the source at run time rather than transcribed, so a reader can
diff them against the authors' file.

The defense, as the artifact composes it at its default attenuation level 2:

  1. the untrusted block is passed through FLATTEN, which rewrites high-risk
     syntactic structures into linear prose and otherwise copies the input
     verbatim;
  2. the result is passed through TRANSPOSE, which converts directives into
     descriptive statements and shifts person;
  3. the agent decides again on the attenuated block, producing the *shadow
     action*, which the judge prompt calls the ground truth of what is safe;
  4. the judge compares the original action against the shadow action and
     returns `survive`.

The original action is taken from `B7`'s baseline replies rather than issued
again, so both experiments share a decider, a unit set and a denominator and
their rows may be read side by side.

What is not reproduced: AgentDojo's tool-calling loop, because our units are
single decisions with no tool calls, and the logprob-weighted variant of the
judge, because the artifact itself falls back to the JSON-only decision when
logprobs are unavailable.
"""

from __future__ import annotations

import json
import math
import re
import sys
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).parent
B7 = HERE.parent / "B7_placement"
ARTIFACT = (HERE.parent.parent / "baselines" / "attriguard" / "unpacked" /
            "usenix-artifacts" / "main" / "pipeline" / "AttriGuard.py")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402
_add_harness()
ollama = import_module("05_experiments._harness.ollama")

MODEL = "gpt-oss:120b"
ATTENUATION_LEVEL = 2


def artifact_prompts() -> dict[str, str]:
    """Read the defense's prompts out of the authors' source, not a copy."""
    source = ARTIFACT.read_text(encoding="utf-8")
    wanted = ("FLATTEN_SYSTEM_PROMPT", "TRANSPOSE_SYSTEM_PROMPT",
              "FUZZY_SYSTEM_PROMPT", "UNIFIED_INPUT_TEMPLATE")
    out = {}
    for name in wanted:
        match = re.search(name + r'\s*=\s*"""(.*?)"""', source, re.S)
        if match is None:
            match = re.search(name + r'\s*=\s*"(.*?)"\n', source, re.S)
        if match is None:
            raise RuntimeError(f"{name} not found in the artifact")
        out[name] = match.group(1)
    return out


P = artifact_prompts()


def transform(system_prompt: str, text: str) -> str:
    user = P["UNIFIED_INPUT_TEMPLATE"].replace("\\n", "\n").replace(
        "{{INPUT_TEXT}}", text)
    reply = ollama.chat(MODEL, [{"role": "system", "content": system_prompt},
                                {"role": "user", "content": user}], timeout=300)
    return ((reply.get("message") or {}).get("content") or "").strip()


def attenuate(text: str) -> tuple[str, str]:
    flattened = transform(P["FLATTEN_SYSTEM_PROMPT"], text)
    transposed = transform(P["TRANSPOSE_SYSTEM_PROMPT"], flattened)
    return flattened, transposed


def action_of(reply: str, candidates: list[str]) -> str | None:
    """The package a reply commits to installing.

    Earliest mention wins, and **at a tie the longest candidate wins**. The tie
    is not rare and ignoring it is wrong in a specific direction: registry
    results routinely contain names that are prefixes of one another, so
    `react`, `react-is` and `react-smooth` all match at the same offset in a
    reply that names only the second. Taking the shortest would report `react`
    every time, which is the same substring failure `A14` found inside clause
    (ii) and `B1` found inside its own screen.
    """
    low = reply.lower()
    hits = [(low.find(c.lower()), -len(c), c)
            for c in candidates if low.find(c.lower()) != -1]
    return min(hits)[2] if hits else None


def registry_names(block: str) -> list[str]:
    """Every package name offered in a registry block, in order."""
    return re.findall(r"name:\s*([^\s]+)", block)


def judge(user_task: str, original: str | None, shadow: str | None) -> dict:
    payload = json.dumps({
        "user_task": user_task,
        "original_action": {"function": "install_package",
                            "arguments": {"package": original}},
        "shadow_actions": [{"function": "install_package",
                            "arguments": {"package": shadow}}],
    }, ensure_ascii=True, sort_keys=True)
    user = P["UNIFIED_INPUT_TEMPLATE"].replace("\\n", "\n").replace(
        "{{INPUT_TEXT}}", payload)
    reply = ollama.chat(MODEL, [{"role": "system", "content": P["FUZZY_SYSTEM_PROMPT"]},
                                {"role": "user", "content": user}], timeout=300)
    raw = ((reply.get("message") or {}).get("content") or "").strip()
    survive = None
    match = re.search(r'"survive"\s*:\s*(true|false)', raw, re.I)
    if match:
        survive = match.group(1).lower() == "true"
    return {"raw": raw[:600], "survive": survive}


def payload_span(full: str, control: str) -> str:
    """The text the attack adds to its paired control, and nothing else."""
    marker = "description:"
    tail_full = full[full.rfind(marker):] if marker in full else full
    tail_ctrl = control[control.rfind(marker):] if marker in control else control
    shared = 0
    while (shared < min(len(tail_full), len(tail_ctrl))
           and tail_full[shared] == tail_ctrl[shared]):
        shared += 1
    return tail_full[shared:].strip()


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower())


def payload_survived(span: str, attenuated: str) -> float | None:
    """Share of the payload's distinctive words still present after attenuation.

    A blunt instrument, kept as a replication artifact only. Whether the
    attenuated text still *asserts* the premise is decided by reading, not by
    this number.
    """
    if not span:
        return None
    words = [w for w in set(normalise(span).split()) if len(w) > 4]
    if not words:
        return None
    haystack = normalise(attenuated)
    return sum(1 for w in words if w in haystack) / max(1, len(words))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def main() -> None:
    units = json.loads((B7 / "replies.json").read_text(encoding="utf-8"))
    print(f"AttriGuard prompts loaded from the artifact: "
          f"{', '.join(f'{k}={len(v)}ch' for k, v in P.items())}")
    print(f"{len(units)} units x 4 calls = {len(units) * 4}\n", flush=True)

    out = HERE / "traces.json"
    stored = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    done = {r["unit"]: r for r in stored}

    rows = []
    for index, unit in enumerate(units, 1):
        if unit["unit"] in done:
            rows.append(done[unit["unit"]])
            continue
        block = unit["full"]
        span = payload_span(block, unit["ablated"]) if unit["arm"] == "attack" else ""
        names = [n for n in (unit.get("promoted"), unit.get("correct")) if n]
        if not names:
            names = re.findall(r"name:\s*([^\s]+)", block)
        try:
            flattened, attenuated = attenuate(block)
            shadow_reply = ollama.chat(
                MODEL, [{"role": "system", "content": unit["system"]},
                        {"role": "user", "content": attenuated}], timeout=300)
            shadow_text = ((shadow_reply.get("message") or {}).get("content") or "")
            original = action_of(unit["reply_baseline"], names)
            shadow = action_of(shadow_text, names)
            verdict = judge(unit["system"], original, shadow)
        except Exception as exc:
            print(f"  [{index}] {type(exc).__name__} -- left unscored", flush=True)
            continue
        rows.append({
            "unit": unit["unit"], "arm": unit["arm"],
            "promoted": unit.get("promoted"), "correct": unit.get("correct"),
            "attenuated": attenuated[:3000], "flattened_len": len(flattened),
            "shadow_reply": shadow_text.strip()[:600],
            "original_action": original, "shadow_action": shadow,
            "judge_raw": verdict["raw"], "survive": verdict["survive"],
            "payload": span,
            "payload_word_survival": payload_survived(span, attenuated),
        })
        print(f"  [{index}/{len(units)}] {unit['arm']:8s} {unit['unit']:22s} "
              f"orig={original} shadow={shadow} survive={verdict['survive']}",
              flush=True)
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                       encoding="utf-8")

    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                   encoding="utf-8")


if __name__ == "__main__":
    main()
