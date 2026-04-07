"""Single source of truth for enums and shared constants."""

# Target status values — used in Cypher, Streamlit dropdowns, and parser
TARGET_STATUS = {
    "NO_PATH": "no_path",
    "PATH_IDENTIFIED": "path_identified",
    "CONTACTED": "contacted",
    "GATE1": "gate1",
    "GATE2": "gate2",
}
TARGET_STATUS_VALUES = list(TARGET_STATUS.values())

# BRIDGES_TO path types
PATH_TYPE = {
    "DIRECT": "direct",
    "BANKER": "banker",
    "CEPA": "cepa",
    "CHAMBER": "chamber",
    "OTHER": "other",
}
PATH_TYPE_VALUES = list(PATH_TYPE.values())

# Person status (CDC)
PERSON_STATUS = {
    "ACTIVE": "active",
    "REMOVED": "removed",
}

# ICP tiers
ICP_TIERS = [1, 2, 3]

# Owner identity — fuzzy match only fires for these aliases
OWNER_CANONICAL_NAME = "Patrick McDonald"
OWNER_ALIASES = [
    "patrick mcdonald",
    "j patrick mcdonald",
    "j. patrick mcdonald",
    "jpatrick mcdonald",
    "jp mcdonald",
    "j.p. mcdonald",
    "pat mcdonald",
]
OWNER_FUZZY_THRESHOLD = 90
