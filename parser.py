"""
LinkedIn Sales Navigator paste parser.

Input: raw text copied from a Navigator connection list page.
Output: list of parsed people with type flags and resolved/unresolved mutuals.

Heuristics are intentionally forgiving — Navigator's HTML-to-text varies.
The Streamlit UI lets you confirm/correct each result before committing.
"""
import re
from pathlib import Path

import yaml
from rapidfuzz import fuzz

from constants import OWNER_ALIASES, OWNER_CANONICAL_NAME, OWNER_FUZZY_THRESHOLD

KEYWORDS = yaml.safe_load((Path(__file__).parent / "keywords.yaml").read_text())


def _has_any(text: str, terms: list[str]) -> bool:
    t = text.lower()
    return any(term.lower() in t for term in terms)


def classify(title: str, company: str) -> list[str]:
    """Return all matching type flags."""
    blob = f"{title} {company}".lower()
    flags = []
    if _has_any(blob, KEYWORDS["banker"]):
        flags.append("banker")
    if _has_any(blob, KEYWORDS["cepa"]):
        flags.append("cepa")
    if _has_any(blob, KEYWORDS["manufacturer_titles"]) and _has_any(blob, KEYWORDS["manufacturer_industries"]):
        flags.append("manufacturer")
    if _has_any(blob, KEYWORDS["chamber"]):
        flags.append("chamber")
    if _has_any(blob, KEYWORDS["supply_chain"]):
        flags.append("supply_chain")
    if not flags:
        flags.append("other")
    return flags


# --- Block parser ---------------------------------------------------------
# Navigator paste shape (typical):
#
#   Jane Doe
#   Senior Vice President at Acme Corp
#   Greater Kansas City Area
#   12 mutual connections including John Smith, Patrick McDonald
#
# Blocks are separated by blank lines OR by the next name line.

NAME_LINE = re.compile(r"^[A-Z][A-Za-z.\-']+(?:\s+[A-Z][A-Za-z.\-']+){1,4}(?:,\s*[A-Z]+)?$")
MUTUALS_RE = re.compile(r"(\d+)\s+mutual connections?(?:\s+including\s+(.+))?", re.IGNORECASE)
TITLE_AT_RE = re.compile(r"^(.*?)\s+at\s+(.*)$", re.IGNORECASE)


def _split_blocks(text: str) -> list[list[str]]:
    blocks, current = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def parse_paste(text: str) -> list[dict]:
    results = []
    for block in _split_blocks(text):
        if len(block) < 2:
            continue
        name = block[0]
        if not NAME_LINE.match(name):
            continue

        title, company, location = "", "", ""
        mutual_count, mutuals = 0, []

        for line in block[1:]:
            mm = MUTUALS_RE.search(line)
            if mm:
                mutual_count = int(mm.group(1))
                if mm.group(2):
                    mutuals = [m.strip() for m in re.split(r",| and ", mm.group(2)) if m.strip()]
                continue
            tm = TITLE_AT_RE.match(line)
            if tm and not title:
                title, company = tm.group(1).strip(), tm.group(2).strip()
                continue
            if not title:
                title = line
                continue
            if not location:
                location = line

        results.append({
            "name": name,
            "title": title,
            "company": company,
            "location": location,
            "mutual_count": mutual_count,
            "mutual_names": mutuals,
            "flags": classify(title, company),
        })
    return results


# --- Owner alias matching -------------------------------------------------

def is_owner_alias(name: str) -> bool:
    n = name.lower().strip()
    if n in OWNER_ALIASES:
        return True
    for alias in OWNER_ALIASES:
        if fuzz.ratio(n, alias) >= OWNER_FUZZY_THRESHOLD:
            return True
    return False


def resolve_mutual(name: str, existing_names: set[str]) -> str | None:
    """Exact match for everyone except owner; fuzzy only for owner aliases."""
    if is_owner_alias(name):
        return OWNER_CANONICAL_NAME
    return name if name in existing_names else None
