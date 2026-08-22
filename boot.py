#!/usr/bin/env python3
from pathlib import Path
import runpy

root = Path(__file__).resolve().parent

# Assemble split frontend if present
parts = sorted(root.glob("app.part*.html"))
if parts:
    html = b"".join(p.read_bytes() for p in parts)
    (root / "index.html").write_bytes(html)
    (root / "frontend.html").write_bytes(html)
    print("assembled", len(html), "from", [p.name for p in parts])

# Force edge-to-edge stylesheet on every HTML shell
link = b'<link rel="stylesheet" href="/static/edge-fix.css">'
for name in ("index.html", "frontend.html", "admin.html"):
    p = root / name
    if not p.exists():
        continue
    data = p.read_bytes()
    if b"edge-fix.css" not in data and b"</head>" in data:
        data = data.replace(b"</head>", link + b"</head>", 1)
        p.write_bytes(data)
        print("injected edge-fix.css into", name)

runpy.run_path(str(root / "server.py"), run_name="__main__")
