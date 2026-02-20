"""
CAPTCHA Solver – ddddocr (best) → EasyOCR → Tesseract.
ddddocr is built for CAPTCHAs; use it when installed for much better accuracy.
"""

import re
from io import BytesIO
from pathlib import Path
from collections import Counter

import cv2
import numpy as np
from PIL import Image, ImageEnhance

# ddddocr – built for CAPTCHAs, best accuracy
try:
    import ddddocr
    DDDDOCR_AVAILABLE = True
    _ddddocr_instance = None
except ImportError:
    DDDDOCR_AVAILABLE = False
    _ddddocr_instance = None

# EasyOCR (good when ddddocr not installed)
try:
    import easyocr
    EASYOCR_AVAILABLE = True
    _easyocr_reader = None
except ImportError:
    EASYOCR_AVAILABLE = False
    _easyocr_reader = None

# Tesseract (fallback / Railway)
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False


def _get_ddddocr():
    global _ddddocr_instance
    if _ddddocr_instance is None and DDDDOCR_AVAILABLE:
        print("  → Loading ddddocr (first time)...")
        _ddddocr_instance = ddddocr.DdddOcr()
    return _ddddocr_instance


def _get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None and EASYOCR_AVAILABLE:
        print("  → Loading EasyOCR (first time)...")
        _easyocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _easyocr_reader


class CaptchaSolver:
    """Solves text CAPTCHAs: ddddocr (best) → EasyOCR → Tesseract."""

    def __init__(self, save_debug_images: bool = True, **kwargs):
        self.save_debug_images = save_debug_images
        self.debug_dir = Path("captcha_debug")
        if self.save_debug_images:
            self.debug_dir.mkdir(exist_ok=True)

    def _scale(self, img: np.ndarray, scale: int = 2) -> np.ndarray:
        h, w = img.shape[:2]
        return cv2.resize(img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

    def preprocess_original(self, img_array: np.ndarray) -> np.ndarray:
        return self._scale(img_array, 2)

    def preprocess_grayscale(self, img_array: np.ndarray) -> np.ndarray:
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        gray = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB) if len(gray.shape) == 2 else gray
        return self._scale(gray, 2)

    def preprocess_threshold(self, img_array: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(thresh) < 127:
            thresh = cv2.bitwise_not(thresh)
        thresh_rgb = cv2.cvtColor(thresh, cv2.COLOR_GRAY2RGB)
        return self._scale(thresh_rgb, 2)

    def preprocess_contrast(self, img_array: np.ndarray) -> np.ndarray:
        pil = Image.fromarray(img_array)
        pil = ImageEnhance.Contrast(pil).enhance(2.0)
        pil = ImageEnhance.Sharpness(pil).enhance(1.5)
        return self._scale(np.array(pil), 2)

    def preprocess_denoise(self, img_array: np.ndarray) -> np.ndarray:
        try:
            denoised = cv2.fastNlMeansDenoisingColored(img_array, None, 10, 10, 7, 21)
            return self._scale(denoised, 2)
        except Exception:
            return self._scale(img_array, 2)

    # ---------- EasyOCR ----------
    def _solve_easyocr(self, img_array: np.ndarray) -> list:
        """Return list of (text, method_name) from EasyOCR."""
        reader = _get_easyocr_reader()
        if reader is None:
            return []
        results = []
        methods = [
            ("original", self.preprocess_original),
            ("grayscale", self.preprocess_grayscale),
            ("threshold", self.preprocess_threshold),
            ("contrast", self.preprocess_contrast),
            ("denoise", self.preprocess_denoise),
        ]
        for name, func in methods:
            try:
                proc = func(img_array)
                if len(proc.shape) == 2:
                    proc = cv2.cvtColor(proc, cv2.COLOR_GRAY2RGB)
                out = reader.readtext(proc, detail=0, paragraph=False)
                for t in out:
                    cleaned = re.sub(r"[^A-Za-z0-9]", "", t)
                    if cleaned and 3 <= len(cleaned) <= 12:
                        results.append((cleaned, name))
            except Exception:
                continue
        return results

    # ---------- Tesseract (multiple PSM for better result) ----------
    def _run_tesseract(self, img: np.ndarray, psm: int = 7) -> str:
        if not PYTESSERACT_AVAILABLE:
            return ""
        if len(img.shape) == 2:
            pil = Image.fromarray(img)
        else:
            pil = Image.fromarray(img)
        cfg = f"--psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        text = pytesseract.image_to_string(pil, config=cfg)
        return re.sub(r"[^A-Za-z0-9]", "", text).strip()

    def _solve_tesseract(self, img_array: np.ndarray) -> list:
        """Return list of (text, method_name) from Tesseract with multiple PSM."""
        results = []
        methods = [
            ("original", self.preprocess_original),
            ("grayscale", self.preprocess_grayscale),
            ("threshold", self.preprocess_threshold),
            ("contrast", self.preprocess_contrast),
        ]
        psms = [7, 8, 13]  # 7=line, 8=word, 13=raw
        for name, func in methods:
            try:
                proc = func(img_array)
                for psm in psms:
                    text = self._run_tesseract(proc, psm=psm)
                    if text and 3 <= len(text) <= 12:
                        results.append((text, f"{name}_psm{psm}"))
            except Exception:
                continue
        return results

    # ---------- ddddocr (CAPTCHA-specific, best) ----------
    def _solve_ddddocr(self, img_bytes: bytes) -> str:
        """Single result from ddddocr; returns '' if unavailable or invalid."""
        ocr = _get_ddddocr()
        if ocr is None:
            return ""
        try:
            raw = ocr.classification(img_bytes=img_bytes)
            if not raw:
                return ""
            cleaned = re.sub(r"[^A-Za-z0-9]", "", str(raw).strip())
            if 3 <= len(cleaned) <= 12:
                return cleaned
            return ""
        except Exception:
            return ""

    def solve(self, image: Image.Image) -> str:
        if not DDDDOCR_AVAILABLE and not EASYOCR_AVAILABLE and not PYTESSERACT_AVAILABLE:
            print("  ❌ No OCR available. Install: pip install ddddocr (recommended) or pytesseract (+ tesseract-ocr)")
            return ""

        if self.save_debug_images:
            image.save(self.debug_dir / "original_captcha.png")

        buf = BytesIO()
        image.save(buf, format="PNG")
        img_bytes = buf.getvalue()
        img_array = np.array(image)

        # 1) ddddocr first (best for CAPTCHAs)
        if DDDDOCR_AVAILABLE:
            print("\n🔍 Analyzing CAPTCHA with ddddocr...")
            d4 = self._solve_ddddocr(img_bytes)
            if d4:
                print(f"  ✓ Result: '{d4}'")
                return d4
            print("  → ddddocr returned nothing, trying fallback...")

        # 2) EasyOCR
        if EASYOCR_AVAILABLE:
            print("\n🔍 Analyzing CAPTCHA with EasyOCR...")
            results = self._solve_easyocr(img_array)
            if results:
                texts = [r[0] for r in results]
                counts = Counter(texts)
                best_text, count = counts.most_common(1)[0]
                print(f"  ✓ Best result: '{best_text}' (matched {count}x)")
                return best_text

        # 3) Tesseract
        if PYTESSERACT_AVAILABLE:
            print("\n🔍 Analyzing CAPTCHA with Tesseract...")
            results = self._solve_tesseract(img_array)
            for t, name in results[:10]:
                print(f"    [{name}] → '{t}'")
            if results:
                texts = [r[0] for r in results]
                counts = Counter(texts)
                best_text, count = counts.most_common(1)[0]
                print(f"\n  ✓ Best result: '{best_text}' (matched {count}x)")
                return best_text

        print("  ❌ No valid OCR result")
        return ""

    def solve_from_screenshot(self, screenshot_bytes: bytes) -> str:
        return self.solve(Image.open(BytesIO(screenshot_bytes)))

    def solve_from_file(self, filepath: str) -> str:
        return self.solve(Image.open(filepath))


def test_solver():
    solver = CaptchaSolver()
    for path in ["captcha_debug/captured_captcha.png", "captcha_debug/original_captcha.png"]:
        if Path(path).exists():
            print(f"\nTesting: {path}")
            print(f"Result: {solver.solve_from_file(path)}")
            return
    print("No CAPTCHA images found. Run the main script first.")


if __name__ == "__main__":
    test_solver()
