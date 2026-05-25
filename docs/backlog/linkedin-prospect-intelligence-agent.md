# Backlog Item: LinkedIn Prospect Intelligence Agent

## Feature Summary

Extend the existing LinkedIn connections tracker to ingest weekly LinkedIn archive exports (including message history) and run an agentic prospect scoring and outreach drafting workflow. The agent evaluates contacts against a configurable sales strategy profile and produces prioritized outreach recommendations with AI-drafted messages.

---

## Context

The existing system loads LinkedIn connection data and updates weekly. This feature adds two capabilities:

1. **Message history ingestion** — Parse the LinkedIn archive `messages.csv` (or equivalent) alongside the existing connections data to build a unified contact record that includes last message date, message thread summary, and relationship warmth signals.

2. **Prospect intelligence agent** — An agentic job that runs on each weekly update, scores contacts against a configurable prospect profile, tiers them, and drafts personalized outreach messages for the top N contacts.

---

## LinkedIn Archive Structure

LinkedIn's archive export (requested via Settings → Data Privacy → Get a copy of your data) includes:

- `Connections.csv` — name, company, title, connected date (already in use)
- `messages.csv` — conversation threads with timestamps, participants, and message bodies
- `Profile.csv` — user's own profile snapshot

The agent should join `messages.csv` to `Connections.csv` on name/profile URL to enrich each contact record with:

- `last_message_date` — most recent message in either direction
- `last_message_direction` — inbound or outbound
- `message_count` — total messages exchanged
- `thread_summary` — brief AI-generated summary of the conversation context

---

## Prospect Scoring Logic

The agent should score each contact against the following configurable criteria. Store the scoring profile in a config file (e.g., `prospect_profile.yaml`) so it can be updated without code changes.

### Current Prospect Profile (v1)

**Target relationship types** (in priority order):

1. Potential consulting client — manufacturing, supply chain, retail, insurance, financial services, healthcare
2. Channel partner — consulting firms (Protiviti, Deloitte, Accenture, IBM, TCS, Sogeti), fractional executives, MSPs
3. Design partner / LOI candidate — AI product companies deploying autonomous agents, agentic workflows, or security automation
4. Strategic partner — sovereign AI infrastructure, cybersecurity platforms, governance-adjacent products
5. Talent / future hire — data science, AI engineering, supply chain analytics backgrounds
6. Investor candidate — angels, family offices, fintech/AI-focused funds

**Scoring signals** (weighted, configurable):

| Signal | Weight | Notes |
|--------|--------|-------|
| Title match to target profile | High | CTO, CIO, CISO, CAO, MD, SVP, VP, Partner, Founder |
| Industry match | High | Manufacturing, supply chain, insurance, financial services, healthcare, cybersecurity, defense |
| Warmth tier | High | Monthly contact > quarterly > annual > cold |
| Last message recency | Medium | <3 months, 3-12 months, 1-3 years, 3+ years |
| Message history depth | Medium | 10+ messages = strong signal; 0 = cold |
| Mutual context signal | Medium | Shared employer, shared project, mentee/mentor, hired by |
| Company size / type | Low | Enterprise, mid-market, startup, government, university |
| Geographic relevance | Low | KC local = higher for in-person; remote = neutral |

**Output tiers:**

- **Tier 1 — Activate this week**: High score, warm relationship, clear strategic fit
- **Tier 2 — Warm touchpoint this month**: Medium score, dormant but recoverable
- **Tier 3 — Slow burn**: Lower score or cold, worth a personalized message quarterly
- **Tier 4 — Monitor**: No clear fit yet; watch for role changes or trigger events

---

## Outreach Drafting

For all Tier 1 and Tier 2 contacts identified in a given weekly run, the agent should draft a short personalized outreach message using the following constraints:

**Message guidelines:**

- 3-5 sentences maximum
- Lead with genuine reference to shared history or recent activity (use thread summary and/or profile data)
- One sentence on what Patrick is building — AI governance infrastructure and/or supply chain consulting — framed as relevant to the contact's world, not as a pitch
- Soft close — "worth a conversation" or "would love to reconnect" — no hard ask
- Do not mention Almynex by name in cold or semi-warm outreach
- Tone: peer-to-peer, confident, not salesy

**Message context inputs per contact:**

- Name, current title, current company
- Shared history (employer overlap, project, mentee relationship)
- Thread summary from message history
- Last contact date and direction
- Tier assignment and reason

**Output format per contact:**

```
### [Full Name] — [Title] @ [Company]
**Tier**: 1 / 2 / 3
**Reason**: [1-2 sentence rationale for tier assignment]
**Last contact**: [date and direction]
**Shared context**: [brief note on relationship history]
**Suggested message**:
[drafted outreach]
```

---

## Agent Job Design

**Trigger**: Weekly, on LinkedIn archive upload/refresh

**Steps:**

1. Parse and join `Connections.csv` + `messages.csv` into unified contact records
2. For each contact, compute prospect score against current `prospect_profile.yaml`
3. Assign tier
4. For Tier 1 and Tier 2 contacts not contacted in the last 30 days, draft outreach message
5. Output a ranked prospect report (markdown or UI view) sorted by tier then score
6. Flag contacts with recent inbound messages that have not been replied to — these are highest priority regardless of tier

**Configurable parameters:**

- `outreach_per_week` — max number of Tier 1/2 drafts to generate (default: 35, i.e., 5/day × 7 days)
- `recontact_cooldown_days` — minimum days between outreach attempts per contact (default: 30)
- `prospect_profile_path` — path to scoring config YAML
- `archive_path` — path to LinkedIn archive export folder

---

## Data Model Extensions

Add the following fields to the existing contact/connection record:

```
last_message_date: date
last_message_direction: enum [inbound, outbound, none]
message_count: int
thread_summary: str
prospect_score: float
prospect_tier: enum [1, 2, 3, 4]
tier_reason: str
last_outreach_date: date
outreach_count: int
do_not_contact: bool
notes: str  # manual override field
```

---

## Implementation Notes

- Use Claude API (claude-sonnet-4-20250514) for thread summarization and outreach drafting — pass thread content plus contact metadata in a single prompt per contact
- Batch API calls where possible to manage token cost — summarization and drafting can be combined in one prompt
- Store prospect scores and tier assignments in the local database alongside connection records so history is preserved week-over-week
- Trend tracking: flag contacts who have moved up or down a tier since last week
- Role change detection: if title or company has changed since last archive load, flag for manual review — role changes are high-value outreach triggers

---

## Out of Scope (v1)

- Automated sending — Patrick reviews and sends manually
- LinkedIn API integration — archive export is the data source
- Email or CRM sync
- Multi-user support

---

## Acceptance Criteria

- [ ] `messages.csv` parsed and joined to connection records on weekly archive load
- [ ] Prospect scoring runs automatically on each weekly refresh
- [ ] Tier assignments stored and trended week-over-week
- [ ] Outreach drafts generated for all Tier 1/2 contacts within cooldown window
- [ ] Output report is readable and actionable — copy/paste ready
- [ ] Scoring profile is configurable via YAML without code changes
- [ ] Inbound unreplied messages flagged as highest priority
- [ ] Role change detection flags contacts for manual review
