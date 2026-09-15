"""Read-only web search for the AI agent (no extra dependencies).

Uses DuckDuckGo Instant Answer API first, then a best-effort HTML lite
fallback. Results are text-only snippets for the model context.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html import unescape

USER_AGENT = "RahYar-AIAgent/1.1 (+https://github.com/mehrshadevilb-cell/RahYar-Academy-Management-System-V14)"
MAX_RESULTS = 6
TIMEOUT = 12


def _http_get(url: str, *, timeout: int = TIMEOUT) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _instant_answer(query: str) -> list[dict[str, str]]:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "json",
            "no_redirect": "1",
            "no_html": "1",
            "skip_disambig": "1",
            "t": "rahyar_ai_agent",
        }
    )
    url = f"https://api.duckduckgo.com/?{params}"
    try:
        raw = _http_get(url)
        data = json.loads(raw)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return []

    results: list[dict[str, str]] = []
    abstract = (data.get("AbstractText") or "").strip()
    abstract_url = (data.get("AbstractURL") or "").strip()
    heading = (data.get("Heading") or "").strip()
    if abstract:
        results.append(
            {
                "title": heading or "Instant Answer",
                "url": abstract_url,
                "snippet": abstract[:500],
                "source": "ddg_instant",
            }
        )

    for item in data.get("RelatedTopics") or []:
        if len(results) >= MAX_RESULTS:
            break
        if not isinstance(item, dict):
            continue
        text = (item.get("Text") or "").strip()
        first_url = (item.get("FirstURL") or "").strip()
        if text:
            results.append(
                {
                    "title": text.split(" - ")[0][:120],
                    "url": first_url,
                    "snippet": text[:500],
                    "source": "ddg_related",
                }
            )
        for sub in item.get("Topics") or []:
            if len(results) >= MAX_RESULTS:
                break
            if not isinstance(sub, dict):
                continue
            text = (sub.get("Text") or "").strip()
            first_url = (sub.get("FirstURL") or "").strip()
            if text:
                results.append(
                    {
                        "title": text.split(" - ")[0][:120],
                        "url": first_url,
                        "snippet": text[:500],
                        "source": "ddg_related",
                    }
                )
    return results


def _html_lite(query: str) -> list[dict[str, str]]:
    """Best-effort parse of DuckDuckGo HTML lite results."""
    params = urllib.parse.urlencode({"q": query, "kl": "wt-wt"})
    url = f"https://html.duckduckgo.com/html/?{params}"
    try:
        html = _http_get(url)
    except (urllib.error.URLError, TimeoutError, OSError):
        return []

    results: list[dict[str, str]] = []
    # result blocks: class result__a + result__snippet
    anchors = re.findall(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        flags=re.I | re.S,
    )
    snippets = re.findall(
        r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)>',
        html,
        flags=re.I | re.S,
    )

    def _clean(text: str) -> str:
        text = re.sub(r"<[^>]+>", " ", text)
        return unescape(re.sub(r"\s+", " ", text)).strip()

    for idx, (href, title_html) in enumerate(anchors):
        if len(results) >= MAX_RESULTS:
            break
        title = _clean(title_html)
        snippet = _clean(snippets[idx]) if idx < len(snippets) else ""
        # DDG wraps redirect URLs; keep raw href when possible
        link = href
        if "uddg=" in href:
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            if parsed.get("uddg"):
                link = parsed["uddg"][0]
        if title:
            results.append(
                {
                    "title": title[:160],
                    "url": link[:300],
                    "snippet": snippet[:500],
                    "source": "ddg_html",
                }
            )
    return results


def web_search(query: str, *, max_results: int = MAX_RESULTS) -> str:
    """Search the public web and return a compact text block for the model."""
    query = (query or "").strip()
    if not query:
        return "(empty query)"
    if len(query) > 300:
        query = query[:300]

    results = _instant_answer(query)
    if len(results) < 2:
        for item in _html_lite(query):
            if len(results) >= max_results:
                break
            # de-dupe by URL
            if any(r.get("url") == item.get("url") for r in results):
                continue
            results.append(item)

    if not results:
        return f"No web results for: {query}"

    lines = [f"WEB SEARCH RESULTS for: {query}"]
    for i, item in enumerate(results[:max_results], start=1):
        lines.append(
            f"{i}. {item.get('title') or 'Result'}\n"
            f"   URL: {item.get('url') or '-'}\n"
            f"   {item.get('snippet') or ''}\n"
            f"   source={item.get('source') or '?'}"
        )
    return "\n".join(lines)
