"""OCR abstraction. Provider chosen by OCR_PROVIDER env: mock | tesseract | google_vision."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OCRResult:
    text: str
    confidence: float
    provider: str
    error: str | None = None


class OCRProvider(ABC):
    name: str

    @abstractmethod
    def extract_text(self, image_path: str) -> OCRResult:
        """Run OCR on a local image file."""


def get_ocr_provider() -> OCRProvider:
    from app.config import get_settings

    provider = get_settings().ocr_provider.lower()
    if provider == "google_vision":
        from app.services.ocr.google_vision_ocr import GoogleVisionOCR

        return GoogleVisionOCR()
    if provider == "tesseract":
        from app.services.ocr.tesseract_ocr import TesseractOCR

        return TesseractOCR()
    from app.services.ocr.mock_ocr import MockOCR

    return MockOCR()
