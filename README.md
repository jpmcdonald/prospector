# KC Prospector

Graph navigator for warm paths from Patrick's LinkedIn network to KC manufacturer targets.

## Stack
Neo4j 5 (Docker) · Python · Streamlit · rapidfuzz · DVC (local data store)

## Data

LinkedIn archive zips live in Dropbox (see `LINKEDIN_ARCHIVE_PATH` in `.env.example`). Derived tables use DVC with local remote at `/Users/jpmcdonald/DVC/Prospector`. Details: [data/README.md](data/README.md).

Install DVC when needed: `pip install dvc` or `brew install dvc`.

## One-time setup

1. **Configure env**
   ```bash
   cp .env.example .env
   # edit .env: NEO4J_PASSWORD and LINKEDIN_ARCHIVE_PATH if needed
   ```

2. **Start Neo4j**
   ```bash
   docker compose up -d
   ```
   Browser: http://localhost:7475 · Bolt: `bolt://localhost:7688`
   (Non-default ports so this instance cohabits with other Neo4j containers.)

3. **Python env**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Apply schema + seed today's session data**
   ```bash
   python db.py
   python seed_data.py
   ```

## Weekly connections refresh

**Target (planned):** quasi-weekly LinkedIn archive zips in Dropbox → parse → `data/tables/` → Neo4j.

**Interim:** single connections CSV:

1. Export connections from LinkedIn → drop the CSV into `data/inbox/`
2. Run:
   ```bash
   python load_connections.py
   ```
3. The loader will:
   - snapshot the file to `data/snapshots/connections_YYYY-MM-DD.csv`
   - upsert all rows (CDC: new, unchanged, removed, reactivated)
   - write a `ConnectionChangeLog` audit node
   - move the processed file to `data/archive/`, clearing the inbox

Re-runs are safe (everything uses MERGE).

## Run the app

```bash
streamlit run app.py
```

Three tabs:
- **Target Dashboard** — all target companies with shortest warm path, filter by tier/status, add new targets
- **Path Finder** — paste raw text from LinkedIn Sales Navigator, parser flags bankers/CEPAs/etc., resolves mutuals against the graph, lets you commit each person with a target/bridge
- **Referral Partners** — bankers, CEPAs, chamber connectors ranked by number of targets they bridge to

## File map

| File | Purpose |
|---|---|
| `docker-compose.yml` | Isolated Neo4j 5 container on ports 7688/7475 |
| `schema.cypher` | Constraints + indexes |
| `db.py` | Driver singleton + `apply_schema()` |
| `constants.py` | Status enums, path types, owner aliases — single source of truth |
| `keywords.yaml` | Parser keyword lists (edit freely, no code change) |
| `load_connections.py` | CSV loader with CDC and history |
| `seed_data.py` | Pre-loads today's session people + 2 starter targets |
| `parser.py` | Navigator paste parser + owner alias matching |
| `app.py` | Streamlit UI (3 tabs) |

## Notes

- **URL-missing rows** are loaded with `url_missing: true` and keyed on `(name, company)`. Visible in queries; not silently dropped.
- **Fuzzy matching** only fires for owner aliases (J. Patrick / JP / Pat → Patrick McDonald). Everyone else is exact-match to avoid false merges.
- **CDC** never deletes Person nodes — removed connections get `status: removed` so historical bridges stay intact.
