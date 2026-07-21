"""Research sources: documentation trees, repositories, and given web refs.

Each source filters the refs it understands and degrades gracefully —
unreadable files are skipped, a failed fetch yields no findings, git-history
search silently steps aside when git or a .git directory is absent.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request
from html.parser import HTMLParser
from typing import Callable

from nexus.research.engine import Finding, paragraphs, query_terms, score_text

_EXCERPT_CHARS = 300
_MAX_FILE_BYTES = 512 * 1024
_MAX_FINDINGS_PER_SOURCE = 50

_DOC_EXTENSIONS = (".md", ".txt", ".rst", ".adoc")
_CODE_EXTENSIONS = _DOC_EXTENSIONS + (
    ".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".h", ".cpp",
    ".sh", ".toml", ".yaml", ".yml", ".json", ".cfg", ".ini",
)


class _FileTreeSource:
    def __init__(self, root: str, name: str, extensions: tuple[str, ...]) -> None:
        self.root = root
        self.name = name
        self._extensions = extensions

    def search(self, query: str, refs: list[str]) -> list[Finding]:
        terms = query_terms(query)
        if not terms:
            return []
        findings: list[Finding] = []
        for rel_path, text in self._files():
            for para in paragraphs(text):
                score = score_text(terms, para)
                if score > 0:
                    findings.append(
                        Finding(
                            source=self.name,
                            location=rel_path,
                            excerpt=para[:_EXCERPT_CHARS],
                            score=score,
                        )
                    )
        findings.sort(key=lambda f: (-f.score, f.location, f.excerpt))
        return findings[:_MAX_FINDINGS_PER_SOURCE]

    def _files(self):
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            for filename in sorted(filenames):
                if not filename.lower().endswith(self._extensions):
                    continue
                path = os.path.join(dirpath, filename)
                try:
                    if os.path.getsize(path) > _MAX_FILE_BYTES:
                        continue
                    with open(path, encoding="utf-8", errors="strict") as f:
                        text = f.read()
                except (OSError, UnicodeDecodeError):
                    continue
                yield os.path.relpath(path, self.root), text


class DocumentationSource(_FileTreeSource):
    """Searches a documentation tree (markdown, text, rst). Ignores refs —
    it always covers its configured root."""

    def __init__(self, root: str, name: str = "docs.local") -> None:
        super().__init__(root, name, _DOC_EXTENSIONS)


class RepositorySource(_FileTreeSource):
    """Searches a repository: source/doc files plus git commit history when
    git and a .git directory are available."""

    def __init__(self, root: str, name: str = "repo.local", history_limit: int = 200) -> None:
        super().__init__(root, name, _CODE_EXTENSIONS)
        self._history_limit = history_limit

    def search(self, query: str, refs: list[str]) -> list[Finding]:
        findings = super().search(query, refs)
        findings.extend(self._history_findings(query))
        findings.sort(key=lambda f: (-f.score, f.location, f.excerpt))
        return findings[:_MAX_FINDINGS_PER_SOURCE]

    def _history_findings(self, query: str) -> list[Finding]:
        if not os.path.isdir(os.path.join(self.root, ".git")) or not shutil.which("git"):
            return []
        terms = query_terms(query)
        if not terms:
            return []
        try:
            proc = subprocess.run(
                ["git", "log", f"-n{self._history_limit}", "--pretty=%h\t%s"],
                cwd=self.root, capture_output=True, text=True, timeout=10, check=True,
            )
        except Exception:
            return []
        findings = []
        for line in proc.stdout.splitlines():
            commit_hash, _, subject = line.partition("\t")
            score = score_text(terms, subject)
            if score > 0:
                findings.append(
                    Finding(
                        source=self.name,
                        location=f"git:{commit_hash}",
                        excerpt=subject[:_EXCERPT_CHARS],
                        score=score,
                    )
                )
        return findings


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "head", "noscript"}
    _BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br",
              "section", "article", "tr"}

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BLOCK:
            self._chunks.append("\n\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in self._BLOCK:
            self._chunks.append("\n\n")

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._chunks.append(data)

    def text(self) -> str:
        return "".join(self._chunks)


def _default_fetcher(url: str, timeout: float = 10.0) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="replace")


class WebSource:
    """Reads the http(s) refs it is given — deliberately no search-engine
    dependency in V1. The fetcher is injectable (tests use stubs; the default
    uses stdlib urllib)."""

    def __init__(
        self,
        fetcher: Callable[[str], str] | None = None,
        name: str = "web.local",
    ) -> None:
        self.name = name
        self._fetch = fetcher or _default_fetcher

    def search(self, query: str, refs: list[str]) -> list[Finding]:
        terms = query_terms(query)
        if not terms:
            return []
        findings: list[Finding] = []
        for url in refs:
            if not url.startswith(("http://", "https://")):
                continue
            try:
                raw = self._fetch(url)
            except Exception:
                continue  # a dead ref yields nothing, never an error
            for para in paragraphs(self._to_text(raw)):
                score = score_text(terms, para)
                if score > 0:
                    findings.append(
                        Finding(
                            source=self.name,
                            location=url,
                            excerpt=para[:_EXCERPT_CHARS],
                            score=score,
                        )
                    )
        findings.sort(key=lambda f: (-f.score, f.location, f.excerpt))
        return findings[:_MAX_FINDINGS_PER_SOURCE]

    @staticmethod
    def _to_text(raw: str) -> str:
        if "<" not in raw:
            return raw
        extractor = _TextExtractor()
        extractor.feed(raw)
        return extractor.text()
