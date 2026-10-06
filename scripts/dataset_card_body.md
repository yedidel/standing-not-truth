# Standing, Not Truth — the data release

Every model response, hand label, ledger and per-experiment write-up behind the
paper *Standing, Not Truth: Who May Say What About Whom in Agentic Selection*.

The code that produced all of it is a separate release: <!--CODE-->

## What was measured

An agent chooses between competing offerings supplied by parties who benefit
from the outcome. A lawful participant, whose identity fields are correctly
bound and whose channel is not compromised, writes one false factual claim
**about a competitor**. The claim carries no instruction. The experiments
measure whether that moves the agent's selection, whether defenses placed on
the **origin** of content or on its **influence** on the decision can separate
it from benign traffic, and whether a check placed on the **subject** of the
claim can.

## Subsets

Each experiment is its own table, because each measured its own thing and they
do not share a schema. The viewer's dropdown lists them.

<!--SUBSETS-->

`ledger` and `labels` are flattened views, written by
`scripts/build_data_release.py` in the code release. The ledgers carry two
schemas across 27 files and a nested `meta` field, and the hand labels are
dictionaries keyed by unit, so neither loads as it stands. Nothing is added:
`ledger` drops an always-empty `balance_after` column and lifts the traceback
out of `meta`, and `labels` turns each dictionary into one row per item. The
per-experiment files under `experiments/` remain the record.

One pass labelled four arms per unit and stored them as a list, so those rows
carry a `position` and the rest leave it empty. Its own note gives the order:
attack, control, check, sentence, with `H` the honest cheaper product, `P` the
promoted one, `A` asserts, `M` mentions, and an empty label where the arm was
not run for that unit.

Left out of the subset list, because they hold a mapping rather than a list of
rows: <!--SKIPPED-->. Both are present as files.

## Layout

```
LIMITATIONS.md     all 34 limitations, with their states
data/
  ledger.jsonl     every metered call, one row each
  labels.jsonl     every hand label, one row each
experiments/<id>/  one directory per experiment, 52 of them. `A*` are the
                   Phase-A feasibility experiments, `B*` the Phase-B programme
                   the paper reports.
  RESULTS.md       the write-up: numbers, denominators, reading notes
  rows.json        one row per unit, with the replies and the labels
  labels.json      hand-assigned outcomes, where a pass was made
  raw/             the stored response for every call, one file each
  ledger.jsonl     one append-only record per metered call
```

Forty-seven directories hold a `RESULTS.md`. The five that do not are
`B14_annotator_agreement` (`README.md`), `B2_binding_taxonomy`
(`TAXONOMY.md`), `B35_model_panel` and `B36_extractor_transfer`
(`run/RUN_REPORT.md`, with the panel's reported numbers in
`B37_relabel/RESULTS.md`), and `B28_multi_span`, which holds stored rows and no
write-up because nothing in the paper rests on it.

## Limitations

`LIMITATIONS.md` holds every limitation this work recorded, 34 of them, each
with its state and, where one exists, the measurement that settled it. None is
open. The paper's Limitations section carries the load-bearing entries; this is
all of them, including the two pre-registered theses our own experiments
refuted.

The ids are not contiguous with the order the limitations were recorded in.
Five were added later and given ids an earlier block already held; they are
`L30` to `L34`. Two result files here, `B19` and `B27`, cite `L21` and `L22` in
the earlier sense, so the earlier block kept its numbers.

## How to read a result

Four conventions run through every write-up.

1. **Scoring is by reading, not by code.** No script decided whether a reply
   was a hit. The annotator is an LLM reading replies one at a time, so its
   reliability is measured rather than assumed: against an independent human
   pass over a stratified sample of 201 items, Cohen's kappa is 0.933 on the
   choice task and 1.000 on the subject task, with every disagreement
   adjudicated, and a later 183-item pass over the thirteen-model panel gives
   1.000. That frame covers `B13`, `B5`, `B12` and the panel; the remaining
   experiments carry no second pass.
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

## Ledgers

Every metered call is recorded in an append-only JSONL ledger next to the
experiment that made it: the request, the model, the cost, and a **SHA-256 over
the stored raw response**. `verify_ledger.py` in the code release checks them
and classifies what it finds:

```
ledger records examined : 12340
  digest verified       : 9863
  superseded by a retry : 1688
  empty, asked again    :   29
  no digest stored      :  760
  UNEXPLAINED           :    0
```

**Use that script rather than hashing the files directly.** Two undocumented
facts stand in the way: the digest was taken before the writer applied the
platform newline translation, and the backfilled records digest one row inside
the named file rather than the file.

The two middle rows follow from one design decision. The ledger is append-only;
the response store is keyed by unit id and is not. When a unit was called twice
the second response overwrote the first file, so the earlier record's digest
can never match again. A superseded record counts as accounted for only when a
later record over the same file matches the file as it now stands; one with no
such partner is reported as unexplained. The 29 are fifteen `claude-opus-5`
units that returned no content, which the harness recorded as `ok` with zero
tokens without writing a file, and which `retry_empties.py` asked again under a
`|retry` unit id. The 760 without a digest are calls that failed outright.

Some stored responses contain an opaque encrypted `data` field. That is the
provider's own encrypted reasoning payload, kept as returned so the digests
verify. Absolute paths inside stored tracebacks are replaced by `<project>`,
`<harness>` and `<python>`; every frame and line number is untouched.

## Licence

Data and documentation under CC BY 4.0. See `LICENSE`, which also covers the
code release and the third-party material not redistributed here. The npm and
marketplace text under study belongs to its original authors and is included as
research data.
