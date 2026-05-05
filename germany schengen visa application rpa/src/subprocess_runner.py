"""
Stand-alone runner: read raw applicant JSON from stdin, drive the VIDEX
form filler in a fresh Python process, and write a single JSON envelope to
the file path passed as argv[1]. The PDF (if produced) is base64-encoded
inside the envelope.

We write the envelope to a side file (not stdout) because `rich.Console`
inside `form_filler` chats freely on stdout during the run; the parent
process needs a clean channel for the structured result.

Why a subprocess at all?
  Playwright's sync_api hangs forever when invoked from inside a thread that
  was spawned from an asyncio-aware framework (uvicorn / FastAPI / Starlette
  via anyio). Running the same code in a brand-new child process — which has
  its own Python interpreter and no inherited event loop — is the documented
  workaround. The cost is one extra `fork+exec`, ~50 MB RSS, and a few
  hundred milliseconds of startup, all negligible compared to the ~85 s VIDEX
  run itself.

Envelope schema:
  {
    "success_count": int,
    "fail_count": int,
    "fields": { field_id: bool, ... },
    "validation_error": str | null,
    "error": str | null,
    "pdf_base64": str | null,
  }
"""

import base64
import json
import sys
import traceback
from pathlib import Path

# Make `src/...` imports work no matter where this module is launched from.
sys.path.insert(0, str(Path(__file__).parent))


def _emit(envelope_path: Path, envelope: dict) -> None:
    """Atomically write the envelope to the given file path."""
    tmp = envelope_path.with_suffix(envelope_path.suffix + ".tmp")
    tmp.write_text(json.dumps(envelope), encoding="utf-8")
    tmp.replace(envelope_path)


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("usage: subprocess_runner.py <envelope_out_path>\n")
        return 64
    envelope_path = Path(sys.argv[1])

    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception as e:
        _emit(envelope_path, {
            "error": f"bad stdin JSON: {e}",
            "success_count": 0,
            "fail_count": 0,
        })
        return 2

    try:
        from prepare_fill import build_translated_data  # noqa: WPS433
        from form_runner import run_form_filler  # noqa: WPS433

        translated_data, full_name = build_translated_data(data)
        result = run_form_filler(translated_data, full_name)
    except Exception as e:
        _emit(envelope_path, {
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(),
            "success_count": 0,
            "fail_count": 0,
        })
        return 1

    pdf_b64 = None
    if result.get("pdf_content"):
        pdf_b64 = base64.b64encode(result["pdf_content"]).decode("ascii")

    envelope = {
        "success_count": result.get("success_count", result.get("successful", 0)),
        "fail_count": result.get("fail_count", result.get("failed", 0)),
        "fields": result.get("fields") or {},
        "validation_error": result.get("validation_error"),
        "invalid_wrappers": result.get("invalid_wrappers") or [],
        "error": result.get("error"),
        "pdf_base64": pdf_b64,
    }
    _emit(envelope_path, envelope)
    return 0


if __name__ == "__main__":
    sys.exit(main())
