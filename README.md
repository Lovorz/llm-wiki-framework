# LLM Wiki Framework

A multi-agent research intelligence pipeline that converts research questions into structured, persistent knowledge. Built on Mistral AI for OCR, embeddings, and LLM reasoning — with an Obsidian vault as the knowledge base.

> *"The researcher's job is not to read papers. It is to build understanding."*

---

## Overview

This framework separates **pipeline code** from **vault data**, so one installation serves multiple research vaults.

**4-Tier Memory Model:**

```
raw/        ← Immutable source PDFs (read-only)
log/        ← Raw OCR extractions (temporary)
wiki/       ← Structured knowledge pages with claims[] (permanent)
handoffs/   ← Inter-agent communication (pipeline artifacts)
```

The pipeline ingests PDFs, extracts structured claims using LLM, then runs an 8-agent research pipeline against your knowledge base to answer research questions with gap analysis, strategy, and audit.

---

## Pipeline Flow

```
Research Question
      │
      ▼
   [Dao]  ─── Multi-hop graph search over wiki/
      │        Identifies gaps, proposes sources
      │
  ╔══ CP1 ══╗  Approve source plan
      │
      ▼
 [Builder]  ─── Mistral OCR on raw/ PDFs → log/
      │          Auto-promotes log/ → wiki/ with LLM claims
      │
      ▼
 [Cherry]  ──── Reads claims[] from wiki/ frontmatter
      │          Blind-spot sweep against Dao's analysis
      │
      ▼
   [Nam]  ────  Synthesizes strategy, proposes research directions
      │
  ╔══ CP2 ══╗  Select directions to focus on
      │
      ▼
[Som ║ Manao]  ─── Parallel audit (logic + fact)
      │              Silent revision loop (up to 2 retries)
      │
      ▼
   [Mod]  ────  Extracts atomic insights, marks stale knowledge
      │          Writes to wiki/concepts/
      │
  ╔══ CP3 ══╗  Choose output format: report / marp / obsidian
      │
      ▼
  [Nanny]  ───  Generates final deliverable
                Archives full mission_YYYYMMDD_HHMM.md
```

---

## Agent Roles

| Agent | Role | Output |
|-------|------|--------|
| **Dao** | Multi-hop graph search, gap analysis, source discovery | `handoff_dao.md` |
| **Builder** | Mistral OCR extraction, wiki promotion | `handoff_builder.md` |
| **Cherry** | Claims-based blind-spot sweep | `handoff_cherry.md` |
| **Nam** | Research strategy synthesis, 5 directions | `handoff_nam.md` |
| **Som** | Logic audit — checks internal consistency | `handoff_audit.md` |
| **Manao** | Fact audit — cross-checks against wiki evidence | `handoff_audit.md` |
| **Mod** | Atomic insight extraction, contradiction resolution | `handoff_mod.md` |
| **Nanny** | Final report generation, mission file archiving | `handoff_nanny.md` |

---

## Key Features

- **Multi-hop Graph Search** — Cosine similarity + wikilink traversal (2 hops). Pages reachable from relevant seeds get a connectivity bonus, surfacing conceptually adjacent knowledge even without keyword matches.
- **Structured Claims** — Each wiki page stores 30–50 LLM-extracted claims in YAML frontmatter (`claims[]`), categorized as RESULT / TABLE / METHOD / MECHANISM / COMPARISON. Cherry reads these directly for token efficiency.
- **Contradiction Resolution** — Mod compares new insights against existing wiki pages and marks superseded claims as `stale: true`.
- **Audit Trail** — Every pipeline operation is logged to `wiki/.audit-log.md` with timestamp, agent, and details.
- **Parallel Auditing** — Som and Manao run concurrently. Silent revision loop retries Nam before interrupting the user.
- **Multi-vault Support** — One pipeline installation, many vaults. The pipeline operates on the current working directory.

---

## Prerequisites

- Python 3.9+
- **Mistral AI API key** — for OCR, embeddings, and LLM calls ([mistral.ai](https://mistral.ai))
- Obsidian (optional, for vault visualization)

---

## Installation

```bash
# Clone the pipeline code
git clone https://github.com/Lovorz/llm-wiki-framework.git
cd llm-wiki-framework
pip install requests numpy pyyaml

# Store your API key permanently
echo 'export MISTRAL_API_KEY="your-key-here"' >> ~/.bash_env
echo 'export BASH_ENV="$HOME/.bash_env"' >> ~/.profile

# Add the orchestrator command to PATH
cat > ~/.local/bin/orchestrator << 'EOF'
#!/usr/bin/env bash
PIPELINE_HOME="/path/to/llm-wiki-framework"
exec python "$PIPELINE_HOME/scripts/orchestrator.py" "$@"
EOF
chmod +x ~/.local/bin/orchestrator
```

---

## Setting Up a Vault

Each vault is just a directory with `raw/` and `wiki/` folders:

```bash
mkdir my-research-vault
cd my-research-vault
mkdir raw wiki log handoffs
```

Copy your PDFs into `raw/`, then build the knowledge base:

```bash
# Step 1 — OCR extract PDFs: raw/ → log/
python /path/to/llm-wiki-framework/scripts/wiki_manager.py ingest

# Step 2 — LLM promote with claim extraction: log/ → wiki/
python /path/to/llm-wiki-framework/scripts/wiki_manager.py promote

# Step 3 — Build semantic vector index
python /path/to/llm-wiki-framework/scripts/wiki_manager.py index-vectors

# Step 4 — Run the pipeline
orchestrator "Your research question here"
```

---

## Usage

### Running the Pipeline

```bash
cd /path/to/your-vault
orchestrator "What is the role of surface defects in CoOOH for OER activity?"
```

### Knowledge Base Management

```bash
python scripts/wiki_manager.py ingest          # OCR new PDFs → log/
python scripts/wiki_manager.py promote         # LLM extract claims → wiki/
python scripts/wiki_manager.py index-vectors   # Rebuild vector index
python scripts/wiki_manager.py query "search terms"
python scripts/wiki_manager.py categorize      # Rebuild hub pages
```

---

## Project Structure

```
llm-wiki-framework/          ← Pipeline code (shared across vaults)
├── agents/
│   ├── base.py              ← BaseAgent: LLM, embeddings, graph search
│   ├── dao.py               ← Librarian
│   ├── builder.py           ← OCR + auto-promote
│   ├── cherry.py            ← Blind-spot sweep
│   ├── nam.py               ← Strategist
│   ├── som.py               ← Logic auditor
│   ├── manao.py             ← Fact auditor
│   ├── mod.py               ← Distiller
│   └── nanny.py             ← Output writer
└── scripts/
    ├── orchestrator.py      ← Pipeline runner
    └── wiki_manager.py      ← KB management

your-vault/                  ← Vault data (per project)
├── raw/                     ← Source PDFs (read-only)
├── log/                     ← OCR extractions (temporary)
├── wiki/                    ← Knowledge pages with claims[]
│   ├── .vectors.json        ← Semantic index
│   └── concepts/            ← Mod-generated insight pages
└── handoffs/                ← Agent outputs + mission files
    └── mission_YYYYMMDD_HHMM.md
```

---

## Checkpoints

| # | Trigger | User Action |
|---|---------|-------------|
| **CP1** | After Dao | Approve source plan or type `stop` |
| **CP2** | After Nam | Pick direction numbers (e.g. `1,3`) or Enter for all |
| **CP3** | After Mod | Choose format: `report` / `marp` / `obsidian` |

---

## Output Formats

- **report** — Comprehensive technical report with abstract, findings, mechanistic discussion, open questions
- **marp** — Slide deck (Marp-compatible Markdown, ready to present)
- **obsidian** — Wikilink-rich Markdown with callout blocks and Mermaid diagrams

All outputs are archived as `handoffs/mission_YYYYMMDD_HHMM.md` — a complete record of every agent's work for that session.

---

## Built With

- [Mistral AI](https://mistral.ai) — OCR (`mistral-ocr-latest`), LLM (`mistral-large-latest`), embeddings (`mistral-embed`)
- [Obsidian](https://obsidian.md) — Vault visualization and graph view
