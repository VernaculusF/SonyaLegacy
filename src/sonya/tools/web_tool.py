"""Web tool: search and fetch.

`web.search` uses DuckDuckGo's HTML endpoint (no API key required).
`web.fetch` does a GET with timeout and strips HTML to text-ish output.

Both are blocking-from-the-agent's-POV (called via asyncio.run inside the
sync dispatcher). Limits enforced server-side: 10s request timeout, 200KB
response cap, 5 results per search.
"""
from __future__ import annotations

import asyncio
import html
import re
from urllib.parse import quote_plus, unquote, urlparse

import aiohttp


_USER_AGENT = (
    "Mozilla/5.0 (Sonya/0.1; +https://github.com/VernaculusF/Sonya) "
    "Python-aiohttp"
)
_REQUEST_TIMEOUT = 10.0
_MAX_BODY_BYTES = 200_000
_MAX_RESULTS = 5

# DuckDuckGo HTML endpoint — anonymous, no API key.
_DDG_URL = "https://duckduckgo.com/html/?q={q}"

_SCRIPT_RE = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_STYLE_RE = re.compile(r"<style[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_DDG_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
    r'.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


def _strip_html(s: str) -> str:
    s = _SCRIPT_RE.sub(" ", s)
    s = _STYLE_RE.sub(" ", s)
    s = _TAG_RE.sub(" ", s)
    s = html.unescape(s)
    return _WS_RE.sub(" ", s).strip()


def _decode_ddg_redirect(href: str) -> str:
    """DuckDuckGo wraps result URLs in /l/?uddg=<encoded>. Decode it."""
    if href.startswith("//"):
        href = "https:" + href
    if "uddg=" in href:
        try:
            from urllib.parse import parse_qs
            qs = parse_qs(urlparse(href).query)
            if "uddg" in qs and qs["uddg"]:
                return unquote(qs["uddg"][0])
        except Exception:
            pass
    return href


class WebTool:
    """Agent-facing web tool. All methods return strings."""

    def __init__(self, *, user_agent: str = _USER_AGENT) -> None:
        self._user_agent = user_agent

    # ---------- search ----------

    def search(self, query: str) -> str:
        query = query.strip()
        if not query:
            return "[ERROR] web.search needs a query"
        try:
            return asyncio.run(self._do_search(query))
        except RuntimeError:
            # Already in event loop — fall back to nested via thread.
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, self._do_search(query)).result()
        except Exception as err:
            return f"[ERROR] web.search failed: {type(err).__name__}: {err}"

    async def _do_search(self, query: str) -> str:
        url = _DDG_URL.format(q=quote_plus(query))
        timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
        headers = {"User-Agent": self._user_agent}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return f"[ERROR] DDG returned HTTP {resp.status}"
                body = await resp.read()
                if len(body) > _MAX_BODY_BYTES:
                    body = body[:_MAX_BODY_BYTES]
                text = body.decode("utf-8", errors="ignore")

        results = []
        for match in _DDG_RESULT_RE.finditer(text):
            href, title_html, snippet_html = match.groups()
            title = _strip_html(title_html)
            snippet = _strip_html(snippet_html)
            actual_url = _decode_ddg_redirect(href)
            results.append(f"{title}\n  {actual_url}\n  {snippet}")
            if len(results) >= _MAX_RESULTS:
                break

        if not results:
            return "(no results)"
        return f"Results for: {query}\n\n" + "\n\n".join(results)

    # ---------- fetch ----------

    def fetch(self, url: str) -> str:
        url = url.strip()
        if not url:
            return "[ERROR] web.fetch needs a url"
        if not (url.startswith("http://") or url.startswith("https://")):
            return "[ERROR] web.fetch needs http(s):// URL"
        try:
            return asyncio.run(self._do_fetch(url))
        except RuntimeError:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, self._do_fetch(url)).result()
        except Exception as err:
            return f"[ERROR] web.fetch failed: {type(err).__name__}: {err}"

    async def _do_fetch(self, url: str) -> str:
        timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
        headers = {"User-Agent": self._user_agent}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as resp:
                ctype = resp.headers.get("Content-Type", "").lower()
                body = await resp.read()
                if len(body) > _MAX_BODY_BYTES:
                    body = body[:_MAX_BODY_BYTES]
                preamble = (
                    f"[HTTP {resp.status}] {resp.url}\n"
                    f"Content-Type: {ctype}\n"
                    f"Bytes: {len(body)} (capped at {_MAX_BODY_BYTES})\n\n"
                )
                if "html" in ctype or "xml" in ctype:
                    text = _strip_html(body.decode("utf-8", errors="ignore"))
                else:
                    text = body.decode("utf-8", errors="ignore")
                return preamble + text[:8000]
