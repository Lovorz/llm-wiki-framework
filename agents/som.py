"""Som — Logic Auditor. Verifies internal consistency of the research strategy."""
from .base import BaseAgent


class SomAuditor(BaseAgent):

    def run(self, nam_report: str, cherry_report: str) -> dict:
        print("[Som] Running logic audit...")

        system = (
            "You are Som, the Logic Auditor. You verify the internal logical consistency of a research strategy.\n\n"
            "VERDICT: REVISE only if you find BLOCKING issues — ones that would make a direction "
            "fundamentally unworkable or self-contradictory:\n"
            "- A direction directly contradicts another (not just sequential dependency — real contradiction)\n"
            "- An effort estimate is so wrong it would mislead resource planning (e.g., 'Low' for a 3-year project)\n"
            "- A direction is entirely disconnected from the stated gaps\n"
            "- An unfalsifiable claim is the *core* of a direction (not a minor hedge)\n\n"
            "VERDICT: PASS if the strategy is logically coherent overall, even if imperfect. "
            "Research strategies are inherently provisional — minor hedging, sequential dependencies, "
            "and open-ended risks are NORMAL and should NOT trigger REVISE.\n\n"
            "Your output MUST start with exactly one of:\n"
            "  VERDICT: PASS\n"
            "  VERDICT: REVISE\n\n"
            "Then: list any blocking issues (if REVISE) or summarise confirmed strengths (if PASS). "
            "Note minor concerns separately under '## Minor Notes' — these do not affect the verdict."
        )
        user = (
            f"### Strategy (from Nam):\n{nam_report}\n\n"
            f"### Blind Spots (from Cherry):\n{cherry_report}\n\n"
            "Audit for BLOCKING logical issues only. Minor issues go under Minor Notes and do not change the verdict."
        )

        result = self.call_llm(system, user)
        verdict = "PASS" if result.strip().startswith("VERDICT: PASS") else "REVISE"
        return {"agent": "Som", "verdict": verdict, "report": result}
