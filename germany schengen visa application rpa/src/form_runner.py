"""Run VIDEX form filler (Playwright). Shared by API and worker."""
import os
import shutil
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from automation.form_filler import VidexFormFiller

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = BASE_DIR / "output" / "fields_schema.json"


def _debug_dir() -> Path | None:
    """When DEBUG_OUT_DIR is set, persist screenshots/PDF there per request."""
    raw = os.environ.get("DEBUG_OUT_DIR", "").strip()
    if not raw:
        return None
    base = Path(raw)
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out = base / stamp
    out.mkdir(parents=True, exist_ok=True)
    return out


def run_form_filler(data: dict[str, Any], name: str) -> dict[str, Any]:
    """Run the form filler synchronously. Returns dict with pdf_content (bytes) or error."""
    debug_out = _debug_dir()
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # When DEBUG_OUT_DIR is set, write screenshots straight to the
            # persistent debug folder so they survive even if fill_form raises.
            if debug_out:
                screenshot_dir = debug_out / "screenshots"
            else:
                screenshot_dir = temp_path / "screenshots"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
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
            if debug_out:
                try:
                    if pdf_path and Path(pdf_path).exists():
                        shutil.copy(pdf_path, debug_out / Path(pdf_path).name)
                    fields_map = result.get("fields") or {}
                    failed = sorted([fid for fid, ok in fields_map.items() if not ok])
                    (debug_out / "result.txt").write_text(
                        f"success_count={result.get('success_count')}\n"
                        f"fail_count={result.get('fail_count')}\n"
                        f"pdf_path={pdf_path}\n"
                        f"failed_fields=\n  " + "\n  ".join(failed),
                        encoding="utf-8",
                    )
                except Exception as copy_err:
                    print(f"[debug] copy to {debug_out} failed: {copy_err}", flush=True)
            return result
    except Exception as e:
        if debug_out:
            try:
                (debug_out / "exception.txt").write_text(
                    f"{e}\n\n{traceback.format_exc()}", encoding="utf-8"
                )
            except Exception:
                pass
        return {"error": str(e), "successful": 0, "failed": 0}
