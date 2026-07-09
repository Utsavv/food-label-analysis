"""Tesseract OCR fallback (requires the tesseract binary + pytesseract)."""
from app.services.ocr.base import OCRProvider, OCRResult


class TesseractOCR(OCRProvider):
    name = "tesseract"

    def extract_text(self, image_path: str) -> OCRResult:
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            return OCRResult(text="", confidence=0.0, provider=self.name,
                             error="pytesseract/Pillow not installed (pip install '.[ocr]')")
        try:
            image = Image.open(image_path)
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            words = [w for w in data["text"] if w.strip()]
            confs = [float(c) for c in data["conf"] if str(c) not in ("-1", "")]
            confidence = round(sum(confs) / len(confs) / 100.0, 3) if confs else 0.0
            return OCRResult(text=" ".join(words), confidence=confidence, provider=self.name)
        except Exception as exc:
            return OCRResult(text="", confidence=0.0, provider=self.name, error=str(exc))
