#!/usr/bin/env python3
from pathlib import Path
import runpy
root = Path(__file__).resolve().parent
parts = sorted(root.glob("app.part*.html"))
if parts:
    html = b"".join(p.read_bytes() for p in parts)
    (root / "index.html").write_bytes(html)
    (root / "frontend.html").write_bytes(html)
    print("assembled", len(html), "from", [p.name for p in parts])
runpy.run_path(str(root / "server.py"), run_name="__main__")
