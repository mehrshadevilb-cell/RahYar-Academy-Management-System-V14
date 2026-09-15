"""Retrieval-only web research with source prioritisation for music software."""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html import HTMLParser, unescape


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    official: bool = False


# Official documentation/manual hosts. Search results from these hosts are preferred,
# but the assistant may still use reputable third-party sources when official docs do
# not contain the required detail.
OFFICIAL_HOSTS = {
    "steinberg.net": "Cubase",
    "helpcenter.steinberg.de": "Cubase",
    "presonus.com": "Studio One",
    "support.presonus.com": "Studio One",
    "fender.com": "Fender Studio",
    "help.ableton.com": "Ableton Live",
    "ableton.com": "Ableton Live",
    "image-line.com": "FL Studio",
    "support.image-line.com": "FL Studio",
    "waves.com": "Waves",
    "support.waves.com": "Waves",
    "arturia.com": "Arturia",
    "support.arturia.com": "Arturia",
    "izotope.com": "iZotope",
    "support.izotope.com": "iZotope",
}

TOPIC_HOST_HINTS = {
    "cubase": ["site:steinberg.net", "site:helpcenter.steinberg.de"],
    "studio one": ["site:support.presonus.com", "site:presonus.com"],
    "fender studio": ["site:fender.com"],
    "ableton": ["site:help.ableton.com", "site:ableton.com"],
    "fl studio": ["site:image-line.com", "site:support.image-line.com"],
    "waves": ["site:waves.com", "site:support.waves.com"],
    "arturia": ["site:arturia.com", "site:support.arturia.com"],
    "izotope": ["site:izotope.com", "site:support.izotope.com"],
}


class _SearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._href: str | None = None
        self._title: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        classes = (attrs_map.get("class") or "").split()
        if tag == "a" and "result__a" in classes:
            self._href = attrs_map.get("href")
            self._title = []
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_title:
            self._in_title = False
            if self._href and self._title:
                title = re.sub(r"\s+", " ", " ".join(self._title)).strip()
                url = self._normalise_url(self._href)
                if title and url:
                    host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
                    official = any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS)
                    self.results.append(SearchResult(title[:300], url, "", official))
            self._href = None
            self._title = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title.append(data)

    @staticmethod
    def _normalise_url(value: str) -> str:
        value = unescape(value)
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return value
        query = urllib.parse.parse_qs(parsed.query)
        target = query.get("uddg", [""])[0]
        return target if target.startswith(("http://", "https://")) else ""


class WebResearchService:
    USER_AGENT = "RahYar-Academy-Assistant/2.0"
    MAX_RESULTS = 8
    MAX_PAGE_CHARS = 6500

    def _get(self, url: str, timeout: int = 12) -> str:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": self.USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(1_000_000).decode("utf-8", errors="replace")

    def _query_variants(self, query: str) -> list[str]:
        q = re.sub(r"\s+", " ", query).strip()[:600]
        lowered = q.lower()
        variants = [q]
        for topic, hints in TOPIC_HOST_HINTS.items():
            if topic in lowered:
                variants.extend([f"{hint} {q} manual documentation" for hint in hints])
                variants.append(f"{q} official manual documentation")
                break
        return list(dict.fromkeys(variants))[:4]

    def search(self, query: str, limit: int | None = None) -> list[SearchResult]:
        limit = max(1, min(limit or self.MAX_RESULTS, self.MAX_RESULTS))
        unique: list[SearchResult] = []
        seen_urls: set[str] = set()
        seen_hosts: set[str] = set()
        for variant in self._query_variants(query):
            encoded = urllib.parse.urlencode({"q": variant, "kl": "wt-wt", "kp": "1"})
            try:
                html = self._get("https://html.duckduckgo.com/html/?" + encoded)
            except Exception:
                continue
            parser = _SearchParser()
            parser.feed(html)
            for result in parser.results:
                if result.url in seen_urls:
                    continue
                seen_urls.add(result.url)
                host = urllib.parse.urlparse(result.url).netloc.lower().removeprefix("www.")
                if not host:
                    continue
                # Keep several independent hosts, while allowing multiple official docs.
                if host in seen_hosts and not result.official:
                    continue
                seen_hosts.add(host)
                unique.append(result)
                if len(unique) >= limit:
                    return sorted(unique, key=lambda x: (not x.official))[:limit]
        return sorted(unique, key=lambda x: (not x.official))[:limit]

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
        results = self.search(query, limit=limit)
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
                f"SOURCE {index}\nOFFICIAL: {'yes' if result.official else 'no'}\n"
                f"TITLE: {result.title}\nURL: {result.url}\nPAGE TEXT: {body}"
            )
        return "\n\n".join(blocks)
