"""Manao — Fact Auditor. Cross-checks claims against the knowledge base."""
from .base import BaseAgent


class ManaoAuditor(BaseAgent):

    def run(self, nam_report: str) -> dict:
        print("[Manao] Running fact audit...")

        # Load wiki pages referenced in the strategy to fact-check against
        links = self.extract_wikilinks(nam_report)[:6]
        wiki_evidence = "\n\n".join(
            f"### [[{link}]]\n{self.read_wiki_page(link, max_chars=1500)}"
            for link in links
        ) or "(no direct wiki references found in strategy)"

        system = (
            "You are Manao, the Fact Auditor. You cross-check factual claims in a research strategy "
            "against available wiki evidence.\n\n"
            "VERDICT: REVISE only for BLOCKING fact issues:\n"
            "- A specific number or metric is stated as fact but directly contradicted by wiki evidence\n"
            "- A paper is cited as supporting something it explicitly does not support\n"
            "- A foundational assumption is factually wrong based on wiki evidence\n\n"
            "VERDICT: PASS if no claims directly contradict the wiki evidence. "
            "Remember: a research STRATEGY proposes directions for NEW work — it is expected to contain "
            "unverified hypotheses, speculative mechanisms, and gaps. These are the POINT of the strategy, "
            "not errors. Do NOT flag speculation, hedged language, or absence of evidence as REVISE "
            "(absence of evidence ≠ evidence of absence).\n\n"
            "Your output MUST start with exactly one of:\n"
            "  VERDICT: PASS\n"
            "  VERDICT: REVISE\n\n"
            "List only BLOCKING contradictions (if REVISE). "
            "Put speculative or unverified items under '## Recommendations' — these do not affect the verdict."
        )
        user = (
            f"### Strategy to Audit:\n{nam_report}\n\n"
            f"### Available Wiki Evidence:\n{wiki_evidence}\n\n"
            "Check only for direct factual contradictions with the wiki evidence. "
            "Speculation and unverified hypotheses are expected and should NOT trigger REVISE."
        )

        result = self.call_llm(system, user)
        verdict = "PASS" if result.strip().startswith("VERDICT: PASS") else "REVISE"
        return {"agent": "Manao", "verdict": verdict, "report": result}
