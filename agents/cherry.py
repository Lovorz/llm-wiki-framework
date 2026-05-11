"""Cherry — adversarial blind-spot sweep. Reads structured claims from wiki frontmatter."""
import re
import yaml
from .base import BaseAgent, WIKI_DIR, LOG_DIR


class CherryAgent(BaseAgent):

    def run(self, dao_report: str, builder_context: str) -> str:
        print("[Cherry] Loading claims pool then running blind-spot sweep...")

        has_notebook = (
            "notebook:" in builder_context
            and "N/A" not in builder_context.split("notebook:")[-1][:20]
        )

        # 1. Load structured claims from wiki frontmatter (token-efficient, complete)
        claims_pool = self._load_claims_pool(dao_report, builder_context)

        source_label = "NotebookLM + wiki claims" if has_notebook else "wiki claims pool"

        # 2. Adversarial sweep — context is structured claims, not raw text
        system = (
            "You are Cherry, the adversarial Question Shaper. Two tasks:\n\n"
            "TASK 1 — Q&A: Generate 6–8 research questions and answer each from the "
            "provided claims pool. If an answer is not found, write 'Not found' — "
            "this confirms a gap and is as valuable as a found answer.\n"
            "Question types: 2 foundational, 2 mechanistic, 2 gap-targeting, 1 blind-spot, 1 cross-domain.\n\n"
            "TASK 2 — Critique: Adversarially evaluate the research direction:\n"
            "- Which analogies from other systems may NOT transfer?\n"
            "- Which quantitative claims have no evidence in the claims pool?\n"
            "- What experimental/computational evidence is completely absent?\n"
            "- What single finding would falsify the entire approach?\n\n"
            "Output:\n"
            "## Q&A\n### Q1: ...\n- bullet answers (max 5 per question)\n\n"
            "## Unverified Claims\n"
            "## Dangerous Analogies\n"
            "## Missing Evidence\n"
            "## Critical Questions\n"
            "## Verdict (1–2 sentences: the single most critical risk)"
        )
        user = (
            f"**Research Direction (Dao):**\n{dao_report}\n\n"
            f"**Evidence Pool ({source_label}) — {len(claims_pool)} structured claims:**\n"
            f"{self._format_claims(claims_pool)}\n\n"
            "Answer each question from the claims pool. Mark 'Not found' when evidence is absent."
        )

        report = self.call_llm(system, user)
        self.write_handoff("cherry", report)
        return report

    # ─────────────────────────────────── claims loading

    def _load_claims_pool(self, topic: str, builder_context: str) -> list:
        """
        Load structured claims from wiki page frontmatter.
        Primary: semantic search for relevant pages.
        Secondary: pages referenced in builder handoff.
        Falls back to log/ per-paper summarization if wiki has no claims yet.
        """
        # Try wiki pages first (post-promote)
        wiki_pages = self._relevant_wiki_pages(topic, builder_context)
        claims = []
        for page_path in wiki_pages[:10]:
            page_claims = self._read_page_claims(page_path)
            if page_claims:
                stem = page_path.stem
                for c in page_claims:
                    c["source"] = stem
                claims.extend(page_claims)

        if claims:
            print(f"  [Cherry] {len(claims)} claims loaded from {len(wiki_pages)} wiki pages")
            return claims

        # Fallback: log/ files not yet promoted — summarize them
        print("  [Cherry] No wiki claims found — falling back to log/ summarization")
        return self._fallback_log_summaries(topic, builder_context)

    def _read_page_claims(self, page_path) -> list:
        """Extract claims[] from YAML frontmatter of a wiki page."""
        try:
            content = page_path.read_text(encoding="utf-8", errors="ignore")
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            if match:
                fm = yaml.safe_load(match.group(1))
                return fm.get("claims", [])
        except Exception:
            pass
        return []

    def _relevant_wiki_pages(self, topic: str, builder_context: str) -> list:
        """Get wiki pages relevant to the topic, prioritizing builder-referenced ones."""
        # Collect stems from both log/ and wiki/ paths in builder handoff
        stems = set()
        for name in re.findall(r"log/([^\s|]+?)\.md", builder_context):
            stems.add(name)
        for name in re.findall(r"wiki/([^\s|/]+?)\.md", builder_context):
            stems.add(name)

        pages = []
        for stem in stems:
            p = WIKI_DIR / f"{stem}.md"
            if p.exists():
                pages.append(p)

        # Semantic search fallback
        if not pages:
            try:
                results = self.semantic_search(topic, top_k=10)
                for title, _score in results:
                    p = WIKI_DIR / f"{title}.md"
                    if p.exists():
                        pages.append(p)
            except Exception:
                pages = [p for p in sorted(WIKI_DIR.glob("*.md"))
                         if p.name not in ("index.md",) and "Hub" not in p.name][-10:]

        return pages

    def _format_claims(self, claims: list) -> str:
        """Format claims pool grouped by category for LLM context."""
        by_cat: dict = {}
        for c in claims:
            cat = c.get("category", "RESULT")
            by_cat.setdefault(cat, []).append(c)

        lines = []
        for cat in ["RESULT", "TABLE", "MECHANISM", "METHOD", "COMPARISON"]:
            if cat not in by_cat:
                continue
            lines.append(f"\n### {cat}")
            for c in by_cat[cat]:
                src = c.get("source", "")
                conf = c.get("confidence", 0.9)
                lines.append(f"- [{src}] {c['fact']} (conf={conf:.2f})")
        return "\n".join(lines)

    # ─────────────────────────────────── fallback

    def _fallback_log_summaries(self, topic: str, builder_context: str) -> list:
        """
        When wiki has no promoted claims yet: read log/ files, extract key sections,
        run per-paper LLM summarization, return as pseudo-claims.
        """
        log_files = self._collect_log_files(builder_context)
        if not log_files:
            return []

        all_claims = []
        for lf in log_files[:8]:
            print(f"  [Cherry] summarizing {lf.name} ...", end="", flush=True)
            raw = lf.read_text(encoding="utf-8", errors="ignore")
            body = re.sub(r"^---.*?---\s*", "", raw, count=1, flags=re.DOTALL).strip()
            excerpt = self._extract_key_sections(body, char_limit=10_000)
            bullets = self._one_paper_summary(lf.stem, excerpt, topic)
            for line in bullets.split("\n"):
                line = line.strip().lstrip("- ").strip()
                if len(line) > 10:
                    all_claims.append({"fact": line, "confidence": 0.8, "category": "RESULT", "source": lf.stem})
            print(" ✓")

        return all_claims

    def _extract_key_sections(self, markdown: str, char_limit: int = 10_000) -> str:
        _KEEP = re.compile(r"^#{1,3}\s+.*?(abstract|introduction|result|finding|discussion|conclusion|summary|outlook|implication)", re.IGNORECASE)
        _SKIP = re.compile(r"^#{1,3}\s+.*?(method|experimental|computational|calculation|reference|acknowledgement|supporting|appendix|author contribution)", re.IGNORECASE)

        lines = markdown.split("\n")
        in_keep, in_skip = False, False
        kept: list = []
        total = 0

        for line in lines:
            if _SKIP.match(line):
                in_skip, in_keep = True, False
                continue
            if _KEEP.match(line):
                in_skip, in_keep = False, True
                kept.append(line)
                total += len(line)
                continue
            if not in_skip and (in_keep or total == 0):
                kept.append(line)
                total += len(line)
            if total >= char_limit:
                break

        result = "\n".join(kept).strip()
        if len(result) < 500:
            head = markdown[:4_000]
            tail = markdown[-2_000:] if len(markdown) > 6_000 else ""
            result = head + ("\n\n[...]\n\n" + tail if tail else "")
        return result[:char_limit]

    def _one_paper_summary(self, title: str, excerpt: str, topic: str) -> str:
        system = (
            "You are a scientific summarizer. Extract exactly 5 bullet points from the paper excerpt "
            "that are most relevant to the research topic. Each bullet: one precise fact or finding, "
            "with any numbers preserved. Use LaTeX for formulas. "
            "If the paper has nothing relevant, write: '- Not relevant to this topic.'"
        )
        user = f"**Topic:** {topic}\n\n**Paper: {title}**\n\n{excerpt[:8_000]}"
        try:
            return self.call_llm(system, user)
        except Exception as e:
            return f"- Summary failed: {e}"

    def _collect_log_files(self, builder_context: str):
        referenced = re.findall(r"log/([^\s|]+?\.md)", builder_context)
        files = []
        for name in referenced:
            p = LOG_DIR / name
            if p.exists():
                files.append(p)
        if not files and LOG_DIR.exists():
            files = [f for f in sorted(LOG_DIR.glob("*.md")) if f.name != "log.md"][-8:]
        return files
