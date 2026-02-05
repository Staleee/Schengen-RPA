"""
CAPTCHA Solver Module - EasyOCR
===============================
Solves text-based CAPTCHAs using EasyOCR (no external dependencies needed).
"""

import re
import ssl
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

# Fix SSL certificate issue on macOS
ssl._create_default_https_context = ssl._create_unverified_context

# EasyOCR
try:
    import easyocr
    EASYOCR_AVAILABLE = True
    # Initialize reader once (lazy load)
    _reader = None
except ImportError:
    EASYOCR_AVAILABLE = False
    _reader = None


def get_reader():
    """Get or create EasyOCR reader (lazy initialization)."""
    global _reader
    if _reader is None and EASYOCR_AVAILABLE:
        print("  → Loading OCR model (first time only)...")
        _reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _reader


class CaptchaSolver:
    """Solves text-based CAPTCHAs using EasyOCR."""
    
    def __init__(self, save_debug_images: bool = True, **kwargs):
        self.save_debug_images = save_debug_images
        self.debug_dir = Path("captcha_debug")
        
        if self.save_debug_images:
            self.debug_dir.mkdir(exist_ok=True)
    
    def preprocess_original(self, img_array: np.ndarray) -> np.ndarray:
        """Return original image scaled up."""
        return self.scale_image(img_array, 2)
    
    def preprocess_grayscale(self, img_array: np.ndarray) -> np.ndarray:
        """Convert to grayscale and scale."""
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            gray = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)  # Back to 3 channel for easyocr
        else:
            gray = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
        return self.scale_image(gray, 2)
    
    def preprocess_threshold(self, img_array: np.ndarray) -> np.ndarray:
        """Binary threshold."""
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(thresh) < 127:
            thresh = cv2.bitwise_not(thresh)
        thresh_rgb = cv2.cvtColor(thresh, cv2.COLOR_GRAY2RGB)
        return self.scale_image(thresh_rgb, 2)
    
    def preprocess_contrast(self, img_array: np.ndarray) -> np.ndarray:
        """Increase contrast."""
        pil_img = Image.fromarray(img_array)
        enhanced = ImageEnhance.Contrast(pil_img).enhance(2.0)
        enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.5)
        return self.scale_image(np.array(enhanced), 2)
    
    def preprocess_denoise(self, img_array: np.ndarray) -> np.ndarray:
        """Denoise the image."""
        denoised = cv2.fastNlMeansDenoisingColored(img_array, None, 10, 10, 7, 21)
        return self.scale_image(denoised, 2)
    
    def scale_image(self, img: np.ndarray, scale: int = 2) -> np.ndarray:
        """Scale up image for better OCR."""
        height, width = img.shape[:2]
        return cv2.resize(img, (width * scale, height * scale), interpolation=cv2.INTER_CUBIC)
    
    def solve(self, image: Image.Image) -> str:
        """
        Solve CAPTCHA using EasyOCR with multiple preprocessing methods.
        """
        if not EASYOCR_AVAILABLE:
            print("  ❌ EasyOCR not available!")
            print("     Install: pip install easyocr")
            return ""
        
        print("\n🔍 Analyzing CAPTCHA with OCR...")
        
        # Save original
        if self.save_debug_images:
            image.save(self.debug_dir / "original_captcha.png")
        
        img_array = np.array(image)
        reader = get_reader()
        
        if reader is None:
            print("  ❌ Failed to initialize OCR reader")
            return ""
        
        # Preprocessing methods
        methods = [
            ("original", self.preprocess_original),
            ("grayscale", self.preprocess_grayscale),
            ("threshold", self.preprocess_threshold),
            ("contrast", self.preprocess_contrast),
            ("denoise", self.preprocess_denoise),
        ]
        
        results = []
        
        for name, preprocess_func in methods:
            try:
                processed = preprocess_func(img_array)
                
                # Save debug image
                if self.save_debug_images:
                    cv2.imwrite(str(self.debug_dir / f"processed_{name}.png"), 
                               cv2.cvtColor(processed, cv2.COLOR_RGB2BGR))
                
                # Run EasyOCR
                ocr_results = reader.readtext(processed, detail=0, paragraph=False)
                
                for text in ocr_results:
                    # Clean - keep only alphanumeric
                    cleaned = re.sub(r'[^A-Za-z0-9]', '', text)
                    if cleaned and len(cleaned) >= 3:
                        results.append((cleaned, name))
                        print(f"    [{name}] → '{cleaned}'")
                
            except Exception as e:
                print(f"    [{name}] Error: {e}")
                continue
        
        if not results:
            print("  ❌ No valid results from OCR")
            return ""
        
        # Find most common result
        from collections import Counter
        text_counts = Counter([r[0] for r in results])
        best_text, count = text_counts.most_common(1)[0]
        
        print(f"\n  ✓ Best result: '{best_text}' (matched {count}x)")
        
        # Post-process: try common OCR corrections
        # Many CAPTCHAs are case-insensitive, so we also generate variants
        corrections = {
            'g': '9', 'q': '9', 'G': '9',  # g/q often confused with 9
            'O': '0', 'o': '0', 'D': '0',  # O/o confused with 0
            'l': '1', 'I': '1', 'i': '1',  # l/I confused with 1
            'S': '5', 's': '5',            # S confused with 5
            'Z': '2', 'z': '2',            # Z confused with 2
            'B': '8',                       # B confused with 8
        }
        
        # Apply most common correction: trailing g -> 9
        if best_text.endswith('g'):
            corrected = best_text[:-1] + '9'
            print(f"  → Correction applied: '{best_text}' → '{corrected}'")
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
    
    test_files = [
        "captcha_debug/captured_captcha.png",
        "captcha_debug/original_captcha.png",
    ]
    
    for path in test_files:
        if Path(path).exists():
            print(f"\nTesting: {path}")
            result = solver.solve_from_file(path)
            print(f"\nFinal Result: {result}")
            return
    
    print("No CAPTCHA images found. Run the main script first.")


if __name__ == "__main__":
    test_solver()
