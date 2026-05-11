"""Nanny — Output Writer. Formats insights into the user-chosen deliverable."""
from datetime import datetime
from .base import BaseAgent, HANDOFF_DIR

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

        # Archived mission file: header + all agent handoffs + formatted output
        ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M")
        mission_path = HANDOFF_DIR / f"mission_{ts}.md"
        mission_path.write_text(
            self._build_mission(idea, ts, report, fmt),
            encoding="utf-8",
        )
        print(f"    → {mission_path.name}  (archived)")

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
