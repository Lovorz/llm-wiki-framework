"""Builder — extracts raw/ PDFs via Mistral OCR into log/, promotes to wiki/, and optionally loads into NotebookLM."""
import os
import re
import sys
import subprocess
import yaml
import requests
import tempfile
import base64
from datetime import datetime
from pathlib import Path
from .base import BaseAgent, WIKI_DIR, LOG_DIR

_MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")  # OCR only — LLM calls use Gemini via BaseAgent

RAW_DIR = Path("raw")
ASSETS_DIR = WIKI_DIR / "assets"
_MISTRAL_FILES = "https://api.mistral.ai/v1/files"
_MISTRAL_OCR = "https://api.mistral.ai/v1/ocr"


class BuilderAgent(BaseAgent):

    def run(self, dao_report: str) -> str:
        print("[Builder] Dual-source extraction: Mistral OCR + NotebookLM (if available)...")

        wikilinks = self.extract_wikilinks(dao_report)[:12]
        raw_sources = self._match_raw_pdfs(wikilinks)

        # 1. Mistral OCR → log/  (primary, always attempted)
        ocr_results = self._extract_all_with_mistral(raw_sources)

        # 1b. Auto-promote newly extracted log/ files → wiki/ claims
        self._auto_promote_new()

        # 2. NotebookLM (optional, adds Q&A capability on top)
        notebook_id, nb_results = self._load_notebooklm(raw_sources)

        # 3. Load existing wiki pages for already-processed sources
        wiki_context = self._load_wiki_context(wikilinks)

        report = self._build_report(ocr_results, notebook_id, nb_results, wiki_context)
        self.write_handoff("builder", report)
        return report

    # ─────────────────────────────────────────── raw/ matching

    def _match_raw_pdfs(self, wikilinks: list[str]) -> list[dict]:
        available = {p.stem: p for p in RAW_DIR.glob("*.pdf")}
        results = []
        for link in wikilinks:
            slug = re.sub(r"[\s_]+", "-", link)
            match = available.get(link) or available.get(slug)
            if not match:
                match = next(
                    (p for stem, p in available.items() if link.lower()[:20] in stem.lower()),
                    None,
                )
            results.append({"name": link, "pdf": match, "path": str(match) if match else None})
        return results

    # ─────────────────────────────────────────── Mistral OCR

    def _extract_all_with_mistral(self, sources: list[dict]) -> list[dict]:
        """Extract each PDF with Mistral OCR and store result in log/."""
        LOG_DIR.mkdir(exist_ok=True)
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)

        for source in sources:
            if not source["pdf"]:
                source["ocr_status"] = "no_pdf"
                source["log_path"] = None
                continue

            log_path = LOG_DIR / f"{source['pdf'].stem}.md"
            wiki_path = WIKI_DIR / f"{source['pdf'].stem}.md"

            # Skip if already in log/ or already promoted to wiki/
            if log_path.exists():
                source["ocr_status"] = "cached"
                source["log_path"] = str(log_path)
                print(f"  [cached/log] {source['name']}")
                continue
            if wiki_path.exists():
                source["ocr_status"] = "cached"
                source["log_path"] = str(wiki_path)
                print(f"  [cached/wiki] {source['name']}")
                continue

            print(f"  [OCR]    {source['name']} ...", end="", flush=True)
            markdown = self._mistral_ocr(source["pdf"])

            if markdown.startswith("Error"):
                source["ocr_status"] = f"failed: {markdown[:80]}"
                source["log_path"] = None
                print(f" ✗")
            else:
                self._write_log_entry(log_path, source, markdown)
                source["ocr_status"] = "extracted"
                source["log_path"] = str(log_path)
                print(f" ✓ ({len(markdown)} chars)")

        return sources

    def _mistral_ocr(self, pdf_path: Path) -> str:
        if not _MISTRAL_API_KEY:
            return "Error: MISTRAL_API_KEY not set — OCR skipped"
        headers = {"Authorization": f"Bearer {_MISTRAL_API_KEY}"}
        try:
            # Upload
            with open(pdf_path, "rb") as f:
                upload = requests.post(
                    _MISTRAL_FILES,
                    headers=headers,
                    files={"file": (pdf_path.name, f, "application/pdf")},
                    data={"purpose": "ocr"},
                    timeout=60,
                )
                upload.raise_for_status()
            file_id = upload.json()["id"]

            # Signed URL
            url_resp = requests.get(
                f"{_MISTRAL_FILES}/{file_id}/url", headers=headers, timeout=30
            )
            url_resp.raise_for_status()
            signed_url = url_resp.json()["url"]

            # OCR
            ocr_resp = requests.post(
                _MISTRAL_OCR,
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "model": "mistral-ocr-latest",
                    "document": {"type": "document_url", "document_url": signed_url},
                    "include_image_base64": False,
                },
                timeout=120,
            )
            ocr_resp.raise_for_status()

            pages = ocr_resp.json().get("pages", [])
            return "\n\n".join(p.get("markdown", "") for p in pages)

        except Exception as e:
            return f"Error: {e}"

    def _write_log_entry(self, log_path: Path, source: dict, markdown: str) -> None:
        frontmatter = {
            "title": source["name"].replace("-", " "),
            "type": "paper",
            "sources": [f"raw/{source['pdf'].name}"],
            "extraction_method": "mistral-ocr-latest",
            "confidence": 1.0,
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
        }
        content = (
            f"---\n{yaml.dump(frontmatter, sort_keys=False, allow_unicode=True)}---\n\n"
            f"# {source['name']}\n\n"
            f"{markdown}"
        )
        log_path.write_text(content, encoding="utf-8")

    # ─────────────────────────────────────────── NotebookLM (optional)

    def _notebooklm_available(self) -> bool:
        try:
            r = subprocess.run(["notebooklm", "--version"], capture_output=True, timeout=10)
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _nb_run(self, args: list[str], timeout: int = 180) -> tuple[bool, str]:
        try:
            r = subprocess.run(
                ["notebooklm"] + args, capture_output=True, text=True, timeout=timeout
            )
            return r.returncode == 0, r.stdout + r.stderr
        except Exception as e:
            return False, str(e)

    def _load_notebooklm(self, sources: list[dict]) -> tuple[str | None, list[dict]]:
        if not self._notebooklm_available():
            print("  [Builder] notebooklm-py not installed — NotebookLM step skipped")
            for s in sources:
                s["nb_status"] = "skipped"
            return None, sources

        ok, out = self._nb_run(["create", "Research Session"])
        notebook_id = None
        if ok:
            m = re.search(r"([a-f0-9\-]{20,})", out)
            notebook_id = m.group(1) if m else None

        if not notebook_id:
            print(f"  [Builder] NotebookLM creation failed")
            for s in sources:
                s["nb_status"] = "creation_failed"
            return None, sources

        print(f"  [Builder] NotebookLM notebook: {notebook_id}")
        self._nb_run(["use", notebook_id])

        for source in sources:
            if not source.get("pdf"):
                source["nb_status"] = "no_pdf"
                continue
            ok, _ = self._nb_run(["source", "add", source["path"]], timeout=180)
            source["nb_status"] = "loaded" if ok else "failed"

        return notebook_id, sources

    # ─────────────────────────────────────────── auto-promote

    def _auto_promote_new(self) -> None:
        """Promote any log/ files that don't yet have a wiki/ counterpart."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        try:
            from wiki_manager import WikiManager
            mgr = WikiManager()
            # Only promote log/ files that are missing from wiki/
            to_promote = [
                f for f in LOG_DIR.glob("*.md")
                if f.name != "log.md" and not (WIKI_DIR / f.name).exists()
            ]
            if to_promote:
                print(f"  [Builder] Auto-promoting {len(to_promote)} new log/ file(s) to wiki/...")
                mgr.promote()
            else:
                print("  [Builder] All log/ files already promoted — skipping.")
        except Exception as e:
            print(f"  [Builder] Auto-promote skipped: {e}")

    # ─────────────────────────────────────────── wiki context

    def _load_wiki_context(self, wikilinks: list[str]) -> str:
        parts = []
        for link in wikilinks:
            content = self.read_wiki_page(link, max_chars=1500)
            if not content.startswith("[Page not found"):
                parts.append(f"### [[{link}]]\n{content}")
        return "\n\n---\n\n".join(parts) or "(no existing wiki pages found)"

    # ─────────────────────────────────────────── report

    def _build_report(
        self,
        sources: list[dict],
        notebook_id: str | None,
        nb_results: list[dict],
        wiki_context: str,
    ) -> str:
        ocr_ok = sum(1 for s in sources if s.get("ocr_status") in ("extracted", "cached"))
        nb_ok = sum(1 for s in sources if s.get("nb_status") == "loaded")

        rows = []
        for s in sources:
            ocr = s.get("ocr_status", "n/a")
            nb = s.get("nb_status", "skipped")
            raw = f"raw/{s['pdf'].name}" if s.get("pdf") else "not in vault"
            log = s.get("log_path") or "—"
            rows.append(f"| {s['name'][:38]} | {ocr} | {nb} | {log} |")

        table = "\n".join(rows)

        cherry_note = (
            f"Query NotebookLM notebook `{notebook_id}` for Q&A, then complement with log/ extractions."
            if notebook_id
            else "NotebookLM unavailable. Use Mistral OCR extractions in log/ as primary source."
        )

        return (
            f"# [Builder] Source Environment Report\n\n"
            f"## Extraction Summary\n"
            f"- Mistral OCR extracted: {ocr_ok}/{len(sources)} (stored in log/)\n"
            f"- NotebookLM loaded: {nb_ok}/{len(sources)} "
            f"(notebook: `{notebook_id or 'N/A'}`)\n\n"
            f"## Source Status\n"
            f"| Source | OCR Status | NotebookLM | log/ Path |\n"
            f"|--------|-----------|------------|----------|\n"
            f"{table}\n\n"
            f"## Local Wiki Context\n{wiki_context[:4000]}\n\n"
            f"## Note for Cherry\n{cherry_note}"
        )
