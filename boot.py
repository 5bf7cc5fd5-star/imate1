#!/usr/bin/env python3
"""Start Own Club. Do NOT assemble frontend.part* — those parts are the old dark login."""
from pathlib import Path
import runpy

root = Path(__file__).resolve().parent
(root / "static").mkdir(exist_ok=True)

# Copy market feed into static if needed
src = root / "static" / "market-data.js"
alt = root / "market-data.js"
if (not src.exists() or src.stat().st_size < 200) and alt.exists() and alt.stat().st_size > 200:
    src.write_bytes(alt.read_bytes())
    print("copied market-data.js -> static/")

# Inject live market clubs into the Wiyak HTML
try:
    pm = root / "patch_market.py"
    if pm.exists():
        runpy.run_path(str(pm), run_name="__market_patch__")
except Exception as e:
    print("patch_market failed", e)

for name in ("index.html", "frontend.html"):
    p = root / name
    if not p.exists():
        continue
    data = p.read_bytes()
    extra = b""
    if b"edge-fix.css" not in data:
        extra += b'<link rel="stylesheet" href="/static/edge-fix.css">'
    if b"/static/market-data.js" not in data:
        extra += b'<script src="/static/market-data.js" defer></script>'
    if extra and b"</head>" in data:
        data = data.replace(b"</head>", extra + b"</head>", 1)
        p.write_bytes(data)
        print("injected tags into", name)

print("boot: serving Wiyak index, no part-assemble")
runpy.run_path(str(root / "server.py"), run_name="__main__")
