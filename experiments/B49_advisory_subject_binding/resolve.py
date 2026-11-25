"""B-49, step 1: resolve every advisory B-40 used and record what it affects.

OSV is public and read only. No model call is made here, and nothing is paid
for. The resolved records are written to disk so that every later step, and
anyone reproducing this, scores offline against a fixed snapshot.

What this establishes is a fact about each identifier, not a judgment:
which package names the advisory itself lists under `affected`.
"""
from __future__ import annotations

import io
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
B40 = HERE.parent / "B40_advisory_strain"
OSV_ONE = "https://api.osv.dev/v1/vulns/"


def fetch(vuln_id: str) -> dict | None:
    req = urllib.request.Request(
        OSV_ONE + vuln_id,
        headers={"Accept": "application/json", "User-Agent": "osv-client/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        print("    !! %s -> HTTP %s" % (vuln_id, exc.code))
        return None
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print("    !! %s -> %s" % (vuln_id, exc))
        return None


def affected_names(rec: dict) -> list[str]:
    out = []
    for a in rec.get("affected", []):
        name = (a.get("package") or {}).get("name")
        eco = (a.get("package") or {}).get("ecosystem")
        if name:
            out.append("%s/%s" % (eco or "?", name))
    return sorted(set(out))


def main() -> None:
    units = json.load(io.open(B40 / "units.json", encoding="utf-8"))
    print("B-40 units: %d" % len(units))

    ids = sorted({u["advisory"] for u in units})
    print("distinct advisory identifiers: %d" % len(ids))

    store: dict[str, dict] = {}
    for k, vid in enumerate(ids, 1):
        print("  [%2d/%2d] %s" % (k, len(ids), vid))
        rec = fetch(vid)
        if rec is None:
            store[vid] = {"resolves": False}
            continue
        store[vid] = {
            "resolves": True,
            "summary": rec.get("summary", ""),
            "aliases": rec.get("aliases", []),
            "affected": affected_names(rec),
        }
        time.sleep(0.3)

    io.open(HERE / "osv_snapshot.json", "w", encoding="utf-8").write(
        json.dumps(store, indent=1, sort_keys=True))

    print("\nunit by unit: does the cited advisory name the SUBJECT?")
    print("%-34s %-24s %-22s %s" % ("unit", "subject u", "advisory", "u in affected?"))
    bound = 0
    for u in units:
        rec = store[u["advisory"]]
        names = [n.split("/", 1)[1] for n in rec.get("affected", [])]
        ok = u["other"] in names
        bound += ok
        print("%-34s %-24s %-22s %s" % (
            u["unit_id"][:34], u["other"][:24], u["advisory"], "YES" if ok else "NO"))
    print("\nsubject-bound: %d of %d" % (bound, len(units)))
    unresolved = [v for v, r in store.items() if not r["resolves"]]
    print("unresolved identifiers: %d %s" % (len(unresolved), unresolved or ""))


if __name__ == "__main__":
    main()
