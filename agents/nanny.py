"""Nanny — Output Writer. Formats insights into the user-chosen deliverable."""
from datetime import datetime
from .base import BaseAgent, HANDOFF_DIR

_BRIEF_SYSTEMS = {
    "marp": (
        "Format as a concise Marp slide deck (brief overview of the full session). "
        "YAML front matter: marp: true, theme: default, size: 16:9, paginate: true.\n"
        "One slide per agent section, separated by ---:\n"
        "1. Title slide — research question + date\n"
        "2. [Dao] Key Gaps — top 3–5 gaps as tight bullets\n"
        "3. [Cherry] Blind Spots — top 2–3 blind spots as tight bullets\n"
        "4. [Nam] Research Directions — all 5 directions, one line each\n"
        "5. [Audit] Verdict — Som PASS/FAIL + Manao PASS/FAIL + top 2 flags\n"
        "6. [Mod] Key Insights — top 3–5 insights as tight bullets\n"
        "7. Next Steps — 3–5 concrete actions\n"
        "Max 6 bullets per slide. No paragraphs. Scannable only."
    ),
    "report": (
        "Write a concise research brief (~500 words). Sections:\n"
        "1. Research Question (1 sentence)\n"
        "2. Key Gaps (top 3–5, one sentence each)\n"
        "3. Blind Spots (top 2–3, one sentence each)\n"
        "4. Research Directions (all 5, one line each)\n"
        "5. Audit Verdict (PASS/FAIL + top flag)\n"
        "6. Key Insights (top 3–5, one sentence each)\n"
        "7. Recommended Next Steps (3 bullets)\n"
        "No paragraphs. Tight bullets throughout."
    ),
    "obsidian": (
        "Format as a compact Obsidian brief page. Requirements:\n"
        "- YAML frontmatter: type: brief, date, tags, summary (1 sentence)\n"
        "- One > [!summary] callout per agent section (3–4 bullets each)\n"
        "- All key concepts as [[wikilinks]]\n"
        "- End with ## Next Steps (3 bullets)\n"
        "Keep each callout tight — no prose paragraphs."
    ),
}

_FORMAT_SYSTEMS = {
    "marp": (
        "Format the atomic insights as a complete Marp slide deck. "
        "Include YAML front matter (marp: true, theme: gaia, size: 16:9, paginate: true). "
        "Slides separated by ---. Structure: title slide → one slide per mechanism/insight → summary slide. "
        "Use LaTeX where provided. Each slide: 5–7 bullet points, each bullet fully explained (not one-liners)."
    ),
    "report": (
        "Format the atomic insights as a comprehensive, detailed technical research report. "
        "Do NOT summarize or truncate — write full paragraphs for every section. "
        "Sections:\n"
        "1. Abstract (full paragraph, 5–7 sentences)\n"
        "2. Key Findings — one dedicated subsection per insight with:\n"
        "   - Full explanation of the finding (3–5 sentences)\n"
        "   - Mechanistic context (how it connects to the research topic)\n"
        "   - Evidence basis and confidence level\n"
        "3. Mechanistic Discussion — a coherent narrative connecting all insights\n"
        "4. Confidence Summary Table (| Insight | Confidence | Status | Evidence |)\n"
        "5. Open Questions — speculative insights reframed as testable research questions, with suggested approaches\n"
        "6. Recommended Next Steps — concrete experimental/computational actions\n"
        "Preserve all LaTeX formatting. Aim for depth, not brevity."
    ),
    "obsidian": (
        "Format as Obsidian-ready Markdown. Requirements:\n"
        "- YAML frontmatter with tags, type, date, and a 'summary' field (2–3 sentences)\n"
        "- All materials/concepts as [[wikilinks]]\n"
        "- High-confidence findings in > [!important] callouts with full paragraph explanations\n"
        "- Speculative items in > [!warning] callouts with reasoning\n"
        "- A Mermaid diagram of the main mechanistic pathway\n"
        "- A ## References section listing all [[wikilinks]] cited\n"
        "Be comprehensive — every insight gets its own callout block with full context."
    ),
}


class NannyAgent(BaseAgent):

    def run(self, mod_report: str, format_type: str = "report",
            timestamp: str = "", idea: str = "") -> str:
        fmt = format_type.lower()
        system = _FORMAT_SYSTEMS.get(fmt, _FORMAT_SYSTEMS["report"])
        print(f"[Nanny] Generating output as: {fmt}")

        user = (
            f"**Research Topic:** {idea}\n\n"
            f"### Atomic Insights (from Mod):\n{mod_report}\n\n"
            "Generate the final deliverable. Be thorough and detailed — "
            "this is the permanent record of the research session. "
            "Preserve all LaTeX formatting."
        )

        report = self.call_llm(system, user)
        self.write_handoff("nanny", report)

        # ── Full archive ──
        ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M")
        research_path = HANDOFF_DIR / f"research_{ts}.md"
        research_path.write_text(
            self._build_mission(idea, ts, report, fmt),
            encoding="utf-8",
        )
        print(f"    → research_{ts}.md  (archived)")

        # ── Trace folder: preserve each agent's handoff for this session ──
        trace_dir = HANDOFF_DIR / f"trace_{ts}"
        trace_dir.mkdir(parents=True, exist_ok=True)
        for agent in ("dao", "builder", "cherry", "nam", "audit", "mod", "nanny"):
            content = self.read_handoff(agent)
            if not content.startswith("[Handoff not found"):
                (trace_dir / f"handoff_{agent}.md").write_text(content, encoding="utf-8")
        print(f"    → trace_{ts}/  (agent handoffs)")

        # ── Abstract: condensed version in the same format ──
        abstract_system = _BRIEF_SYSTEMS.get(fmt, _BRIEF_SYSTEMS["report"])
        all_handoffs = ""
        for agent, label in [
            ("dao",   "[Dao] Discovery & Gap Analysis"),
            ("cherry","[Cherry] Blind-Spot Sweep"),
            ("nam",   "[Nam] Strategic Roadmap"),
            ("audit", "[Som ∥ Manao] Audit"),
            ("mod",   "[Mod] Atomic Insights"),
        ]:
            content = self.read_handoff(agent)
            if not content.startswith("[Handoff not found"):
                all_handoffs += f"\n\n### {label}\n{content[:2500]}"
        abstract_user = f"**Research Topic:** {idea}\n\n{all_handoffs}"
        abstract_output = self.call_llm(abstract_system, abstract_user)

        abstracts_dir = HANDOFF_DIR / "abstracts"
        abstracts_dir.mkdir(parents=True, exist_ok=True)
        (abstracts_dir / f"abstract_{ts}.md").write_text(abstract_output, encoding="utf-8")
        print(f"    → abstracts/abstract_{ts}.md  (condensed {fmt})")

        return report

    def _build_mission(self, idea: str, ts: str, nanny_output: str, fmt: str) -> str:
        """
        Concatenate all agent handoffs into one comprehensive mission file,
        matching the original format from the Gemini sessions.
        """
        sections = [f"# 🧠 Intelligent Research Mission: {idea}\n\n"]

        for agent, label in [
            ("dao",    "[Dao] Discovery & Gap Analysis"),
            ("builder","[Builder] Source Environment"),
            ("cherry", "[Cherry] Blind-Spot Sweep"),
            ("nam",    "[Nam] Strategic Roadmap"),
            ("audit",  "[Som ∥ Manao] Audit"),
            ("mod",    "[Mod] Atomic Insights"),
        ]:
            content = self.read_handoff(agent)
            if not content.startswith("[Handoff not found"):
                sections.append(f"---\n\n### {label}\n\n{content}\n\n")

        sections.append(f"---\n\n### [Nanny] Final Output ({fmt})\n\n{nanny_output}\n")
        return "".join(sections)
