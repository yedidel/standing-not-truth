# Premise attacks on agentic selection — code

Experiment code for the paper *Signed, Verified, and False: The Attestation
Fallacy in Agentic Selection*.

**This repository is code and this document, nothing else.** The stored model
responses, the hand labels, the append-only ledgers and the per-experiment
write-ups are data, and they are published as a separate data release. A code
repository that also carries 78 MB of API responses is hard to read and hard to
clone, and the two are wanted separately: this one to see what was run, the
other to check what came back.

| | |
|---|---|
| here | 51 experiment directories, 132 Python files, 2 fetch scripts, the vendored harness |
| data release | every stored response, both label passes, the ledgers and the per-experiment result files, at https://huggingface.co/datasets/anonymos-2321135/standing-not-truth |

---

## What the paper measures, in one paragraph

An agent chooses between competing offerings supplied by parties who benefit
from the outcome. A lawful participant, whose identity fields are correctly
bound and whose channel is not compromised, writes one false factual claim
**about a competitor**. The claim carries no instruction. We measure whether
that moves the agent's selection, whether defenses placed on the **origin** of
content or on its **influence** on the decision can separate it from benign
traffic, and whether a check placed on the **subject** of the claim can.

---

## Layout

```
experiments/     51 experiments, one directory each. `A*` are the Phase-A
                 feasibility experiments, `B*` the Phase-B programme the paper
                 reports. Each directory holds the script that produced its
                 numbers; the replies and labels it produced are in the data
                 release under the same directory name.
vendor/          the model-call harness (ledger, Ollama and OpenRouter
                 clients), vendored from the authors' A-VIP artifact so this
                 repository runs on its own
scripts/         fetch_attriguard.sh and fetch_camel.sh, for the two
                 dependencies not shipped here. sync_release.py builds this
                 tree, build_data_release.py builds the data release, and
                 build_dataset_card.py writes that release's dataset card
                 with its subset list taken from the tree rather than typed
```

`experiments/harness_path.py` resolves the harness in either tree, so nothing
needs a path edited. `experiments/preflight.py` and `verify_ledger.py` check
the data release and need it present to do anything.

---

## Reproducing

### Requirements

- Python 3.11 or later, standard library only for the harness and for every
  experiment. `scripts/build_dataset_card.py` needs `pyarrow`, because it
  checks that each table it declares really loads as one; nothing else does.
- [Ollama](https://ollama.com) for the open-weight deciders (`gpt-oss:120b`,
  `glm-5.3`, `mistral-large-3:675b`)
- An OpenRouter API key for the closed-weight arms, exported as an environment
  variable. **No key is stored in this repository, in any ledger, or in any
  stored response.** That is a standing rule of the project, and this tree was
  scanned for one before release.

### Running one experiment

Each experiment directory is self-contained and resolves the harness relative
to the repository root:

```bash
cd experiments/B13_harmonise_n
python run.py
```

`B13` is the one to start with. It re-runs the placement comparison on both
deciders over the full unit set, it costs nothing because both models are
open-weight, and it produces the paper's headline figure.

Scripts are resumable. Each writes partial results as it goes and skips units
already stored, so an interrupted run continues rather than restarting. That
also means a script run against the data release will do nothing until the
stored responses are moved aside.

### The two dependencies not shipped here

```bash
bash scripts/fetch_attriguard.sh    # USENIX Security 2026 artifact, digest-pinned
bash scripts/fetch_camel.sh         # google-research/camel-prompt-injection, Apache 2.0
```

`B4` reproduces AttriGuard by parsing its prompts out of the authors' own
source at run time rather than transcribing them, and `B18` imports CaMeL's
capability model and policy engine directly and reimplements nothing. Both
checkouts must be present for those two to run. Neither is redistributed here:
they are other authors' work.

The AttriGuard fetch is pinned by SHA-256 and byte count against a Zenodo
deposit, verified before unpacking, and refuses to proceed on a mismatch.
**If the digest does not match, the upstream distribution has changed and the
B-4 numbers in the paper were measured against a different file.** CaMeL is
cloned unpinned from a live repository, because `B18` uses only its capability
model and policy interface and will fail loudly on import rather than quietly
produce a different number.

---

## How to read a result

Each experiment in the data release carries its own write-up, recorded at the
time of the run: the numbers, the denominators and the reading notes,
**including the defects found in our own instruments and what was done about
them**. Those files are the primary record; the paper is a selection from them.

Forty-seven of the fifty-two directories hold a `RESULTS.md`. The remaining
five are named here so nobody goes looking: `B14_annotator_agreement` uses
`README.md`, `B2_binding_taxonomy` uses `TAXONOMY.md`, and `B35_model_panel`
and `B36_extractor_transfer` keep a `run/RUN_REPORT.md` because the panel's
reported numbers come from the later reading pass and live in
`B37_relabel/RESULTS.md`. `B28_multi_span` holds stored rows and no write-up,
and nothing in the paper rests on it.

Four conventions run through all of them.

1. **Scoring is by reading, not by code.** No script decides whether a reply is
   a hit. Deterministic readers exist in this repository only as replication
   artifacts, validated against the hand labels after the fact. The annotator
   is an LLM reading replies one at a time, so its reliability is measured
   rather than assumed: against an independent human pass over a stratified
   sample of 201 items, Cohen's kappa is 0.933 on the choice task and 1.000 on
   the subject task, with every disagreement adjudicated, and a later 183-item
   pass over the thirteen-model panel gives 1.000. That frame covers `B13`,
   `B5`, `B12` and the panel; the remaining experiments carry no second pass.
2. **Denominators are stated and never pooled across populations.**
3. **Every rate carries a Wilson 95% interval**, and where a unit is decided by
   several models the interval is also computed by cluster bootstrap, because
   treating thirteen decisions on one base pair as thirteen independent
   observations understates the width.
4. **Negative and refuted results are kept.** Two pre-registered theses were
   refuted by our own experiments and both are recorded rather than removed.

`B37_relabel` is the later pass in which all 1,689 stored replies of the three
largest experiments, and then all 1,682 replies of the thirteen-model panel,
were read again one at a time. It moved four published rates, left the attack
outcomes unchanged, and supplied the panel result. **The panel's
blanket-removal arm is a baseline floor rather than a defense result**, and
reading it as one matters: `command-r7b` lands the attacker's package on 22 of
45 units with the description deleted entirely, against 7 of 45 with only the
claim removed, because it reads the earlier of two publish dates as the more
recent. Without that floor, one model's arithmetic would be scored as the
defense failing.

---

## Ledgers and evidence retention

Every metered model call is recorded in an append-only JSONL ledger next to the
experiment that made it: the request, the model, the cost, and a **SHA-256 over
the stored raw response**. The ledgers and the responses are in the data
release; these two scripts verify them once it is present.

```bash
python experiments/preflight.py      # four defect classes this project kept repeating
python experiments/verify_ledger.py  # digests over the stored raw responses
```

`preflight.py` exists because point-fixing an error does not prevent it: one of
its four classes recurred five times before it was checked mechanically.

**Use `verify_ledger.py` rather than hashing the files directly.** Two
undocumented facts stand in the way: the digest is taken before `write_text`
applies the platform newline translation, and the backfilled records digest one
row inside the named file rather than the file. Hashing file bytes naively
mismatches on every record. The script handles both, and it classifies what it
finds rather than reporting a bare count:

```
ledger records examined : 12340
  digest verified       : 9863
  superseded by a retry : 1688
  empty, asked again    :   29
  no digest stored      :  760
  UNEXPLAINED           :    0
```

The two middle rows are the consequence of one design decision. **The ledger is
append-only; the raw-response store is keyed by unit id and is not.** When a
unit is called twice the second response overwrites the first file, so the
earlier record's digest can never match again. The script does not take that on
trust: a superseded record counts as accounted for only when a later record
over the same file matches the file as it now stands, and an earlier record
with no such partner is reported as unexplained. Most of the 1,688 come from
the thirteen-model panel, where rate limits forced long retry passes.

The 29 are fifteen `claude-opus-5` units that returned no content. The harness
recorded them as `ok` with zero tokens and never wrote a file, which also made
them invisible to resume, so `retry_empties.py` asked them again under a
`|retry` unit id. Both records stay in the ledger. The 760 without a digest are
calls that failed outright and produced no response to hash.

No reported number is affected by any of this: every figure was computed from
the surviving file.

Some stored OpenRouter responses contain an opaque encrypted `data` field. That
is the provider's own encrypted reasoning payload, kept as returned so the
digests verify. It contains nothing of ours.

---

## Citing

See [`CITATION.cff`](CITATION.cff). Until the paper appears, cite this
artifact.

## Licence

Code under MIT. See [`LICENSE`](LICENSE). Third-party material is not covered:
the vendored harness is the authors' own, carried under the same terms, and the
AttriGuard and CaMeL artifacts are fetched rather than redistributed. The npm
and marketplace text under study belongs to its original authors and is
included in the data release as research data.
