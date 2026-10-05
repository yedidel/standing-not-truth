"""Verify every ledger digest against the response it covers.

**Run this before any release.** A digest nobody has ever checked is a claim,
not evidence, and this project's ledgers turned out to carry two different
digest schemes under one field name, neither of them documented. A reader who
assumed the obvious method got **2,484 mismatches out of 2,484** and would
reasonably have concluded the artifact was corrupt.

Two schemes, and the difference is not cosmetic:

  live      `runner.py` computes the digest over
            `json.dumps(response, ensure_ascii=False, indent=2)` and then calls
            `path.write_text(...)`. **On Windows that translates every newline
            to CRLF after the digest was taken**, so hashing the file's bytes
            never matches. Normalise CRLF back to LF before hashing.

  backfill  `backfill_ledger.py` computes the digest over
            `json.dumps(row, ensure_ascii=False, sort_keys=True)` for the
            individual row, not over the file at all. `response_path` points at
            the file the row came from, and hashing that file is meaningless
            for these records.

Records written by the backfill carry `backfilled: true`, which is the only way
to tell the two apart. **That flag is load-bearing and must not be stripped
from the released ledgers.**

Two further classes are expected and are not corruption. The ledger is
append-only; the response store is keyed by unit id and is not.

  superseded  a unit was called more than once, and the second response
              overwrote the first file. The earlier record's digest can never
              match again. It is accounted for when a later record on the same
              file does match, and that pairing is checked here rather than
              asserted. An earlier record with no such partner is a real
              defect and is reported.

  empty       fifteen `claude-opus-5` units returned no content. The harness
              recorded `status: ok` with zero tokens and never wrote the file,
              so resume could not reach them; `retry_empties.py` asked them
              again under a `|retry` unit id and both records remain. A
              record whose file is absent is accounted for when the retry is
              present in the same ledger.

The exit status follows the unexplained count alone.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent

CR_LF = chr(13) + chr(10)
LF = chr(10)
BACKSLASH = chr(92)


def live_digest(path: Path) -> str:
    """Hash the stored response the way `runner.py` hashed it before writing."""
    text = path.read_bytes().decode("utf-8", "replace").replace(CR_LF, LF)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def backfill_digest(obj) -> str:
    """Hash one row the way `backfill_ledger.py` hashed it."""
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def rows_of(payload, kind_hint: str):
    """The row list a backfilled digest was taken over."""
    if isinstance(payload, dict) and "instances" in payload:
        return [m for inst in payload.get("instances", [])
                for m in inst.get("models", [])]
    return payload if isinstance(payload, list) else []


def main() -> None:
    records = []          # every digested record, in the order it was written
    undigested = 0

    for ledger in sorted(HERE.rglob("*.jsonl")):
        base = ledger.parent
        for line in ledger.read_text(encoding="utf-8",
                                     errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            digest = record.get("response_sha256")
            rel = record.get("response_path")
            if not digest or digest == "None" or not rel or rel == "None":
                undigested += 1
                continue
            records.append((ledger, base / rel.replace(BACKSLASH, "/"),
                            digest, record))

    # what each stored file hashes to now, and which unit ids each ledger holds
    actual = {}
    for _, path, _, _ in records:
        if path not in actual:
            actual[path] = live_digest(path) if path.is_file() else None
    unit_ids = {}
    for ledger, _, _, record in records:
        unit_ids.setdefault(ledger, set()).add(str(record.get("unit_id")))

    verified = superseded = emptied = 0
    unexplained = []

    for order, (ledger, path, digest, record) in enumerate(records):
        if record.get("backfilled"):
            # the digest covers one row inside this file, so find it
            try:
                payload = json.loads(path.read_text(encoding="utf-8",
                                                    errors="replace"))
            except (OSError, json.JSONDecodeError):
                unexplained.append((record, "backfill", path, "unreadable"))
                continue
            if any(backfill_digest(row) == digest
                   for row in rows_of(payload, record.get("exp", ""))):
                verified += 1
            else:
                unexplained.append((record, "backfill", path, "no row matches"))
            continue

        if actual[path] is None:
            # never written; accounted for only if the unit was asked again
            if f"{record.get('unit_id')}|retry" in unit_ids[ledger]:
                emptied += 1
            else:
                unexplained.append((record, "live", path, "file absent"))
            continue

        if actual[path] == digest:
            verified += 1
            continue

        # a later record on the same file matching it means this one was
        # overwritten by a retry, which the append-only ledger preserves
        later = any(p == path and d == actual[path] and o > order
                    for o, (_, p, d, _) in enumerate(records))
        if later:
            superseded += 1
        else:
            unexplained.append((record, "live", path, "no later record matches"))

    total = len(records) + undigested
    print(f"ledger records examined : {total}")
    print(f"  digest verified       : {verified}")
    print(f"  superseded by a retry : {superseded}")
    print(f"  empty, asked again    : {emptied}")
    print(f"  no digest stored      : {undigested}")
    print(f"  UNEXPLAINED           : {len(unexplained)}")

    if unexplained:
        print()
        for record, scheme, path, why in unexplained[:12]:
            print(f"  {str(record.get('exp')):18s} "
                  f"{str(record.get('unit_id'))[:40]:42s} {scheme:9s} "
                  f"{why:24s} {path.name}")
        raise SystemExit(1)

    print()
    print("every digest accounted for")


if __name__ == "__main__":
    main()
