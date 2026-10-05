#!/usr/bin/env bash
# Fetch the AttriGuard artifact (USENIX Security 2026, MIT).
#
# Not redistributed here: it is other authors' work. B-4 parses AttriGuard's
# own prompts out of this source at run time rather than transcribing them, so
# the checkout must be present for B-4 to run.
#
# Unlike CaMeL, this one is pinned. The artifact of record is a Zenodo deposit,
# and a Zenodo DOI resolves to a fixed version, so the exact bytes B-4 was
# measured against can be named. They are checked before anything is unpacked.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/baselines/attriguard"
ZIP="$DEST/usenix-artifacts.zip"

# Zenodo 10.5281/zenodo.20308739, "AttriGuard: USENIX Security 2026 Artifacts
# Available", He and Yu, 2026-05-20, MIT.
RECORD="20308739"
URL="https://zenodo.org/records/$RECORD/files/usenix-artifacts.zip?download=1"

# The artifact of record, as measured for B-4.
WANT_SHA="81c6d58fdd09c8af217e59dc752dc032dab32c29e204dd7f9d936592174bbf1a"
WANT_BYTES="118255"

PROBE="$DEST/unpacked/usenix-artifacts/main/pipeline/AttriGuard.py"
if [ -f "$PROBE" ]; then
  echo "already present: $PROBE"
  exit 0
fi

mkdir -p "$DEST"
if [ ! -f "$ZIP" ]; then
  curl -fL --retry 3 -o "$ZIP" "$URL"
fi

got_bytes="$(wc -c < "$ZIP" | tr -d ' ')"
got_sha="$(sha256sum "$ZIP" | cut -d' ' -f1)"

if [ "$got_sha" != "$WANT_SHA" ] || [ "$got_bytes" != "$WANT_BYTES" ]; then
  echo "ERROR: the downloaded artifact is not the one B-4 was measured against." >&2
  echo "  expected  $WANT_SHA  ($WANT_BYTES bytes)" >&2
  echo "  got       $got_sha  ($got_bytes bytes)" >&2
  echo >&2
  echo "The upstream distribution has changed. The B-4 numbers in the paper" >&2
  echo "were measured against a different file, and rerunning against this one" >&2
  echo "may not reproduce them. Do not report the result as a reproduction" >&2
  echo "without saying which bytes it used." >&2
  exit 1
fi

mkdir -p "$DEST/unpacked"
unzip -q -o "$ZIP" -d "$DEST/unpacked"

if [ ! -f "$PROBE" ]; then
  echo "ERROR: unpacked, but AttriGuard's pipeline is missing at:" >&2
  echo "    $PROBE" >&2
  exit 1
fi

echo "ready: $PROBE"
