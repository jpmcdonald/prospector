"""
Pre-load Persons and BRIDGES_TO from today's session.

Idempotent — uses MERGE everywhere. Safe to re-run.
"""
from datetime import date

from constants import OWNER_CANONICAL_NAME, PATH_TYPE, PERSON_STATUS, TARGET_STATUS
from db import session, apply_schema

TODAY = date.today().isoformat()

# (name, title, company, path_type, bridges_via_name_or_None, is_first_degree)
SEED_PEOPLE = [
    ("Quintin Ostrom", "SVP", "Security Bank of Kansas City", PATH_TYPE["BANKER"], None, False),
    ("Peter Frankel", "SVP", "Central Bank of Kansas City", PATH_TYPE["BANKER"], None, False),
    ("Jason Moxness", "CEPA", "Lenexa", PATH_TYPE["CEPA"], "Peter Frankel", False),
    ("Douglas Ubel", "SVP Supply Chain", "Milbank Manufacturing", PATH_TYPE["DIRECT"], "Quintin Ostrom", False),
    ("Joseph Kessinger", "TIGER 21 Chair KC", "TIGER 21", PATH_TYPE["CHAMBER"], "Quintin Ostrom", False),
    ("Jill McCarthy", "SVP", "KCADC", PATH_TYPE["CHAMBER"], "Quintin Ostrom", False),
    ("Amy Wiehl", "Project Manager", "CST Industries", PATH_TYPE["DIRECT"], None, True),
    ("David Nast", "Vistage Chair", "Vistage", PATH_TYPE["CHAMBER"], None, True),
    ("Michael Flannery", "Vistage Chair", "Vistage", PATH_TYPE["CHAMBER"], None, True),
    ("Joe Beveridge", "Board Member", "Lenexa Chamber", PATH_TYPE["CHAMBER"], None, True),
]

# (target_company, industry, est_revenue_range, icp_tier)
SEED_TARGETS = [
    ("Milbank Manufacturing", "manufacturing", "$50M-$100M", 1),
    ("CST Industries", "manufacturing", "$100M-$250M", 1),
]


def merge_owner(tx):
    tx.run(
        "MERGE (p:Person {name:$name}) "
        "ON CREATE SET p.is_first_degree = true, p.is_owner = true, "
        "              p.status = $active, p.first_seen = date($today)",
        name=OWNER_CANONICAL_NAME, active=PERSON_STATUS["ACTIVE"], today=TODAY,
    )


def merge_person(tx, name, title, company, is_first_degree):
    tx.run(
        """
        MERGE (p:Person {name:$name})
        ON CREATE SET p.title = $title,
                      p.company_name = $company,
                      p.is_first_degree = $first,
                      p.status = $active,
                      p.first_seen = date($today),
                      p.url_missing = true,
                      p.seeded = true
        ON MATCH SET  p.title = coalesce(p.title, $title),
                      p.company_name = coalesce(p.company_name, $company)
        WITH p
        MERGE (c:Company {name:$company})
        MERGE (p)-[:WORKS_AT]->(c)
        """,
        name=name, title=title, company=company, first=is_first_degree,
        active=PERSON_STATUS["ACTIVE"], today=TODAY,
    )


def merge_knows(tx, name):
    tx.run(
        "MATCH (me:Person {name:$owner}), (p:Person {name:$name}) "
        "MERGE (me)-[:KNOWS]->(p)",
        owner=OWNER_CANONICAL_NAME, name=name,
    )


def merge_bridges_to(tx, from_name, to_name, path_type):
    tx.run(
        """
        MATCH (a:Person {name:$from_name}), (b:Person {name:$to_name})
        MERGE (a)-[r:BRIDGES_TO]->(b)
        ON CREATE SET r.path_type = $path_type, r.date_added = date($today)
        """,
        from_name=from_name, to_name=to_name, path_type=path_type, today=TODAY,
    )


def merge_target(tx, company, industry, revenue, tier):
    tx.run(
        """
        MERGE (c:Company {name:$company})
        ON CREATE SET c.industry = $industry, c.est_revenue_range = $revenue, c.icp_tier = $tier
        ON MATCH  SET c.industry = coalesce(c.industry, $industry),
                      c.est_revenue_range = coalesce(c.est_revenue_range, $revenue),
                      c.icp_tier = coalesce(c.icp_tier, $tier)
        MERGE (t:Target {company_name:$company})
        ON CREATE SET t.status = $no_path, t.notes = ''
        MERGE (c)-[:IS_TARGET]->(t)
        """,
        company=company, industry=industry, revenue=revenue, tier=tier,
        no_path=TARGET_STATUS["NO_PATH"],
    )


def main():
    apply_schema()
    with session() as s:
        s.execute_write(merge_owner)

        for name, title, company, _ptype, _via, first in SEED_PEOPLE:
            s.execute_write(merge_person, name, title, company, first)
            if first:
                s.execute_write(merge_knows, name)

        # Bridges
        for name, _t, _c, ptype, via, first in SEED_PEOPLE:
            if via is None and first:
                # First-degree, no intermediate bridge
                continue
            if via is None:
                # Non-first-degree, no via -> bridged from owner directly via type
                s.execute_write(merge_bridges_to, OWNER_CANONICAL_NAME, name, ptype)
            else:
                s.execute_write(merge_bridges_to, via, name, ptype)

        for company, industry, revenue, tier in SEED_TARGETS:
            s.execute_write(merge_target, company, industry, revenue, tier)

    print(f"Seeded {len(SEED_PEOPLE)} people and {len(SEED_TARGETS)} targets.")


if __name__ == "__main__":
    main()
