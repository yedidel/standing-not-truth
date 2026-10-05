"""Emit B-35 panel replies for reading, and hold the outcomes I assign.

    python read_panel.py show <arm> [model substring] [count]
    python read_panel.py save <arm> <json of {unit key: outcome}>
    python read_panel.py stat

`show` pages through whatever is still unread. For the `sentence` arm it only
offers units whose undefended reply I have already read and found to land, so
the second pass is confined to the units that decide the pre-registration.

No classification happens here. The script records what I decide.
"""
import json
import sys
from pathlib import Path

STORE = Path(__file__).resolve().parent
ROWS = STORE.parent / "B35_model_panel" / "rows.json"
LABELS = STORE / "panel_labels.json"


def load():
    return json.loads(LABELS.read_text(encoding="utf-8")) if LABELS.exists() else {}


def rows():
    return json.loads(ROWS.read_text(encoding="utf-8"))


def main():
    cmd = sys.argv[1]
    lab = load()

    if cmd == "stat":
        rs = rows()
        for arm in ("undefended", "sentence", "blanket"):
            have = sum(1 for r in rs if f"{arm}|{r['key']}" in lab)
            tot = sum(1 for r in rs if r.get(f"{arm}_reply"))
            print(f"  {arm:11s} {have:5d} / {tot:5d} read")
        lands = [r for r in rows()
                 if lab.get(f"undefended|{r['key']}") == r["promoted"]]
        print(f"\n  attacks landing undefended, so far: {len(lands)}")
        need = [r for r in lands
                if r.get("sentence_reply") and f"sentence|{r['key']}" not in lab]
        print(f"  sentence-arm replies still to read for those: {len(need)}")
        return

    if cmd == "save":
        arm, blob = sys.argv[2], sys.argv[3]
        add = json.loads(blob)
        for k, v in add.items():
            lab[f"{arm}|{k}"] = v
        LABELS.write_text(json.dumps(lab, ensure_ascii=False, indent=1),
                          encoding="utf-8")
        print(f"stored {len(add)}; total {len(lab)}")
        return

    arm = sys.argv[2]
    pick = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].isdigit() else None
    count = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 20

    rs = [r for r in rows() if r.get(f"{arm}_reply")]
    if pick:
        rs = [r for r in rs if pick in r["model"]]
    if arm == "sentence":
        rs = [r for r in rs
              if lab.get(f"undefended|{r['key']}") == r["promoted"]]
    todo = [r for r in rs if f"{arm}|{r['key']}" not in lab]

    print(f"# {arm}: {len(todo)} unread of {len(rs)}\n")
    for r in todo[:count]:
        a, b = r["names"]
        print(f"### {r['key']}")
        print(f"    menu: {a}  |  {b}   [attacker pushes: {r['promoted']}, "
              f"correct: {r['correct']}]")
        print(f"    {' '.join(str(r[f'{arm}_reply']).split())}")
        print()


if __name__ == "__main__":
    main()
