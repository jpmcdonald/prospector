"""
Streamlit UI — three tabs:
  1. Target Dashboard
  2. Path Finder (paste parser)
  3. Referral Partners
"""
import pandas as pd
import streamlit as st

from constants import (
    ICP_TIERS, OWNER_CANONICAL_NAME, PATH_TYPE_VALUES,
    TARGET_STATUS, TARGET_STATUS_VALUES,
)
from db import session
from parser import parse_paste, resolve_mutual

st.set_page_config(page_title="KC Prospector", layout="wide")


# --- Query helpers --------------------------------------------------------

def q_targets() -> pd.DataFrame:
    cypher = """
    MATCH (c:Company)-[:IS_TARGET]->(t:Target)
    OPTIONAL MATCH path = (me:Person {name:$owner})-[:KNOWS|BRIDGES_TO*1..4]->(p:Person)-[:WORKS_AT]->(c)
    WITH c, t, path, p
    ORDER BY length(path) ASC
    WITH c, t, collect({bridge: p.name, hops: length(path)})[0] AS best
    RETURN c.name AS company,
           c.industry AS industry,
           c.est_revenue_range AS est_revenue,
           c.icp_tier AS tier,
           t.status AS status,
           t.notes AS notes,
           best.bridge AS bridge_person,
           best.hops AS hops
    ORDER BY c.icp_tier, c.name
    """
    with session() as s:
        return pd.DataFrame([r.data() for r in s.run(cypher, owner=OWNER_CANONICAL_NAME)])


def q_warm_paths(company: str) -> pd.DataFrame:
    cypher = """
    MATCH path = (me:Person {name:$owner})-[:KNOWS|BRIDGES_TO*1..4]->(p:Person)-[:WORKS_AT]->(c:Company {name:$company})
    RETURN [n IN nodes(path) | n.name] AS chain, length(path) AS hops
    ORDER BY hops ASC
    LIMIT 10
    """
    with session() as s:
        return pd.DataFrame([r.data() for r in s.run(cypher, owner=OWNER_CANONICAL_NAME, company=company)])


def q_referral_partners() -> pd.DataFrame:
    cypher = """
    MATCH (p:Person)
    WHERE EXISTS {
      MATCH (p)-[r:BRIDGES_TO]->()
      WHERE r.path_type IN ['banker','cepa','chamber']
    } OR p.title =~ '(?i).*(SVP|exit planning|CEPA|chamber|vistage).*'
    OPTIONAL MATCH (p)-[:BRIDGES_TO*1..3]->(:Person)-[:WORKS_AT]->(c:Company)-[:IS_TARGET]->()
    RETURN p.name AS name, p.title AS title, p.company_name AS company,
           p.status AS status,
           count(DISTINCT c) AS targets_bridged
    ORDER BY targets_bridged DESC, p.name
    """
    with session() as s:
        return pd.DataFrame([r.data() for r in s.run(cypher)])


def q_existing_names() -> set[str]:
    with session() as s:
        return {r["name"] for r in s.run("MATCH (p:Person) RETURN p.name AS name")}


def q_recent_changelogs(limit=4) -> pd.DataFrame:
    cypher = """
    MATCH (l:ConnectionChangeLog)
    RETURN l.run_date AS run_date, l.added_count AS added,
           l.removed_count AS removed, l.unchanged_count AS unchanged,
           l.reactivated_count AS reactivated, l.source_file AS source
    ORDER BY l.run_date DESC LIMIT $limit
    """
    with session() as s:
        return pd.DataFrame([r.data() for r in s.run(cypher, limit=limit)])


# --- Mutations ------------------------------------------------------------

def add_target(company, industry, revenue, tier, notes):
    cypher = """
    MERGE (c:Company {name:$company})
    ON CREATE SET c.industry=$industry, c.est_revenue_range=$revenue, c.icp_tier=$tier
    MERGE (t:Target {company_name:$company})
    ON CREATE SET t.status=$status, t.notes=$notes
    MERGE (c)-[:IS_TARGET]->(t)
    """
    with session() as s:
        s.run(cypher, company=company, industry=industry, revenue=revenue, tier=tier,
              status=TARGET_STATUS["NO_PATH"], notes=notes)


def add_parsed_person(name, title, company, location, flags, mutual_names,
                      target_company, path_type, notes, bridges_via):
    """Create the Person, WORKS_AT, and BRIDGES_TO from selected via-person."""
    create_person = """
    MERGE (p:Person {name:$name})
    ON CREATE SET p.title=$title, p.company_name=$company, p.location=$location,
                  p.flags=$flags, p.mutual_connection_names=$mutuals,
                  p.url_missing=true
    ON MATCH SET  p.title=coalesce(p.title,$title),
                  p.company_name=coalesce(p.company_name,$company)
    WITH p
    MERGE (c:Company {name:$company})
    MERGE (p)-[:WORKS_AT]->(c)
    """
    with session() as s:
        s.run(create_person, name=name, title=title, company=company, location=location,
              flags=flags, mutuals=mutual_names)

        if bridges_via:
            s.run(
                """
                MATCH (a:Person {name:$via}), (b:Person {name:$name})
                MERGE (a)-[r:BRIDGES_TO]->(b)
                ON CREATE SET r.path_type=$ptype, r.notes=$notes, r.date_added=date()
                """,
                via=bridges_via, name=name, ptype=path_type, notes=notes,
            )

        if target_company:
            s.run(
                """
                MATCH (p:Person {name:$name})
                MERGE (c:Company {name:$target})
                MERGE (t:Target {company_name:$target})
                ON CREATE SET t.status=$status
                MERGE (c)-[:IS_TARGET]->(t)
                MERGE (p)-[:WORKS_AT]->(c)
                """,
                name=name, target=target_company, status=TARGET_STATUS["PATH_IDENTIFIED"],
            )


# --- UI -------------------------------------------------------------------

tab1, tab2, tab3 = st.tabs(["Target Dashboard", "Path Finder", "Referral Partners"])

# ============== Tab 1 ==============
with tab1:
    st.header("Target Dashboard")

    with st.expander("Network Changes (last 4 runs)"):
        logs = q_recent_changelogs()
        if logs.empty:
            st.caption("No CSV loads yet.")
        else:
            st.dataframe(logs, use_container_width=True, hide_index=True)

    with st.expander("Add Target"):
        with st.form("add_target"):
            c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
            t_name = c1.text_input("Company")
            t_industry = c2.text_input("Industry")
            t_revenue = c3.text_input("Est revenue")
            t_tier = c4.selectbox("ICP tier", ICP_TIERS)
            t_notes = st.text_area("Notes", height=68)
            if st.form_submit_button("Add"):
                if t_name:
                    add_target(t_name, t_industry, t_revenue, t_tier, t_notes)
                    st.success(f"Added {t_name}")
                    st.rerun()

    df = q_targets()
    if df.empty:
        st.info("No targets yet — add one above.")
    else:
        with st.sidebar:
            st.subheader("Filter")
            f_tier = st.multiselect("Tier", ICP_TIERS, default=ICP_TIERS)
            f_status = st.multiselect("Status", TARGET_STATUS_VALUES, default=TARGET_STATUS_VALUES)
        view = df[df["tier"].isin(f_tier) & df["status"].isin(f_status)]
        st.dataframe(view, use_container_width=True, hide_index=True)

        sel = st.selectbox("Inspect warm paths to:", [""] + view["company"].tolist())
        if sel:
            paths = q_warm_paths(sel)
            if paths.empty:
                st.warning(f"No warm path to {sel} yet.")
            else:
                for _, row in paths.iterrows():
                    st.write(f"**{row['hops']} hops:** " + " → ".join(row["chain"]))

# ============== Tab 2 ==============
with tab2:
    st.header("Path Finder")
    st.caption("Paste raw text from a LinkedIn Sales Navigator connection page.")

    raw = st.text_area("Navigator paste", height=250, key="paste_box")

    if st.button("Parse"):
        st.session_state["parsed"] = parse_paste(raw)
        st.session_state["existing_names"] = q_existing_names()

    parsed = st.session_state.get("parsed", [])
    existing = st.session_state.get("existing_names", set())

    targets_df = q_targets()
    target_options = [""] + (targets_df["company"].tolist() if not targets_df.empty else [])

    for i, person in enumerate(parsed):
        with st.container(border=True):
            cA, cB = st.columns([3, 2])
            with cA:
                flag_str = ", ".join(person["flags"])
                st.markdown(f"**{person['name']}** — _{flag_str}_")
                st.caption(f"{person['title']} @ {person['company']}  ·  {person['location']}")
                st.caption(f"{person['mutual_count']} mutual connections")
                if person["mutual_names"]:
                    chips = []
                    for m in person["mutual_names"]:
                        resolved = resolve_mutual(m, existing)
                        chips.append(f":green[{resolved}]" if resolved else f":gray[{m}]")
                    st.markdown("Mutuals: " + " · ".join(chips))

            with cB:
                tgt = st.selectbox("Target", target_options, key=f"tgt_{i}")
                ptype = st.selectbox("Path type", PATH_TYPE_VALUES, key=f"pt_{i}")
                via_options = [""] + sorted(existing)
                via = st.selectbox("Bridges via (existing person)", via_options, key=f"via_{i}")
                notes = st.text_input("Notes", key=f"n_{i}")
                if st.button("Add to graph", key=f"btn_{i}"):
                    add_parsed_person(
                        person["name"], person["title"], person["company"],
                        person["location"], person["flags"], person["mutual_names"],
                        tgt or None, ptype, notes, via or None,
                    )
                    st.success(f"Added {person['name']}")

# ============== Tab 3 ==============
with tab3:
    st.header("Referral Partners")
    df = q_referral_partners()
    if df.empty:
        st.info("No referral partners flagged yet.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
