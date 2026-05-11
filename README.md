# LLM Wiki Framework

A multi-agent research intelligence pipeline that reads your PDF papers, builds a structured knowledge base, and answers research questions with gap analysis, strategy, and audit — all with minimal human input.

> *"The researcher's job is not to read papers. It is to build understanding."*

---

## How It Works (Simple Version)

1. You drop PDF papers into a `raw/` folder
2. The framework reads and understands all of them automatically
3. You ask a research question
4. 8 AI agents work together to find gaps, propose strategies, fact-check each other, and write a final report
5. Everything is saved permanently in an Obsidian vault

---

## Architecture

**4-Tier Memory Model:**

```
raw/       ← Your PDF papers (never modified)
log/       ← Extracted text from OCR (temporary workspace)
wiki/      ← Structured knowledge pages (permanent, grows over time)
handoffs/  ← Agent-to-agent messages + archived session reports
```

**One pipeline, many vaults.** The code lives in one place; each research project gets its own folder with `raw/` and `wiki/`.

---

## Pipeline Flow

```
Your Research Question
        │
        ▼
     [Dao]  ── Searches your knowledge base, identifies what's known vs unknown
        │
   ── CP1 ──  You approve the source list (press Enter or type 'stop')
        │
        ▼
  [Builder]  ── OCR-extracts any new PDFs, adds them to wiki/
        │
        ▼
  [Cherry]   ── Reads structured claims from wiki pages, sweeps for blind spots
        │
        ▼
    [Nam]    ── Synthesizes findings, proposes 5 research directions
        │
   ── CP2 ──  You pick which directions to focus on (e.g. type '1,3' or Enter for all)
        │
        ▼
[Som ║ Manao] ── Logic audit + Fact audit run in parallel
        │         Silent retry if something fails (up to 2 attempts)
        │
        ▼
    [Mod]    ── Extracts atomic insights, marks outdated knowledge as stale
        │
   ── CP3 ──  You choose the output format: report / marp / obsidian
        │
        ▼
  [Nanny]   ── Writes the final deliverable + archives the full session
```

---

## Agent Roles

| Agent | What it does | Output file |
|-------|-------------|-------------|
| **Dao** | Scans wiki with multi-hop graph search, maps what's known, lists knowledge gaps, proposes sources | `handoff_dao.md` |
| **Builder** | Runs Mistral OCR on new PDFs, promotes extracted text into structured wiki pages | `handoff_builder.md` |
| **Cherry** | Reads structured claims from wiki frontmatter, finds blind spots Dao missed | `handoff_cherry.md` |
| **Nam** | Synthesizes everything into a research strategy with 5 concrete directions | `handoff_nam.md` |
| **Som** | Logic auditor — checks if the strategy is internally consistent | `handoff_audit.md` |
| **Manao** | Fact auditor — cross-checks claims against wiki evidence | `handoff_audit.md` |
| **Mod** | Extracts atomic insights, detects contradictions, marks stale knowledge | `handoff_mod.md` |
| **Nanny** | Writes final report/slides/Obsidian page, archives the full session | `handoff_nanny.md` |

---

## Prerequisites

- Python 3.9+
- **Mistral AI API key** — used for OCR, LLM reasoning, and embeddings ([get one at mistral.ai](https://mistral.ai))
- Obsidian (optional, for visualizing the knowledge graph)

---

## Installation

```bash
# 1. Clone the pipeline code
git clone https://github.com/Lovorz/llm-wiki-framework.git
cd llm-wiki-framework
pip install -r requirements.txt

# 2. Store your Mistral API key permanently
echo 'export MISTRAL_API_KEY="your-key-here"' >> ~/.bash_env
echo 'export BASH_ENV="$HOME/.bash_env"' >> ~/.profile

# 3. Create the orchestrator shortcut command
PIPELINE_HOME="$(pwd)"
cat > ~/.local/bin/orchestrator << EOF
#!/usr/bin/env bash
exec python "$PIPELINE_HOME/scripts/orchestrator.py" "\$@"
EOF
chmod +x ~/.local/bin/orchestrator

# 4. Create the wiki-manager shortcut command
cat > ~/.local/bin/wiki-manager << EOF
#!/usr/bin/env bash
exec python "$PIPELINE_HOME/scripts/wiki_manager.py" "\$@"
EOF
chmod +x ~/.local/bin/wiki-manager
```

---

## Setting Up a Vault

A vault is just a folder with your PDFs and the generated knowledge base.

```bash
# Create a new vault
mkdir my-research-vault
cd my-research-vault
mkdir raw wiki log handoffs

# Drop your PDF papers into raw/
cp /path/to/paper1.pdf raw/
cp /path/to/paper2.pdf raw/
```

---

## Command Reference

### `wiki-manager` — Knowledge Base Management

Run these from inside your vault folder.

---

#### `wiki-manager all`
**What it does:** Runs the full ingestion pipeline — OCR extracts all new PDFs, promotes them to structured wiki pages, and rebuilds the search index. Run this whenever you add new papers to `raw/`.

```bash
cd my-research-vault
wiki-manager all
```

**Output:**
```
Scanning raw/ for new files...
  [OCR] My-Paper-2024 ... ✓ (42300 chars)
  [LLM extract] My Paper 2024 ... 38 claims (12 RESULT, 8 TABLE, 10 MECHANISM, 8 METHOD)
Promoted 1 logs.
Generating Semantic Vector Index...
Index Update Complete. 1 files newly embedded.
```
→ Creates `wiki/My-Paper-2024.md` with 30–50 structured claims in YAML frontmatter

---

#### `wiki-manager ingest`
**What it does:** OCR step only. Extracts text from new PDFs in `raw/` and saves raw extractions to `log/`. Useful if you want to inspect the raw text before promoting.

```bash
wiki-manager ingest
```

---

#### `wiki-manager promote`
**What it does:** LLM step only. Reads files in `log/`, extracts 30–50 structured claims per paper (categorized as RESULT / TABLE / METHOD / MECHANISM / COMPARISON), and saves them to `wiki/`.

```bash
wiki-manager promote
```

---

#### `wiki-manager index-vectors`
**What it does:** Rebuilds the semantic search index (`.vectors.json`). Run this after adding new wiki pages so the pipeline can find them via similarity search.

```bash
wiki-manager index-vectors
```

---

#### `wiki-manager query "search terms"`
**What it does:** Semantic search over your wiki. Finds the most relevant pages for a topic using vector similarity.

```bash
wiki-manager query "oxygen vacancy defects CoOOH"
```

**Output:**
```
Semantic Search: 'oxygen vacancy defects CoOOH'...

--- Semantic Search Results (Top 10) ---
1. [[Ce-doped-self-assembled-ultrathin-CoOOH-nanosheets]] (Match: 0.921)
2. [[A-DFT-investigation-on-surface-and-defect-modulation-of-Co3O4]] (Match: 0.887)
3. [[Operando-Surface-X-Ray-Diffraction-Studies]] (Match: 0.843)
...
```

---

#### `wiki-manager crystallize`
**What it does:** Takes the most recent pipeline session (or a specific mission file) and distills it into a permanent insight page saved to `wiki/concepts/`. Think of it as turning a research session into a citable, permanent record.

```bash
# Use the latest session automatically
wiki-manager crystallize

# Or specify a session file
wiki-manager crystallize handoffs/mission_20260511_2041.md
```

**Output:**
```
Crystallizing: mission_20260511_2041.md ...
  → wiki/concepts/Role-of-Surface-Defects-in-CoOOH-for-OER.md
```
→ Creates a wiki page with: Summary, Key Findings, Mechanisms, Open Questions, Related Pages

---

#### `wiki-manager synthesize "Concept Name"`
**What it does:** Gathers all wiki pages related to a concept and writes an expert "State of the Art" synthesis page. Synthesizes trends, contradictions, and quantitative comparisons across papers — not just a list.

```bash
wiki-manager synthesize "OER"
wiki-manager synthesize "CoOOH" --keywords defects vacancy overpotential
```

**Output:**
```
Synthesizing: OER ...
  → wiki/concepts/OER.md  (14 sources)
```
→ Creates a synthesis page with: Overview, Current Trends, Quantitative Comparison, Contradictions & Open Questions, Strategic Outlook

---

#### `wiki-manager export "topic" --format FORMAT`
**What it does:** Generates a formatted document from your wiki knowledge on a topic. Useful for turning your knowledge base into presentations, thesis sections, or data tables.

```bash
# Marp slide deck (default)
wiki-manager export "CoOOH OER defects" --format marp

# LaTeX section for a thesis
wiki-manager export "CoOOH OER defects" --format latex

# CSV data table of all quantitative claims
wiki-manager export "CoOOH OER defects" --format csv

# Academic report section
wiki-manager export "CoOOH OER defects" --format report
```

**Output:**
```
Exporting 'CoOOH OER defects' as marp ...
  → exports/CoOOH-OER-defects.md
```
→ Ready-to-use file in `exports/` folder

---

#### `wiki-manager lint`
**What it does:** Health check for your wiki. Finds broken wikilinks (links pointing to pages that don't exist) and orphan pages (pages that no other page links to).

```bash
wiki-manager lint
```

**Output:**
```
=== Wiki Lint Report ===
Total pages : 87
Broken links: 3
  [[Defect-Engineered-CoOOH]]  ←  in Ce-doped-self-assembled-ultrathin-CoOOH-nanosheets
  [[Lattice-Oxygen-Redox]]     ←  in Two-sites-better-than-one-OER-on-CoOOH
  ...

Orphan pages (no incoming links): 12
  Recent-developments-of-zinc-oxide...
  ...
```

---

### `orchestrator` — Research Pipeline

Run this from inside your vault folder after the knowledge base is built.

```bash
cd my-research-vault
orchestrator "Your research question here"
```

**Example:**
```bash
orchestrator "What is the role of surface defects in CoOOH for OER activity?"
```

**Output formats at CP3:**

| Format | Best for | Output |
|--------|----------|--------|
| `report` | Reading, sharing | Full technical report with abstract, findings, discussion |
| `marp` | Presentations | Slide deck ready to open in VS Code + Marp extension |
| `obsidian` | Knowledge base | Wikilink-rich page with callout blocks and Mermaid diagrams |

All sessions are archived as `handoffs/mission_YYYYMMDD_HHMM.md` — the complete record of every agent's work.

---

## Typical Workflow

```bash
# Day 1: Set up vault and build knowledge base
mkdir my-vault && cd my-vault && mkdir raw wiki log handoffs
# copy PDFs to raw/
wiki-manager all

# Day 2: Run a research session
orchestrator "What gaps exist in understanding X?"

# After the session: crystallize findings permanently
wiki-manager crystallize

# When writing a paper: export a section
wiki-manager export "Topic X" --format latex

# Monthly: health check + concept synthesis
wiki-manager lint
wiki-manager synthesize "Main Topic"
```

---

## Project Structure

```
llm-wiki-framework/          ← Pipeline code (install once, use everywhere)
├── agents/
│   ├── base.py              ← Shared: LLM calls, embeddings, multi-hop graph search
│   ├── dao.py               ← Gap analysis & source discovery
│   ├── builder.py           ← PDF OCR & wiki promotion
│   ├── cherry.py            ← Blind-spot detection
│   ├── nam.py               ← Strategy synthesis
│   ├── som.py               ← Logic auditor
│   ├── manao.py             ← Fact auditor
│   ├── mod.py               ← Insight distiller
│   └── nanny.py             ← Output writer
└── scripts/
    ├── orchestrator.py      ← Pipeline runner (8 agents + 3 checkpoints)
    └── wiki_manager.py      ← Knowledge base management (10 commands)

my-vault/                    ← Your research project (data only)
├── raw/                     ← Drop PDFs here
├── log/                     ← OCR extractions (auto-managed)
├── wiki/                    ← Structured knowledge pages
│   ├── .vectors.json        ← Semantic search index (auto-generated)
│   └── concepts/            ← Synthesized insight pages
├── exports/                 ← Generated slides, LaTeX, CSVs
└── handoffs/                ← Agent outputs + archived sessions
    └── mission_YYYYMMDD_HHMM.md
```

---

## Key Features

- **Multi-hop Graph Search** — Finds related knowledge 2 links away, not just keyword matches
- **Structured Claims** — Each wiki page stores 30–50 LLM-extracted claims in YAML (`claims[]`), so agents read structured facts instead of raw text
- **Contradiction Resolution** — Mod detects when new findings contradict old ones and marks superseded knowledge as stale
- **Parallel Auditing** — Som and Manao fact-check simultaneously; silent retry before interrupting you
- **Multi-vault Support** — One code installation, unlimited research projects
- **Audit Trail** — Every operation logged to `wiki/.audit-log.md`

---

## Built With

- [Mistral AI](https://mistral.ai) — OCR (`mistral-ocr-latest`), LLM reasoning (`mistral-large-latest`), embeddings (`mistral-embed`)
- [Obsidian](https://obsidian.md) — Knowledge graph visualization
