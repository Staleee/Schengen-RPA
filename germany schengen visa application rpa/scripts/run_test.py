"""
Test the Germany VIDEX API: start server, POST example JSON to /fill, save PDF.

Run from project root (germany schengen visa application rpa):
  python scripts/run_test.py

Requires: pip install requests (or use urllib)
"""

import json
import subprocess
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
API_URL = "http://localhost:8000"
HEALTH_URL = f"{API_URL}/health"
FILL_URL = f"{API_URL}/fill"
DATA_FILE = PROJECT_ROOT / "output" / "mandatory_fields_example.json"
OUTPUT_PDF = PROJECT_ROOT / "test_output.pdf"
MAX_WAIT = 30
POLL_INTERVAL = 0.5


def wait_for_api() -> bool:
    """Wait for the API to respond to /health."""
    start = time.monotonic()
    while (time.monotonic() - start) < MAX_WAIT:
        try:
            if requests:
                r = requests.get(HEALTH_URL, timeout=2)
                if r.status_code == 200:
                    return True
            else:
                import urllib.request
                req = urllib.request.Request(HEALTH_URL, method="GET")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        return True
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)
    return False


def post_fill_and_save() -> bool:
    """POST JSON to /fill and save PDF. Returns True on success."""
    if not DATA_FILE.exists():
        print(f"Data file not found: {DATA_FILE}")
        return False

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Remove comment keys so the API gets clean JSON
    data = {k: v for k, v in data.items() if not k.startswith("_")}

    try:
        if requests:
            r = requests.post(FILL_URL, json=data, timeout=120)
            if r.status_code != 200:
                print(f"API error {r.status_code}: {r.text[:500]}")
                return False
            content = r.content
            ct = r.headers.get("Content-Type", "")
        else:
            import urllib.request
            req = urllib.request.Request(
                FILL_URL,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                content = resp.read()
                ct = resp.headers.get("Content-Type", "")
            if resp.status != 200:
                print(f"API error {resp.status}")
                return False

        if "application/pdf" in ct or not ct:
            OUTPUT_PDF.write_bytes(content)
            print(f"PDF saved: {OUTPUT_PDF}")
            return True
        # Maybe JSON error response
        try:
            err = json.loads(content.decode("utf-8"))
            print("API returned JSON (error?):", err)
        except Exception:
            print("Response (first 200 chars):", content[:200])
        return False
    except Exception as e:
        print(f"Request failed: {e}")
        return False


def main() -> int:
    print("Germany VIDEX RPA – API test")
    print("Project root:", PROJECT_ROOT)
    print()

    # Start API in subprocess
    print("Starting API (python -m src.api)...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "src.api"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env={**__import__("os").environ, "HEADLESS": "true"},
    )

    try:
        print("Waiting for API to be ready...")
        if not wait_for_api():
            print("API did not become ready in time.")
            return 1
        print("API is ready.")

        ok = post_fill_and_save()
        return 0 if ok else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        if proc.stderr:
            err = proc.stderr.read().decode("utf-8", errors="replace")
            if err.strip():
                print("API stderr:", err[:500])


if __name__ == "__main__":
    sys.exit(main())
