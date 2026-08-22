#!/usr/bin/env python3
from pathlib import Path
import runpy

root = Path(__file__).resolve().parent
(root / "static").mkdir(exist_ok=True)

INJECT = """
<link rel=\"stylesheet\" href=\"/static/edge-fix.css?v=12\">
<script src=\"/static/market-data.js?v=12\"></script>
<script src=\"/static/lock-nav.js?v=12\"></script>
<style id=\"lock-tabs\">
nav.bottom{position:fixed!important;left:0!important;right:0!important;bottom:0!important;top:auto!important;width:100vw!important;margin:0!important;padding:0!important;transform:none!important;z-index:2147483647!important}
</style>
"""

def fix_html(text):
    text = text.replace("nav.bottom,.nav{", "nav.bottom{")
    text = text.replace("top:-14px;", "top:0!important;")
    if "lock-nav.js?v=12" not in text:
        if "</body>" in text:
            text = text.replace("</body>", INJECT + "\n</body>", 1)
        elif "</head>" in text:
            text = text.replace("</head>", INJECT + "\n</head>", 1)
    return text

for name in ("index.html", "frontend.html"):
    p = root / name
    if p.exists():
        old = p.read_text(encoding="utf-8", errors="replace")
        new = fix_html(old)
        if new != old:
            p.write_text(new, encoding="utf-8")
            print("html fixed", name)

print("boot starting server")
runpy.run_path(str(root / "server.py"), run_name="__main__")
