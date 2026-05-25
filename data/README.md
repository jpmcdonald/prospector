# Data layout

## Raw LinkedIn exports (never in git)

Quasi-weekly zip downloads from LinkedIn (Settings → Data Privacy → Get a copy of your data):

```
/Users/jpmcdonald/Library/CloudStorage/Dropbox/LinkedIn/
```

Set `LINKEDIN_ARCHIVE_PATH` in `.env` to this folder. Zips stay in Dropbox only.

## Derived tables (DVC-tracked)

Parsed outputs live under `data/tables/`. Blobs are stored in the local DVC remote; git holds `.dvc` pointer files and small manifests only.

| Path | Purpose |
|------|---------|
| `data/tables/` | Normalized connections, messages, joins |
| `data/tables/manifest/` | Zip SHA256 registry and run metadata (small files, in git) |

## DVC local remote

```
/Users/jpmcdonald/DVC/Prospector
```

```bash
dvc pull    # restore tracked tables after clone
dvc push    # copy blobs to local store after ingest
```

Remote backup server: configure later by changing `.dvc/config` `url`.

## Interim dev path (single CSV)

Until the zip pipeline exists, you can still drop a connections export in `data/inbox/` and run `python load_connections.py`. Snapshots go to `data/snapshots/`; processed files move to `data/archive/`.

## Neo4j graph

The live graph and `ConnectionChangeLog` audit nodes live in Docker volumes (`prospector_neo4j_data`), not in git or DVC.

## Provenance (Quarterdeck-aligned)

When ingestion work is Charter-governed, each load records:

- `source_file`, `source_sha256`, `loaded_at_utc`, `run_id` on staged rows
- Manifest per run: input zip hashes, git commit, environment
- SHA registry under `data/tables/manifest/` for derived artifacts

See [Quarterdeck OPERATING_DISCIPLINE](file:///Users/jpmcdonald/Quarterdeck/OPERATING_DISCIPLINE.md).
