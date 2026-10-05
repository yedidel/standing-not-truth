"""Emit a batch of stored replies for reading, and hold the labels I assign.

No classification happens here. The script pages through the replies and
records what I decide; it never decides anything itself, and it never compares
my label with the one the old code produced until I have finished a batch.

    python read_batch.py show <arm> <from> <count>
    python read_batch.py save <arm> <json of {key: label}>
    python read_batch.py stat
"""
import json
import sys
from pathlib import Path

STORE = Path(__file__).resolve().parent
EXP = STORE.parent
STORE.mkdir(exist_ok=True)
LABELS = STORE / "labels.json"

ARMS = {
    # arm: (rows file, reply field, old code label field)
    "gem_base":  ("B29_span_second_decider", "reply_action_baseline", "action_baseline"),
    "gem_abl":   ("B29_span_second_decider", "reply_action_ablated",  "action_ablated"),
    "gem_span":  ("B29_span_second_decider", "reply_single",          "action_single"),
    "oss_base":  ("B26_wide_natural",        "reply_baseline",        "action_baseline"),
    "oss_abl":   ("B26_wide_natural",        "reply_ablated",         "action_ablated"),
    "oss_span":  ("B27_span_scoped",         "reply_span",            "action_span"),
    # attack arms: the headline claims. `promoted` is the attacker's package.
    "oss_atk_span":  ("B27_span_scoped",         "reply_span",   "action_span"),
    "gem_atk_span":  ("B29_span_second_decider", "reply_single", "action_single"),
    "gem_atk_multi": ("B29_span_second_decider", "reply_multi",  "action_multi"),
}

ATTACK = {"oss_atk_span", "gem_atk_span", "gem_atk_multi"}


def rows_for(arm):
    d, rk, ck = ARMS[arm]
    rows = json.loads((EXP / d / "rows.json").read_text(encoding="utf-8"))
    want = "attack" if arm in ATTACK else None
    rows = [r for r in rows
            if (r.get("arm") == "attack") == (want == "attack")]
    return rows, rk, ck


def load():
    return json.loads(LABELS.read_text(encoding="utf-8")) if LABELS.exists() else {}


def main():
    cmd = sys.argv[1]
    if cmd == "stat":
        lab = load()
        for arm in ARMS:
            rows, rk, _ = rows_for(arm)
            have = sum(1 for r in rows if f"{arm}|{r['key']}" in lab)
            tot = sum(1 for r in rows if r.get(rk) is not None)
            print(f"  {arm:9s} {have:4d} / {tot:4d} read")
        return

    if cmd == "save":
        arm, blob = sys.argv[2], sys.argv[3]
        lab = load()
        for k, v in json.loads(blob).items():
            lab[f"{arm}|{k}"] = v
        LABELS.write_text(json.dumps(lab, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"stored {len(json.loads(blob))}; total {len(lab)}")
        return

    arm, start, count = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    pair_with = sys.argv[5] if len(sys.argv) > 5 else None
    rows, rk, _ = rows_for(arm)
    rows = [r for r in rows if r.get(rk) is not None]
    if pair_with:
        lab0 = load()
        rows = [r for r in rows if f"{pair_with}|{r['key']}" in lab0]
    lab = load()
    todo = [r for r in rows if f"{arm}|{r['key']}" not in lab]
    print(f"# {arm}: {len(todo)} unread of {len(rows)}; showing {start}..{start+count}\n")
    for r in todo[start:start + count]:
        key = r["key"]
        pair = key.split("natural|", 1)[-1] if "natural|" in key else key
        names = [r.get("claimant"), r.get("other")]
        if not names[0]:
            parts = pair.split("|")
            names = parts[:2]
        txt = " ".join(str(r.get(rk)).split())
        print(f"### {key}")
        if r.get("promoted"):
            print(f"    candidates: {names[0]}  |  {names[1]}"
                  f"   [attacker pushes: {r['promoted']}]")
        else:
            print(f"    candidates: {names[0]}  |  {names[1]}")
        print(f"    {txt}")
        print()


if __name__ == "__main__":
    main()
