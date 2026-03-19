"""Run VIDEX form filler (Playwright). Shared by API and worker."""
import os
import tempfile
from pathlib import Path
from typing import Any

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from automation.form_filler import VidexFormFiller

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = BASE_DIR / "output" / "fields_schema.json"


def run_form_filler(data: dict[str, Any], name: str) -> dict[str, Any]:
    """Run the form filler synchronously. Returns dict with pdf_content (bytes) or error."""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            screenshot_dir = temp_path / "screenshots"
            screenshot_dir.mkdir(exist_ok=True)
            headless = os.environ.get("HEADLESS", "true").lower() in ("1", "true", "yes")
            filler = VidexFormFiller(
                applicant_data=data,
                schema_path=SCHEMA_PATH if SCHEMA_PATH.exists() else None,
                headless=headless,
                slow_mo=0,
                screenshot_on_error=True,
                screenshot_dir=screenshot_dir,
                output_dir=temp_path,
            )
            result = filler.fill_form(submit=False, save_pdf=True)
            pdf_path = result.get("pdf_path")
            if pdf_path and Path(pdf_path).exists():
                result["pdf_content"] = Path(pdf_path).read_bytes()
            return result
    except Exception as e:
        return {"error": str(e), "successful": 0, "failed": 0}
