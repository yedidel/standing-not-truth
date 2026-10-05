#!/usr/bin/env bash
# Fetch the CaMeL artifact (Google Research, Apache 2.0).
#
# Not redistributed here: it is other authors' work and it is better obtained
# from its own repository, where it is maintained. B-18 imports its capability
# model and policy engine directly, so the checkout must be present.
#
# Apache 2.0 permits redistribution with attribution; fetching is chosen so the
# version in use is always the one the reader can inspect upstream.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/baselines/camel"
REPO="https://github.com/google-research/camel-prompt-injection"

if [ -d "$DEST/src/camel" ]; then
  echo "already present: $DEST"
else
  mkdir -p "$(dirname "$DEST")"
  git clone --depth 1 "$REPO" "$DEST"
fi

PROBE="$DEST/src/camel/capabilities/capabilities.py"
if [ ! -f "$PROBE" ]; then
  echo "ERROR: cloned, but the capability model is missing at:" >&2
  echo "    $PROBE" >&2
  exit 1
fi

echo "ready: $PROBE"
echo
echo "Note: upstream is not pinned here. B-18 uses only the capability model"
echo "and the policy interface, both stable since the 2025 release, and it"
echo "reimplements nothing. If those move, B-18 will fail loudly on import"
echo "rather than silently producing a different number."
