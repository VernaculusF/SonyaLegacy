"""BrowserTool — Playwright sync wrapper, persistent profile, headless by default.

Соня использует когда `web.fetch` недостаточно: JS-render, формы, login flows,
captcha (через сторонние solver-сервисы), скриншоты, выполнение JS на странице.

Tool family `browser.*`:
  browser.open <url>             — открыть URL в singleton-странице
  browser.click <selector>       — клик по CSS selector
  browser.fill <selector>|<value>— заполнить поле
  browser.text <selector>        — innerText (если selector пуст — весь body)
  browser.eval <js>              — выполнить JS, вернуть JSON-результат
  browser.screenshot [path]      — сохранить PNG (default ~/.sonya/screenshots/)
  browser.wait <selector>        — ждать появления selector до 15с
  browser.close                  — закрыть browser сессию

Особенности:
  - Persistent context в `~/.sonya/browser-profile/` — куки/storage сохраняются
    между сессиями. Логинется один раз — помнит.
  - Headless по умолчанию (`SONYA_BROWSER_HEADLESS=0` чтобы открыть видимое окно).
  - Lazy import: если playwright не установлен — каждый tool возвращает [ERROR]
    с инструкцией установить.

Lifecycle:
  - Browser создаётся при первом `browser.open` и переиспользуется до `browser.close`
    или процесс рестарта.
  - Чтобы переключиться на чистый профиль: вручную удалить `~/.sonya/browser-profile/`.

Установка (deploy/update.sh должен это делать):
  pip install playwright
  python -m playwright install chromium
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_PROFILE_DIR = Path.home() / ".sonya" / "browser-profile"
_SCREENSHOT_DIR = Path.home() / ".sonya" / "screenshots"


class BrowserTool:
    """Singleton-style Playwright wrapper. One persistent browser per process."""

    def __init__(self) -> None:
        self._playwright = None
        self._context = None
        self._page = None

    # ---------- lifecycle ----------

    def _ensure(self) -> str | None:
        """Lazy-init Playwright + persistent context. Returns error string if can't init."""
        if self._page is not None:
            return None
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return (
                "[ERROR] Playwright не установлен. Установить:\n"
                "  pip install playwright\n"
                "  python -m playwright install chromium\n"
                "После — перезапустить core."
            )
        try:
            _PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            self._playwright = sync_playwright().start()
            headless_env = os.environ.get("SONYA_BROWSER_HEADLESS", "1").lower()
            headless = headless_env not in ("0", "false", "no", "off")
            self._context = self._playwright.chromium.launch_persistent_context(
                str(_PROFILE_DIR),
                headless=headless,
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
                ),
            )
            pages = self._context.pages
            self._page = pages[0] if pages else self._context.new_page()
            self._page.set_default_timeout(15000)
            return None
        except Exception as e:
            return f"[ERROR] Browser init failed: {type(e).__name__}: {e}"

    def close(self, _arg: str = "") -> str:
        try:
            if self._context is not None:
                self._context.close()
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass
        finally:
            self._page = None
            self._context = None
            self._playwright = None
        return "[OK] browser closed"

    # ---------- nav ----------

    def open(self, url: str) -> str:
        url = (url or "").strip()
        if not url:
            return "[ERROR] browser.open: укажи URL"
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        err = self._ensure()
        if err:
            return err
        try:
            response = self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            status = response.status if response else 0
            title = self._page.title()
            curr_url = self._page.url
            return (
                f"[OK] opened (status={status})\n"
                f"  url:   {curr_url}\n"
                f"  title: {title}"
            )
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"

    def wait_for(self, arg: str) -> str:
        sel = (arg or "").strip()
        if not sel:
            return "[ERROR] browser.wait: укажи CSS selector"
        err = self._ensure()
        if err:
            return err
        try:
            self._page.wait_for_selector(sel, timeout=15000)
            return f"[OK] selector visible: {sel}"
        except Exception as e:
            return f"[ERROR] timeout / not found: {sel} ({e})"

    # ---------- interaction ----------

    def click(self, arg: str) -> str:
        sel = (arg or "").strip()
        if not sel:
            return "[ERROR] browser.click: укажи selector"
        err = self._ensure()
        if err:
            return err
        try:
            self._page.click(sel, timeout=10000)
            return f"[OK] clicked: {sel}"
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"

    def fill(self, arg: str) -> str:
        """`<selector>|<value>` — заполнить input/textarea."""
        sep = arg.find("|")
        if sep < 0:
            return "[ERROR] browser.fill: формат `<selector>|<value>`"
        sel = arg[:sep].strip()
        val = arg[sep + 1:]
        if not sel:
            return "[ERROR] browser.fill: пустой selector"
        err = self._ensure()
        if err:
            return err
        try:
            self._page.fill(sel, val, timeout=10000)
            return f"[OK] filled: {sel} = {val[:50]!r}{'...' if len(val) > 50 else ''}"
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"

    # ---------- read ----------

    def text(self, arg: str) -> str:
        """Selector → innerText. Empty selector → весь body (capped at 12000 chars)."""
        sel = (arg or "").strip()
        err = self._ensure()
        if err:
            return err
        try:
            if sel:
                node = self._page.query_selector(sel)
                if not node:
                    return f"[ERROR] not found: {sel}"
                return node.inner_text()[:12000]
            return self._page.inner_text("body")[:12000]
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"

    def eval_js(self, js: str) -> str:
        if not js.strip():
            return "[ERROR] browser.eval: пустой js"
        err = self._ensure()
        if err:
            return err
        try:
            result = self._page.evaluate(js)
            try:
                return json.dumps(result, ensure_ascii=False)[:6000]
            except Exception:
                return str(result)[:6000]
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"

    def screenshot(self, arg: str = "") -> str:
        err = self._ensure()
        if err:
            return err
        try:
            target = (arg or "").strip()
            if not target:
                ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
                target = str(_SCREENSHOT_DIR / f"shot-{ts}.png")
            self._page.screenshot(path=target, full_page=True)
            return f"[OK] screenshot saved: {target}"
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"
