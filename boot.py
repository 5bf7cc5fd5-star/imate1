#!/usr/bin/env python3
from pathlib import Path
import runpy

root = Path(__file__).resolve().parent

parts = sorted(root.glob("app.part*.html"))
if not parts:
    parts = sorted(root.glob("frontend.part*.html"))
if parts:
    html = b"".join(p.read_bytes() for p in parts)
    (root / "index.html").write_bytes(html)
    (root / "frontend.html").write_bytes(html)
    print("assembled", len(html), "from", [p.name for p in parts])

for name in ("index.html", "frontend.html", "admin.html"):
    p = root / name
    if not p.exists():
        continue
    data = p.read_bytes()
    extra = b""
    if b"edge-fix.css" not in data:
        extra += b'<link rel="stylesheet" href="/static/edge-fix.css">'
    if b"market-data.js" not in data:
        extra += b'<script src="/static/market-data.js"></script>'
    if extra and b"</head>" in data:
        data = data.replace(b"</head>", extra + b"</head>", 1)
        p.write_bytes(data)
        print("injected tags into", name)

runpy.run_path(str(root / "server.py"), run_name="__main__")
