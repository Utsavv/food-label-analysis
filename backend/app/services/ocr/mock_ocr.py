"""Mock OCR for local development: returns sidecar .txt content if present."""
from pathlib import Path

from app.services.ocr.base import OCRProvider, OCRResult


class MockOCR(OCRProvider):
    """Reads `<image>.txt` next to the image as the 'OCR result'.

    Lets tests and demos exercise the OCR code path without any OCR engine.
    """

    name = "mock"

    def extract_text(self, image_path: str) -> OCRResult:
        sidecar = Path(image_path).with_suffix(".txt")
        if sidecar.exists():
            return OCRResult(text=sidecar.read_text(encoding="utf-8"), confidence=0.99, provider=self.name)
        return OCRResult(
            text="", confidence=0.0, provider=self.name,
            error=f"Mock OCR: no sidecar text file for {Path(image_path).name}",
        )
