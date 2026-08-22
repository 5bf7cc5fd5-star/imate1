#!/usr/bin/env python3
from pathlib import Path
import runpy

root = Path(__file__).resolve().parent
(root / "static").mkdir(exist_ok=True)

NAV_STYLE = """
<style id=\"nav-row-live\">
nav.bottom{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;align-items:flex-end!important;justify-content:space-between!important;position:fixed!important;left:0!important;right:0!important;bottom:0!important;width:100%!important;z-index:90!important;transform:none!important}
nav.bottom>.nav,nav.bottom button.nav{position:relative!important;left:auto!important;right:auto!important;top:0!important;width:20%!important;flex:1 1 20%!important;display:flex!important;flex-direction:column!important;align-items:center!important;justify-content:flex-end!important;height:52px!important;margin:0!important;border:0!important;background:transparent!important;transform:none!important;float:none!important}
nav.bottom>.nav.nav-center{position:relative!important;left:auto!important;right:auto!important;top:0!important;transform:none!important}
</style>
"""

SCRIPT = '<script src="/static/market-data.js?v=10"></script>'

def fix_html(text):
    text = text.replace("nav.bottom,.nav, .bottom-nav", "nav.bottom,.bottom-nav")
    text = text.replace("nav.bottom,.nav{", "nav.bottom{")
    text = text.replace("top:-14px;", "top:0!important;")
    if "nav-row-live" not in text and "</body>" in text:
        text = text.replace("</body>", NAV_STYLE + "</body>", 1)
    if "market-data.js" not in text and "</body>" in text:
        text = text.replace("</body>", SCRIPT + "\n</body>", 1)
    elif "market-data.js" not in text and "</head>" in text:
        text = text.replace("</head>", SCRIPT + "\n</head>", 1)
    return text

for name in ("index.html", "frontend.html"):
    p = root / name
    if p.exists():
        old = p.read_text(encoding="utf-8", errors="replace")
        new = fix_html(old)
        if new != old:
            p.write_text(new, encoding="utf-8")
            print("html fixed", name, len(new))

print("boot starting server")
runpy.run_path(str(root / "server.py"), run_name="__main__")
