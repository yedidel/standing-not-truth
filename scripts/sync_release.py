"""Mirror the working tree into `dist/github`, and say what drifted.

**This exists because the release has already been wrong once for the same
reason.** `dist/build_hf.py` carried a hand-written list of four experiments
and silently published four of fourteen. Source/release parity was then
asserted rather than checked, and by 2026-09-18 `dist/github` was a full
experiment behind the working tree again.

A manual copy is a defect class, not an accident, so the copy is mechanical
here and the drift report is the point: run it with `--check` and it exits
non-zero if anything differs, which is the form a release gate needs.

    python scripts/sync_release.py --check     # report only, exit 1 on drift
    python scripts/sync_release.py             # report and copy
    python scripts/sync_release.py --prune     # also delete what has no source

**The GitHub release is code and one README.** Stored responses, ledgers,
labels, per-experiment write-ups and the project's internal working documents
are data and belong in the data release, which `dist/build_hf.py` builds. A
code repository that also carries 78 MB of API responses is hard to read, hard
to clone and mixes two things a reader wants separately. The split is the point,
so this manifest publishes code and nothing else.

**Every published file must have a source in this manifest, or `--prune`
deletes it.** That is deliberate, and it has already cost something: the first
prune removed a hand-written `scripts/fetch_attriguard.sh` that existed only in
the release, because nothing here produced it. Anything the release needs is
written in the working tree and published from here. Nothing is edited in
`dist/github` directly.
"""

from __future__ import annotations

import argparse
import ast
import filecmp
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_data_release          # the one scrub, shared

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "dist" / "github"


@dataclass(frozen=True)
class Tree:
    """One source directory and where it is published."""

    src: Path
    dst: str
    # When non-empty, only these paths are published, each a file or a
    # directory given relative to `src`.
    subset: tuple[Path, ...] = field(default=())


# The harness is not in this project. It lives in the authors' A-VIP checkout
# beside it, which is the second place `experiments/harness_path.py` looks, and
# it is vendored into the release so a reader needs only the one repository.
# Only the harness package is taken: A-VIP's own experiments are a different
# paper's artifact.
AVIP = ROOT.parent / "a-vip"

TREES = (
    Tree(ROOT / "experiments", "experiments"),
    Tree(ROOT / "scripts", "scripts"),
    Tree(AVIP, "vendor", (Path("05_experiments/__init__.py"),
                          Path("05_experiments/_harness"))),
)

CODE_SUFFIX = {".py", ".sh"}
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".ipynb_checkpoints"}
# Never copied and never removed; everything else in SKIP_DIRS that reaches the
# destination is stale and gets cleaned. A `.pyc` carries the absolute path it
# was compiled from, which is how eight of them published a local directory.
PRESERVE_DIRS = {".git"}
SKIP_SUFFIX = {".pyc", ".pyo"}
# A stray key is never published, whatever the manifest says
SKIP_NAMES = {".env", "key.txt", "openrouter_key.txt"}


def wanted(rel: Path, tree: Tree) -> bool:
    if any(part in SKIP_DIRS for part in rel.parts):
        return False
    if rel.suffix in SKIP_SUFFIX or rel.name in SKIP_NAMES:
        return False
    if rel.suffix not in CODE_SUFFIX:
        return False
    if tree.subset and not any(rel == s or s in rel.parents
                               for s in tree.subset):
        return False
    return True


def walk(tree: Tree) -> list[Path]:
    if not tree.src.is_dir():
        return []
    return sorted(p.relative_to(tree.src) for p in tree.src.rglob("*")
                  if p.is_file() and wanted(p.relative_to(tree.src), tree))


def published_bytes(src: Path) -> bytes:
    """What this source file looks like once published.

    A docstring that records an account balance or a spend cap is the author's
    billing position, not a measurement, and it is removed here exactly as it
    is removed from the data release. The estimate and the approval date stay:
    those are the pre-registration. A scrubbed script that no longer parses is
    a defect, so it is checked rather than assumed.
    """
    raw = src.read_bytes()
    if src.suffix != ".py":
        return raw
    # The release tooling states the patterns it searches for, so scrubbing it
    # with them removes the patterns themselves. It narrates no run and has
    # nothing to scrub.
    if src.parent.name == "scripts":
        return raw
    text, hits = build_data_release.scrub(raw.decode("utf-8"), tidy=False)
    if not hits:
        return raw
    try:
        ast.parse(text)
    except SyntaxError as exc:
        raise SystemExit(f"ERROR: scrubbing {src} broke it: {exc}")
    return text.encode("utf-8")


def plan() -> list[tuple[Path, Path, str]]:
    """Every file that should be published, with what is wrong with it now."""
    jobs: list[tuple[Path, Path, str]] = []
    for tree in TREES:
        for rel in walk(tree):
            src, dst = tree.src / rel, DEST / tree.dst / rel
            if not dst.exists():
                jobs.append((src, dst, "missing"))
            elif dst.read_bytes() != published_bytes(src):
                jobs.append((src, dst, "differs"))
    return jobs


# Published by hand and kept: they have no source in the working tree.
KEEP = {Path("README.md"), Path("LICENSE"), Path("CITATION.cff"),
        Path(".gitignore")}


def orphans() -> list[Path]:
    """Published files with no source, reported and removed only with --prune."""
    out = []
    roots = {DEST / t.dst: t for t in TREES}
    for path in sorted(DEST.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(DEST)
        if rel in KEEP or any(part in PRESERVE_DIRS for part in rel.parts):
            continue
        if any(part in SKIP_DIRS for part in rel.parts):
            out.append(path)   # bytecode compiled inside the release tree
            continue
        root = next((r for r in roots if path.is_relative_to(r)), None)
        if root is not None:
            tree, sub = roots[root], path.relative_to(root)
            if (tree.src / sub).is_file() and wanted(sub, tree):
                continue
        out.append(path)
    return out


def missing_sources() -> list[Tree]:
    """Trees whose source directory is absent, so nothing would be published."""
    return [t for t in TREES if not t.src.is_dir()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report drift and exit non-zero, copying nothing")
    ap.add_argument("--prune", action="store_true",
                    help="also delete published files with no source")
    args = ap.parse_args()

    # A missing source directory looks identical to a tree with nothing to
    # publish, and under --prune it silently deletes that tree from the
    # release. It is an error, not an empty result.
    absent = missing_sources()
    if absent:
        for tree in absent:
            print(f"ERROR: source for {tree.dst}/ does not exist: {tree.src}",
                  file=sys.stderr)
        return 2

    jobs = plan()
    extra = orphans()

    if not jobs:
        print("dist/github is in sync with the working tree")
    for _, dst, why in jobs[:40]:
        print(f"  [{why:7s}] {dst.relative_to(DEST)}")
    if len(jobs) > 40:
        print(f"  ... and {len(jobs) - 40} more")

    if extra:
        print(f"\n{len(extra)} published file(s) with no source in the manifest:")
        for path in extra[:20]:
            print(f"  [orphan ] {path.relative_to(DEST)}")
        if len(extra) > 20:
            print(f"  ... and {len(extra) - 20} more")
        if not args.prune:
            print("  (run with --prune to remove them)")

    if args.check:
        return 1 if (jobs or extra) else 0

    for src, dst, _ in jobs:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(published_bytes(src))
    print(f"\ncopied {len(jobs)} file(s)")

    if args.prune and extra:
        for path in extra:
            path.unlink()
        for d in sorted((p for p in DEST.rglob("*") if p.is_dir()),
                        key=lambda p: -len(p.parts)):
            if not any(d.iterdir()):
                d.rmdir()
        print(f"removed {len(extra)} file(s) with no source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
