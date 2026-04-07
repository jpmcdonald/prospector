---
name: Per-workspace Python venv
overview: Your script can work per-repo, but reliability breaks when (a) the interpreter used to create the venv differs from the one agents/IDE use, (b) tooling never loads your shell hook, and (c) the repo does not declare a Python version. Prefer **mechanical** binding (pinned version, `.venv`, editor settings, small scripts) over prose; **Cursor rules / AGENTS.md help sometimes but are model- and session-dependent**—treat them as optional hints, not guarantees. Same repo may be opened in **Cursor and Claude Code**; both benefit from the same on-disk conventions.
todos:
  - id: pin-python
    content: "Choose pin mechanism: .python-version (pyenv/asdf) and/or pyproject.toml requires-python"
    status: pending
  - id: standard-venv
    content: Standardize on project-root .venv; create with explicit python3.x -m venv
    status: pending
  - id: vscode-interpreter
    content: Add .vscode/settings.json with python.defaultInterpreterPath -> ${workspaceFolder}/.venv/bin/python (Cursor + VS Code family)
    status: pending
  - id: agent-hint
    content: "Optional: minimal AGENTS.md / .cursor/rules as reminders—do not rely on them alone; adherence varies by model and product"
    status: pending
  - id: script-entrypoint
    content: "Optional: Makefile or scripts/bootstrap.sh with explicit brew/python path for humans and agents that run commands"
    status: pending
  - id: optional-uv
    content: Optionally adopt uv for venv + pip installs on fresh machines
    status: pending
---

# Per-workspace Python environments (post-rebuild)

## Why README + a personal activate script often “fails”

- **README is not machine-readable.** Agents and some tools do not load it before picking `python`/`python3`; even humans skip it.
- **Your script only fixes shells where you explicitly source it.** Cursor agent terminals, tasks, and CI often start **without** your `~/.zprofile` extras or without sourcing your project script—so they fall back to **whatever `python3` is first on PATH** (often `/usr/bin/python3`), which may differ from the interpreter that created the venv.
- **Mixed interpreters.** If a venv was created with Homebrew 3.13 but a session runs `/usr/bin/python3`, you get confusing “wrong venv” or package-not-found behavior.
- **Non-standard venv name** (`vWairenv`) is fine *if* it lives under the project root (your script does that), but **editors and many tools auto-detect `.venv`** in the workspace root and ignore custom names unless configured.

So the issue is less “the script is wrong” and more “nothing in the repo **binds** the workspace to one interpreter.”

## A better default pattern (Cursor, Claude Code, and plain terminal)

Principle: **anything an LLM might skip should still be true on disk**—standard layout, pinned version, and one obvious command path.

1. **One venv per repo at the workspace root: `.venv/`**  
   Matches what [README.md](../../README.md) already suggests (`python -m venv .venv`). Editors and many extensions look here first. **Claude Code and Cursor** both behave more predictably when the venv is where convention expects it.

2. **Pin the Python version in the repo** (pick one mechanism):
   - **`.python-version`** with a single line, e.g. `3.13.2`, if you use **pyenv** or **asdf** with python plugin—`cd` into the repo and tools select that version.
   - Or **`pyproject.toml`** with `[project] requires-python = ">=3.12,<3.14"` (even before full packaging)—modern tooling and humans see one declared range.

3. **Lock workspace interpreter for VS Code–family editors** (reduces guessing when the agent uses the embedded terminal):
   - Add `.vscode/settings.json` in the repo (or user settings) with:
     - `"python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python"`
   - After creating `.venv`, select that interpreter once in the palette; the path above makes it stick for the folder.

4. **One explicit command to recreate from scratch** (README + optional `Makefile` / `scripts/bootstrap.sh`):
   - `cd /path/to/repo && python3.13 -m venv .venv && source .venv/bin/activate && pip install -U pip && pip install -r requirements.txt`  
   Use an **explicit** `python3.13` (or full path from `brew --prefix python@3.13`) when creating the venv so PATH ambiguity goes away. A **named script target** (e.g. `make venv` or `./scripts/bootstrap.sh`) gives agents a single string to run instead of inferring steps.

## Optional: faster, more reproducible installs

- **`uv`** ([Astral](https://github.com/astral-sh/uv)): `uv venv --python 3.13` then `uv pip install -r requirements.txt`—very fast on a rebuilt Mac; can still use `.venv`.

## Agent-facing docs (helpful, not dependable)

**Reality check:** In Cursor, **`.cursor/rules` and `AGENTS.md` are soft hints**. Different models and sessions may ignore or partially apply them. Claude Code has its own conventions; neither stack treats these files like a compiler reading `pyproject.toml`.

So:

- **Do still add** a short `AGENTS.md` or rule if you want a quick reminder when a model *does* load context—but **rank it below** `.venv` + pin + `.vscode/settings.json` + optional `Makefile`/`bootstrap.sh`.
- **Cross-tool win:** The same `.venv` path and `requires-python` help **whichever** product you open tomorrow.

Duplicating one line of setup in README + a script target is often more reliable than duplicating prose into rules alone.

## Your existing bash script

Keep it if you like, but for fewer surprises:

- Point it at **`.venv`** (or set `VENV_NAME=".venv"`) so it matches editor defaults.
- Use **`python3.13 -m venv`** (or `$(brew --prefix python@3.13)/bin/python3 -m venv`) instead of bare `python3`.
- Know that **sourcing the script is not enough for agent terminals** unless you also set workspace interpreter (where applicable) and/or run commands through an explicit **`./.venv/bin/python`** when instructing tools.

## Prospector-specific note

Repo is **early**; only requirements + README today. Highest leverage for “wrong Python” prevention: **pin + `.venv` + `.vscode/settings.json` + one bootstrap command** (Makefile or script). Optional rules/`AGENTS.md` last—not because they are useless, but because **adherence is inconsistent** across models and between Cursor and Claude Code.
