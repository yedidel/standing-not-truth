"""B-56, step 1: the blind sample for a second pass over E1 and E4 to E7.

The limitations register concedes that *"E1 and E4 through E7 carry no second
pass at all"*, and two reviewers asked for one. `B-14` measured the annotator
on the arms behind E2 and E3, with 201 items, a fixed seed, no first-pass
label shown and the items shuffled. This applies the same protocol to the
arms the register names.

Two tasks, as in `B-14`:

  subject   whether an entry ASSERTS something about the other package or
            only MENTIONS it. Feeds E1's benign flag rates.
  action    which offering a reply chose, or REFUSAL / OFF_MENU / NONE.
            Feeds E1's benign disturbance, E4's two removals, E5's matched
            comparison, E6's disclosure arms and E7's held-out scenarios.

The sheet carries the reply and the two candidate names and nothing else. The
first-pass labels are written to a separate file that the sheet does not
reference and that the second pass does not open. No model call.
"""
from __future__ import annotations

import io
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
SEED = 20261124
N_SUBJECT = 50
N_ACTION = 100


def load(rel: str):
    return json.load(io.open(EXP / rel, encoding="utf-8"))


def main() -> None:
    rng = random.Random(SEED)
    items = []

    # ---- subject task, E1's screen on natural prose -------------------
    scr = [r for r in load("B1_indistinguishability/screened.json")
           if r.get("reply") and r.get("screen") in ("ASSERTS", "MENTIONS")]
    strata = {}
    for r in scr:
        strata.setdefault((r["population"], r["screen"]), []).append(r)
    per = max(1, N_SUBJECT // max(1, len(strata)))
    for (pop, verdict), rows in sorted(strata.items()):
        for r in rng.sample(rows, min(per, len(rows))):
            items.append({
                "task": "subject", "stratum": "E1|%s|%s" % (pop, verdict),
                "claimant": r["claimant"], "other": r["other"],
                "names": [r["claimant"], r["other"]],
                "reply": r["reply"], "text": r["text"],
                "first": r["screen"],
            })

    # ---- action task, one source per experiment ----------------------
    SOURCES = [
        ("E1|commerce", "B20_commerce_domain/rows.json", "reply", "action",
         ("promoted", "correct")),
        ("E1|npm|base", "B26_wide_natural/rows.json", "reply_baseline",
         "action_baseline", ("claimant", "other")),
        ("E4|npm|ablated", "B26_wide_natural/rows.json", "reply_ablated",
         "action_ablated", ("claimant", "other")),
        ("E4|span", "B27_span_scoped/rows.json", "reply_span", "action_span",
         ("promoted", "correct")),
        ("E5|attriguard", "B25_attriguard_matched/rows.json", "shadow_reply",
         "shadow_action", ("promoted", "correct")),
        ("E6|quoted", "B30_attribution/rows.json", "reply_quoted",
         "action_quoted", ("promoted", "correct")),
        ("E6|warned", "B30_attribution/rows.json", "reply_quoted_warn",
         "action_quoted_warn", ("promoted", "correct")),
        ("E7|avip", "B39_avip_selection/rows.json", "attack_reply", None,
         ("promoted_name", "honest_name")),
    ]
    per = max(1, N_ACTION // len(SOURCES))
    for stratum, rel, reply_key, action_key, name_keys in SOURCES:
        rows = [r for r in load(rel) if r.get(reply_key)]
        if action_key:
            rows = [r for r in rows if r.get(action_key)]
        # A row whose two candidate names are not stored cannot be labelled
        # "which of these two did it choose", so it is not sampled. In the
        # natural arms of B-27 and B-30 those fields hold the attack arm's
        # promoted and correct names and are null on natural rows.
        rows = [r for r in rows if all(r.get(k) for k in name_keys)]
        if not rows:
            print("  no rows with both candidate names in %s" % rel)
            continue
        if not rows:
            print("  no usable rows in %s (%s)" % (rel, reply_key))
            continue
        for r in rng.sample(rows, min(per, len(rows))):
            a, b = (r.get(k) for k in name_keys)
            items.append({
                "task": "action", "stratum": stratum,
                "names": [a, b],
                "reply": r[reply_key],
                "first": r.get(action_key) if action_key else None,
            })

    rng.shuffle(items)
    for i, it in enumerate(items, 1):
        it["id"] = i

    first = {it["id"]: it.pop("first") for it in items}
    json.dump(first, io.open(HERE / "first_pass.json", "w",
                             encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(items, io.open(HERE / "sample.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)

    with io.open(HERE / "sheet.txt", "w", encoding="utf-8",
                 newline="\n") as fh:
        for it in items:
            fh.write("=" * 76 + "\n")
            fh.write("[%03d] task=%s\n" % (it["id"], it["task"]))
            if it["task"] == "subject":
                fh.write("claimant=%s   other=%s\n"
                         % (it["claimant"], it["other"]))
                fh.write("ENTRY TEXT:\n%s\n" % it["text"].strip())
                fh.write("-" * 76 + "\nSCREEN REPLY:\n")
            else:
                fh.write("candidates: %s | %s\n"
                         % (it["names"][0], it["names"][1]))
                fh.write("-" * 76 + "\nDECIDE REPLY:\n")
            fh.write((it["reply"] or "").strip() + "\n\n")

    from collections import Counter
    print("sample: %d items, seed %d" % (len(items), SEED))
    print("  by task   ", dict(Counter(i["task"] for i in items)))
    for s, n in sorted(Counter(i["stratum"] for i in items).items()):
        print("    %-18s %d" % (s, n))
    print("first-pass labels written to first_pass.json, not to the sheet")


if __name__ == "__main__":
    main()
