"""Shared base for all pipeline agents."""
import os
import re
import json
import requests
from pathlib import Path

WIKI_DIR = Path("wiki")
HANDOFF_DIR = Path("handoffs")
LOG_DIR = Path("log")
VECTOR_FILE = WIKI_DIR / ".vectors.json"

_MISTRAL_CHAT = "https://api.mistral.ai/v1/chat/completions"
_MISTRAL_EMBED = "https://api.mistral.ai/v1/embeddings"


class BaseAgent:
    MODEL = "mistral-large-latest"
    EMBED_MODEL = "mistral-embed"

    def __init__(self):
        self.api_key = os.environ.get("MISTRAL_API_KEY")
        if not self.api_key:
            raise EnvironmentError(
                "MISTRAL_API_KEY environment variable is not set. "
                "Export it before running the pipeline."
            )
        self._vectors: dict | None = None

    # ------------------------------------------------------------------ LLM

    def call_llm(self, system: str, user: str, timeout: int = 300) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        resp = requests.post(
            _MISTRAL_CHAT,
            headers=headers,
            json={"model": self.MODEL,
                  "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": user}]},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    # ---------------------------------------------------------- Vector search

    def _load_vectors(self) -> dict:
        if self._vectors is None:
            if not VECTOR_FILE.exists():
                self._vectors = {}
            else:
                with open(VECTOR_FILE, encoding="utf-8") as f:
                    self._vectors = json.load(f)
        return self._vectors

    def _embed(self, text: str) -> list[float]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        resp = requests.post(
            _MISTRAL_EMBED,
            headers=headers,
            json={"model": self.EMBED_MODEL, "input": text[:4096]},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]

    def semantic_search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Cosine-similarity search over .vectors.json."""
        try:
            import numpy as np

            vectors = self._load_vectors()
            if not vectors:
                return []
            q = np.array(self._embed(query), dtype=float)
            scores = []
            for fname, data in vectors.items():
                v = np.array(data["vector"], dtype=float)
                score = float(np.dot(q, v) / (np.linalg.norm(q) * np.linalg.norm(v) + 1e-9))
                scores.append((fname, score))
            return sorted(scores, key=lambda x: x[1], reverse=True)[:top_k]
        except Exception:
            return []

    def graph_search(self, query: str, top_k: int = 12, hops: int = 2) -> list[tuple[str, float]]:
        """
        Multi-hop graph search: cosine similarity + wikilink traversal.
        Pages reachable from highly-relevant seeds get a connectivity bonus
        (0.30 for hop-1, 0.15 for hop-2), so conceptually adjacent pages
        surface even without direct keyword matches.
        """
        try:
            import numpy as np

            vectors = self._load_vectors()
            if not vectors:
                return self.semantic_search(query, top_k)

            q = np.array(self._embed(query), dtype=float)

            # Base cosine scores for every indexed page
            base: dict[str, float] = {}
            for fname, data in vectors.items():
                v = np.array(data["vector"], dtype=float)
                base[fname] = float(
                    np.dot(q, v) / (np.linalg.norm(q) * np.linalg.norm(v) + 1e-9)
                )

            bonus: dict[str, float] = {f: 0.0 for f in base}

            # Seeds: top-20 by cosine, then traverse their wikilinks
            seeds = sorted(base, key=lambda f: base[f], reverse=True)[:20]
            visited: set[str] = set(seeds)
            frontier: set[str] = set(seeds)

            for hop in range(1, hops + 1):
                decay = 0.30 / hop  # 0.30 hop-1, 0.15 hop-2
                next_frontier: set[str] = set()
                for fname in frontier:
                    page = WIKI_DIR / fname
                    if not page.exists():
                        continue
                    content = page.read_text(encoding="utf-8", errors="ignore")
                    for link in self.extract_wikilinks(content):
                        linked = f"{link}.md"
                        if linked in base:
                            bonus[linked] = max(bonus[linked], decay * base[fname])
                            if linked not in visited:
                                next_frontier.add(linked)
                                visited.add(linked)
                frontier = next_frontier
                if not frontier:
                    break

            combined = {f: base[f] + bonus[f] for f in base}
            return sorted(combined.items(), key=lambda x: x[1], reverse=True)[:top_k]

        except Exception:
            return self.semantic_search(query, top_k)

    def keyword_search(self, query: str, top_k: int = 10) -> list[str]:
        terms = set(query.lower().split())
        results = []
        for f in WIKI_DIR.glob("*.md"):
            content = f.read_text(encoding="utf-8", errors="ignore").lower()
            hits = sum(1 for t in terms if t in content)
            if hits:
                results.append((f.name, hits))
        return [name for name, _ in sorted(results, key=lambda x: x[1], reverse=True)[:top_k]]

    # ---------------------------------------------------------- Wiki helpers

    def read_wiki_page(self, name: str, max_chars: int = 2500) -> str:
        """Load a wiki page by stem or filename, with fuzzy fallback."""
        candidates = [
            WIKI_DIR / name,
            WIKI_DIR / f"{name}.md",
        ]
        # Also try replacing spaces with dashes and vice versa
        slug = re.sub(r"[\s_]+", "-", name)
        candidates += [WIKI_DIR / f"{slug}.md", WIKI_DIR / f"{slug.replace('-', ' ')}.md"]
        for path in candidates:
            if path.exists():
                return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
        # Last resort: partial filename match
        matches = [p for p in WIKI_DIR.glob("*.md") if name.split("-")[0].lower() in p.name.lower()]
        if matches:
            return matches[0].read_text(encoding="utf-8", errors="ignore")[:max_chars]
        return f"[Page not found: {name}]"

    def extract_wikilinks(self, text: str) -> list[str]:
        return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", text)

    # --------------------------------------------------------- Audit trail

    @staticmethod
    def audit_log(agent: str, operation: str, details: str) -> None:
        from datetime import datetime
        log_path = WIKI_DIR / ".audit-log.md"
        WIKI_DIR.mkdir(exist_ok=True)
        if not log_path.exists():
            log_path.write_text(
                "# Audit Trail\n\n"
                "| Timestamp | Agent | Operation | Details |\n"
                "|-----------|-------|-----------|---------|",
                encoding="utf-8",
            )
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        safe = details.replace("|", "∣").replace("\n", " ")[:120]
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n| {ts} | {agent} | {operation} | {safe} |")

    # --------------------------------------------------------- Handoff I/O

    def read_handoff(self, name: str) -> str:
        path = HANDOFF_DIR / f"handoff_{name.lower()}.md"
        if path.exists():
            return path.read_text(encoding="utf-8", errors="ignore")
        return f"[Handoff not found: {name}]"

    def write_handoff(self, name: str, content: str) -> None:
        HANDOFF_DIR.mkdir(exist_ok=True)
        path = HANDOFF_DIR / f"handoff_{name.lower()}.md"
        path.write_text(content, encoding="utf-8")
        print(f"    → {path.name}")
        self.audit_log(name, "write_handoff", f"{len(content)} chars → {path.name}")
