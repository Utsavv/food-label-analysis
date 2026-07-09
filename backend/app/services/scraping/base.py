"""Scraper abstractions: fetch result contract and source-adapter registry.

New manufacturers/source types are added by registering an adapter — the
pipeline code never changes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class FetchResult:
    url: str
    ok: bool
    status_code: int | None = None
    html: str | None = None
    text: str | None = None            # extracted label-relevant text
    image_urls: list[str] = field(default_factory=list)
    error: str | None = None
    fetcher: str = "httpx"


class SourceAdapter(ABC):
    """One adapter per source_type (manufacturer, retailer, mock, ...)."""

    source_type: str

    @abstractmethod
    def fetch(self, url: str) -> FetchResult:
        """Fetch and extract label-relevant text from the source."""


_REGISTRY: dict[str, SourceAdapter] = {}


def register_adapter(adapter: SourceAdapter) -> None:
    _REGISTRY[adapter.source_type] = adapter


def get_adapter(source_type: str) -> SourceAdapter:
    if source_type not in _REGISTRY:
        raise KeyError(
            f"No source adapter registered for source_type='{source_type}'. "
            f"Available: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[source_type]
