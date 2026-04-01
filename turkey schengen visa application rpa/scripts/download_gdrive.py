import re
import sys
from pathlib import Path

import requests


def download(file_id: str, out_path: Path) -> None:
    s = requests.Session()
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    r = s.get(url)
    r.raise_for_status()

    # If direct download, it's already the bytes.
    if r.content[:4] == b"%PDF":
        out_path.write_bytes(r.content)
        return

    html = r.text
    m = re.search(r"confirm=([0-9A-Za-z_\-]+)", html) or re.search(r'name="confirm"\s+value="([0-9A-Za-z_\-]+)"', html)
    confirm = m.group(1) if m else None

    if confirm:
        url2 = f"https://drive.google.com/uc?export=download&confirm={confirm}&id={file_id}"
        r2 = s.get(url2)
        r2.raise_for_status()
        out_path.write_bytes(r2.content)
        return

    # Fallback: just write what we got (may be HTML if permissions block)
    out_path.write_bytes(r.content)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python download_gdrive.py <file_id> <out_path>")
        raise SystemExit(2)
    fid = sys.argv[1]
    out = Path(sys.argv[2]).expanduser().resolve()
    download(fid, out)
    head = out.read_bytes()[:12]
    print(f"wrote {out} bytes={out.stat().st_size} head={head!r}")

