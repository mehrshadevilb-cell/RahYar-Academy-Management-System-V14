"""Structured knowledge-pack routing for DAWs, plugins and music theory."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PACK_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "music_software" / "knowledge_packs.json"


class MusicKnowledgePackService:
    """Loads curated metadata and turns a user question into retrieval hints."""

    def __init__(self, path: Path = PACK_PATH) -> None:
        self.path = path
        self._data: dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        self._data = json.loads(self.path.read_text(encoding="utf-8"))

    @property
    def packs(self) -> list[dict[str, Any]]:
        return list(self._data.get("packs", []))

    def match(self, question: str) -> list[dict[str, Any]]:
        q = question.casefold()
        scored: list[tuple[int, dict[str, Any]]] = []
        for pack in self.packs:
            score = 0
            for alias in pack.get("aliases", []):
                if alias.casefold() in q:
                    score = max(score, 10 if len(alias) > 4 else 6)
            if pack.get("name", "").casefold() in q:
                score = max(score, 12)
            if score:
                scored.append((score, pack))
        return [pack for _, pack in sorted(scored, key=lambda item: item[0], reverse=True)]

    def retrieval_context(self, question: str) -> str:
        matches = self.match(question)
        if not matches:
            return ""
        lines = ["MUSIC KNOWLEDGE PACK ROUTING:"]
        for pack in matches[:3]:
            lines.append(f"- {pack['name']} ({pack['kind']}) by {pack['vendor']}")
            lines.append("  categories: " + ", ".join(pack.get("categories", [])))
            lines.append("  official domains: " + ", ".join(pack.get("official_domains", [])))
            lines.append("  source hints: " + "; ".join(pack.get("source_hints", [])))
        lines.append("Use the relevant category explicitly: manual, FAQ, workflow, troubleshooting, shortcuts, or version notes.")
        return "\n".join(lines)

    def research_query(self, question: str) -> str:
        matches = self.match(question)
        if not matches:
            return question[:900]
        pack = matches[0]
        domains = " ".join(f"site:{domain}" for domain in pack.get("official_domains", [])[:2])
        return f"{domains} {pack['name']} manual FAQ workflow troubleshooting shortcuts release notes {question[:700]}"
