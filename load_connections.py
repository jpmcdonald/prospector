"""
LinkedIn connections CSV loader with change data capture.

Workflow:
  1. Drop LinkedIn export into data/inbox/
  2. Run: python load_connections.py
  3. File is snapshotted, diffed against graph, then moved to archive/

CDC behavior:
  - New URLs       -> create Person, status=active, first_seen=today
  - Existing URLs  -> update last_seen
  - Missing URLs   -> mark status=removed, removed_date=today (NOT deleted)
  - Reactivated    -> flip back to active, append to reactivation_dates

A ConnectionChangeLog node is created per run for audit history.
"""
import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from constants import OWNER_CANONICAL_NAME, PERSON_STATUS
from db import session, apply_schema

ROOT = Path(__file__).parent
INBOX = ROOT / "data" / "inbox"
SNAPSHOTS = ROOT / "data" / "snapshots"
ARCHIVE = ROOT / "data" / "archive"

# LinkedIn export header columns (post-skip)
COL_FIRST = "First Name"
COL_LAST = "Last Name"
COL_URL = "URL"
COL_COMPANY = "Company"
COL_POSITION = "Position"
COL_CONNECTED = "Connected On"


def find_inbox_file() -> Path:
    csvs = sorted(INBOX.glob("*.csv"))
    if not csvs:
        print(f"No CSV in {INBOX}. Drop a LinkedIn export there and re-run.")
        sys.exit(1)
    if len(csvs) > 1:
        print(f"Multiple CSVs in inbox; processing newest: {csvs[-1].name}")
    return csvs[-1]


def read_linkedin_csv(path: Path) -> pd.DataFrame:
    """LinkedIn export has a 3-line preamble before the real header."""
    # Try with skiprows=3 first (standard LinkedIn export)
    for skip in (3, 0):
        try:
            df = pd.read_csv(path, skiprows=skip, dtype=str, keep_default_na=False)
            if COL_FIRST in df.columns and COL_URL in df.columns:
                return df
        except Exception:
            continue
    raise ValueError(f"Could not parse {path} — expected columns {COL_FIRST}, {COL_URL}")


def normalize_rows(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        first = (r.get(COL_FIRST) or "").strip()
        last = (r.get(COL_LAST) or "").strip()
        name = f"{first} {last}".strip()
        if not name:
            continue
        url = (r.get(COL_URL) or "").strip()
        rows.append({
            "name": name,
            "linkedin_url": url,
            "company_name": (r.get(COL_COMPANY) or "").strip(),
            "title": (r.get(COL_POSITION) or "").strip(),
            "connected_date": (r.get(COL_CONNECTED) or "").strip(),
            "url_missing": url == "",
        })
    return rows


def ensure_owner(tx):
    tx.run(
        "MERGE (p:Person {name: $name}) "
        "ON CREATE SET p.is_first_degree = true, p.status = $active, p.is_owner = true",
        name=OWNER_CANONICAL_NAME, active=PERSON_STATUS["ACTIVE"],
    )


def upsert_person(tx, row, today):
    """MERGE on URL when present, else on (name, company) composite — flagged."""
    if row["url_missing"]:
        result = tx.run(
            """
            MERGE (p:Person {name: $name, company_name: $company, url_missing: true})
            ON CREATE SET p.is_first_degree = true,
                          p.first_seen = date($today),
                          p.status = $active,
                          p.title = $title,
                          p.connected_date = $connected
            ON MATCH SET  p.last_seen = date($today)
            WITH p
            CALL {
                WITH p
                WITH p WHERE p.status = $removed
                SET p.status = $active,
                    p.reactivation_dates = coalesce(p.reactivation_dates, []) + [date($today)],
                    p.removed_date = null
                RETURN 1 AS reactivated
                UNION
                WITH p WHERE p.status <> $removed
                RETURN 0 AS reactivated
            }
            SET p.last_seen = date($today)
            RETURN p.first_seen = date($today) AS created, reactivated
            """,
            name=row["name"], company=row["company_name"], title=row["title"],
            connected=row["connected_date"], today=today,
            active=PERSON_STATUS["ACTIVE"], removed=PERSON_STATUS["REMOVED"],
        )
    else:
        result = tx.run(
            """
            MERGE (p:Person {linkedin_url: $url})
            ON CREATE SET p.name = $name,
                          p.is_first_degree = true,
                          p.first_seen = date($today),
                          p.status = $active,
                          p.title = $title,
                          p.company_name = $company,
                          p.connected_date = $connected,
                          p.url_missing = false
            ON MATCH SET  p.last_seen = date($today),
                          p.name = $name,
                          p.title = $title,
                          p.company_name = $company
            WITH p, p.first_seen = date($today) AS created
            CALL {
                WITH p
                WITH p WHERE p.status = $removed
                SET p.status = $active,
                    p.reactivation_dates = coalesce(p.reactivation_dates, []) + [date($today)],
                    p.removed_date = null
                RETURN 1 AS reactivated
                UNION
                WITH p WHERE p.status <> $removed
                RETURN 0 AS reactivated
            }
            SET p.last_seen = date($today)
            RETURN created, reactivated
            """,
            url=row["linkedin_url"], name=row["name"], company=row["company_name"],
            title=row["title"], connected=row["connected_date"], today=today,
            active=PERSON_STATUS["ACTIVE"], removed=PERSON_STATUS["REMOVED"],
        )

    rec = result.single()
    return {"created": bool(rec["created"]), "reactivated": bool(rec["reactivated"])}


def link_company(tx, row):
    if not row["company_name"]:
        return
    if row["url_missing"]:
        tx.run(
            """
            MATCH (p:Person {name:$name, company_name:$company, url_missing:true})
            MERGE (c:Company {name:$company})
            MERGE (p)-[:WORKS_AT]->(c)
            """,
            name=row["name"], company=row["company_name"],
        )
    else:
        tx.run(
            """
            MATCH (p:Person {linkedin_url:$url})
            MERGE (c:Company {name:$company})
            MERGE (p)-[:WORKS_AT]->(c)
            """,
            url=row["linkedin_url"], company=row["company_name"],
        )


def link_owner_knows(tx, row):
    if row["url_missing"]:
        tx.run(
            """
            MATCH (me:Person {name:$owner})
            MATCH (p:Person {name:$name, company_name:$company, url_missing:true})
            MERGE (me)-[:KNOWS]->(p)
            """,
            owner=OWNER_CANONICAL_NAME, name=row["name"], company=row["company_name"],
        )
    else:
        tx.run(
            """
            MATCH (me:Person {name:$owner})
            MATCH (p:Person {linkedin_url:$url})
            MERGE (me)-[:KNOWS]->(p)
            """,
            owner=OWNER_CANONICAL_NAME, url=row["linkedin_url"],
        )


def mark_removed(tx, incoming_urls, incoming_composite_keys, today):
    """Anything in graph as is_first_degree but not in this CSV -> removed."""
    result = tx.run(
        """
        MATCH (me:Person {name:$owner})-[:KNOWS]->(p:Person)
        WHERE p.status = $active
          AND coalesce(p.is_owner, false) = false
          AND (
                (p.url_missing = false AND NOT p.linkedin_url IN $urls)
             OR (p.url_missing = true  AND NOT (p.name + '||' + p.company_name) IN $composites)
          )
        SET p.status = $removed, p.removed_date = date($today)
        RETURN collect(coalesce(p.linkedin_url, p.name)) AS removed
        """,
        owner=OWNER_CANONICAL_NAME, urls=list(incoming_urls),
        composites=list(incoming_composite_keys),
        active=PERSON_STATUS["ACTIVE"], removed=PERSON_STATUS["REMOVED"], today=today,
    )
    return result.single()["removed"]


def write_changelog(tx, run_date, source_file, added, removed, unchanged, reactivated):
    tx.run(
        """
        CREATE (l:ConnectionChangeLog {
            run_date: date($run_date),
            source_file: $source_file,
            added_count: $added_count,
            removed_count: $removed_count,
            unchanged_count: $unchanged_count,
            reactivated_count: $reactivated_count,
            added_keys: $added_keys,
            removed_keys: $removed_keys
        })
        """,
        run_date=run_date, source_file=source_file,
        added_count=len(added), removed_count=len(removed),
        unchanged_count=unchanged, reactivated_count=len(reactivated),
        added_keys=added, removed_keys=removed,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["initial", "update"], default="update")
    parser.add_argument("--file", type=str, default=None,
                        help="Override: process this file instead of inbox/")
    args = parser.parse_args()

    apply_schema()

    src = Path(args.file) if args.file else find_inbox_file()
    today = date.today().isoformat()

    # Snapshot first — immutable archive
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    snapshot_path = SNAPSHOTS / f"connections_{today}.csv"
    shutil.copy2(src, snapshot_path)
    print(f"Snapshotted -> {snapshot_path.name}")

    df = read_linkedin_csv(src)
    rows = normalize_rows(df)
    print(f"Parsed {len(rows)} rows ({sum(1 for r in rows if r['url_missing'])} missing URL)")

    incoming_urls = {r["linkedin_url"] for r in rows if not r["url_missing"]}
    incoming_composite = {f"{r['name']}||{r['company_name']}" for r in rows if r["url_missing"]}

    added, reactivated = [], []

    with session() as s:
        s.execute_write(ensure_owner)

        for row in rows:
            result = s.execute_write(upsert_person, row, today)
            s.execute_write(link_company, row)
            s.execute_write(link_owner_knows, row)
            key = row["linkedin_url"] or f"{row['name']}||{row['company_name']}"
            if result["created"]:
                added.append(key)
            if result["reactivated"]:
                reactivated.append(key)

        removed = s.execute_write(mark_removed, incoming_urls, incoming_composite, today)
        unchanged = len(rows) - len(added) - len(reactivated)

        s.execute_write(
            write_changelog, today, src.name, added, removed, unchanged, reactivated
        )

    # Move processed file to archive — clears inbox
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    archive_path = ARCHIVE / f"{src.stem}_{today}{src.suffix}"
    shutil.move(str(src), archive_path)

    print()
    print(f"  added:       {len(added)}")
    print(f"  removed:     {len(removed)}")
    print(f"  reactivated: {len(reactivated)}")
    print(f"  unchanged:   {unchanged}")
    print(f"  archived ->  {archive_path.name}")


if __name__ == "__main__":
    main()
