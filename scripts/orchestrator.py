#!/usr/bin/env python3
"""
Research pipeline orchestrator.

Usage (from repo root):
    python scripts/orchestrator.py "Your research question here"

Requires:
    MISTRAL_API_KEY environment variable
"""
import os
import sys
import json
import threading
from pathlib import Path
from datetime import datetime

# Load API keys from ~/.bash_env if not already in environment
_bash_env = Path.home() / ".bash_env"
if _bash_env.exists():
    for _line in _bash_env.read_text().splitlines():
        if _line.startswith("export ") and "=" in _line:
            _k, _, _v = _line[len("export "):].partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip('"'))

# Allow imports from the pipeline code home (where this script lives)
_PIPELINE_HOME = Path(__file__).parent.parent
sys.path.insert(0, str(_PIPELINE_HOME))

# Validate CWD looks like a vault (has raw/ or wiki/)
if not (Path("raw").exists() or Path("wiki").exists()):
    print("Error: no raw/ or wiki/ folder found in the current directory.")
    print(f"  CWD: {Path.cwd()}")
    print("  cd into your vault folder first, then run orchestrator.")
    sys.exit(1)

from agents.dao import DaoLibrarian
from agents.builder import BuilderAgent
from agents.cherry import CherryAgent
from agents.nam import NamStrategist
from agents.som import SomAuditor
from agents.manao import ManaoAuditor
from agents.mod import ModDistiller
from agents.nanny import NannyAgent
from agents.base import HANDOFF_DIR

STATE_FILE = HANDOFF_DIR / "pipeline_state.json"


# ----------------------------------------------------------------- helpers

def _checkpoint(number: int, message: str, handoff: str | None = None) -> str:
    sep = "=" * 60
    print(f"\n{sep}\n🛑  CHECKPOINT {number}\n{sep}")
    if handoff:
        path = HANDOFF_DIR / f"handoff_{handoff}.md"
        if path.exists():
            content = path.read_text(encoding="utf-8")
            # Print at most 120 lines so the terminal doesn't flood
            lines = content.splitlines()
            print("\n".join(lines[:120]))
            if len(lines) > 120:
                print(f"\n... ({len(lines) - 120} more lines — open handoffs/handoff_{handoff}.md for full view)")
            print(sep)
    print(message)
    print(sep)
    return input("→ ").strip()


def _save_state(state: dict) -> None:
    HANDOFF_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _parallel_audit(nam_report: str, cherry_report: str) -> dict:
    """Run Som and Manao concurrently, then merge their verdicts."""
    results: dict = {}
    errors: dict = {}

    def run_som():
        try:
            results["som"] = SomAuditor().run(nam_report, cherry_report)
        except Exception as e:
            errors["som"] = str(e)
            results["som"] = {"agent": "Som", "verdict": "REVISE", "report": f"Error: {e}"}

    def run_manao():
        try:
            results["manao"] = ManaoAuditor().run(nam_report)
        except Exception as e:
            errors["manao"] = str(e)
            results["manao"] = {"agent": "Manao", "verdict": "REVISE", "report": f"Error: {e}"}

    t1 = threading.Thread(target=run_som, daemon=True)
    t2 = threading.Thread(target=run_manao, daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    combined = (
        f"### [Som] Logic Audit\n{results['som']['report']}\n\n"
        f"### [Manao] Fact Audit\n{results['manao']['report']}"
    )
    overall = (
        "PASS"
        if results["som"]["verdict"] == "PASS" and results["manao"]["verdict"] == "PASS"
        else "REVISE"
    )
    return {"verdict": overall, "combined_report": combined, "details": results}


# ----------------------------------------------------------------- pipeline

def run_pipeline(idea: str) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    state = {"idea": idea, "timestamp": timestamp, "stage": "start"}
    _save_state(state)

    print(f"\n🚀  PIPELINE START\n    {idea}\n")

    # ── Dao ──────────────────────────────────────────────────────────────
    print("── [Dao] ──")
    dao_report = DaoLibrarian().run(idea)
    state["stage"] = "dao_done"
    _save_state(state)

    response = _checkpoint(
        1,
        "Press Enter to approve, or type 'stop' to abort:",
        handoff="dao",
    )
    if response.lower() == "stop":
        print("Pipeline aborted at CP1.")
        return

    # ── Builder ───────────────────────────────────────────────────────────
    print("\n── [Builder] ──")
    builder_context = BuilderAgent().run(dao_report)
    state["stage"] = "builder_done"
    _save_state(state)

    # ── Cherry ────────────────────────────────────────────────────────────
    print("\n── [Cherry] ──")
    cherry_report = CherryAgent().run(dao_report, builder_context)
    state["stage"] = "cherry_done"
    _save_state(state)

    # ── Nam ───────────────────────────────────────────────────────────────
    print("\n── [Nam] ──")
    nam_report = NamStrategist().run(dao_report, cherry_report)
    state["stage"] = "nam_done"
    _save_state(state)

    direction_pick = _checkpoint(
        2,
        "Type direction numbers to focus on (e.g. '1,3') or press Enter for all:",
        handoff="nam",
    )
    if direction_pick.lower() == "stop":
        print("Pipeline aborted at CP2.")
        return
    if direction_pick:
        nam_report += f"\n\n> **PK Selection:** Focus on directions {direction_pick}."

    # ── Som ∥ Manao (parallel audit, up to 2 retries) ────────────────────
    audit: dict = {}
    for attempt in range(1, 3):
        print(f"\n── [Som ∥ Manao] — attempt {attempt}/2 ──")
        audit = _parallel_audit(nam_report, cherry_report)

        # Write combined audit handoff
        (HANDOFF_DIR / "handoff_audit.md").write_text(
            audit["combined_report"], encoding="utf-8"
        )
        print(f"    → handoff_audit.md")

        if audit["verdict"] == "PASS":
            print("    ✅  Audit: PASS")
            break

        print(f"    ⚠️   Audit: REVISE (attempt {attempt})")
        if attempt < 2:
            # Silent revision: feed audit feedback back to Nam
            print("\n── [Nam] Silent revision ──")
            feedback_prompt = dao_report + f"\n\n**Audit Feedback (attempt {attempt}):**\n{audit['combined_report']}"
            nam_report = NamStrategist().run(feedback_prompt, cherry_report)
        else:
            # Second failure: notify user (soft interrupt)
            _checkpoint(
                0,
                "⚠️  Audit failed twice. Press Enter to continue anyway, or 'stop' to abort:",
                handoff="audit",
            )

    state["stage"] = "audit_done"
    _save_state(state)

    # ── Mod ───────────────────────────────────────────────────────────────
    print("\n── [Mod] ──")
    mod_report = ModDistiller().run(nam_report, audit["combined_report"], idea)
    state["stage"] = "mod_done"
    _save_state(state)

    fmt_input = _checkpoint(
        3,
        "Choose output format — marp / report / obsidian  (default: report):",
        handoff="mod",
    )
    if fmt_input.lower() == "stop":
        print("Pipeline aborted at CP3.")
        return
    fmt = fmt_input.lower() if fmt_input.lower() in ("marp", "report", "obsidian") else "report"

    # ── Nanny ─────────────────────────────────────────────────────────────
    print(f"\n── [Nanny] ──")
    NannyAgent().run(mod_report, fmt, timestamp=timestamp, idea=idea)
    state["stage"] = "complete"
    _save_state(state)

    print(f"\n🏁  MISSION COMPLETE")
    print(f"    Archived → handoffs/mission_{timestamp}.md")
    print(f"    Wiki page  → wiki/concepts/\n")


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    run_pipeline(" ".join(sys.argv[1:]))
