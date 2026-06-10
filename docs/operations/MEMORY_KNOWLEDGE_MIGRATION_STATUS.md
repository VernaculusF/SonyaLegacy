# Memory and Knowledge Migration Status

**Status:** Active audit; no production migration writes performed
**Last updated:** 2026-06-10

## Production Inventory

Read-only VPS inventory:

| Layer | Rows / files |
|---|---:|
| `episodic_events` | 13,273 |
| `semantic_facts` | 3,346 |
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

Next, create the WAL-safe backup and run migration-source/deduplication analysis
against the backup copy before any production write.

Operational note: `deploy/backup.sh` must use SQLite Backup API even when the
`sqlite3` CLI is absent. Plain `cp` of the live WAL database is forbidden.
