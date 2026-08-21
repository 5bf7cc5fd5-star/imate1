#!/usr/bin/env python3
import base64, gzip
from pathlib import Path
root = Path(__file__).resolve().parent
parts = sorted((root / "static").glob("aug14-*.b64"))
if parts:
    blob = "".join(p.read_text(encoding="ascii") for p in parts)
    html = gzip.decompress(base64.b64decode(blob))
    (root / "index.html").write_bytes(html)
    (root / "frontend.html").write_bytes(html)
import runpy
runpy.run_path(str(root / "server.py"), run_name="__main__")
