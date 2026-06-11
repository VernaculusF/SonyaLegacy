# Memory and Knowledge Migration Status

**Status:** Active audit; production semantic dedup applied after explicit approval
**Last updated:** 2026-06-11

## Production Inventory

Read-only VPS inventory:

| Layer | Rows / files |
|---|---:|
| `episodic_events` | 13,273 |
| `semantic_facts` | 1,913 after exact semantic dedup |
| `raw_traces` | 1 |
| `procedural_memory` | 20 |
| `continuity_events` | 23,238 |
| `tool_experiences` | 242 |
| `~/.sonya/knowledge/` | 12 files, about 82 KB |

No Telegram Desktop `result.json` import source was found in the repository
checkout. The live `tg.session` is runtime authentication state, not an import
source and must not be modified by migration work.

## Main Finding

The production substrate already contains substantial episodic, semantic, and
continuity history. This is not a blank migration. The critical gap is the
nearly empty process-wide `raw_traces` layer, not absence of memory generally.

Migration work must preserve the one shared Sonya memory while keeping main and
project UI histories distinct. Subagent raw chatter must not be copied directly
into durable semantic/procedural memory; only scoped traces, results, and
derived lessons should enter those layers.

## Existing Migration Capabilities

- `src/sonya/tools/import_history.py` imports Telegram Desktop `result.json`
  into episodic memory when such an export exists.
- `migrate_legacy_knowledge_dirs()` migrates legacy markdown knowledge and
  built-in knowledge constants.
- current memory layers use `episodic_events`, `semantic_facts`, `raw_traces`,
  `procedural_memory`, and `continuity_events`.

## Safe Migration Order

1. Create a WAL-safe substrate backup and knowledge tarball.
2. Generate a read-only manifest containing row counts, schemas, source paths,
   hashes, and provenance categories.
3. Identify actual legacy sources; do not invent imports where no source exists.
4. Run migration on a backup copy and record inserted/skipped/deduplicated
   counts.
5. Verify retrieval, project scope, provenance, and one-Sonya continuity.
6. Apply idempotently to production only after the backup-copy proof passes.
7. Re-run the manifest and compare counts/hashes.

## Next Implementation Slice

The read-only migration manifest command is implemented:

```bash
python -m sonya.tools.memory_migration_manifest \
  --substrate ~/.sonya/sonya_substrate.db \
  --knowledge-root ~/.sonya/knowledge \
  --project-root ~/Sonya \
  --output /tmp/sonya-memory-manifest.json
```

It opens SQLite with `mode=ro` and emits only counts, schemas, paths, sizes,
knowledge hashes, an inventory fingerprint, and source categories. It does not
emit memory or knowledge content. Full SQLite file hashing is disabled by
default because a live WAL database is not a stable file snapshot; use
`--hash-substrate` only against an offline or backup copy.

The manifest also records capped distributions for explicitly allowed
provenance fields such as event/source/type/scope, continuity kind, trace type,
tool outcome, provider, and model. It never reads content fields into output.
Exact duplicate group counts are available through `--analyze-duplicates` and
must be run only against a backup copy. The output contains counts, never the
duplicate values.

## Backup Proof

On 2026-06-10 the VPS backup path was repaired and proven:

- Python SQLite Backup API fallback used because the `sqlite3` CLI is absent;
- gzip integrity check passed;
- unpacked backup `PRAGMA quick_check` returned `ok`;
- full backup SHA-256 recorded in the offline manifest;
- memory-layer row counts matched the live inventory except expected new
  continuity events written between snapshots.

Next, inspect provenance distributions and design explicit deduplication rules
against the backup copy before any production write.

## Deduplication Policy

- Never deduplicate episodic events by content alone. Repeated messages and
  observations are distinct events.
- Exact semantic duplicates may merge only when `fact_type`, `statement`,
  `scope`, `project_id`, and `retention_policy` all match.
- Semantic merge keeps the strongest/newest fact and unions source event IDs
  and contradiction flags.
- Procedural, raw trace, and knowledge deduplication remain manual until their
  evidence justifies an automated rule.

`sonya.tools.memory_semantic_dedup` is dry-run by default. Apply requires either
`--apply --target-is-backup-copy` for disposable proofs or
`--apply --target-is-production-approved` after explicit production approval.

## Backup-Copy Dedup Proof

Applied only to `/tmp/sonya-semantic-dedup-proof.db`:

- dry-run: `245 groups`, `1,532 extra rows`
- apply: deleted exactly `1,532` rows
- semantic rows: `3,396 -> 1,864`
- repeated dry-run: `0 groups`, `0 extra rows`
- `PRAGMA quick_check`: `ok`
- `1,708` retained facts still carry source provenance
- `SemanticMemory.get_for_context(limit=50)` returned 50 unique statements

The initial backup-copy proof did not modify production. Production apply still
requires explicit approval because it deletes duplicate rows even when exact
semantic provenance merge rules pass.

Operational note: `deploy/backup.sh` must use SQLite Backup API even when the
`sqlite3` CLI is absent. Plain `cp` of the live WAL database is forbidden.

## Project Shared-Memory Proof

On 2026-06-11 the project outcome compiler was corrected and proven on the VPS:

- completed project runs are no longer skipped by `MemoryCompiler`;
- project summaries are written as semantic facts with `scope="project"` and
  the concrete `project_id`;
- raw subagent chatter remains out of semantic behavior memory;
- fresh WAL-safe production backup was created and gzip-verified;
- live and backup read-only migration manifests were generated;
- duplicate analysis ran only against the backup copy;
- focused project-memory and manifest suite passed (`4 passed`).

## Production Semantic Dedup

Applied on 2026-06-11 after explicit approval:

- fresh WAL-safe production backup created and gzip-verified:
  `/home/jester-sonya/.sonya/backups/daily/sonya_2026-06-11.db.gz`;
- pre-apply live plan: `287 groups`, `1,951 extra rows`;
- apply: deleted exactly `1,951` duplicate semantic rows;
- semantic rows: `3,864 -> 1,913`;
- post-apply plan: `0 groups`, `0 extra rows`;
- SQL duplicate group check: `0`;
- `PRAGMA quick_check`: `ok`;
- `SemanticMemory.get_for_context(limit=50)` returned 50 facts with 50 unique
  semantic signatures.
