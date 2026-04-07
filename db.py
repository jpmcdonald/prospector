"""Neo4j driver singleton + schema bootstrap."""
import os
from pathlib import Path
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7688")
USER = os.getenv("NEO4J_USER", "patrick")
PASSWORD = os.getenv("NEO4J_PASSWORD", "")

_driver = None


def driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    return _driver


def session():
    return driver().session()


def apply_schema():
    schema_file = Path(__file__).parent / "schema.cypher"
    statements = [s.strip() for s in schema_file.read_text().split(";") if s.strip() and not s.strip().startswith("//")]
    with session() as s:
        for stmt in statements:
            s.run(stmt)


if __name__ == "__main__":
    apply_schema()
    print("Schema applied.")
