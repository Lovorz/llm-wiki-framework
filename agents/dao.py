"""Dao — Librarian agent. Maps existing knowledge and identifies gaps."""
from .base import BaseAgent, WIKI_DIR


class DaoLibrarian(BaseAgent):

    def run(self, topic: str) -> str:
        print(f"[Dao] Scanning wiki for gaps on: {topic}")

        # 1. Load hub pages for domain context (truncated)
        hub_parts = []
        for hub in sorted(WIKI_DIR.glob("*Hub.md")):
            text = hub.read_text(encoding="utf-8", errors="ignore")[:1200]
            hub_parts.append(f"### {hub.stem}\n{text}")
        hub_context = "\n\n".join(hub_parts) or "(no hub pages found)"

        # 2. Multi-hop graph search for relevant pages
        graph_results = self.graph_search(topic, top_k=15, hops=2)
        if graph_results:
            existing = "\n".join(
                f"- {name} (score: {score:.3f})" for name, score in graph_results
            )
        else:
            kw_results = self.keyword_search(topic, top_k=15)
            existing = "\n".join(f"- {name}" for name in kw_results) or "(no relevant pages found)"

        system = (
            "You are Dao, the Librarian agent. Your job is to map existing knowledge and identify research gaps "
            "with surgical precision. Be comprehensive and detailed — generic or brief answers are useless.\n\n"
            "Output format (Markdown):\n\n"
            "## Known\n"
            "For each known topic: cite [[wikilinks]], explain what is covered, and note its limitations (2–3 sub-bullets each).\n\n"
            "## Gaps\n"
            "Numbered list. For each gap: explain the context (why it matters), state the specific missing knowledge, "
            "and note which existing sources hint at it but fall short.\n\n"
            "## Proposed Sources\n"
            "10–15 items as [[wikilinks]]. For each: a *Relevance:* paragraph explaining exactly what the source "
            "would contribute, what method or data it provides, and how it connects to the gaps above.\n\n"
            "## Proposed Workflow\n"
            "A step-by-step computational/experimental workflow that addresses the gaps using the proposed sources."
        )
        user = (
            f"**Research Topic:** {topic}\n\n"
            f"### Existing Wiki Pages (ranked by relevance):\n{existing}\n\n"
            f"### Domain Hub Context:\n{hub_context}\n\n"
            "Produce the handoff_dao.md report. Be specific — generic gaps are useless."
        )

        report = self.call_llm(system, user)
        self.write_handoff("dao", report)
        return report
