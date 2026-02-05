"""
CAPTCHA Solver Module - Tesseract OCR (lightweight for Railway <4GB).
Uses pytesseract + Tesseract; no PyTorch/EasyOCR so image stays under 4GB.
"""

import re
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageEnhance

# Tesseract (primary – small image size)
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False


class CaptchaSolver:
    """Solves text-based CAPTCHAs using Tesseract OCR."""

    def __init__(self, save_debug_images: bool = True, **kwargs):
        self.save_debug_images = save_debug_images
        self.debug_dir = Path("captcha_debug")

        if self.save_debug_images:
            self.debug_dir.mkdir(exist_ok=True)

    def preprocess_original(self, img_array: np.ndarray) -> np.ndarray:
        """Return original image scaled up."""
        return self._scale(img_array, 2)

    def preprocess_grayscale(self, img_array: np.ndarray) -> np.ndarray:
        """Convert to grayscale and scale."""
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        return self._scale(gray, 2)

    def preprocess_threshold(self, img_array: np.ndarray) -> np.ndarray:
        """Binary threshold."""
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(thresh) < 127:
            thresh = cv2.bitwise_not(thresh)
        return self._scale(thresh, 2)

    def preprocess_contrast(self, img_array: np.ndarray) -> np.ndarray:
        """Increase contrast."""
        pil_img = Image.fromarray(img_array)
        enhanced = ImageEnhance.Contrast(pil_img).enhance(2.0)
        enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.5)
        return self._scale(np.array(enhanced), 2)

    def _scale(self, img: np.ndarray, scale: int = 2) -> np.ndarray:
        """Scale up image for better OCR."""
        height, width = img.shape[:2]
        return cv2.resize(img, (width * scale, height * scale), interpolation=cv2.INTER_CUBIC)

    def _run_tesseract(self, img: np.ndarray) -> str:
        """Run Tesseract on image; return cleaned text."""
        if not PYTESSERACT_AVAILABLE:
            return ""
        # Tesseract expects RGB or grayscale
        if len(img.shape) == 2:
            pil_img = Image.fromarray(img)
        else:
            pil_img = Image.fromarray(img)
        text = pytesseract.image_to_string(pil_img, config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
        return re.sub(r"[^A-Za-z0-9]", "", text).strip()

    def solve(self, image: Image.Image) -> str:
        """Solve CAPTCHA using Tesseract with multiple preprocessing methods."""
        if not PYTESSERACT_AVAILABLE:
            print("  ❌ pytesseract not available! Install: pip install pytesseract + tesseract-ocr")
            return ""

        print("\n🔍 Analyzing CAPTCHA with Tesseract...")

        if self.save_debug_images:
            image.save(self.debug_dir / "original_captcha.png")

        img_array = np.array(image)
        methods = [
            ("original", self.preprocess_original),
            ("grayscale", self.preprocess_grayscale),
            ("threshold", self.preprocess_threshold),
            ("contrast", self.preprocess_contrast),
        ]

        results = []
        for name, preprocess_func in methods:
            try:
                processed = preprocess_func(img_array)
                if self.save_debug_images and len(processed.shape) == 2:
                    cv2.imwrite(str(self.debug_dir / f"processed_{name}.png"), processed)
                text = self._run_tesseract(processed)
                if text and len(text) >= 3:
                    results.append((text, name))
                    print(f"    [{name}] → '{text}'")
            except Exception as e:
                print(f"    [{name}] Error: {e}")
                continue

        if not results:
            print("  ❌ No valid results from OCR")
            return ""

        from collections import Counter
        text_counts = Counter([r[0] for r in results])
        best_text, count = text_counts.most_common(1)[0]
        print(f"\n  ✓ Best result: '{best_text}' (matched {count}x)")

        # Common correction: trailing g -> 9
        if best_text.endswith("g"):
            corrected = best_text[:-1] + "9"
            print(f"  → Correction: '{best_text}' → '{corrected}'")
            best_text = corrected

        return best_text

    def solve_from_screenshot(self, screenshot_bytes: bytes) -> str:
        """Solve CAPTCHA from screenshot bytes."""
        image = Image.open(BytesIO(screenshot_bytes))
        return self.solve(image)

    def solve_from_file(self, filepath: str) -> str:
        """Solve CAPTCHA from image file."""
        image = Image.open(filepath)
        return self.solve(image)


def test_solver():
    """Test the solver with captured CAPTCHA."""
    solver = CaptchaSolver()
    for path in ["captcha_debug/captured_captcha.png", "captcha_debug/original_captcha.png"]:
        if Path(path).exists():
            print(f"\nTesting: {path}")
            print(f"Result: {solver.solve_from_file(path)}")
            return
    print("No CAPTCHA images found. Run the main script first.")


if __name__ == "__main__":
    test_solver()
