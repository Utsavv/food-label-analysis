"""Google Cloud Vision OCR (requires GOOGLE_APPLICATION_CREDENTIALS)."""
from app.services.ocr.base import OCRProvider, OCRResult


class GoogleVisionOCR(OCRProvider):
    name = "google_vision"

    def extract_text(self, image_path: str) -> OCRResult:
        try:
            from google.cloud import vision
        except ImportError:
            return OCRResult(text="", confidence=0.0, provider=self.name,
                             error="google-cloud-vision not installed (pip install '.[ocr]')")
        try:
            client = vision.ImageAnnotatorClient()
            with open(image_path, "rb") as f:
                image = vision.Image(content=f.read())
            response = client.document_text_detection(image=image)
            if response.error.message:
                return OCRResult(text="", confidence=0.0, provider=self.name, error=response.error.message)
            annotation = response.full_text_annotation
            confidences = [
                page.confidence for page in annotation.pages if page.confidence
            ] or [0.8]
            return OCRResult(
                text=annotation.text,
                confidence=round(sum(confidences) / len(confidences), 3),
                provider=self.name,
            )
        except Exception as exc:  # credentials/network errors
            return OCRResult(text="", confidence=0.0, provider=self.name, error=str(exc))
