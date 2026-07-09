"""Evidence storage: raw HTML snapshots, label text, and downloaded label images.

Filesystem-backed for MVP; the interface maps directly onto GCS for production.
"""
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class ArtifactStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or get_settings().artifact_path

    def _run_dir(self, product_id: int, run_id: int) -> Path:
        d = self.base_dir / f"product_{product_id}" / f"run_{run_id}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_snapshot(self, product_id: int, run_id: int, html: str | None, text: str | None) -> str:
        """Store the source snapshot (HTML where legally safe, plus extracted text)."""
        run_dir = self._run_dir(product_id, run_id)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if html:
            (run_dir / f"snapshot_{stamp}.html").write_text(html, encoding="utf-8")
        if text:
            (run_dir / f"label_text_{stamp}.txt").write_text(text, encoding="utf-8")
        return str(run_dir)

    def save_images(self, product_id: int, run_id: int, image_urls: list[str],
                    user_agent: str, max_images: int = 5) -> list[str]:
        """Download label images as evidence. Failures are logged, not fatal."""
        run_dir = self._run_dir(product_id, run_id)
        saved: list[str] = []
        for i, url in enumerate(image_urls[:max_images]):
            try:
                resp = httpx.get(url, headers={"User-Agent": user_agent}, timeout=20.0, follow_redirects=True)
                if resp.status_code != 200:
                    continue
                suffix = Path(url.split("?")[0]).suffix or ".jpg"
                path = run_dir / f"label_image_{i}{suffix}"
                path.write_bytes(resp.content)
                saved.append(str(path))
            except httpx.HTTPError as exc:
                logger.warning("Failed to download label image %s: %s", url, exc)
        return saved
