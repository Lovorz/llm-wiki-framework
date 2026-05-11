"""Mod — Distiller. Extracts atomic insights and writes them to wiki/concepts/."""
import re
import yaml
from datetime import datetime
from pathlib import Path
from .base import BaseAgent, WIKI_DIR


class ModDistiller(BaseAgent):

    def run(self, nam_report: str, audit_report: str, topic: str) -> str:
        print("[Mod] Distilling atomic insights...")

        system = (
            "You are Mod, the Distiller. Extract self-contained atomic insights from a research strategy.\n\n"
            "Rules:\n"
            "- Each insight is a single verifiable fact or mechanism — no multi-claim paragraphs\n"
            "- Use LaTeX for all chemical formulas and equations (e.g., $Co_3O_4$, $\\Delta G$)\n"
            "- Assign confidence based on evidence quality:\n"
            "    1.0 = directly quoted from a cited source in the vault\n"
            "    0.7-0.9 = inferred from multiple converging sources\n"
            "    0.4-0.6 = plausible but speculative or uncited\n"
            "- Any metric without a [[wikilink]] citation gets confidence ≤ 0.6\n"
            "- Be thorough — extract ALL distinct insights, not just the most obvious ones\n\n"
            "Format each insight as:\n"
            "### [Descriptive Title]\n"
            "**Fact:** (one precise sentence, LaTeX-formatted)\n"
            "**Detail:** (2–3 sentences expanding the fact: mechanism, evidence, implications)\n"
            "**Source:** [[WikiLink]] (or 'uncited' if none)\n"
            "**Confidence:** 0.X\n"
            "**Status:** verified | inferred | speculative"
        )
        user = (
            f"**Topic:** {topic}\n\n"
            f"### Strategy (from Nam):\n{nam_report}\n\n"
            f"### Audit Notes (from Som+Manao):\n{audit_report}\n\n"
            "Extract all atomic insights you can find (aim for 10–15). "
            "Downgrade confidence for anything flagged in the audit. "
            "Preserve LaTeX formatting. Be detailed in the **Detail:** field."
        )

        report = self.call_llm(system, user)
        self._persist_to_wiki(report, topic)
        self.write_handoff("mod", report)
        return report

    def _persist_to_wiki(self, report: str, topic: str) -> None:
        concepts_dir = WIKI_DIR / "concepts"
        concepts_dir.mkdir(exist_ok=True)

        slug = re.sub(r"[^\w-]", "-", topic.lower()).strip("-")[:50]
        out_path = concepts_dir / f"{slug}-insights.md"
        ts = datetime.now().strftime("%Y-%m-%d")

        # Contradiction resolution: compare against existing insights
        stale_titles: list[str] = []
        if out_path.exists():
            existing_body = out_path.read_text(encoding="utf-8", errors="ignore")
            stale_titles = self._find_stale_insights(existing_body, report)
            if stale_titles:
                print(f"    ⚠️  Marking {len(stale_titles)} stale insight(s): {stale_titles}")
                self.audit_log("Mod", "contradiction", f"stale: {stale_titles}")

        # Rebuild page: stale old insights marked, new session appended
        if out_path.exists():
            existing_body = self._mark_stale(out_path.read_text(encoding="utf-8"), stale_titles)
            content = existing_body.rstrip() + f"\n\n## Session {ts}\n\n{report}"
        else:
            frontmatter = {
                "title": f"Insights: {topic}",
                "type": "crystallized_insight",
                "last_updated": ts,
                "generated_by": "Mod",
            }
            content = (
                f"---\n{yaml.dump(frontmatter, sort_keys=False)}---\n\n"
                f"# Insights: {topic}\n\n"
                f"## Session {ts}\n\n{report}"
            )

        out_path.write_text(content, encoding="utf-8")
        self.audit_log("Mod", "persist_insights", f"{len(stale_titles)} stale, topic={topic[:60]}")
        print(f"    → {out_path.relative_to(WIKI_DIR.parent)}")

    def _find_stale_insights(self, old_body: str, new_report: str) -> list[str]:
        """Use LLM to find old insight titles that are contradicted by new findings."""
        # Only bother if old body is substantial
        old_section = old_body[-3000:] if len(old_body) > 3000 else old_body
        system = (
            "You compare OLD research insights against NEW ones. "
            "Return ONLY a JSON array of old insight short titles (### headings) "
            "that are directly contradicted by the new report. "
            "If nothing is contradicted, return []. "
            "Example: [\"Vacancy Effect on d-band\", \"OER Rate-limiting Step\"]"
        )
        user = (
            f"**OLD insights (last 3000 chars):**\n{old_section}\n\n"
            f"**NEW insights:**\n{new_report[:3000]}"
        )
        try:
            raw = self.call_llm(system, user)
            import json
            # Extract the JSON array from the response
            match = re.search(r"\[.*?\]", raw, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception:
            pass
        return []

    def _mark_stale(self, body: str, stale_titles: list[str]) -> str:
        """Wrap stale insight blocks in a [!stale] callout."""
        if not stale_titles:
            return body
        lines = body.split("\n")
        result = []
        in_stale = False
        for line in lines:
            # Detect start of a stale insight (### heading matching a stale title)
            if line.startswith("### "):
                title = line[4:].strip()
                in_stale = any(s.lower() in title.lower() for s in stale_titles)
                if in_stale:
                    result.append("> [!stale] Superseded")
            if in_stale:
                result.append(f"> {line}")
            else:
                result.append(line)
            # End stale block at the next blank line after content
        return "\n".join(result)
