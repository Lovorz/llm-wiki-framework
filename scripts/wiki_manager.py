import os
import re
import sys
import yaml
import argparse
import json
import requests
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

# Load API keys from ~/.bash_env if not already in environment
_bash_env = Path.home() / ".bash_env"
if _bash_env.exists():
    for _line in _bash_env.read_text().splitlines():
        if _line.startswith("export ") and "=" in _line:
            _k, _, _v = _line[len("export "):].partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip('"'))
WIKI_DIR = Path('wiki')
LOG_DIR = Path('log')
RAW_DIR = Path('raw')
INDEX_FILE = WIKI_DIR / 'index.md'
VECTOR_INDEX = WIKI_DIR / '.vectors.json'

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
_MISTRAL_CHAT = "https://api.mistral.ai/v1/chat/completions"
_MISTRAL_EMBED = "https://api.mistral.ai/v1/embeddings"
_LLM_MODEL = "mistral-large-latest"
_EMBED_MODEL = "mistral-embed"

if not MISTRAL_API_KEY:
    raise EnvironmentError("MISTRAL_API_KEY environment variable is not set.")

class WikiManager:
    def __init__(self):
        self.link_pattern = re.compile(r'\[\[([^|\]]+)(?:\|[^\]]+)?\]\]')
        self.frontmatter_pattern = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)

        # Taxonomy Definitions
        self.apps = {
            "🔋 Battery & Energy Storage": ["battery", "batteries", "anode", "cathode", "lithium", "aluminum", "al-s", "li-s", "polysulfide", "shuttle", "sulfur"],
            "⚡ Electrocatalysis": ["oer", "orr", "her", "overpotential", "tafel", "oxygen evolution", "hydrogen evolution", "water splitting"],
            "☀️ Photocatalysis": ["photocatalyst", "photocatalysis", "visible light", "z-scheme", "solar"],
            "☁️ CO2 & Gas Conversion": ["co oxidation", "co2", "methanation", "gas capture", "adsorption"]
        }
        self.materials = {
            "💠 MXenes & 2D Materials": ["mxene", "monolayer", "2d material", "bluep", "heterostructure", "g-c3n4"],
            "💎 Perovskites": ["perovskite", "lanio3", "lacoo3", "perovskite-based"],
            "🧱 Metal Oxides & Hydroxides": ["oxide", "co3o4", "coooh", "niooh", "nio", "zno", "tio2", "hydroxide", "nanosheet", "nanoplate"]
        }

    def _get_processed_sources(self):
        sources = set()
        for f in WIKI_DIR.glob('*.md'):
            try:
                content = f.read_text(encoding='utf-8', errors='ignore')
                match = self.frontmatter_pattern.match(content)
                if match:
                    fm = yaml.safe_load(match.group(1))
                    if 'sources' in fm:
                        for s in fm['sources']:
                            if s.startswith('raw/'): sources.add(s[4:])
            except: pass
        return sources

    def ingest(self, include_images=False):
        print(f"Scanning raw/ for new files... (Include Images: {include_images})")
        sys.path.append(str(Path(__file__).parent))
        from mistral_ocr_client import extract_with_mistral
        processed = self._get_processed_sources()
        raw_files = [f for f in RAW_DIR.glob('*.pdf') if f.name not in processed]
        for f in raw_files:
            print(f"Ingesting: {f.name}")
            text = extract_with_mistral(str(f), include_images=include_images)
            if "Error" in text: continue
            fm = {'title': f.stem.replace('-', ' '), 'type': 'paper', 'sources': [f"raw/{f.name}"],
                  'last_updated': datetime.now().strftime('%Y-%m-%d'), 'extraction_method': 'mistral'}
            (LOG_DIR / f"{f.stem}.md").write_text(f"---\n{yaml.dump(fm, sort_keys=False)}---\n# {f.stem}\n\n{text}", encoding='utf-8')
        self._log_operation("ingest", f"{len(raw_files)} new files from raw/")
        print(f"Ingested {len(raw_files)} files.")

    # ─────────────────────────────────── audit trail

    def _log_operation(self, op_type: str, details: str) -> None:
        log_path = WIKI_DIR / ".audit-log.md"
        WIKI_DIR.mkdir(exist_ok=True)
        if not log_path.exists():
            log_path.write_text(
                "# Audit Trail\n\n"
                "| Timestamp | Operation | Details |\n"
                "|-----------|-----------|---------|",
                encoding="utf-8",
            )
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        safe = details.replace("|", "∣").replace("\n", " ")[:150]
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n| {ts} | {op_type} | {safe} |")

    # ─────────────────────────────────── LLM helpers

    def _call_llm(self, system: str, user: str) -> str:
        headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
        resp = requests.post(
            _MISTRAL_CHAT,
            headers=headers,
            json={"model": _LLM_MODEL,
                  "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": user}]},
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def _extract_claims_llm(self, body: str, title: str) -> list:
        """
        LLM-based comprehensive claim extraction — 5 categories, ~30-50 claims per paper.
        Each claim stored as {fact, confidence, category}.
        """
        system = (
            "You are a scientific claim extractor. Extract ALL precise claims from the paper excerpt.\n"
            "Output one claim per line in this exact format:\n"
            "[CATEGORY] <one precise sentence with numbers/LaTeX preserved>\n\n"
            "Categories (use exactly these labels):\n"
            "RESULT — quantitative results, benchmark numbers, performance metrics\n"
            "TABLE — data from tables (include all columns/values)\n"
            "METHOD — computational or experimental parameters, software, functionals\n"
            "MECHANISM — reaction pathways, charge transfer, bonding mechanisms\n"
            "COMPARISON — comparisons between materials, methods, or conditions\n\n"
            "Rules:\n"
            "- Preserve all numbers, units, LaTeX formulas exactly\n"
            "- Do NOT paraphrase — use the paper's own language\n"
            "- Extract at least 20 claims if the text is long enough\n"
            "- Skip figure captions and reference lists"
        )
        user = f"**Paper:** {title}\n\n{body[:12_000]}"
        try:
            raw = self._call_llm(system, user)
        except Exception as e:
            print(f" [claim extraction failed: {e}]")
            return []

        claims = []
        category_conf = {"RESULT": 0.95, "TABLE": 0.90, "METHOD": 0.85, "MECHANISM": 0.80, "COMPARISON": 0.85}
        for line in raw.split("\n"):
            line = line.strip()
            for cat in category_conf:
                if line.startswith(f"[{cat}]"):
                    fact = line[len(f"[{cat}]"):].strip()
                    if len(fact) > 10:
                        claims.append({"fact": fact, "confidence": category_conf[cat], "category": cat})
                    break
        return claims

    def read_page_claims(self, page_name: str) -> list:
        """Read claims[] from wiki page YAML frontmatter."""
        for path in [WIKI_DIR / f"{page_name}.md", WIKI_DIR / f"{page_name.replace(' ', '-')}.md"]:
            if path.exists():
                content = path.read_text(encoding="utf-8", errors="ignore")
                match = self.frontmatter_pattern.match(content)
                if match:
                    fm = yaml.safe_load(match.group(1))
                    return fm.get("claims", [])
        return []

    # ─────────────────────────────────── promote

    def promote(self):
        print("Promoting logs to wiki/ with LLM claim extraction...")
        files = list(LOG_DIR.glob("*.md"))
        promoted = 0
        keywords = ["OER", "ORR", "HER", "Li-S", "Al-S", "CO2", "MXene", "Perovskite", "VASP", "DFT"]

        for f in files:
            if f.name == "log.md":
                continue
            content = f.read_text(encoding="utf-8", errors="ignore")
            fm_match = self.frontmatter_pattern.match(content)
            fm = yaml.safe_load(fm_match.group(1)) if fm_match else {}
            body = content[fm_match.end():] if fm_match else content

            title = fm.get("title", f.stem.replace("_full", "").replace("-", " ").strip())
            lower_title = title.lower()
            doc_type = "paper"
            if "review" in lower_title:
                doc_type = "review"
            elif "chapter" in lower_title or "thesis" in lower_title:
                doc_type = "thesis"

            print(f"  [LLM extract] {title} ...", end="", flush=True)
            claims = self._extract_claims_llm(body, title)

            by_cat = {}
            for c in claims:
                by_cat.setdefault(c.get("category", "OTHER"), []).append(c)
            summary = ", ".join(f"{len(v)} {k}" for k, v in by_cat.items())
            print(f" {len(claims)} claims ({summary})")

            entities = [f"[[{kw}]]" for kw in keywords if kw.lower() in content.lower()]

            new_fm = {
                **fm,
                "type": doc_type,
                "claims": claims,
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
            }
            md = f"---\n{yaml.dump(new_fm, sort_keys=False, allow_unicode=True)}---\n# {title}\n\n"
            md += "## 📄 Full Extraction\n\n" + body.strip() + "\n\n---\n\n"
            md += "## 💎 Crystallized Wrap\n\n"
            for cat in ["RESULT", "TABLE", "MECHANISM", "METHOD", "COMPARISON"]:
                cat_claims = [c for c in claims if c.get("category") == cat]
                if cat_claims:
                    md += f"### {cat}\n"
                    for c in cat_claims[:15]:
                        md += f"- {c['fact']}\n"
                    md += "\n"
            if entities:
                md += "### 🔗 Relationships\n- " + "\n- ".join(sorted(set(entities))) + "\n"

            (WIKI_DIR / f"{f.stem}.md").write_text(md, encoding="utf-8")

            for entity in entities:
                concept_name = entity.strip("[]")
                concept_path = WIKI_DIR / "concepts" / f"{concept_name}.md"
                if concept_path.exists():
                    try:
                        with open(concept_path, "a", encoding="utf-8") as cf:
                            ts = datetime.now().strftime("%Y-%m-%d")
                            first = claims[0]["fact"] if claims else "New data available."
                            cf.write(f"\n### ➕ Compounding Evidence ({ts})\n")
                            cf.write(f"- **Source**: [[{f.stem}]]\n")
                            cf.write(f"- **Key Update**: {first}\n")
                    except Exception:
                        pass

            f.unlink()
            promoted += 1

        self._log_operation("promote", f"{promoted} logs → wiki/ with LLM claim extraction")
        print(f"Promoted {promoted} logs.")

    def categorize(self):
        print("Categorizing Index...")
        pages = [f for f in WIKI_DIR.glob('*.md') if f.name != 'index.md' and "Hub" not in f.name and "concepts" not in f.parts]
        app_results = {cat: [] for cat in self.apps}
        mat_results = {cat: [] for cat in self.materials}

        for p in pages:
            content = p.read_text(encoding='utf-8', errors='ignore').lower()
            for cat, kws in self.apps.items():
                if any(kw in p.stem.lower() or kw in content for kw in kws): app_results[cat].append(p.stem)
            for cat, kws in self.materials.items():
                if any(kw in p.stem.lower() or kw in content for kw in kws): mat_results[cat].append(p.stem)

        def write_hub(name, titles):
            (WIKI_DIR / f"{name}.md").write_text(f"# {name}\n\n" + "\n".join([f"- [[{t}]]" for t in sorted(list(set(titles)))]), encoding='utf-8')

        for cat, titles in app_results.items(): write_hub(f"{cat.split()[-1]} Hub", titles)
        for cat, titles in mat_results.items(): write_hub(f"{cat.split()[-1]} Hub", titles)

        idx_md = "# 🏛️ Knowledge Vault Index\n\n## 🎯 Applications\n"
        for cat in self.apps: idx_md += f"- [[{cat.split()[-1]} Hub]] ({cat})\n"
        idx_md += "\n## 🧪 Materials\n"
        for cat in self.materials: idx_md += f"- [[{cat.split()[-1]} Hub]] ({cat})\n"
        idx_md += "\n## 🧠 Intelligent Syntheses\n- [[OER]] | [[Al-S Batteries]] | [[MXenes]] | [[Perovskites]]\n"

        idx_md += "\n---\n### 🕒 Recent Ingestions\n"
        recent_files = sorted(pages, key=lambda x: x.stat().st_mtime, reverse=True)[:5]
        for rf in recent_files: idx_md += f"- [[{rf.stem}]]\n"

        INDEX_FILE.write_text(idx_md, encoding='utf-8')

    def _embed(self, text: str) -> list:
        headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
        resp = requests.post(
            _MISTRAL_EMBED,
            headers=headers,
            json={"model": _EMBED_MODEL, "input": text[:4096]},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]

    def index_vectors(self):
        print("Generating Semantic Vector Index (Mistral Embeddings)...")
        if VECTOR_INDEX.exists():
            with open(VECTOR_INDEX, 'r') as f: data = json.load(f)
        else: data = {}

        files = list(WIKI_DIR.glob('**/*.md'))
        updated = 0
        for f in files:
            if f.name == 'index.md' or VECTOR_INDEX.name in f.name: continue
            mtime = f.stat().st_mtime
            if f.name in data and data[f.name]['mtime'] >= mtime: continue

            content = f.read_text(encoding='utf-8', errors='ignore')
            match = self.frontmatter_pattern.match(content)
            body = content[match.end():].strip() if match else content

            try:
                vector = self._embed(body[:4000])
                data[f.name] = {'vector': vector, 'mtime': mtime, 'title': f.stem}
                updated += 1
                print(f"Indexed: {f.name}")
            except Exception as e:
                print(f"Failed to index {f.name}: {e}")

        with open(VECTOR_INDEX, 'w') as f: json.dump(data, f)
        print(f"Index Update Complete. {updated} files newly embedded.")

    def query(self, query_text):
        if not VECTOR_INDEX.exists():
            print("Error: Vector index not found. Run 'index-vectors' first.")
            return

        print(f"Semantic Search: '{query_text}'...")
        with open(VECTOR_INDEX, 'r') as f: index_data = json.load(f)
        try:
            query_vec = np.array(self._embed(query_text))
        except Exception as e:
            print(f"Query embedding failed: {e}"); return

        results = []
        for fname, info in index_data.items():
            doc_vec = np.array(info['vector'])
            similarity = np.dot(query_vec, doc_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(doc_vec))
            results.append((info['title'], similarity))

        results = sorted(results, key=lambda x: x[1], reverse=True)[:10]
        self._log_operation("query", f"'{query_text[:80]}' → {len(results)} results")
        print("\n--- Semantic Search Results (Top 10) ---")
        for i, (title, score) in enumerate(results):
            print(f"{i+1}. [[{title}]] (Match: {score:.3f})")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ingest", "promote", "categorize", "index-vectors", "query", "all"])
    parser.add_argument("query", nargs="?", help="Search query")
    args = parser.parse_args()
    mgr = WikiManager()
    if args.command == "ingest": mgr.ingest()
    elif args.command == "promote": mgr.promote()
    elif args.command == "categorize": mgr.categorize()
    elif args.command == "index-vectors": mgr.index_vectors()
    elif args.command == "query":
        if not args.query: print("Error: query requires a string.")
        else: mgr.query(args.query)
    elif args.command == "all":
        mgr.ingest(); mgr.promote(); mgr.categorize(); mgr.index_vectors()

if __name__ == '__main__': main()
