"""Source adapters: manufacturer websites, retailer pages (future), and mock demo sources.

The mock adapter serves label text from local fixture files so the whole app
can be demoed with zero network access. A mock source_url looks like
``mock://protein_powder_v2`` and maps to ``seed/fixtures/protein_powder_v2.txt``.
"""
import logging
from pathlib import Path

from app.services.scraping.base import FetchResult, SourceAdapter, register_adapter
from app.services.scraping.html_extractor import extract_label_images, extract_text
from app.services.scraping.playwright_fetcher import fetch_page

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "seed" / "fixtures"


class ManufacturerAdapter(SourceAdapter):
    """Generic manufacturer product-page scraper (httpx, Playwright fallback)."""

    source_type = "manufacturer"
    use_playwright = False

    def fetch(self, url: str) -> FetchResult:
        result = fetch_page(url, use_playwright=self.use_playwright)
        if not result.ok:
            # Retry dynamic rendering once for JS-heavy pages before giving up
            if not self.use_playwright and result.error and "robots" not in result.error:
                dynamic = fetch_page(url, use_playwright=True)
                if dynamic.ok:
                    result = dynamic
        if not result.ok or not result.html:
            return result
        result.text = extract_text(result.html)
        result.image_urls = extract_label_images(result.html, url)
        return result


class RetailerAdapter(ManufacturerAdapter):
    """Retailer pages (future). Amazon is intentionally NOT supported in MVP."""

    source_type = "retailer"
    use_playwright = True

    def fetch(self, url: str) -> FetchResult:
        if "amazon." in url.lower():
            return FetchResult(url=url, ok=False,
                               error="Amazon scraping is not supported in the MVP")
        return super().fetch(url)


class MockAdapter(SourceAdapter):
    """Serves label text from seed fixture files. URL format: mock://<fixture_name>."""

    source_type = "mock"

    def fetch(self, url: str) -> FetchResult:
        fixture_name = url.removeprefix("mock://").strip("/")
        path = FIXTURES_DIR / f"{fixture_name}.txt"
        if not path.exists():
            return FetchResult(url=url, ok=False, error=f"Mock fixture not found: {path.name}")
        text = path.read_text(encoding="utf-8")
        return FetchResult(url=url, ok=True, status_code=200, html=None, text=text, fetcher="mock")


class ManualAdapter(SourceAdapter):
    """Manual/uploaded label text: URL is a local file path (future: upload endpoint)."""

    source_type = "manual"

    def fetch(self, url: str) -> FetchResult:
        path = Path(url.removeprefix("file://"))
        if not path.exists():
            return FetchResult(url=url, ok=False, error=f"Manual label file not found: {path}")
        return FetchResult(url=url, ok=True, text=path.read_text(encoding="utf-8"), fetcher="manual")


register_adapter(ManufacturerAdapter())
register_adapter(RetailerAdapter())
register_adapter(MockAdapter())
register_adapter(ManualAdapter())
