"""Research engine: aggregate findings from pluggable sources.

Relevance is deterministic term-frequency scoring — same corpus, same query,
same report, always. A broken source never breaks research: its failure just
yields no findings from that source.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

_STOPWORDS = frozenset(
    {
        "the", "and", "for", "with", "from", "this", "that", "into", "are",
        "was", "how", "what", "when", "where", "which", "will", "can",
    }
)


def query_terms(query: str) -> list[str]:
    return [
        term
        for term in re.findall(r"[a-z0-9]+", query.lower())
        if len(term) >= 3 and term not in _STOPWORDS
    ]


def score_text(terms: list[str], text: str) -> float:
    """Prefix word matches per term ("route" also credits "routing")."""
    lowered = text.lower()
    return float(
        sum(len(re.findall(rf"\b{re.escape(term)}", lowered)) for term in terms)
    )


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


@dataclass(frozen=True)
class Finding:
    source: str  # source name
    location: str  # file path, "git:<hash>", or URL
    excerpt: str
    score: float


@dataclass
class ResearchReport:
    query: str
    findings: list[Finding]  # ranked: score desc, then source/location
    sources_consulted: list[str]
    stats: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResearchSource(Protocol):
    name: str

    def search(self, query: str, refs: list[str]) -> list[Finding]: ...


class ResearchEngine:
    """Sources register themselves; research consults all of them and merges
    into one deterministically ranked report — mirroring the capability
    philosophy one level down."""

    def __init__(self) -> None:
        self._sources: list[ResearchSource] = []

    def add_source(self, source: ResearchSource) -> None:
        self._sources.append(source)

    def sources(self) -> list[str]:
        return [s.name for s in self._sources]

    def research(
        self, query: str, refs: list[str] | None = None, top_k: int = 10
    ) -> ResearchReport:
        refs = list(refs or [])
        consulted: list[str] = []
        findings: list[Finding] = []
        for source in self._sources:
            consulted.append(source.name)
            try:
                findings.extend(source.search(query, refs))
            except Exception:  # a broken source never breaks research
                continue
        findings.sort(key=lambda f: (-f.score, f.source, f.location, f.excerpt))
        return ResearchReport(
            query=query,
            findings=findings[:top_k],
            sources_consulted=consulted,
            stats={
                "findings_total": len(findings),
                "sources": len(consulted),
                "refs": refs,
            },
        )
