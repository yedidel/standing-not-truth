"""B-54, step 1: a richer OSV snapshot than B-49 needed.

B-49 closed the subject hole in `AUTHORITY(advisory)`: the published B2 admits
any publisher citing an identifier-shaped string, and B2' requires that the
advisory resolve and name the subject of the claim. Both of those are lookups
on fields the record carries.

A reviewer of the submitted draft then asked the next question: how the
exemption avoids "conferring platform standing to paraphrased or ambiguous
claims". That is a different hole. A publisher can cite an advisory that
resolves, names the subject, and is quoted accurately in every respect B2'
tests, and still say something the record contradicts.

To measure it the snapshot needs the fields an inflated claim would
contradict, which B-49's did not keep:

  * `affected[].ranges[].events[].fixed`  -- the version the record bounds the
    vulnerability at, which a scope inflation denies
  * `severity` and `database_specific.severity` and the CWE ids -- the class
    the record assigns, which a class inflation overstates

Read-only HTTP against the public OSV API. No model call, no credentials.
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
API = "https://api.osv.dev/v1/vulns/"


def fetch(vid: str) -> dict:
    req = urllib.request.Request(
        API + vid, headers={"Accept": "application/json",
                            "User-Agent": "standing-paper-artifact/1.0"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.load(fh)


def main() -> None:
    units = json.load(io.open(B40 / "units.json", encoding="utf-8"))
    out = {}
    for u in units:
        vid = u["advisory"]
        if vid in out:
            continue
        try:
            rec = fetch(vid)
        except urllib.error.HTTPError as exc:
            out[vid] = {"resolves": False, "http": exc.code}
            print("%-24s HTTP %s" % (vid, exc.code))
            continue
        affected = []
        fixed = []
        for a in rec.get("affected", []):
            pkg = a.get("package", {})
            nm = pkg.get("name")
            eco = pkg.get("ecosystem")
            if nm:
                affected.append("%s/%s" % (eco, nm))
            for rng in a.get("ranges", []):
                for ev in rng.get("events", []):
                    if ev.get("fixed"):
                        fixed.append(ev["fixed"])
        dbs = rec.get("database_specific", {}) or {}
        out[vid] = {
            "resolves": True,
            "affected": affected,
            "fixed": sorted(set(fixed)),
            "summary": rec.get("summary", ""),
            "severity_label": dbs.get("severity", ""),
            "cwe_ids": dbs.get("cwe_ids", []),
            "cvss": [s.get("score", "") for s in rec.get("severity", []) or []],
        }
        print("%-24s fixed=%-12s %-9s %s"
              % (vid, ",".join(out[vid]["fixed"]) or "-",
                 out[vid]["severity_label"], ",".join(out[vid]["cwe_ids"])))
        time.sleep(0.2)

    json.dump(out, io.open(HERE / "osv_snapshot.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False, sort_keys=True)
    n_res = sum(1 for v in out.values() if v.get("resolves"))
    n_fix = sum(1 for v in out.values() if v.get("fixed"))
    n_sev = sum(1 for v in out.values() if v.get("severity_label"))
    print()
    print("%d identifiers, %d resolve, %d carry a fixed version, %d a severity"
          % (len(out), n_res, n_fix, n_sev))


if __name__ == "__main__":
    main()
