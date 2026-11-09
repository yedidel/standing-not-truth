"""Collect real security advisories for packages the paper's own npm corpus
already holds, and pair each with an in-set competitor to speak about it.

No model call is made here. OSV is public and read only.

The unit that comes out has the shape of an attack unit and the opposite
content: the speaker is a competitor, the subject is a competitor, and the
claim is TRUE, because it is a real published advisory about a real version
range.
"""
from __future__ import annotations

import io
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
OSV = "https://api.osv.dev/v1/querybatch"


def corpus_instances() -> list[dict]:
    p = EXP / "A5_evidence_prevalence" / "corpus_npm.json"
    return json.load(io.open(p, encoding="utf-8"))["instances"]


def osv_batch(names: list[str]) -> dict[str, list[dict]]:
    """One querybatch call per chunk. Returns name -> list of vuln stubs."""
    out: dict[str, list[dict]] = {}
    for i in range(0, len(names), 50):
        chunk = names[i:i + 50]
        body = json.dumps({
            "queries": [{"package": {"name": n, "ecosystem": "npm"}} for n in chunk]
        }).encode()
        req = urllib.request.Request(
            OSV, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                res = json.loads(r.read().decode())
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            print(f"  !! chunk {i // 50} failed: {exc}")
            continue
        for name, entry in zip(chunk, res.get("results", [])):
            vulns = entry.get("vulns") or []
            if vulns:
                out[name] = vulns
        print(f"  chunk {i // 50}: {sum(1 for n in chunk if n in out)}"
              f" of {len(chunk)} carry an advisory")
        time.sleep(1)
    return out


def vuln_detail(vid: str) -> dict | None:
    try:
        with urllib.request.urlopen(
                f"https://api.osv.dev/v1/vulns/{vid}", timeout=60) as r:
            return json.loads(r.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def main() -> None:
    inst = corpus_instances()
    names = sorted({p["name"] for i in inst for p in i["packages"]})
    print(f"{len(inst)} instances, {len(names)} distinct packages\n")

    print("querying OSV")
    hits = osv_batch(names)
    print(f"\n{len(hits)} packages carry at least one advisory")

    # an in-set pair is two packages from the SAME instance, which is the only
    # case where a claim about a competitor can reach the decision
    pairs = []
    for i in inst:
        pkgs = i["packages"]
        for a in pkgs:
            for b in pkgs:
                if a["name"] == b["name"] or b["name"] not in hits:
                    continue
                pairs.append({
                    "instance": i["instance_id"],
                    "claimant": a["name"],
                    "other": b["name"],
                    "vuln_ids": [v["id"] for v in hits[b["name"]]][:4],
                })
    print(f"{len(pairs)} in-set pairs whose subject carries an advisory")

    json.dump({"pairs": pairs, "hits": {k: [v["id"] for v in vs]
                                        for k, vs in hits.items()}},
              io.open(HERE / "candidates.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\nwrote candidates.json")


if __name__ == "__main__":
    main()
