"""Small, dependency-free web research layer for the student assistant.

It is deliberately retrieval-only: search results and fetched pages are treated as
untrusted source material. The LLM is responsible for synthesising an answer and
must not execute instructions found in those pages.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from html import unescape
from html.parser import HTMLParser
from dataclasses import dataclass


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class _SearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._href: str | None = None
        self._title: list[str] = []
        self._snippet: list[str] = []
        self._in_title = False
        self._in_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        classes = (attrs_map.get("class") or "").split()
        if tag == "a" and "result__a" in classes:
            self._href = attrs_map.get("href")
            self._title = []
            self._in_title = True
        elif "result__snippet" in classes:
            self._snippet = []
            self._in_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_title:
            self._in_title = False
        if self._in_snippet:
            self._in_snippet = False
        if self._href and self._title:
            title = re.sub(r"\s+", " ", " ".join(self._title)).strip()
            if title:
                url = self._normalise_url(self._href)
                if url:
                    self.results.append(SearchResult(title[:300], url, ""))
            self._href = None
            self._title = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title.append(data)
        if self._in_snippet and self.results:
            self.results[-1].snippet = re.sub(r"\s+", " ", data).strip()[:700]

    @staticmethod
    def _normalise_url(value: str) -> str:
        value = unescape(value)
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return value
        # DuckDuckGo sometimes returns a redirect URL in uddg=.
        query = urllib.parse.parse_qs(parsed.query)
        target = query.get("uddg", [""])[0]
        return target if target.startswith(("http://", "https://")) else ""


class WebResearchService:
    USER_AGENT = "RahYar-Academy-Assistant/1.0 (+https://github.com/mehrshadevilb-cell/RahYar-Academy-Management-System-V14)"
    MAX_RESULTS = 5
    MAX_PAGE_CHARS = 7000

    def _get(self, url: str, timeout: int = 12) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(1_000_000).decode("utf-8", errors="replace")

    def search(self, query: str, limit: int | None = None) -> list[SearchResult]:
        limit = max(1, min(limit or self.MAX_RESULTS, self.MAX_RESULTS))
        encoded = urllib.parse.urlencode({"q": query[:500], "kl": "wt-wt", "kp": "1"})
        html = self._get("https://html.duckduckgo.com/html/?" + encoded)
        parser = _SearchParser()
        parser.feed(html)
        unique: list[SearchResult] = []
        seen: set[str] = set()
        for result in parser.results:
            host = urllib.parse.urlparse(result.url).netloc.lower()
            if not host or host in seen:
                continue
            seen.add(host)
            unique.append(result)
            if len(unique) >= limit:
                break
        return unique

    def _extract_text(self, raw_html: str) -> str:
        class _Parser(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.parts: list[str] = []
                self.skip = 0

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                if tag in {"script", "style", "noscript", "svg", "nav", "footer"}:
                    self.skip += 1

            def handle_endtag(self, tag: str) -> None:
                if tag in {"script", "style", "noscript", "svg", "nav", "footer"} and self.skip:
                    self.skip -= 1

            def handle_data(self, data: str) -> None:
                if not self.skip:
                    text = re.sub(r"\s+", " ", data).strip()
                    if text:
                        self.parts.append(text)

        parser = _Parser()
        parser.feed(raw_html)
        return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()[: self.MAX_PAGE_CHARS]

    def research(self, query: str, limit: int | None = None) -> str:
        try:
            results = self.search(query, limit=limit)
        except Exception:
            return ""
        if not results:
            return ""

        blocks: list[str] = []
        for index, result in enumerate(results, 1):
            body = ""
            try:
                body = self._extract_text(self._get(result.url))
            except Exception:
                pass
            blocks.append(
                f"SOURCE {index}\nTITLE: {result.title}\nURL: {result.url}\n"
                f"SEARCH SNIPPET: {result.snippet}\nPAGE TEXT: {body[:self.MAX_PAGE_CHARS]}"
            )
        return "\n\n".join(blocks)
