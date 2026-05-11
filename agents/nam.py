"""Nam — Synthesizer. Produces exactly 5 strategic research directions."""
from .base import BaseAgent


class NamStrategist(BaseAgent):

    def run(self, dao_report: str, cherry_report: str) -> str:
        print("[Nam] Synthesizing strategic roadmap...")

        system = (
            "You are Nam, the Strategist. You synthesize discovered gaps and blind-spot critiques into "
            "a precise research roadmap with EXACTLY 5 numbered directions.\n\n"
            "Each direction must include:\n"
            "1. **Title** — short, descriptive\n"
            "2. **Rationale** — why this direction matters given the gaps\n"
            "3. **Effort** — Low / Medium / High (with brief justification)\n"
            "4. **Key Risk** — the single most likely failure mode\n"
            "5. **Addresses Cherry's concern** — which blind spot this targets\n\n"
            "Output as numbered Markdown sections (Direction 1 … Direction 5). No more, no fewer."
        )
        user = (
            f"### Dao Report (known knowledge and gaps):\n{dao_report}\n\n"
            f"### Cherry Critique (blind spots and risks):\n{cherry_report}\n\n"
            "Synthesize into EXACTLY 5 strategic directions. Each must address at least one gap "
            "and at least one blind spot identified above."
        )

        report = self.call_llm(system, user)
        self.write_handoff("nam", report)
        return report
