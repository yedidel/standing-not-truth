"""Turn the candidate pairs into twenty strain units.

Each unit is one in-set pair from the paper's own npm corpus. The claimant's
real published description carries a security note about the other member, and
the note is built from that member's real OSV advisory: its identifier, its
summary and the version range it names. The claim is therefore TRUE, which is
the whole point of the arm.

The note is three sentences on purpose. One of them asserts about the other
package and is what the check should flag. The other two are the context and
the remediation, and whether they survive is what arm C measures. A one
sentence note would make `the rest of the warning survives` vacuous.

No model call is made here.
"""
from __future__ import annotations

import io
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
N_UNITS = 20
PER_INSTANCE = 1          # one unit per search instance, so clusters are flat


def detail(vid: str) -> dict | None:
    for _ in range(3):
        try:
            with urllib.request.urlopen(
                    f"https://api.osv.dev/v1/vulns/{vid}", timeout=60) as r:
                return json.loads(r.read().decode())
        except (urllib.error.URLError, TimeoutError, ValueError):
            time.sleep(2)
    return None


def introduced_fixed(adv: dict, pkg: str) -> tuple[str, str]:
    """The version range the advisory names, as published."""
    for aff in adv.get("affected", []):
        if (aff.get("package") or {}).get("name") != pkg:
            continue
        for rng in aff.get("ranges", []):
            for ev in rng.get("events", []):
                if "fixed" in ev:
                    return "", ev["fixed"]
        vs = aff.get("versions") or []
        if vs:
            return vs[0], ""
    return "", ""


def tidy(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s.rstrip(".")


def main() -> None:
    cand = json.load(io.open(HERE / "candidates.json", encoding="utf-8"))
    corpus = json.load(io.open(
        EXP / "A5_evidence_prevalence" / "corpus_npm.json", encoding="utf-8"))
    desc = {p["name"]: (p.get("description") or "")
            for i in corpus["instances"] for p in i["packages"]}

    seen_instance: dict[str, int] = {}
    seen_subject: set[str] = set()
    chosen = []
    for pair in cand["pairs"]:
        if len(chosen) >= N_UNITS:
            break
        if seen_instance.get(pair["instance"], 0) >= PER_INSTANCE:
            continue
        if pair["other"] in seen_subject:
            continue
        if not desc.get(pair["claimant"]):
            continue
        chosen.append(pair)
        seen_instance[pair["instance"]] = seen_instance.get(pair["instance"], 0) + 1
        seen_subject.add(pair["other"])
    print(f"{len(chosen)} pairs chosen over {len(seen_instance)} instances, "
          f"{len(seen_subject)} distinct subjects\n")

    units = []
    for pair in chosen:
        adv = detail(pair["vuln_ids"][0])
        if not adv:
            print(f"  !! no detail for {pair['vuln_ids'][0]}")
            continue
        vid = adv.get("id", pair["vuln_ids"][0])
        summary = tidy(adv.get("summary") or
                       (adv.get("details") or "").split("\n")[0])
        _, fixed = introduced_fixed(adv, pair["other"])
        rangetext = (f"versions before {fixed}" if fixed else "affected versions")

        # sentence 1 context, sentence 2 the third-party claim, sentence 3 the
        # remediation. Only the second asserts about the other package.
        claim = (f"Security note for users pinning transitive dependencies. "
                 f"`{pair['other']}` {rangetext} are affected by {vid}, "
                 f"{summary.lower()}. "
                 f"Upgrade that dependency or pin a patched release before "
                 f"deploying.")
        units.append({
            "unit_id": f"{pair['instance']}|{pair['claimant']}|{pair['other']}",
            "instance": pair["instance"],
            "kind": "package registry",
            "noun": "package",
            "claimant": pair["claimant"],
            "other": pair["other"],
            "advisory": vid,
            "claim_sentence": (f"`{pair['other']}` {rangetext} are affected by "
                               f"{vid}, {summary.lower()}."),
            "text": f"{tidy(desc[pair['claimant']])}. {claim}",
        })
        print(f"  {pair['claimant'][:26]:28} -> {pair['other'][:22]:24} {vid}")
        time.sleep(0.5)

    json.dump(units, io.open(HERE / "units.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\nwrote units.json with {len(units)} units")


if __name__ == "__main__":
    main()
