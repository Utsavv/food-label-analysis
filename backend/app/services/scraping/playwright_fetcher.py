"""Page fetching: httpx for static pages, Playwright (if installed) for dynamic ones.

Etiquette: robots.txt is checked, requests are rate-limited per host, and a
clear bot user-agent is sent. Anti-bot systems are never bypassed — a blocked
fetch is reported as a failed run.
"""
import logging
import threading
import time
import urllib.robotparser
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.services.scraping.base import FetchResult

logger = logging.getLogger(__name__)
settings = get_settings()

_last_request_at: dict[str, float] = {}
_rate_lock = threading.Lock()
_robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}


def _rate_limit(host: str) -> None:
    with _rate_lock:
        last = _last_request_at.get(host, 0.0)
        wait = settings.scraper_min_delay_seconds - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        _last_request_at[host] = time.monotonic()


def robots_allows(url: str) -> bool:
    if not settings.respect_robots_txt:
        return True
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    rp = _robots_cache.get(base)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            resp = httpx.get(
                f"{base}/robots.txt",
                headers={"User-Agent": settings.scraper_user_agent},
                timeout=10.0,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            else:
                rp.parse([])  # no robots.txt -> allowed
        except httpx.HTTPError:
            rp.parse([])  # unreachable robots.txt -> assume allowed, but log
            logger.warning("Could not fetch robots.txt for %s", base)
        _robots_cache[base] = rp
    return rp.can_fetch(settings.scraper_user_agent, url)


def fetch_page(url: str, use_playwright: bool = False) -> FetchResult:
    """Fetch a page politely. Falls back from Playwright to httpx if unavailable."""
    if not robots_allows(url):
        return FetchResult(url=url, ok=False, error="Blocked by robots.txt — not fetching")

    _rate_limit(urlparse(url).netloc)

    if use_playwright:
        result = _fetch_with_playwright(url)
        if result is not None:
            return result
        logger.info("Playwright unavailable, falling back to httpx for %s", url)

    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": settings.scraper_user_agent},
            timeout=settings.scraper_timeout_seconds,
            follow_redirects=True,
        )
        if resp.status_code >= 400:
            return FetchResult(url=url, ok=False, status_code=resp.status_code,
                               error=f"HTTP {resp.status_code}")
        return FetchResult(url=url, ok=True, status_code=resp.status_code, html=resp.text)
    except httpx.HTTPError as exc:
        return FetchResult(url=url, ok=False, error=f"Fetch failed: {exc}")


def _fetch_with_playwright(url: str) -> FetchResult | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=settings.scraper_user_agent)
            page.goto(url, timeout=int(settings.scraper_timeout_seconds * 1000))
            page.wait_for_load_state("networkidle", timeout=15000)
            html = page.content()
            browser.close()
        return FetchResult(url=url, ok=True, status_code=200, html=html, fetcher="playwright")
    except Exception as exc:  # playwright raises its own error types
        return FetchResult(url=url, ok=False, error=f"Playwright fetch failed: {exc}", fetcher="playwright")
