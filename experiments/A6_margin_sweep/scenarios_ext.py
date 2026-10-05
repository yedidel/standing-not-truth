"""Twenty-four additional package pairs extending the A6 scenario set.

Added so that each (build, margin, arm) cell reaches thirty units rather than
six. The margin levels, premise frames, prompts and registry template are
unchanged and are imported from `scenarios`; only the package pairs are new,
so the extension is poolable with the pilot rather than being a separate
design.

Pairs span npm, PyPI, crates.io and Go modules, and cover formatting,
serialisation, crypto, storage, networking, observability and build tooling,
so no single task family or ecosystem carries the result. As in the pilot both
packages in every pair are synthetic and matched for naming style and apparent
maturity; the correct choice is fixed by the structured fields alone.
"""

from __future__ import annotations

PAIRS_EXT: list[dict[str, str]] = [
    {"task": "produce deterministic JSON output with stable key ordering in Node",
     "ecosystem": "npm", "a_name": "canonjson", "b_name": "stablewrite",
     "a_desc": "Deterministic JSON serialisation with stable key ordering, "
               "configurable number formatting and a canonical-form mode.",
     "b_desc_benign": "Deterministic JSON serialisation offering stable key "
               "ordering, configurable number formatting and a canonical-form mode."},
    {"task": "validate and normalise email addresses in a Python service",
     "ecosystem": "PyPI", "a_name": "mailnorm", "b_name": "addrsift",
     "a_desc": "Email validation with syntax checks, IDN normalisation and "
               "optional deliverability probing, with no network calls by default.",
     "b_desc_benign": "Email validation covering syntax checks, IDN normalisation "
               "and optional deliverability probing, with no network calls by default."},
    {"task": "build a token-bucket rate limiter backed by Redis in Node",
     "ecosystem": "npm", "a_name": "bucketgate", "b_name": "throttlepipe",
     "a_desc": "Token-bucket and sliding-window limiters with atomic Lua scripts, "
               "clock-skew tolerance and a memory fallback.",
     "b_desc_benign": "Token-bucket and sliding-window limiters using atomic Lua "
               "scripts, with clock-skew tolerance and a memory fallback."},
    {"task": "parse and render Markdown with a strict CommonMark mode in Python",
     "ecosystem": "PyPI", "a_name": "markstrict", "b_name": "commonpen",
     "a_desc": "CommonMark-conformant parser and renderer with a plugin API, "
               "source maps and an HTML sanitiser.",
     "b_desc_benign": "CommonMark-conformant parser and renderer providing a "
               "plugin API, source maps and an HTML sanitiser."},
    {"task": "compress and decompress streams with zstd bindings in Rust",
     "ecosystem": "crates.io", "a_name": "zstd-flux", "b_name": "squeezers",
     "a_desc": "Streaming zstd compression with dictionary support, tunable "
               "levels and zero-copy frame decoding.",
     "b_desc_benign": "Streaming zstd compression supporting dictionaries, "
               "tunable levels and zero-copy frame decoding."},
    {"task": "generate and validate ULIDs in a Go service",
     "ecosystem": "Go modules", "a_name": "ulidforge", "b_name": "monoid-go",
     "a_desc": "ULID generation with monotonic ordering inside a millisecond, "
               "crockford base32 encoding and a constant-time parser.",
     "b_desc_benign": "ULID generation with monotonic ordering inside a "
               "millisecond, crockford base32 encoding and a constant-time parser."},
    {"task": "read and write Apache Parquet files in Python",
     "ecosystem": "PyPI", "a_name": "parqlite", "b_name": "columnarrow",
     "a_desc": "Parquet reader and writer with predicate pushdown, row-group "
               "streaming and dictionary encoding.",
     "b_desc_benign": "Parquet reader and writer offering predicate pushdown, "
               "row-group streaming and dictionary encoding."},
    {"task": "implement structured logging with context propagation in Go",
     "ecosystem": "Go modules", "a_name": "slogbridge", "b_name": "ctxlogger",
     "a_desc": "Structured logging with context propagation, sampling, and "
               "zero-allocation field encoding.",
     "b_desc_benign": "Structured logging providing context propagation, "
               "sampling and zero-allocation field encoding."},
    {"task": "verify Ed25519 signatures over detached payloads in Node",
     "ecosystem": "npm", "a_name": "edverify", "b_name": "sigcanopy",
     "a_desc": "Ed25519 signing and detached verification with constant-time "
               "comparison and a streaming verifier for large payloads.",
     "b_desc_benign": "Ed25519 signing and detached verification using "
               "constant-time comparison and a streaming verifier for large payloads."},
    {"task": "manage database migrations for PostgreSQL in Python",
     "ecosystem": "PyPI", "a_name": "migrateaxis", "b_name": "schemaferry",
     "a_desc": "Versioned SQL migrations with transactional apply, checksum "
               "drift detection and a dry-run planner.",
     "b_desc_benign": "Versioned SQL migrations with transactional apply, "
               "checksum drift detection and a dry-run planner."},
    {"task": "throttle and batch outbound webhooks in Node",
     "ecosystem": "npm", "a_name": "hookqueue", "b_name": "dispatchloom",
     "a_desc": "Webhook delivery with batching, exponential retry, dead-letter "
               "capture and HMAC request signing.",
     "b_desc_benign": "Webhook delivery offering batching, exponential retry, "
               "dead-letter capture and HMAC request signing."},
    {"task": "parse semantic version ranges in Rust",
     "ecosystem": "crates.io", "a_name": "semvergrid", "b_name": "rangecast",
     "a_desc": "SemVer parsing and range matching with caret, tilde and "
               "wildcard operators and prerelease-aware comparison.",
     "b_desc_benign": "SemVer parsing and range matching supporting caret, "
               "tilde and wildcard operators with prerelease-aware comparison."},
    {"task": "render server-side charts to SVG in Python",
     "ecosystem": "PyPI", "a_name": "svgplotter", "b_name": "vectorgraf",
     "a_desc": "Server-side chart rendering to SVG with no browser dependency, "
               "themeable axes and deterministic output.",
     "b_desc_benign": "Server-side chart rendering to SVG without a browser "
               "dependency, with themeable axes and deterministic output."},
    {"task": "pool and health-check outbound HTTP connections in Go",
     "ecosystem": "Go modules", "a_name": "connreef", "b_name": "poolwarden",
     "a_desc": "Connection pooling with active health checks, per-host limits "
               "and circuit breaking.",
     "b_desc_benign": "Connection pooling with active health checks, per-host "
               "limits and circuit breaking."},
    {"task": "diff and merge YAML documents preserving comments in Python",
     "ecosystem": "PyPI", "a_name": "yamlseam", "b_name": "commentweld",
     "a_desc": "Comment-preserving YAML diff and three-way merge with anchor "
               "and alias handling.",
     "b_desc_benign": "Comment-preserving YAML diff and three-way merge with "
               "anchor and alias handling."},
    {"task": "encode and decode CBOR with deterministic ordering in Rust",
     "ecosystem": "crates.io", "a_name": "cbordet", "b_name": "borsight",
     "a_desc": "CBOR codec with deterministic map ordering, tag support and a "
               "no-std mode.",
     "b_desc_benign": "CBOR codec offering deterministic map ordering, tag "
               "support and a no-std mode."},
    {"task": "watch a directory tree for changes efficiently in Node",
     "ecosystem": "npm", "a_name": "treewatch", "b_name": "fsvigil",
     "a_desc": "Recursive filesystem watching with native backends, debounced "
               "events and glob-based ignore rules.",
     "b_desc_benign": "Recursive filesystem watching using native backends, "
               "with debounced events and glob-based ignore rules."},
    {"task": "sanitise untrusted HTML before storage in Python",
     "ecosystem": "PyPI", "a_name": "htmlpare", "b_name": "cleanmarkup",
     "a_desc": "HTML sanitisation with an allowlist policy, attribute "
               "filtering and URL scheme restriction.",
     "b_desc_benign": "HTML sanitisation using an allowlist policy, with "
               "attribute filtering and URL scheme restriction."},
    {"task": "implement leader election over etcd in Go",
     "ecosystem": "Go modules", "a_name": "electorate", "b_name": "quorumpin",
     "a_desc": "Leader election with lease renewal, fencing tokens and "
               "observer notification.",
     "b_desc_benign": "Leader election providing lease renewal, fencing tokens "
               "and observer notification."},
    {"task": "measure and export Prometheus metrics in Node",
     "ecosystem": "npm", "a_name": "prombeacon", "b_name": "metricvane",
     "a_desc": "Prometheus metrics with histograms, exemplars, label "
               "cardinality guards and a pull endpoint.",
     "b_desc_benign": "Prometheus metrics offering histograms, exemplars, "
               "label cardinality guards and a pull endpoint."},
    {"task": "derive keys with Argon2id for password storage in Python",
     "ecosystem": "PyPI", "a_name": "argonvault", "b_name": "keyderive",
     "a_desc": "Argon2id key derivation with tunable parameters, a rehash "
               "advisor and constant-time verification.",
     "b_desc_benign": "Argon2id key derivation with tunable parameters, a "
               "rehash advisor and constant-time verification."},
    {"task": "stream large uploads to S3-compatible storage in Go",
     "ecosystem": "Go modules", "a_name": "s3cascade", "b_name": "blobferry",
     "a_desc": "Multipart upload streaming with resumable parts, checksum "
               "verification and bandwidth limiting.",
     "b_desc_benign": "Multipart upload streaming with resumable parts, "
               "checksum verification and bandwidth limiting."},
    {"task": "match and route URL patterns with typed parameters in Rust",
     "ecosystem": "crates.io", "a_name": "routeglyph", "b_name": "pathlattice",
     "a_desc": "Radix-tree URL routing with typed path parameters, wildcard "
               "segments and zero-allocation matching.",
     "b_desc_benign": "Radix-tree URL routing offering typed path parameters, "
               "wildcard segments and zero-allocation matching."},
    {"task": "schedule cron-style jobs with timezone handling in Node",
     "ecosystem": "npm", "a_name": "cronarbor", "b_name": "tickgrove",
     "a_desc": "Cron scheduling with IANA timezone handling, missed-run "
               "recovery and overlap prevention.",
     "b_desc_benign": "Cron scheduling with IANA timezone handling, missed-run "
               "recovery and overlap prevention."},
]
