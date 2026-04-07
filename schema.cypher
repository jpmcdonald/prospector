// Constraints and indexes for the prospector graph.
// Safe to re-run.

CREATE CONSTRAINT person_url IF NOT EXISTS
FOR (p:Person) REQUIRE p.linkedin_url IS UNIQUE;

CREATE CONSTRAINT company_name IF NOT EXISTS
FOR (c:Company) REQUIRE c.name IS UNIQUE;

CREATE INDEX person_name IF NOT EXISTS
FOR (p:Person) ON (p.name);

CREATE INDEX person_status IF NOT EXISTS
FOR (p:Person) ON (p.status);

CREATE INDEX target_status IF NOT EXISTS
FOR (t:Target) ON (t.status);
