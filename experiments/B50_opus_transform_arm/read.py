"""B-50 reading harness. It extracts, it does not decide.

Every verdict in this experiment is the author's, taken from reading the
reply. This script only lays each reply out beside the two candidate names so
that the reading is possible at all, and records three mechanical facts that
are not judgments:

    has_text        the reply is non-empty after stripping
    finish          the provider's own finish reason, which is NOT a verdict:
                    seven replies in this run carry `refusal` and still hold a
                    full recommendation, and every empty one carries `refusal`
                    too, so the field separates nothing on its own
    names_present   which of the two candidate names appear anywhere in it

`python read.py SHEET` writes `reading_sheet.txt`, one block per row, for
hand reading. `python read.py TALLY <labels.json>` then counts the labels the
author wrote, and refuses if any row is unlabelled.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
EXP = HERE.parent
RUN_DIR = HERE / "run"
B41_RAW = EXP / "B41_implicit_subject" / "run" / "raw"
MODEL = "anthropic/claude-opus-5"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


b41 = _load("b41_run", EXP / "B41_implicit_subject" / "run.py")
b31 = b41.b31
FORMS = b41.FORMS


def safe(uid: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in uid)[:180]


def read_raw(directory: Path, uid: str):
    p = directory / f"{safe(uid)}.json"
    if not p.exists():
        return None, None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        ch = d["choices"][0]
        txt = (ch["message"]["content"] or "").strip()
        fin = ch.get("native_finish_reason") or ch.get("finish_reason") or "?"
        return txt, fin
    except (KeyError, IndexError, ValueError):
        return "", "parse-error"


def rows() -> list[dict]:
    units = b31.build_units()
    out = []
    for name in sorted(units):
        u = units[name]
        ctl, ctl_fin = read_raw(RUN_DIR / "raw", f"control|{name}")
        for form in FORMS:
            first, f1 = read_raw(B41_RAW, f"decide|{MODEL}|{form}|{name}")
            retry, f2 = read_raw(RUN_DIR / "raw", f"retry|{form}|{name}")
            fresh, f3 = read_raw(RUN_DIR / "raw", f"decide|{form}|{name}")
            if first:
                txt, fin, src = first, f1, "B41"
            elif fresh:
                txt, fin, src = fresh, f3, "B50"
            elif retry:
                txt, fin, src = retry, f2, "B50-retry"
            else:
                txt = ""
                fin = f2 or f3 or f1 or "no call"
                src = "B50-retry" if retry == "" else "B50"
            out.append({
                "row": f"{form}|{name}",
                "unit": name, "transform": form,
                "attacker": u["promoted"], "honest": u["correct"],
                "variant": b41.variant(u, form),
                "source": src, "finish": fin,
                "has_text": bool(txt), "reply": txt,
                "names_present": [n for n in (u["promoted"], u["correct"])
                                  if n in txt],
                "control_has_text": bool(ctl), "control_finish": ctl_fin,
                "control_reply": ctl or "",
                "control_names": [n for n in (u["promoted"], u["correct"])
                                  if ctl and n in ctl],
            })
    return out


def sheet() -> None:
    rs = rows()
    with io.open(HERE / "reading_sheet.txt", "w", encoding="utf-8") as f:
        seen_control = set()
        for r in rs:
            if r["unit"] not in seen_control:
                seen_control.add(r["unit"])
                f.write("=" * 78 + "\n")
                f.write("CONTROL  unit %s   attacker=%s  honest=%s\n"
                        % (r["unit"], r["attacker"], r["honest"]))
                f.write("  finish=%s  text=%s  names=%s\n"
                        % (r["control_finish"], r["control_has_text"],
                           r["control_names"]))
                if r["control_reply"]:
                    f.write("  " + r["control_reply"].replace("\n", "\n  ")
                            + "\n")
                f.write("\n")
            f.write("-" * 78 + "\n")
            f.write("ROW %s   src=%s finish=%s text=%s  names=%s\n"
                    % (r["row"], r["source"], r["finish"], r["has_text"],
                       r["names_present"]))
            f.write("  attacker=%s   honest=%s\n" % (r["attacker"], r["honest"]))
            f.write("  variant: %s\n" % r["variant"])
            if r["reply"]:
                f.write("  " + r["reply"].replace("\n", "\n  ") + "\n")
            f.write("\n")
    io.open(HERE / "rows.json", "w", encoding="utf-8").write(
        json.dumps(rs, indent=1, ensure_ascii=False))
    n = len(rs)
    txt = sum(1 for r in rs if r["has_text"])
    cu = len({r["unit"] for r in rs if r["control_has_text"]})
    print("decide rows %d, with text %d, empty %d" % (n, txt, n - txt))
    print("control units with text %d of %d"
          % (cu, len({r["unit"] for r in rs})))
    print("wrote reading_sheet.txt and rows.json")


if __name__ == "__main__":
    arg = (sys.argv[1] if len(sys.argv) > 1 else "").upper()
    if arg == "SHEET":
        sheet()
    else:
        raise SystemExit(__doc__)
