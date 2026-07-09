"""Extract label-relevant text and label-image URLs from product-page HTML."""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# Sections of a product page likely to contain label information
_LABEL_KEYWORDS = re.compile(
    r"nutrition|ingredient|allergen|serving|fssai|protein|supplement facts|label|"
    r"sugar|sodium|energy|kcal|vegetarian",
    re.IGNORECASE,
)

_IMAGE_LABEL_HINTS = re.compile(r"label|nutrition|ingredient|back|facts|info", re.IGNORECASE)


def extract_text(html: str) -> str:
    """Full visible text, with label-relevant blocks first."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()

    blocks: list[str] = []
    other: list[str] = []
    for element in soup.find_all(["p", "li", "td", "th", "div", "span", "h1", "h2", "h3", "h4"]):
        text = element.get_text(" ", strip=True)
        if not text or len(text) < 3:
            continue
        (blocks if _LABEL_KEYWORDS.search(text) else other).append(text)

    seen: set[str] = set()
    ordered: list[str] = []
    for t in blocks + other:
        if t not in seen and not any(t in s for s in seen):
            seen.add(t)
            ordered.append(t)
    return "\n".join(ordered)


def extract_label_images(html: str, base_url: str) -> list[str]:
    """Find image URLs likely to show the physical label."""
    soup = BeautifulSoup(html, "lxml")
    urls: list[str] = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        alt = img.get("alt") or ""
        if not src:
            continue
        if _IMAGE_LABEL_HINTS.search(src) or _IMAGE_LABEL_HINTS.search(alt):
            absolute = urljoin(base_url, src)
            if absolute not in urls:
                urls.append(absolute)
    return urls
