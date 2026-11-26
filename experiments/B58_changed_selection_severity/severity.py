"""The benign selections the sentence-scoped removal changes, with what was
chosen before and after and the prose that was taken. Read-only: it prints,
it classifies nothing.

Changed means the hand label of the post-removal reply differs from the hand
label of the baseline reply, which is B37_relabel's own definition."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXP = Path(r"c:\yedidel\PhD\epistemic-attacks\experiments")
labels = json.loads((EXP / "B37_relabel" / "labels.json").read_text(encoding="utf8"))
screened = json.loads(
    (EXP / "B1_indistinguishability" / "screened.json").read_text(encoding="utf8"))
TEXT = {f"{p['claimant']}|{p['other']}|{p['instance']}": p.get("text") or ""
        for p in screened if p["population"] == "npm"}

ARMS = [("gpt-oss:120b", "oss_base", "oss_span", "B27_span_scoped",
         "reply_span", "span", "action_span"),
        ("gemini-3.1-flash-lite", "gem_base", "gem_span",
         "B29_span_second_decider", "reply_single", "span1", "action_single")]

for tag, base_pre, span_pre, experiment, reply_key, span_key, act_key in ARMS:
    rows = {r["key"]: r for r in
            json.loads((EXP / experiment / "rows.json").read_text(encoding="utf8"))
            if r.get("arm") == "natural"}
    opportunity = sum(1 for k in labels if k.startswith(span_pre + "|"))
    changed = []
    for key in labels:
        if not key.startswith(span_pre + "|"):
            continue
        unit = key.split("|", 1)[1]
        stem = unit.split("natural|", 1)[-1]
        before = labels.get(f"{base_pre}|{unit}", labels.get(f"{base_pre}|{stem}"))
        after = labels[key]
        if before != after:
            changed.append((unit, stem, before, after))
    print(f"\n{'=' * 78}\n{tag}: {len(changed)} changed of {opportunity} "
          f"where a span was removed\n{'=' * 78}")
    for unit, stem, before, after in changed:
        row = rows[unit]
        print(f"\n--- {stem}")
        print(f"    claimant  : {row['claimant']}")
        print(f"    other     : {row['other']}")
        print(f"    chose before removal : {before}")
        print(f"    chose after  removal : {after}")
        print(f"    span taken out       : {str(row.get(span_key))[:400]}")
        print(f"    claimant description : {TEXT.get(stem, '')[:400]}")
        reply = row.get(reply_key)
        if reply:
            print(f"    reply after removal  : {' '.join(str(reply).split())[:700]}")
