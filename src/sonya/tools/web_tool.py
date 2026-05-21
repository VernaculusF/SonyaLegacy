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


def _run_async(coro):
    """Run an async coroutine from sync code, handling 'already in event loop'.

    Tool dispatch sits inside an async ReAct loop, so when WebTool.search is
    called we are always inside a running event loop. asyncio.run() refuses
    to run nested loops. We use a one-shot thread with its own loop.

    The coroutine is constructed by the caller (e.g. self._do_search(q)).
    Importantly, we always submit the SAME coroutine — never recreate it
    after the first attempt — to avoid 'coroutine was never awaited' warnings.
    """
    import concurrent.futures
    try:
        # If there's no running loop, asyncio.run is the simplest path.
        asyncio.get_running_loop()
    except RuntimeError:
        # No event loop in this thread — safe to use asyncio.run directly.
        return asyncio.run(coro)
    # Running loop exists. Run coro on a separate thread+loop.
    def _runner():
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result()


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
            return _run_async(self._do_search(query))
        except Exception as err:
            return f"[ERROR] web.search failed: {type(err).__name__}: {err}"

    async def _do_search(self, query: str) -> str:
        url = _DDG_URL.format(q=quote_plus(query))
        timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)
        headers = {
            "User-Agent": self._user_agent,
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        }
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            # Try DDG first
            try:
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status == 200:
                        body = await resp.read()
                        if len(body) > _MAX_BODY_BYTES:
                            body = body[:_MAX_BODY_BYTES]
                        text = body.decode("utf-8", errors="ignore")
                        results = self._parse_ddg_results(text, query)
                        if results:
                            return results
            except Exception:
                pass

            # Fallback: Google HTML scrape (no API key)
            try:
                google_url = f"https://www.google.com/search?q={quote_plus(query)}&num=5&hl=en"
                async with session.get(google_url, allow_redirects=True) as resp:
                    if resp.status == 200:
                        body = await resp.read()
                        if len(body) > _MAX_BODY_BYTES:
                            body = body[:_MAX_BODY_BYTES]
                        text = body.decode("utf-8", errors="ignore")
                        results = self._parse_google_results(text, query)
                        if results:
                            return results
            except Exception:
                pass

        return (
            "[ERROR] Both DDG and Google search failed. "
            "Search is unavailable — do NOT retry immediately. "
            "If you have a task depending on this, use `tasks.block` and wait."
        )

    def _parse_ddg_results(self, text: str, query: str) -> str:
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
            return ""
        return f"Results for: {query}\n\n" + "\n\n".join(results)

    def _parse_google_results(self, text: str, query: str) -> str:
        """Parse Google HTML search results (best-effort scraping)."""
        results = []
        # Google wraps results in <div class="g"> blocks. Extract title + snippet.
        import re as _re
        # Pattern for result links: <a href="/url?q=ACTUAL_URL&..."><h3>TITLE</h3></a>
        link_re = _re.compile(
            r'<a[^>]+href="/url\?q=([^&"]+)[^"]*"[^>]*>.*?<h3[^>]*>(.*?)</h3>',
            _re.DOTALL,
        )
        # Snippet follows in a nearby <span> or <div>
        snippet_re = _re.compile(
            r'<span[^>]*class="[^"]*(?:st|aCOpRe)[^"]*"[^>]*>(.*?)</span>',
            _re.DOTALL,
        )
        for match in link_re.finditer(text):
            url_encoded, title_html = match.groups()
            title = _strip_html(title_html)
            actual_url = unquote(url_encoded)
            if not actual_url.startswith("http"):
                continue
            # Try to find snippet near this position
            snippet = ""
            snippet_match = snippet_re.search(text, match.end(), match.end() + 2000)
            if snippet_match:
                snippet = _strip_html(snippet_match.group(1))
            results.append(f"{title}\n  {actual_url}\n  {snippet[:200]}")
            if len(results) >= _MAX_RESULTS:
                break

        if not results:
            # Fallback: just extract any visible text with URLs
            return ""
        return f"Results for: {query}\n\n" + "\n\n".join(results)

    # ---------- fetch ----------

    def fetch(self, url: str) -> str:
        url = url.strip()
        if not url:
            return "[ERROR] web.fetch needs a url"
        if not (url.startswith("http://") or url.startswith("https://")):
            return "[ERROR] web.fetch needs http(s):// URL"
        try:
            return _run_async(self._do_fetch(url))
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
